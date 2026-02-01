"""Tests for Python demo generator."""

import ast
import pytest
from pathlib import Path
from src.generators.python_demo_generator import PythonDemoGenerator
from src.parsers.script_importer import ScriptImporter


SAMPLE_SCRIPT = """# ML Training Demo

## HOOK
Have you ever wanted to train a machine learning model?

## CONTENT
Let's start by importing our libraries.

```python
import pandas as pd
from sklearn.cluster import KMeans
```

Now let's load and fit the model.

```python
df = pd.read_csv("data.csv")
model = KMeans(n_clusters=3)
model.fit(df)
```

## SUMMARY
We trained a KMeans model on our dataset.
"""


class TestPythonDemoGenerator:
    """Test suite for PythonDemoGenerator."""

    def test_generates_script_file(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        gen = PythonDemoGenerator()
        path = gen.generate_from_script(script, tmp_path / "demo", "ML Training Demo")
        assert path.exists()
        assert path.name == "screencast_demo.py"

    def test_generates_readme(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        gen = PythonDemoGenerator()
        gen.generate_from_script(script, tmp_path / "demo", "ML Training Demo")
        readme = tmp_path / "demo" / "README.md"
        assert readme.exists()
        assert "ML Training Demo" in readme.read_text()

    def test_script_has_fast_mode(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        gen = PythonDemoGenerator()
        path = gen.generate_from_script(script, tmp_path / "demo", "Test")
        content = path.read_text()
        assert "FAST_MODE" in content

    def test_script_has_colors_class(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        gen = PythonDemoGenerator()
        path = gen.generate_from_script(script, tmp_path / "demo", "Test")
        content = path.read_text()
        assert "class Colors:" in content
        assert "RESET" in content

    def test_script_has_slide_functions(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        gen = PythonDemoGenerator()
        path = gen.generate_from_script(script, tmp_path / "demo", "Test")
        content = path.read_text()
        assert "def slide_" in content

    def test_script_has_main_function(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        gen = PythonDemoGenerator()
        path = gen.generate_from_script(script, tmp_path / "demo", "Test")
        content = path.read_text()
        assert "def main():" in content
        assert '__name__ == "__main__"' in content

    def test_script_has_narration_prompts(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        gen = PythonDemoGenerator()
        path = gen.generate_from_script(script, tmp_path / "demo", "Test")
        content = path.read_text()
        assert "wait_for_enter(" in content

    def test_script_has_code_blocks(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        gen = PythonDemoGenerator()
        path = gen.generate_from_script(script, tmp_path / "demo", "Test")
        content = path.read_text()
        assert "print_code(" in content

    def test_script_is_valid_python(self, tmp_path):
        """Test that the generated script is syntactically valid Python."""
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        gen = PythonDemoGenerator()
        path = gen.generate_from_script(script, tmp_path / "demo", "Test")
        content = path.read_text()
        # This will raise SyntaxError if invalid
        ast.parse(content)

    def test_detect_output_type_dataframe(self):
        gen = PythonDemoGenerator()
        assert gen._detect_output_type({"code": "df.head()"}) == "dataframe"
        assert gen._detect_output_type({"code": "pd.DataFrame(data)"}) == "dataframe"

    def test_detect_output_type_training(self):
        gen = PythonDemoGenerator()
        assert gen._detect_output_type({"code": "model.fit(X)"}) == "training"

    def test_detect_output_type_simple(self):
        gen = PythonDemoGenerator()
        assert gen._detect_output_type({"code": "x = 1"}) == "simple"

    def test_empty_script_still_generates(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown("# Empty\n\n## CONTENT\nNo code.")
        gen = PythonDemoGenerator()
        path = gen.generate_from_script(script, tmp_path / "demo", "Empty Demo")
        assert path.exists()
        content = path.read_text()
        ast.parse(content)  # Should still be valid Python
