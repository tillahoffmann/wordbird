"""CLI entry point for birdword."""

import argparse
import os
import signal
import subprocess
import sys

PIDFILE = os.path.expanduser("~/.birdword.pid")


def _read_pid() -> int | None:
    """Read PID from pidfile, return None if stale or missing."""
    try:
        with open(PIDFILE) as f:
            pid = int(f.read().strip())
        # Check if process is actually running
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        # Clean up stale pidfile
        try:
            os.unlink(PIDFILE)
        except FileNotFoundError:
            pass
        return None


def _write_pid():
    """Write current PID to pidfile."""
    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))


def _remove_pid():
    """Remove pidfile."""
    try:
        os.unlink(PIDFILE)
    except FileNotFoundError:
        pass


def _check_permissions() -> bool:
    """Check permissions, blocking until resolved."""
    from birdword.permissions import verify_permissions

    if not verify_permissions():
        print("   Fix permissions above, then try again.")
        return False
    return True


def _run_daemon(args):
    """Run the daemon (blocking). Enforces singleton."""
    existing = _read_pid()
    if existing is not None:
        print(f"🐦 Birdword is already running (pid {existing}).")
        sys.exit(1)

    if not _check_permissions():
        sys.exit(1)

    _write_pid()
    try:
        from birdword.daemon import Daemon

        daemon = Daemon(
            model_id=args.model,
            fix_model_id=args.fix_model,
            no_fix=args.no_fix,
            hold_key=args.hold_key,
            toggle_key=args.toggle_key,
        )
        daemon.run()
    finally:
        _remove_pid()


def _cmd_start(args):
    """Start birdword in the background."""
    existing = _read_pid()
    if existing is not None:
        print(f"🐦 Birdword is already running (pid {existing}).")
        return

    # Check permissions in the foreground first
    if not _check_permissions():
        sys.exit(1)

    print("🐦 Starting birdword in the background...")

    # Build the command to run ourselves in blocking mode
    cmd = [sys.executable, "-m", "birdword"]
    if args.model:
        cmd += ["--model", args.model]
    if args.fix_model:
        cmd += ["--fix-model", args.fix_model]
    if args.no_fix:
        cmd.append("--no-fix")
    if args.hold_key != "rcmd":
        cmd += ["--hold-key", args.hold_key]
    if args.toggle_key != "space":
        cmd += ["--toggle-key", args.toggle_key]

    # Launch detached subprocess
    log_path = os.path.expanduser("~/.birdword.log")
    log_file = open(log_path, "a")

    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait briefly to make sure it didn't crash immediately
    try:
        proc.wait(timeout=2)
        # If we get here, the process exited
        print(f"   ❌ Failed to start. Check {log_path}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        pass  # Still running — good

    print(f"   ✅ Started (pid {proc.pid}).")
    print(f"   📄 Logs: {log_path}")


def _cmd_stop(args):
    """Stop birdword."""
    pid = _read_pid()
    if pid is None:
        print("🐦 Birdword is not running.")
        return

    print(f"🐦 Stopping birdword (pid {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
        print("   ✅ Stopped.")
    except ProcessLookupError:
        print("   ⚠️  Process already gone.")
    _remove_pid()


def _cmd_status(args):
    """Check if birdword is running."""
    pid = _read_pid()
    if pid is not None:
        print(f"🐦 Birdword is running (pid {pid}).")
    else:
        print("🐦 Birdword is not running.")


def main():
    parser = argparse.ArgumentParser(
        description="Voice dictation using Parakeet on Apple Silicon"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Transcription model (default: mlx-community/parakeet-tdt-0.6b-v2)",
    )
    parser.add_argument(
        "--fix-model",
        default=None,
        help="Post-processor model (default: mlx-community/Qwen2.5-0.5B-Instruct-4bit)",
    )
    parser.add_argument(
        "--no-fix",
        action="store_true",
        help="Disable LLM post-processing of transcription",
    )
    parser.add_argument(
        "--hold-key",
        default="rcmd",
        help="Hold key for record (default: rcmd). Options: rcmd, lcmd, ralt, lalt",
    )
    parser.add_argument(
        "--toggle-key",
        default="space",
        help="Toggle key pressed with hold key (default: space)",
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="Start birdword in the background")
    sub.add_parser("stop", help="Stop birdword")
    sub.add_parser("status", help="Check if birdword is running")

    args = parser.parse_args()

    if args.command == "start":
        _cmd_start(args)
    elif args.command == "stop":
        _cmd_stop(args)
    elif args.command == "status":
        _cmd_status(args)
    else:
        # No subcommand — run blocking (default)
        _run_daemon(args)


if __name__ == "__main__":
    main()
