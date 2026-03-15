"""FastAPI server for wordbird — API + ML inference + static frontend."""

import os
import webbrowser

# Disable huggingface_hub progress bars to avoid tqdm creating
# multiprocessing semaphores that leak on abrupt shutdown.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import wordbird.config as bw_config
from wordbird.config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULTS,
    FIX_MODEL_SUGGESTIONS,
    KEY_LABELS,
    MODIFIER_KEY_OPTIONS,
    TOGGLE_KEY_OPTIONS,
    TRANSCRIPTION_MODEL_SUGGESTIONS,
)
from wordbird.server.history import delete as delete_transcription
from wordbird.server.history import recent, stats
from wordbird.server.history import record as record_transcription

PACKAGE_DIR = Path(__file__).parent


def _get_effective_config() -> dict:
    """Get config with defaults filled in."""
    file_config = bw_config.load_config()
    result = dict(DEFAULTS)
    result.update(file_config)
    return result


class ConfigUpdate(BaseModel):
    modifier_key: str | None = None
    toggle_key: str | None = None
    transcription_model: str | None = None
    fix_model: str | None = None
    no_fix: bool = False
    sound: bool = True
    submit_with_return: bool = False


class PostProcessRequest(BaseModel):
    text: str
    context_content: str = ""


class HistoryRecord(BaseModel):
    raw_text: str
    fixed_text: str | None = None
    app_name: str | None = None
    cwd: str | None = None
    duration_seconds: float | None = None
    transcription_model: str | None = None
    fix_model: str | None = None
    word_count: int | None = None


def create_app() -> FastAPI:
    # ML models — shared state, all inference runs on a single dedicated thread
    # to avoid creating multiple loky worker pools
    from concurrent.futures import ThreadPoolExecutor

    _ml_state: dict = {"transcriber": None, "postprocessor": None}
    _ml_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ml")

    async def _run_ml(func, *args, **kwargs):
        """Run a function on the dedicated ML thread."""
        import asyncio
        import functools

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _ml_executor, functools.partial(func, *args, **kwargs)
        )

    def _get_transcriber():
        if _ml_state["transcriber"] is None:
            from wordbird.server.transcriber import Transcriber

            _ml_state["transcriber"] = Transcriber()
        return _ml_state["transcriber"]

    def _get_postprocessor():
        if _ml_state["postprocessor"] is None:
            from wordbird.server.postprocess import PostProcessor

            _ml_state["postprocessor"] = PostProcessor()
        return _ml_state["postprocessor"]

    def _cleanup():
        """Release ML models and worker pools."""
        import gc

        _ml_executor.shutdown(wait=False)
        try:
            import mlx.core as mx

            mx.synchronize()
            _ml_state["transcriber"] = None
            _ml_state["postprocessor"] = None
            gc.collect()
            mx.clear_cache()
        except Exception:
            pass
        try:
            from joblib.externals.loky import get_reusable_executor

            get_reusable_executor().shutdown(wait=False, kill_workers=True)
        except Exception:
            pass

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        import atexit

        # Preload models on startup
        print("🦜 Preloading ML models...")
        t = _get_transcriber()
        t.load()
        cfg = _get_effective_config()
        if not cfg.get("no_fix", False):
            pp = _get_postprocessor()
            pp.load()
        print("🦜 Models ready.")

        # Register atexit as backup — handles abrupt termination in --reload mode
        atexit.register(_cleanup)

        yield

        print("🦜 Shutting down...")
        _cleanup()
        atexit.unregister(_cleanup)

    app = FastAPI(title="Wordbird", lifespan=lifespan)

    @app.get("/api/config")
    def get_config():
        cfg = _get_effective_config()
        return {
            "config": cfg,
            "modifier_key_options": MODIFIER_KEY_OPTIONS,
            "toggle_key_options": TOGGLE_KEY_OPTIONS,
            "key_labels": KEY_LABELS,
            "transcription_model_suggestions": TRANSCRIPTION_MODEL_SUGGESTIONS,
            "fix_model_suggestions": FIX_MODEL_SUGGESTIONS,
        }

    @app.put("/api/config")
    def save_config(update: ConfigUpdate):
        import tomli_w

        bw_config.ensure_data_dir()
        # Only write values that differ from defaults
        data = update.model_dump(exclude_none=True)
        overrides = {k: v for k, v in data.items() if v != DEFAULTS.get(k)}
        with open(bw_config.CONFIG_PATH, "wb") as f:
            tomli_w.dump(overrides, f)
        return {"ok": True}

    @app.get("/api/transcriptions")
    def get_history(limit: int = 50):
        return {"transcriptions": recent(limit=limit)}

    @app.get("/api/stats")
    def get_stats():
        return stats()

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.post("/api/models/transcription/load")
    async def load_transcription_model():
        """Ensure the transcription model is loaded. Blocks until ready."""
        cfg = _get_effective_config()
        t = _get_transcriber()
        await _run_ml(t.load, cfg.get("transcription_model"))
        return {"ok": True, "model": t._loaded_model_id}

    @app.post("/api/models/postprocess/load")
    async def load_postprocess_model():
        """Ensure the post-processing model is loaded. Blocks until ready."""
        cfg = _get_effective_config()
        if cfg.get("no_fix"):
            return {"ok": True, "model": None}
        pp = _get_postprocessor()
        await _run_ml(pp.load, cfg.get("fix_model"))
        return {"ok": True, "model": pp._loaded_model_id}

    @app.post("/api/transcribe")
    async def transcribe(
        audio: UploadFile = File(...),
        context_content: str = Form(""),
    ):
        """Transcribe audio to text (speech-to-text only)."""
        wav_bytes = await audio.read()

        from wordbird.prompt import parse_wordbird_md

        # Priority: WORDBIRD.md front matter > user config > default
        cfg = _get_effective_config()
        front_matter = {}
        if context_content:
            front_matter, _ = parse_wordbird_md(context_content)

        transcription_model = front_matter.get(
            "transcription_model", cfg.get("transcription_model")
        )

        t = _get_transcriber()
        raw_text = await _run_ml(t.transcribe, wav_bytes, model_id=transcription_model)

        return {
            "raw_text": raw_text or "",
            "model": t._loaded_model_id,
        }

    @app.post("/api/postprocess")
    async def postprocess(req: PostProcessRequest):
        """Post-process transcribed text with LLM."""
        cfg = _get_effective_config()
        pp = _get_postprocessor()
        fixed_text, _ = await _run_ml(
            pp.fix,
            req.text,
            context_content=req.context_content or None,
            model_id=cfg.get("fix_model"),
        )
        return {
            "fixed_text": fixed_text,
            "model": pp._loaded_model_id,
        }

    @app.post("/api/transcriptions")
    def add_history(entry: HistoryRecord):
        """Record a transcription in history."""
        record_transcription(**entry.model_dump())
        return {"ok": True}

    @app.delete("/api/transcriptions/{transcription_id}")
    def remove_transcription(transcription_id: int):
        """Delete a transcription by ID."""
        if delete_transcription(transcription_id):
            return {"ok": True}
        return {"ok": False, "error": "not found"}

    @app.post("/api/transcribe/complete")
    async def transcribe_complete(
        audio: UploadFile = File(...),
        duration_seconds: float = Form(0.0),
        app_name: str = Form(""),
        cwd: str = Form(""),
        context_content: str = Form(""),
        no_fix: bool = Form(False),
    ):
        """Transcribe + postprocess + record history in one call.

        Used by external clients (Claude plugin, etc.) that don't need
        intermediate UI updates.
        """
        wav_bytes = await audio.read()

        from wordbird.prompt import parse_wordbird_md

        cfg = _get_effective_config()
        front_matter = {}
        if context_content:
            front_matter, _ = parse_wordbird_md(context_content)

        transcription_model = front_matter.get(
            "transcription_model", cfg.get("transcription_model")
        )

        t = _get_transcriber()
        raw_text = await _run_ml(t.transcribe, wav_bytes, model_id=transcription_model)

        if not raw_text:
            return {"raw_text": "", "fixed_text": None, "word_count": 0}

        skip_fix = no_fix or cfg.get("no_fix", False)
        fixed_text = None

        if not skip_fix:
            pp = _get_postprocessor()
            fixed_text, _ = await _run_ml(
                pp.fix,
                raw_text,
                context_content=context_content or None,
                model_id=cfg.get("fix_model"),
            )

        final_text = fixed_text or raw_text
        word_count = len(final_text.split())

        record_transcription(
            raw_text=raw_text,
            fixed_text=fixed_text,
            app_name=app_name or None,
            cwd=cwd or None,
            duration_seconds=duration_seconds,
            transcription_model=t._loaded_model_id,
            fix_model=_ml_state["postprocessor"]._loaded_model_id
            if _ml_state["postprocessor"]
            else None,
            word_count=word_count,
        )

        return {
            "raw_text": raw_text,
            "fixed_text": fixed_text,
            "final_text": final_text,
            "word_count": word_count,
        }

    # Serve the React frontend (static files) — must be last
    frontend_dist = PACKAGE_DIR / "static"
    if frontend_dist.is_dir():
        app.mount(
            "/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend"
        )

    return app


