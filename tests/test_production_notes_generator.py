"""Tests for the Production Notes Generator module."""

import pytest
from pathlib import Path

from src.generators.production_notes_generator import (
    ProductionNotes,
    ProductionNotesGenerator,
)
from src.parsers.script_importer import ImportedScript


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_script(
    title="Test Video",
    duration_estimate=5,
    sections=None,
    code_blocks=None,
    ivq=None,
    raw_text="",
) -> ImportedScript:
    """Create a minimal ImportedScript for testing."""
    if sections is None:
        sections = [
            {
                "type": "HOOK",
                "text": "Have you ever wondered about data cleaning? " * 10,
                "visual_cues": ["SHOW SLIDE: Title"],
            },
            {
                "type": "CONTENT",
                "text": "Let's look at some pandas examples. " * 30,
                "visual_cues": ["SWITCH TO: Jupyter Notebook", "RUN CELL"],
            },
            {
                "type": "SUMMARY",
                "text": "Today we learned about data cleaning. " * 8,
                "visual_cues": [],
            },
        ]
    if code_blocks is None:
        code_blocks = [
            {
                "language": "python",
                "code": "import pandas as pd\ndf = pd.read_csv('data.csv')\ndf.head()",
                "section": "CONTENT",
            },
        ]
    return ImportedScript(
        title=title,
        duration_estimate=duration_estimate,
        sections=sections,
        code_blocks=code_blocks,
        ivq=ivq,
        raw_text=raw_text,
    )


# ---------------------------------------------------------------------------
# Tests: ProductionNotesGenerator internals
# ---------------------------------------------------------------------------

