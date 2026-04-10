# Axiom for VS Code

Language support for [Axiom](https://github.com/RCOLKITT/Axiom) spec files (`.axiom`).

Axiom is a spec-driven development platform where humans write executable specifications and machines generate, verify, and maintain the code.

## Features

### Syntax Highlighting

Full syntax highlighting for `.axiom` spec files with support for:
- YAML structure
- Embedded Python code in examples and invariants
- Keywords like `axiom`, `metadata`, `intent`, `interface`, `examples`, `invariants`

### Language Server Protocol (LSP)

Real-time diagnostics, completions, and hover information powered by the Axiom LSP:

- **Diagnostics**: See parsing errors and validation issues as you type
- **Completions**: Get suggestions for spec fields and types
- **Hover**: View documentation for spec elements
- **Go to Definition**: Jump to referenced specs

### Commands

- **Axiom: Build Current Spec** - Generate code from the current spec file
- **Axiom: Verify Current Spec** - Run verification on the current spec
- **Axiom: Restart Language Server** - Restart the LSP if needed

## Requirements

- [Axiom CLI](https://github.com/RCOLKITT/Axiom) installed and available in PATH
- Python 3.12+

## Installation

1. Install Axiom CLI:
   ```bash
   pip install axiom-spec
   ```

2. Install this extension from the VS Code Marketplace

3. Open any `.axiom` file to activate

## Extension Settings

- `axiom.server.path`: Path to the axiom executable (default: `"axiom"`)
- `axiom.trace.server`: Trace level for LSP communication (`"off"`, `"messages"`, `"verbose"`)

## Quick Start

1. Create a new Axiom project:
   ```bash
   axiom quickstart my-project
   ```

2. Open `my-project` in VS Code

3. Edit `specs/examples/hello_world.axiom`

4. Press `Cmd+Shift+P` and run "Axiom: Build Current Spec"

## Example Spec

```yaml
axiom: "0.1"

metadata:
  name: add_numbers
  version: "1.0.0"
  description: "Add two numbers together"
  target: "python:function"

intent: |
  Takes two numbers and returns their sum.

interface:
  function_name: add_numbers
  parameters:
    - name: a
      type: int
    - name: b
      type: int
  returns:
    type: int

examples:
  - name: basic_addition
    input: { a: 2, b: 3 }
    expected_output: 5

invariants:
  - description: "Addition is commutative"
    check: "add_numbers(a, b) == add_numbers(b, a)"
```

## Links

- [Axiom Documentation](https://github.com/RCOLKITT/Axiom)
- [Report Issues](https://github.com/RCOLKITT/Axiom/issues)

## License

MIT
