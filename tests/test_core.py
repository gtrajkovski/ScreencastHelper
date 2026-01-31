"""Tests for src/core models, project store, and parser."""

import json
import tempfile
from pathlib import Path
import pytest
from src.core.models import Segment, SegmentType, SegmentStatus, Project
from src.core.project_store import ProjectStore
from src.core.parser import parse_script_to_segments


class TestSegment:
    def test_create_default(self):
        seg = Segment()
        assert seg.type == SegmentType.SLIDE
        assert seg.status == SegmentStatus.DRAFT
        assert seg.narration == ""
        assert seg.id

    def test_to_dict_and_back(self):
        seg = Segment(
            section="CONTENT",
            title="Demo",
            narration="Hello world",
            type=SegmentType.SCREENCAST,
            code="print('hi')",
        )
        d = seg.to_dict()
        assert d["type"] == "screencast"
        assert d["section"] == "CONTENT"
        restored = Segment.from_dict(d)
        assert restored.type == SegmentType.SCREENCAST
        assert restored.code == "print('hi')"

    def test_ivq_fields(self):
        seg = Segment(
            type=SegmentType.IVQ,
            question="What is 2+2?",
            options=[{"letter": "A", "text": "3"}, {"letter": "B", "text": "4"}],
            correct_answer="B",
            feedback={"A": "Incorrect.", "B": "Correct."},
        )
        d = seg.to_dict()
        assert d["question"] == "What is 2+2?"
        assert len(d["options"]) == 2


class TestProject:
    def test_create_default(self):
        proj = Project()
        assert proj.id.startswith("proj_")
        assert proj.title == "Untitled Project"
        assert proj.segments == []

    def test_to_dict_with_segments(self):
        proj = Project(title="Test")
        proj.segments = [
            Segment(section="HOOK", title="Hook", narration="Attention!"),
            Segment(section="CONTENT", title="Demo", type=SegmentType.SCREENCAST),
        ]
        d = proj.to_dict()
        assert len(d["segments"]) == 2
        assert d["segments"][0]["section"] == "HOOK"

    def test_from_dict(self):
        data = {
            "id": "proj_test123",
            "title": "Test Project",
            "raw_script": "## HOOK\nHello",
            "segments": [{"id": "s1", "type": "slide", "section": "HOOK",
                         "title": "Hook", "narration": "Hello", "visual_cue": "",
                         "code": None, "duration_estimate": 10.0,
                         "status": "draft", "audio_path": None, "video_path": None,
                         "recorded_duration": None, "question": None,
                         "options": None, "correct_answer": None,
                         "feedback": None, "order": 0,
                         "created_at": "2025-01-01", "updated_at": "2025-01-01"}],
            "target_duration": 5,
            "environment": "jupyter",
            "audience_level": "beginner",
            "style": "tutorial",
            "tts_script": "",
            "timeline": None,
            "datasets": [],
            "schema_version": 1,
            "created_at": "2025-01-01",
            "updated_at": "2025-01-01",
        }
        proj = Project.from_dict(data)
        assert proj.id == "proj_test123"
        assert len(proj.segments) == 1
        assert proj.segments[0].type == SegmentType.SLIDE


