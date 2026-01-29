"""Pure terminal environment for demos."""

from pathlib import Path
from typing import List, Dict

from .base import BaseEnvironment
from ..config import EnvironmentConfig


class TerminalEnvironment(BaseEnvironment):
    """Generate terminal/shell demos."""

    def get_file_extension(self) -> str:
        return ".sh"

    def get_run_command(self, filepath: Path) -> str:
        return f"bash {filepath}"

    def get_setup_instructions(self) -> str:
        return """## Terminal Demo Setup

1. Make executable: `chmod +x demo.sh`
2. Run: `./demo.sh`
3. Press ENTER to advance through each command

Recording Tips:
- Use a clean terminal (no distracting history)
- Increase font size (14-16pt)
- Use dark theme with good contrast
"""

    def generate_demo(self, script: str, code_blocks: List[Dict]) -> str:
        """Generate terminal demo script."""

        lines = [
            '#!/bin/bash',
            '# ═══════════════════════════════════════════════════════════════════',
            '# TERMINAL DEMO',
            '# Interactive demo for screencast recording',
            '# ═══════════════════════════════════════════════════════════════════',
            '',
            '# Colors',
            'RED="\\033[0;31m"',
            'GREEN="\\033[0;32m"',
            'YELLOW="\\033[1;33m"',
            'BLUE="\\033[0;34m"',
            'CYAN="\\033[0;36m"',
            'BOLD="\\033[1m"',
            'NC="\\033[0m" # No Color',
            '',
            '# Utility functions',
            'pause() {',
            '    echo ""',
            '    read -p "   [${1:-Press ENTER to continue...}]"',
            '}',
            '',
            'section() {',
            '    clear',
            '    echo ""',
            '    echo "${CYAN}═══════════════════════════════════════════════════════════${NC}"',
            '    echo "${BOLD}${YELLOW}  $1${NC}"',
            '    echo "${CYAN}═══════════════════════════════════════════════════════════${NC}"',
            '    echo ""',
            '}',
            '',
            'narration() {',
            '    echo "${BLUE}NARRATION:${NC}"',
            '    echo "$1"',
            '    echo ""',
            '}',
            '',
            'show_command() {',
            '    echo -n "${GREEN}$ ${NC}"',
            '    echo "$1"',
            '}',
            '',
            'run_command() {',
            '    show_command "$1"',
            '    echo ""',
            '    eval "$1"',
            '}',
            '',
            '# ═══════════════════════════════════════════════════════════════════',
            '# DEMO START',
            '# ═══════════════════════════════════════════════════════════════════',
            '',
            'clear',
            'echo "${BOLD}╔═══════════════════════════════════════════════════════════╗${NC}"',
            'echo "${BOLD}║           INTERACTIVE TERMINAL DEMO                       ║${NC}"',
            'echo "${BOLD}║                                                           ║${NC}"',
            'echo "${BOLD}║   Press ENTER to advance through each step                ║${NC}"',
            'echo "${BOLD}║   Press Ctrl+C to exit at any time                        ║${NC}"',
            'echo "${BOLD}╚═══════════════════════════════════════════════════════════╝${NC}"',
            '',
            'pause "Press ENTER to begin..."',
            '',
        ]

        # Add sections based on code blocks
        for i, block in enumerate(code_blocks):
            section_name = block.get("section", f"Section {i+1}")
            narration_text = block.get("narration", "")
            code = block.get("code", "")

            lines.extend([
                f'# {"="*70}',
                f'# SECTION: {section_name}',
                f'# {"="*70}',
                '',
                f'section "{section_name}"',
                '',
            ])

            if narration_text:
                safe_narration = narration_text[:200].replace('"', '\\"').replace("'", "\\'")
                lines.append(f'narration "{safe_narration}..."')
                lines.append('')

            lines.append('pause')
            lines.append('')

            # Handle the code
            for cmd in code.strip().split('\\n'):
                if cmd.strip() and not cmd.strip().startswith('#'):
                    lines.append(f'run_command "{cmd.strip()}"')
                    lines.append('pause')

            lines.append('')

        # Ending
        lines.extend([
            '# ═══════════════════════════════════════════════════════════════════',
            '# DEMO COMPLETE',
            '# ═══════════════════════════════════════════════════════════════════',
            '',
            'section "Demo Complete!"',
            'echo "${GREEN}All sections completed${NC}"',
            'echo ""',
            'echo "Thank you for watching!"',
            '',
        ])

        return '\\n'.join(lines)
