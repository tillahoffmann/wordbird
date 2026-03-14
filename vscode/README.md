# 🐦 Birdword for VS Code

Context bridge for [Birdword](https://github.com/tillahoffmann/birdword) voice dictation.

This extension connects your VS Code workspace to Birdword so that `BIRDWORD.md` context files are picked up when dictating — even in remote SSH sessions.

## How it works

1. Install and run [Birdword](https://github.com/tillahoffmann/birdword): `uvx birdword`
2. Install this extension in VS Code
3. Add a `BIRDWORD.md` to your project root (`uvx birdword init`)
4. Dictate — Birdword uses your project's context to correct transcription errors

The extension reads `BIRDWORD.md` from your workspace and writes it to `~/.config/birdword/active-context.json`. Birdword picks this up when VS Code is the focused app, cross-checking the process ID to ensure the context matches the active window.

## What it sends

The context file contains:

- **pid** — the extension host process ID (used for verification)
- **workspace** — the workspace folder path
- **birdword_md** — the contents of `BIRDWORD.md` (if it exists)

Everything stays local on your machine. Nothing is sent to any server.

## Works with remote SSH

Because the extension reads files via `vscode.workspace.fs`, it works transparently with remote SSH workspaces. The `BIRDWORD.md` on the remote machine is read and relayed to the local Birdword process.

## Requirements

- [Birdword](https://github.com/tillahoffmann/birdword) running on macOS with Apple Silicon
- A `BIRDWORD.md` in your project root (optional — Birdword works without it, just without project context)
