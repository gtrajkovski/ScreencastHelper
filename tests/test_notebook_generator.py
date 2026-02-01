"""Tests for notebook generator."""

import json
import pytest
import nbformat
from pathlib import Path
from src.generators.notebook_generator import NotebookGenerator, GeneratedNotebook
from src.parsers.script_importer import ScriptImporter


SAMPLE_SCRIPT = """# Demo Notebook

## CONTENT
Let's load the data.

Say: "First, import pandas and load our CSV file."

```python
import pandas as pd
df = pd.read_csv("data.csv")
print(df.head())
```

Now let's analyze the results.

```python
summary = df.describe()
print(summary)
```
"""


class TestNotebookGenerator:
    """Test suite for NotebookGenerator."""

    def test_generate_notebook(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        output_path = tmp_path / "notebook" / "demo.ipynb"

        gen = NotebookGenerator()
        result = gen.generate_from_script(script, output_path)

        assert isinstance(result, GeneratedNotebook)
        assert result.filepath == output_path
        assert result.filepath.exists()
        assert result.cell_count == 2  # 2 code blocks

    def test_notebook_is_valid_nbformat(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        output_path = tmp_path / "demo.ipynb"

        gen = NotebookGenerator()
        gen.generate_from_script(script, output_path)

        nb = nbformat.read(str(output_path), as_version=4)
        nbformat.validate(nb)  # Raises if invalid

    def test_code_cells_present(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        output_path = tmp_path / "demo.ipynb"

        gen = NotebookGenerator()
        gen.generate_from_script(script, output_path)

        nb = nbformat.read(str(output_path), as_version=4)
        code_cells = [c for c in nb.cells if c.cell_type == "code"]
        assert len(code_cells) == 2
        assert "pandas" in code_cells[0].source

    def test_say_instructions_in_markdown(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        output_path = tmp_path / "demo.ipynb"

        gen = NotebookGenerator()
        gen.generate_from_script(script, output_path)

        nb = nbformat.read(str(output_path), as_version=4)
        md_cells = [c for c in nb.cells if c.cell_type == "markdown"]
        # At least the title cell + instruction cells
        assert len(md_cells) >= 1

    def test_cell_mapping(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        output_path = tmp_path / "demo.ipynb"

        gen = NotebookGenerator()
        result = gen.generate_from_script(script, output_path)

        assert len(result.cell_mapping) == 2
        assert result.cell_mapping[0]["cell_number"] == 1
        assert result.cell_mapping[1]["cell_number"] == 2

    def test_generate_cell_mapping_without_file(self):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)

        gen = NotebookGenerator()
        mapping = gen.generate_cell_mapping(script)

        assert len(mapping) == 2
        assert all("cell_number" in m for m in mapping)
        assert all("language" in m for m in mapping)

    def test_title_cell_present(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        output_path = tmp_path / "demo.ipynb"

        gen = NotebookGenerator()
        gen.generate_from_script(script, output_path)

        nb = nbformat.read(str(output_path), as_version=4)
        assert nb.cells[0].cell_type == "markdown"
        assert "Demo Notebook" in nb.cells[0].source

    def test_empty_script_no_code_cells(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown("# Empty\n\n## CONTENT\nNo code here.")
        output_path = tmp_path / "demo.ipynb"

        gen = NotebookGenerator()
        result = gen.generate_from_script(script, output_path)

        assert result.cell_count == 0
        nb = nbformat.read(str(output_path), as_version=4)
        code_cells = [c for c in nb.cells if c.cell_type == "code"]
        assert len(code_cells) == 0

    def test_notebook_kernelspec(self, tmp_path):
        importer = ScriptImporter()
        script = importer._parse_markdown(SAMPLE_SCRIPT)
        output_path = tmp_path / "demo.ipynb"

        gen = NotebookGenerator()
        gen.generate_from_script(script, output_path)

        nb = nbformat.read(str(output_path), as_version=4)
        assert nb.metadata.get("kernelspec", {}).get("name") == "python3"
