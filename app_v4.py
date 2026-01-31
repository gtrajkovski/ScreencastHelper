"""ScreenCast Studio v4.0 - Browser-native screencast creation tool.

No desktop dependencies (FFmpeg, tkinter). All recording via browser MediaRecorder API.
"""

import ast
import io
import json
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file, redirect, url_for

load_dotenv()

from src.config import Config
from src.ai.client import AIClient
from src.generators.tts_audio_generator import TTSAudioGenerator
from src.generators.timeline_generator import TimelineGenerator
from src.generators.v4_script_generator import generate_script as ai_generate_script
from src.generators.v4_code_generator import generate_code as ai_generate_code

app = Flask(__name__,
            template_folder='templates_v4',
            static_folder='static_v4',
            static_url_path='/static')

PROJECTS_DIR = Path('projects')
PROJECTS_DIR.mkdir(exist_ok=True)

ai_client = AIClient()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def sanitize_filename(name: str) -> str:
    """Create safe filename from project name."""
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')[:50] or 'untitled'


def get_project_dir(project_id: str) -> Path:
    """Get project directory path."""
    return PROJECTS_DIR / project_id


def load_project(project_id: str) -> dict | None:
    """Load project from disk."""
    project_file = get_project_dir(project_id) / 'project.json'
    if not project_file.exists():
        return None
    with open(project_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_project(project: dict) -> None:
    """Save project to disk."""
    project_dir = get_project_dir(project['id'])
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / 'audio').mkdir(exist_ok=True)
    project['modified'] = datetime.now(timezone.utc).isoformat()
    with open(project_dir / 'project.json', 'w', encoding='utf-8') as f:
        json.dump(project, f, indent=2, ensure_ascii=False)


def new_project(name: str) -> dict:
    """Create a new empty project."""
    return {
        'id': f'proj_{uuid.uuid4().hex[:12]}',
        'name': name,
        'created': datetime.now(timezone.utc).isoformat(),
        'modified': datetime.now(timezone.utc).isoformat(),
        'script_raw': '',
        'segments': [],
        'config': {
            'resolution': [1920, 1080],
            'fps': 30,
            'theme': 'dark',
            'voice': Config.TTS_VOICE,
            'duration_minutes': 5
        }
    }


