# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ScreenCast Studio is an AI-powered screencast production assistant that transforms bullet points into narration scripts, optimizes them for TTS, generates synchronized demo code, and creates supporting assets for technical educational videos.

## Commands

### Setup
```bash
pip install -r requirements.txt
cp .env.example .env             # Then add ANTHROPIC_API_KEY
```

### Run the Application
```bash
python app_v3.py              # Web app v3.0 on http://127.0.0.1:5555
python app_v4.py              # Web app v4.0 (browser-native recording, no FFmpeg)
python -m src.ui.cli <command> # CLI mode
```

### Testing
```bash
pytest tests/ -v                           # Run all tests
pytest tests/test_script_generator.py -v   # Single test file
pytest tests/ --cov=src                    # With coverage
```

CI runs pytest across Python 3.9, 3.10, 3.11 (see `.github/workflows/test.yml`).

### Linting/Formatting
```bash
black src/
ruff check src/
```

## Architecture

### Content Generation Pipeline
```
Bullet Points → ScriptGenerator → TTSOptimizer → DemoGenerator → AssetGenerator → Output Files
```

Each generator in `src/generators/` has a `generate()` method returning a dataclass result (e.g., `GeneratedScript`, `GeneratedDemo`) with metadata like word counts and estimated duration.

### Dual AI Client Pattern

Two separate AI client implementations exist for different contexts:
- **`src/utils/ai_client.py`** (one-shot): Pre-built methods like `generate_script()`, `generate_demo_code()` with hardcoded prompts. Used by CLI generators.
- **`src/ai/client.py`** (conversational): `chat()`, `chat_stream()`, `generate()` with conversation history. Used by web app for interactive features.

The web app (`app_v3.py`) builds prompts inline using constants from `src/ai/prompts.py`.

### WWHAA Script Structure

Scripts use Coursera-style `## SECTION_NAME` headers: HOOK (10%), OBJECTIVE (10%), CONTENT (60%), SUMMARY (10%), CALL TO ACTION (10%). Content sections use `[visual cues]` and `[PAUSE]` markers.

Section parsing regex: `r'## (HOOK|OBJECTIVE|CONTENT|SUMMARY|CALL TO ACTION)\n(.*?)(?=## |$)'`

### Multi-Environment Support

`src/environments/base.py` defines `BaseEnvironment` (abstract) and `DemoStep` dataclass. Implementations in `jupyter.py` and `terminal.py`. `ENV_RECOMMENDATIONS` in `src/config.py` maps `DemoType` → `Environment`.

### Web App (v3.0 and v4.0)

**v3.0** (`app_v3.py`, ~2000 lines): Flask app with templates in `templates_v3/` and static assets in `static_v3/`. Main frontend logic is in `static_v3/js/workspace.js` (~2000 lines). Screen recording uses FFmpeg with Windows GDI capture (`gdigrab`) — Windows only. `find_ffmpeg()` searches PATH, winget, and common install directories.

**v4.0** (`app_v4.py`): Browser-native recording via MediaRecorder API and Web Audio — no desktop dependencies (FFmpeg, tkinter). Uses `v4_script_generator.py`, `v4_code_generator.py`, `tts_audio_generator.py` (Edge TTS), and `timeline_generator.py`. Templates in `templates_v4/`, static in `static_v4/`.

Key v3 pages: `/` (dashboard), `/workspace` (editor), `/recording` (3-panel recording), `/present` (presentation mode), `/segment-recorder` (per-segment MP4 recording).

State is held in an in-memory `current_project` dict. Projects persist to `projects/` directory as JSON + artifact files.

### TTS Optimization

`TTSOptimizer` uses `Config.TTS_REPLACEMENTS` dictionary (~40 entries with word boundaries) for code-term pronunciation fixes: acronym expansion (`API` → "A-P-I"), file extensions (`.py` → "dot pie"), math notation (`O(n²)` → "O of n squared").

### TTS Audio Generation (v4.0)

`TTSAudioGenerator` in `src/generators/tts_audio_generator.py` synthesizes MP3 audio via Edge TTS (`edge-tts` package). `TimelineGenerator` produces timed event sequences that sync narration audio with demo code execution.

## Configuration

Requires `ANTHROPIC_API_KEY` in `.env` file (see `.env.example`). Default model is `claude-sonnet-4-20250514` (configurable via `MODEL` env var). Max tokens: 4096. Default duration: 7 minutes at 150 WPM.
