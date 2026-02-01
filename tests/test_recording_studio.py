"""Tests for the Recording Studio feature (models + session generator + API)."""

import json
import pytest
from pathlib import Path

from src.recording.models import (
    RecordingMode, CueType, RecordingCue, TeleprompterSettings,
    RehearsalResult, TimelineTrack, RecordingSession,
)
from src.recording.session_generator import RecordingSessionGenerator


# ============================================================================
# Model serialization round-trip tests
# ============================================================================

class TestRecordingCue:
    def test_defaults(self):
        cue = RecordingCue()
        assert cue.cue_type == CueType.NARRATION
        assert cue.section == ""
        assert cue.text == ""
        assert cue.duration_estimate == 0.0
        assert cue.order == 0

    def test_round_trip(self):
        cue = RecordingCue(
            cue_type=CueType.CODE_ACTION,
            section="CONTENT",
            text="print('hello')",
            duration_estimate=3.0,
            order=5,
            notes="Execute cell",
        )
        d = cue.to_dict()
        restored = RecordingCue.from_dict(d)
        assert restored.cue_type == CueType.CODE_ACTION
        assert restored.section == "CONTENT"
        assert restored.text == "print('hello')"
        assert restored.duration_estimate == 3.0
        assert restored.order == 5
        assert restored.notes == "Execute cell"

    def test_from_dict_invalid_cue_type(self):
        cue = RecordingCue.from_dict({"cue_type": "invalid_type"})
        assert cue.cue_type == CueType.NARRATION


class TestTeleprompterSettings:
    def test_defaults(self):
        s = TeleprompterSettings()
        assert s.font_size == 32
        assert s.scroll_speed == 1.0
        assert s.mirror is False
        assert s.highlight_current is True
        assert s.countdown_seconds == 3
        assert s.auto_scroll is True

    def test_round_trip(self):
        s = TeleprompterSettings(font_size=48, mirror=True, scroll_speed=2.0)
        d = s.to_dict()
        restored = TeleprompterSettings.from_dict(d)
        assert restored.font_size == 48
        assert restored.mirror is True
        assert restored.scroll_speed == 2.0

    def test_from_dict_ignores_unknown(self):
        s = TeleprompterSettings.from_dict({"font_size": 24, "unknown_field": True})
        assert s.font_size == 24


class TestRehearsalResult:
    def test_pace_ratio_good(self):
        r = RehearsalResult(actual_duration=100, target_duration=100)
        assert r.pace_ratio == 1.0
        assert r.pace_feedback == "good pace"

    def test_pace_ratio_fast(self):
        r = RehearsalResult(actual_duration=70, target_duration=100)
        assert r.pace_ratio == 0.7
        assert r.pace_feedback == "too fast"

    def test_pace_ratio_slow(self):
        r = RehearsalResult(actual_duration=130, target_duration=100)
        assert r.pace_ratio == 1.3
        assert r.pace_feedback == "too slow"

    def test_pace_ratio_zero_target(self):
        r = RehearsalResult(actual_duration=50, target_duration=0)
        assert r.pace_ratio == 0.0
        assert r.pace_feedback == "no data"

    def test_round_trip(self):
        r = RehearsalResult(
            actual_duration=120,
            target_duration=100,
            section_timings=[{"section": "HOOK", "duration": 15}],
            notes="Spoke too fast in HOOK",
        )
        d = r.to_dict()
        assert d["pace_ratio"] == 1.2
        assert d["pace_feedback"] == "too slow"
        restored = RehearsalResult.from_dict(d)
        assert restored.actual_duration == 120
        assert restored.target_duration == 100
        assert len(restored.section_timings) == 1
        assert restored.notes == "Spoke too fast in HOOK"


class TestTimelineTrack:
    def test_round_trip(self):
        t = TimelineTrack(
            name="Narration",
            track_type="narration",
            events=[{"start_time": 0, "duration": 10, "text": "Hello"}],
        )
        d = t.to_dict()
        restored = TimelineTrack.from_dict(d)
        assert restored.name == "Narration"
        assert restored.track_type == "narration"
        assert len(restored.events) == 1


