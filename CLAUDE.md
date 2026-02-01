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
python app_v5.py                # Web app v5.0 on http://127.0.0.1:5001 (recommended)
python -m src.ui.cli <command>  # CLI mode
```

Legacy apps: `app_v3.py` (port 5555), `app_v4.py` — templates/static in `templates_v3/`..`v4/`, `static_v3/`..`v4/`.

### Testing
```bash
pytest tests/ -v                           # Run all tests
pytest tests/test_script_generator.py -v   # Single test file
pytest tests/ --cov=src                    # With coverage
```

CI runs pytest across Python 3.9, 3.10, 3.11 on Ubuntu (`.github/workflows/test.yml`) with codecov upload. On this Windows dev machine, use `py -3` instead of `python` if `python` is not found.

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
- **`src/ai/actions.py`**: AI-driven actions (segment improvement, text selection editing) used by v5 API endpoints.

The web app (`app_v3.py`) builds prompts inline using constants from `src/ai/prompts.py`.

### WWHAA Script Structure

Scripts use Coursera-style `## SECTION_NAME` headers: HOOK (10%), OBJECTIVE (10%), CONTENT (60%), SUMMARY (10%), CALL TO ACTION (10%). Content sections use `[visual cues]` and `[PAUSE]` markers.

IVQ (In-Video Quiz) sections are also supported. `src/core/parser.py` handles both WWHAA and IVQ parsing, extracting questions, options, correct answers, and feedback.

Section parsing regex: `r'## (HOOK|OBJECTIVE|CONTENT|SUMMARY|CALL TO ACTION)\n(.*?)(?=## |$)'`

### Multi-Environment Support

`src/environments/base.py` defines `BaseEnvironment` (abstract) and `DemoStep` dataclass. Implementations in `jupyter.py` and `terminal.py`. `ENV_RECOMMENDATIONS` in `src/config.py` maps `DemoType` → `Environment`.

### Slide Generator

`SlideGenerator` uses `matplotlib.use('Agg')` at module level for headless rendering. Coursera palette: primary `#2A73CC`, dark `#1F5FAA`, light bg `#F0F4F8`. Output is 19.20×10.80 inches at 100 DPI (1920×1080) but `bbox_inches='tight'` trims whitespace so actual dimensions are smaller.

### Web App (v5.0 — current)

**v5.0** (`app_v5.py`): Unified app consolidating v2 (TUI+data), v3 (Web+TTS), and v4 (Web+Recording). Uses canonical `Project`/`Segment` dataclasses in `src/core/models.py` with `ProjectStore` for disk persistence. Templates in `templates_v5/`, static in `static_v5/`.

Key v5 modules:
- **`src/core/`**: `models.py` (Project, Segment, SegmentType, SegmentStatus), `project_store.py` (JSON persistence with audio/video/data subdirs), `parser.py` (WWHAA+IVQ script parser)
- **`src/parsers/`**: `script_importer.py` (ImportedScript dataclass, .docx/.md import, WWHAA section parsing, code block extraction, IVQ parsing)
- **`src/generators/`**: Production asset generators — `slide_generator.py` (PNG/SVG via matplotlib), `notebook_generator.py` (Jupyter via nbformat), `production_notes_generator.py` (.docx/.md recording instructions), `python_demo_generator.py` (terminal demo scripts with typing effects), `tts_optimizer.py` (also has `generate_narration_file()` and `extract_narration_segments()`), `package_exporter.py` (full ZIP package with all assets)
- **`src/services/`**: `recording_service.py` (FFmpeg integration)
- **`app_v5.py`**: Flask app with all API endpoints. Module-level singletons: `project_store = ProjectStore(Path('projects'))` and `ai_client = AIClient()`

Key v5 pages: `/dashboard`, `/workspace/<id>` (editor), `/player/<id>` (synchronized playback), `/recorder/<id>` (per-segment recording)

Key v5 API endpoint groups (all defined in `app_v5.py`):
- `/api/projects` — CRUD, segment management
- `/api/generate/*`, `/api/ai/*` — AI script generation, segment improvement, text editing
- `/api/audio/*` — TTS audio synthesis
- `/api/projects/<id>/export*` — folder and ZIP export
- `/api/projects/<id>/import-script` — .docx/.md script import
- `/api/projects/<id>/generate-slides`, `generate-notebook`, `generate-tts-narration`, `generate-production-notes`, `generate-demo-script` — production asset generation
- `/api/projects/<id>/export-full-package` — complete ZIP package with all assets
- `/api/projects/<id>/timeline`, `quality-check`, `analyze-data`, `generate-datasets` — analysis
- `/api/system/ffmpeg-status` — system checks

Migration: `python scripts/migrate_v4_to_v5.py [--dry-run]`

### TTS Optimization

`TTSOptimizer` uses `Config.TTS_REPLACEMENTS` dictionary (~40 entries with word boundaries) for code-term pronunciation fixes: acronym expansion (`API` → "A-P-I"), file extensions (`.py` → "dot pie"), math notation (`O(n²)` → "O of n squared").

### TTS Audio Generation (v4.0)

`TTSAudioGenerator` in `src/generators/tts_audio_generator.py` synthesizes MP3 audio via Edge TTS (`edge-tts` package). `TimelineGenerator` produces timed event sequences that sync narration audio with demo code execution.

### Data Model (v5)

`Project` and `Segment` are Python dataclasses in `src/core/models.py` with `.to_dict()` / `.from_dict()` for JSON serialization. `ProjectStore` persists projects to `projects/{id}/project.json` with `audio/`, `video/`, `data/` subdirectories. Path traversal is blocked via `_sanitize_id()`.

Segment types: `SLIDE`, `SCREENCAST`, `IVQ`. Statuses: `DRAFT`, `RECORDED`, `APPROVED`.

### Path Safety

API endpoints use `safe_filename()` (raises `ValueError` on invalid input) and `sanitize_filename()` for user-provided names. `ProjectStore._sanitize_id()` strips path traversal characters (`/`, `\`, `..`).

## Testing Conventions

- Tests use pytest's `tmp_path` fixture for isolated file operations
- Serialization round-trip tests: `.to_dict()` → `.from_dict()` → assert equality
- Flask endpoints tested via `app.test_client()` with temporary `ProjectStore`
- Security tests verify path traversal protection in `ProjectStore`

## Platform

Primary target is Windows (screen recording uses FFmpeg with `gdigrab` capture). TTS uses `edge-tts` which is cross-platform.

## Configuration

Requires `ANTHROPIC_API_KEY` in `.env` file (see `.env.example`). Other env vars:
- `MODEL` — AI model (default: `claude-sonnet-4-20250514`)
- `TTS_VOICE` — Edge TTS voice (default: `en-US-AriaNeural`)
- `TTS_RATE` — Speech rate (default: `+0%`)
- `TTS_PITCH` — Speech pitch (default: `+0Hz`)

Max tokens: 4096. Default duration: 7 minutes at 150 WPM.
