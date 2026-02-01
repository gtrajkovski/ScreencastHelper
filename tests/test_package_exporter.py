"""Tests for package exporter."""

import zipfile
import pytest
from pathlib import Path
from src.generators.package_exporter import PackageExporter


SAMPLE_SCRIPT = """# Export Test Video

## HOOK
Opening hook text here.

## OBJECTIVE
- Learn to export
- Learn to validate

## CONTENT
Main content with code.

```python
import pandas as pd
df = pd.read_csv("data.csv")
print(df.head())
```

## SUMMARY
We learned about exporting.
This is a key takeaway line.

## CALL TO ACTION
Try the practice exercise next.
"""


class TestPackageExporter:
    """Test suite for PackageExporter."""

    def test_export_creates_package_dir(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "output"

        exporter = PackageExporter()
        package_dir = exporter.export_full_package(
            project_id="test123",
            project_dir=project_dir,
            output_dir=output_dir,
            video_title="Test Video",
            raw_script=SAMPLE_SCRIPT,
        )

        assert package_dir.exists()
        assert package_dir.is_dir()

    def test_export_contains_readme(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "output"

        exporter = PackageExporter()
        package_dir = exporter.export_full_package(
            project_id="test123",
            project_dir=project_dir,
            output_dir=output_dir,
            video_title="Test Video",
            raw_script=SAMPLE_SCRIPT,
        )

        readme = package_dir / "README.txt"
        assert readme.exists()
        content = readme.read_text()
        assert "Test Video" in content

    def test_export_contains_script(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "output"

        exporter = PackageExporter()
        package_dir = exporter.export_full_package(
            project_id="test123",
            project_dir=project_dir,
            output_dir=output_dir,
            video_title="Test Video",
            raw_script=SAMPLE_SCRIPT,
        )

        script_files = list(package_dir.glob("*_Recording_Script.md"))
        assert len(script_files) == 1
        assert "HOOK" in script_files[0].read_text()

    def test_export_generates_slides(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "output"

        exporter = PackageExporter()
        package_dir = exporter.export_full_package(
            project_id="test123",
            project_dir=project_dir,
            output_dir=output_dir,
            video_title="Test Video",
            raw_script=SAMPLE_SCRIPT,
        )

        slides_png = package_dir / "slides_png"
        assert slides_png.exists()
        png_files = list(slides_png.glob("*.png"))
        assert len(png_files) >= 1

    def test_export_generates_notebook(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "output"

        exporter = PackageExporter()
        package_dir = exporter.export_full_package(
            project_id="test123",
            project_dir=project_dir,
            output_dir=output_dir,
            video_title="Test Video",
            raw_script=SAMPLE_SCRIPT,
        )

        notebook_dir = package_dir / "notebook"
        assert notebook_dir.exists()
        ipynb_files = list(notebook_dir.glob("*.ipynb"))
        assert len(ipynb_files) == 1

    def test_export_generates_tts_narration(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "output"

        exporter = PackageExporter()
        package_dir = exporter.export_full_package(
            project_id="test123",
            project_dir=project_dir,
            output_dir=output_dir,
            video_title="Test Video",
            raw_script=SAMPLE_SCRIPT,
        )

        tts_dir = package_dir / "tts_narration"
        assert tts_dir.exists()
        narration_files = list(tts_dir.glob("*Narration*"))
        assert len(narration_files) == 1

    def test_export_as_zip(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "output"

        exporter = PackageExporter()
        package_dir = exporter.export_full_package(
            project_id="test123",
            project_dir=project_dir,
            output_dir=output_dir,
            video_title="Zip Test",
            raw_script=SAMPLE_SCRIPT,
        )

        zip_path = exporter.export_as_zip(package_dir)
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert any("README.txt" in n for n in names)

    def test_export_copies_existing_data(self, tmp_path):
        project_dir = tmp_path / "project"
        data_dir = project_dir / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "sample.csv").write_text("a,b,c\n1,2,3\n")

        output_dir = tmp_path / "output"

        exporter = PackageExporter()
        package_dir = exporter.export_full_package(
            project_id="test123",
            project_dir=project_dir,
            output_dir=output_dir,
            video_title="Data Test",
            raw_script=SAMPLE_SCRIPT,
        )

        exported_data = package_dir / "data" / "sample.csv"
        assert exported_data.exists()
        assert "1,2,3" in exported_data.read_text()

    def test_export_safe_title(self, tmp_path):
        """Verify special characters in title are sanitized."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "output"

        exporter = PackageExporter()
        package_dir = exporter.export_full_package(
            project_id="test123",
            project_dir=project_dir,
            output_dir=output_dir,
            video_title="Test: Video! (v2)",
            raw_script=SAMPLE_SCRIPT,
        )

        assert package_dir.exists()
        # Folder name should not contain special chars
        assert ":" not in package_dir.name
        assert "!" not in package_dir.name
