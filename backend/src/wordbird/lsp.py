"""Minimal LSP server that bridges editor workspace context to the Wordbird daemon.

Speaks JSON-RPC 2.0 over stdio with Content-Length framing. Writes a per-instance
context file to ~/.wordbird/editor-contexts/<pid>.json so the daemon can look up
the active workspace and WORDBIRD.md content.

Zero external dependencies — stdlib only.
"""

import json
import logging
import os
import sys
from urllib.parse import unquote, urlparse

DATA_DIR = os.path.expanduser("~/.wordbird")
CONTEXTS_DIR = os.path.join(DATA_DIR, "editor-contexts")

logger = logging.getLogger("wordbird-lsp")


def _context_path() -> str:
    return os.path.join(CONTEXTS_DIR, f"{os.getpid()}.json")


def _uri_to_path(uri: str) -> str:
    """Convert a file:// URI to a local filesystem path."""
    parsed = urlparse(uri)
    return unquote(parsed.path)


# ---------------------------------------------------------------------------
# Context file I/O
# ---------------------------------------------------------------------------

_workspace_root: str | None = None


def _read_wordbird_md() -> str | None:
    """Read WORDBIRD.md from the workspace root, or return None."""
    if _workspace_root is None:
        return None
    path = os.path.join(_workspace_root, "WORDBIRD.md")
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None
    except Exception:
        logger.debug("Failed to read WORDBIRD.md", exc_info=True)
        return None


def _write_context() -> None:
    """Write the context file for the daemon."""
    try:
        os.makedirs(CONTEXTS_DIR, exist_ok=True)
        ctx = {
            "pid": os.getpid(),
            "workspace": _workspace_root,
            "wordbird_md": _read_wordbird_md(),
        }
        path = _context_path()
        with open(path, "w") as f:
            json.dump(ctx, f, indent=2)
            f.write("\n")
    except Exception:
        logger.debug("Failed to write context file", exc_info=True)


def _delete_context() -> None:
    """Remove the context file on shutdown."""
    try:
        os.unlink(_context_path())
    except FileNotFoundError:
        pass
    except Exception:
        logger.debug("Failed to delete context file", exc_info=True)


# ---------------------------------------------------------------------------
# JSON-RPC transport
# ---------------------------------------------------------------------------


def _read_message() -> dict | None:
    """Read a single JSON-RPC message from stdin (Content-Length framing)."""
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None  # EOF
        line_str = line.decode("utf-8").rstrip("\r\n")
        if line_str == "":
            break  # end of headers
        if ":" in line_str:
            key, value = line_str.split(":", 1)
            headers[key.strip()] = value.strip()

    length = int(headers.get("Content-Length", "0"))
    if length == 0:
        return None

    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))


def _write_message(msg: dict) -> None:
    """Write a JSON-RPC message to stdout with Content-Length framing."""
    body = json.dumps(msg).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    sys.stdout.buffer.write(header + body)
    sys.stdout.buffer.flush()


def _respond(id: int | str, result: object) -> None:
    _write_message({"jsonrpc": "2.0", "id": id, "result": result})


# ---------------------------------------------------------------------------
# LSP handlers
# ---------------------------------------------------------------------------


def _handle_initialize(params: dict) -> dict:
    global _workspace_root

    root_uri = params.get("rootUri")
    if root_uri:
        _workspace_root = _uri_to_path(root_uri)
    else:
        root_path = params.get("rootPath")
        if root_path:
            _workspace_root = root_path

    _write_context()

    return {
        "capabilities": {
            "textDocumentSync": {
                "openClose": True,
                "save": True,
            },
        },
    }


def _handle_did_open(params: dict) -> None:
    uri = params.get("textDocument", {}).get("uri", "")
    if uri.endswith("WORDBIRD.md"):
        _write_context()


def _handle_did_save(params: dict) -> None:
    uri = params.get("textDocument", {}).get("uri", "")
    if uri.endswith("WORDBIRD.md"):
        _write_context()


def _handle_shutdown() -> None:
    _delete_context()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        stream=sys.stderr,
        format="%(name)s: %(message)s",
    )

    shutdown_requested = False

    while True:
        msg = _read_message()
        if msg is None:
            break

        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        try:
            if method == "initialize":
                result = _handle_initialize(params)
                _respond(msg_id, result)
            elif method == "initialized":
                pass  # notification, no response
            elif method == "textDocument/didOpen":
                _handle_did_open(params)
            elif method == "textDocument/didSave":
                _handle_did_save(params)
            elif method == "shutdown":
                _handle_shutdown()
                _respond(msg_id, None)
                shutdown_requested = True
            elif method == "exit":
                sys.exit(0 if shutdown_requested else 1)
            elif msg_id is not None:
                # Unknown request — respond with method not found
                _write_message(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}",
                        },
                    }
                )
        except Exception:
            logger.debug("Error handling %s", method, exc_info=True)
            if msg_id is not None:
                _write_message(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                        },
                    }
                )


if __name__ == "__main__":
    main()
