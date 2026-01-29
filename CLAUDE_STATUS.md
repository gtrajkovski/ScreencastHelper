# ScreenCast Studio - Development Status

**Last Updated:** 2026-01-28
**App Version:** v3.0
**Status:** Running on http://127.0.0.1:5555

---

## What This App Does

ScreenCast Studio is an AI-powered screencast production tool that helps create educational video content. It generates:
- Narration scripts (WWHAA structure: Hook, Objective, Content, Summary, CTA)
- TTS-optimized versions (acronyms expanded, code terms fixed)
- Demo code (Jupyter notebooks, Python scripts, or bash scripts)
- Sample datasets

## Current Architecture

```
C:\ScreencastHelper\
├── app_v3.py              # Flask web app (main entry point)
├── templates_v3/          # HTML templates
│   ├── base.html
│   ├── dashboard.html     # Project selection
│   ├── workspace.html     # Content generation
│   ├── recording.html     # Teleprompter + demo execution
│   └── export.html        # File export
├── static_v3/
│   ├── css/styles.css     # Dark theme styling
│   └── js/workspace.js    # Frontend logic
├── src/
│   ├── config.py          # Configuration classes
│   └── ai/                # AI client and prompts
└── output/                # Generated files go here
```

## Recently Completed Tasks

1. **FFmpeg Installation** - Installed via winget for screen recording
2. **EnvironmentConfig Fix** - Changed `env_type` to `name` parameter with backward-compatible property
3. **Flask-CORS Added** - Added to requirements.txt
4. **Package Generation** - Verified working (API returns 200)
5. **Workspace-Recording Sync** - Recording studio now loads generated content from `/api/project` API

## Screen Recording Feature

- Uses FFmpeg with Windows GDI capture
- FFmpeg installed at: `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe`
- App has fallback path detection in `find_ffmpeg()` function

---

## Pending/Future Tasks

### High Priority
- [ ] Test screen recording end-to-end (FFmpeg just installed)
- [ ] Add audio recording option (microphone input)
- [ ] Improve script section parsing (more robust regex)

### Medium Priority
- [ ] Add project save/load functionality (currently in-memory only)
- [ ] Implement actual dataset generation (currently placeholder data)
- [ ] Add keyboard shortcuts for recording studio (spacebar = next cell, etc.)

### Low Priority
- [ ] Add dark/light theme toggle
- [ ] Export to different video formats
- [ ] Add multi-project support on dashboard

---

## How to Run

```bash
cd C:\ScreencastHelper
python app_v3.py
# Opens at http://127.0.0.1:5555
```

## Key Files Modified This Session

| File | Changes |
|------|---------|
| `app_v3.py` | Added `/api/project` endpoint, `find_ffmpeg()` function |
| `templates_v3/recording.html` | Dynamic content loading from API, script parsing |
| `src/config.py` | Fixed EnvironmentConfig (name vs env_type) |
| `requirements.txt` | Added flask-cors, mss |

---

## Notes for Next Session

- The Flask app runs on port 5555 (5005 was occupied by another app)
- FFmpeg is installed but may need PATH refresh in new terminals
- Screen recording outputs to `output/` folder as .mov files
- The Textual TUI version (`app.py`) still exists but v3.0 is the Flask web version
