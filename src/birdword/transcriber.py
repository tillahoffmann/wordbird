"""Speech-to-text transcription using Parakeet via mlx-audio."""

import tempfile
import os

MODEL_ID = "mlx-community/parakeet-tdt-0.6b-v2"


class Transcriber:
    """Transcribes audio using the Parakeet TDT model on Apple Silicon."""

    def __init__(self, model_id: str = MODEL_ID):
        self.model_id = model_id
        self._model = None

    def load(self):
        """Pre-load the model into memory."""
        from mlx_audio.stt.utils import load_model

        print(f"Loading model {self.model_id}...")
        self._model = load_model(self.model_id)
        print("Model loaded.")

    def transcribe(self, wav_bytes: bytes) -> str:
        """Transcribe WAV audio bytes to text."""
        if self._model is None:
            self.load()

        # Write to a temp file since mlx-audio expects a file path
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp_path = f.name

        try:
            result = self._model.generate(tmp_path)
            return result.text.strip()
        finally:
            os.unlink(tmp_path)
