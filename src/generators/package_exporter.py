"""Export complete video production packages."""

import json
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .slide_generator import generate_slides_from_script
from .notebook_generator import NotebookGenerator
from .production_notes_generator import ProductionNotesGenerator
from .tts_optimizer import TTSOptimizer
from .python_demo_generator import PythonDemoGenerator
from ..parsers.script_importer import ScriptImporter


class PackageExporter:
    """Export complete video production package with all assets."""

    def export_full_package(
        self,
        project_id: str,
        project_dir: Path,
        output_dir: Path,
        video_title: str,
        raw_script: str,
    ) -> Path:
        """Generate and export a complete production package.

        Args:
            project_id: The project identifier.
            project_dir: Path to the project's data directory.
            output_dir: Where to create the package folder.
            video_title: Title used for folder and file naming.
            raw_script: The raw markdown script text.

        Returns:
            Path to the created package directory.
        """
        safe_title = re.sub(r'[^\w\s-]', '', video_title).replace(' ', '_')
        package_name = f"Video_{safe_title}"
        package_dir = output_dir / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        # Parse script once for all generators
        importer = ScriptImporter()
        script = importer._parse_markdown(raw_script)

        # Generate missing assets into project_dir, then copy to package
        self._ensure_slides(script, project_dir)
        self._ensure_notebook(script, project_dir)
        self._ensure_tts_narration(raw_script, project_dir)
        self._ensure_production_notes(script, project_dir)
        self._ensure_demo_script(script, project_dir, video_title)

        # Copy everything into the package
        self._export_script(raw_script, package_dir, package_name)
        self._export_notebook(project_dir, package_dir, package_name)
        self._export_slides(project_dir, package_dir)
        self._export_data(project_dir, package_dir)
        self._export_tts(project_dir, package_dir, package_name)
        self._export_production_notes(project_dir, package_dir)
        self._export_demo_script(project_dir, package_dir, package_name)
        self._generate_readme(package_dir, video_title)

        return package_dir

    def export_as_zip(self, package_dir: Path) -> Path:
        """Create ZIP archive from package directory.

        Args:
            package_dir: The package directory to compress.

        Returns:
            Path to the created ZIP file.
        """
        zip_path = package_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in package_dir.rglob("*"):
                if file.is_file():
                    arcname = file.relative_to(package_dir.parent)
                    zf.write(file, arcname)
        return zip_path

    # --- Asset generation helpers ---

    def _ensure_slides(self, script, project_dir: Path):
        """Generate slides if they don't exist yet."""
        slides_dir = project_dir / "slides"
        if not (slides_dir / "png").exists() or not list((slides_dir / "png").glob("*.png")):
            generate_slides_from_script(script, slides_dir)

    def _ensure_notebook(self, script, project_dir: Path):
        """Generate notebook if it doesn't exist yet."""
        nb_path = project_dir / "notebook" / "demo.ipynb"
        if not nb_path.exists():
            NotebookGenerator().generate_from_script(script, nb_path)

    def _ensure_tts_narration(self, raw_script: str, project_dir: Path):
        """Generate TTS narration file if it doesn't exist yet."""
        narration_path = project_dir / "tts_narration" / "narration.txt"
        if not narration_path.exists():
            TTSOptimizer().generate_narration_file(raw_script, narration_path)

    def _ensure_production_notes(self, script, project_dir: Path):
        """Generate production notes if they don't exist yet."""
        notes_docx = project_dir / "production_notes.docx"
        notes_md = project_dir / "production_notes.md"
        if not notes_docx.exists() and not notes_md.exists():
            ProductionNotesGenerator().generate(script, project_dir, fmt="docx")

    def _ensure_demo_script(self, script, project_dir: Path, video_title: str):
        """Generate Python demo script if it doesn't exist yet."""
        demo_path = project_dir / "demo_script" / "screencast_demo.py"
        if not demo_path.exists():
            PythonDemoGenerator().generate_from_script(
                script, project_dir / "demo_script", video_title,
            )

    # --- Copy helpers ---

    def _export_script(self, raw_script: str, package_dir: Path, name: str):
        """Export the raw script as markdown."""
        script_path = package_dir / f"{name}_Recording_Script.md"
        script_path.write_text(raw_script, encoding="utf-8")

    def _export_notebook(self, project_dir: Path, package_dir: Path, name: str):
        """Export Jupyter notebook."""
        nb_dir = package_dir / "notebook"
        nb_dir.mkdir(exist_ok=True)
        src = project_dir / "notebook" / "demo.ipynb"
        if src.exists():
            shutil.copy(src, nb_dir / f"{name}_Demo.ipynb")

    def _export_slides(self, project_dir: Path, package_dir: Path):
        """Export slide images in PNG and SVG."""
        for fmt in ("png", "svg"):
            src_dir = project_dir / "slides" / fmt
            dst_dir = package_dir / f"slides_{fmt}"
            if src_dir.exists():
                shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)

    def _export_data(self, project_dir: Path, package_dir: Path):
        """Export data files."""
        src_data = project_dir / "data"
        if src_data.exists():
            data_dir = package_dir / "data"
            data_dir.mkdir(exist_ok=True)
            for f in src_data.glob("*"):
                if f.is_file():
                    shutil.copy(f, data_dir / f.name)

    def _export_tts(self, project_dir: Path, package_dir: Path, name: str):
        """Export TTS narration file."""
        tts_dir = package_dir / "tts_narration"
        tts_dir.mkdir(exist_ok=True)
        src = project_dir / "tts_narration" / "narration.txt"
        if src.exists():
            shutil.copy(src, tts_dir / f"{name}_ElevenLabs_Narration.txt")

    def _export_production_notes(self, project_dir: Path, package_dir: Path):
        """Export production notes document."""
        for ext in ("docx", "md"):
            src = project_dir / f"production_notes.{ext}"
            if src.exists():
                shutil.copy(src, package_dir / f"production_notes.{ext}")

    def _export_demo_script(self, project_dir: Path, package_dir: Path, name: str):
        """Export Python demo script."""
        src_script = project_dir / "demo_script" / "screencast_demo.py"
        if src_script.exists():
            script_dir = package_dir / "demo_script"
            script_dir.mkdir(exist_ok=True)
            shutil.copy(src_script, script_dir / f"{name}_screencast_demo.py")
            src_readme = project_dir / "demo_script" / "README.md"
            if src_readme.exists():
                shutil.copy(src_readme, script_dir / "README.md")

    def _generate_readme(self, package_dir: Path, video_title: str):
        """Generate README with package contents."""
        readme = f"""# Video Production Package: {video_title}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Package Contents

### Recording Script
- `*_Recording_Script.md` - Markdown script with visual cues

### Jupyter Notebook
- `notebook/*_Demo.ipynb` - Demo notebook aligned to script segments
- Cells are numbered and mapped to script sections

### Slides
- `slides_png/` - Static slide images (1920x1080) for recording
- `slides_svg/` - Editable SVG versions

### TTS Narration
- `tts_narration/*_ElevenLabs_Narration.txt` - Clean text for ElevenLabs
- Visual cues removed, acronyms expanded, code terms fixed

### Production Notes
- `production_notes.docx` (or `.md`) - Recording instructions
- Pre-recording checklist, timing summary, cue legend

### Data Files
- `data/` - Sample datasets for demo

## Recording Workflow

1. Review production_notes.docx
2. Open Jupyter Notebook and clear outputs
3. Load data files into working directory
4. Record segments following script cues:
   - [SHOW SLIDE: ...] - Display slide image
   - [SWITCH TO: Jupyter Notebook] - Switch to notebook
   - [RUN CELL] - Execute notebook cell
   - [PAUSE] - Brief pause for viewer
5. Use TTS narration file with ElevenLabs if needed

## Slide Order

1. Title slide (Hook)
2. Learning Goals (Objective)
3. IVQ slide (In-Video Question)
4. Key Takeaways (Summary)
5. Next Steps (CTA)

---
Generated by ScreenCast Studio
"""
        (package_dir / "README.txt").write_text(readme, encoding="utf-8")