# ASGI app for `uvicorn wordbird.server.server:app`
app = create_app()


def _find_available_port(host: str, start_port: int, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port."""
    import socket

    for offset in range(max_attempts):
        port = start_port + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"No available port found in range {start_port}-{start_port + max_attempts - 1}"
    )


def start_server(wait: bool = True, timeout: float = 120) -> tuple:
    """Start the server in a subprocess.

    Finds an available port (starting from DEFAULT_PORT), starts uvicorn,
    writes server.json for the daemon, and waits for the health endpoint.
    """
    import subprocess
    import sys
    import time

    import httpx

    host = DEFAULT_HOST
    port = _find_available_port(host, DEFAULT_PORT)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "wordbird.server.server:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
    )

    url = f"http://{host}:{port}"

    if wait:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"Server process exited with code {proc.returncode}")
            try:
                resp = httpx.get(f"{url}/api/health", timeout=2)
                if resp.status_code == 200:
                    break
            except httpx.ConnectError:
                pass
            time.sleep(0.5)
        else:
            proc.terminate()
            raise RuntimeError(f"Server failed to start within {timeout}s")

    # Write server info so daemon and CLI can discover the port
    bw_config.write_server_info(host, port, proc.pid)

    return proc, url


def server_url() -> str:
    """Get the server URL, reading from server.json if available."""
    info = bw_config.read_server_info()
    if info:
        host, port = info
        return f"http://{host}:{port}"
    return f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"


VITE_DEV_URL = "http://localhost:5173"


def open_dashboard(hash: str | None = None):
    """Open the dashboard in the default browser.

    Prefers the Vite dev server if it's running (for development),
    otherwise falls back to the backend's static files.
    """
    import httpx

    suffix = f"#{hash}" if hash else ""
    try:
        resp = httpx.get(VITE_DEV_URL, timeout=1)
        if resp.status_code == 200:
            webbrowser.open(f"{VITE_DEV_URL}{suffix}")
            return
    except Exception:
        pass
    webbrowser.open(f"{server_url()}{suffix}")
