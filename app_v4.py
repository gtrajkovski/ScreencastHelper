"""ScreenCast Studio v4.0 - Browser-native screencast creation tool.

No desktop dependencies (FFmpeg, tkinter). All recording via browser MediaRecorder API.
"""

import json
import os
import re
import uuid
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
        'HOOK': 0.10, 'OBJECTIVE': 0.10, 'CONTENT': 0.60,
        'SUMMARY': 0.10, 'CTA': 0.10, 'CALL TO ACTION': 0.10
    }
    total_seconds = duration_minutes * 60

    section_pattern = (
        r'##\s*(\d+\.\s*)?(HOOK|OBJECTIVE|CONTENT|SUMMARY|CALL TO ACTION|CTA)'
        r'([^\n]*)\n([\s\S]*?)(?=##\s*\d*\.?\s*'
        r'(?:HOOK|OBJECTIVE|CONTENT|SUMMARY|CALL TO ACTION|CTA)|$)'
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
        narration = re.sub(r'\n{3,}', '\n\n', narration).strip()

        code_blocks = re.findall(r'```(?:python)?\n([\s\S]*?)```', content)

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
                cells.append({
                    'id': f'cell_{i + 1}',
                    'type': 'code',
                    'content': block.strip(),
                    'output': None,
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

            segments.append({
                'id': seg_id_str,
                'type': 'slide',
                'section': section_type,
                'title': subtitle or section_type,
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
        notes=data.get('notes')
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
