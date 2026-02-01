"""Import existing video scripts from .docx or .md files."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class ImportedScript:
    """Complete imported script with parsed structure."""
    title: str
    duration_estimate: int  # minutes
    sections: List[Dict[str, Any]]
    code_blocks: List[Dict[str, Any]]
    ivq: Optional[Dict[str, Any]]
    raw_text: str
    visual_cues: List[str] = field(default_factory=list)
    expected_results: List[Dict[str, Any]] = field(default_factory=list)


class ScriptImporter:
    """Import existing video scripts from .docx or .md files."""

    SECTION_PATTERN = re.compile(
        r'##\s*(HOOK|OBJECTIVE|CONTENT|SUMMARY|CALL TO ACTION|IN-VIDEO QUESTION|IVQ)',
        re.IGNORECASE,
    )
    VISUAL_CUE_PATTERN = re.compile(r'\[([^\]]+)\]')
    CODE_BLOCK_PATTERN = re.compile(r'```(\w+)?\n(.*?)```', re.DOTALL)

    def import_docx(self, filepath: Path) -> ImportedScript:
        """Convert .docx to text and parse.

        Uses python-docx to extract paragraph text, then parses
        the combined text as markdown.
        """
        try:
            from docx import Document
        except ImportError:
            raise ImportError(
                "python-docx is required for .docx import. "
                "Install with: pip install python-docx"
            )

        doc = Document(str(filepath))
        lines = []
        for para in doc.paragraphs:
            style_name = (para.style.name or "").lower()
            text = para.text.strip()
            if not text:
                lines.append("")
                continue

            # Map Word heading styles to markdown headers
            if "heading 2" in style_name:
                lines.append(f"## {text}")
            elif "heading 1" in style_name:
                lines.append(f"# {text}")
            elif "heading 3" in style_name:
                lines.append(f"### {text}")
            elif "code" in style_name:
                lines.append(f"```python\n{text}\n```")
            else:
                lines.append(text)

        md_content = "\n".join(lines)
        return self._parse_markdown(md_content)

    def import_markdown(self, filepath: Path) -> ImportedScript:
        """Parse markdown script directly."""
        content = filepath.read_text(encoding="utf-8")
        return self._parse_markdown(content)

    # Patterns for expected outputs in narration
    EXPECTED_RESULT_PATTERNS = [
        # "accuracy of 0.923" / "accuracy is 0.923"
        (r'(\w+)\s+(?:of|is|equals?|was)\s+([\d.]+)', 'float'),
        # "Accuracy: 0.923"
        (r'(\w+):\s*([\d.]+)', 'float'),
    ]

    # Variable names to skip
    _SKIP_VARS = {
        'line', 'step', 'cell', 'version', 'python', 'slide', 'section',
        'import', 'from', 'print', 'range', 'len', 'fig', 'size',
    }

    def _parse_markdown(self, content: str) -> ImportedScript:
        """Extract sections, code blocks, visual cues, and IVQ."""
        sections = []
        code_blocks = []
        ivq = None
        all_visual_cues: List[str] = []

        # Extract all code blocks first
        for match in self.CODE_BLOCK_PATTERN.finditer(content):
            lang = match.group(1) or "python"
            code = match.group(2).strip()
            code_blocks.append({
                "language": lang,
                "code": code,
                "section": "",  # will be populated below
            })

        # Split by section headers
        parts = self.SECTION_PATTERN.split(content)

        # parts alternates: [preamble, HEADER1, body1, HEADER2, body2, ...]
        current_section = None
        code_block_idx = 0
        for i, part in enumerate(parts):
            upper = part.strip().upper()
            if upper in (
                "HOOK", "OBJECTIVE", "CONTENT", "SUMMARY", "CALL TO ACTION",
            ):
                current_section = upper
            elif upper in ("IN-VIDEO QUESTION", "IVQ"):
                # Find the next part which is the IVQ body
                if i + 1 < len(parts):
                    ivq = self._parse_ivq(parts[i + 1])
                current_section = "IVQ"
            elif current_section and current_section != "IVQ":
                text = part.strip()
                if not text:
                    continue

                visual_cues = self.VISUAL_CUE_PATTERN.findall(text)
                all_visual_cues.extend(visual_cues)

                # Tag code blocks with their section
                section_code_matches = self.CODE_BLOCK_PATTERN.findall(text)
                for lang, code in section_code_matches:
                    if code_block_idx < len(code_blocks):
                        code_blocks[code_block_idx]["section"] = current_section
                        code_block_idx += 1

                sections.append({
                    "type": current_section,
                    "text": text,
                    "visual_cues": visual_cues,
                })

        # Extract expected results from narration
        expected_results = self._extract_expected_results(content)

        return ImportedScript(
            title=self._extract_title(content),
            duration_estimate=self._estimate_duration(content),
            sections=sections,
            code_blocks=code_blocks,
            ivq=ivq,
            raw_text=content,
            visual_cues=all_visual_cues,
            expected_results=expected_results,
        )

    def _parse_ivq(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse In-Video Question section."""
        if not text or not text.strip():
            return None

        result: Dict[str, Any] = {
            "question": "",
            "options": [],
            "correct_answer": "",
            "feedback": {},
        }

        # Extract question
        q_match = re.search(
            r'\*\*Question:\*\*\s*(.+?)(?=\n[A-D]\)|\n\*\*|\Z)',
            text, re.DOTALL,
        )
        if q_match:
            result["question"] = q_match.group(1).strip()

        # Extract options A-D
        option_matches = re.findall(r'([A-D])\)\s+(.+)', text)
        for letter, option_text in option_matches:
            result["options"].append({
                "letter": letter,
                "text": option_text.strip(),
            })

        # Extract correct answer
        correct_match = re.search(r'\*\*Correct Answer:\*\*\s*([A-D])', text)
        if correct_match:
            result["correct_answer"] = correct_match.group(1)

        # Extract feedback
        feedback_matches = re.findall(r'\*\*Feedback ([A-D]):\*\*\s*(.+)', text)
        for letter, fb_text in feedback_matches:
            result["feedback"][letter] = fb_text.strip()

        if not result["question"] and not result["options"]:
            return None

        return result

    def _extract_expected_results(self, content: str) -> List[Dict[str, Any]]:
        """Extract expected output values from narration text.

        Looks for patterns like 'accuracy of 0.923' or 'Accuracy: 0.92'
        near code blocks.
        """
        results: List[Dict[str, Any]] = []
        seen_vars: set = set()

        # Strip code blocks to search only narration
        narration = self.CODE_BLOCK_PATTERN.sub('', content)

        for pattern, vtype in self.EXPECTED_RESULT_PATTERNS:
            for match in re.finditer(pattern, narration, re.IGNORECASE):
                var_name = match.group(1).lower().strip()
                value_str = match.group(2)

                if var_name in self._SKIP_VARS or var_name in seen_vars:
                    continue

                try:
                    value = float(value_str)
                except ValueError:
                    continue

                # Filter out obviously non-metric values
                if value > 10000:
                    continue

                seen_vars.add(var_name)
                results.append({
                    'variable_name': var_name,
                    'expected_value': value,
                    'value_type': vtype,
                    'context': match.group(0),
                })

        return results

    def _extract_title(self, content: str) -> str:
        """Extract title from first heading."""
        match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
        return match.group(1).strip() if match else "Untitled"

    def _estimate_duration(self, content: str) -> int:
        """Estimate duration from word count (150 WPM)."""
        # Strip code blocks and visual cues for word count
        text = self.CODE_BLOCK_PATTERN.sub("", content)
        text = self.VISUAL_CUE_PATTERN.sub("", text)
        text = re.sub(r'#+ .+', '', text)  # Remove headers
        words = len(text.split())
        return max(1, words // 150)
