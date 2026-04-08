"""The 'axiom sync' command for bidirectional spec-code synchronization.

When generated code has been hand-edited, this command analyzes the changes
and suggests corresponding spec updates. This enables a workflow where
developers can experiment with code and then "sync back" to the spec.

This is a paradigm shift: the spec-code relationship becomes bidirectional.
"""

from __future__ import annotations

import ast
import difflib
from pathlib import Path
from typing import Any

import click
import structlog

from axiom.cache import AXIOM_VERSION, CacheStore
from axiom.config import load_settings
from axiom.spec import parse_spec_file
from axiom.spec.models import Example, ExpectedOutput, Invariant

logger = structlog.get_logger()


@click.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option(
    "--apply",
    is_flag=True,
    help="Apply suggested changes to the spec file",
)
@click.option(
    "--show-code-diff",
    is_flag=True,
    help="Show the code diff that was analyzed",
)
@click.pass_context
def sync(
    ctx: click.Context,
    spec_path: str,
    apply: bool,
    show_code_diff: bool,
) -> None:
    """Suggest spec updates based on code changes.

    When you've edited generated code, this command analyzes the changes
    and suggests corresponding updates to the spec. This enables:

    1. Experiment with code, then formalize changes in specs
    2. Fix bugs in generated code, then update spec to prevent regression
    3. Add features to code, then capture in spec for documentation

    \\b
    Examples:
      axiom sync specs/validate_email.axiom
      axiom sync specs/validate_email.axiom --apply
      axiom sync specs/ --show-code-diff
    """
    settings = load_settings()
    path = Path(spec_path)

    # Handle directory
    if path.is_dir():
        spec_files = list(path.glob("**/*.axiom"))
    else:
        spec_files = [path]

    if not spec_files:
        raise click.ClickException(f"No .axiom files found in {path}")

    for spec_file in spec_files:
        _sync_spec(spec_file, settings, apply, show_code_diff)


def _sync_spec(
    spec_path: Path,
    settings: Any,
    apply: bool,
    show_code_diff: bool,
) -> None:
    """Analyze and sync a single spec.

    Args:
        spec_path: Path to the spec file.
        settings: Axiom settings.
        apply: Whether to apply changes.
        show_code_diff: Whether to show code diff.
    """
    # Parse spec
    try:
        spec = parse_spec_file(spec_path)
    except Exception as e:
        click.echo(f"  ✗ Could not parse {spec_path.name}: {e}")
        return

    # Find generated code
    generated_dir = settings.get_generated_dir()
    generated_path = generated_dir / f"{spec.metadata.name}.py"

    if not generated_path.exists():
        click.echo(f"  ○ {spec_path.name}: No generated code found")
        return

    # Get cached code
    cache_store = CacheStore(settings.get_cache_dir())
    model = settings.get_model_for_target(spec.metadata.target)
    cache_status = cache_store.lookup(spec, model, AXIOM_VERSION)

    if not cache_status.hit or not cache_status.entry:
        click.echo(f"  ○ {spec_path.name}: Not in cache, cannot compare")
        return

    cached_code = cache_status.entry.code
    current_code = generated_path.read_text(encoding="utf-8")

    # Check for changes
    if cached_code == current_code:
        click.echo(f"  ✓ {spec_path.name}: No changes detected")
        return

    click.echo(f"  ✗ {spec_path.name}: DRIFT DETECTED")
    click.echo("")

    # Show diff if requested
    if show_code_diff:
        diff = difflib.unified_diff(
            cached_code.splitlines(keepends=True),
            current_code.splitlines(keepends=True),
            fromfile="cached",
            tofile="current",
            lineterm="",
        )
        click.echo("    Code diff:")
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                click.echo(f"      {click.style(line.rstrip(), fg='green')}")
            elif line.startswith("-") and not line.startswith("---"):
                click.echo(f"      {click.style(line.rstrip(), fg='red')}")
            else:
                click.echo(f"      {line.rstrip()}")
        click.echo("")

    # Analyze changes and suggest spec updates
    suggestions = _analyze_changes(spec, cached_code, current_code)

    if not suggestions:
        click.echo("    No spec updates suggested.")
        click.echo("    The changes may be formatting or comments only.")
        return

    click.echo("    Suggested spec updates:")
    for suggestion in suggestions:
        click.echo(f"      • {suggestion['description']}")
        if suggestion.get("yaml_snippet"):
            for line in suggestion["yaml_snippet"].split("\n"):
                click.echo(f"        {line}")

    if apply:
        # Apply changes to spec file
        _apply_suggestions(spec_path, suggestions)
        click.echo("")
        click.echo(f"    ✓ Applied {len(suggestions)} changes to {spec_path.name}")
    else:
        click.echo("")
        click.echo("    Run with --apply to update the spec file.")


