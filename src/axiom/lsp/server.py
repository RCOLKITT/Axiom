"""Axiom Language Server implementation.

Provides IDE features for .axiom spec files including:
- Real-time diagnostics (syntax and semantic validation)
- Hover information
- Code completion
- Go-to-definition for dependencies
"""

from __future__ import annotations

from pathlib import Path

from lsprotocol import types as lsp
from pygls.lsp.server import LanguageServer

from axiom.lsp.actions import get_code_actions
from axiom.lsp.completion import get_completions
from axiom.lsp.diagnostics import validate_document
from axiom.lsp.hover import get_hover_info
from axiom.lsp.symbols import get_document_symbols

# Server metadata
SERVER_NAME = "axiom-lsp"
SERVER_VERSION = "0.1.0"


def create_server() -> LanguageServer:
    """Create and configure the Axiom language server.

    Returns:
        Configured LanguageServer instance ready to start.
    """
    server = LanguageServer(SERVER_NAME, SERVER_VERSION)

    @server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
    def did_open(params: lsp.DidOpenTextDocumentParams) -> None:
        """Handle document open - validate and publish diagnostics."""
        doc = server.workspace.get_text_document(params.text_document.uri)
        diagnostics = validate_document(doc.source, doc.uri)
        server.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=doc.uri, diagnostics=diagnostics)
        )

    @server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
    def did_change(params: lsp.DidChangeTextDocumentParams) -> None:
        """Handle document changes - re-validate and publish diagnostics."""
        doc = server.workspace.get_text_document(params.text_document.uri)
        diagnostics = validate_document(doc.source, doc.uri)
        server.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=doc.uri, diagnostics=diagnostics)
        )

    @server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
    def did_save(params: lsp.DidSaveTextDocumentParams) -> None:
        """Handle document save - full re-validation."""
        doc = server.workspace.get_text_document(params.text_document.uri)
        diagnostics = validate_document(doc.source, doc.uri)
        server.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=doc.uri, diagnostics=diagnostics)
        )

    @server.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
    def did_close(params: lsp.DidCloseTextDocumentParams) -> None:
        """Handle document close - clear diagnostics."""
        server.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[])
        )

    @server.feature(lsp.TEXT_DOCUMENT_COMPLETION)
    def completion(params: lsp.CompletionParams) -> lsp.CompletionList:
        """Provide code completion for .axiom files."""
        doc = server.workspace.get_text_document(params.text_document.uri)
        items = get_completions(doc.source, params.position)
        return lsp.CompletionList(is_incomplete=False, items=items)

    @server.feature(lsp.TEXT_DOCUMENT_HOVER)
    def hover(params: lsp.HoverParams) -> lsp.Hover | None:
        """Provide hover information for .axiom files."""
        doc = server.workspace.get_text_document(params.text_document.uri)
        return get_hover_info(doc.source, params.position)

    @server.feature(lsp.TEXT_DOCUMENT_DEFINITION)
    def goto_definition(
        params: lsp.DefinitionParams,
    ) -> lsp.Location | list[lsp.Location] | None:
        """Go to definition for dependencies."""
        doc = server.workspace.get_text_document(params.text_document.uri)
        return _find_definition(doc.source, params.position, doc.uri, server)

    @server.feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def document_symbol(
        params: lsp.DocumentSymbolParams,
    ) -> list[lsp.DocumentSymbol]:
        """Provide document symbols for outline view."""
        doc = server.workspace.get_text_document(params.text_document.uri)
        return get_document_symbols(doc.source)

    @server.feature(lsp.TEXT_DOCUMENT_CODE_ACTION)
    def code_action(params: lsp.CodeActionParams) -> list[lsp.CodeAction]:
        """Provide code actions and quick fixes."""
        doc = server.workspace.get_text_document(params.text_document.uri)
        return get_code_actions(
            doc.source,
            params.context.diagnostics,
            params.text_document.uri,
        )

    @server.feature(lsp.INITIALIZE)
    def initialize(params: lsp.InitializeParams) -> lsp.InitializeResult:
        """Handle LSP initialization."""
        return lsp.InitializeResult(
            capabilities=lsp.ServerCapabilities(
                text_document_sync=lsp.TextDocumentSyncOptions(
                    open_close=True,
                    change=lsp.TextDocumentSyncKind.Full,
                    save=lsp.SaveOptions(include_text=True),
                ),
                completion_provider=lsp.CompletionOptions(
                    trigger_characters=[":", " ", "-", "\n"],
                    resolve_provider=False,
                ),
                hover_provider=True,
                definition_provider=True,
                document_symbol_provider=True,
                code_action_provider=lsp.CodeActionOptions(
                    code_action_kinds=[
                        lsp.CodeActionKind.QuickFix,
                        lsp.CodeActionKind.SourceOrganizeImports,
                    ],
                ),
            ),
            server_info=lsp.ServerInfo(name=SERVER_NAME, version=SERVER_VERSION),
        )

    return server


def _find_definition(
    source: str,
    position: lsp.Position,
    current_uri: str,
    server: LanguageServer,
) -> lsp.Location | None:
    """Find the definition location for dependencies.

    Args:
        source: Document source text.
        position: Cursor position.
        current_uri: URI of the current document.
        server: Language server instance.

    Returns:
        Location of the definition, or None if not found.
    """
    import re

    lines = source.split("\n")
    if position.line >= len(lines):
        return None

    line = lines[position.line]

    # Check if we're on a dependency name line
    dep_match = re.match(r'\s*-\s*name:\s*["\']?(\w+)["\']?', line)
    if dep_match:
        dep_name = dep_match.group(1)

        # Try to find the spec file
        try:
            # Parse the current spec to get its directory
            current_path = Path(current_uri.replace("file://", ""))
            spec_dir = current_path.parent

            # Look for the dependency spec
            potential_paths = [
                spec_dir / f"{dep_name}.axiom",
                spec_dir.parent / f"{dep_name}.axiom",
                spec_dir.parent / dep_name / f"{dep_name}.axiom",
            ]

            for path in potential_paths:
                if path.exists():
                    return lsp.Location(
                        uri=f"file://{path}",
                        range=lsp.Range(
                            start=lsp.Position(line=0, character=0),
                            end=lsp.Position(line=0, character=0),
                        ),
                    )
        except Exception:
            pass

    return None


def start_server() -> None:
    """Start the Axiom language server using stdio transport."""
    server = create_server()
    server.start_io()


if __name__ == "__main__":
    start_server()