class TestRecordingSession:
    def test_defaults(self):
        s = RecordingSession()
        assert s.mode == RecordingMode.TELEPROMPTER
        assert s.cues == []
        assert s.timeline_tracks == []
        assert s.rehearsals == []
        assert s.total_duration_estimate == 0.0

    def test_round_trip(self):
        session = RecordingSession(
            project_id="proj_abc",
            mode=RecordingMode.CUE_SYSTEM,
            cues=[
                RecordingCue(cue_type=CueType.NARRATION, text="Hello", duration_estimate=5.0),
                RecordingCue(cue_type=CueType.PAUSE, text="[PAUSE]", duration_estimate=2.0),
            ],
            teleprompter_settings=TeleprompterSettings(font_size=40),
            timeline_tracks=[
                TimelineTrack(name="Narration", track_type="narration", events=[]),
            ],
            rehearsals=[
                RehearsalResult(actual_duration=60, target_duration=60),
            ],
            total_duration_estimate=7.0,
        )
        d = session.to_dict()
        assert d["mode"] == "cue_system"
        assert len(d["cues"]) == 2
        assert d["teleprompter_settings"]["font_size"] == 40

        restored = RecordingSession.from_dict(d)
        assert restored.project_id == "proj_abc"
        assert restored.mode == RecordingMode.CUE_SYSTEM
        assert len(restored.cues) == 2
        assert restored.cues[0].cue_type == CueType.NARRATION
        assert restored.cues[1].cue_type == CueType.PAUSE
        assert restored.teleprompter_settings.font_size == 40
        assert len(restored.timeline_tracks) == 1
        assert len(restored.rehearsals) == 1
        assert restored.total_duration_estimate == 7.0

    def test_from_dict_invalid_mode(self):
        s = RecordingSession.from_dict({"mode": "invalid_mode"})
        assert s.mode == RecordingMode.TELEPROMPTER


# ============================================================================
# Session Generator tests
# ============================================================================

SAMPLE_SCRIPT = """# Test Screencast

## HOOK
Welcome to this video about Python data analysis.
We will explore pandas and matplotlib.

## OBJECTIVE
By the end of this video, you will understand how to load and visualize data.

## CONTENT
[SCREEN: Show Jupyter Notebook]

Let's start by importing our libraries.

```python
import pandas as pd
import matplotlib.pyplot as plt
```

**[PAUSE]**

Now let's load a dataset.

```python
df = pd.read_csv('data.csv')
print(df.head())
```

The output shows the first five rows.

**[PAUSE]**

## IVQ
**Question:** What function loads a CSV file?
A) pd.load_csv()
B) pd.read_csv()
C) pd.open_csv()
D) pd.import_csv()
**Correct Answer:** B

## SUMMARY
Today we learned how to load data with pandas.

## CALL TO ACTION
Try loading your own dataset and share your results.
"""


