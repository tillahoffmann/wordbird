"""Integration tests for ML models — verifies each suggested model loads and produces output.

These tests download and load ML models, so they are slow. Run explicitly with:
    uv run pytest tests/test_models.py -v
They are excluded from the default test run via the 'slow' marker.
"""

import os

import pytest

from wordbird.config import FIX_MODEL_SUGGESTIONS, TRANSCRIPTION_MODEL_SUGGESTIONS

pytestmark = pytest.mark.slow

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
EXAMPLE_WAV = os.path.join(ASSETS_DIR, "example.wav")


@pytest.mark.parametrize("model_id", TRANSCRIPTION_MODEL_SUGGESTIONS)
def test_transcription_model(model_id):
    from wordbird.server.transcriber import Transcriber

    t = Transcriber(model_id)
    t.load()

    with open(EXAMPLE_WAV, "rb") as f:
        wav_bytes = f.read()

    text = t.transcribe(wav_bytes)
    assert isinstance(text, str)
    assert len(text) > 0, f"Model {model_id} produced empty transcription"


@pytest.mark.parametrize("model_id", FIX_MODEL_SUGGESTIONS)
def test_fix_model(model_id):
    from wordbird.server.postprocess import PostProcessor

    pp = PostProcessor(model_id)
    pp.load()

    fixed, _ = pp.fix("the quik brown fox jumpd over the lasy dog")
    assert isinstance(fixed, str)
    assert len(fixed) > 0, f"Model {model_id} produced empty output"
    # Should at least preserve most of the content
    assert "fox" in fixed.lower(), f"Model {model_id} lost content: {fixed}"
