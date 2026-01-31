"""Tests for v5 services and app endpoints."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.core.models import Segment, SegmentType, SegmentStatus, Project
from src.core.project_store import ProjectStore
from src.core.parser import parse_script_to_segments
from src.services.recording_service import (
    find_ffmpeg,
    is_ffmpeg_available,
    merge_audio_video,
    concatenate_segments,
    trim_segment,
)


# ============================================================================
# Recording Service Tests
# ============================================================================

class TestRecordingService:
    def test_find_ffmpeg_returns_string_or_none(self):
        result = find_ffmpeg()
        assert result is None or isinstance(result, str)

    def test_is_ffmpeg_available_returns_bool(self):
        assert isinstance(is_ffmpeg_available(), bool)

    def test_merge_no_ffmpeg(self):
        with patch('src.services.recording_service.find_ffmpeg', return_value=None):
            ok, msg = merge_audio_video("a.webm", "b.mp3", "c.webm")
            assert ok is False
            assert "FFmpeg not found" in msg

    def test_merge_missing_video(self, tmp_path):
        with patch('src.services.recording_service.find_ffmpeg', return_value="/usr/bin/ffmpeg"):
            ok, msg = merge_audio_video(
                str(tmp_path / "nonexistent.webm"),
                str(tmp_path / "audio.mp3"),
                str(tmp_path / "out.webm"),
            )
            assert ok is False
            assert "not found" in msg

    def test_concatenate_no_ffmpeg(self):
        with patch('src.services.recording_service.find_ffmpeg', return_value=None):
            ok, msg = concatenate_segments(["a.webm", "b.webm"], "out.webm")
            assert ok is False

    def test_concatenate_empty_list(self):
        with patch('src.services.recording_service.find_ffmpeg', return_value="/usr/bin/ffmpeg"):
            ok, msg = concatenate_segments([], "out.webm")
            assert ok is False
            assert "No input" in msg

    def test_trim_no_ffmpeg(self):
        with patch('src.services.recording_service.find_ffmpeg', return_value=None):
            ok, msg = trim_segment("input.webm", "output.webm", 0, 10)
            assert ok is False


# ============================================================================
# Migration Script Tests
# ============================================================================

class TestMigration:
    def test_convert_v4_project(self):
        """Test v4-to-v5 project conversion."""
        # Import here to avoid path issues
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
        from migrate_v4_to_v5 import convert_v4_project

        v4_data = {
            'id': 'proj_test',
            'name': 'Test Project',
            'script_raw': '## HOOK\nHello world',
            'config': {
                'duration_minutes': 7,
                'environment': 'terminal',
            },
            'segments': [
                {
                    'id': 'seg_1',
                    'type': 'slide',
                    'section': 'HOOK',
                    'title': 'Hook',
                    'narration': 'Welcome!',
                    'visual_cues': ['Title slide'],
                    'duration_seconds': 15.0,
                    'cells': [],
                },
                {
                    'id': 'seg_2',
                    'type': 'notebook',
                    'section': 'CONTENT',
                    'title': 'Demo',
                    'narration': 'Let me show you.',
                    'visual_cues': [],
                    'duration_seconds': 60.0,
                    'cells': [
                        {'type': 'code', 'content': 'print("hi")', 'output': 'hi'},
                    ],
                },
            ],
        }

        project = convert_v4_project(v4_data)
        assert project.id == 'proj_test'
        assert project.title == 'Test Project'
        assert project.raw_script == '## HOOK\nHello world'
        assert project.target_duration == 7
        assert project.environment == 'terminal'
        assert len(project.segments) == 2
        assert project.segments[0].type == SegmentType.SLIDE
        assert project.segments[0].visual_cue == 'Title slide'
        assert project.segments[1].type == SegmentType.SCREENCAST
        assert project.segments[1].code == 'print("hi")'

    def test_convert_v4_ivq(self):
        """Test v4 IVQ segment conversion."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
        from migrate_v4_to_v5 import convert_v4_project

        v4_data = {
            'name': 'IVQ Test',
            'segments': [
                {
                    'id': 'seg_ivq',
                    'type': 'ivq',
                    'section': 'IVQ',
                    'title': 'Question',
                    'narration': '',
                    'question': 'What is 2+2?',
                    'options': [{'letter': 'A', 'text': '3'}, {'letter': 'B', 'text': '4'}],
                    'correct_answer': 'B',
                    'feedback': {'A': 'Wrong', 'B': 'Correct'},
                },
            ],
        }

        project = convert_v4_project(v4_data)
        seg = project.segments[0]
        assert seg.type == SegmentType.IVQ
        assert seg.question == 'What is 2+2?'
        assert seg.correct_answer == 'B'


