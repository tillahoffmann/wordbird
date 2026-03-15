"""Post-process transcription output using a small local LLM."""

from html.parser import HTMLParser

import jinja2
from markdown_it import MarkdownIt
from mlx_lm import generate, load

from wordbird.prompt import DEFAULT_FIX_MODEL, DEFAULT_PROMPT, parse_wordbird_md

_md = MarkdownIt()


class _TextExtractor(HTMLParser):
    """Extract plain text from HTML, discarding all tags."""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str):
        self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


def strip_markdown(text: str) -> str:
    """Convert markdown to plain text, removing all formatting."""
    html = _md.render(text)
    extractor = _TextExtractor()
    extractor.feed(html)
    return extractor.get_text().strip()


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
        self._model = None
        self._tokenizer = None
        import gc

        gc.collect()
        import mlx.core as mx

        mx.clear_cache()
        result = load(model_id)
        self._model, self._tokenizer = result[0], result[1]
        self._loaded_model_id = model_id
        print("   ✨ Post-processor ready.")

    def fix(
        self,
        text: str,
        context_content: str | None = None,
        model_id: str | None = None,
    ) -> tuple[str, dict]:
        """Fix transcription errors. Returns (fixed_text, front_matter)."""
        if not text.strip():
            return text, {}

        if context_content:
            front_matter, body = parse_wordbird_md(context_content)
        else:
            front_matter, body = parse_wordbird_md(DEFAULT_PROMPT)

        # Priority: front matter > explicit model_id > CLI flag > default
        fix_model = front_matter.get(
            "fix_model", model_id or self._cli_model_id or DEFAULT_FIX_MODEL
        )

        self.load(fix_model)

        user_msg = render_prompt(body, text)

        messages = [
            {"role": "user", "content": user_msg},
        ]

        assert self._model is not None and self._tokenizer is not None

        prompt = self._tokenizer.apply_chat_template(  # type: ignore[reportCallIssue]
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

        # Strip any markdown formatting the model injected
        result = strip_markdown(result)

        # Guard: if result is much shorter, the model hallucinated
        if len(result) < len(text) * 0.5:
            return text, front_matter

        return result, front_matter
