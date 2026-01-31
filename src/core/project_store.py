"""Project persistence layer for ScreenCast Studio v5.0."""

import json
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from .models import Project


class ProjectStore:
    """Manages project persistence on disk."""

    def __init__(self, base_dir: Path = Path("projects")):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize_id(project_id: str) -> str:
        """Sanitize project ID to prevent path traversal."""
        # Strip any path separators or parent-directory references
        sanitized = project_id.replace("/", "").replace("\\", "").replace("..", "")
        if not sanitized:
            raise ValueError("Invalid project ID")
        return sanitized

    def _project_dir(self, project_id: str) -> Path:
        safe_id = self._sanitize_id(project_id)
        return self.base_dir / safe_id

    def _project_file(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    def save(self, project: Project) -> Path:
        project_dir = self._project_dir(project.id)
        project_dir.mkdir(parents=True, exist_ok=True)

        (project_dir / "audio").mkdir(exist_ok=True)
        (project_dir / "video").mkdir(exist_ok=True)
        (project_dir / "data").mkdir(exist_ok=True)

        project.updated_at = datetime.now().isoformat()
        data = project.to_dict()

        path = self._project_file(project.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return path

    def load(self, project_id: str) -> Optional[Project]:
        path = self._project_file(project_id)
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return Project.from_dict(data)

    def list_projects(self) -> List[dict]:
        projects = []
        if not self.base_dir.exists():
            return projects

        for project_dir in self.base_dir.iterdir():
            if project_dir.is_dir():
                project_file = project_dir / "project.json"
                if project_file.exists():
                    try:
                        with open(project_file, encoding="utf-8") as f:
                            data = json.load(f)
                        projects.append({
                            "id": data["id"],
                            "title": data.get("title", "Untitled"),
                            "description": data.get("description", ""),
                            "target_duration": data.get("target_duration", 7),
                            "environment": data.get("environment", "jupyter"),
                            "segment_count": len(data.get("segments", [])),
                            "created_at": data.get("created_at", ""),
                            "updated_at": data.get("updated_at", ""),
                        })
                    except (json.JSONDecodeError, KeyError):
                        continue

        return sorted(projects, key=lambda x: x.get("updated_at", ""), reverse=True)

    def delete(self, project_id: str) -> bool:
        project_dir = self._project_dir(project_id)
        if project_dir.exists():
            shutil.rmtree(project_dir)
            return True
        return False