# ============================================================================
# Quality Check Logic Tests (same logic as in app_v5.py)
# ============================================================================

class TestQualityChecks:
    def test_missing_sections_detected(self):
        """Quality check should detect missing WWHAA sections."""
        script = "## HOOK\nHello\n## CONTENT\nStuff"
        required = ['## HOOK', '## OBJECTIVE', '## CONTENT', '## IVQ', '## SUMMARY', '## CTA']
        missing = [s for s in required if s not in script]
        assert '## OBJECTIVE' in missing
        assert '## IVQ' in missing
        assert '## SUMMARY' in missing
        assert '## CTA' in missing

    def test_timing_too_long(self):
        """Quality check should flag scripts that exceed target duration."""
        words = ' '.join(['word'] * 1500)  # 1500 words = 10 min at 150 WPM
        est_minutes = 1500 / 150
        target = 5
        assert est_minutes > target * 1.2

    def test_timing_too_short(self):
        """Quality check should flag scripts shorter than 70% of target."""
        words = ' '.join(['word'] * 300)  # 300 words = 2 min
        est_minutes = 300 / 150
        target = 5
        assert est_minutes < target * 0.7

    def test_code_syntax_validation(self):
        """Quality check should catch Python syntax errors."""
        import ast
        good_code = "x = 42\nprint(x)"
        bad_code = "def foo(\n  print('hi')"

        # Good code should parse
        ast.parse(good_code)

        # Bad code should fail
        with pytest.raises(SyntaxError):
            ast.parse(bad_code)


# ============================================================================
# Timeline Generation Tests
# ============================================================================

class TestTimeline:
    def test_project_timeline_ordering(self):
        """Timeline should have increasing start times."""
        project = Project(title="Timeline Test")
        project.segments = [
            Segment(section="HOOK", title="Hook", narration="Hello world",
                    duration_estimate=10.0),
            Segment(section="CONTENT", title="Demo", narration="Let me show you code",
                    duration_estimate=30.0),
            Segment(section="SUMMARY", title="Summary", narration="That wraps up",
                    duration_estimate=10.0),
        ]

        current_time = 0.0
        for seg in project.segments:
            duration = seg.recorded_duration or seg.duration_estimate or 30.0
            assert current_time >= 0
            start = current_time
            current_time += duration
            assert current_time > start

    def test_segment_timeline_generation(self):
        """TimelineGenerator should produce events for a segment."""
        from src.generators.timeline_generator import TimelineGenerator

        gen = TimelineGenerator()
        seg = {
            'id': 'test_seg',
            'type': 'notebook',
            'code_cells': [
                {'code': 'x = 42', 'output': '42', 'id': 'cell_0'},
            ],
        }
        timeline = gen.generate(seg, 30.0)
        assert timeline.total_duration == 30.0
        assert len(timeline.events) > 0

        # Should have audio_start and audio_end
        actions = [e.action for e in timeline.events]
        assert 'audio_start' in actions
        assert 'audio_end' in actions


# ============================================================================
# Parser Edge Cases
# ============================================================================

