"""Detect the focused app and resolve project context."""

import json
import logging
import os
import subprocess
from pathlib import Path

import AppKit
import ApplicationServices

from wordbird.config import DATA_DIR

logger = logging.getLogger(__name__)

EDITOR_CONTEXTS_DIR = DATA_DIR / "editor-contexts"


def get_frontmost_app() -> tuple[str, str]:
    """Return (bundle_id, app_name) of the frontmost application."""
    workspace = AppKit.NSWorkspace.sharedWorkspace()
    app = workspace.frontmostApplication()
    return (app.bundleIdentifier() or "", app.localizedName() or "")


def get_terminal_cwd() -> str | None:
    """Get the cwd of the shell in the frontmost Terminal.app tab."""
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
        logger.debug("Failed to detect Terminal.app cwd", exc_info=True)

    return None


def _is_child_of(child_pid: int, parent_pid: int) -> bool:
    """Check if child_pid is a descendant of parent_pid."""
    try:
        result = subprocess.run(
            ["ps", "-o", "ppid=", "-p", str(child_pid)],
            capture_output=True,
            text=True,
            timeout=2,
        )
        ppid = int(result.stdout.strip())
        if ppid == parent_pid:
            return True
        if ppid <= 1:
            return False
        return _is_child_of(ppid, parent_pid)
    except Exception:
        logger.debug("Failed to check process ancestry", exc_info=True)
        return False


def _process_is_alive(pid: int) -> bool:
    """Check if a process is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _get_focused_window_title(pid: int) -> str | None:
    """Get the title of the focused window for a given PID using Accessibility API."""
    try:
        app_ref = ApplicationServices.AXUIElementCreateApplication(pid)
        err, focused_window = ApplicationServices.AXUIElementCopyAttributeValue(
            app_ref, "AXFocusedWindow", None
        )
        if err or focused_window is None:
            return None
        err, title = ApplicationServices.AXUIElementCopyAttributeValue(
            focused_window, "AXTitle", None
        )
        if err or title is None:
            return None
        return str(title)
    except Exception:
        logger.debug("Failed to get window title for pid %d", pid, exc_info=True)
        return None


def _cleanup_stale_contexts():
    """Remove context files for processes that are no longer running."""
    if not EDITOR_CONTEXTS_DIR.is_dir():
        return
    for path in EDITOR_CONTEXTS_DIR.iterdir():
        if path.suffix != ".json":
            continue
        try:
            data = json.loads(path.read_text())
            pid = data.get("pid")
            if pid is not None and not _process_is_alive(pid):
                path.unlink()
                logger.debug("Cleaned up stale context: %s (pid %d)", path.name, pid)
        except Exception:
            try:
                path.unlink()
            except Exception:
                pass


def _read_wordbird_md_from_disk(workspace: str) -> str | None:
    """Read WORDBIRD.md from a workspace directory on disk."""
    try:
        return (Path(workspace) / "WORDBIRD.md").read_text()
    except Exception:
        return None


def _read_editor_contexts(frontmost_pid: int) -> tuple[str | None, str | None]:
    """Scan editor-contexts/ for the context matching the frontmost app.

    Cleans up stale context files first, then matches by PID ancestry.
    If multiple candidates match, checks if all WORDBIRD.md contents are
    identical (in which case it doesn't matter which we pick). If they
    differ, reads from disk to find the one matching the focused window.
    """
    _cleanup_stale_contexts()

    if not EDITOR_CONTEXTS_DIR.is_dir():
        return None, None

    # Collect candidates that belong to the frontmost app
    candidates: list[tuple[float, str | None, str | None]] = []
    for path in EDITOR_CONTEXTS_DIR.iterdir():
        if path.suffix != ".json":
            continue
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue

        ctx_pid = data.get("pid")
        if ctx_pid is None:
            continue

        if ctx_pid != frontmost_pid and not _is_child_of(ctx_pid, frontmost_pid):
            continue

        workspace = data.get("workspace")
        wordbird_md = data.get("wordbird_md")
        mtime = path.stat().st_mtime
        candidates.append((mtime, workspace, wordbird_md))

    if not candidates:
        return None, None

    if len(candidates) == 1:
        _, workspace, wordbird_md = candidates[0]
        return workspace, wordbird_md

    # Multiple candidates. If all WORDBIRD.md contents are the same,
    # it doesn't matter which we pick.
    contents = {c[2] for c in candidates}
    if len(contents) == 1:
        # All identical — pick the most recent
        candidates.sort(reverse=True)
        _, workspace, wordbird_md = candidates[0]
        return workspace, wordbird_md

    # Contents differ — use the focused window title to find the right workspace,
    # then read WORDBIRD.md from disk to verify.
    title = _get_focused_window_title(frontmost_pid)
    if title:
        for _, workspace, wordbird_md in candidates:
            if workspace and Path(workspace).name in title:
                return workspace, wordbird_md

    # Last resort: most recently modified
    candidates.sort(reverse=True)
    _, workspace, wordbird_md = candidates[0]
    return workspace, wordbird_md


def find_context_file(start_dir: str) -> Path | None:
    """Walk up from start_dir looking for a WORDBIRD.md file."""
    current = Path(start_dir).resolve()
    while True:
        candidate = current / "WORDBIRD.md"
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def get_context() -> tuple[str, str | None, str | None]:
    """Get current context: (app_name, cwd, WORDBIRD.md contents or None)."""
    bundle_id, app_name = get_frontmost_app()

    cwd = None
    context_content = None

    if bundle_id == "com.apple.Terminal":
        cwd = get_terminal_cwd()
        if cwd:
            context_file = find_context_file(cwd)
            if context_file:
                try:
                    context_content = context_file.read_text()
                except Exception:
                    logger.debug("Failed to read %s", context_file, exc_info=True)
    else:
        # Try editor-contexts/ (works for any editor with an extension)
        ws = AppKit.NSWorkspace.sharedWorkspace()
        frontmost_pid = ws.frontmostApplication().processIdentifier()
        cwd, context_content = _read_editor_contexts(frontmost_pid)

    return app_name, cwd, context_content
