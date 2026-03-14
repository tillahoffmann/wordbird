"""Detect the focused app and resolve project context."""

import json
import os
import subprocess

import AppKit

from birdword.config import CONFIG_DIR

ACTIVE_CONTEXT_PATH = os.path.join(CONFIG_DIR, "active-context.json")

_VSCODE_BUNDLE_IDS = {
    "com.microsoft.VSCode",
    "com.microsoft.VSCodeInsiders",
}


def get_frontmost_app() -> tuple[str, str]:
    """Return (bundle_id, app_name) of the frontmost application."""
    workspace = AppKit.NSWorkspace.sharedWorkspace()
    app = workspace.frontmostApplication()
    return (app.bundleIdentifier() or "", app.localizedName() or "")


def get_terminal_cwd() -> str | None:
    """Get the cwd of the shell in the frontmost Terminal.app tab.

    Only called when Terminal.app is the focused app.
    Requires Automation permission for Terminal.app (prompts once).
    """
    try:
        tty = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "Terminal" to tty of selected tab of front window',
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if tty.returncode != 0 or not tty.stdout.strip():
            return None

        tty_name = tty.stdout.strip()
        tty_short = tty_name.replace("/dev/", "")

        ps = subprocess.run(
            ["ps", "-t", tty_short, "-o", "pid=,comm="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if ps.returncode != 0:
            return None

        pid = None
        for line in ps.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2 and any(
                sh in parts[-1] for sh in ("zsh", "bash", "fish")
            ):
                pid = parts[0]
                break

        if pid is None:
            return None

        lsof = subprocess.run(
            ["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in lsof.stdout.strip().splitlines():
            if line.startswith("n/"):
                return line[1:]

    except Exception:
        pass

    return None


def _read_active_context(frontmost_pid: int) -> str | None:
    """Read BIRDWORD.md content from the active-context.json file.

    Written by the VS Code extension. Only used if the PID in the file
    matches the frontmost application's PID.
    """
    try:
        with open(ACTIVE_CONTEXT_PATH) as f:
            data = json.load(f)

        if data.get("pid") != frontmost_pid:
            return None

        return data.get("birdword_md")
    except Exception:
        return None


def find_context_file(start_dir: str) -> str | None:
    """Walk up from start_dir looking for a BIRDWORD.md file."""
    current = os.path.abspath(start_dir)
    while True:
        candidate = os.path.join(current, "BIRDWORD.md")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def get_context() -> tuple[str, str | None]:
    """Get current context: (app_name, BIRDWORD.md contents or None).

    Resolves context from:
    - Terminal.app: detects focused tab's shell cwd, walks up for BIRDWORD.md
    - VS Code / Insiders: reads active-context.json written by the extension
    """
    bundle_id, app_name = get_frontmost_app()

    context_content = None

    if bundle_id == "com.apple.Terminal":
        cwd = get_terminal_cwd()
        if cwd:
            context_file = find_context_file(cwd)
            if context_file:
                try:
                    with open(context_file) as f:
                        context_content = f.read()
                except Exception:
                    pass

    elif bundle_id in _VSCODE_BUNDLE_IDS:
        workspace = AppKit.NSWorkspace.sharedWorkspace()
        frontmost_pid = workspace.frontmostApplication().processIdentifier()
        context_content = _read_active_context(frontmost_pid)

    return app_name, context_content