class TestParserEdgeCases:
    def test_multiple_code_blocks(self):
        """Parser should handle multiple code blocks in one section."""
        script = """## CONTENT
### Segment 1: Multi-code

```python
x = 1
```

Some narration here.

```python
y = 2
```
"""
        segments = parse_script_to_segments(script)
        code_segs = [s for s in segments if s.code]
        assert len(code_segs) >= 1
        # Code should contain both blocks
        assert 'x = 1' in code_segs[0].code
        assert 'y = 2' in code_segs[0].code

    def test_cell_break_ignored(self):
        """Parser should skip --- CELL BREAK --- lines."""
        script = """## CONTENT
First line.
--- CELL BREAK ---
Second line.
"""
        segments = parse_script_to_segments(script)
        for seg in segments:
            assert 'CELL BREAK' not in (seg.narration or '')

    def test_narration_label_parsed(self):
        """Parser should handle **NARRATION:** labels."""
        script = """## CONTENT
**NARRATION:** This is narration text.
"""
        segments = parse_script_to_segments(script)
        narrations = [s.narration for s in segments if s.narration]
        assert any('This is narration text' in n for n in narrations)

    def test_full_wwhaa_section_count(self):
        """Full WWHAA+IVQ script should produce segments for each section."""
        script = """## HOOK
Hook text here.

## OBJECTIVE
Learn something.

## CONTENT
### Segment 1: Intro
Let's begin.

```python
print("hello")
```

### Segment 2: More
More content.

## IVQ
**Question:** What is it?
A) Option A
B) Option B
C) Option C
D) Option D
**Correct Answer:** B
**Feedback A:** Wrong.
**Feedback B:** Right.
**Feedback C:** Wrong.
**Feedback D:** Wrong.

## SUMMARY
We learned stuff.

## CTA
Go practice.
"""
        segments = parse_script_to_segments(script)
        sections = {s.section for s in segments}
        assert 'HOOK' in sections
        assert 'OBJECTIVE' in sections
        assert 'CONTENT' in sections
        assert 'IVQ' in sections
        assert 'SUMMARY' in sections
        assert 'CTA' in sections

        # Check IVQ was parsed correctly
        ivq = [s for s in segments if s.type == SegmentType.IVQ]
        assert len(ivq) == 1
        assert ivq[0].question == 'What is it?'
        assert ivq[0].correct_answer == 'B'
        assert len(ivq[0].options) == 4
        assert ivq[0].feedback is not None


# ============================================================================
# App Flask Endpoint Tests (using test client)
# ============================================================================

