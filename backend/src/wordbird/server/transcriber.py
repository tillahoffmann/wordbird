"""Speech-to-text transcription using Parakeet via mlx-audio."""

import gc
import os
import tempfile

import mlx.core as mx
from mlx_audio.stt.utils import load_model

from wordbird.prompt import DEFAULT_TRANSCRIPTION_MODEL


class Transcriber:
    """Transcribes audio using MLX-based models on Apple Silicon."""

    def __init__(self, model_id: str | None = None):
        self._cli_model_id = model_id
        self._default_model_id = model_id or DEFAULT_TRANSCRIPTION_MODEL
        self._model = None
        self._loaded_model_id: str | None = None

    def load(self, model_id: str | None = None):
        """Load (or reload) the transcription model."""
        model_id = model_id or self._default_model_id
        if self._loaded_model_id == model_id:
            return

        print(f"   🧠 Loading transcription model ({model_id})...")
        mx.synchronize()
        self._model = None
        gc.collect()
        mx.clear_cache()
        # Cap MLX's buffer cache so it can't grow unbounded over a long-lived
        # session (the cache is retained, not freed, while the model stays loaded).
        mx.set_cache_limit(2 * 1024**3)
        self._model = load_model(model_id)
        self._loaded_model_id = model_id
        print("   🧠 Transcription model ready.")

    def transcribe(self, wav_bytes: bytes, model_id: str | None = None) -> str:
        """Transcribe WAV audio bytes to text."""
        # CLI flag overrides front matter
        effective_id = self._cli_model_id or model_id or self._default_model_id
        self.load(effective_id)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp_path = f.name

        try:
            assert self._model is not None
            result = self._model.generate(tmp_path)
            return result.text.strip()
        finally:
            os.unlink(tmp_path)
            # Return MLX's scratch/activation cache to the system. Without this,
            # the cache ratchets up across runs and never shrinks while the model
            # stays loaded (Apple Silicon unified memory).
            mx.clear_cache()
