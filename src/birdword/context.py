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


def _is_child_of(child_pid: int, parent_pid: int) -> bool:
    """Check if child_pid is a descendant of parent_pid."""
    try:
        result = subprocess.run(
            ["ps", "-o", "ppid=", "-p", str(child_pid)],
            capture_output=True, text=True, timeout=2,
        )
        ppid = int(result.stdout.strip())
        if ppid == parent_pid:
            return True
        if ppid <= 1:
            return False
        return _is_child_of(ppid, parent_pid)
    except Exception:
        return False


def _read_active_context(frontmost_pid: int) -> tuple[str | None, str | None]:
    """Read workspace and BIRDWORD.md from active-context.json.

    Written by the VS Code extension. Verified by checking that the PID
    in the file is a child process of the frontmost application.

    Returns (workspace_path, birdword_md_content).
    """
    try:
        with open(ACTIVE_CONTEXT_PATH) as f:
            data = json.load(f)

        ctx_pid = data.get("pid")
        if ctx_pid != frontmost_pid and not _is_child_of(ctx_pid, frontmost_pid):
            return None, None

        return data.get("workspace"), data.get("birdword_md")
    except Exception:
        return None, None


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


def get_context() -> tuple[str, str | None, str | None]:
    """Get current context: (app_name, cwd, BIRDWORD.md contents or None).

    Resolves context from:
    - Terminal.app: detects focused tab's shell cwd, walks up for BIRDWORD.md
    - VS Code / Insiders: reads active-context.json written by the extension
    """
    bundle_id, app_name = get_frontmost_app()

    cwd = None
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
        ws = AppKit.NSWorkspace.sharedWorkspace()
        frontmost_pid = ws.frontmostApplication().processIdentifier()
        cwd, context_content = _read_active_context(frontmost_pid)

    return app_name, cwd, context_content