class TestProjectStore:
    def test_save_and_load(self, tmp_path):
        store = ProjectStore(tmp_path / "projects")
        proj = Project(title="Save Test")
        proj.segments = [Segment(section="HOOK", narration="Hello")]
        store.save(proj)

        loaded = store.load(proj.id)
        assert loaded is not None
        assert loaded.title == "Save Test"
        assert len(loaded.segments) == 1
        assert loaded.segments[0].narration == "Hello"

    def test_list_projects(self, tmp_path):
        store = ProjectStore(tmp_path / "projects")
        p1 = Project(title="First")
        p2 = Project(title="Second")
        store.save(p1)
        store.save(p2)

        listing = store.list_projects()
        assert len(listing) == 2
        titles = {p["title"] for p in listing}
        assert titles == {"First", "Second"}

    def test_delete(self, tmp_path):
        store = ProjectStore(tmp_path / "projects")
        proj = Project(title="To Delete")
        store.save(proj)
        assert store.load(proj.id) is not None

        result = store.delete(proj.id)
        assert result is True
        assert store.load(proj.id) is None

    def test_load_nonexistent(self, tmp_path):
        store = ProjectStore(tmp_path / "projects")
        assert store.load("proj_nonexistent") is None

    def test_delete_nonexistent(self, tmp_path):
        store = ProjectStore(tmp_path / "projects")
        assert store.delete("proj_nonexistent") is False

    def test_creates_subdirs(self, tmp_path):
        store = ProjectStore(tmp_path / "projects")
        proj = Project(title="Subdir Test")
        store.save(proj)
        project_dir = tmp_path / "projects" / proj.id
        assert (project_dir / "audio").is_dir()
        assert (project_dir / "video").is_dir()
        assert (project_dir / "data").is_dir()


class TestParser:
    def test_empty_script(self):
        assert parse_script_to_segments("") == []
        assert parse_script_to_segments("   ") == []

    def test_basic_wwhaa(self):
        script = """## HOOK
This is the hook with a cool opening.

## OBJECTIVE
By the end of this video, you'll be able to:
- Use pandas DataFrames

## CONTENT
### Segment 1: Introduction
Let's get started with some code.

```python
import pandas as pd
df = pd.read_csv("data.csv")
print(df.head())
```

## IVQ
**Question:** What method shows the first rows of a DataFrame?
A) df.first()
B) df.head()
C) df.top()
D) df.start()
**Correct Answer:** B
**Feedback A:** Incorrect. first() is not a DataFrame method.
**Feedback B:** Correct. head() returns the first 5 rows.
**Feedback C:** Incorrect. top() is not a DataFrame method.
**Feedback D:** Incorrect. start() is not a DataFrame method.

## SUMMARY
We learned about pandas DataFrames.

## CTA
Try the practice quiz next.
"""
        segments = parse_script_to_segments(script)
        assert len(segments) >= 6  # HOOK, OBJECTIVE, Segment 1, IVQ, SUMMARY, CTA

        # Check sections are detected
        sections = [s.section for s in segments]
        assert "HOOK" in sections
        assert "OBJECTIVE" in sections
        assert "CONTENT" in sections
        assert "IVQ" in sections
        assert "SUMMARY" in sections
        assert "CTA" in sections

    def test_code_detection(self):
        script = """## CONTENT
### Segment 1: Demo

```python
x = 42
print(x)
```
"""
        segments = parse_script_to_segments(script)
        code_segs = [s for s in segments if s.code]
        assert len(code_segs) >= 1
        assert "x = 42" in code_segs[0].code

    def test_ivq_parsing(self):
        script = """## IVQ
**Question:** What is 2+2?
A) 3
B) 4
C) 5
D) 6
**Correct Answer:** B
**Feedback A:** Incorrect.
**Feedback B:** Correct.
**Feedback C:** Incorrect.
**Feedback D:** Incorrect.
"""
        segments = parse_script_to_segments(script)
        ivq_segs = [s for s in segments if s.type == SegmentType.IVQ]
        assert len(ivq_segs) == 1
        ivq = ivq_segs[0]
        assert ivq.question == "What is 2+2?"
        assert ivq.correct_answer == "B"
        assert len(ivq.options) == 4
        assert ivq.feedback is not None

    def test_duration_estimation(self):
        script = """## HOOK
This is a hook with about twenty words or so to test the duration estimation feature that we have built into the parser module.
"""
        segments = parse_script_to_segments(script)
        assert len(segments) >= 1
        # Should have a duration estimate
        assert segments[0].duration_estimate is not None
        assert segments[0].duration_estimate > 0

    def test_visual_cue_detection(self):
        script = """## CONTENT
[SCREEN: Jupyter Notebook - new cell]
Let's write some code.
"""
        segments = parse_script_to_segments(script)
        cue_segs = [s for s in segments if s.visual_cue]
        assert len(cue_segs) >= 1
        assert "Jupyter" in cue_segs[0].visual_cue

    def test_segment_ordering(self):
        script = """## HOOK
Hook text.

## OBJECTIVE
Objective text.

## CONTENT
Content text.
"""
        segments = parse_script_to_segments(script)
        orders = [s.order for s in segments]
        assert orders == sorted(orders)

    def test_section_false_positive_prevention(self):
        """Headers containing section keywords as substrings should NOT match."""
        script = """## CONTENT
### Summary of Results
This is about summarizing results, not the SUMMARY section.

### Content Overview
More details.
"""
        segments = parse_script_to_segments(script)
        # "Summary of Results" should be a CONTENT sub-segment, not SUMMARY section
        for seg in segments:
            if seg.title == "Summary of Results":
                assert seg.section == "CONTENT", f"Expected CONTENT but got {seg.section}"
            if seg.title == "Content Overview":
                assert seg.section == "CONTENT", f"Expected CONTENT but got {seg.section}"

    def test_ivq_feedback_completeness(self):
        """IVQ should parse all feedback entries."""
        script = """## IVQ
**Question:** Which is correct?
A) Alpha
B) Beta
C) Gamma
D) Delta
**Correct Answer:** B
**Feedback A:** Wrong, not Alpha.
**Feedback B:** Correct, it's Beta.
**Feedback C:** Wrong, not Gamma.
**Feedback D:** Wrong, not Delta.
"""
        segments = parse_script_to_segments(script)
        ivq = [s for s in segments if s.type == SegmentType.IVQ][0]
        assert ivq.feedback is not None
        assert len(ivq.feedback) == 4
        assert "A" in ivq.feedback
        assert "D" in ivq.feedback


