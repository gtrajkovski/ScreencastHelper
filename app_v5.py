"""ScreenCast Studio v5.0 — Unified screencast production tool.

Consolidates v2 (TUI+data tools), v3 (Web+TTS), and v4 (Web+Recording)
into a single comprehensive application with:
- Canonical Project/Segment data model
- AI script generation & improvement
- TTS audio generation (Edge TTS)
- Timeline synchronization
- Quality checks
- Export (folder + ZIP)
- Text selection AI editing
- Environment recommendation
- Dataset generation
- Browser recording (MediaRecorder)
"""

import ast
import asyncio
import io
import json
import os
import re
import shutil
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import (Flask, jsonify, render_template, request,
                   send_file, redirect, url_for)

load_dotenv()

from src.config import Config
from src.ai.client import AIClient
from src.core.models import Project, Segment, SegmentType, SegmentStatus
from src.core.project_store import ProjectStore
from src.core.parser import parse_script_to_segments
from src.generators.v4_script_generator import generate_script as ai_generate_script
from src.generators.v4_code_generator import generate_code as ai_generate_code
from src.generators.tts_audio_generator import TTSAudioGenerator
from src.generators.timeline_generator import TimelineGenerator
from src.parsers.script_importer import ScriptImporter
from src.generators.slide_generator import generate_slides_from_script
from src.generators.notebook_generator import NotebookGenerator
from src.generators.production_notes_generator import ProductionNotesGenerator
from src.generators.tts_optimizer import TTSOptimizer
from src.generators.package_exporter import PackageExporter
from src.generators.python_demo_generator import PythonDemoGenerator
from src.ai.script_improver import ScriptImprover
from src.generators.dataset_generator import (
    ScriptResultExtractor, DatasetGenerator, DatasetValidator, DatasetAuditor,
)
from src.recording.models import (
    RecordingSession, RecordingMode, TeleprompterSettings, RehearsalResult,
)
from src.recording.session_generator import RecordingSessionGenerator

app = Flask(__name__,
            template_folder='templates_v5',
            static_folder='static_v5',
            static_url_path='/static')

project_store = ProjectStore(Path('projects'))
ai_client = AIClient()

