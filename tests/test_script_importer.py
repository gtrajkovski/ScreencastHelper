"""Tests for script importer."""

import pytest
from pathlib import Path
from src.parsers.script_importer import ScriptImporter, ImportedScript


SAMPLE_WWHAA_SCRIPT = """# Data Validation with Python

## HOOK
Have you ever wondered how data professionals ensure data quality?
[SHOW SLIDE: Title]

## OBJECTIVE
By the end of this video, you'll be able to:
- Identify common data quality issues
- Use pandas to validate datasets
- Build automated validation pipelines

## CONTENT
Let's start by loading our dataset.

Say: "First, we'll import our libraries and load the data."

```python
import pandas as pd
df = pd.read_csv("sample_data.csv")
print(df.head())
```

Now let's check for missing values.

```python
missing = df.isnull().sum()
print(missing)
```

[SWITCH TO: Jupyter Notebook]

## IVQ
**Question:** Which pandas method detects missing values?
A) df.empty()
B) df.isnull()
C) df.missing()
D) df.na()
**Correct Answer:** B
**Feedback A:** empty() checks if the DataFrame has no rows, not missing values.
**Feedback B:** Correct! isnull() returns a boolean mask of missing values.
**Feedback C:** There is no missing() method in pandas.
**Feedback D:** There is no na() method — but isna() is an alias for isnull().

## SUMMARY
Today we learned how to validate data using pandas.
We covered missing value detection and type checking.

## CALL TO ACTION
Next, try the hands-on lab to practice data validation on your own.
"""


class TestScriptImporter:
    """Test suite for ScriptImporter."""

    def test_parse_markdown_returns_imported_script(self):
        importer = ScriptImporter()
        result = importer._parse_markdown(SAMPLE_WWHAA_SCRIPT)
        assert isinstance(result, ImportedScript)

    def test_extract_title(self):
        importer = ScriptImporter()
        result = importer._parse_markdown(SAMPLE_WWHAA_SCRIPT)
        assert result.title == "Data Validation with Python"

    def test_estimate_duration(self):
        importer = ScriptImporter()
        result = importer._parse_markdown(SAMPLE_WWHAA_SCRIPT)
        assert result.duration_estimate >= 1

    def test_parse_wwhaa_sections(self):
        importer = ScriptImporter()
        result = importer._parse_markdown(SAMPLE_WWHAA_SCRIPT)
        section_types = [s["type"] for s in result.sections]
        assert "HOOK" in section_types
        assert "OBJECTIVE" in section_types
        assert "CONTENT" in section_types
        assert "SUMMARY" in section_types
        assert "CALL TO ACTION" in section_types

    def test_extract_code_blocks(self):
        importer = ScriptImporter()
        result = importer._parse_markdown(SAMPLE_WWHAA_SCRIPT)
        assert len(result.code_blocks) == 2
        assert "pandas" in result.code_blocks[0]["code"]
        assert result.code_blocks[0]["language"] == "python"

    def test_parse_ivq(self):
        importer = ScriptImporter()
        result = importer._parse_markdown(SAMPLE_WWHAA_SCRIPT)
        assert result.ivq is not None
        assert "missing values" in result.ivq["question"]
        assert len(result.ivq["options"]) == 4
        assert result.ivq["correct_answer"] == "B"
        assert "B" in result.ivq["feedback"]

    def test_extract_visual_cues(self):
        importer = ScriptImporter()
        result = importer._parse_markdown(SAMPLE_WWHAA_SCRIPT)
        # HOOK section should have a visual cue
        hook = [s for s in result.sections if s["type"] == "HOOK"]
        assert len(hook) == 1
        assert len(hook[0]["visual_cues"]) >= 1

    def test_import_markdown_file(self, tmp_path):
        md_file = tmp_path / "test_script.md"
        md_file.write_text(SAMPLE_WWHAA_SCRIPT, encoding="utf-8")
        importer = ScriptImporter()
        result = importer.import_markdown(md_file)
        assert result.title == "Data Validation with Python"
        assert len(result.sections) >= 4

    def test_empty_script(self):
        importer = ScriptImporter()
        result = importer._parse_markdown("")
        assert result.title == "Untitled"
        assert len(result.sections) == 0

    def test_script_without_ivq(self):
        script = """# Simple Script

## HOOK
Hello world

## CONTENT
Some content here
"""
        importer = ScriptImporter()
        result = importer._parse_markdown(script)
        assert result.ivq is None

    def test_ivq_without_feedback(self):
        script = """## IVQ
**Question:** What is 2+2?
A) 3
B) 4
C) 5
D) 6
**Correct Answer:** B
"""
        importer = ScriptImporter()
        result = importer._parse_ivq(script)
        assert result is not None
        assert result["correct_answer"] == "B"
        assert len(result["options"]) == 4

    def test_code_blocks_tagged_with_section(self):
        importer = ScriptImporter()
        result = importer._parse_markdown(SAMPLE_WWHAA_SCRIPT)
        content_blocks = [b for b in result.code_blocks if b["section"] == "CONTENT"]
        assert len(content_blocks) >= 1
