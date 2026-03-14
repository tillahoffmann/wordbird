"""Post-process transcription output using a small local LLM."""

from mlx_lm import load, generate

from birdword.context import get_context

MODEL_ID = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"

SYSTEM_PROMPT = (
    "Fix transcription errors in the text below. Fix wrong words, punctuation, "
    "and capitalization. Keep wording as close to the original as possible. "
    "Output ONLY the corrected text. Do not add commentary or explanation."
)


class PostProcessor:
    """Cleans up transcription output using a small LLM."""

    def __init__(self, model_id: str = MODEL_ID):
        self.model_id = model_id
        self._model = None
        self._tokenizer = None

    def load(self):
        """Pre-load the model."""
        print(f"   ✨ Loading post-processor ({self.model_id})...")
        self._model, self._tokenizer = load(self.model_id)
        print("   ✨ Post-processor ready.")

    def fix(self, text: str) -> str:
        """Fix transcription errors in the given text."""
        if not text.strip():
            return text

        if self._model is None:
            self.load()

        app_name, project_context = get_context()

        # Build the user message with context and text clearly separated
        user_msg = ""
        if project_context:
            user_msg += f"Context: {project_context.strip()}\n\n"
        user_msg += f"<text>\n{text}\n</text>"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        result = generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=len(text.split()) * 3,
            verbose=False,
        )

        result = result.strip()

        # Guard: if the result is much shorter than input or doesn't share
        # enough words, the model hallucinated — return original
        if len(result) < len(text) * 0.5:
            return text

        return result
