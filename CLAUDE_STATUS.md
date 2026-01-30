# ScreenCast Studio - Development Status

**Last Updated:** 2026-01-29
**App Version:** v3.0
**Status:** Running on http://127.0.0.1:5555

---

## What This App Does

ScreenCast Studio is an AI-powered screencast production tool that helps create educational video content. The full pipeline:

1. **Input** bullet points, topic, audience level, demo requirements
2. **Generate** narration script (WWHAA structure: Hook, Objective, Content, Summary, CTA)
3. **Optimize** for TTS (acronyms expanded, code terms fixed, visual cues removed)
4. **Generate** demo code (Jupyter notebooks, Python scripts, bash scripts)
5. **Generate** supporting assets (datasets, terminal output, YAML, HTML reports)
6. **Present** with slides, notebook cells, and IVQ views
7. **Record** each section as individual MP4 segments
8. **Export** as ZIP package

## Current Architecture

```
C:\ScreencastHelper\
├── app_v3.py                      # Flask web app (main entry, ~1700 lines)
├── templates_v3/
│   ├── base.html
│   ├── dashboard.html             # Project selection/creation
│   ├── workspace.html             # Content generation workspace
│   ├── recording.html             # 3-panel recording (teleprompter + demo + sections)
│   ├── recording_studio.html      # Enhanced teleprompter with auto-scroll
│   ├── present.html               # Presentation mode (slides/notebook/IVQ)
│   ├── segment_recorder.html      # Per-segment recording with status badges
│   └── export.html                # File export
├── static_v3/
│   ├── css/styles.css             # Dark theme styling
│   └── js/workspace.js           # Frontend workspace logic (~2000 lines)
├── src/
│   ├── config.py                  # Configuration, enums, TTS replacements
│   ├── ai/
│   │   ├── client.py              # Claude API wrapper (conversation-aware)
│   │   └── prompts.py             # System prompts for each generator
│   ├── generators/
│   │   ├── script_generator.py    # Narration script generation
│   │   ├── tts_optimizer.py       # TTS optimization with word boundary fixes
│   │   ├── demo_generator.py      # Demo code generation
│   │   └── asset_generator.py     # Supporting asset generation
│   ├── environments/              # Multi-environment support (Jupyter, Terminal, VS Code)
│   ├── data/                      # Data generation utilities
│   ├── validators/                # Quality/alignment validation
│   ├── web/                       # Web module
│   └── utils/                     # AI client utilities
├── projects/                      # Saved projects (JSON + artifacts)
├── output/                        # Generated files and recordings
├── tests/                         # 35 passing tests
└── .env                           # ANTHROPIC_API_KEY
```

## Features Implemented

### Core Generation Pipeline
- [x] Narration script generation (WWHAA structure)
- [x] TTS optimization (acronym expansion, code term fixes, word boundary matching)
- [x] Demo code generation (Jupyter, Python, bash)
- [x] Asset generation (CSV, YAML, terminal output, HTML reports)
- [x] AI chat with project context
- [x] Quality checking and alignment verification

### Workspace (workspace.html + workspace.js)
- [x] Project setup panel (topic, bullets, audience, environment, duration)
- [x] Script generation with inline editing
- [x] Markdown preview/edit toggle with section navigation
- [x] AI suggestions for script improvement
- [x] TTS optimization with preview
- [x] Demo code generation
- [x] Save/load projects to disk
- [x] Quick action buttons

### Recording & Presentation
- [x] 3-panel recording view (teleprompter + demo notebook + sections)
- [x] Enhanced teleprompter with customizable text size, auto-scroll, colors
- [x] Presentation mode with slides, notebook cells, IVQ views
- [x] Script parser: splits WWHAA sections into typed segments
- [x] Per-segment recording (each section as separate MP4)
- [x] Segment status badges (pending/recording/recorded)
- [x] 3-2-1 countdown before recording
- [x] Auto-scroll teleprompter during recording
- [x] Preview recorded segments in-browser
- [x] Re-record individual segments
- [x] ZIP export of all recorded segments with metadata

### Infrastructure
- [x] FFmpeg integration for screen recording (gdigrab, H.264, MP4)
- [x] Project persistence (JSON + artifact files)
- [x] XSS prevention in dynamic HTML rendering
- [x] Path validation for file serving
- [x] Safe process cleanup for FFmpeg
- [x] beforeunload protection during active recording
- [x] 35 passing tests (generators, TTS optimizer, asset generator)

## Screen Recording

- Uses FFmpeg with Windows GDI capture (`gdigrab`)
- FFmpeg installed at: `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe`
- Fallback path detection in `find_ffmpeg()`
- Two recording modes:
  - **Full recording**: `/api/start-screen-record` + `/api/stop-screen-record`
  - **Segment recording**: `/api/segments/<id>/record` + `/api/segments/<id>/stop`
- Output: MP4 (H.264, ultrafast preset, CRF 23, yuv420p)

## Recent Commits

| Commit | Description |
|--------|-------------|
| `11f2cf8` | Add segment-based recording with per-section MP4 capture and export |
| `46b70cc` | Add visual presentation mode with slides, notebook cells, and IVQ views |
| `805c1d7` | Fix recording studio to open full recording view with demo code panel |
| `eec9380` | Add inline editing, AI suggestions, markdown preview, and bug fixes |
| `b2726b5` | Fix screen recording (MP4/1920x1080) and add native save/open dialogs |

---

## Pending/Future Tasks

### High Priority
- [ ] Add audio recording option (microphone input via FFmpeg dshow)
- [ ] Concatenate recorded segments into final video
- [ ] Add tests for segment recording endpoints

### Medium Priority
- [ ] Implement actual dataset generation (currently uses placeholder data in some cases)
- [ ] Add progress indicator during AI generation
- [ ] Improve error recovery when AI API calls fail

### Low Priority
- [ ] Add dark/light theme toggle
- [ ] Export to different video formats
- [ ] Multi-user support (currently single-user in-memory state)

---

## How to Run

```bash
cd C:\ScreencastHelper
python app_v3.py
# Opens at http://127.0.0.1:5555
```

## Key Configuration

- `ANTHROPIC_API_KEY` in `.env` file
- Default model: `claude-sonnet-4-20250514` (configurable via `MODEL` env var)
- Output directory: `output/`
- Projects directory: `projects/`
- Port: 5555
