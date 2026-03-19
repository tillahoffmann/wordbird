import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

const CONTEXTS_DIR = path.join(os.homedir(), ".wordbird", "editor-contexts");
const CONTEXT_PATH = path.join(CONTEXTS_DIR, `${process.pid}.json`);

interface WordbirdContext {
  pid: number;
  workspace: string | null;
  wordbird_md: string | null;
}

let fileWatcher: vscode.FileSystemWatcher | undefined;

export function activate(context: vscode.ExtensionContext) {
  writeContext().catch(() => {});

  context.subscriptions.push(
    vscode.window.onDidChangeWindowState((e) => {
      if (e.focused) {
        writeContext().catch(() => {});
      }
    })
  );

  context.subscriptions.push(
    vscode.workspace.onDidChangeWorkspaceFolders(() => {
      setupFileWatcher(context);
      writeContext().catch(() => {});
    })
  );

  setupFileWatcher(context);
}

function setupFileWatcher(context: vscode.ExtensionContext) {
  fileWatcher?.dispose();

  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) {
    return;
  }

  const pattern = new vscode.RelativePattern(folders[0], "WORDBIRD.md");
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
      const wordbirdUri = vscode.Uri.joinPath(folder.uri, "WORDBIRD.md");
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

    fs.mkdirSync(CONTEXTS_DIR, { recursive: true });
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
