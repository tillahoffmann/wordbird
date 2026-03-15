"""CLI entry point for wordbird."""

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

from wordbird.config import (
    CONFIG_PATH,
    DEFAULT_CONFIG_TOML,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULTS,
    LOG_PATH,
    PIDFILE,
    ensure_data_dir,
    load_config,
    remove_server_info,
)

# --- PID management ---


def _read_pid() -> int | None:
    try:
        pid = int(PIDFILE.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        PIDFILE.unlink(missing_ok=True)
        return None


def _write_pid():
    ensure_data_dir()
    PIDFILE.write_text(str(os.getpid()))


def _remove_pid():
    PIDFILE.unlink(missing_ok=True)


# --- Shared helpers ---


def _check_permissions() -> bool:
    from wordbird.daemon.permissions import verify_permissions

    if not verify_permissions():
        print("   Fix permissions above, then try again.")
        return False
    return True


def _cli_overrides(args) -> dict:
    """Extract CLI overrides as a dict (only explicitly set values)."""
    result = {}
    if getattr(args, "model", None):
        result["transcription_model"] = args.model
    if getattr(args, "fix_model", None):
        result["fix_model"] = args.fix_model
    if getattr(args, "no_fix", False):
        result["no_fix"] = True
    if (
        getattr(args, "modifier_key", DEFAULTS["modifier_key"])
        != DEFAULTS["modifier_key"]
    ):
        result["modifier_key"] = args.modifier_key
    if getattr(args, "toggle_key", DEFAULTS["toggle_key"]) != DEFAULTS["toggle_key"]:
        result["toggle_key"] = args.toggle_key
    return result


def _create_daemon(cfg: dict, url: str | None = None):
    """Create a Daemon from resolved config."""
    from wordbird.daemon.daemon import Daemon
    from wordbird.server.server import server_url

    return Daemon(
        cfg=cfg,
        server_url=url or server_url(),
    )


# --- Commands ---


def _run_foreground(args):
    """Run wordbird in the foreground: start server + daemon as siblings."""
    existing = _read_pid()
    if existing is not None:
        print(f"🦜 Wordbird is already running (pid {existing}).")
        sys.exit(1)

    if not _check_permissions():
        sys.exit(1)

    _write_pid()
    server_proc = None
    try:
        from wordbird.config import resolve

        cfg = resolve(_cli_overrides(args))
        url = None

        if not args.no_server:
            from wordbird.server.server import start_server

            server_proc, url = start_server()
            print(f"🦜 Server started on {url}")

        daemon = _create_daemon(cfg, url)
        daemon.run()
    finally:
        if server_proc is not None:
            server_proc.terminate()
            server_proc.wait(timeout=5)
        remove_server_info()
        _remove_pid()


def _cmd_start(args):
    """Start wordbird in the background."""
    existing = _read_pid()
    if existing is not None:
        print(f"🦜 Wordbird is already running (pid {existing}).")
        return

    if not _check_permissions():
        sys.exit(1)

    print("🦜 Starting wordbird in the background...")

    # Build the command from CLI overrides
    cmd = [sys.executable, "-m", "wordbird"]
    overrides = _cli_overrides(args)
    if "transcription_model" in overrides:
        cmd += ["--model", overrides["transcription_model"]]
    if "fix_model" in overrides:
        cmd += ["--fix-model", overrides["fix_model"]]
    if overrides.get("no_fix"):
        cmd.append("--no-fix")
    if "modifier_key" in overrides:
        cmd += ["--modifier-key", overrides["modifier_key"]]
    if "toggle_key" in overrides:
        cmd += ["--toggle-key", overrides["toggle_key"]]

    ensure_data_dir()
    log_file = open(LOG_PATH, "a")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    finally:
        log_file.close()

    try:
        proc.wait(timeout=2)
        print(f"   ❌ Failed to start. Check {LOG_PATH}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        pass

    print(f"   ✅ Started (pid {proc.pid}).")
    print(f"   📄 Logs: {LOG_PATH}")


def _cmd_stop(args):
    pid = _read_pid()
    if pid is None:
        print("🦜 Wordbird is not running.")
        return

    print(f"🦜 Stopping wordbird (pid {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
        print("   ✅ Stopped.")
    except ProcessLookupError:
        print("   ⚠️  Process already gone.")
    _remove_pid()


def _cmd_status(args):
    pid = _read_pid()
    if pid is not None:
        print(f"🦜 Wordbird is running (pid {pid}).")
    else:
        print("🦜 Wordbird is not running.")


def _cmd_init(args):
    from wordbird.prompt import INIT_TEMPLATE

    path = Path.cwd() / "WORDBIRD.md"
    if path.exists():
        print(f"   ⚠️  {path} already exists.")
        return

    path.write_text(INIT_TEMPLATE)

    print(f"   ✅ Created {path}")
    print("   📝 Edit it to add project-specific terms and context.")


def _cmd_config(args):
    if not CONFIG_PATH.exists():
        ensure_data_dir()
        CONFIG_PATH.write_text(DEFAULT_CONFIG_TOML)
        print(f"   ✅ Created {CONFIG_PATH}")
    else:
        print(f"   📄 {CONFIG_PATH}\n")
        print(CONFIG_PATH.read_text())

    cfg = load_config()
    if cfg:
        print("   Active overrides:")
        for k, v in cfg.items():
            print(f"      {k} = {v!r}")
    else:
        print("   No overrides set (using defaults).")


def _cmd_history(args):
    from wordbird.server.history import recent

    rows = recent(limit=args.limit)
    if not rows:
        print("🦜 No transcription history.")
        return

    for row in reversed(rows):
        ts = row["timestamp"][:19].replace("T", " ")
        text = row["fixed_text"] or row["raw_text"]
        app = row["app_name"] or ""
        print(f"   [{ts}] ({app}) {text[:100]}{'...' if len(text) > 100 else ''}")


# --- Entry points ---


def main():
    parser = argparse.ArgumentParser(
        description="Voice dictation using Parakeet on Apple Silicon"
    )
    parser.add_argument("--model", default=None, help="Transcription model")
    parser.add_argument("--fix-model", default=None, help="Post-processor model")
    parser.add_argument(
        "--no-fix", action="store_true", help="Disable LLM post-processing"
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Don't spawn the API server (run it separately)",
    )
    parser.add_argument(
        "--modifier-key",
        default=DEFAULTS["modifier_key"],
        help=f"Modifier key (default: {DEFAULTS['modifier_key']})",
    )
    parser.add_argument(
        "--toggle-key",
        default=DEFAULTS["toggle_key"],
        help=f"Toggle key (default: {DEFAULTS['toggle_key']})",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("init", help="Create a WORDBIRD.md in the current directory")
    sub.add_parser("start", help="Start wordbird in the background")
    sub.add_parser("stop", help="Stop wordbird")
    sub.add_parser("status", help="Check if wordbird is running")
    sub.add_parser("config", help="Show or create the config file")

    history_parser = sub.add_parser("history", help="Show transcription history")
    history_parser.add_argument(
        "-n", "--limit", type=int, default=20, help="Number of entries (default: 20)"
    )

    args = parser.parse_args()

    commands = {
        "init": _cmd_init,
        "start": _cmd_start,
        "stop": _cmd_stop,
        "status": _cmd_status,
        "config": _cmd_config,
        "history": _cmd_history,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        _run_foreground(args)


def server_main():
    """Entry point for `wordbird-server`."""
    import uvicorn

    uvicorn.run(
        "wordbird.server.server:app", host=DEFAULT_HOST, port=DEFAULT_PORT, factory=True
    )


def daemon_main():
    """Entry point for `wordbird-daemon`."""
    if not _check_permissions():
        sys.exit(1)

    from wordbird.config import resolve

    cfg = resolve({})
    daemon = _create_daemon(cfg)
    daemon.run()


if __name__ == "__main__":
    main()
