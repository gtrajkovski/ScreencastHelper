# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ScreenCast Studio is an AI-powered screencast production assistant that automates technical educational video content creation. It transforms bullet points into full narration scripts, optimizes them for text-to-speech, generates synchronized demo code, and creates supporting assets.

## Commands

### Run the Application
```bash
# Web app (v3.0 - current)
python app_v3.py  # Runs on http://127.0.0.1:5555

# CLI
python -m src.ui.cli <command>
```

### CLI Commands
```bash
python -m src.ui.cli init-project <name>
python -m src.ui.cli generate-script <bullets.txt> --output script.md --duration 7
python -m src.ui.cli optimize-tts <script.md> --output script_tts.txt
python -m src.ui.cli generate-demo <script.md> "<requirements>" --output demo.py
python -m src.ui.cli generate-assets <type> --output-dir assets  # types: terminal, csv, yaml, html
```

### Testing
```bash
pytest tests/ -v                  # Run all tests
pytest tests/ --cov=src           # With coverage
pytest tests/test_script_generator.py -v  # Single test file
```

### Linting/Formatting
```bash
black src/                        # Format code
ruff check src/                   # Lint
```

## Architecture

### Content Generation Pipeline
```
Bullet Points → ScriptGenerator → TTSOptimizer → DemoGenerator → AssetGenerator → Output Files
```

Each generator in `src/generators/` has a `generate()` method returning a dataclass result (e.g., `GeneratedScript`, `GeneratedDemo`) with metadata like word counts and estimated duration.

### AI Client Architecture

Two AI client implementations exist:
- `src/utils/ai_client.py`: One-shot generation with pre-built methods (`generate_script()`, `generate_demo_code()`) - used by CLI generators
- `src/ai/client.py`: Conversation-aware client with `chat()`, `chat_stream()`, and `generate()` - used by web app for interactive features

The web app (`app_v3.py`) uses `src/ai/client.py` and builds prompts inline, while CLI generators use `src/utils/ai_client.py` with hardcoded prompts.

### Prompt System (`src/ai/prompts.py`)

System prompt constants for each AI action:
- `SCRIPT_GENERATOR`, `TTS_OPTIMIZER`, `DEMO_GENERATOR` - Core generation
- `ALIGNMENT_CHECKER`, `QUALITY_CHECKER` - Validation
- `JUPYTER_GENERATOR`, `TERMINAL_GENERATOR`, `VSCODE_GENERATOR`, `IPYTHON_GENERATOR` - Environment-specific demos
- `DATA_ANALYZER`, `ENV_RECOMMENDER` - Planning/recommendation
- `CHAT_ASSISTANT` - Interactive chat mode

### WWHAA Script Structure
Scripts follow the Coursera-style structure with `## SECTION_NAME` headers:
- **HOOK (10%)**: Relatable problem, create curiosity
- **OBJECTIVE (10%)**: Learning goals ("By the end...")
- **CONTENT (60%)**: Core teaching with `[visual cues]` and `[PAUSE]` markers
- **SUMMARY (10%)**: Key takeaways
- **CALL TO ACTION (10%)**: Call to action

Section parsing uses regex: `r'## (HOOK|OBJECTIVE|CONTENT|SUMMARY|CALL TO ACTION)\n(.*?)(?=## |$)'`

### Multi-Environment Support (`src/environments/`)

Abstract `BaseEnvironment` class with required methods:
- `generate_demo(script, code_blocks)` → environment-specific demo code
- `get_file_extension()` → `.ipynb`, `.py`, `.sh`
- `get_run_command(filepath)` → how to execute the demo
- `get_setup_instructions()` → environment setup guide

`DemoStep` dataclass represents individual demo actions with section, narration, code, expected output, and pause flags.

`ENV_RECOMMENDATIONS` in config maps `DemoType` → `Environment` (e.g., DATA_ANALYSIS → JUPYTER, CLI_TOOL → TERMINAL).

### Key Enums (`src/config.py`)
- `Environment`: JUPYTER, VSCODE, TERMINAL, IPYTHON, PYCHARM
- `AudienceLevel`: BEGINNER, INTERMEDIATE, ADVANCED
- `DemoType`: DATA_ANALYSIS, CLI_TOOL, WEB_APP, ML_TRAINING, DATA_PIPELINE, API_USAGE, DEBUGGING, REFACTORING

### TTS Optimization
The `TTSOptimizer` transforms scripts for speech engines:
- Removes visual cues (keeps only `[PAUSE]`)
- Expands acronyms: `API` → "A-P-I"
- Fixes code terms: `.py` → "dot pie", `O(n²)` → "O of n squared"
- Uses `Config.TTS_REPLACEMENTS` dictionary for predefined substitutions

### Web App (v3.0)

Flask app in `app_v3.py` with templates in `templates_v3/` and static assets in `static_v3/`.

**Pages:**
- `/` - Dashboard: project list, create/load projects
- `/workspace` - Main workspace: project setup, script generation, AI chat, inline editing, markdown preview
- `/recording` - 3-panel recording: teleprompter + demo notebook + section nav
- `/recording-studio` - Enhanced teleprompter with customizable text, auto-scroll
- `/present` - Presentation mode: slides, notebook cells, IVQ views with keyboard navigation
- `/segment-recorder` - Per-segment recording: record each WWHAA section as separate MP4
- `/export` - Export page

**Core API endpoints:**
- `/api/generate` - Generate full screencast package (script + TTS + demo)
- `/api/chat` - AI chat with project context
- `/api/check-alignment` - Verify component sync
- `/api/check-quality` - Run quality checks
- `/api/suggest` - AI suggestions for script improvement
- `/api/recording-data` - Get data for recording studio

**Project management:**
- `/api/projects` - List/create projects (GET/POST)
- `/api/projects/<id>` - Load project (GET)
- `/api/projects/save` - Save current project (POST)
- `/api/projects/current` - Get current in-memory project (GET)

**Presentation system:**
- `/api/parse-script` - Parse script into presentation segments (POST)
- `/api/presentation/segments` - Get parsed segments (GET)

**Segment recording:**
- `/api/parse-segments` - Parse script into recording segments with filenames (POST)
- `/api/segments` - Get segments with statuses (GET)
- `/api/segments/<id>/record` - Start recording a segment (POST)
- `/api/segments/<id>/stop` - Stop recording a segment (POST)
- `/api/segments/<id>/preview` - Serve recorded MP4 (GET)
- `/api/segments/export` - Export all segments as ZIP (POST)

**Screen recording:**
- `/api/start-screen-record`, `/api/stop-screen-record` - FFmpeg-based screen capture

In-memory `current_project` dict stores project state between requests. Projects persist to disk in `projects/` directory as JSON + artifact files.

### Utility Functions (`app_v3.py`)
- `sanitize_filename(name)` - Safe filename generation for output files
- `find_ffmpeg()` - Locate FFmpeg executable (PATH, winget, common dirs)
- `parse_script_to_segments(script, duration)` - Parse WWHAA script into typed segments (slide/notebook/ivq)

## Configuration

Requires `ANTHROPIC_API_KEY` in `.env` file. Default model is `claude-sonnet-4-20250514` (configurable via `MODEL` env var).