# Demo recording state (singleton — one recording at a time)
demo_recorder = {
    "active": False,
    "project_id": None,
    "ffmpeg_process": None,
    "demo_process": None,
    "output_path": None,
    "start_time": None,
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def sanitize_filename(name: str) -> str:
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')[:50] or 'untitled'


def safe_filename(name: str) -> str:
    """Sanitize a filename to prevent path traversal."""
    # Use only the basename and strip any path separators
    base = Path(name).name
    if not base or base.startswith('.'):
        raise ValueError(f"Invalid filename: {name}")
    return base


def project_to_api(project: Project) -> dict:
    """Convert Project to API-compatible dict (for legacy template compat)."""
    d = project.to_dict()
    # Legacy v4 compat fields
    d['name'] = d['title']
    d['script_raw'] = d['raw_script']
    d['config'] = {
        'duration_minutes': d['target_duration'],
        'voice': Config.TTS_VOICE,
        'theme': 'dark',
        'resolution': [1920, 1080],
        'fps': 30,
    }
    # Convert segments to legacy format for templates
    legacy_segments = []
    for seg in project.segments:
        ls = {
            'id': seg.id,
            'type': seg.type.value,
            'section': seg.section,
            'title': seg.title,
            'narration': seg.narration,
            'visual_cues': [seg.visual_cue] if seg.visual_cue else [],
            'duration_seconds': seg.duration_estimate or 30,
            'environment': project.environment,
            'cells': [],
            'code': seg.code,
        }
        if seg.code:
            ls['cells'] = [{
                'id': 'cell_1',
                'type': 'code',
                'content': seg.code,
                'output': None,
                'execution_count': 1,
            }]
        legacy_segments.append(ls)
    d['segments'] = legacy_segments
    return d


# ============================================================================
# PAGE ROUTES
# ============================================================================

@app.route('/')
def index():
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/workspace/<project_id>')
def workspace(project_id):
    project = project_store.load(project_id)
    if not project:
        return redirect(url_for('dashboard'))
    return render_template('workspace.html', project=project_to_api(project))


@app.route('/player/<project_id>')
def player_page(project_id):
    project = project_store.load(project_id)
    if not project:
        return redirect(url_for('dashboard'))
    return render_template('player.html', project=project_to_api(project))


@app.route('/recorder/<project_id>')
def recorder_page(project_id):
    project = project_store.load(project_id)
    if not project:
        return redirect(url_for('dashboard'))
    return render_template('segment_recorder.html', project=project_to_api(project))


@app.route('/studio/<project_id>')
def recording_studio_page(project_id):
    project = project_store.load(project_id)
    if not project:
        return redirect(url_for('dashboard'))
    return render_template('recording_studio.html', project=project_to_api(project))


# ============================================================================
# PROJECT MANAGEMENT API
# ============================================================================

@app.route('/api/projects', methods=['GET'])
def list_projects():
    projects = project_store.list_projects()
    return jsonify(projects)


@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.json or {}
    title = data.get('name', data.get('title', 'Untitled Project'))
    project = Project(title=title)

    if data.get('topic'):
        project.title = data['topic']
    if data.get('duration_minutes'):
        project.target_duration = int(data['duration_minutes'])
    if data.get('environment'):
        project.environment = data['environment']
    if data.get('audience_level'):
        project.audience_level = data['audience_level']

    project_store.save(project)
    return jsonify(project_to_api(project)), 201


@app.route('/api/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify(project_to_api(project))


@app.route('/api/projects/<project_id>', methods=['PUT'])
def update_project(project_id):
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.json or {}
    if 'name' in data or 'title' in data:
        project.title = data.get('name', data.get('title', project.title))
    if 'script_raw' in data:
        project.raw_script = data['script_raw']
    if 'raw_script' in data:
        project.raw_script = data['raw_script']
    if 'description' in data:
        project.description = data['description']
    if 'target_duration' in data:
        project.target_duration = int(data['target_duration'])
    if 'environment' in data:
        project.environment = data['environment']
    if 'audience_level' in data:
        project.audience_level = data['audience_level']
    if 'style' in data:
        project.style = data['style']
    if 'config' in data:
        cfg = data['config']
        if 'duration_minutes' in cfg:
            project.target_duration = int(cfg['duration_minutes'])
        if 'voice' in cfg:
            pass  # voice stored per-request, not on project

    # If segments sent as legacy format, update
    if 'segments' in data:
        new_segments = []
        for s in data['segments']:
            if isinstance(s, dict):
                try:
                    seg_type = SegmentType(s.get('type', 'slide'))
                except ValueError:
                    seg_type = SegmentType.SLIDE
                seg = Segment(
                    id=s.get('id', ''),
                    type=seg_type,
                    section=s.get('section', ''),
                    title=s.get('title', ''),
                    narration=s.get('narration', ''),
                    visual_cue=s.get('visual_cues', [''])[0] if s.get('visual_cues') else s.get('visual_cue', ''),
                    code=s.get('code'),
                    duration_estimate=s.get('duration_seconds'),
                )
                new_segments.append(seg)
        project.segments = new_segments

    project_store.save(project)
    return jsonify(project_to_api(project))


@app.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    if project_store.delete(project_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Project not found'}), 404


@app.route('/api/projects/<project_id>/segments', methods=['GET'])
def get_segments(project_id):
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify({'segments': [s.to_dict() for s in project.segments]})


@app.route('/api/projects/<project_id>/segments/<segment_id>', methods=['PUT'])
def update_segment(project_id, segment_id):
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    seg = next((s for s in project.segments if s.id == segment_id), None)
    if not seg:
        return jsonify({'error': 'Segment not found'}), 404

    data = request.json or {}
    for field in ('title', 'narration', 'visual_cue', 'code', 'section'):
        if field in data:
            setattr(seg, field, data[field])
    if 'duration_estimate' in data:
        seg.duration_estimate = float(data['duration_estimate'])
    if 'status' in data:
        try:
            seg.status = SegmentStatus(data['status'])
        except ValueError:
            return jsonify({'error': f'Invalid status: {data["status"]}'}), 400

    seg.updated_at = datetime.now().isoformat()
    project_store.save(project)
    return jsonify(seg.to_dict())


@app.route('/api/projects/<project_id>/parse', methods=['POST'])
def parse_project_script(project_id):
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.json or {}
    script_text = data.get('script_text', project.raw_script)

    if not script_text:
        return jsonify({'error': 'No script text available'}), 400

    project.raw_script = script_text
    project.segments = parse_script_to_segments(script_text)
    project_store.save(project)

    api_proj = project_to_api(project)
    return jsonify({'success': True, 'segments': api_proj['segments']})


# ============================================================================
# CONTENT GENERATION API
# ============================================================================

@app.route('/api/generate/script', methods=['POST'])
def generate_script():
    data = request.json or {}
    topic = data.get('topic', '')
    if not topic:
        return jsonify({'error': 'Topic is required'}), 400

    result = ai_generate_script(
        ai_client=ai_client,
        topic=topic,
        duration_minutes=int(data.get('duration_minutes', 5)),
        style=data.get('style', 'tutorial'),
        environment=data.get('environment', 'jupyter'),
        audience=data.get('audience', 'intermediate'),
        learning_objectives=data.get('learning_objectives'),
        sample_code=data.get('sample_code'),
        notes=data.get('notes'),
        course_name=data.get('course_name'),
        lesson_number=data.get('lesson_number'),
        video_number=data.get('video_number'),
        format_type=data.get('format_type'),
    )

    if result['success']:
        return jsonify(result)
    return jsonify({'error': result['error']}), 500


@app.route('/api/generate/code', methods=['POST'])
def generate_code():
    data = request.json or {}
    description = data.get('description', '')
    if not description:
        return jsonify({'error': 'Description is required'}), 400

    result = ai_generate_code(
        ai_client=ai_client,
        description=description,
        language=data.get('language', 'python'),
        context=data.get('context'),
        environment=data.get('environment', 'jupyter'),
        include_output=data.get('include_output', True),
    )

    if result['success']:
        return jsonify(result)
    return jsonify({'error': result['error']}), 500


@app.route('/api/parse/script', methods=['POST'])
def parse_script():
    data = request.json or {}
    script_text = data.get('script_text', '')
    project_id = data.get('project_id')

    if not script_text:
        return jsonify({'error': 'script_text is required'}), 400

    segments = parse_script_to_segments(script_text)

    # Convert to legacy format for API response
    legacy = []
    for seg in segments:
        ls = {
            'id': seg.id,
            'type': seg.type.value,
            'section': seg.section,
            'title': seg.title,
            'narration': seg.narration,
            'visual_cues': [seg.visual_cue] if seg.visual_cue else [],
            'duration_seconds': seg.duration_estimate or 30,
            'environment': 'jupyter',
            'cells': [],
        }
        if seg.code:
            ls['cells'] = [{'id': 'cell_1', 'type': 'code',
                           'content': seg.code, 'output': None,
                           'execution_count': 1}]
        legacy.append(ls)

    if project_id:
        project = project_store.load(project_id)
        if project:
            project.raw_script = script_text
            project.segments = segments
            project_store.save(project)

    return jsonify({'success': True, 'segments': legacy})


# ============================================================================
# AI HELPERS API
# ============================================================================

SEGMENT_IMPROVE_PROMPTS = {
    'shorten': "Rewrite this script segment to be 20-30% shorter while keeping all key information. Maintain the same tone and format.",
    'expand': "Expand this script segment with more detail, examples, or explanation. Add 20-30% more content. Keep the same tone.",
    'fix_tone': "Rewrite this script segment to be more conversational and engaging. Use first-person where appropriate. Avoid academic tone.",
    'simplify': "Simplify the language in this script segment. Use shorter sentences and simpler words. Keep technical accuracy.",
    'improve_code_explanation': 'Improve the narration around the code in this segment. Explain WHAT the code does and WHY each line matters.',
    'add_output': "Add realistic **OUTPUT:** blocks after each code cell showing what the code would produce when run.",
    'fix_code': "Fix any syntax errors in the Python code blocks. Ensure all code is valid and would actually run.",
    'add_comments': "Add clear, helpful comments to the code blocks explaining what each section does.",
    'add_visual_cue': "Add [SCREEN: ...] visual cues to indicate what should be shown on screen during this segment.",
    'improve_transition': 'Improve the transition into and out of this segment. Add connecting phrases.',
    'add_pause': "Add **[PAUSE]** markers after important outputs or concepts.",
    'balance_ivq_options': "Rewrite the IVQ options so they are all similar in length.",
    'improve_ivq_feedback': "Improve the feedback for each IVQ option. Explain WHY each wrong answer is wrong.",
    'make_ivq_harder': "Make this IVQ question more challenging. Require deeper understanding.",
    'make_ivq_easier': "Make this IVQ question easier. Focus on basic understanding.",
}

SEGMENT_IMPROVE_SYSTEM = """You are an expert instructional designer improving a screencast \
video script segment. Return ONLY the improved segment in the exact same markdown format. \
Preserve all structure markers like ### headings, **[RUN CELL]** markers, **NARRATION:** blocks, \
**OUTPUT:** blocks, [SCREEN: ...] cues, and code blocks. Do not add explanations outside the segment."""


@app.route('/api/ai/improve-segment', methods=['POST'])
def improve_segment():
    data = request.json or {}
    segment_text = data.get('segment_text', '')
    action = data.get('action', '')
    custom_instruction = data.get('custom_instruction', '')

    if not segment_text:
        return jsonify({'error': 'segment_text is required'}), 400
    if not action:
        return jsonify({'error': 'action is required'}), 400

    instruction = SEGMENT_IMPROVE_PROMPTS.get(action, custom_instruction)
    if action == 'custom':
        instruction = custom_instruction
    if not instruction:
        return jsonify({'error': 'Unknown action or empty custom instruction'}), 400

    user_prompt = f"""{instruction}

SEGMENT TO IMPROVE:
---
{segment_text}
---

Return ONLY the improved segment in the same format."""

    try:
        improved = ai_client.generate(SEGMENT_IMPROVE_SYSTEM, user_prompt)
        return jsonify({'success': True, 'improved_segment': improved, 'action': action})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# TEXT SELECTION AI EDITING
# ============================================================================

SELECTION_EDIT_SYSTEM = """You are an expert editor for screencast video scripts. \
You will receive a selected text fragment and an editing instruction. \
Return ONLY the improved version of the selected text. \
Do not add explanations, preamble, or wrap in quotes. Just the replacement text. \
Preserve any markers like **[RUN CELL]**, **[PAUSE]**, [SCREEN: ...], **NARRATION:**, **OUTPUT:**."""

SELECTION_EDIT_PROMPTS = {
    'improve': 'Improve the clarity, flow, and engagement of this text.',
    'shorten': 'Make this text 30-40% shorter while preserving meaning.',
    'expand': 'Expand this text with more detail and examples. Add 30-50% more content.',
    'rewrite': 'Completely rewrite this text with the same meaning but different wording.',
    'fix_grammar': 'Fix all grammar, spelling, and punctuation errors.',
    'simplify': 'Simplify the language. Use shorter sentences and common words.',
    'fix_code': 'Fix any code errors (syntax, logic) in this text. Ensure valid Python.',
    'add_comments': 'Add helpful code comments to the code in this selection.',
    'add_output': 'Add realistic **OUTPUT:** blocks showing what this code would produce.',
    'optimize': 'Optimize this code for readability and best practices.',
}


@app.route('/api/ai/edit-selection', methods=['POST'])
def edit_selection():
    data = request.json or {}
    selected_text = data.get('selected_text', '')
    action = data.get('action', '')
    custom_instruction = data.get('custom_instruction', '')
    full_script = data.get('full_script', '')

    if not selected_text:
        return jsonify({'error': 'selected_text is required'}), 400
    if not action:
        return jsonify({'error': 'action is required'}), 400

    instruction = SELECTION_EDIT_PROMPTS.get(action, custom_instruction)
    if action == 'custom':
        instruction = custom_instruction
    if not instruction:
        return jsonify({'error': 'Unknown action or empty instruction'}), 400

    context_hint = ''
    if full_script:
        context_hint = (
            "\n\nFOR CONTEXT, here is the surrounding script "
            "(do NOT return this, only return the edited selection):\n---\n"
            + full_script[:2000] + "\n---\n"
        )

    user_prompt = f"""{instruction}

SELECTED TEXT TO EDIT:
---
{selected_text}
---
{context_hint}
Return ONLY the replacement text."""

    try:
        result = ai_client.generate(SELECTION_EDIT_SYSTEM, user_prompt)
        return jsonify({'success': True, 'edited_text': result, 'action': action})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# CODE VALIDATION API
# ============================================================================

@app.route('/api/validate-all-code', methods=['POST'])
def validate_all_code():
    data = request.json or {}
    script_text = data.get('script_text', '')
    if not script_text:
        return jsonify({'error': 'script_text is required'}), 400

    code_blocks = re.findall(r'```(?:python)?\n([\s\S]*?)```', script_text)
    results = []
    for i, block in enumerate(code_blocks):
        block = block.strip()
        try:
            ast.parse(block)
            results.append({'index': i, 'valid': True, 'code_preview': block[:80], 'error': None})
        except SyntaxError as e:
            results.append({
                'index': i, 'valid': False,
                'code_preview': block[:80],
                'error': f'Line {e.lineno}: {e.msg}'
            })

    return jsonify({
        'success': True,
        'all_valid': all(r['valid'] for r in results),
        'total_blocks': len(results),
        'invalid_count': sum(1 for r in results if not r['valid']),
        'results': results,
    })


# ============================================================================
# QUALITY CHECK API
# ============================================================================

@app.route('/api/projects/<project_id>/quality-check', methods=['GET'])
def quality_check(project_id):
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    issues = {}
    script = project.raw_script

    # Structure check
    structure_issues = []
    required = ['## HOOK', '## OBJECTIVE', '## CONTENT', '## IVQ', '## SUMMARY', '## CTA']
    for section in required:
        if section not in script and section.replace('## ', '### ') not in script:
            structure_issues.append({
                'severity': 'error',
                'message': f'Missing section: {section}',
                'suggestion': f'Add {section} section to your script',
                'auto_fixable': False,
            })
    issues['structure'] = structure_issues

    # Timing check
    timing_issues = []
    word_count = len(script.split())
    est_minutes = word_count / 150
    target = project.target_duration
    if est_minutes > target * 1.2:
        timing_issues.append({
            'severity': 'warning',
            'message': f'Script is ~{est_minutes:.1f} min, target is {target} min (too long)',
            'suggestion': 'Consider shortening CONTENT section',
            'auto_fixable': False,
        })
    elif est_minutes < target * 0.7:
        timing_issues.append({
            'severity': 'warning',
            'message': f'Script is ~{est_minutes:.1f} min, target is {target} min (too short)',
            'suggestion': 'Consider expanding CONTENT section with more examples',
            'auto_fixable': False,
        })
    issues['timing'] = timing_issues

    # Code check
    code_issues = []
    code_blocks = re.findall(r'```(?:python)?\n([\s\S]*?)```', script)
    for i, block in enumerate(code_blocks):
        try:
            ast.parse(block.strip())
        except SyntaxError as e:
            code_issues.append({
                'severity': 'error',
                'message': f'Code block {i+1}: syntax error at line {e.lineno}: {e.msg}',
                'suggestion': 'Fix the Python syntax error',
                'auto_fixable': False,
            })
    issues['code'] = code_issues

    # Clarity check
    clarity_issues = []
    paragraphs = script.split('\n\n')
    for i, para in enumerate(paragraphs):
        words = para.split()
        if len(words) > 100:
            clarity_issues.append({
                'severity': 'warning',
                'message': f'Long paragraph ({len(words)} words)',
                'suggestion': 'Break into smaller paragraphs or add [PAUSE] markers',
                'auto_fixable': False,
            })
    issues['clarity'] = clarity_issues

    # Engagement check
    engagement_issues = []
    if '[PAUSE]' not in script and '**[PAUSE]**' not in script:
        engagement_issues.append({
            'severity': 'info',
            'message': 'No [PAUSE] markers found',
            'suggestion': 'Add [PAUSE] markers after key outputs to let viewers absorb information',
            'auto_fixable': False,
        })
    screen_cues = re.findall(r'\[SCREEN:', script)
    if len(screen_cues) < 3:
        engagement_issues.append({
            'severity': 'info',
            'message': f'Only {len(screen_cues)} visual cues found',
            'suggestion': 'Add more [SCREEN: ...] cues for visual direction',
            'auto_fixable': False,
        })
    issues['engagement'] = engagement_issues

    # IVQ check
    ivq_issues = []
    if '## IVQ' not in script and '### IVQ' not in script and 'IN-VIDEO' not in script.upper():
        ivq_issues.append({
            'severity': 'error',
            'message': 'No IVQ section found',
            'suggestion': 'Add an in-video question section',
            'auto_fixable': False,
        })
    else:
        if not re.search(r'[A-D]\)', script):
            ivq_issues.append({
                'severity': 'warning',
                'message': 'IVQ section missing answer options (A-D)',
                'suggestion': 'Add multiple choice options A) through D)',
                'auto_fixable': False,
            })
        if 'Correct Answer' not in script:
            ivq_issues.append({
                'severity': 'warning',
                'message': 'IVQ missing correct answer indicator',
                'suggestion': 'Add **Correct Answer:** line',
                'auto_fixable': False,
            })
    issues['ivq'] = ivq_issues

    # Accessibility check
    accessibility_issues = []
    issues['accessibility'] = accessibility_issues

    # Technical accuracy (placeholder - would need AI)
    issues['technical_accuracy'] = []

    total_issues = sum(len(v) for v in issues.values())
    errors = sum(1 for v in issues.values() for i in v if i['severity'] == 'error')
    warnings = sum(1 for v in issues.values() for i in v if i['severity'] == 'warning')

    return jsonify({
        'success': True,
        'total_issues': total_issues,
        'errors': errors,
        'warnings': warnings,
        'issues': issues,
    })


# ============================================================================
# SCRIPT SCORING & IMPROVEMENT API
# ============================================================================

@app.route('/api/projects/<project_id>/score-script', methods=['POST'])
def score_script(project_id):
    """Score the project script using the 0-100 rubric."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    try:
        improver = ScriptImprover(ai_client)
        score = improver.score_script(project.raw_script)
        return jsonify({'success': True, **score.to_dict()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<project_id>/fix-issue', methods=['POST'])
def fix_issue(project_id):
    """Fix a single script issue by re-scoring and matching issue ID."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.json or {}
    issue_id = data.get('issue_id')
    if not issue_id:
        return jsonify({'error': 'issue_id is required'}), 400

    try:
        improver = ScriptImprover(ai_client)

        # Re-score to find the issue
        score = improver.score_script(project.raw_script)
        issue = next((i for i in score.issues if i.id == issue_id), None)

        if not issue:
            return jsonify({'error': 'Issue not found'}), 404

        # Apply fix
        updated_script, explanation = improver.fix_issue(project.raw_script, issue)

        # Save
        project.raw_script = updated_script
        project.segments = parse_script_to_segments(updated_script)
        project_store.save(project)

        # Re-score
        new_score = improver.score_script(updated_script)

        return jsonify({
            'success': True,
            'explanation': explanation,
            'old_score': score.total,
            'new_score': new_score.total,
            'remaining_issues': len(new_score.issues),
            'updated_script': updated_script,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<project_id>/fix-all-issues', methods=['POST'])
def fix_all_issues(project_id):
    """Iteratively fix all script issues until target score is reached."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.json or {}
    target_score = int(data.get('target_score', 95))
    max_iterations = int(data.get('max_iterations', 5))

    try:
        improver = ScriptImprover(ai_client)

        initial_score = improver.score_script(project.raw_script)

        updated_script, history = improver.fix_all_issues(
            project.raw_script,
            max_iterations=max_iterations,
            target_score=target_score,
        )

        # Save
        project.raw_script = updated_script
        project.segments = parse_script_to_segments(updated_script)
        project_store.save(project)

        final_score = improver.score_script(updated_script)

        return jsonify({
            'success': True,
            'initial_score': initial_score.total,
            'final_score': final_score.total,
            'iterations': len([h for h in history if h.get('iteration') != 'final']),
            'history': history,
            'remaining_issues': len(final_score.issues),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# EXPORT API
# ============================================================================

def extract_code_cells(script_text: str) -> str:
    code_blocks = re.findall(r'```(?:python)?\n([\s\S]*?)```', script_text)
    lines = []
    for i, block in enumerate(code_blocks):
        lines.append(f'# --- Cell {i + 1} ---')
        lines.append(block.strip())
        lines.append('')
    return '\n'.join(lines)


def create_jupyter_notebook(script_text: str):
    try:
        import nbformat
        nb = nbformat.v4.new_notebook()
        parts = re.split(r'(```(?:python)?\n[\s\S]*?```)', script_text)
        for part in parts:
            code_match = re.match(r'```(?:python)?\n([\s\S]*?)```', part)
            if code_match:
                nb.cells.append(nbformat.v4.new_code_cell(code_match.group(1).strip()))
            else:
                text = part.strip()
                if text:
                    text = re.sub(r'\*\*\[(RUN CELL|TYPE|SHOW|PAUSE)\]\*\*', '', text)
                    text = re.sub(r'\[SCREEN:[^\]]*\]', '', text)
                    if text.strip():
                        nb.cells.append(nbformat.v4.new_markdown_cell(text.strip()))
        return nb
    except ImportError:
        return None


@app.route('/api/projects/<project_id>/export', methods=['POST'])
def export_project(project_id):
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.json or {}
    output_folder = data.get('output_folder', '')
    options = data.get('options', {})

    if not output_folder:
        return jsonify({'error': 'output_folder is required'}), 400

    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    exported = []
    script_raw = project.raw_script
    safe_name = sanitize_filename(project.title)

    if options.get('script', True) and script_raw:
        f = output_path / f'{safe_name}.md'
        f.write_text(script_raw, encoding='utf-8')
        exported.append(str(f))

    if options.get('code', False) and script_raw:
        code_content = extract_code_cells(script_raw)
        if code_content.strip():
            f = output_path / f'{safe_name}.py'
            f.write_text(code_content, encoding='utf-8')
            exported.append(str(f))

    if options.get('notebook', False) and script_raw:
        nb = create_jupyter_notebook(script_raw)
        if nb:
            import nbformat
            f = output_path / f'{safe_name}.ipynb'
            with open(f, 'w', encoding='utf-8') as fh:
                nbformat.write(nb, fh)
            exported.append(str(f))

    if options.get('audio', False):
        audio_dir = project_store._project_dir(project_id) / 'audio'
        if audio_dir.exists():
            out_audio = output_path / 'audio'
            out_audio.mkdir(exist_ok=True)
            for mp3 in audio_dir.glob('*.mp3'):
                dest = out_audio / mp3.name
                shutil.copy2(str(mp3), str(dest))
                exported.append(str(dest))

    return jsonify({'success': True, 'exported_files': exported, 'count': len(exported)})


@app.route('/api/projects/<project_id>/export-zip', methods=['POST'])
def export_project_zip(project_id):
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.json or {}
    options = data.get('options', {})
    script_raw = project.raw_script
    safe_name = sanitize_filename(project.title)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        if options.get('script', True) and script_raw:
            zf.writestr(f'{safe_name}/{safe_name}.md', script_raw)
        if options.get('code', False) and script_raw:
            code_content = extract_code_cells(script_raw)
            if code_content.strip():
                zf.writestr(f'{safe_name}/{safe_name}.py', code_content)
        if options.get('notebook', False) and script_raw:
            nb = create_jupyter_notebook(script_raw)
            if nb:
                import nbformat
                zf.writestr(f'{safe_name}/{safe_name}.ipynb', nbformat.writes(nb))
        if options.get('audio', False):
            audio_dir = project_store._project_dir(project_id) / 'audio'
            if audio_dir.exists():
                for mp3 in audio_dir.glob('*.mp3'):
                    zf.write(str(mp3), f'{safe_name}/audio/{mp3.name}')

    buffer.seek(0)
    return send_file(buffer, mimetype='application/zip', as_attachment=True,
                     download_name=f'{safe_name}.zip')


@app.route('/api/browse-folders', methods=['GET'])
def browse_folders():
    base = request.args.get('path', '.')
    base_path = Path(base).resolve()
    if not base_path.exists() or not base_path.is_dir():
        return jsonify({'error': 'Invalid path'}), 400

    folders = []
    try:
        for entry in sorted(base_path.iterdir()):
            if entry.is_dir() and not entry.name.startswith('.'):
                folders.append({'name': entry.name, 'path': str(entry)})
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403

    return jsonify({
        'current': str(base_path),
        'parent': str(base_path.parent) if base_path.parent != base_path else None,
        'folders': folders,
    })


@app.route('/api/create-folder', methods=['POST'])
def create_folder():
    data = request.json or {}
    folder_path = data.get('path', '')
    if not folder_path:
        return jsonify({'error': 'path is required'}), 400
    try:
        Path(folder_path).mkdir(parents=True, exist_ok=True)
        return jsonify({'success': True, 'path': folder_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# AUDIO GENERATION API
# ============================================================================

@app.route('/api/audio/generate/<segment_id>', methods=['POST'])
def generate_segment_audio(segment_id):
    data = request.json or {}
    project_id = data.get('project_id')
    voice = data.get('voice', Config.TTS_VOICE)
    rate = data.get('rate', Config.TTS_RATE)
    pitch = data.get('pitch', Config.TTS_PITCH)

    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400

    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    seg = next((s for s in project.segments if s.id == segment_id), None)
    if not seg:
        return jsonify({'error': f'Segment {segment_id} not found'}), 404

    narration = seg.narration
    if not narration.strip():
        return jsonify({'error': 'Segment has no narration text'}), 400

    for old, new in Config.TTS_REPLACEMENTS.items():
        narration = narration.replace(old, new)

    audio_dir = project_store._project_dir(project_id) / 'audio'
    audio_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(audio_dir / f'segment_{segment_id}.mp3')

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        tts = TTSAudioGenerator(voice=voice, rate=rate, pitch=pitch)
        result = loop.run_until_complete(
            tts.generate_segment(0, seg.section, narration, output_path)
        )

        seg.audio_path = output_path
        seg.recorded_duration = result.duration_seconds
        project_store.save(project)

        return jsonify({
            'success': True,
            'segment_id': segment_id,
            'duration_seconds': result.duration_seconds,
            'file_size_bytes': result.file_size_bytes,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        loop.close()


@app.route('/api/audio/generate-all', methods=['POST'])
def generate_all_audio():
    data = request.json or {}
    project_id = data.get('project_id')
    voice = data.get('voice', Config.TTS_VOICE)

    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400

    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    if not project.segments:
        return jsonify({'error': 'No segments to generate audio for'}), 400

    audio_dir = project_store._project_dir(project_id) / 'audio'
    audio_dir.mkdir(parents=True, exist_ok=True)

    results = []
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        tts = TTSAudioGenerator(voice=voice)

        for seg in project.segments:
            narration = seg.narration
            if not narration.strip():
                continue
            for old, new_val in Config.TTS_REPLACEMENTS.items():
                narration = narration.replace(old, new_val)

            output_path = str(audio_dir / f'segment_{seg.id}.mp3')
            result = loop.run_until_complete(
                tts.generate_segment(0, seg.section, narration, output_path)
            )
            seg.audio_path = output_path
            seg.recorded_duration = result.duration_seconds
            results.append({
                'segment_id': seg.id,
                'duration_seconds': result.duration_seconds,
                'file_size_bytes': result.file_size_bytes,
            })

        project_store.save(project)

        total_duration = sum(r['duration_seconds'] for r in results)
        return jsonify({
            'success': True,
            'segments_generated': len(results),
            'total_duration_seconds': total_duration,
            'results': results,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        loop.close()


@app.route('/api/audio/<segment_id>')
def serve_audio(segment_id):
    project_id = request.args.get('project_id')
    if not project_id:
        return jsonify({'error': 'project_id query param required'}), 400

    try:
        safe_seg = safe_filename(f'segment_{segment_id}.mp3')
    except ValueError:
        return jsonify({'error': 'Invalid segment ID'}), 400

    audio_path = project_store._project_dir(project_id) / 'audio' / safe_seg
    if not audio_path.exists():
        return jsonify({'error': 'Audio not found'}), 404
    return send_file(str(audio_path), mimetype='audio/mpeg')


# ============================================================================
# TTS VOICES
# ============================================================================

@app.route('/api/voices')
def list_voices():
    try:
        voices = TTSAudioGenerator.list_voices_sync()
        return jsonify({'success': True, 'voices': voices})
    except Exception:
        return jsonify({
            'success': True,
            'voices': [
                {"id": "en-US-AriaNeural", "name": "Aria", "language": "en-US", "gender": "Female"},
                {"id": "en-US-JennyNeural", "name": "Jenny", "language": "en-US", "gender": "Female"},
                {"id": "en-US-GuyNeural", "name": "Guy", "language": "en-US", "gender": "Male"},
                {"id": "en-GB-SoniaNeural", "name": "Sonia", "language": "en-GB", "gender": "Female"},
                {"id": "en-GB-RyanNeural", "name": "Ryan", "language": "en-GB", "gender": "Male"},
            ]
        })


# ============================================================================
# TIMELINE API
# ============================================================================

@app.route('/api/projects/<project_id>/timeline', methods=['GET'])
def get_project_timeline(project_id):
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    timeline_segments = []
    current_time = 0.0

    for seg in project.segments:
        duration = seg.recorded_duration or seg.duration_estimate or 30.0
        timeline_segments.append({
            'id': seg.id,
            'title': seg.title,
            'section': seg.section,
            'start_time': current_time,
            'duration': duration,
            'end_time': current_time + duration,
            'narration': seg.narration,
            'visual_cue': seg.visual_cue,
            'code': seg.code,
            'audio_path': seg.audio_path,
        })
        current_time += duration

    return jsonify({
        'total_duration': current_time,
        'segments': timeline_segments,
    })


@app.route('/api/timeline/generate/<segment_id>', methods=['POST'])
def generate_timeline(segment_id):
    data = request.json or {}
    project_id = data.get('project_id')
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400

    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    seg = next((s for s in project.segments if s.id == segment_id), None)
    if not seg:
        return jsonify({'error': f'Segment {segment_id} not found'}), 404

    audio_duration = seg.recorded_duration or seg.duration_estimate or 30

    adapted = {
        'id': seg.id,
        'type': 'notebook' if seg.type == SegmentType.SCREENCAST else 'slide',
        'cells': [],
        'slide_content': {'bullets': []},
        'code_cells': [],
    }

    if seg.code:
        adapted['code_cells'] = [{'code': seg.code, 'output': '', 'id': 'cell_1'}]
        adapted['cells'] = [{'id': 'cell_1', 'type': 'code', 'content': seg.code}]

    gen = TimelineGenerator()
    timeline = gen.generate(adapted, audio_duration)

    events = []
    for e in timeline.events:
        events.append({
            'time_ms': int(e.time * 1000),
            'type': e.action,
            'data': e.params,
        })

    return jsonify({
        'segment_id': segment_id,
        'total_duration_ms': int(timeline.total_duration * 1000),
        'events': events,
    })


@app.route('/api/timeline/<segment_id>')
def get_timeline(segment_id):
    project_id = request.args.get('project_id')
    if not project_id:
        return jsonify({'error': 'project_id query param required'}), 400

    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    seg = next((s for s in project.segments if s.id == segment_id), None)
    if not seg:
        return jsonify({'error': f'Segment {segment_id} not found'}), 404

    audio_duration = seg.recorded_duration or seg.duration_estimate or 30

    adapted = {
        'id': seg.id,
        'type': 'notebook' if seg.type == SegmentType.SCREENCAST else 'slide',
        'cells': [],
        'slide_content': {'bullets': []},
        'code_cells': [],
    }

    if seg.code:
        adapted['code_cells'] = [{'code': seg.code, 'output': '', 'id': 'cell_1'}]
        adapted['cells'] = [{'id': 'cell_1', 'type': 'code', 'content': seg.code}]

    gen = TimelineGenerator()
    timeline = gen.generate(adapted, audio_duration)

    events = []
    for e in timeline.events:
        events.append({
            'time_ms': int(e.time * 1000),
            'type': e.action,
            'data': e.params,
        })

    return jsonify({
        'segment_id': segment_id,
        'total_duration_ms': int(timeline.total_duration * 1000),
        'events': events,
    })


# ============================================================================
# ENVIRONMENT RECOMMENDATION API
# ============================================================================

ENV_RECOMMEND_SYSTEM = """You are an expert instructional designer. Analyze the screencast topic \
and recommend the best demo environment. Return ONLY valid JSON with no other text."""


@app.route('/api/recommend-environment', methods=['POST'])
def recommend_environment():
    data = request.json or {}
    topic = data.get('topic', '')
    demo_type = data.get('demo_type', 'general')
    audience = data.get('audience', 'intermediate')
    requirements = data.get('requirements', '')

    if not topic:
        return jsonify({'error': 'topic is required'}), 400

    prompt = f"""Analyze this screencast topic and recommend the best environment.

Topic: {topic}
Demo Type: {demo_type}
Audience: {audience}
Requirements: {requirements}

Environments available:
- jupyter: Interactive notebooks, data visualization, step-by-step execution
- terminal: CLI tools, system commands, shell scripting
- vscode: IDE features, debugging, file management
- ipython: Quick interactive Python, REPL exploration
- pycharm: Professional IDE, refactoring, project-based

Return JSON:
{{"recommended": "environment_name", "confidence": "high|medium|low", "reason": "2-3 sentence explanation", "alternatives": ["env1", "env2"]}}"""

    try:
        response = ai_client.generate(ENV_RECOMMEND_SYSTEM, prompt)
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            result = json.loads(json_match.group())
            return jsonify({'success': True, **result})
        return jsonify({'success': True, 'recommended': 'jupyter', 'confidence': 'low',
                       'reason': 'Could not parse AI response', 'alternatives': ['terminal', 'vscode']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# DATA ANALYSIS & GENERATION API
# ============================================================================

DATA_ANALYZE_SYSTEM = """You are an expert data scientist. Analyze the screencast requirements \
and determine what datasets are needed for the demo. Return ONLY valid JSON."""


@app.route('/api/projects/<project_id>/analyze-data', methods=['POST'])
def analyze_data(project_id):
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.json or {}
    demo_requirements = data.get('demo_requirements', project.raw_script[:2000])

    prompt = f"""Analyze this screencast and determine what datasets are needed.

Script/Requirements:
{demo_requirements}

Return JSON array of dataset configs:
[{{"name": "dataset_name", "filename": "file.csv", "rows": 100, "description": "what it contains",
"columns": [{{"name": "col_name", "dtype": "int|float|str|date|category|bool", "generator": "sequential|random|faker.name|faker.email|category", "params": {{}}}}]}}]"""

    try:
        response = ai_client.generate(DATA_ANALYZE_SYSTEM, prompt)
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            configs = json.loads(json_match.group())
            return jsonify({'success': True, 'datasets': configs})
        return jsonify({'success': True, 'datasets': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<project_id>/generate-datasets', methods=['POST'])
def generate_datasets(project_id):
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.json or {}
    configs = data.get('configs', [])

    if not configs:
        return jsonify({'error': 'configs is required'}), 400

    data_dir = project_store._project_dir(project_id) / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        import pandas as pd
        import numpy as np
        from faker import Faker
        fake = Faker()
        Faker.seed(42)
        np.random.seed(42)

        results = []
        for config in configs:
            rows = config.get('rows', 100)
            columns = config.get('columns', [])
            df_data = {}

            for col in columns:
                name = col['name']
                dtype = col.get('dtype', 'str')
                gen = col.get('generator', 'random')
                params = col.get('params', {})

                if gen == 'sequential':
                    df_data[name] = list(range(1, rows + 1))
                elif gen == 'random':
                    low = params.get('min', 0)
                    high = params.get('max', 100)
                    if dtype == 'float':
                        df_data[name] = np.random.uniform(low, high, rows).round(2)
                    else:
                        df_data[name] = np.random.randint(low, high, rows)
                elif gen == 'category':
                    choices = params.get('choices', ['A', 'B', 'C'])
                    weights = params.get('weights')
                    if weights:
                        df_data[name] = np.random.choice(choices, rows, p=weights)
                    else:
                        df_data[name] = np.random.choice(choices, rows)
                elif gen == 'bool':
                    prob = params.get('probability', 0.5)
                    df_data[name] = np.random.random(rows) < prob
                elif gen.startswith('faker.'):
                    method = gen.split('.', 1)[1]
                    faker_fn = getattr(fake, method, fake.name)
                    df_data[name] = [faker_fn() for _ in range(rows)]
                else:
                    df_data[name] = [f'{name}_{i}' for i in range(rows)]

            df = pd.DataFrame(df_data)
            filename = config.get('filename', f'{config["name"]}.csv')
            filepath = data_dir / filename
            df.to_csv(filepath, index=False)

            preview = df.head(5).to_string()
            results.append({
                'name': config['name'],
                'filename': filename,
                'path': str(filepath),
                'rows': len(df),
                'columns': list(df.columns),
                'preview': preview,
            })

        project.datasets = results
        project_store.save(project)

        return jsonify({'success': True, 'datasets': results})
    except ImportError as e:
        return jsonify({'error': f'Missing dependency: {e}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<project_id>/datasets', methods=['GET'])
def get_datasets(project_id):
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify({'datasets': project.datasets})


@app.route('/api/data/<project_id>/<filename>')
def serve_data(project_id, filename):
    try:
        safe_name = safe_filename(filename)
    except ValueError:
        return jsonify({'error': 'Invalid filename'}), 400
    filepath = project_store._project_dir(project_id) / 'data' / safe_name
    if not filepath.exists():
        return jsonify({'error': 'File not found'}), 404
    return send_file(str(filepath), mimetype='text/csv')


# ============================================================================
# DATASET RESULT ALIGNMENT
# ============================================================================

@app.route('/api/projects/<project_id>/analyze-script-data', methods=['POST'])
def analyze_script_data(project_id):
    """Extract code blocks and expected results from script."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    try:
        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(project.raw_script or '')
        return jsonify({
            'success': True,
            'code_blocks': [b.to_dict() for b in blocks],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<project_id>/generate-aligned-dataset', methods=['POST'])
def generate_aligned_dataset(project_id):
    """AI-generate a dataset for a specific code block that produces expected results."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.json or {}
    block_id = data.get('code_block_id')
    num_rows = data.get('num_rows', 100)

    if not block_id:
        return jsonify({'error': 'code_block_id is required'}), 400

    try:
        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(project.raw_script or '')
        block = next((b for b in blocks if b.id == block_id), None)
        if not block:
            return jsonify({'error': f'Code block {block_id} not found'}), 404

        generator = DatasetGenerator(ai_client)
        df = generator.generate_for_code_block(block, num_rows=num_rows)

        # Save to project data dir
        data_dir = project_store._project_dir(project_id) / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)

        filename = block.input_datasets[0] if block.input_datasets else f'{block_id}.csv'
        filepath = data_dir / filename
        df.to_csv(filepath, index=False)

        # Update project datasets
        if not project.datasets:
            project.datasets = []
        project.datasets.append({
            'name': block_id,
            'filename': filename,
            'rows': len(df),
            'columns': list(df.columns),
            'aligned': True,
            'code_block_id': block_id,
        })
        project_store.save(project)

        return jsonify({
            'success': True,
            'filename': filename,
            'rows': len(df),
            'columns': list(df.columns),
            'preview': df.head(5).to_string(),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<project_id>/datasets/<dataset_name>/validate', methods=['POST'])
def validate_dataset(project_id, dataset_name):
    """Run code against a dataset and check expected results."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    try:
        import pandas as pd

        safe_name = safe_filename(dataset_name)
    except ValueError:
        return jsonify({'error': 'Invalid dataset name'}), 400

    try:
        data_dir = project_store._project_dir(project_id) / 'data'
        filepath = data_dir / safe_name
        if not filepath.exists():
            return jsonify({'error': 'Dataset file not found'}), 404

        df = pd.read_csv(filepath)

        # Find matching code block
        req = request.json or {}
        block_id = req.get('code_block_id')

        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(project.raw_script or '')
        block = next((b for b in blocks if b.id == block_id), None) if block_id else None

        if not block:
            return jsonify({'error': 'code_block_id is required or not found'}), 400

        validator = DatasetValidator()
        result = validator.validate(block, {'df': df})

        return jsonify({'success': True, 'validation': result.to_dict()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<project_id>/datasets/<dataset_name>/audit', methods=['GET'])
def audit_dataset(project_id, dataset_name):
    """Quality checks on a dataset."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    try:
        import pandas as pd

        safe_name = safe_filename(dataset_name)
    except ValueError:
        return jsonify({'error': 'Invalid dataset name'}), 400

    try:
        data_dir = project_store._project_dir(project_id) / 'data'
        filepath = data_dir / safe_name
        if not filepath.exists():
            return jsonify({'error': 'Dataset file not found'}), 404

        df = pd.read_csv(filepath)
        auditor = DatasetAuditor()
        audit = auditor.audit(df, dataset_name)

        return jsonify({'success': True, 'audit': audit.to_dict()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<project_id>/datasets/<dataset_name>/finalize', methods=['POST'])
def finalize_dataset(project_id, dataset_name):
    """Mark a dataset as production-ready."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    try:
        safe_name = safe_filename(dataset_name)
    except ValueError:
        return jsonify({'error': 'Invalid dataset name'}), 400

    try:
        data_dir = project_store._project_dir(project_id) / 'data'
        filepath = data_dir / safe_name
        if not filepath.exists():
            return jsonify({'error': 'Dataset file not found'}), 404

        # Update dataset status in project
        if project.datasets:
            for ds in project.datasets:
                if ds.get('filename') == safe_name:
                    ds['finalized'] = True
                    break
        project_store.save(project)

        return jsonify({'success': True, 'finalized': safe_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<project_id>/datasets/<dataset_name>/download', methods=['GET'])
def download_dataset(project_id, dataset_name):
    """Download a dataset as CSV."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    try:
        safe_name = safe_filename(dataset_name)
    except ValueError:
        return jsonify({'error': 'Invalid dataset name'}), 400

    filepath = project_store._project_dir(project_id) / 'data' / safe_name
    if not filepath.exists():
        return jsonify({'error': 'File not found'}), 404

    return send_file(
        str(filepath),
        mimetype='text/csv',
        as_attachment=True,
        download_name=safe_name,
    )


# ============================================================================
# DEMO RECORDING
# ============================================================================

@app.route('/api/projects/<project_id>/record-demo', methods=['POST'])
def start_record_demo(project_id):
    """Start FFmpeg screen capture and launch demo script in a terminal."""
    if demo_recorder['active']:
        return jsonify({'error': 'A demo recording is already in progress'}), 400

    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    from src.services.recording_service import start_screen_capture

    # Check demo script exists
    demo_dir = project_store._project_dir(project_id) / 'demo_script'
    demo_script = demo_dir / 'screencast_demo.py'
    if not demo_script.exists():
        return jsonify({
            'error': 'Demo script not found. Generate it first via /generate-demo-script.'
        }), 400

    data = request.json or {}
    width = int(data.get('width', 1920))
    height = int(data.get('height', 1080))
    offset_x = int(data.get('offset_x', 0))
    offset_y = int(data.get('offset_y', 0))
    fps = int(data.get('fps', 30))

    # Prepare output path
    rec_dir = project_store._project_dir(project_id) / 'recordings'
    rec_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = rec_dir / f'demo_{timestamp}.mp4'

    # Start FFmpeg screen capture
    ffmpeg_proc, err = start_screen_capture(
        str(output_path), width=width, height=height,
        offset_x=offset_x, offset_y=offset_y, fps=fps,
    )
    if not ffmpeg_proc:
        return jsonify({'error': f'Failed to start screen capture: {err}'}), 500

    # Launch demo script in a visible terminal window
    try:
        if os.name == 'nt':
            demo_proc = subprocess.Popen(
                ['cmd', '/c', 'start', 'Demo Recording', 'py', '-3', 'screencast_demo.py'],
                cwd=str(demo_dir),
            )
        else:
            # Linux/macOS fallback
            terminal = shutil.which('gnome-terminal') or shutil.which('xterm')
            if terminal and 'gnome-terminal' in terminal:
                demo_proc = subprocess.Popen(
                    [terminal, '--', 'python3', 'screencast_demo.py'],
                    cwd=str(demo_dir),
                )
            elif terminal:
                demo_proc = subprocess.Popen(
                    [terminal, '-e', 'python3 screencast_demo.py'],
                    cwd=str(demo_dir),
                )
            else:
                demo_proc = subprocess.Popen(
                    ['python3', 'screencast_demo.py'],
                    cwd=str(demo_dir),
                )
    except Exception as e:
        # Stop FFmpeg if demo launch fails
        from src.services.recording_service import stop_screen_capture
        stop_screen_capture(ffmpeg_proc)
        return jsonify({'error': f'Failed to launch demo terminal: {e}'}), 500

    demo_recorder['active'] = True
    demo_recorder['project_id'] = project_id
    demo_recorder['ffmpeg_process'] = ffmpeg_proc
    demo_recorder['demo_process'] = demo_proc
    demo_recorder['output_path'] = str(output_path)
    demo_recorder['start_time'] = time.time()

    return jsonify({
        'success': True,
        'output_path': str(output_path),
        'message': 'Recording started. Press ENTER in the demo terminal to advance slides.',
    })


@app.route('/api/projects/<project_id>/record-demo/stop', methods=['POST'])
def stop_record_demo(project_id):
    """Stop demo recording — gracefully stop FFmpeg and terminate demo."""
    if not demo_recorder['active']:
        return jsonify({'error': 'No demo recording in progress'}), 400

    if demo_recorder['project_id'] != project_id:
        return jsonify({'error': 'Recording belongs to a different project'}), 400

    from src.services.recording_service import stop_screen_capture

    # Stop FFmpeg
    stop_screen_capture(demo_recorder['ffmpeg_process'])

    # Terminate demo process if still running
    demo_proc = demo_recorder['demo_process']
    if demo_proc and demo_proc.poll() is None:
        try:
            demo_proc.terminate()
        except Exception:
            pass

    duration = round(time.time() - demo_recorder['start_time'], 1)
    output_path = demo_recorder['output_path']

    # Reset state
    demo_recorder['active'] = False
    demo_recorder['project_id'] = None
    demo_recorder['ffmpeg_process'] = None
    demo_recorder['demo_process'] = None
    demo_recorder['output_path'] = None
    demo_recorder['start_time'] = None

    if Path(output_path).exists():
        size_mb = round(Path(output_path).stat().st_size / (1024 * 1024), 2)
        return jsonify({
            'success': True,
            'filename': Path(output_path).name,
            'path': output_path,
            'duration_seconds': duration,
            'size_mb': size_mb,
        })

    return jsonify({'error': 'Recording file was not created'}), 500


@app.route('/api/projects/<project_id>/record-demo/status', methods=['GET'])
def record_demo_status(project_id):
    """Poll demo recording status."""
    if not demo_recorder['active'] or demo_recorder['project_id'] != project_id:
        return jsonify({
            'active': False,
            'project_id': None,
            'elapsed_seconds': 0,
            'output_path': None,
        })

    elapsed = round(time.time() - demo_recorder['start_time'], 1)

    # Check if FFmpeg is still running
    ffmpeg_alive = (
        demo_recorder['ffmpeg_process'] is not None
        and demo_recorder['ffmpeg_process'].poll() is None
    )

    return jsonify({
        'active': demo_recorder['active'],
        'project_id': demo_recorder['project_id'],
        'elapsed_seconds': elapsed,
        'output_path': demo_recorder['output_path'],
        'ffmpeg_alive': ffmpeg_alive,
    })


# ============================================================================
# FFMPEG STATUS
# ============================================================================

@app.route('/api/system/ffmpeg-status')
def ffmpeg_status():
    from src.services.recording_service import is_ffmpeg_available, get_ffmpeg_version
    available = is_ffmpeg_available()
    version = get_ffmpeg_version() if available else None
    return jsonify({'available': available, 'version': version})


# ============================================================================
# UPLOAD RECORDING
# ============================================================================

@app.route('/api/recordings/upload', methods=['POST'])
def upload_recording():
    project_id = request.form.get('project_id')
    segment_id = request.form.get('segment_id', 'full')
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400
    if 'video' not in request.files:
        return jsonify({'error': 'No video file uploaded'}), 400

    video = request.files['video']
    rec_dir = project_store._project_dir(project_id) / 'recordings'
    rec_dir.mkdir(parents=True, exist_ok=True)
    try:
        filename = safe_filename(f'{segment_id}.webm')
    except ValueError:
        return jsonify({'error': 'Invalid segment ID'}), 400
    save_path = rec_dir / filename
    video.save(str(save_path))

    return jsonify({
        'success': True,
        'filename': filename,
        'size_bytes': save_path.stat().st_size,
    })


@app.route('/api/recordings/<project_id>/<filename>')
def serve_recording(project_id, filename):
    try:
        safe_name = safe_filename(filename)
    except ValueError:
        return jsonify({'error': 'Invalid filename'}), 400
    file_path = project_store._project_dir(project_id) / 'recordings' / safe_name
    if not file_path.exists():
        return jsonify({'error': 'Recording not found'}), 404
    return send_file(str(file_path), mimetype='video/webm')


# ============================================================================
# COURSERA PRODUCTION FEATURES
# ============================================================================

@app.route('/api/projects/<project_id>/import-script', methods=['POST'])
def import_script(project_id):
    """Import an existing video script file (.docx or .md)."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    try:
        filename = safe_filename(file.filename)
    except ValueError:
        return jsonify({'error': 'Invalid filename'}), 400

    # Save to temp location inside project dir
    project_dir = project_store._project_dir(project_id)
    temp_path = project_dir / filename
    file.save(str(temp_path))

    try:
        importer = ScriptImporter()
        if filename.lower().endswith('.docx'):
            imported = importer.import_docx(temp_path)
        elif filename.lower().endswith('.md'):
            imported = importer.import_markdown(temp_path)
        else:
            temp_path.unlink(missing_ok=True)
            return jsonify({'error': 'Unsupported file type. Use .docx or .md'}), 400

        # Update project
        project.raw_script = imported.raw_text
        project.title = imported.title
        project.target_duration = imported.duration_estimate
        project.updated_at = datetime.now().isoformat()

        # Parse into segments
        segments = parse_script_to_segments(imported.raw_text)
        project.segments = segments
        project_store.save(project)

        return jsonify({
            'success': True,
            'title': imported.title,
            'duration': imported.duration_estimate,
            'sections': len(imported.sections),
            'code_blocks': len(imported.code_blocks),
            'has_ivq': imported.ivq is not None,
            'segments': [s.to_dict() for s in segments],
        })
    except Exception as e:
        return jsonify({'error': f'Import failed: {str(e)}'}), 500
    finally:
        temp_path.unlink(missing_ok=True)


@app.route('/api/projects/<project_id>/generate-slides', methods=['POST'])
def generate_slides(project_id):
    """Generate slide images for the project."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    if not project.raw_script:
        return jsonify({'error': 'No script to generate slides from'}), 400

    try:
        importer = ScriptImporter()
        script = importer._parse_markdown(project.raw_script)

        output_dir = project_store._project_dir(project_id) / 'slides'
        paths = generate_slides_from_script(script, output_dir)

        return jsonify({
            'success': True,
            'slides_generated': len(paths) // 2,  # PNG + SVG pairs
            'png_folder': str(output_dir / 'png'),
            'svg_folder': str(output_dir / 'svg'),
            'files': [p.name for p in paths],
        })
    except Exception as e:
        return jsonify({'error': f'Slide generation failed: {str(e)}'}), 500


@app.route('/api/projects/<project_id>/generate-notebook', methods=['POST'])
def generate_notebook(project_id):
    """Generate Jupyter notebook aligned to script."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    if not project.raw_script:
        return jsonify({'error': 'No script to generate notebook from'}), 400

    try:
        importer = ScriptImporter()
        script = importer._parse_markdown(project.raw_script)

        output_path = project_store._project_dir(project_id) / 'notebook' / 'demo.ipynb'
        generator = NotebookGenerator()
        result = generator.generate_from_script(script, output_path)

        return jsonify({
            'success': True,
            'notebook_path': str(result.filepath),
            'cell_count': result.cell_count,
            'cell_mapping': result.cell_mapping,
        })
    except Exception as e:
        return jsonify({'error': f'Notebook generation failed: {str(e)}'}), 500


@app.route('/api/projects/<project_id>/generate-tts-narration', methods=['POST'])
def generate_tts_narration(project_id):
    """Generate clean TTS narration file for ElevenLabs."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    if not project.raw_script:
        return jsonify({'error': 'No script to extract narration from'}), 400

    try:
        optimizer = TTSOptimizer()
        output_path = project_store._project_dir(project_id) / 'tts_narration' / 'narration.txt'
        optimizer.generate_narration_file(project.raw_script, output_path)

        segments = optimizer.extract_narration_segments(project.raw_script)
        total_duration = sum(s['duration_seconds'] for s in segments)

        return jsonify({
            'success': True,
            'narration_file': str(output_path),
            'total_words': sum(s['word_count'] for s in segments),
            'estimated_duration': f'{total_duration // 60}:{total_duration % 60:02d}',
            'segments': segments,
        })
    except Exception as e:
        return jsonify({'error': f'Narration generation failed: {str(e)}'}), 500


@app.route('/api/projects/<project_id>/generate-production-notes', methods=['POST'])
def generate_production_notes(project_id):
    """Generate production notes document."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    if not project.raw_script:
        return jsonify({'error': 'No script to generate notes from'}), 400

    try:
        data = request.json or {}
        fmt = data.get('format', 'docx')
        if fmt not in ('docx', 'md'):
            fmt = 'docx'

        importer = ScriptImporter()
        script = importer._parse_markdown(project.raw_script)

        project_dir = project_store._project_dir(project_id)
        generator = ProductionNotesGenerator()
        output_path = generator.generate(script, project_dir, fmt=fmt)

        return jsonify({
            'success': True,
            'filepath': str(output_path),
            'format': fmt,
        })
    except Exception as e:
        return jsonify({'error': f'Production notes generation failed: {str(e)}'}), 500


@app.route('/api/projects/<project_id>/generate-demo-script', methods=['POST'])
def generate_demo_script(project_id):
    """Generate Python terminal demo script for screencast recording."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    if not project.raw_script:
        return jsonify({'error': 'No script to generate demo from'}), 400

    try:
        importer = ScriptImporter()
        script = importer._parse_markdown(project.raw_script)

        project_dir = project_store._project_dir(project_id)
        output_dir = project_dir / 'demo_script'

        generator = PythonDemoGenerator()
        script_path = generator.generate_from_script(script, output_dir, project.title)

        return jsonify({
            'success': True,
            'demo_script': str(script_path),
            'output_dir': str(output_dir),
            'instructions': 'Set FAST_MODE=True for testing, False for recording',
        })
    except Exception as e:
        return jsonify({'error': f'Demo script generation failed: {str(e)}'}), 500


@app.route('/api/projects/<project_id>/export-full-package', methods=['POST'])
def export_full_package(project_id):
    """Export complete video production package."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    if not project.raw_script:
        return jsonify({'error': 'No script to export'}), 400

    try:
        project_dir = project_store._project_dir(project_id)
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)

        exporter = PackageExporter()
        package_dir = exporter.export_full_package(
            project_id=project_id,
            project_dir=project_dir,
            output_dir=output_dir,
            video_title=project.title,
            raw_script=project.raw_script,
        )

        data = request.json or {}
        if data.get('create_zip', True):
            zip_path = exporter.export_as_zip(package_dir)
            return send_file(
                str(zip_path), mimetype='application/zip',
                as_attachment=True,
                download_name=f'{sanitize_filename(project.title)}.zip',
            )

        contents = [
            str(f.relative_to(package_dir))
            for f in package_dir.rglob('*') if f.is_file()
        ]
        return jsonify({
            'success': True,
            'package_dir': str(package_dir),
            'contents': contents,
        })
    except Exception as e:
        return jsonify({'error': f'Export failed: {str(e)}'}), 500


# ============================================================================
# RECORDING STUDIO API
# ============================================================================

# In-memory session store (one session per project)
recording_sessions = {}  # project_id -> RecordingSession


@app.route('/api/projects/<project_id>/recording-session', methods=['POST'])
def generate_recording_session(project_id):
    """Generate a recording session from the project script."""
    project = project_store.load(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    if not project.raw_script:
        return jsonify({'error': 'No script to generate session from'}), 400

    data = request.json or {}
    mode_str = data.get('mode', 'teleprompter')
    try:
        mode = RecordingMode(mode_str)
    except ValueError:
        mode = RecordingMode.TELEPROMPTER

    generator = RecordingSessionGenerator()
    session = generator.generate_session(
        project_id=project_id,
        raw_script=project.raw_script,
        segments=[s.to_dict() for s in project.segments],
        mode=mode,
    )

    recording_sessions[project_id] = session
    return jsonify({'success': True, 'session': session.to_dict()})


@app.route('/api/projects/<project_id>/recording-session', methods=['GET'])
def get_recording_session(project_id):
    """Get the current recording session for a project."""
    session = recording_sessions.get(project_id)
    if not session:
        return jsonify({'error': 'No recording session found. Generate one first.'}), 404
    return jsonify({'session': session.to_dict()})


@app.route('/api/projects/<project_id>/recording-session/mode', methods=['PUT'])
def set_recording_mode(project_id):
    """Change the recording mode for the current session."""
    session = recording_sessions.get(project_id)
    if not session:
        return jsonify({'error': 'No recording session found'}), 404

    data = request.json or {}
    mode_str = data.get('mode', '')
    if not mode_str:
        return jsonify({'error': 'mode is required'}), 400

    try:
        session.mode = RecordingMode(mode_str)
    except ValueError:
        return jsonify({'error': f'Invalid mode: {mode_str}'}), 400

    return jsonify({'success': True, 'mode': session.mode.value})


@app.route('/api/projects/<project_id>/recording-session/teleprompter', methods=['PUT'])
def update_teleprompter_settings(project_id):
    """Update teleprompter settings for the recording session."""
    session = recording_sessions.get(project_id)
    if not session:
        return jsonify({'error': 'No recording session found'}), 404

    data = request.json or {}
    settings = session.teleprompter_settings

    for field_name in ('font_size', 'scroll_speed', 'line_height', 'countdown_seconds'):
        if field_name in data:
            setattr(settings, field_name, data[field_name])
    for field_name in ('mirror', 'highlight_current', 'auto_scroll'):
        if field_name in data:
            setattr(settings, field_name, bool(data[field_name]))

    return jsonify({'success': True, 'teleprompter_settings': settings.to_dict()})


@app.route('/api/projects/<project_id>/recording-session/rehearsal', methods=['POST'])
def start_rehearsal(project_id):
    """Start a rehearsal run — returns session info for the client to time."""
    session = recording_sessions.get(project_id)
    if not session:
        return jsonify({'error': 'No recording session found'}), 404

    return jsonify({
        'success': True,
        'rehearsal_id': RehearsalResult().id,
        'total_cues': len(session.cues),
        'target_duration': session.total_duration_estimate,
        'cues': [c.to_dict() for c in session.cues],
    })


@app.route('/api/projects/<project_id>/recording-session/rehearsal/complete', methods=['POST'])
def complete_rehearsal(project_id):
    """Record the results of a completed rehearsal."""
    session = recording_sessions.get(project_id)
    if not session:
        return jsonify({'error': 'No recording session found'}), 404

    data = request.json or {}
    actual_duration = data.get('actual_duration', 0)
    section_timings = data.get('section_timings', [])
    notes = data.get('notes', '')

    result = RehearsalResult(
        actual_duration=float(actual_duration),
        target_duration=session.total_duration_estimate,
        section_timings=section_timings,
        notes=notes,
    )

    session.rehearsals.append(result)

    return jsonify({
        'success': True,
        'rehearsal': result.to_dict(),
        'total_rehearsals': len(session.rehearsals),
    })


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5001)