class TestRecordingSessionGenerator:
    def setup_method(self):
        self.gen = RecordingSessionGenerator()

    def test_generate_session_basic(self):
        session = self.gen.generate_session("proj_1", SAMPLE_SCRIPT)
        assert session.project_id == "proj_1"
        assert session.mode == RecordingMode.TELEPROMPTER
        assert len(session.cues) > 0
        assert session.total_duration_estimate > 0

    def test_cue_order_sequential(self):
        session = self.gen.generate_session("proj_1", SAMPLE_SCRIPT)
        orders = [c.order for c in session.cues]
        assert orders == list(range(len(session.cues)))

    def test_sections_present(self):
        session = self.gen.generate_session("proj_1", SAMPLE_SCRIPT)
        sections = {c.section for c in session.cues}
        assert "HOOK" in sections
        assert "CONTENT" in sections
        assert "SUMMARY" in sections

    def test_code_blocks_become_code_cues(self):
        session = self.gen.generate_session("proj_1", SAMPLE_SCRIPT)
        code_cues = [c for c in session.cues if c.cue_type == CueType.CODE_ACTION]
        assert len(code_cues) >= 2  # Two code blocks in CONTENT

    def test_pauses_become_pause_cues(self):
        session = self.gen.generate_session("proj_1", SAMPLE_SCRIPT)
        pause_cues = [c for c in session.cues if c.cue_type == CueType.PAUSE]
        assert len(pause_cues) >= 1

    def test_visual_cues_extracted(self):
        session = self.gen.generate_session("proj_1", SAMPLE_SCRIPT)
        visual_cues = [c for c in session.cues if c.cue_type == CueType.VISUAL_CUE]
        assert len(visual_cues) >= 1
        assert any("Jupyter" in c.text for c in visual_cues)

    def test_timeline_tracks_generated(self):
        session = self.gen.generate_session("proj_1", SAMPLE_SCRIPT)
        assert len(session.timeline_tracks) > 0
        track_types = {t.track_type for t in session.timeline_tracks}
        assert "narration" in track_types

    def test_timeline_events_have_times(self):
        session = self.gen.generate_session("proj_1", SAMPLE_SCRIPT)
        for track in session.timeline_tracks:
            for event in track.events:
                assert "start_time" in event
                assert "duration" in event
                assert "end_time" in event
                assert event["end_time"] > event["start_time"]

    def test_empty_script_produces_no_cues(self):
        session = self.gen.generate_session("proj_1", "")
        assert len(session.cues) == 0
        assert session.total_duration_estimate == 0

    def test_no_sections_script(self):
        session = self.gen.generate_session("proj_1", "Just some plain text without any sections.")
        # Should still produce cues from the preamble
        assert len(session.cues) >= 1

    def test_estimate_duration(self):
        dur = self.gen._estimate_duration("This is a short sentence.")
        assert dur >= 1.0

    def test_estimate_code_duration(self):
        dur = self.gen._estimate_code_duration("x = 1\ny = 2\nprint(x + y)")
        assert dur >= 6.0  # 3 lines * 3 seconds

    def test_split_content_basic(self):
        chunks = self.gen._split_content("Paragraph one.\n\nParagraph two.")
        assert len(chunks) == 2

    def test_cta_normalized(self):
        script = "## CTA\nPlease subscribe."
        session = self.gen.generate_session("proj_1", script)
        sections = {c.section for c in session.cues}
        assert "CALL TO ACTION" in sections

    def test_custom_mode(self):
        session = self.gen.generate_session("proj_1", SAMPLE_SCRIPT, mode=RecordingMode.CUE_SYSTEM)
        assert session.mode == RecordingMode.CUE_SYSTEM


# ============================================================================
# API endpoint tests
# ============================================================================

@pytest.fixture
def client(tmp_path):
    from app_v5 import app, project_store, recording_sessions
    from src.core.project_store import ProjectStore
    from src.core.models import Project

    app.config['TESTING'] = True
    store = ProjectStore(tmp_path / 'projects')
    # Monkey-patch the store
    import app_v5
    original_store = app_v5.project_store
    app_v5.project_store = store

    # Create a test project
    project = Project(id="test_proj", title="Test", raw_script=SAMPLE_SCRIPT)
    store.save(project)

    # Clear sessions
    recording_sessions.clear()

    with app.test_client() as c:
        yield c

    app_v5.project_store = original_store
    recording_sessions.clear()


