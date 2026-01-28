"""File handling utilities for ScreenCast Studio."""

import json
from pathlib import Path
from typing import Any, Dict, Optional
import yaml


class FileHandler:
    """Handle file operations for projects."""

    @staticmethod
    def load_text(filepath: Path) -> str:
        """Load text file content."""
        return filepath.read_text(encoding='utf-8')

    @staticmethod
    def save_text(filepath: Path, content: str) -> Path:
        """Save text content to file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding='utf-8')
        return filepath

    @staticmethod
    def load_json(filepath: Path) -> Dict[str, Any]:
        """Load JSON file."""
        return json.loads(filepath.read_text(encoding='utf-8'))

    @staticmethod
    def save_json(filepath: Path, data: Dict[str, Any], indent: int = 2) -> Path:
        """Save data as JSON file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json.dumps(data, indent=indent), encoding='utf-8')
        return filepath

    @staticmethod
    def load_yaml(filepath: Path) -> Dict[str, Any]:
        """Load YAML file."""
        return yaml.safe_load(filepath.read_text(encoding='utf-8'))

    @staticmethod
    def save_yaml(filepath: Path, data: Dict[str, Any]) -> Path:
        """Save data as YAML file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding='utf-8'
        )
        return filepath

    @staticmethod
    def ensure_directory(dirpath: Path) -> Path:
        """Ensure directory exists."""
        dirpath.mkdir(parents=True, exist_ok=True)
        return dirpath


class ProjectManager:
    """Manage screencast project files."""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.input_dir = self.project_dir / "input"
        self.output_dir = self.project_dir / "output"
        self.scripts_dir = self.output_dir / "scripts"
        self.demos_dir = self.output_dir / "demos"
        self.assets_dir = self.output_dir / "assets"

    def initialize(self) -> None:
        """Create project directory structure."""
        for dir_path in [
            self.input_dir,
            self.scripts_dir,
            self.demos_dir,
            self.assets_dir
        ]:
            FileHandler.ensure_directory(dir_path)

    def get_bullets_file(self) -> Optional[Path]:
        """Get the bullets input file if it exists."""
        bullets_file = self.input_dir / "bullets.txt"
        return bullets_file if bullets_file.exists() else None

    def save_script(self, content: str, filename: str = "script.md") -> Path:
        """Save generated script."""
        return FileHandler.save_text(self.scripts_dir / filename, content)

    def save_demo(self, content: str, filename: str = "demo.py") -> Path:
        """Save generated demo script."""
        return FileHandler.save_text(self.demos_dir / filename, content)

    def save_asset(self, content: str, filename: str) -> Path:
        """Save generated asset."""
        return FileHandler.save_text(self.assets_dir / filename, content)