def parse_script_to_segments(script: str, duration_minutes: int = 5) -> list:
    """Parse WWHAA-structured script into segments.

    Returns list of segment dicts with id, type, section, title, narration,
    visual_cues, duration_seconds, cells, environment.
    """
    segments = []
    segment_id = 0

    section_proportions = {
        'HOOK': 0.08, 'OBJECTIVE': 0.08, 'CONTENT': 0.52,
        'IVQ': 0.10, 'SUMMARY': 0.08, 'CTA': 0.06, 'CALL TO ACTION': 0.06
    }
    total_seconds = duration_minutes * 60

    # Strip metadata table if present (not a script section)
    script = re.sub(r'^\s*\|[^\n]*\|\n(?:\|[-:| ]+\|\n)?(?:\|[^\n]*\|\n)*', '', script).strip()

    section_pattern = (
        r'##\s*(\d+\.\s*)?(HOOK|OBJECTIVE|CONTENT|IVQ|SUMMARY|CALL TO ACTION|CTA)'
        r'([^\n]*)\n([\s\S]*?)(?=##\s*\d*\.?\s*'
        r'(?:HOOK|OBJECTIVE|CONTENT|IVQ|SUMMARY|CALL TO ACTION|CTA)|$)'
    )
    matches = re.findall(section_pattern, script, re.IGNORECASE)

    if not matches:
        return [{
            'id': 'seg_000',
            'type': 'slide',
            'section': 'CONTENT',
            'title': 'Presentation',
            'narration': script.strip(),
            'visual_cues': [],
            'duration_seconds': total_seconds,
            'environment': 'jupyter',
            'cells': []
        }]

    for match in matches:
        _, section_type, subtitle, content = match
        section_type = section_type.strip().upper()
        subtitle = subtitle.strip(' -:')
        content = content.strip()

        proportion = section_proportions.get(section_type, 0.10)
        duration = int(total_seconds * proportion)

        all_cues = re.findall(r'\[([^\]]+)\]', content)
        visual_cues = [c for c in all_cues if c.upper() != 'PAUSE']

        narration = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
        narration = re.sub(r'#{1,3}\s+', '', narration)
        narration = re.sub(r'\[(?!PAUSE)[^\]]*\]', '', narration)
        narration = re.sub(r'```(?:python)?\n[\s\S]*?```', '', narration)
        narration = re.sub(r'---\s*CELL BREAK\s*---', '', narration)
        narration = re.sub(r'\b(NARRATION|OUTPUT|RUN CELL|TYPE|SHOW):', '', narration)
        narration = re.sub(r'\n{3,}', '\n\n', narration).strip()

        code_blocks = re.findall(r'```(?:python)?\n([\s\S]*?)```', content)

        # Extract OUTPUT blocks paired with code blocks
        output_blocks = []
        for m in re.finditer(r'```(?:python)?\n[\s\S]*?```\s*(?:\*\*OUTPUT:\*\*\s*)?```\n?([\s\S]*?)```', content):
            output_blocks.append(m.group(1).strip())
        # Fallback: also match OUTPUT: blocks without code fences
        if not output_blocks:
            output_blocks = re.findall(r'\*\*OUTPUT:\*\*\s*```\n?([\s\S]*?)```', content)

        seg_id_str = f'seg_{segment_id:03d}'

        if code_blocks and section_type == 'CONTENT':
            # Leading prose as slide
            parts = re.split(r'```(?:python)?\n[\s\S]*?```', content)
            prose_parts = [p.strip() for p in parts if p.strip()]

            if prose_parts:
                prose_narration = re.sub(r'\[(?!PAUSE)[^\]]*\]', '', prose_parts[0]).strip()
                prose_narration = re.sub(r'\*\*([^*]+)\*\*', r'\1', prose_narration)
                if prose_narration:
                    bullets = [line.lstrip('- *').strip()
                               for line in prose_parts[0].split('\n')
                               if re.match(r'^\s*[-*]\s+', line)]
                    segments.append({
                        'id': seg_id_str,
                        'type': 'slide',
                        'section': section_type,
                        'title': subtitle or section_type,
                        'narration': prose_narration,
                        'visual_cues': visual_cues,
                        'duration_seconds': duration // 3,
                        'environment': 'jupyter',
                        'cells': []
                    })
                    segment_id += 1
                    seg_id_str = f'seg_{segment_id:03d}'

            cells = []
            for i, block in enumerate(code_blocks):
                cell_output = output_blocks[i] if i < len(output_blocks) else None
                cells.append({
                    'id': f'cell_{i + 1}',
                    'type': 'code',
                    'content': block.strip(),
                    'output': cell_output,
                    'execution_count': i + 1
                })

            segments.append({
                'id': seg_id_str,
                'type': 'screencast',
                'section': section_type,
                'title': subtitle or 'Live Demo',
                'narration': narration,
                'visual_cues': visual_cues,
                'duration_seconds': duration * 2 // 3,
                'environment': 'jupyter',
                'cells': cells
            })
            segment_id += 1
        else:
            bullets = [line.lstrip('- *').strip()
                       for line in content.split('\n')
                       if re.match(r'^\s*[-*]\s+', line)]
            if not bullets:
                sentences = [s.strip() for s in re.split(r'[.!?]\s+', narration) if len(s.strip()) > 15]
                bullets = sentences[:5]

            default_title = 'In-Video Question' if section_type == 'IVQ' else section_type
            segments.append({
                'id': seg_id_str,
                'type': 'slide',
                'section': section_type,
                'title': subtitle or default_title,
                'narration': narration,
                'visual_cues': visual_cues,
                'duration_seconds': duration,
                'environment': 'jupyter',
                'cells': []
            })
            segment_id += 1

    return segments


# ============================================================================
# PAGE ROUTES
# ============================================================================

@app.route('/')
def index():
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    return render_template('index.html')


