"""Post-process transcription output using a small local LLM."""

import jinja2
from mlx_lm import load, generate

from wordbird.prompt import DEFAULT_FIX_MODEL, DEFAULT_TEMPLATE, parse_wordbird_md


def render_prompt(template_str: str, transcript: str) -> str:
    """Render a WORDBIRD.md template body with the transcript.

    If {{ transcript }} is not found in the template, append the transcript.
    """
    if "transcript" not in template_str:
        return template_str.rstrip() + "\n\n" + transcript

    tmpl = jinja2.Template(template_str)
    return tmpl.render(transcript=transcript)


class PostProcessor:
    """Cleans up transcription output using a small LLM."""

    def __init__(self, model_id: str | None = None):
        self._cli_model_id = model_id
        self._default_model_id = model_id or DEFAULT_FIX_MODEL
        self._model = None
        self._tokenizer = None
        self._loaded_model_id: str | None = None

    def load(self, model_id: str | None = None):
        """Load (or reload) the model."""
        model_id = model_id or self._default_model_id
        if self._loaded_model_id == model_id:
            return
        print(f"   ✨ Loading post-processor ({model_id})...")
        self._model, self._tokenizer = load(model_id)
        self._loaded_model_id = model_id
        print("   ✨ Post-processor ready.")

    def fix(self, text: str, context_content: str | None = None) -> tuple[str, dict]:
        """Fix transcription errors. Returns (fixed_text, front_matter)."""
        if not text.strip():
            return text, {}

        if context_content:
            front_matter, body = parse_wordbird_md(context_content)
        else:
            front_matter, body = parse_wordbird_md(DEFAULT_TEMPLATE)

        # CLI flag overrides front matter
        fix_model = self._cli_model_id or front_matter.get(
            "fix_model", DEFAULT_FIX_MODEL
        )

        self.load(fix_model)

        user_msg = render_prompt(body, text)

        messages = [
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

        # Strip surrounding quotes (few-shot format causes the model to quote output)
        if len(result) >= 2 and result[0] == '"' and result[-1] == '"':
            result = result[1:-1]

        # Guard: if result is much shorter, the model hallucinated
        if len(result) < len(text) * 0.5:
            return text, front_matter

        return result, front_matter