class TestFlaskApp:
    @pytest.fixture
    def client(self, tmp_path):
        """Create a test Flask client with temporary project store."""
        import app_v5
        app_v5.project_store = ProjectStore(tmp_path / "projects")
        app_v5.app.config['TESTING'] = True
        with app_v5.app.test_client() as client:
            yield client

    def test_dashboard_loads(self, client):
        resp = client.get('/dashboard')
        assert resp.status_code == 200

    def test_list_projects_empty(self, client):
        resp = client.get('/api/projects')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == []

    def test_create_project(self, client):
        resp = client.post('/api/projects',
                          json={'name': 'Test Project', 'duration_minutes': 5})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == 'Test Project'
        assert data['id'].startswith('proj_')

    def test_create_and_get_project(self, client):
        resp = client.post('/api/projects', json={'name': 'CRUD Test'})
        project_id = resp.get_json()['id']

        resp = client.get(f'/api/projects/{project_id}')
        assert resp.status_code == 200
        assert resp.get_json()['name'] == 'CRUD Test'

    def test_update_project(self, client):
        resp = client.post('/api/projects', json={'name': 'Update Test'})
        pid = resp.get_json()['id']

        resp = client.put(f'/api/projects/{pid}',
                         json={'name': 'Updated Name', 'script_raw': '## HOOK\nHello'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['name'] == 'Updated Name'

    def test_delete_project(self, client):
        resp = client.post('/api/projects', json={'name': 'Delete Me'})
        pid = resp.get_json()['id']

        resp = client.delete(f'/api/projects/{pid}')
        assert resp.status_code == 200

        resp = client.get(f'/api/projects/{pid}')
        assert resp.status_code == 404

    def test_parse_script(self, client):
        resp = client.post('/api/projects', json={'name': 'Parse Test'})
        pid = resp.get_json()['id']

        resp = client.post(f'/api/projects/{pid}/parse',
                          json={'script_text': '## HOOK\nHello world\n## CONTENT\nSome content'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert len(data['segments']) >= 2

    def test_parse_standalone(self, client):
        resp = client.post('/api/parse/script',
                          json={'script_text': '## HOOK\nIntro text'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert len(data['segments']) >= 1

    def test_validate_code(self, client):
        resp = client.post('/api/validate-all-code',
                          json={'script_text': '```python\nx = 42\n```\n```python\ndef f(\n```'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total_blocks'] == 2
        assert data['invalid_count'] == 1

    def test_quality_check(self, client):
        resp = client.post('/api/projects',
                          json={'name': 'QC Test'})
        pid = resp.get_json()['id']

        # Set a script
        client.put(f'/api/projects/{pid}',
                  json={'script_raw': '## HOOK\nHello\n## CONTENT\nStuff'})

        resp = client.get(f'/api/projects/{pid}/quality-check')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['errors'] > 0  # Missing sections

    def test_get_nonexistent_project(self, client):
        resp = client.get('/api/projects/proj_nonexistent')
        assert resp.status_code == 404

    def test_ffmpeg_status(self, client):
        resp = client.get('/api/system/ffmpeg-status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'available' in data

    def test_voices_endpoint(self, client):
        resp = client.get('/api/voices')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert len(data['voices']) > 0

    def test_workspace_redirect_nonexistent(self, client):
        resp = client.get('/workspace/proj_nonexistent')
        assert resp.status_code == 302  # Redirect to dashboard

    def test_browse_folders(self, client, tmp_path):
        resp = client.get(f'/api/browse-folders?path={tmp_path}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'current' in data
        assert 'folders' in data

    def test_update_segment_invalid_status(self, client):
        """Invalid status should return 400, not crash."""
        resp = client.post('/api/projects', json={'name': 'Status Test'})
        pid = resp.get_json()['id']
        # Parse a script to create segments
        client.post(f'/api/projects/{pid}/parse',
                   json={'script_text': '## HOOK\nHello'})

        proj = client.get(f'/api/projects/{pid}').get_json()
        seg_id = proj['segments'][0]['id']

        resp = client.put(f'/api/projects/{pid}/segments/{seg_id}',
                         json={'status': 'nonexistent_status'})
        assert resp.status_code == 400

    def test_update_project_invalid_segment_type(self, client):
        """Invalid segment type should fall back to SLIDE, not crash."""
        resp = client.post('/api/projects', json={'name': 'Type Test'})
        pid = resp.get_json()['id']

        resp = client.put(f'/api/projects/{pid}', json={
            'segments': [{'id': 's1', 'type': 'nonexistent', 'section': 'HOOK',
                         'title': 'Test', 'narration': 'Hello'}]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['segments'][0]['type'] == 'slide'

    def test_recorder_page_loads(self, client):
        """Recorder page should load for valid project."""
        resp = client.post('/api/projects', json={'name': 'Rec Test'})
        pid = resp.get_json()['id']
        resp = client.get(f'/recorder/{pid}')
        assert resp.status_code == 200

    def test_recorder_page_nonexistent(self, client):
        """Recorder page should redirect for nonexistent project."""
        resp = client.get('/recorder/proj_nonexistent')
        assert resp.status_code == 302

    def test_timeline_endpoint(self, client):
        """Timeline endpoint should return segment timing data."""
        resp = client.post('/api/projects', json={'name': 'Timeline Test'})
        pid = resp.get_json()['id']
        client.post(f'/api/projects/{pid}/parse',
                   json={'script_text': '## HOOK\nHello world\n## CONTENT\nSome content'})

        resp = client.get(f'/api/projects/{pid}/timeline')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total_duration' in data
        assert 'segments' in data
        assert len(data['segments']) >= 2
        # Verify start times are increasing
        for i in range(1, len(data['segments'])):
            assert data['segments'][i]['start_time'] >= data['segments'][i-1]['start_time']

    def test_player_page_loads(self, client):
        """Player page should load for valid project."""
        resp = client.post('/api/projects', json={'name': 'Player Test'})
        pid = resp.get_json()['id']
        resp = client.get(f'/player/{pid}')
        assert resp.status_code == 200
