"""Tests for script generator."""

import pytest
from src.generators.script_generator import ScriptGenerator, GeneratedScript, ScriptSection


class TestScriptGenerator:
    """Test suite for ScriptGenerator."""

    def test_parse_sections(self):
        """Test section parsing from script text."""
        generator = ScriptGenerator()

        script_text = """## HOOK
This is the hook.

## OBJECTIVE
By the end of this video...

## CONTENT
Main content here.

## SUMMARY
Key takeaways.

## CALL TO ACTION
Next, try the lab.
"""

        sections = generator._parse_sections(script_text, 7)

        assert len(sections) == 5
        assert sections[0].name == "HOOK"
        assert "This is the hook" in sections[0].content

    def test_parse_sections_word_count(self):
        """Test that word count is calculated correctly."""
        generator = ScriptGenerator()

        script_text = """## HOOK
One two three four five.

## OBJECTIVE
Six seven eight.
"""

        sections = generator._parse_sections(script_text, 7)

        assert sections[0].word_count == 5
        assert sections[1].word_count == 3

    def test_generated_script_to_tts_removes_visual_cues(self):
        """Test that TTS export removes visual cues."""
        script = GeneratedScript(
            raw_text="## HOOK\nLook at this [visual cue here] example.",
            sections=[],
            total_words=10,
            estimated_duration_minutes=1.0
        )

        tts_text = script.to_tts_text()

        assert "[visual cue here]" not in tts_text
        assert "Look at this" in tts_text
        assert "example" in tts_text

    def test_generated_script_to_markdown(self):
        """Test markdown export returns raw text."""
        raw = "## HOOK\nTest content"
        script = GeneratedScript(
            raw_text=raw,
            sections=[],
            total_words=5,
            estimated_duration_minutes=0.5
        )

        assert script.to_markdown() == raw

    def test_script_section_dataclass(self):
        """Test ScriptSection dataclass."""
        section = ScriptSection(
            name="HOOK",
            content="Test content",
            duration_seconds=42,
            word_count=2
        )

        assert section.name == "HOOK"
        assert section.content == "Test content"
        assert section.duration_seconds == 42
        assert section.word_count == 2
