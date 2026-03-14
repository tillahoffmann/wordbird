"""Default WORDBIRD.md prompt template and front matter parsing."""

import frontmatter

DEFAULT_TRANSCRIPTION_MODEL = "mlx-community/parakeet-tdt-0.6b-v2"
DEFAULT_FIX_MODEL = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"

DEFAULT_TEMPLATE = """\
---
transcription_model: mlx-community/parakeet-tdt-0.6b-v2
fix_model: mlx-community/Qwen2.5-1.5B-Instruct-4bit
---

Fix transcription errors. Output only the corrected text.

Example 1:
Input: "the java script function isnt working"
Output: "The JavaScript function isn't working."

Example 2:
Input: "check the get ignore file for the repo"
Output: "Check the .gitignore file for the repo."

Example 3:
Input: "we need to refactor the a p i endpoint"
Output: "We need to refactor the API endpoint."

{# Add project-specific context below. For example: #}
{# Key terms: MyClass, some_function, PostgreSQL #}
{# Names: Alice, Bob #}

Input: "{{ transcript }}"
Output:
"""


def parse_wordbird_md(content: str) -> tuple[dict, str]:
    """Parse YAML front matter and body from a WORDBIRD.md file.

    Returns (metadata_dict, body_str).
    """
    post = frontmatter.loads(content)
    return dict(post.metadata), post.content
