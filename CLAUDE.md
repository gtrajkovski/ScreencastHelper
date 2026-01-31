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
python app_v5.py              # Web app v5.0 on http://127.0.0.1:5001 (recommended)
python app_v3.py              # Web app v3.0 on http://127.0.0.1:5555 (legacy)
python app_v4.py              # Web app v4.0 (legacy)
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

### Web App (v5.0 — current)

**v5.0** (`app_v5.py`): Unified app consolidating v2 (TUI+data), v3 (Web+TTS), and v4 (Web+Recording). Uses canonical `Project`/`Segment` dataclasses in `src/core/models.py` with `ProjectStore` for disk persistence. Templates in `templates_v5/`, static in `static_v5/`.

Key v5 modules:
- **`src/core/`**: `models.py` (Project, Segment, SegmentType, SegmentStatus), `project_store.py` (JSON persistence with audio/video/data subdirs), `parser.py` (WWHAA+IVQ script parser)
- **`src/services/`**: `recording_service.py` (FFmpeg integration)
- **`app_v5.py`**: Flask app with all API endpoints

Key v5 pages: `/dashboard`, `/workspace/<id>` (editor), `/player/<id>` (synchronized playback), `/recorder/<id>` (per-segment recording)

Key v5 API endpoints:
- `GET/POST /api/projects` — list/create projects
- `GET/PUT/DELETE /api/projects/<id>` — CRUD
- `POST /api/projects/<id>/parse` — parse raw script to segments
- `POST /api/generate/script` — AI script generation
- `POST /api/ai/improve-segment` — AI segment improvement
- `POST /api/ai/edit-selection` — AI text selection editing
- `POST /api/audio/generate/<segment_id>` — TTS audio generation
- `GET /api/projects/<id>/timeline` — project timeline
- `GET /api/projects/<id>/quality-check` — quality checks
- `POST /api/projects/<id>/export` — folder export
- `POST /api/projects/<id>/export-zip` — ZIP export
- `POST /api/recommend-environment` — AI environment recommendation
- `POST /api/projects/<id>/analyze-data` — AI dataset analysis
- `POST /api/projects/<id>/generate-datasets` — dataset generation
- `GET /api/system/ffmpeg-status` — FFmpeg availability

Migration: `python scripts/migrate_v4_to_v5.py [--dry-run]`

### Web App (v3.0 and v4.0 — legacy)

**v3.0** (`app_v3.py`, ~2000 lines): Flask app with templates in `templates_v3/` and static assets in `static_v3/`. Screen recording uses FFmpeg with Windows GDI capture (`gdigrab`).

**v4.0** (`app_v4.py`): Browser-native recording via MediaRecorder API. Templates in `templates_v4/`, static in `static_v4/`.

State is held in an in-memory `current_project` dict. Projects persist to `projects/` directory as JSON + artifact files.

### TTS Optimization

`TTSOptimizer` uses `Config.TTS_REPLACEMENTS` dictionary (~40 entries with word boundaries) for code-term pronunciation fixes: acronym expansion (`API` → "A-P-I"), file extensions (`.py` → "dot pie"), math notation (`O(n²)` → "O of n squared").

### TTS Audio Generation (v4.0)

`TTSAudioGenerator` in `src/generators/tts_audio_generator.py` synthesizes MP3 audio via Edge TTS (`edge-tts` package). `TimelineGenerator` produces timed event sequences that sync narration audio with demo code execution.

## Configuration

Requires `ANTHROPIC_API_KEY` in `.env` file (see `.env.example`). Default model is `claude-sonnet-4-20250514` (configurable via `MODEL` env var). Max tokens: 4096. Default duration: 7 minutes at 150 WPM.
