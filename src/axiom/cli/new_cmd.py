"""The 'axiom new' command for creating new specs from templates."""

from __future__ import annotations

from pathlib import Path

import click

# Spec templates
TEMPLATES: dict[str, str] = {
    "function": """axiom: "0.1"

metadata:
  name: {name}
  version: "1.0.0"
  description: "{description}"
  target: "python:function"

intent: |
  # TODO: Describe what this function should do.
  # Be specific about edge cases and error handling.

interface:
  function_name: {name}
  parameters:
    - name: input
      type: str
      description: "TODO: Describe this parameter"
  returns:
    type: str
    description: "TODO: Describe the return value"

examples:
  - name: basic_example
    input:
      input: "example"
    expected_output: "TODO: expected result"

  - name: edge_case_empty
    input:
      input: ""
    expected_output:
      raises: ValueError

  # TODO: Add more examples (aim for 3-5)

invariants:
  - description: "TODO: Property that always holds"
    check: |
      # Example: len(output) >= 0
      True
""",
    "fastapi": """axiom: "0.1"

metadata:
  name: {name}
  version: "1.0.0"
  description: "{description}"
  target: "python:fastapi"

intent: |
  # TODO: Describe this API endpoint.
  # Include request/response format and error cases.

interface:
  method: POST
  path: "/api/{name}"
  request_body:
    type: dict
    description: "TODO: Describe request body"
  response:
    type: dict
    description: "TODO: Describe response"
  errors:
    - status_code: 400
      description: "Invalid request"
    - status_code: 404
      description: "Not found"

examples:
  - name: success
    input:
      request_body:
        field: "value"
    expected_output:
      status_code: 200
      body:
        success: true

  - name: invalid_request
    input:
      request_body: {{}}
    expected_output:
      status_code: 400

  # TODO: Add more examples

invariants:
  - description: "Response always has correct structure"
    check: |
      isinstance(output.get("body"), dict)
""",
    "validator": """axiom: "0.1"

metadata:
  name: {name}
  version: "1.0.0"
  description: "{description}"
  target: "python:function"

intent: |
  Validates input and returns True if valid, False otherwise.
  Does not raise exceptions for invalid input.

interface:
  function_name: {name}
  parameters:
    - name: value
      type: str
      description: "The value to validate"
  returns:
    type: bool
    description: "True if valid, False otherwise"

examples:
  - name: valid_input
    input:
      value: "valid_example"
    expected_output: true

  - name: invalid_input
    input:
      value: "invalid"
    expected_output: false

  - name: empty_input
    input:
      value: ""
    expected_output: false

  - name: whitespace_only
    input:
      value: "   "
    expected_output: false

invariants:
  - description: "Always returns boolean"
    check: |
      isinstance(output, bool)

  - description: "Empty string is always invalid"
    check: |
      output == False if value == "" else True
""",
    "transformer": """axiom: "0.1"

metadata:
  name: {name}
  version: "1.0.0"
  description: "{description}"
  target: "python:function"

intent: |
  Transforms input data into a different format.
  Pure function with no side effects.

interface:
  function_name: {name}
  parameters:
    - name: data
      type: str
      description: "The data to transform"
  returns:
    type: str
    description: "The transformed data"

examples:
  - name: basic_transform
    input:
      data: "input"
    expected_output: "OUTPUT"  # TODO: actual transformation

  - name: empty_input
    input:
      data: ""
    expected_output: ""

  - name: special_characters
    input:
      data: "hello world!"
    expected_output: "HELLO WORLD!"  # TODO: actual transformation

invariants:
  - description: "Transformation is deterministic"
    check: |
      True  # Same input always produces same output
""",
}


def _to_snake_case(name: str) -> str:
    """Convert a name to snake_case.

    Args:
        name: The name to convert.

    Returns:
        Snake case version of the name.
    """
    import re

    # Insert underscore before uppercase letters and convert to lowercase
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower().replace("-", "_").replace(" ", "_")


@click.command()
@click.argument("template", type=click.Choice(list(TEMPLATES.keys())))
@click.argument("name")
@click.option("--description", "-d", default="", help="Description for the spec")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="specs",
    help="Output directory (default: specs/)",
)
@click.option("--force", "-f", is_flag=True, help="Overwrite existing file")
def new(template: str, name: str, description: str, output_dir: str, force: bool) -> None:
    """Create a new spec file from a template.

    \b
    Templates:
      function    - Pure Python function (default)
      fastapi     - FastAPI endpoint
      validator   - Boolean validation function
      transformer - Data transformation function

    \b
    Examples:
      axiom new function validate_phone
      axiom new fastapi create_user
      axiom new validator is_valid_url -d "Validates URL format"
      axiom new transformer slugify -o specs/utils/
    """
    # Normalize name
    spec_name = _to_snake_case(name)

    # Use name as description if not provided
    if not description:
        description = f"TODO: Describe {spec_name}"

    # Generate spec content
    content = TEMPLATES[template].format(
        name=spec_name,
        description=description,
    )

    # Determine output path
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    spec_file = output_path / f"{spec_name}.axiom"

    # Check if file exists
    if spec_file.exists() and not force:
        raise click.ClickException(f"File already exists: {spec_file}\nUse --force to overwrite.")

    # Write file
    spec_file.write_text(content)

    click.echo(f"Created: {spec_file}")
    click.echo("")
    click.echo(f"Template: {template}")
    click.echo(f"Name: {spec_name}")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  1. Edit {spec_file} to define your spec")
    click.echo(f"  2. axiom build {spec_file}")
    click.echo(f"  3. axiom verify {spec_file}")
