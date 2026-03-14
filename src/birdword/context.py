"""Detect the focused app and resolve project context."""

import json
import os
import sqlite3
import subprocess
from urllib.parse import unquote, urlparse

import AppKit

_VSCODE_BUNDLE_IDS = {
    "com.microsoft.VSCode": "Code",
    "com.microsoft.VSCodeInsiders": "Code - Insiders",
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


def _get_vscode_window_title(pid: int) -> str | None:
    """Get the window title of a VS Code window via Accessibility API."""
    try:
        from ApplicationServices import (
            AXUIElementCreateApplication,
            AXUIElementCopyAttributeValue,
            kAXErrorSuccess,
        )

        app_ref = AXUIElementCreateApplication(pid)
        err, window = AXUIElementCopyAttributeValue(app_ref, "AXFocusedWindow", None)
        if err != kAXErrorSuccess:
            return None
        err, title = AXUIElementCopyAttributeValue(window, "AXTitle", None)
        if err != kAXErrorSuccess:
            return None
        return str(title)
    except Exception:
        return None


def _extract_workspace_from_title(title: str) -> str | None:
    """Extract workspace/folder name from a VS Code window title.

    Default format: '{dirty}{filename} - {rootName} - Visual Studio Code'
    """
    for suffix in (" - Visual Studio Code - Insiders", " - Visual Studio Code"):
        if title.endswith(suffix):
            title = title[: -len(suffix)]
            break
    else:
        return None

    parts = title.rsplit(" - ", 1)
    name = parts[-1].lstrip("● ")
    return name if name else None


def _get_vscode_recent_workspaces(bundle_id: str) -> list[str]:
    """Get recently opened folder paths from VS Code's state database."""
    app_support_name = _VSCODE_BUNDLE_IDS.get(bundle_id, "Code")
    if "Insiders" in app_support_name:
        app_support_name = "Code - Insiders"
    else:
        app_support_name = "Code"

    db_path = os.path.expanduser(
        f"~/Library/Application Support/{app_support_name}/User/globalStorage/state.vscdb"
    )
    if not os.path.exists(db_path):
        return []

    folders = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.execute(
            "SELECT value FROM ItemTable WHERE key = 'history.recentlyOpenedPathsList'"
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            data = json.loads(row[0])
            for entry in data.get("entries", []):
                folder_uri = entry.get("folderUri", "")
                if folder_uri.startswith("file://"):
                    parsed = urlparse(folder_uri)
                    path = unquote(parsed.path)
                    if os.path.isdir(path):
                        folders.append(path)
    except Exception:
        pass

    return folders


def get_vscode_cwd(bundle_id: str) -> str | None:
    """Get the workspace path of the frontmost VS Code window.

    Uses the Accessibility API to read the window title, extracts the
    workspace name, then resolves it to a full path via VS Code's
    recent workspaces database.
    """
    workspace = AppKit.NSWorkspace.sharedWorkspace()
    app = workspace.frontmostApplication()
    pid = app.processIdentifier()

    title = _get_vscode_window_title(pid)
    if not title:
        return None

    folder_name = _extract_workspace_from_title(title)
    if not folder_name:
        return None

    # Resolve folder name to full path via recent workspaces
    for path in _get_vscode_recent_workspaces(bundle_id):
        if os.path.basename(path) == folder_name:
            return path

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


def _resolve_cwd(bundle_id: str) -> str | None:
    """Resolve the working directory for the frontmost app."""
    if bundle_id == "com.apple.Terminal":
        return get_terminal_cwd()
    if bundle_id in _VSCODE_BUNDLE_IDS:
        return get_vscode_cwd(bundle_id)
    return None


def get_context() -> tuple[str, str | None]:
    """Get current context: (app_name, BIRDWORD.md contents or None).

    Detects workspace for Terminal.app, VS Code, and VS Code Insiders.
    """
    bundle_id, app_name = get_frontmost_app()

    context_content = None
    cwd = _resolve_cwd(bundle_id)

    if cwd:
        context_file = find_context_file(cwd)
        if context_file:
            try:
                with open(context_file) as f:
                    context_content = f.read()
            except Exception:
                pass

    return app_name, context_content