@app.route('/workspace/<project_id>')
def workspace(project_id):
    project = load_project(project_id)
    if not project:
        return redirect(url_for('dashboard'))
    return render_template('workspace.html', project=project)


@app.route('/player/<project_id>')
def player(project_id):
    project = load_project(project_id)
    if not project:
        return redirect(url_for('dashboard'))
    return render_template('player.html', project=project)


# ============================================================================
# PROJECT MANAGEMENT API
# ============================================================================

@app.route('/api/projects', methods=['GET'])
def list_projects():
    """List all projects."""
    projects = []
    for p_dir in sorted(PROJECTS_DIR.iterdir()):
        pf = p_dir / 'project.json'
        if pf.exists():
            try:
                with open(pf, 'r', encoding='utf-8') as f:
                    proj = json.load(f)
                projects.append({
                    'id': proj['id'],
                    'name': proj.get('name', 'Untitled'),
                    'created': proj.get('created'),
                    'modified': proj.get('modified'),
                    'segment_count': len(proj.get('segments', [])),
                    'has_audio': any(
                        (p_dir / 'audio' / f'segment_{s["id"]}.mp3').exists()
                        for s in proj.get('segments', [])
                    )
                })
            except (json.JSONDecodeError, KeyError):
                continue
    return jsonify(projects)


@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project."""
    data = request.json or {}
    name = data.get('name', 'Untitled Project')
    project = new_project(name)

    if data.get('topic'):
        project['name'] = data['topic']
    if data.get('duration_minutes'):
        project['config']['duration_minutes'] = data['duration_minutes']
    if data.get('voice'):
        project['config']['voice'] = data['voice']

    save_project(project)
    return jsonify(project), 201


@app.route('/api/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    """Get project details."""
    project = load_project(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify(project)


@app.route('/api/projects/<project_id>', methods=['PUT'])
def update_project(project_id):
    """Update project."""
    project = load_project(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.json or {}
    for key in ('name', 'script_raw', 'segments', 'config'):
        if key in data:
            project[key] = data[key]

    save_project(project)
    return jsonify(project)


@app.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete project."""
    project_dir = get_project_dir(project_id)
    if not project_dir.exists():
        return jsonify({'error': 'Project not found'}), 404

    import shutil
    shutil.rmtree(project_dir)
    return jsonify({'success': True})


# ============================================================================
# CONTENT GENERATION API
# ============================================================================

@app.route('/api/generate/script', methods=['POST'])
def generate_script():
    """Generate a WWHAA video script via AI with full context."""
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
        format_type=data.get('format_type')
    )

    if result['success']:
        return jsonify(result)
    else:
        return jsonify({'error': result['error']}), 500


@app.route('/api/generate/code', methods=['POST'])
def generate_code():
    """Generate code for a segment via AI with full context."""
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
        include_output=data.get('include_output', True)
    )

    if result['success']:
        return jsonify(result)
    else:
        return jsonify({'error': result['error']}), 500


@app.route('/api/parse/script', methods=['POST'])
def parse_script():
    """Parse script text into segments."""
    data = request.json or {}
    script_text = data.get('script_text', '')
    project_id = data.get('project_id')
    duration = data.get('duration_minutes', 5)

    if not script_text:
        return jsonify({'error': 'script_text is required'}), 400

    segments = parse_script_to_segments(script_text, duration)

    # If project_id provided, save segments to project
    if project_id:
        project = load_project(project_id)
        if project:
            project['script_raw'] = script_text
            project['segments'] = segments
            save_project(project)

    return jsonify({'success': True, 'segments': segments})


# ============================================================================
# AI HELPERS API
# ============================================================================

