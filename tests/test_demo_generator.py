"""Tests for demo generator."""

import pytest
from src.generators.demo_generator import DemoGenerator, DemoSection, GeneratedDemo


class TestDemoGenerator:
    """Test suite for DemoGenerator."""

    def test_parse_script_sections(self):
        """Test parsing script into sections."""
        generator = DemoGenerator()

        script = """## HOOK
This is the hook content.

## CONTENT
This is the main content.

## SUMMARY
This is the summary.
"""

        sections = generator._parse_script_sections(script)

        assert len(sections) == 3
        assert sections[0].title == "HOOK"
        assert "hook content" in sections[0].narration
        assert sections[1].title == "CONTENT"
        assert sections[2].title == "SUMMARY"

    def test_demo_section_dataclass(self):
        """Test DemoSection dataclass."""
        section = DemoSection(
            title="Test Section",
            narration="Test narration",
            code="print('test')",
            pause_message="Continue..."
        )

        assert section.title == "Test Section"
        assert section.narration == "Test narration"
        assert section.code == "print('test')"
        assert section.pause_message == "Continue..."

    def test_demo_section_default_pause(self):
        """Test DemoSection default pause message."""
        section = DemoSection(
            title="Test",
            narration="Test",
            code=""
        )

        assert section.pause_message == "Press ENTER to continue..."

    def test_extract_required_files(self):
        """Test file extraction from code."""
        generator = DemoGenerator()

        code = '''
data = pd.read_csv("data.csv")
config = load_yaml("config.yaml")
output = Path("report.html")
script = open("process.py")
'''

        files = generator._extract_required_files(code)

        assert "data.csv" in files
        assert "config.yaml" in files
        assert "report.html" in files
        assert "process.py" in files

    def test_generate_basic_demo(self):
        """Test basic demo generation."""
        generator = DemoGenerator()

        script = """## HOOK
Introduction to the demo.

## CONTENT
Main demonstration content.
"""

        demo = generator.generate(
            script=script,
            demo_requirements="Show data loading",
            title="Test Demo",
            filename="test_demo.py"
        )

        assert isinstance(demo, GeneratedDemo)
        assert "Test Demo" in demo.code
        assert "def main():" in demo.code
        assert 'if __name__ == "__main__":' in demo.code

    def test_generated_demo_has_sections(self):
        """Test that generated demo has section functions."""
        generator = DemoGenerator()

        script = """## HOOK
Hook content.

## CONTENT
Content here.
"""

        demo = generator.generate(
            script=script,
            demo_requirements="Test requirements",
            title="Test"
        )

        assert "def section_1():" in demo.code
        assert "def section_2():" in demo.code

    def test_generated_demo_has_utilities(self):
        """Test that generated demo has utility functions."""
        generator = DemoGenerator()

        script = """## HOOK
Test hook.
"""

        demo = generator.generate(
            script=script,
            demo_requirements="Test",
            title="Test"
        )

        assert "def clear_screen():" in demo.code
        assert "def pause(" in demo.code
        assert "def print_narration(" in demo.code
        assert "def print_section(" in demo.code
