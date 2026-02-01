"""Tests for TTS optimizer."""

import pytest
from pathlib import Path
from src.generators.tts_optimizer import TTSOptimizer


class TestTTSOptimizer:
    """Test suite for TTSOptimizer."""

    def test_remove_visual_cues(self):
        """Test visual cue removal."""
        optimizer = TTSOptimizer()

        text = "Look at [click button] this [scroll down] example."
        result = optimizer._remove_visual_cues(text)

        assert "[click button]" not in result
        assert "[scroll down]" not in result
        assert "Look at" in result
        assert "example" in result

    def test_keep_pause_markers(self):
        """Test that [PAUSE] markers are kept."""
        optimizer = TTSOptimizer()

        text = "First point. [PAUSE] Second point."
        result = optimizer._remove_visual_cues(text)

        assert "[PAUSE]" in result

    def test_acronym_replacements(self):
        """Test acronym replacements."""
        optimizer = TTSOptimizer()

        text = "We use ML and API calls to process CSV files."
        result = optimizer._apply_replacements(text)

        assert "M-L" in result
        assert "A-P-I" in result
        assert "C-S-V" in result

    def test_python_specific_replacements(self):
        """Test Python-specific term replacements."""
        optimizer = TTSOptimizer()

        text = "Import sklearn and use numpy."
        result = optimizer._apply_replacements(text)

        assert "scikit-learn" in result
        assert "num-pie" in result

    def test_optimize_percentages(self):
        """Test percentage optimization."""
        optimizer = TTSOptimizer()

        text = "The accuracy is 95% on the test set."
        result = optimizer._optimize_numbers(text)

        assert "95 percent" in result

    def test_optimize_version_numbers(self):
        """Test version number optimization."""
        optimizer = TTSOptimizer()

        text = "We're using Python v3.9 for this project."
        result = optimizer._optimize_numbers(text)

        assert "version 3 point 9" in result

    def test_custom_replacements(self):
        """Test custom replacements."""
        custom = {"myterm": "my custom term"}
        optimizer = TTSOptimizer(custom_replacements=custom)

        text = "This is myterm in a sentence."
        result = optimizer._apply_replacements(text)

        assert "my custom term" in result

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        optimizer = TTSOptimizer()

        text = "Line one.\n\n\n\nLine two."
        result = optimizer._normalize_whitespace(text)

        assert "\n\n\n\n" not in result
        assert "Line one." in result
        assert "Line two." in result

    def test_ssml_markers(self):
        """Test SSML marker addition."""
        optimizer = TTSOptimizer()

        text = "First point. [PAUSE] Second point."
        result = optimizer.add_ssml_markers(text)

        assert "<speak>" in result
        assert "</speak>" in result
        assert '<break time="500ms"/>' in result
        assert "[PAUSE]" not in result

    def test_elevenlabs_markers(self):
        """Test ElevenLabs marker addition."""
        optimizer = TTSOptimizer()

        text = "First point. [PAUSE] Second point."
        result = optimizer.add_elevenlabs_markers(text)

        assert "..." in result
        assert "[PAUSE]" not in result

    def test_get_changes_report(self):
        """Test changes report generation."""
        optimizer = TTSOptimizer()

        original = "Use ML for the task."
        optimized = optimizer.optimize(original)

        changes = optimizer.get_changes_report(original, optimized)

        assert any(orig == "ML" for orig, _ in changes)

    def test_full_optimization(self):
        """Test full optimization pipeline."""
        optimizer = TTSOptimizer()

        text = """## HOOK
Look at [click here] this ML model. [PAUSE]
It achieves 95% accuracy using the sklearn API.
"""

        result = optimizer.optimize(text)

        # Visual cues removed (except PAUSE)
        assert "[click here]" not in result
        assert "[PAUSE]" in result

        # Acronyms replaced
        assert "M-L" in result
        assert "A-P-I" in result

        # Percentages optimized
        assert "95 percent" in result

        # Python terms replaced
        assert "scikit-learn" in result


class TestTTSNarrationExtraction:
    """Tests for narration file generation and segment extraction."""

    SCRIPT = """## HOOK
Have you ever wondered about data quality?
[SHOW SLIDE: Title]

## OBJECTIVE
By the end of this video, you'll understand validation.

## CONTENT
Let's look at an example.

```python
import pandas as pd
```

This code loads the library.

## SUMMARY
Today we learned about validation.
"""

    def test_generate_narration_file(self, tmp_path):
        optimizer = TTSOptimizer()
        output = tmp_path / "narration.txt"
        result = optimizer.generate_narration_file(self.SCRIPT, output)
        assert result == output
        assert output.exists()
        content = output.read_text()
        # Visual cues should be removed
        assert "[SHOW SLIDE" not in content
        # Code blocks should be removed
        assert "import pandas" not in content
        # Section headers should be removed
        assert "## HOOK" not in content

    def test_narration_file_has_pause_markers(self, tmp_path):
        optimizer = TTSOptimizer()
        output = tmp_path / "narration.txt"
        optimizer.generate_narration_file(self.SCRIPT, output)
        content = output.read_text()
        assert "[pause]" in content

    def test_narration_file_creates_parent_dirs(self, tmp_path):
        optimizer = TTSOptimizer()
        output = tmp_path / "deep" / "nested" / "narration.txt"
        optimizer.generate_narration_file(self.SCRIPT, output)
        assert output.exists()

    def test_extract_narration_segments(self):
        optimizer = TTSOptimizer()
        segments = optimizer.extract_narration_segments(self.SCRIPT)
        assert len(segments) >= 3  # HOOK, OBJECTIVE, CONTENT, SUMMARY
        types = [s["type"] for s in segments]
        assert "HOOK" in types
        assert "CONTENT" in types

    def test_segment_word_counts(self):
        optimizer = TTSOptimizer()
        segments = optimizer.extract_narration_segments(self.SCRIPT)
        for seg in segments:
            assert seg["word_count"] > 0
            assert seg["duration_seconds"] >= 10

    def test_segments_have_no_visual_cues(self):
        optimizer = TTSOptimizer()
        segments = optimizer.extract_narration_segments(self.SCRIPT)
        for seg in segments:
            assert "[SHOW SLIDE" not in seg["narration"]

    def test_segments_have_no_code_blocks(self):
        optimizer = TTSOptimizer()
        segments = optimizer.extract_narration_segments(self.SCRIPT)
        for seg in segments:
            assert "```" not in seg["narration"]
            assert "import pandas" not in seg["narration"]
