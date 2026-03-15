"""Detect the focused app and resolve project context."""

import glob
import json
import logging
import subprocess
from pathlib import Path

import AppKit
import Quartz

from wordbird.config import DATA_DIR

logger = logging.getLogger(__name__)

VSCODE_CONTEXT_PATH = DATA_DIR / "vscode-context.json"
EDITOR_CONTEXTS_DIR = DATA_DIR / "editor-contexts"

_VSCODE_BUNDLE_IDS = {
    "com.microsoft.VSCode",
    "com.microsoft.VSCodeInsiders",
}

_ZED_BUNDLE_IDS = {
    "dev.zed.Zed",
    "dev.zed.Zed-Preview",
}


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


def _read_active_context(frontmost_pid: int) -> tuple[str | None, str | None]:
    """Read workspace and WORDBIRD.md from active-context.json."""
    try:
        data = json.loads(VSCODE_CONTEXT_PATH.read_text())

        ctx_pid = data.get("pid")
        if ctx_pid != frontmost_pid and not _is_child_of(ctx_pid, frontmost_pid):
            return None, None

        return data.get("workspace"), data.get("wordbird_md")
    except FileNotFoundError:
        return None, None
    except Exception:
        logger.debug("Failed to read active-context.json", exc_info=True)
        return None, None


def _get_frontmost_window_title(pid: int) -> str | None:
    """Get the title of the frontmost window owned by *pid*."""
    try:
        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
        )
        for win in windows:
            if (
                win.get("kCGWindowOwnerPID") == pid
                and win.get("kCGWindowLayer", -1) == 0
            ):
                title = win.get("kCGWindowName")
                if title:
                    return title
    except Exception:
        logger.debug("Failed to get window title for pid %d", pid, exc_info=True)
    return None


def _read_editor_context(frontmost_pid: int) -> tuple[str | None, str | None]:
    """Scan editor-contexts/ and return context matching the frontmost window."""
    pattern = os.path.join(EDITOR_CONTEXTS_DIR, "*.json")
    files = glob.glob(pattern)
    if not files:
        return None, None

    # Collect valid (alive, child-of-frontmost) contexts with mtime.
    candidates: list[tuple[float, str, str | None]] = []
    stale: list[str] = []

    for path in files:
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue

        ctx_pid = data.get("pid")
        if ctx_pid is None:
            continue

        # Check if process is still alive.
        try:
            os.kill(ctx_pid, 0)
        except (ProcessLookupError, OSError):
            stale.append(path)
            continue

        if ctx_pid != frontmost_pid and not _is_child_of(ctx_pid, frontmost_pid):
            continue

        workspace = data.get("workspace")
        wordbird_md = data.get("wordbird_md")
        mtime = os.path.getmtime(path)
        candidates.append((mtime, workspace, wordbird_md))

    # Clean up stale files from dead processes.
    for path in stale:
        try:
            os.unlink(path)
        except Exception:
            pass

    if not candidates:
        return None, None

    if len(candidates) == 1:
        _, workspace, wordbird_md = candidates[0]
        return workspace, wordbird_md

    # Multiple candidates — match against window title.
    title = _get_frontmost_window_title(frontmost_pid)
    if title:
        for mtime, workspace, wordbird_md in candidates:
            if workspace and os.path.basename(workspace) in title:
                return workspace, wordbird_md

    # Fallback: most recently modified context file.
    candidates.sort(reverse=True)  # newest first by mtime
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

    elif bundle_id in _VSCODE_BUNDLE_IDS:
        ws = AppKit.NSWorkspace.sharedWorkspace()
        frontmost_pid = ws.frontmostApplication().processIdentifier()
        cwd, context_content = _read_active_context(frontmost_pid)

    elif bundle_id in _ZED_BUNDLE_IDS:
        ws = AppKit.NSWorkspace.sharedWorkspace()
        frontmost_pid = ws.frontmostApplication().processIdentifier()
        cwd, context_content = _read_editor_context(frontmost_pid)

    return app_name, cwd, context_content
