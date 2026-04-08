/**
 * VSCode extension for Axiom spec files.
 *
 * Provides:
 * - Syntax highlighting for .axiom files
 * - LSP integration for diagnostics, completion, hover, and go-to-definition
 * - Commands for building and verifying specs
 */

import * as path from "path";
import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient | undefined;

/**
 * Activate the extension.
 */
export function activate(context: vscode.ExtensionContext): void {
  // Start the language server
  startLanguageServer(context);

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand("axiom.buildSpec", buildCurrentSpec),
    vscode.commands.registerCommand("axiom.verifySpec", verifyCurrentSpec),
    vscode.commands.registerCommand("axiom.restartServer", () =>
      restartServer(context)
    )
  );

  // Show status bar item
  const statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBarItem.text = "$(zap) Axiom";
  statusBarItem.tooltip = "Axiom Language Server";
  statusBarItem.command = "axiom.restartServer";
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);
}

/**
 * Deactivate the extension.
 */
export function deactivate(): Thenable<void> | undefined {
  if (client) {
    return client.stop();
  }
  return undefined;
}

/**
 * Start the Axiom language server.
 */
function startLanguageServer(context: vscode.ExtensionContext): void {
  const config = vscode.workspace.getConfiguration("axiom");
  const axiomPath = config.get<string>("server.path", "axiom");

  // Server options - run axiom lsp command
  const serverOptions: ServerOptions = {
    command: axiomPath,
    args: ["lsp", "--stdio"],
    transport: TransportKind.stdio,
  };

  // Client options
  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: "file", language: "axiom" }],
    synchronize: {
      // Watch for changes to .axiom files
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.axiom"),
    },
    outputChannelName: "Axiom Language Server",
  };

  // Create and start the client
  client = new LanguageClient(
    "axiom",
    "Axiom Language Server",
    serverOptions,
    clientOptions
  );

  client.start();
}

/**
 * Restart the language server.
 */
async function restartServer(
  context: vscode.ExtensionContext
): Promise<void> {
  if (client) {
    await client.stop();
  }
  startLanguageServer(context);
  vscode.window.showInformationMessage("Axiom Language Server restarted");
}

/**
 * Build the current spec file.
 */
async function buildCurrentSpec(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "axiom") {
    vscode.window.showWarningMessage(
      "No Axiom spec file is currently open"
    );
    return;
  }

  const filePath = editor.document.fileName;
  const config = vscode.workspace.getConfiguration("axiom");
  const axiomPath = config.get<string>("server.path", "axiom");

  const terminal = vscode.window.createTerminal("Axiom Build");
  terminal.show();
  terminal.sendText(`${axiomPath} build "${filePath}" --verify`);
}

/**
 * Verify the current spec file.
 */
async function verifyCurrentSpec(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "axiom") {
    vscode.window.showWarningMessage(
      "No Axiom spec file is currently open"
    );
    return;
  }

  const filePath = editor.document.fileName;
  const config = vscode.workspace.getConfiguration("axiom");
  const axiomPath = config.get<string>("server.path", "axiom");

  const terminal = vscode.window.createTerminal("Axiom Verify");
  terminal.show();
  terminal.sendText(`${axiomPath} verify "${filePath}"`);
}