class TestProductionNotesGeneratorBuildNotes:
    def test_build_notes_returns_production_notes(self, tmp_path):
        """_build_notes should return a ProductionNotes dataclass."""
        gen = ProductionNotesGenerator()
        script = _make_script()
        notes = gen._build_notes(script, tmp_path)

        assert isinstance(notes, ProductionNotes)
        assert notes.title == "Test Video"
        assert notes.duration_estimate == 5

    def test_build_notes_timing_summary(self, tmp_path):
        """Timing summary should have one entry per section."""
        gen = ProductionNotesGenerator()
        script = _make_script()
        notes = gen._build_notes(script, tmp_path)

        assert len(notes.timing_summary) == len(script.sections)
        for entry in notes.timing_summary:
            assert "segment" in entry
            assert "duration" in entry
            assert "visual" in entry
            assert "narration_preview" in entry

    def test_build_notes_timing_uses_section_type(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script()
        notes = gen._build_notes(script, tmp_path)

        segments = [e["segment"] for e in notes.timing_summary]
        assert "HOOK" in segments
        assert "CONTENT" in segments
        assert "SUMMARY" in segments

    def test_build_notes_visual_cues_in_timing(self, tmp_path):
        """Timing visual field should use visual_cues from sections."""
        gen = ProductionNotesGenerator()
        script = _make_script()
        notes = gen._build_notes(script, tmp_path)

        hook_entry = notes.timing_summary[0]
        assert "SHOW SLIDE: Title" in hook_entry["visual"]

    def test_build_notes_empty_visual_cues_fallback(self, tmp_path):
        """Sections with no visual cues should use fallback text."""
        gen = ProductionNotesGenerator()
        script = _make_script()
        notes = gen._build_notes(script, tmp_path)

        summary_entry = notes.timing_summary[2]
        assert summary_entry["visual"] == "Talking head / Notebook"

    def test_build_notes_pre_recording_checklist(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script()
        notes = gen._build_notes(script, tmp_path)

        assert len(notes.pre_recording_checklist) == len(
            ProductionNotesGenerator.PRE_RECORDING_CHECKLIST
        )
        assert notes.pre_recording_checklist is ProductionNotesGenerator.PRE_RECORDING_CHECKLIST

    def test_build_notes_cue_legend(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script()
        notes = gen._build_notes(script, tmp_path)

        assert "[PAUSE]" in notes.cue_legend
        assert "[RUN CELL]" in notes.cue_legend

    def test_build_notes_discovers_slide_assets(self, tmp_path):
        """Should list PNG files from slides/png/ directory."""
        slides_dir = tmp_path / "slides" / "png"
        slides_dir.mkdir(parents=True)
        (slides_dir / "slide_01_title.png").write_bytes(b"fake")
        (slides_dir / "slide_02_objective.png").write_bytes(b"fake")

        gen = ProductionNotesGenerator()
        script = _make_script()
        notes = gen._build_notes(script, tmp_path)

        assert len(notes.visual_assets) == 2
        assert "slide_01_title.png" in notes.visual_assets

    def test_build_notes_no_slides_dir(self, tmp_path):
        """Should return empty list when slides dir doesn't exist."""
        gen = ProductionNotesGenerator()
        script = _make_script()
        notes = gen._build_notes(script, tmp_path)

        assert notes.visual_assets == []


class TestCellAlignment:
    def test_cell_alignment_maps_code_blocks(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script(code_blocks=[
            {"language": "python", "code": "x = 1\ny = 2\nprint(x + y)", "section": "CONTENT"},
            {"language": "python", "code": "import numpy as np\nnp.array([1,2,3])", "section": "CONTENT"},
        ])
        notes = gen._build_notes(script, tmp_path)

        assert len(notes.cell_alignment_table) == 2
        assert notes.cell_alignment_table[0]["cell"] == 1
        assert notes.cell_alignment_table[1]["cell"] == 2

    def test_cell_alignment_truncates_code(self, tmp_path):
        gen = ProductionNotesGenerator()
        long_code = "x = " + "a" * 100
        script = _make_script(code_blocks=[
            {"language": "python", "code": long_code, "section": "CONTENT"},
        ])
        notes = gen._build_notes(script, tmp_path)

        assert notes.cell_alignment_table[0]["code"].endswith("...")
        assert len(notes.cell_alignment_table[0]["code"]) <= 54

    def test_cell_alignment_empty_code_blocks(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script(code_blocks=[])
        notes = gen._build_notes(script, tmp_path)

        assert notes.cell_alignment_table == []


# ---------------------------------------------------------------------------
# Tests: Markdown output
# ---------------------------------------------------------------------------

class TestMarkdownOutput:
    def test_generate_markdown_creates_file(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script()
        result = gen.generate(script, tmp_path, fmt="md")

        assert result.exists()
        assert result.suffix == ".md"

    def test_markdown_contains_title(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script(title="My Great Video")
        result = gen.generate(script, tmp_path, fmt="md")

        content = result.read_text(encoding="utf-8")
        assert "My Great Video" in content

    def test_markdown_contains_checklist(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script()
        result = gen.generate(script, tmp_path, fmt="md")

        content = result.read_text(encoding="utf-8")
        assert "Pre-Recording Checklist" in content
        assert "- [ ]" in content

    def test_markdown_contains_timing_table(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script()
        result = gen.generate(script, tmp_path, fmt="md")

        content = result.read_text(encoding="utf-8")
        assert "Timing Summary" in content
        assert "| HOOK |" in content

    def test_markdown_contains_cue_legend(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script()
        result = gen.generate(script, tmp_path, fmt="md")

        content = result.read_text(encoding="utf-8")
        assert "Cue Legend" in content
        assert "[PAUSE]" in content

    def test_markdown_contains_cell_alignment(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script()
        result = gen.generate(script, tmp_path, fmt="md")

        content = result.read_text(encoding="utf-8")
        assert "Notebook Cell Alignment" in content

    def test_markdown_omits_cell_alignment_when_no_code(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script(code_blocks=[])
        result = gen.generate(script, tmp_path, fmt="md")

        content = result.read_text(encoding="utf-8")
        assert "Notebook Cell Alignment" not in content

    def test_markdown_contains_visual_assets(self, tmp_path):
        slides_dir = tmp_path / "slides" / "png"
        slides_dir.mkdir(parents=True)
        (slides_dir / "slide_01_title.png").write_bytes(b"fake")

        gen = ProductionNotesGenerator()
        script = _make_script()
        result = gen.generate(script, tmp_path, fmt="md")

        content = result.read_text(encoding="utf-8")
        assert "Visual Assets" in content
        assert "slide_01_title.png" in content

    def test_markdown_omits_visual_assets_when_none(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script()
        result = gen.generate(script, tmp_path, fmt="md")

        content = result.read_text(encoding="utf-8")
        assert "Visual Assets" not in content

    def test_markdown_contains_duration_estimate(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script(duration_estimate=7)
        result = gen.generate(script, tmp_path, fmt="md")

        content = result.read_text(encoding="utf-8")
        assert "7 minutes" in content


# ---------------------------------------------------------------------------
# Tests: Docx output (falls back to markdown if python-docx missing)
# ---------------------------------------------------------------------------

class TestDocxOutput:
    def test_generate_docx_creates_file(self, tmp_path):
        """Should create a .docx or fall back to .md."""
        gen = ProductionNotesGenerator()
        script = _make_script()
        result = gen.generate(script, tmp_path, fmt="docx")

        assert result.exists()
        assert result.suffix in (".docx", ".md")

    def test_generate_docx_file_not_empty(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script()
        result = gen.generate(script, tmp_path, fmt="docx")

        assert result.stat().st_size > 0


# ---------------------------------------------------------------------------
# Tests: Default format
# ---------------------------------------------------------------------------

class TestDefaultFormat:
    def test_default_format_is_docx(self, tmp_path):
        """Default fmt should be 'docx'."""
        gen = ProductionNotesGenerator()
        script = _make_script()
        result = gen.generate(script, tmp_path)

        assert result.exists()
        # Either .docx or .md fallback
        assert result.suffix in (".docx", ".md")


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_sections(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script(sections=[])
        result = gen.generate(script, tmp_path, fmt="md")

        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "Timing Summary" in content

    def test_section_with_very_short_text(self, tmp_path):
        gen = ProductionNotesGenerator()
        script = _make_script(sections=[
            {"type": "HOOK", "text": "Hi", "visual_cues": []},
        ])
        notes = gen._build_notes(script, tmp_path)

        # Duration should be at least 30 seconds
        assert "30 seconds" in notes.timing_summary[0]["duration"]

    def test_creates_parent_directories(self, tmp_path):
        """Should create parent dirs if they don't exist."""
        gen = ProductionNotesGenerator()
        script = _make_script()
        nested = tmp_path / "deep" / "nested"
        result = gen.generate(script, nested, fmt="md")

        assert result.exists()
