#!/usr/bin/env python3
"""Migrate v4 projects to v5 schema.

Reads v4 project JSON files from the projects/ directory and converts them
to the v5 Project/Segment model using ProjectStore.

Usage:
    python scripts/migrate_v4_to_v5.py [--dry-run]
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.models import Project, Segment, SegmentType, SegmentStatus
from src.core.project_store import ProjectStore


def convert_v4_project(v4_data: dict) -> Project:
    """Convert a v4 project dict to a v5 Project."""
    project = Project()

    # Map v4 fields to v5
    project.id = v4_data.get('id', project.id)
    project.title = v4_data.get('name', v4_data.get('title', 'Untitled'))
    project.raw_script = v4_data.get('script_raw', v4_data.get('raw_script', ''))
    project.description = v4_data.get('description', '')

    # Config fields
    config = v4_data.get('config', {})
    project.target_duration = config.get('duration_minutes', 5)
    project.environment = config.get('environment', 'jupyter')
    project.audience_level = v4_data.get('audience_level', 'intermediate')
    project.style = v4_data.get('style', 'tutorial')

    # Timestamps
    project.created_at = v4_data.get('created', v4_data.get('created_at', project.created_at))
    project.updated_at = v4_data.get('modified', v4_data.get('updated_at', project.updated_at))

    # Convert segments
    v4_segments = v4_data.get('segments', [])
    for i, v4_seg in enumerate(v4_segments):
        seg = Segment()
        seg.id = v4_seg.get('id', seg.id)
        seg.section = v4_seg.get('section', '')
        seg.title = v4_seg.get('title', '')
        seg.narration = v4_seg.get('narration', '')
        seg.order = i

        # Type mapping
        seg_type = v4_seg.get('type', 'slide')
        if seg_type == 'screencast' or seg_type == 'notebook':
            seg.type = SegmentType.SCREENCAST
        elif seg_type == 'ivq':
            seg.type = SegmentType.IVQ
        else:
            seg.type = SegmentType.SLIDE

        # Visual cues (v4 uses list, v5 uses single string)
        visual_cues = v4_seg.get('visual_cues', [])
        if visual_cues:
            seg.visual_cue = ' | '.join(visual_cues)

        # Code from cells
        cells = v4_seg.get('cells', [])
        code_parts = []
        for cell in cells:
            if cell.get('type') == 'code' and cell.get('content'):
                code_parts.append(cell['content'])
        if code_parts:
            seg.code = '\n\n'.join(code_parts)
        elif v4_seg.get('code'):
            seg.code = v4_seg['code']

        # Duration
        seg.duration_estimate = v4_seg.get('duration_seconds', v4_seg.get('duration_estimate'))

        # Audio/video
        seg.audio_path = v4_seg.get('audio_path')
        seg.video_path = v4_seg.get('video_path')
        seg.recorded_duration = v4_seg.get('recorded_duration')

        # IVQ fields
        if seg.type == SegmentType.IVQ:
            seg.question = v4_seg.get('question')
            seg.options = v4_seg.get('options')
            seg.correct_answer = v4_seg.get('correct_answer')
            seg.feedback = v4_seg.get('feedback')

        project.segments.append(seg)

    # Datasets
    project.datasets = v4_data.get('datasets', [])

    return project


def migrate_all(projects_dir: Path, dry_run: bool = False):
    """Migrate all v4 projects in the directory."""
    if not projects_dir.exists():
        print(f"Projects directory not found: {projects_dir}")
        return

    store = ProjectStore(projects_dir)
    migrated = 0
    skipped = 0
    errors = 0

    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue

        json_file = project_dir / 'project.json'
        if not json_file.exists():
            continue

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Skip if already v5 (has schema_version)
            if data.get('schema_version', 0) >= 1:
                print(f"  SKIP {project_dir.name} (already v5)")
                skipped += 1
                continue

            project = convert_v4_project(data)
            print(f"  MIGRATE {project_dir.name} -> {project.title} ({len(project.segments)} segments)")

            if not dry_run:
                store.save(project)
                migrated += 1
            else:
                migrated += 1

        except Exception as e:
            print(f"  ERROR {project_dir.name}: {e}")
            errors += 1

    print(f"\nMigration complete: {migrated} migrated, {skipped} skipped, {errors} errors")
    if dry_run:
        print("(DRY RUN — no changes written)")


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    projects_path = Path(__file__).resolve().parent.parent / 'projects'
    print(f"Migrating v4 projects in: {projects_path}")
    if dry_run:
        print("DRY RUN mode — no changes will be written\n")
    migrate_all(projects_path, dry_run=dry_run)