SEGMENT_IMPROVE_PROMPTS = {
    'shorten': "Rewrite this script segment to be 20-30% shorter while keeping all key information. Maintain the same tone and format.",
    'expand': "Expand this script segment with more detail, examples, or explanation. Add 20-30% more content. Keep the same tone.",
    'fix_tone': "Rewrite this script segment to be more conversational and engaging. Use first-person where appropriate. Avoid academic tone.",
    'simplify': "Simplify the language in this script segment. Use shorter sentences and simpler words. Keep technical accuracy.",
    'improve_code_explanation': 'Improve the narration around the code in this segment. Explain WHAT the code does and WHY each line matters. Add "Notice..." and "Here\'s the key..." phrases.',
    'add_output': "Add realistic **OUTPUT:** blocks after each code cell showing what the code would produce when run.",
    'fix_code': "Fix any syntax errors in the Python code blocks. Ensure all code is valid and would actually run. Keep the same logic.",
    'add_comments': "Add clear, helpful comments to the code blocks explaining what each section does. Don't over-comment obvious lines.",
    'add_visual_cue': "Add [SCREEN: ...] visual cues to indicate what should be shown on screen during this segment. Add at least one per 60 seconds of content.",
    'improve_transition': 'Improve the transition into and out of this segment. Add connecting phrases like "Now that we have...", "With that in place...".',
    'add_pause': "Add **[PAUSE]** markers after important outputs or concepts to give viewers time to absorb the information.",
    'balance_ivq_options': "Rewrite the IVQ options so they are all similar in length (within 10-15 characters of each other). Keep the same meanings.",
    'improve_ivq_feedback': "Improve the feedback for each IVQ option. Explain WHY each wrong answer is wrong, not just that it's incorrect.",
    'make_ivq_harder': "Make this IVQ question more challenging. Require deeper understanding or application, not just recall.",
    'make_ivq_easier': "Make this IVQ question easier. Focus on basic understanding. Make one option clearly correct and others clearly different.",
}

SEGMENT_IMPROVE_SYSTEM = """You are an expert instructional designer improving a screencast \
video script segment. Return ONLY the improved segment in the exact same markdown format. \
Preserve all structure markers like ### headings, **[RUN CELL]** markers, **NARRATION:** blocks, \
**OUTPUT:** blocks, [SCREEN: ...] cues, and code blocks. Do not add explanations outside the segment."""


@app.route('/api/ai/improve-segment', methods=['POST'])
def improve_segment():
    """Use AI to improve a specific script segment."""
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
    """Use AI to edit a selected text range."""
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
    """Validate all Python code blocks in a script using ast.parse()."""
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
        'results': results
    })


# ============================================================================
# EXPORT API
# ============================================================================

def extract_code_cells(script_text: str) -> str:
    """Extract all Python code blocks into a single .py file."""
    code_blocks = re.findall(r'```(?:python)?\n([\s\S]*?)```', script_text)
    lines = []
    for i, block in enumerate(code_blocks):
        lines.append(f'# --- Cell {i + 1} ---')
        lines.append(block.strip())
        lines.append('')
    return '\n'.join(lines)


def create_jupyter_notebook(script_text: str) -> dict:
    """Convert code blocks from script into a Jupyter notebook dict."""
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
    """Export project artifacts to a folder on disk."""
    project = load_project(project_id)
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
    script_raw = project.get('script_raw', '')
    safe_name = sanitize_filename(project.get('name', 'untitled'))

    if options.get('script', True) and script_raw:
        script_file = output_path / f'{safe_name}.md'
        script_file.write_text(script_raw, encoding='utf-8')
        exported.append(str(script_file))

    if options.get('code', False) and script_raw:
        code_content = extract_code_cells(script_raw)
        if code_content.strip():
            code_file = output_path / f'{safe_name}.py'
            code_file.write_text(code_content, encoding='utf-8')
            exported.append(str(code_file))

    if options.get('notebook', False) and script_raw:
        nb = create_jupyter_notebook(script_raw)
        if nb:
            import nbformat
            nb_file = output_path / f'{safe_name}.ipynb'
            with open(nb_file, 'w', encoding='utf-8') as f:
                nbformat.write(nb, f)
            exported.append(str(nb_file))

    if options.get('audio', False):
        audio_dir = get_project_dir(project_id) / 'audio'
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
    """Export project as downloadable ZIP."""
    project = load_project(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.json or {}
    options = data.get('options', {})
    script_raw = project.get('script_raw', '')
    safe_name = sanitize_filename(project.get('name', 'untitled'))

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
            audio_dir = get_project_dir(project_id) / 'audio'
            if audio_dir.exists():
                for mp3 in audio_dir.glob('*.mp3'):
                    zf.write(str(mp3), f'{safe_name}/audio/{mp3.name}')

    buffer.seek(0)
    return send_file(buffer, mimetype='application/zip', as_attachment=True,
                     download_name=f'{safe_name}.zip')


@app.route('/api/browse-folders', methods=['GET'])
def browse_folders():
    """List subdirectories of a given path for folder browser."""
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
        'folders': folders
    })


