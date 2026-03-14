# 🦜 Wordbird for VS Code

Context bridge for [Wordbird](https://github.com/tillahoffmann/wordbird) voice dictation.

This extension connects your VS Code workspace to Wordbird so that `WORDBIRD.md` context files are picked up when dictating — even in remote SSH sessions.

## How it works

1. Install and run [Wordbird](https://github.com/tillahoffmann/wordbird): `uvx wordbird`
2. Install this extension in VS Code
3. Add a `WORDBIRD.md` to your project root (`uvx wordbird init`)
4. Dictate — Wordbird uses your project's context to correct transcription errors

The extension reads `WORDBIRD.md` from your workspace and writes it to `~/.config/wordbird/active-context.json`. Wordbird picks this up when VS Code is the focused app, cross-checking the process ID to ensure the context matches the active window.

## What it sends

The context file contains:

- **pid** — the extension host process ID (used for verification)
- **workspace** — the workspace folder path
- **wordbird_md** — the contents of `WORDBIRD.md` (if it exists)

Everything stays local on your machine. Nothing is sent to any server.

## Works with remote SSH

Because the extension reads files via `vscode.workspace.fs`, it works transparently with remote SSH workspaces. The `WORDBIRD.md` on the remote machine is read and relayed to the local Wordbird process.

## Requirements

- [Wordbird](https://github.com/tillahoffmann/wordbird) running on macOS with Apple Silicon
- A `WORDBIRD.md` in your project root (optional — Wordbird works without it, just without project context)
