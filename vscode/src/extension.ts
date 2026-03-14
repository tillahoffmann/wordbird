import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

const CONTEXT_PATH = path.join(
  os.homedir(),
  ".config",
  "wordbird",
  "active-context.json"
);

interface WordbirdContext {
  pid: number;
  workspace: string | null;
  wordbird_md: string | null;
}

let fileWatcher: vscode.FileSystemWatcher | undefined;

export function activate(context: vscode.ExtensionContext) {
  // Write context on activation (fire-and-forget with error handling)
  writeContext().catch(() => {});

  // Update on window focus
  context.subscriptions.push(
    vscode.window.onDidChangeWindowState((e) => {
      if (e.focused) {
        writeContext().catch(() => {});
      }
    })
  );

  // Update when workspace folders change
  context.subscriptions.push(
    vscode.workspace.onDidChangeWorkspaceFolders(() => {
      setupFileWatcher(context);
      writeContext().catch(() => {});
    })
  );

  // Watch BIRDWORD.md for changes
  setupFileWatcher(context);
}

function setupFileWatcher(context: vscode.ExtensionContext) {
  fileWatcher?.dispose();

  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) {
    return;
  }

  const pattern = new vscode.RelativePattern(folders[0], "BIRDWORD.md");
  fileWatcher = vscode.workspace.createFileSystemWatcher(pattern);

  fileWatcher.onDidChange(() => writeContext().catch(() => {}));
  fileWatcher.onDidCreate(() => writeContext().catch(() => {}));
  fileWatcher.onDidDelete(() => writeContext().catch(() => {}));

  context.subscriptions.push(fileWatcher);
}

async function writeContext(): Promise<void> {
  try {
    const folder = vscode.workspace.workspaceFolders?.[0];

    let wordbirdMd: string | null = null;
    if (folder) {
      const wordbirdUri = vscode.Uri.joinPath(folder.uri, "BIRDWORD.md");
      try {
        const content = await vscode.workspace.fs.readFile(wordbirdUri);
        wordbirdMd = Buffer.from(content).toString("utf-8");
      } catch {
        // File doesn't exist — that's fine
      }
    }

    const ctx: WordbirdContext = {
      pid: process.pid,
      workspace: folder?.uri.fsPath ?? null,
      wordbird_md: wordbirdMd,
    };

    const dir = path.dirname(CONTEXT_PATH);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(
      CONTEXT_PATH,
      JSON.stringify(ctx, null, 2) + "\n",
      "utf-8"
    );
  } catch {
    // Never crash the extension host
  }
}

export function deactivate() {
  try {
    fs.unlinkSync(CONTEXT_PATH);
  } catch {
    // Already gone
  }
}
