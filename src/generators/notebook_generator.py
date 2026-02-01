"""Generate Jupyter notebooks aligned to video script segments."""

import re
import nbformat
from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class NotebookCell:
    """A single notebook cell with script alignment metadata."""
    cell_type: str  # 'code' or 'markdown'
    content: str
    script_segment: str  # Which WWHAA section this maps to
    say_text: Optional[str] = None


@dataclass
class GeneratedNotebook:
    """Result of notebook generation."""
    filepath: Path
    cell_count: int
    cell_mapping: List[Dict[str, Any]] = field(default_factory=list)


class NotebookGenerator:
    """Generate Jupyter notebooks aligned to video script segments."""

    def generate_from_script(self, script, output_path: Path) -> GeneratedNotebook:
        """Generate a notebook from an ImportedScript.

        Args:
            script: An ImportedScript instance.
            output_path: Where to save the .ipynb file.

        Returns:
            GeneratedNotebook with filepath, cell count, and mapping.
        """
        nb = new_notebook()
        nb.metadata["kernelspec"] = {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        }

        cells = []

        # Title cell
        cells.append(new_markdown_cell(f"# {script.title}\n\n*Video Demo Notebook*"))

        # Add cells for each code block
        cell_number = 1
        mapping: List[Dict[str, Any]] = []
        for block in script.code_blocks:
            say_text = self._find_say_text(script, block)
            if say_text:
                md_cell = new_markdown_cell(
                    f"### Cell {cell_number}: {block['section']}\n\n"
                    f"> **Say:** *\"{say_text}\"*\n\n"
                    f"Then run the cell below:"
                )
                cells.append(md_cell)

            code_cell = new_code_cell(block["code"])
            code_cell.metadata["cell_number"] = cell_number
            code_cell.metadata["section"] = block.get("section", "")
            cells.append(code_cell)

            mapping.append({
                "cell_number": cell_number,
                "section": block.get("section", ""),
                "code_preview": block["code"][:50] + ("..." if len(block["code"]) > 50 else ""),
                "language": block.get("language", "python"),
            })
            cell_number += 1

        nb.cells = cells

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)

        return GeneratedNotebook(
            filepath=output_path,
            cell_count=cell_number - 1,
            cell_mapping=mapping,
        )

    def generate_cell_mapping(self, script) -> List[Dict[str, Any]]:
        """Generate a cell-to-script mapping table without writing a file."""
        mapping = []
        for i, block in enumerate(script.code_blocks, 1):
            mapping.append({
                "cell_number": i,
                "section": block.get("section", ""),
                "code_preview": block["code"][:50] + ("..." if len(block["code"]) > 50 else ""),
                "language": block.get("language", "python"),
            })
        return mapping

    def _find_say_text(self, script, block: Dict[str, Any]) -> Optional[str]:
        """Find the narration text associated with a code block.

        Searches the section text for 'Say:' instructions that appear
        before the code block.
        """
        for section in script.sections:
            if section["type"] != block.get("section", ""):
                continue
            text = section["text"]
            code_prefix = block["code"][:50]
            code_pos = text.find(code_prefix)
            if code_pos > 0:
                preceding = text[:code_pos]
                say_match = re.search(
                    r'Say:\s*["\']?([^"\']+)["\']?',
                    preceding, re.IGNORECASE,
                )
                if say_match:
                    return say_match.group(1).strip()

        # Fallback: use the section's narration-like text (first sentence)
        for section in script.sections:
            if section["type"] == block.get("section", ""):
                # Strip visual cues and code blocks, take first sentence
                text = re.sub(r'\[([^\]]+)\]', '', section["text"])
                text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
                text = text.strip()
                if text:
                    # First sentence or first 100 chars
                    first_sentence = re.split(r'[.!?]\s', text, maxsplit=1)[0]
                    if first_sentence and len(first_sentence) > 10:
                        return first_sentence[:150].strip()
        return None