def _analyze_changes(
    spec: Any,
    cached_code: str,
    current_code: str,
) -> list[dict[str, Any]]:
    """Analyze code changes and suggest spec updates.

    Args:
        spec: The parsed spec.
        cached_code: The cached (original) code.
        current_code: The current (modified) code.

    Returns:
        List of suggested changes with descriptions and YAML snippets.
    """
    suggestions: list[dict[str, Any]] = []

    try:
        cached_ast = ast.parse(cached_code)
        current_ast = ast.parse(current_code)
    except SyntaxError:
        return suggestions

    # Find function definitions
    cached_funcs = {
        node.name: node
        for node in ast.walk(cached_ast)
        if isinstance(node, ast.FunctionDef)
    }
    current_funcs = {
        node.name: node
        for node in ast.walk(current_ast)
        if isinstance(node, ast.FunctionDef)
    }

    func_name = spec.function_name

    if func_name in cached_funcs and func_name in current_funcs:
        cached_func = cached_funcs[func_name]
        current_func = current_funcs[func_name]

        # Check for new parameters
        cached_params = {arg.arg for arg in cached_func.args.args}
        current_params = {arg.arg for arg in current_func.args.args}
        new_params = current_params - cached_params

        for param in new_params:
            suggestions.append({
                "type": "new_parameter",
                "description": f"New parameter detected: {param}",
                "yaml_snippet": f"""- name: {param}
  type: str  # Update with correct type
  description: "TODO: Add description"
""",
            })

        # Check for return type changes (via type annotations)
        if current_func.returns and cached_func.returns:
            if ast.dump(current_func.returns) != ast.dump(cached_func.returns):
                new_type = _get_type_annotation_str(current_func.returns)
                suggestions.append({
                    "type": "return_type_change",
                    "description": f"Return type may have changed to: {new_type}",
                    "yaml_snippet": f"""returns:
  type: {new_type}
  description: "TODO: Verify description"
""",
                })

        # Check for new exception handling
        cached_raises = _find_raises(cached_func)
        current_raises = _find_raises(current_func)
        new_raises = current_raises - cached_raises

        for exc in new_raises:
            suggestions.append({
                "type": "new_exception",
                "description": f"New exception raised: {exc}",
                "yaml_snippet": f"""- name: raises_{exc.lower()}
  input:
    # TODO: Add input that triggers this exception
  expected_output:
    raises: {exc}
""",
            })

        # Check for docstring changes that might indicate new behavior
        cached_doc = ast.get_docstring(cached_func)
        current_doc = ast.get_docstring(current_func)

        if current_doc and current_doc != cached_doc:
            suggestions.append({
                "type": "docstring_change",
                "description": "Docstring changed - intent may need updating",
                "yaml_snippet": None,
            })

    return suggestions


def _find_raises(func: ast.FunctionDef) -> set[str]:
    """Find all exception types raised in a function.

    Args:
        func: The function AST node.

    Returns:
        Set of exception type names.
    """
    raises = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Raise) and node.exc:
            if isinstance(node.exc, ast.Call):
                if isinstance(node.exc.func, ast.Name):
                    raises.add(node.exc.func.id)
            elif isinstance(node.exc, ast.Name):
                raises.add(node.exc.id)
    return raises


def _get_type_annotation_str(node: ast.expr) -> str:
    """Convert an AST type annotation to a string.

    Args:
        node: The type annotation AST node.

    Returns:
        String representation of the type.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Subscript):
        base = _get_type_annotation_str(node.value)
        if isinstance(node.slice, ast.Tuple):
            args = ", ".join(_get_type_annotation_str(e) for e in node.slice.elts)
        else:
            args = _get_type_annotation_str(node.slice)
        return f"{base}[{args}]"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _get_type_annotation_str(node.left)
        right = _get_type_annotation_str(node.right)
        return f"{left} | {right}"
    return "Any"


def _apply_suggestions(
    spec_path: Path,
    suggestions: list[dict[str, Any]],
) -> None:
    """Apply suggested changes to a spec file.

    Args:
        spec_path: Path to the spec file.
        suggestions: List of suggestions to apply.
    """
    # Read current spec content
    content = spec_path.read_text(encoding="utf-8")

    # Add a comment about the sync
    sync_comment = "# AUTO-SYNCED: Review the following suggestions\n"

    for suggestion in suggestions:
        if suggestion.get("yaml_snippet"):
            # Add as comment for manual review
            snippet = suggestion["yaml_snippet"]
            commented = "\n".join(f"# {line}" for line in snippet.split("\n") if line)
            sync_comment += f"# {suggestion['description']}:\n{commented}\n"

    # Append to end of file
    if sync_comment:
        content += f"\n{sync_comment}"
        spec_path.write_text(content, encoding="utf-8")
