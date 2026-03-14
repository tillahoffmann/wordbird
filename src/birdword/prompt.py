"""Default BIRDWORD.md prompt template and front matter parsing."""

import frontmatter

DEFAULT_TRANSCRIPTION_MODEL = "mlx-community/parakeet-tdt-0.6b-v2"
DEFAULT_FIX_MODEL = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"

DEFAULT_TEMPLATE = """\
---
transcription_model: mlx-community/parakeet-tdt-0.6b-v2
fix_model: mlx-community/Qwen2.5-0.5B-Instruct-4bit
---

Fix transcription errors in the text below. Fix wrong words, punctuation,
and capitalization. Keep wording as close to the original as possible.
Output ONLY the corrected text. Do not add commentary or explanation.

{# Add project-specific context below. For example: #}
{# This is a Rust networking project using tokio and hyper. #}
{# Key terms: epoll, mio, AsyncRead, TcpListener #}
{# Names: Till #}

{{ transcript }}
"""


def parse_birdword_md(content: str) -> tuple[dict, str]:
    """Parse YAML front matter and body from a BIRDWORD.md file.

    Returns (metadata_dict, body_str).
    """
    post = frontmatter.loads(content)
    return dict(post.metadata), post.content