class TestRecordingStudioAPI:
    def test_generate_session(self, client):
        resp = client.post('/api/projects/test_proj/recording-session',
                           json={'mode': 'teleprompter'},
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'session' in data
        assert len(data['session']['cues']) > 0
        assert data['session']['total_duration_estimate'] > 0

    def test_get_session_not_found(self, client):
        resp = client.get('/api/projects/test_proj/recording-session')
        assert resp.status_code == 404

    def test_get_session_after_generate(self, client):
        client.post('/api/projects/test_proj/recording-session',
                     json={}, content_type='application/json')
        resp = client.get('/api/projects/test_proj/recording-session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'session' in data

    def test_set_mode(self, client):
        client.post('/api/projects/test_proj/recording-session',
                     json={}, content_type='application/json')
        resp = client.put('/api/projects/test_proj/recording-session/mode',
                          json={'mode': 'cue_system'},
                          content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['mode'] == 'cue_system'

    def test_set_invalid_mode(self, client):
        client.post('/api/projects/test_proj/recording-session',
                     json={}, content_type='application/json')
        resp = client.put('/api/projects/test_proj/recording-session/mode',
                          json={'mode': 'nonexistent'},
                          content_type='application/json')
        assert resp.status_code == 400

    def test_update_teleprompter_settings(self, client):
        client.post('/api/projects/test_proj/recording-session',
                     json={}, content_type='application/json')
        resp = client.put('/api/projects/test_proj/recording-session/teleprompter',
                          json={'font_size': 48, 'mirror': True},
                          content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['teleprompter_settings']['font_size'] == 48
        assert data['teleprompter_settings']['mirror'] is True

    def test_start_rehearsal(self, client):
        client.post('/api/projects/test_proj/recording-session',
                     json={}, content_type='application/json')
        resp = client.post('/api/projects/test_proj/recording-session/rehearsal',
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['total_cues'] > 0
        assert data['target_duration'] > 0

    def test_complete_rehearsal(self, client):
        client.post('/api/projects/test_proj/recording-session',
                     json={}, content_type='application/json')
        resp = client.post('/api/projects/test_proj/recording-session/rehearsal/complete',
                           json={'actual_duration': 120, 'notes': 'Good run'},
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['rehearsal']['actual_duration'] == 120
        assert data['rehearsal']['pace_feedback'] in ('good pace', 'too fast', 'too slow')

    def test_recording_studio_page(self, client):
        resp = client.get('/studio/test_proj')
        assert resp.status_code == 200
        assert b'Recording Studio' in resp.data

    def test_recording_studio_page_not_found(self, client):
        resp = client.get('/studio/nonexistent')
        assert resp.status_code == 302  # redirect to dashboard

    def test_generate_session_no_script(self, client):
        from src.core.models import Project
        import app_v5
        empty_proj = Project(id="empty_proj", title="Empty")
        app_v5.project_store.save(empty_proj)
        resp = client.post('/api/projects/empty_proj/recording-session',
                           json={}, content_type='application/json')
        assert resp.status_code == 400

    def test_generate_session_project_not_found(self, client):
        resp = client.post('/api/projects/nonexistent/recording-session',
                           json={}, content_type='application/json')
        assert resp.status_code == 404

    def test_mode_no_session(self, client):
        resp = client.put('/api/projects/test_proj/recording-session/mode',
                          json={'mode': 'rehearsal'},
                          content_type='application/json')
        assert resp.status_code == 404

    def test_teleprompter_no_session(self, client):
        resp = client.put('/api/projects/test_proj/recording-session/teleprompter',
                          json={'font_size': 24},
                          content_type='application/json')
        assert resp.status_code == 404

    def test_rehearsal_no_session(self, client):
        resp = client.post('/api/projects/test_proj/recording-session/rehearsal',
                           content_type='application/json')
        assert resp.status_code == 404

    def test_complete_rehearsal_no_session(self, client):
        resp = client.post('/api/projects/test_proj/recording-session/rehearsal/complete',
                           json={'actual_duration': 60},
                           content_type='application/json')
        assert resp.status_code == 404

    def test_set_mode_missing_mode(self, client):
        client.post('/api/projects/test_proj/recording-session',
                     json={}, content_type='application/json')
        resp = client.put('/api/projects/test_proj/recording-session/mode',
                          json={},
                          content_type='application/json')
        assert resp.status_code == 400
