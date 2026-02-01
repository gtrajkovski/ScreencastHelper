"""Generate terminal-based screencast demo scripts."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any


@dataclass
class DemoSlide:
    """Represents one slide/section in the demo."""
    slide_num: str
    section_type: str  # HOOK, CONTENT, IVQ, etc.
    narration: str
    code_blocks: List[Dict[str, Any]]
    visual_elements: List[str] = field(default_factory=list)


class PythonDemoGenerator:
    """Generate terminal-based screencast demo scripts.

    Produces a runnable Python script with:
    - Typing animation effects for code
    - ANSI color-coded syntax highlighting
    - Narration prompts between sections
    - FAST_MODE toggle for testing vs recording
    - Simulated outputs (DataFrames, metrics)
    """

    KEYWORDS = {
        "import", "from", "as", "def", "class", "return", "if", "elif",
        "else", "for", "while", "in", "not", "and", "or", "is", "None",
        "True", "False", "try", "except", "finally", "with", "lambda",
    }

    def generate_from_script(
        self,
        script,
        output_dir: Path,
        video_title: str,
    ) -> Path:
        """Generate Python demo script from an ImportedScript.

        Args:
            script: An ImportedScript instance.
            output_dir: Directory for output files.
            video_title: Title of the video.

        Returns:
            Path to the generated Python script.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        slides = self._parse_script_to_slides(script)
        demo_code = self._generate_demo_script(slides, video_title)

        script_path = output_dir / "screencast_demo.py"
        script_path.write_text(demo_code, encoding="utf-8")

        self._write_readme(output_dir, video_title)

        return script_path

    def _parse_script_to_slides(self, script) -> List[DemoSlide]:
        """Convert script sections to demo slides."""
        slides: List[DemoSlide] = []
        slide_num = 1

        # Build a mapping of section -> code blocks
        section_blocks: Dict[str, List[Dict]] = {}
        for block in script.code_blocks:
            sec = block.get("section", "")
            section_blocks.setdefault(sec, []).append(block)

        for section in script.sections:
            narration = re.sub(r"\[([^\]]+)\]", "", section["text"]).strip()
            # Truncate for display in prompts
            narration_short = narration[:200]

            code_blocks = section_blocks.get(section["type"], [])

            slides.append(DemoSlide(
                slide_num=str(slide_num),
                section_type=section["type"],
                narration=narration_short,
                code_blocks=code_blocks,
                visual_elements=section.get("visual_cues", []),
            ))
            slide_num += 1

        return slides

    def _detect_output_type(self, block: Dict) -> str:
        """Detect type of output for a code block."""
        code = block.get("code", "")
        if "pd.DataFrame" in code or ".head()" in code or "df[" in code:
            return "dataframe"
        if ".fit(" in code:
            return "training"
        if ".predict" in code or "accuracy" in code:
            return "metrics"
        if "print(" in code:
            return "simple"
        return "simple"

    def _generate_demo_script(self, slides: List[DemoSlide], title: str) -> str:
        """Generate complete Python demo script."""
        parts = [self._generate_header(title)]

        for slide in slides:
            parts.append(self._generate_slide_function(slide))

        parts.append(self._generate_main_function(slides, title))

        return "\n".join(parts)

    def _generate_header(self, title: str) -> str:
        safe_title = title.replace('"', '\\"')
        return f'''#!/usr/bin/env python3
"""
{safe_title.upper()} - SCREENCAST DEMO

BEFORE RECORDING:
- Set terminal font size to 16pt
- Set terminal background to black
- Maximize terminal window

HOW IT WORKS:
- Press ENTER to advance to next screen
- Content stays on screen until you press ENTER
"""

import time
import sys
import os

# =============================================================================
# SPEED CONTROL - Set True for testing, False for recording
# =============================================================================
FAST_MODE = False


def delay(seconds):
    """Sleep only if not in fast mode."""
    if not FAST_MODE:
        time.sleep(seconds)


class Colors:
    """ANSI color codes for terminal styling."""
    RED = "\\033[91m"
    GREEN = "\\033[92m"
    YELLOW = "\\033[93m"
    BLUE = "\\033[94m"
    MAGENTA = "\\033[95m"
    CYAN = "\\033[96m"
    WHITE = "\\033[97m"
    DIM = "\\033[2m"
    BOLD = "\\033[1m"
    RESET = "\\033[0m"

    # Syntax highlighting
    KEYWORD = "\\033[94m"
    STRING = "\\033[92m"
    COMMENT = "\\033[90m"
    NUMBER = "\\033[96m"
    FUNCTION = "\\033[93m"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def clear_screen():
    """Clear screen by printing blank lines."""
    print("\\n" * 50)


def wait_for_enter(narration="", slide=""):
    """Display narration prompt and wait for Enter key."""
    clear_screen()
    print()
    print(f"{{Colors.MAGENTA}}{{'-' * 58}}{{Colors.RESET}}")
    if slide:
        print(f"{{Colors.MAGENTA}}  SLIDE {{slide}} — NARRATION:{{Colors.RESET}}")
    if narration:
        words = narration.split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 <= 54:
                line += (" " if line else "") + word
            else:
                print(f"{{Colors.WHITE}}  {{line}}{{Colors.RESET}}")
                line = word
        if line:
            print(f"{{Colors.WHITE}}  {{line}}{{Colors.RESET}}")
    print(f"{{Colors.MAGENTA}}{{'-' * 58}}{{Colors.RESET}}")
    print(f"{{Colors.DIM}}  [Press ENTER]{{Colors.RESET}}")
    input()
    clear_screen()


def print_header(text):
    """Print cyan header banner."""
    print()
    delay(0.4)
    print(f"{{Colors.CYAN}}{{'=' * 58}}{{Colors.RESET}}")
    delay(0.3)
    print(f"{{Colors.WHITE}}{{Colors.BOLD}}  {{text}}{{Colors.RESET}}")
    delay(0.3)
    print(f"{{Colors.CYAN}}{{'=' * 58}}{{Colors.RESET}}")
    print()
    delay(0.4)


def print_code(text, prefix=">>> "):
    """Print code with typing effect."""
    delay(0.2)
    if FAST_MODE:
        print(f"{{Colors.DIM}}{{prefix}}{{Colors.RESET}}{{Colors.WHITE}}{{text}}{{Colors.RESET}}")
    else:
        print(f"{{Colors.DIM}}{{prefix}}{{Colors.RESET}}", end="", flush=True)
        for char in text:
            print(char, end="", flush=True)
            delay(0.02)
        print(Colors.RESET)
    delay(0.25)


def print_output(text, color=None):
    """Print output text."""
    delay(0.2)
    c = color if color else Colors.WHITE
    print(f"{{c}}{{text}}{{Colors.RESET}}")


def run_indicator(msg="Running...", duration=0.8):
    """Show execution indicator."""
    delay(0.3)
    print(f"{{Colors.DIM}}  {{msg}}{{Colors.RESET}}")
    delay(duration)


def print_success(text):
    """Print green success message."""
    print()
    delay(0.4)
    print(f"{{Colors.GREEN}}  {{'=' * 48}}{{Colors.RESET}}")
    delay(0.3)
    print(f"{{Colors.GREEN}}  ✓ {{text}}{{Colors.RESET}}")
    delay(0.3)
    print(f"{{Colors.GREEN}}  {{'=' * 48}}{{Colors.RESET}}")
    print()


def print_dataframe(title, headers, rows):
    """Print tabular data like a DataFrame."""
    print()
    delay(0.3)
    print(f"{{Colors.WHITE}}  {{title}}{{Colors.RESET}}")
    print()
    widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    header = "  " + "  ".join(f"{{h:>{{widths[i]}}}}" for i, h in enumerate(headers))
    print(f"{{Colors.WHITE}}{{header}}{{Colors.RESET}}")
    delay(0.3)
    for row in rows:
        line = "  " + "  ".join(f"{{str(cell):>{{widths[i]}}}}" for i, cell in enumerate(row))
        print(line)
        delay(0.25)
    print()

'''

    def _generate_slide_function(self, slide: DemoSlide) -> str:
        """Generate a function for one slide."""
        func_name = f"slide_{slide.slide_num}_{slide.section_type.lower().replace(' ', '_')}"
        safe_section = slide.section_type.upper().replace('"', '\\"')

        lines = [
            f"\n# {'=' * 77}",
            f"# SLIDE {slide.slide_num}: {safe_section}",
            f"# {'=' * 77}\n",
            f"def {func_name}():",
            f'    print_header("{safe_section}")',
        ]

        for block in slide.code_blocks:
            output_type = self._detect_output_type(block)
            code_lines = block["code"].strip().split("\n")
            for code_line in code_lines:
                escaped = code_line.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'    print_code("{escaped}")')

            if output_type == "training":
                lines.append('    run_indicator("Training model...")')
                lines.append('    print_success("Model trained successfully!")')
            elif output_type == "dataframe":
                lines.append("    run_indicator()")
            elif output_type == "metrics":
                lines.append("    run_indicator()")

        lines.append("    input()  # Wait for ENTER")
        lines.append("")

        return "\n".join(lines)

    def _generate_main_function(self, slides: List[DemoSlide], title: str) -> str:
        """Generate the main function."""
        safe_title = title.replace("\\", "\\\\").replace('"', '\\"').upper()

        lines = [
            f"\n# {'=' * 77}",
            "# MAIN",
            f"# {'=' * 77}\n",
            "def main():",
            "    clear_screen()",
            "    print()",
            f"    print(f\"{{Colors.CYAN}}{{'=' * 58}}{{Colors.RESET}}\")",
            "    print()",
            f'    print(f"{{Colors.WHITE}}{{Colors.BOLD}}    {safe_title}{{Colors.RESET}}")',
            "    print()",
            f"    print(f\"{{Colors.DIM}}    Screencast Demo{{Colors.RESET}}\")",
            "    print()",
            f"    print(f\"{{Colors.CYAN}}{{'=' * 58}}{{Colors.RESET}}\")",
            "    print()",
            f"    print(f\"{{Colors.YELLOW}}  Press ENTER to advance.{{Colors.RESET}}\")",
            "    input()",
            "",
        ]

        for slide in slides:
            func_name = f"slide_{slide.slide_num}_{slide.section_type.lower().replace(' ', '_')}"
            narration_escaped = slide.narration.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")[:150]
            lines.append(f'    wait_for_enter("{narration_escaped}", "{slide.slide_num}")')
            lines.append(f"    {func_name}()")
            lines.append("")

        lines.extend([
            "    # End screen",
            "    clear_screen()",
            "    print()",
            f"    print(f\"{{Colors.GREEN}}{{'=' * 58}}{{Colors.RESET}}\")",
            "    print()",
            f"    print(f\"{{Colors.GREEN}}    ✓ SCREENCAST DEMO COMPLETE{{Colors.RESET}}\")",
            "    print()",
            f"    print(f\"{{Colors.GREEN}}{{'=' * 58}}{{Colors.RESET}}\")",
            "    print()",
            "    input()",
            "",
            "",
            'if __name__ == "__main__":',
            "    main()",
            "",
        ])

        return "\n".join(lines)

    def _write_readme(self, output_dir: Path, title: str):
        """Generate README for the demo script."""
        safe_title = title.replace('"', '\\"')
        readme = f"""# {safe_title} - Screencast Demo Script

## Usage

### Testing (Fast Mode)
```bash
# Edit screencast_demo.py and set:
FAST_MODE = True

python screencast_demo.py
```

### Recording
```bash
# Set FAST_MODE = False for proper timing
FAST_MODE = False

# Run in terminal (not IDE)
python screencast_demo.py
```

## Recording Tips

1. **Terminal Setup**
   - Font: 16pt monospace
   - Background: Black
   - Maximize window
   - Disable notifications

2. **During Recording**
   - Press ENTER to advance
   - Read narration aloud
   - Pause naturally at code blocks

3. **Post-Processing**
   - Trim dead air
   - Add audio from ElevenLabs narration file
   - Speed up typing sections if needed

---
Generated by ScreenCast Studio
"""
        (output_dir / "README.md").write_text(readme, encoding="utf-8")
