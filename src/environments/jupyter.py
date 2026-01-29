"""Jupyter notebook environment for demos."""

import json
import re
from pathlib import Path
from typing import List, Dict

from .base import BaseEnvironment
from ..config import EnvironmentConfig


class JupyterEnvironment(BaseEnvironment):
    """Generate Jupyter notebook demos."""

    def get_file_extension(self) -> str:
        return ".ipynb"

    def get_run_command(self, filepath: Path) -> str:
        return f"jupyter notebook {filepath}"

    def get_setup_instructions(self) -> str:
        return """## Jupyter Notebook Demo Setup

1. Install Jupyter: `pip install jupyter`
2. Open the notebook: `jupyter notebook demo.ipynb`
3. Run cells one at a time with Shift+Enter
4. Pause for narration between cells

Recording Tips:
- Zoom browser to 125% for readability
- Use dark theme for less eye strain
- Clear all outputs before recording
- Run cells slowly, one at a time
"""

    def generate_demo(self, script: str, code_blocks: List[Dict]) -> str:
        """Generate a Jupyter notebook from script and code."""

        cells = []

        # Title cell
        cells.append(self._markdown_cell([
            "# Interactive Demo\\n",
            "\\n",
            "Run each cell with Shift+Enter, pausing for narration.\\n"
        ]))

        # Parse script sections and interleave with code
        sections = self._parse_sections(script)
        code_idx = 0

        for section_name, section_content in sections.items():
            # Section header
            preview = section_content[:200] + "..." if len(section_content) > 200 else section_content
            cells.append(self._markdown_cell([
                f"## {section_name}\\n",
                "\\n",
                f"*{preview}*\\n"
            ]))

            # Add relevant code blocks for this section
            while code_idx < len(code_blocks):
                block = code_blocks[code_idx]
                if block.get("section", "").upper() == section_name.upper():
                    cells.append(self._code_cell(block["code"].split("\\n")))
                    code_idx += 1
                else:
                    break

        # Add remaining code blocks
        for block in code_blocks[code_idx:]:
            cells.append(self._code_cell(block["code"].split("\\n")))

        # Build notebook structure
        notebook = {
            "cells": cells,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
                "language_info": {
                    "name": "python",
                    "version": "3.11.0"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 5
        }

        return json.dumps(notebook, indent=2)

    def _markdown_cell(self, source: List[str]) -> Dict:
        """Create a markdown cell."""
        return {
            "cell_type": "markdown",
            "metadata": {},
            "source": source
        }

    def _code_cell(self, source: List[str]) -> Dict:
        """Create a code cell."""
        formatted = [line + "\\n" for line in source[:-1]] if len(source) > 1 else []
        if source:
            formatted.append(source[-1] if len(source) == 1 else source[-1])

        return {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": formatted
        }

    def _parse_sections(self, script: str) -> Dict[str, str]:
        """Parse script into sections."""
        sections = {}
        pattern = r'## (HOOK|OBJECTIVE|CONTENT|SUMMARY|CALL TO ACTION)\\n(.*?)(?=## |$)'

        for match in re.finditer(pattern, script, re.DOTALL):
            sections[match.group(1)] = match.group(2).strip()

        return sections

    def generate_interactive_runner(self) -> str:
        """Generate a Python script that runs the notebook interactively."""

        return '''#!/usr/bin/env python3
"""
Interactive Jupyter notebook runner for screencast recording.
Runs cells one at a time with ENTER prompts.
"""

import sys

def pause(msg="Press ENTER to run next cell..."):
    input(f"\\n   [{msg}]")

def run_notebook_interactive(notebook_path):
    """Run notebook cells one at a time."""
    import json

    with open(notebook_path) as f:
        nb = json.load(f)

    print("=" * 60)
    print("INTERACTIVE NOTEBOOK RUNNER")
    print("=" * 60)
    print(f"\\nNotebook: {notebook_path}")
    print(f"Cells: {len(nb['cells'])}")
    print("\\nPress ENTER to execute each cell.")
    print("=" * 60)

    for i, cell in enumerate(nb['cells']):
        print(f"\\n--- Cell {i+1}/{len(nb['cells'])} ({cell['cell_type']}) ---")

        source = ''.join(cell.get('source', []))
        print(source[:500])

        pause()

        if cell['cell_type'] == 'code':
            print("\\n[Executing...]")
            try:
                exec(source)
            except Exception as e:
                print(f"[Error: {e}]")

    print("\\n" + "=" * 60)
    print("NOTEBOOK COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    notebook_path = sys.argv[1] if len(sys.argv) > 1 else "demo.ipynb"
    run_notebook_interactive(notebook_path)
'''
