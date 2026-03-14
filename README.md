# 🐦 Birdword

Contextual voice dictation for macOS. Powered by [NVIDIA Parakeet](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2) running locally on Apple Silicon via [MLX](https://github.com/ml-explore/mlx).

Press a hotkey, speak, and your words are transcribed and pasted into whatever app is focused. A small LLM (Qwen2.5-0.5B) post-processes the transcription to fix errors, optionally using project-specific context from a `BIRDWORD.md` file.

## Install

```
pip install birdword
```

Or run without installing:

```
uvx birdword
```

Requires macOS on Apple Silicon (M1+) and Python 3.12+.

## Usage

```bash
# Run in the foreground
birdword

# Run in the background
birdword start
birdword stop
birdword status
```

### Hotkeys

| Action | Default |
|---|---|
| Toggle recording | Right ⌘ + Space |
| Hold to record | Hold Right ⌘ for >1s, release to transcribe |

### Options

```
--model MODEL        Transcription model (default: mlx-community/parakeet-tdt-0.6b-v2)
--fix-model MODEL    Post-processor model (default: mlx-community/Qwen2.5-0.5B-Instruct-4bit)
--no-fix             Disable LLM post-processing
--hold-key KEY       Hold key (default: rcmd). Options: rcmd, lcmd, ralt, lalt, rshift, lshift, rctrl, lctrl
--toggle-key KEY     Toggle key (default: space). Options: space, return, tab, escape
```

## Permissions

Birdword needs three macOS permissions, granted to your terminal app:

- **Microphone** — to record your voice
- **Accessibility** — to paste text and intercept the hotkey
- **Input Monitoring** — to detect the global hotkey

Birdword checks these on startup and tells you what's missing.

## Context-aware correction

Drop a `BIRDWORD.md` file in your project directory with domain-specific terms, names, and jargon:

```markdown
This is a Rust networking project using tokio and hyper.

Key terms: epoll, mio, AsyncRead, TcpListener
Names: Till
```

When you dictate into a Terminal tab whose shell is in that directory (or a child), birdword feeds this context to the post-processor so it knows not to "correct" your domain terms.

## Menu bar

Birdword shows a bird icon in the menu bar:

- **White** — idle
- **Yellow** — connecting mic
- **Red** — listening
- **✨ Sparkles** — transcribing

## License

MIT
