"""Main CLI entry point for Axiom."""

from __future__ import annotations

from pathlib import Path

import click
import structlog

# Load .env file if it exists
try:
    from dotenv import load_dotenv

    load_dotenv(Path.cwd() / ".env")
except ImportError:
    pass  # dotenv not installed, skip

from axiom import __version__
from axiom.cli.build_cmd import build
from axiom.cli.cache_cmd import cache
from axiom.cli.diff_cmd import diff
from axiom.cli.doctor_cmd import doctor
from axiom.cli.explain_cmd import explain
from axiom.cli.infer_cmd import infer, infer_all
from axiom.cli.init_cmd import init
from axiom.cli.lint_cmd import lint
from axiom.cli.lsp_cmd import lsp
from axiom.cli.new_cmd import new
from axiom.cli.provenance_cmd import provenance
from axiom.cli.stats_cmd import stats
from axiom.cli.verify_cmd import verify
from axiom.cli.watch_cmd import watch


def configure_logging(verbose: bool) -> None:
    """Configure structlog for CLI output.

    Args:
        verbose: Whether to enable debug logging.
    """
    processors = [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if verbose:
        # In verbose mode, show all logs with nice formatting
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # In normal mode, filter to INFO+ and use simple output
        def filter_info_and_above(
            logger: object, method_name: str, event_dict: dict[str, object]
        ) -> dict[str, object]:
            if method_name == "debug":
                raise structlog.DropEvent
            return event_dict

        processors.append(filter_info_and_above)
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,  # type: ignore[arg-type]
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


@click.group()
@click.version_option(version=__version__, prog_name="axiom")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Axiom: Compile .axiom specs into verified Python code.

    Axiom is a development platform where humans write executable specifications
    and machines generate, verify, and maintain the code.

    \b
    Quick start:
      axiom init                    # Initialize a new project
      axiom build specs/example.axiom   # Generate code from a spec
      axiom verify specs/example.axiom  # Verify generated code
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    configure_logging(verbose)


# Register commands
cli.add_command(init)
cli.add_command(new)
cli.add_command(build)
cli.add_command(verify)
cli.add_command(watch)
cli.add_command(lint)
cli.add_command(infer)
cli.add_command(infer_all)
cli.add_command(cache)
cli.add_command(provenance)
cli.add_command(lsp)
cli.add_command(diff)
cli.add_command(doctor)
cli.add_command(stats)
cli.add_command(explain)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
