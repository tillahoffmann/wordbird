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
        print("Fix permissions above, then try again.")
        return False
    return True


def _run_daemon(args):
    """Run the daemon (blocking). Enforces singleton."""
    existing = _read_pid()
    if existing is not None:
        print(f"birdword is already running (pid {existing}).")
        sys.exit(1)

    if not _check_permissions():
        sys.exit(1)

    _write_pid()
    try:
        from birdword.daemon import Daemon

        daemon = Daemon(model_id=args.model, no_fix=args.no_fix)
        daemon.run()
    finally:
        _remove_pid()


def _cmd_start(args):
    """Start birdword in the background."""
    existing = _read_pid()
    if existing is not None:
        print(f"birdword is already running (pid {existing}).")
        return

    # Check permissions in the foreground first
    if not _check_permissions():
        sys.exit(1)

    print("Starting birdword in the background...")

    # Build the command to run ourselves in blocking mode
    cmd = [sys.executable, "-m", "birdword"]
    if args.model:
        cmd += ["--model", args.model]
    if args.no_fix:
        cmd.append("--no-fix")

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
        print(f"birdword failed to start. Check {log_path}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        pass  # Still running — good

    print(f"birdword started (pid {proc.pid}).")
    print(f"Logs: {log_path}")


def _cmd_stop(args):
    """Stop birdword."""
    pid = _read_pid()
    if pid is None:
        print("birdword is not running.")
        return

    print(f"Stopping birdword (pid {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
        print("Stopped.")
    except ProcessLookupError:
        print("Process already gone.")
    _remove_pid()


def _cmd_status(args):
    """Check if birdword is running."""
    pid = _read_pid()
    if pid is not None:
        print(f"birdword is running (pid {pid}).")
    else:
        print("birdword is not running.")


def main():
    parser = argparse.ArgumentParser(
        description="Voice dictation using Parakeet on Apple Silicon"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model ID (default: mlx-community/parakeet-tdt-0.6b-v2)",
    )
    parser.add_argument(
        "--no-fix",
        action="store_true",
        help="Disable LLM post-processing of transcription",
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
