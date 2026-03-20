"""Default WORDBIRD.md prompt template and front matter parsing."""

import frontmatter

DEFAULT_TRANSCRIPTION_MODEL = "mlx-community/parakeet-tdt-0.6b-v2"
DEFAULT_FIX_MODEL = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"

DEFAULT_PROMPT = """\
You are a speech-to-text post-processor. Your job is to fix minor transcription errors while keeping the speaker's exact words and meaning.

Output the complete corrected text only. Match the input length closely.

ALWAYS:
- Keep the first word's capitalization exactly as given.
- Keep every word the speaker said, including filler and emphasis.
- Keep the original sentence structure and word order.
- Add commas after introductory words (Actually, Okay, So, Now).
- Add missing periods at the end of sentences.
- Hyphenate compound modifiers (hard coded → hard-coded).
- Fix obvious technical terms (a p i → API).
- Remove clear stutters (s two → two) while keeping surrounding words intact.
- Output plain text with no formatting.
- When in doubt, keep the original text unchanged.

Example 1:
Input: "Actually that won't work because of the bug"
Output: "Actually, that won't work because of the bug."

Example 2:
Input: "we need to refactor the a p i endpoint"
Output: "We need to refactor the API endpoint."

Example 3:
Input: "Yes, I see it now."
Output: "Yes, I see it now."

Example 4:
Input: "There were s two more points to discuss."
Output: "There were two more points to discuss."

Example 5:
Input: "I think the hard coded defaults changed."
Output: "I think the hard-coded defaults changed."

Input: "{{ transcript }}"
Output:
"""

INIT_TEMPLATE = """\
---
transcription_model: mlx-community/parakeet-tdt-0.6b-v2
fix_model: mlx-community/Qwen2.5-1.5B-Instruct-4bit
---

Fix speech-to-text errors. Output ONLY the corrected text. Do NOT add formatting.

Rules:
1. KEEP the original capitalization of the first word. "Yes" stays "Yes", not "yes".
2. NEVER lowercase words that are already capitalized correctly.
3. Fix punctuation: add commas after introductory words, add missing periods.
4. Fix misheard tech terms ONLY when obvious from context.
5. NEVER rephrase, reorder, or restructure sentences.
6. NEVER remove words the speaker said.
7. NEVER change meaning.
8. If the text is already correct, output it unchanged.

Example 1:
Input: "check the get ignore file for the repo"
Output: "Check the .gitignore file for the repo."

Example 2:
Input: "we need to refactor the a p i endpoint"
Output: "We need to refactor the API endpoint."

Example 3:
Input: "Yes, I see it now."
Output: "Yes, I see it now."

Example 4:
Input: "Actually that won't work because of the bug."
Output: "Actually, that won't work because of the bug."

Example 5:
Input: "I think the hard coded defaults changed."
Output: "I think the hard-coded defaults changed."

{# Add project-specific context below. For example: #}
{# Key terms: MyApp, some_function, PostgreSQL #}
{# Names: Alice, Bob #}
{# Misheard words: "bird word" should be "Birdword" #}

Input: "{{ transcript }}"
Output:
"""

CLAUDE_INIT_PROMPT = f"""\
Generate a WORDBIRD.md file in the current working directory, pre-populated with \
project-specific terms discovered by analyzing the codebase.

Step 1: Check if WORDBIRD.md already exists. If it does, read it and note its contents. \
If it does not exist, proceed directly.

Step 2: Explore the codebase. Read ~10-15 files to understand the project. Prioritize:
1. Package manifests: pyproject.toml, package.json, Cargo.toml, go.mod, etc.
2. README and docs
3. Source file sampling: entry points, main modules, config files
4. CI/CD and tooling: Makefile, Dockerfile, workflow files

Step 3: Identify terms. Categorize into:

Key terms (target: 15-40 terms) — only terms a speech-to-text model is likely to \
get wrong or that are domain-specific: library/framework names, tool names, \
project-specific names, acronyms, technical terms with unusual spelling.

Misheard words (target: 5-15 mappings) — think phonetically about what a speech \
model would produce. Common patterns:
- Compound words split: "word bird" -> "wordbird", "git hub" -> "GitHub"
- Spelled-out acronyms: "a p i" -> "API"
- Sound-alikes: "pie test" -> "pytest", "numb pie" -> "NumPy"
- Camel/pascal case split: "app kit" -> "AppKit"

Step 4: Write WORDBIRD.md. Start from the default prompt template shown below, \
then add your discovered terms. Replace the Jinja2 comment placeholders with \
a "Key terms:" line and "Misheard words:" lines.

Default prompt template:
```
{INIT_TEMPLATE}\
```

Key terms go on a single comma-separated line. Each misheard mapping goes on its \
own line with format: "misheard phrase" should be "correct term".

Important: The {{{{ transcript }}}} placeholder MUST appear exactly as shown (Jinja2 variable). \
Keep the 5 standard examples. Keep the total prompt concise.

Step 5: Report the number of key terms and misheard mappings generated.
"""

CLAUDE_INIT_TOOLS = [
    "Read",
    "Glob",
    "Grep",
    "Edit(WORDBIRD.md)",
    "Write(WORDBIRD.md)",
]


def parse_wordbird_md(content: str) -> tuple[dict, str]:
    """Parse YAML front matter and body from a WORDBIRD.md file.

    Returns (metadata_dict, body_str).
    """
    post = frontmatter.loads(content)
    return dict(post.metadata), post.content
