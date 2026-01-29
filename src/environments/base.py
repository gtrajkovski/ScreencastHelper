"""Base class for demo environments."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict
from pathlib import Path

from ..config import EnvironmentConfig


@dataclass
class DemoStep:
    """A single step in the demo."""
    section: str           # Section name (HOOK, CONTENT, etc.)
    narration: str         # What to say
    code: str              # Code to show/execute
    action: str            # Type of action (show, execute, highlight)
    expected_output: str   # Expected result
    pause_after: bool      # Whether to pause for ENTER
    duration_hint: float   # Estimated seconds


class BaseEnvironment(ABC):
    """Base class for all demo environments."""

    def __init__(self, config: EnvironmentConfig):
        self.config = config
        self.steps: List[DemoStep] = []

    @abstractmethod
    def generate_demo(self, script: str, code_blocks: List[Dict]) -> str:
        """Generate environment-specific demo code."""
        pass

    @abstractmethod
    def get_file_extension(self) -> str:
        """Return the file extension for this environment."""
        pass

    @abstractmethod
    def get_run_command(self, filepath: Path) -> str:
        """Return the command to run the demo."""
        pass

    @abstractmethod
    def get_setup_instructions(self) -> str:
        """Return setup instructions for this environment."""
        pass

    def export(self, output_dir: Path) -> Dict[str, Path]:
        """Export demo files to directory."""
        pass
