"""CLI entry point for paracorder."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Voice dictation daemon using Parakeet on Apple Silicon"
    )
    parser.add_argument(
        "--check-permissions",
        action="store_true",
        help="Check required macOS permissions and exit",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model ID to use (default: mlx-community/parakeet-tdt-0.6b-v2)",
    )

    args = parser.parse_args()

    if args.check_permissions:
        from paracorder.permissions import verify_permissions

        ok = verify_permissions()
        sys.exit(0 if ok else 1)

    # Quick permission check before starting
    from paracorder.permissions import verify_permissions

    if not verify_permissions():
        print("Fix permissions above, then try again.")
        sys.exit(1)

    from paracorder.daemon import Daemon

    daemon = Daemon(model_id=args.model)
    daemon.run()


if __name__ == "__main__":
    main()