class TestModelResilience:
    def test_segment_from_dict_unknown_keys(self):
        """from_dict should ignore unknown keys instead of crashing."""
        data = {
            "id": "test_seg",
            "type": "slide",
            "section": "HOOK",
            "title": "Test",
            "narration": "Hello",
            "unknown_future_field": "some value",
            "another_new_field": 42,
        }
        seg = Segment.from_dict(data)
        assert seg.id == "test_seg"
        assert seg.section == "HOOK"

    def test_project_from_dict_unknown_keys(self):
        """from_dict should ignore unknown keys instead of crashing."""
        data = {
            "id": "proj_test",
            "title": "Test",
            "raw_script": "",
            "segments": [],
            "new_v6_field": "future",
            "schema_version": 1,
        }
        proj = Project.from_dict(data)
        assert proj.id == "proj_test"
        assert proj.title == "Test"

    def test_segment_from_dict_invalid_type(self):
        """from_dict should handle invalid enum values gracefully."""
        data = {
            "id": "test_seg",
            "type": "unknown_type",
            "status": "invalid_status",
        }
        seg = Segment.from_dict(data)
        assert seg.type == SegmentType.SLIDE  # Falls back to default
        assert seg.status == SegmentStatus.DRAFT  # Falls back to default


class TestProjectStoreEdgeCases:
    def test_path_traversal_blocked(self, tmp_path):
        """Project IDs with path traversal should be sanitized."""
        store = ProjectStore(tmp_path / "projects")
        sanitized = store._sanitize_id("../../../etc/passwd")
        assert ".." not in sanitized
        assert "/" not in sanitized
        assert "\\" not in sanitized

    def test_empty_id_raises(self, tmp_path):
        """Empty project ID after sanitization should raise ValueError."""
        store = ProjectStore(tmp_path / "projects")
        with pytest.raises(ValueError):
            store._sanitize_id("../../..")

    def test_unicode_title_save_load(self, tmp_path):
        """Projects with unicode titles should save/load correctly."""
        store = ProjectStore(tmp_path / "projects")
        proj = Project(title="Données d'analyse — café")
        store.save(proj)
        loaded = store.load(proj.id)
        assert loaded.title == "Données d'analyse — café"