@app.route('/api/create-folder', methods=['POST'])
def create_folder():
    """Create a new folder."""
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
    """Generate TTS audio for a specific segment."""
    data = request.json or {}
    project_id = data.get('project_id')
    voice = data.get('voice', Config.TTS_VOICE)
    rate = data.get('rate', Config.TTS_RATE)
    pitch = data.get('pitch', Config.TTS_PITCH)

    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400

    project = load_project(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    segment = next((s for s in project.get('segments', []) if s['id'] == segment_id), None)
    if not segment:
        return jsonify({'error': f'Segment {segment_id} not found'}), 404

    narration = segment.get('narration', '')
    if not narration.strip():
        return jsonify({'error': 'Segment has no narration text'}), 400

    # Apply TTS text fixes
    for old, new in Config.TTS_REPLACEMENTS.items():
        narration = narration.replace(old, new)

    audio_dir = get_project_dir(project_id) / 'audio'
    audio_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(audio_dir / f'segment_{segment_id}.mp3')

    try:
        import asyncio
        tts = TTSAudioGenerator(voice=voice, rate=rate, pitch=pitch)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            tts.generate_segment(0, segment.get('section', 'CONTENT'), narration, output_path)
        )
        loop.close()

        return jsonify({
            'success': True,
            'segment_id': segment_id,
            'duration_seconds': result.duration_seconds,
            'file_size_bytes': result.file_size_bytes
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/audio/generate-all', methods=['POST'])
def generate_all_audio():
    """Generate TTS audio for all segments of a project."""
    data = request.json or {}
    project_id = data.get('project_id')
    voice = data.get('voice', Config.TTS_VOICE)

    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400

    project = load_project(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    segments = project.get('segments', [])
    if not segments:
        return jsonify({'error': 'No segments to generate audio for'}), 400

    audio_dir = get_project_dir(project_id) / 'audio'
    audio_dir.mkdir(parents=True, exist_ok=True)

    results = []
    try:
        import asyncio
        tts = TTSAudioGenerator(voice=voice)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for seg in segments:
            narration = seg.get('narration', '')
            if not narration.strip():
                continue

            # Apply TTS fixes
            for old, new_val in Config.TTS_REPLACEMENTS.items():
                narration = narration.replace(old, new_val)

            output_path = str(audio_dir / f'segment_{seg["id"]}.mp3')
            result = loop.run_until_complete(
                tts.generate_segment(0, seg.get('section', 'CONTENT'), narration, output_path)
            )

            # Update segment duration based on actual audio
            seg['duration_seconds'] = result.duration_seconds

            results.append({
                'segment_id': seg['id'],
                'duration_seconds': result.duration_seconds,
                'file_size_bytes': result.file_size_bytes
            })

        loop.close()

        # Save updated project with audio durations
        save_project(project)

        total_duration = sum(r['duration_seconds'] for r in results)
        return jsonify({
            'success': True,
            'segments_generated': len(results),
            'total_duration_seconds': total_duration,
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/audio/<segment_id>')
def serve_audio(segment_id):
    """Stream MP3 audio file for a segment."""
    project_id = request.args.get('project_id')
    if not project_id:
        return jsonify({'error': 'project_id query param required'}), 400

    audio_path = get_project_dir(project_id) / 'audio' / f'segment_{segment_id}.mp3'
    if not audio_path.exists():
        return jsonify({'error': 'Audio not found'}), 404

    return send_file(str(audio_path), mimetype='audio/mpeg')


# ============================================================================
# TIMELINE API
# ============================================================================

@app.route('/api/timeline/generate/<segment_id>', methods=['POST'])
def generate_timeline(segment_id):
    """Generate event timeline for a segment."""
    data = request.json or {}
    project_id = data.get('project_id')

    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400

    project = load_project(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    segment = next((s for s in project.get('segments', []) if s['id'] == segment_id), None)
    if not segment:
        return jsonify({'error': f'Segment {segment_id} not found'}), 404

    audio_duration = segment.get('duration_seconds', 30)

    # Adapt segment format for TimelineGenerator
    adapted = {
        'id': segment['id'],
        'type': 'notebook' if segment.get('type') == 'screencast' else segment.get('type', 'slide'),
        'cells': segment.get('cells', []),
        'slide_content': {'bullets': []},
        'code_cells': []
    }

    # Convert cells format for timeline generator
    if segment.get('cells'):
        adapted['code_cells'] = [
            {'code': c.get('content', ''), 'output': c.get('output', ''), 'id': c.get('id', f'cell_{i}')}
            for i, c in enumerate(segment['cells'])
        ]

    gen = TimelineGenerator()
    timeline = gen.generate(adapted, audio_duration)

    # Convert to spec format (time_ms instead of time seconds)
    events = []
    for e in timeline.events:
        event = {
            'time_ms': int(e.time * 1000),
            'type': e.action,
            'data': e.params
        }
        events.append(event)

    result = {
        'segment_id': segment_id,
        'total_duration_ms': int(timeline.total_duration * 1000),
        'events': events
    }

    return jsonify(result)


@app.route('/api/timeline/<segment_id>')
def get_timeline(segment_id):
    """Get timeline for a segment (generates on the fly)."""
    project_id = request.args.get('project_id')
    if not project_id:
        return jsonify({'error': 'project_id query param required'}), 400

    project = load_project(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    segment = next((s for s in project.get('segments', []) if s['id'] == segment_id), None)
    if not segment:
        return jsonify({'error': f'Segment {segment_id} not found'}), 404

    audio_duration = segment.get('duration_seconds', 30)

    adapted = {
        'id': segment['id'],
        'type': 'notebook' if segment.get('type') == 'screencast' else segment.get('type', 'slide'),
        'cells': segment.get('cells', []),
        'slide_content': {'bullets': []},
        'code_cells': []
    }

    if segment.get('cells'):
        adapted['code_cells'] = [
            {'code': c.get('content', ''), 'output': c.get('output', ''), 'id': c.get('id', f'cell_{i}')}
            for i, c in enumerate(segment['cells'])
        ]

    gen = TimelineGenerator()
    timeline = gen.generate(adapted, audio_duration)

    events = []
    for e in timeline.events:
        events.append({
            'time_ms': int(e.time * 1000),
            'type': e.action,
            'data': e.params
        })

    return jsonify({
        'segment_id': segment_id,
        'total_duration_ms': int(timeline.total_duration * 1000),
        'events': events
    })


# ============================================================================
# TTS VOICES
# ============================================================================

@app.route('/api/voices')
def list_voices():
    """List available Edge TTS voices."""
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
# UPLOAD RECORDING (receive WebM from browser)
# ============================================================================

@app.route('/api/recordings/upload', methods=['POST'])
def upload_recording():
    """Receive recorded WebM blob from browser MediaRecorder."""
    project_id = request.form.get('project_id')
    segment_id = request.form.get('segment_id', 'full')

    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400

    if 'video' not in request.files:
        return jsonify({'error': 'No video file uploaded'}), 400

    video = request.files['video']
    rec_dir = get_project_dir(project_id) / 'recordings'
    rec_dir.mkdir(parents=True, exist_ok=True)

    filename = f'{segment_id}.webm'
    save_path = rec_dir / filename
    video.save(str(save_path))

    return jsonify({
        'success': True,
        'filename': filename,
        'size_bytes': save_path.stat().st_size
    })


@app.route('/api/recordings/<project_id>/<filename>')
def serve_recording(project_id, filename):
    """Serve a recorded WebM file."""
    file_path = get_project_dir(project_id) / 'recordings' / filename
    if not file_path.exists():
        return jsonify({'error': 'Recording not found'}), 404
    return send_file(str(file_path), mimetype='video/webm')


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5001)
