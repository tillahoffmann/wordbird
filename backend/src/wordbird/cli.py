"""CLI entry point for wordbird."""

import argparse
import os
import signal
import subprocess
import sys

from wordbird.config import (
    CONFIG_PATH,
    DEFAULTS,
    DEFAULT_CONFIG_TOML,
    LOG_PATH,
    PIDFILE,
    ensure_config_dir,
    load_config,
)
from wordbird.server.server import HOST, PORT


def _read_pid() -> int | None:
    """Read PID from pidfile, return None if stale or missing."""
    try:
        with open(PIDFILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        try:
            os.unlink(PIDFILE)
        except FileNotFoundError:
            pass
        return None


def _write_pid():
    ensure_config_dir()
    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))


def _remove_pid():
    try:
        os.unlink(PIDFILE)
    except FileNotFoundError:
        pass


def _check_permissions() -> bool:
    from wordbird.daemon.permissions import verify_permissions

    if not verify_permissions():
        print("   Fix permissions above, then try again.")
        return False
    return True


def _cli_overrides(args) -> dict:
    """Extract CLI overrides as a dict (only explicitly set values)."""
    result = {}
    if args.model:
        result["transcription_model"] = args.model
    if args.fix_model:
        result["fix_model"] = args.fix_model
    if args.no_fix:
        result["no_fix"] = True
    if args.hold_key != DEFAULTS["hold_key"]:
        result["hold_key"] = args.hold_key
    if args.toggle_key != DEFAULTS["toggle_key"]:
        result["toggle_key"] = args.toggle_key
    return result


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
        from wordbird.daemon.daemon import Daemon

        cli = _cli_overrides(args)
        cfg = resolve(cli)
        server_url = f"http://{HOST}:{PORT}"

        if not args.no_server:
            # Start server as sibling subprocess
            from wordbird.server.server import start_server

            server_proc, server_url = start_server()
            print(f"🦜 Server started on {server_url}")

        daemon = Daemon(
            hold_key=cfg["hold_key"],
            toggle_key=cfg["toggle_key"],
            server_url=server_url,
            no_fix=cfg["no_fix"],
        )
        daemon.run()
    finally:
        if server_proc is not None:
            server_proc.terminate()
            server_proc.wait(timeout=5)
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

    cmd = [sys.executable, "-m", "wordbird"]
    if args.model:
        cmd += ["--model", args.model]
    if args.fix_model:
        cmd += ["--fix-model", args.fix_model]
    if args.no_fix:
        cmd.append("--no-fix")
    if args.hold_key != DEFAULTS["hold_key"]:
        cmd += ["--hold-key", args.hold_key]
    if args.toggle_key != DEFAULTS["toggle_key"]:
        cmd += ["--toggle-key", args.toggle_key]

    ensure_config_dir()
    log_file = open(LOG_PATH, "a")

    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

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
    from wordbird.prompt import DEFAULT_TEMPLATE

    path = os.path.join(os.getcwd(), "WORDBIRD.md")
    if os.path.exists(path):
        print(f"   ⚠️  {path} already exists.")
        return

    with open(path, "w") as f:
        f.write(DEFAULT_TEMPLATE)

    print(f"   ✅ Created {path}")
    print("   📝 Edit it to add project-specific terms and context.")


def _cmd_config(args):
    """Show or create the config file."""
    if not os.path.exists(CONFIG_PATH):
        ensure_config_dir()
        with open(CONFIG_PATH, "w") as f:
            f.write(DEFAULT_CONFIG_TOML)
        print(f"   ✅ Created {CONFIG_PATH}")
    else:
        print(f"   📄 {CONFIG_PATH}\n")
        with open(CONFIG_PATH) as f:
            print(f.read())

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


def main():
    parser = argparse.ArgumentParser(
        description="Voice dictation using Parakeet on Apple Silicon"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Transcription model",
    )
    parser.add_argument(
        "--fix-model",
        default=None,
        help="Post-processor model",
    )
    parser.add_argument(
        "--no-fix",
        action="store_true",
        help="Disable LLM post-processing",
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Don't spawn the API server (run it separately)",
    )
    parser.add_argument(
        "--hold-key",
        default=DEFAULTS["hold_key"],
        help=f"Hold key (default: {DEFAULTS['hold_key']})",
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
        "-n",
        "--limit",
        type=int,
        default=20,
        help="Number of entries to show (default: 20)",
    )

    args = parser.parse_args()

    if args.command == "init":
        _cmd_init(args)
    elif args.command == "start":
        _cmd_start(args)
    elif args.command == "stop":
        _cmd_stop(args)
    elif args.command == "status":
        _cmd_status(args)
    elif args.command == "config":
        _cmd_config(args)
    elif args.command == "history":
        _cmd_history(args)
    else:
        _run_foreground(args)


def server_main():
    """Entry point for `wordbird-server` — runs just the API server."""
    import uvicorn

    from wordbird.server.server import HOST, PORT

    uvicorn.run("wordbird.server.server:app", host=HOST, port=PORT)


def daemon_main():
    """Entry point for `wordbird-daemon` — runs just the daemon (no server)."""
    if not _check_permissions():
        sys.exit(1)

    from wordbird.config import resolve
    from wordbird.daemon.daemon import Daemon

    cfg = resolve({})
    daemon = Daemon(
        hold_key=cfg["hold_key"],
        toggle_key=cfg["toggle_key"],
        server_url=f"http://{HOST}:{PORT}",
        no_fix=cfg["no_fix"],
    )
    daemon.run()


if __name__ == "__main__":
    main()
