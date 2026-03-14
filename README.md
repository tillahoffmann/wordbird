# 🦜 Wordbird

Contextual voice dictation for macOS. Powered by [NVIDIA Parakeet](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2) running locally on Apple Silicon via [MLX](https://github.com/ml-explore/mlx).

Press a hotkey, speak, and your words are transcribed and pasted into whatever app is focused. A small LLM post-processes the transcription to fix errors, using project-specific context from a `BIRDWORD.md` file.

## Getting started

Requires macOS on Apple Silicon (M1+) and Python 3.10+.

```bash
# Run with uvx (no install needed)
uvx wordbird

# Or run in the background
uvx wordbird start
uvx wordbird stop
uvx wordbird status
```

## Context-aware correction

The key idea behind wordbird is **contextual transcription correction**. When dictating into **Terminal.app**, wordbird detects the focused tab's working directory and looks for a `BIRDWORD.md` file up the directory tree. This lets you teach wordbird your project's domain:

Context detection works with:
- **Terminal.app** — detects the focused tab's shell working directory
- **VS Code / VS Code Insiders** — via the [Wordbird extension](https://marketplace.visualstudio.com/items?itemName=tillahoffmann.wordbird), which works with local and remote (SSH) workspaces

Transcription and pasting work in any app.

```bash
uvx wordbird init
```

This creates a `BIRDWORD.md` with the default prompt template. Edit it to add your project's terms, names, and jargon:

```markdown
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

Key terms: MyClass, some_function, PostgreSQL
Names: Alice, Bob

Input: "{{ transcript }}"
Output:
```

The file is a [Jinja template](https://jinja.palletsprojects.com/). `{{ transcript }}` is replaced with the raw transcription. If omitted, the transcript is appended automatically.

The YAML front matter lets you override models per-project. When you dictate into a Terminal tab whose shell is in that directory (or a child), wordbird picks up the nearest `BIRDWORD.md` and uses it.

## Hotkeys

| Action | Default |
|---|---|
| Toggle recording | Right ⌘ + Space |
| Hold to record | Hold Right ⌘ for >1s, release to transcribe |

Hotkeys are configurable:

```
--hold-key KEY       Hold key (default: rcmd). Options: rcmd, lcmd, ralt, lalt, rshift, lshift, rctrl, lctrl
--toggle-key KEY     Toggle key (default: space). Options: space, return, tab, escape
```

## Options

```
--model MODEL        Transcription model (default: mlx-community/parakeet-tdt-0.6b-v2)
--fix-model MODEL    Post-processor model (default: mlx-community/Qwen2.5-1.5B-Instruct-4bit)
--no-fix             Disable LLM post-processing
```

## Dashboard

Wordbird runs a local web dashboard at [localhost:7870](http://localhost:7870). Click the bird in the menu bar → **Dashboard…** to open it.

- 📝 **History** — browse all your transcriptions with timestamps, app name, working directory, and duration. See both the original and corrected text.
- ⚙️ **Settings** — configure hotkeys, models, and post-processing. Changes take effect immediately without restarting.

You can also view history from the command line:

```bash
uvx wordbird history
```

## Menu bar

Wordbird shows a bird icon in the menu bar:

- ⚪ **White** — idle
- 🟡 **Yellow** — connecting mic
- 🔴 **Red** — listening
- ✨ **Sparkles** — transcribing

## Permissions

Wordbird needs three macOS permissions, granted to your terminal app:

- 🎤 **Microphone** — to record your voice
- 🔐 **Accessibility** — to paste text and intercept the hotkey
- ⌨️ **Input Monitoring** — to detect the global hotkey

Wordbird checks these on startup and tells you what's missing.

## License

MIT
