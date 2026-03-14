"""Post-process transcription output using a small local LLM."""

from mlx_lm import load, generate

from birdword.context import get_context

MODEL_ID = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"

SYSTEM_PROMPT = (
    "You are a transcription post-processor. You receive raw speech-to-text output "
    "and fix obvious errors: wrong words, missing or incorrect punctuation, "
    "capitalization, and garbled phrases. Keep the meaning and wording as close "
    "to the original as possible. Only fix clear mistakes. "
    "Output ONLY the corrected text, nothing else."
)


class PostProcessor:
    """Cleans up transcription output using a small LLM."""

    def __init__(self, model_id: str = MODEL_ID):
        self.model_id = model_id
        self._model = None
        self._tokenizer = None

    def load(self):
        """Pre-load the model."""
        print(f"Loading post-processor {self.model_id}...")
        self._model, self._tokenizer = load(self.model_id)
        print("Post-processor loaded.")

    def fix(self, text: str) -> str:
        """Fix transcription errors in the given text."""
        if not text.strip():
            return text

        if self._model is None:
            self.load()

        # Build context-aware system prompt
        app_name, project_context = get_context()

        system = SYSTEM_PROMPT
        if app_name:
            system += f"\n\nThe user is dictating into: {app_name}."
        if project_context:
            system += (
                f"\n\nProject context (use this to correct domain-specific terms):\n"
                f"{project_context}"
            )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
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

        return result.strip()
