"""Tests for slide generator."""

import pytest
from pathlib import Path
from src.generators.slide_generator import SlideGenerator, SlideSpec, generate_slides_from_script
from src.parsers.script_importer import ScriptImporter


class TestSlideGenerator:
    """Test suite for SlideGenerator."""

    def test_init_creates_directories(self, tmp_path):
        output_dir = tmp_path / "slides"
        gen = SlideGenerator(output_dir)
        assert (output_dir / "png").exists()
        assert (output_dir / "svg").exists()

    def test_generate_title_slide(self, tmp_path):
        gen = SlideGenerator(tmp_path / "slides")
        spec = SlideSpec(slide_type="title", title="Test Video", subtitle="Module 1")
        paths = gen._generate_slide(spec, "slide_01_title")
        assert len(paths) == 2
        png = [p for p in paths if p.suffix == ".png"]
        svg = [p for p in paths if p.suffix == ".svg"]
        assert len(png) == 1
        assert len(svg) == 1
        assert png[0].exists()
        assert svg[0].exists()

    def test_generate_objective_slide(self, tmp_path):
        gen = SlideGenerator(tmp_path / "slides")
        spec = SlideSpec(
            slide_type="objective",
            title="Learning Goals",
            content=["Objective 1", "Objective 2", "Objective 3"],
        )
        paths = gen._generate_slide(spec, "slide_02_objective")
        assert len(paths) == 2
        assert all(p.exists() for p in paths)

    def test_generate_ivq_slide(self, tmp_path):
        gen = SlideGenerator(tmp_path / "slides")
        spec = SlideSpec(
            slide_type="ivq",
            title="What is the capital of France?",
            content=["London", "Paris", "Berlin", "Madrid"],
        )
        paths = gen._generate_slide(spec, "slide_03_ivq")
        assert len(paths) == 2
        assert all(p.exists() for p in paths)

    def test_generate_takeaways_slide(self, tmp_path):
        gen = SlideGenerator(tmp_path / "slides")
        spec = SlideSpec(
            slide_type="takeaways",
            title="Key Takeaways",
            content=["Point 1", "Point 2", "Point 3"],
        )
        paths = gen._generate_slide(spec, "slide_04_takeaways")
        assert all(p.exists() for p in paths)

    def test_generate_cta_slide(self, tmp_path):
        gen = SlideGenerator(tmp_path / "slides")
        spec = SlideSpec(
            slide_type="cta",
            title="Next Steps",
            content=["Try the lab exercise"],
        )
        paths = gen._generate_slide(spec, "slide_05_cta")
        assert all(p.exists() for p in paths)

    def test_generate_concept_slide(self, tmp_path):
        gen = SlideGenerator(tmp_path / "slides")
        spec = SlideSpec(
            slide_type="concept",
            title="Key Concepts",
            content=["Concept A", "Concept B"],
        )
        paths = gen._generate_slide(spec, "slide_06_concept")
        assert all(p.exists() for p in paths)

    def test_generate_all_slides(self, tmp_path):
        gen = SlideGenerator(tmp_path / "slides")
        specs = [
            SlideSpec(slide_type="title", title="Test"),
            SlideSpec(slide_type="objective", title="Goals", content=["G1"]),
        ]
        paths = gen.generate_all_slides(specs)
        assert len(paths) == 4  # 2 slides x 2 formats

    def test_slide_dimensions(self, tmp_path):
        """Verify slides are generated at reasonable dimensions."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not available")
        gen = SlideGenerator(tmp_path / "slides")
        spec = SlideSpec(slide_type="title", title="Dimension Test")
        paths = gen._generate_slide(spec, "dim_test")
        png_path = [p for p in paths if p.suffix == ".png"][0]
        img = Image.open(png_path)
        # bbox_inches='tight' trims whitespace, so dimensions are smaller
        # than 1920x1080 but should be landscape and reasonably large
        assert img.width > img.height  # landscape orientation
        assert img.width >= 1000


class TestGenerateSlidesFromScript:
    """Test the module-level helper function."""

    def test_generates_slides_from_script(self, tmp_path):
        script_text = """# Test Video

## HOOK
Opening hook text

## OBJECTIVE
- Learn objective 1
- Learn objective 2

## CONTENT
Main content here

## SUMMARY
Key takeaway one
Key takeaway two is also important

## CALL TO ACTION
Try the lab exercise next
"""
        importer = ScriptImporter()
        script = importer._parse_markdown(script_text)
        output_dir = tmp_path / "slides"
        paths = generate_slides_from_script(script, output_dir)
        # Should produce at least title + objective + takeaways + cta slides
        assert len(paths) >= 6  # At least 3 slides x 2 formats

    def test_generates_ivq_slide_when_present(self, tmp_path):
        script_text = """# Quiz Video

## HOOK
Hello

## IVQ
**Question:** What is 1+1?
A) 1
B) 2
C) 3
D) 4
**Correct Answer:** B

## CONTENT
Content here
"""
        importer = ScriptImporter()
        script = importer._parse_markdown(script_text)
        paths = generate_slides_from_script(script, tmp_path / "slides")
        filenames = [p.name for p in paths]
        ivq_slides = [f for f in filenames if "ivq" in f]
        assert len(ivq_slides) >= 1
