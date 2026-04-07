"""LSP server command for Axiom.

Starts the Language Server Protocol server for IDE integration.
"""

from __future__ import annotations

import click


@click.command()
@click.option(
    "--stdio",
    is_flag=True,
    default=True,
    help="Use stdio transport (default)",
)
@click.option(
    "--tcp",
    is_flag=True,
    help="Use TCP transport",
)
@click.option(
    "--host",
    default="127.0.0.1",
    help="TCP host (when using --tcp)",
)
@click.option(
    "--port",
    default=2087,
    type=int,
    help="TCP port (when using --tcp)",
)
def lsp(stdio: bool, tcp: bool, host: str, port: int) -> None:
    """Start the Axiom Language Server.

    The LSP server provides IDE features for .axiom files:
    - Real-time validation and diagnostics
    - Code completion
    - Hover documentation
    - Go-to-definition for dependencies

    \b
    For VSCode, install the vscode-axiom extension.
    For other editors, configure the LSP client to run:
        axiom lsp --stdio
    """
    from axiom.lsp.server import create_server

    server = create_server()

    if tcp:
        click.echo(f"Starting Axiom LSP server on {host}:{port}")
        server.start_tcp(host, port)
    else:
        # stdio is default
        server.start_io()
