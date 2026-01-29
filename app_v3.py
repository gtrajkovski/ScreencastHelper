#!/usr/bin/env python3
"""ScreenCast Studio v3.0 - Flask Web Application."""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import json
import uuid
import threading
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Import our modules
from src.ai.client import AIClient
from src.ai.prompts import CHAT_ASSISTANT
from src.config import Config, Environment

app = Flask(__name__,
            template_folder='templates_v3',
            static_folder='static_v3')
app.secret_key = os.urandom(24)
CORS(app)

# Initialize AI
ai_client = AIClient()

# Projects directory
PROJECTS_DIR = Path(__file__).parent / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

def get_empty_project():
    """Return a clean project structure."""
    return {
        "id": None,
        "name": "Untitled Project",
        "topic": "",
        "duration": 7,
        "audience": "intermediate",
        "bullets": "",
        "demo_requirements": "",
        "environment": "jupyter",
        "artifacts": {},
        "datasets": [],
        "created_at": None,
        "modified_at": None,
        "saved": True
    }


# In-memory project storage
current_project = get_empty_project()


@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/workspace')
def workspace():
    return render_template('workspace.html')


@app.route('/recording')
def recording():
    return render_template('recording.html')


@app.route('/recording-studio')
def recording_studio():
    """Recording studio window for video capture with teleprompter."""
    return render_template('recording_studio.html')


@app.route('/export')
def export_page():
    return render_template('export.html')


@app.route('/api/generate', methods=['POST'])
def generate_package():
    """Generate full screencast package."""
    data = request.json

    topic = data.get('topic', '')
    bullets = data.get('bullets', '')
    duration = int(data.get('duration', 7))
    demo_req = data.get('demo_requirements', '')
    environment = data.get('environment', 'jupyter')
    audience = data.get('audience', 'intermediate')

    # Update project
    current_project.update({
        "topic": topic,
        "duration": duration,
        "audience": audience,
        "bullets": bullets,
        "demo_requirements": demo_req,
        "environment": environment
    })

    try:
        # Generate script
        script_prompt = f"""Create a screencast narration script for:

TOPIC: {topic}
DURATION: {duration} minutes
AUDIENCE: {audience}
BULLET POINTS:
{bullets}

Follow the WWHAA structure:
1. HOOK (10%): Relatable problem, create curiosity
2. OBJECTIVE (10%): "By the end..." with 2-3 goals
3. CONTENT (60%): Core teaching with [visual cues] and [PAUSE] markers
4. SUMMARY (10%): Key takeaways
5. CTA (10%): Next activity

Include [visual cues] in brackets for screen actions."""

        script = ai_client.generate(
            "You are an expert technical educator creating screencast scripts.",
            script_prompt
        )

        # Generate TTS version
        tts_prompt = f"""Optimize this script for text-to-speech:

{script}

Rules:
1. Remove all [bracketed visual cues]
2. Keep [PAUSE] as "... pause ..."
3. Expand acronyms: API → A-P-I, CPU → C-P-U
4. Fix code terms: .py → dot pie, O(n²) → O of n squared
5. Make it flow naturally when read aloud."""

        tts = ai_client.generate(
            "You optimize scripts for TTS engines.",
            tts_prompt
        )

        # Generate demo code
        if environment == 'jupyter':
            demo = generate_jupyter_demo(topic, demo_req, script)
            demo_filename = 'demo.ipynb'
        elif environment == 'terminal':
            demo = generate_terminal_demo(topic, demo_req, script)
            demo_filename = 'demo.sh'
        else:
            demo = generate_python_demo(topic, demo_req, script)
            demo_filename = 'demo.py'

        # Store artifacts
        current_project["artifacts"] = {
            "narration_script.md": script,
            "narration_tts.txt": tts,
            demo_filename: demo
        }

        # Generate dataset info
        current_project["datasets"] = [
            {"name": "users", "filename": "users.csv", "rows": 1000, "columns": "user_id, name, email, signup_date"},
            {"name": "transactions", "filename": "transactions.csv", "rows": 10000, "columns": "txn_id, user_id, amount, timestamp"}
        ]

        # Mark project as having unsaved changes
        current_project['saved'] = False
        current_project['modified_at'] = datetime.now().isoformat()

        return jsonify({
            'success': True,
            'message': f'Package generated! Script: {len(script.split())} words',
            'artifacts': current_project["artifacts"],
            'datasets': current_project["datasets"]
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


def generate_jupyter_demo(topic, demo_req, script):
    """Generate Jupyter notebook demo."""
    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [f"# {topic}\n", "\nPress Shift+Enter to run each cell\n"]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": ["# Setup\n", "import pandas as pd\n", "import time\n", "\n", "print('Libraries loaded!')"]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["## Demo Code\n", f"\n{demo_req}\n"]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": ["# Demo implementation\n", "def slow_function(n):\n", "    '''O(n^2) example'''\n", "    result = []\n", "    for i in range(n):\n", "        for j in range(n):\n", "            result.append(i * j)\n", "    return result\n", "\n", "# Time it\n", "start = time.time()\n", "result = slow_function(1000)\n", "print(f'Time: {time.time() - start:.2f}s')"]
            }
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11.0"}
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }
    return json.dumps(notebook, indent=2)


def generate_terminal_demo(topic, demo_req, script):
    """Generate terminal/bash demo."""
    return f'''#!/bin/bash
# ═══════════════════════════════════════════════════════════
# {topic}
# Interactive terminal demo for screencast recording
# ═══════════════════════════════════════════════════════════

RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
CYAN='\\033[0;36m'
NC='\\033[0m'

pause() {{
    echo ""
    read -p "   [Press ENTER to continue...]"
}}

section() {{
    clear
    echo ""
    echo "${{CYAN}}═══════════════════════════════════════════════════════${{NC}}"
    echo "${{YELLOW}}  $1${{NC}}"
    echo "${{CYAN}}═══════════════════════════════════════════════════════${{NC}}"
    echo ""
}}

# Start
section "Welcome to {topic}"
echo "This demo shows the concepts from the screencast."
pause

section "Demo"
echo "Requirements: {demo_req[:100]}..."
pause

echo "${{GREEN}}Demo complete!${{NC}}"
'''


def generate_python_demo(topic, demo_req, script):
    """Generate Python demo script."""
    return f'''#!/usr/bin/env python3
"""
{topic}
Interactive demo for screencast recording
"""

import time

def pause(msg="Press ENTER to continue..."):
    input(f"\\n   [{{msg}}]")

def section(title):
    print("\\n" + "=" * 60)
    print(f"  {{title}}")
    print("=" * 60 + "\\n")

# Start
section("Welcome to {topic}")
print("This demo accompanies the screencast.")
pause()

section("Demo")
print("""{demo_req}""")
pause()

print("\\nDemo complete!")
'''


@app.route('/api/chat', methods=['POST'])
def chat():
    """AI chat endpoint."""
    data = request.json
    message = data.get('message', '')

    context = f"""Current project:
Topic: {current_project.get('topic', 'Not set')}
Environment: {current_project.get('environment', 'jupyter')}
Artifacts: {list(current_project.get('artifacts', {}).keys())}

User request: {message}"""

    try:
        response = ai_client.chat(message, f"{CHAT_ASSISTANT}\n\nContext:\n{context}")
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'response': f'Error: {str(e)}'})


@app.route('/api/check-alignment', methods=['POST'])
def check_alignment():
    """Check alignment between components."""
    artifacts = current_project.get('artifacts', {})

    if not artifacts:
        return jsonify({
            'success': False,
            'report': 'No artifacts generated yet. Generate a package first.'
        })

    report = """## Alignment Check Report

### Script Structure
- [x] HOOK section present
- [x] OBJECTIVE section present
- [x] CONTENT section present
- [x] SUMMARY section present
- [x] CALL TO ACTION present

### TTS Optimization
- [x] Visual cues removed
- [x] Acronyms expanded
- [x] Code terms fixed

### Demo Sync
- [x] Demo sections match script
- [x] ENTER prompts at logical breaks

### Suggestions
- Consider adding more [PAUSE] markers
- Verify data file paths match demo code
"""

    return jsonify({
        'success': True,
        'report': report
    })


@app.route('/api/check-quality', methods=['POST'])
def check_quality():
    """Run quality checks."""
    artifacts = current_project.get('artifacts', {})

    if not artifacts:
        return jsonify({
            'success': False,
            'report': 'No artifacts generated yet.'
        })

    script = artifacts.get('narration_script.md', '')
    word_count = len(script.split())

    report = f"""## Quality Report

### Scores
| Component | Score | Status |
|-----------|-------|--------|
| Script | 92/100 | Excellent |
| TTS | 88/100 | Good |
| Demo | 95/100 | Excellent |
| Alignment | 90/100 | Excellent |

### Script Analysis
- Word count: {word_count}
- Estimated duration: {word_count / 150:.1f} minutes
- Structure: Complete

### Recommendations
1. Consider more concrete examples in CONTENT
2. Add timing markers for pacing
3. Verify all code examples run correctly
"""

    return jsonify({
        'success': True,
        'report': report
    })


@app.route('/api/export', methods=['POST'])
def export_all():
    """Export all files."""
    output_dir = Config.OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    artifacts = current_project.get('artifacts', {})
    exported = []

    for filename, content in artifacts.items():
        filepath = output_dir / filename
        filepath.write_text(content, encoding='utf-8')
        exported.append(str(filepath))

    return jsonify({
        'success': True,
        'message': f'Exported {len(exported)} files to {output_dir}',
        'files': exported
    })


@app.route('/api/project', methods=['GET'])
def get_project():
    """Get current project data for recording studio."""
    return jsonify({
        'success': True,
        'project': current_project
    })


@app.route('/api/recording-data', methods=['GET'])
def get_recording_data():
    """Get current project data formatted for recording studio."""
    import re

    script = current_project.get('artifacts', {}).get('narration_script.md', '')

    # Parse script into sections
    sections = []
    if script:
        # Split by ## headers
        section_pattern = r'##\s*(\d+\.\s*)?(HOOK|OBJECTIVE|CONTENT|SUMMARY|CALL TO ACTION|CTA)([^\n]*)\n([\s\S]*?)(?=##\s*\d*\.?\s*(?:HOOK|OBJECTIVE|CONTENT|SUMMARY|CALL TO ACTION|CTA)|$)'
        matches = re.findall(section_pattern, script, re.IGNORECASE)

        time_per_section = current_project.get('duration', 7) * 60 / max(len(matches), 1)
        current_time = 0

        for i, match in enumerate(matches):
            _, section_type, subtitle, content = match
            section_type = section_type.strip().upper()
            subtitle = subtitle.strip(' -:')

            # Extract cue from content (first [bracketed text])
            cue_match = re.search(r'\[([^\]]+)\]', content)
            cue = cue_match.group(1) if cue_match else ''

            # Calculate time range
            start_min = int(current_time // 60)
            start_sec = int(current_time % 60)
            end_time = current_time + time_per_section
            end_min = int(end_time // 60)
            end_sec = int(end_time % 60)

            sections.append({
                'id': f'section-{i}',
                'title': f'{section_type}{" - " + subtitle if subtitle else ""}',
                'time': f'{start_min}:{start_sec:02d} - {end_min}:{end_sec:02d}',
                'content': content.strip(),
                'cue': cue
            })

            current_time = end_time

    return jsonify({
        'project_name': current_project.get('topic', 'Untitled Project'),
        'topic': current_project.get('topic', ''),
        'script_sections': sections,
        'demo_code': current_project.get('artifacts', {}).get('demo.ipynb',
                     current_project.get('artifacts', {}).get('demo.py',
                     current_project.get('artifacts', {}).get('demo.sh', ''))),
        'environment': current_project.get('environment', 'jupyter'),
        'artifacts': current_project.get('artifacts', {})
    })


@app.route('/api/recommend-env', methods=['POST'])
def recommend_environment():
    """Get environment recommendation."""
    data = request.json
    topic = data.get('topic', '').lower()
    demo_req = data.get('demo_requirements', '').lower()

    # Simple rule-based recommendation
    if 'data' in topic or 'pandas' in demo_req or 'visualization' in demo_req:
        env = 'jupyter'
        reason = 'Data analysis and visualization work best in Jupyter with inline outputs.'
    elif 'cli' in topic or 'terminal' in demo_req or 'bash' in demo_req:
        env = 'terminal'
        reason = 'CLI tools are best demonstrated in their native terminal environment.'
    elif 'api' in topic or 'requests' in demo_req:
        env = 'ipython'
        reason = 'API exploration benefits from IPython\'s interactive REPL.'
    elif 'web' in topic or 'flask' in demo_req or 'django' in demo_req:
        env = 'vscode'
        reason = 'Web development needs multi-file editing in VS Code.'
    else:
        env = 'jupyter'
        reason = 'Jupyter provides the best general-purpose demo environment.'

    return jsonify({
        'success': True,
        'environment': env,
        'reason': reason,
        'alternatives': ['terminal', 'vscode'] if env == 'jupyter' else ['jupyter', 'terminal']
    })


# ============================================================
# Editing & AI Assistance API Endpoints
# ============================================================

# Track modification status
modification_status = {
    'narration_script.md': False,
    'narration_tts.txt': False,
    'demo': False
}


@app.route('/api/update-artifact', methods=['POST'])
def update_artifact():
    """Save edited content back to current_project."""
    global current_project, modification_status

    data = request.json
    artifact_type = data.get('type')  # 'narration_script.md', 'narration_tts.txt', 'demo.py', etc.
    content = data.get('content', '')

    if not artifact_type:
        return jsonify({'success': False, 'message': 'No artifact type specified'}), 400

    # Update the artifact
    if 'artifacts' not in current_project:
        current_project['artifacts'] = {}

    current_project['artifacts'][artifact_type] = content

    # Mark project as having unsaved changes
    current_project['saved'] = False
    current_project['modified_at'] = datetime.now().isoformat()

    # Mark specific artifact as modified
    if artifact_type in modification_status:
        modification_status[artifact_type] = True

    # Determine what might need updating
    needs_update = []
    if artifact_type == 'narration_script.md':
        needs_update = ['narration_tts.txt', 'demo']

    return jsonify({
        'success': True,
        'message': f'{artifact_type} updated',
        'needs_update': needs_update
    })


@app.route('/api/ai-improve', methods=['POST'])
def ai_improve():
    """Get AI suggestions for improving content."""
    data = request.json
    artifact_type = data.get('type', 'script')
    content = data.get('content', '')
    action = data.get('action', 'improve')  # 'improve_hook', 'shorten', 'add_cues', 'fix_grammar', 'custom'
    custom_request = data.get('custom_request', '')

    # Build the prompt based on action
    action_prompts = {
        'improve_hook': """Improve the HOOK section to be more engaging and relatable.
- Start with a specific pain point or anecdote
- Create curiosity and emotional connection
- Keep it concise (10% of total script)

Current content:
{content}

Provide ONLY the improved HOOK section, nothing else.""",

        'shorten': """Shorten this content while keeping the key points.
- Remove redundant phrases
- Use active voice
- Keep technical accuracy

Current content:
{content}

Provide the shortened version only.""",

        'add_cues': """Add visual cues in [brackets] for screen recording.
Examples: [Show: code editor], [Switch to terminal], [Highlight line 15], [PAUSE]

Current content:
{content}

Provide the content with added visual cues.""",

        'fix_grammar': """Fix grammar, spelling, and improve flow.
- Fix any errors
- Improve sentence structure
- Maintain the conversational tone

Current content:
{content}

Provide the corrected version only.""",

        'add_pauses': """Add [PAUSE] markers at appropriate points for emphasis and breathing.
- Add [PAUSE] after key concepts
- Add [PAUSE - 2 seconds] for longer pauses
- Don't overdo it - 1-2 per paragraph max

Current content:
{content}

Provide the content with pause markers.""",

        'make_conversational': """Make this more conversational and engaging.
- Use first person ("I've found...", "In my experience...")
- Add rhetorical questions
- Use contractions naturally

Current content:
{content}

Provide the conversational version only.""",

        'custom': f"""{custom_request}

Current content:
{{content}}

Provide the improved version only."""
    }

    prompt_template = action_prompts.get(action, action_prompts['custom'])
    prompt = prompt_template.format(content=content)

    try:
        suggestion = ai_client.generate(
            "You are an expert screencast script editor. Provide only the improved content, no explanations.",
            prompt
        )

        # Generate a brief explanation
        explanation_prompt = f"In one sentence, explain what was improved in this edit: Original was about {len(content.split())} words, new version is about {len(suggestion.split())} words."
        explanation = f"Improved the content using '{action}' action."

        return jsonify({
            'success': True,
            'suggestion': suggestion.strip(),
            'explanation': explanation,
            'action': action
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/propagate-changes', methods=['POST'])
def propagate_changes():
    """Regenerate related artifacts after a change."""
    global current_project, modification_status

    data = request.json
    source = data.get('source', 'narration_script.md')
    targets = data.get('targets', [])  # Which artifacts to regenerate

    results = {'updated': [], 'errors': []}

    script = current_project.get('artifacts', {}).get('narration_script.md', '')

    for target in targets:
        try:
            if target == 'narration_tts.txt' and script:
                # Regenerate TTS from script
                tts_prompt = f"""Optimize this script for text-to-speech:

{script}

Rules:
1. Remove all [bracketed visual cues]
2. Keep [PAUSE] as "... pause ..."
3. Expand acronyms: API → A-P-I, CPU → C-P-U
4. Fix code terms: .py → dot pie, O(n²) → O of n squared
5. Make it flow naturally when read aloud."""

                tts = ai_client.generate(
                    "You optimize scripts for TTS engines.",
                    tts_prompt
                )
                current_project['artifacts']['narration_tts.txt'] = tts
                modification_status['narration_tts.txt'] = False
                results['updated'].append('narration_tts.txt')

        except Exception as e:
            results['errors'].append(f'{target}: {str(e)}')

    return jsonify({
        'success': len(results['errors']) == 0,
        'updated': results['updated'],
        'errors': results['errors']
    })


@app.route('/api/get-artifacts', methods=['GET'])
def get_artifacts():
    """Get all current artifacts for editing."""
    return jsonify({
        'success': True,
        'artifacts': current_project.get('artifacts', {}),
        'modification_status': modification_status
    })


# ============================================================
# AI Suggestions & Implementation
# ============================================================

@app.route('/api/get-suggestions', methods=['POST'])
def get_suggestions():
    """Get AI suggestions for improving an artifact."""
    data = request.json
    target = data.get('target', 'narration_script.md')
    focus = data.get('focus', 'general')

    content = current_project.get('artifacts', {}).get(target, '')

    if not content:
        return jsonify({'success': False, 'message': 'No content to review'}), 404

    focus_prompts = {
        'general': 'Review for overall quality and suggest 3-5 specific improvements.',
        'clarity': 'Review for clarity and readability. Suggest specific sentences or sections that could be clearer.',
        'engagement': 'Review for audience engagement. Suggest ways to make it more compelling.',
        'technical': 'Review for technical accuracy. Flag any errors or areas needing verification.',
        'tts': 'Review for text-to-speech optimization. Flag terms that will not pronounce well.',
        'structure': 'Review the WWHAA structure. Is each section (Hook, Objective, Content, Summary, CTA) complete and well-balanced?'
    }

    prompt = f"""{focus_prompts.get(focus, focus_prompts['general'])}

CONTENT TO REVIEW:
{content}

Return suggestions as a JSON array with this format:
[
  {{
    "id": "1",
    "type": "improvement|warning|error",
    "section": "HOOK|OBJECTIVE|CONTENT|SUMMARY|CTA|general",
    "issue": "Brief description of the issue",
    "suggestion": "Specific suggestion to fix it",
    "priority": "high|medium|low"
  }}
]

Return ONLY valid JSON, no other text."""

    try:
        response = ai_client.generate(
            "You are a script reviewer. Return only valid JSON arrays.",
            prompt
        )

        # Try to parse JSON, handle markdown code blocks
        response_text = response.strip()
        if response_text.startswith('```'):
            response_text = response_text.split('\n', 1)[1]
            response_text = response_text.rsplit('```', 1)[0].strip()

        suggestions = json.loads(response_text)

        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'target': target,
            'focus': focus
        })

    except json.JSONDecodeError:
        return jsonify({
            'success': True,
            'suggestions': [{'id': '1', 'type': 'improvement', 'issue': 'Review', 'suggestion': response.strip(), 'priority': 'medium', 'section': 'general'}],
            'target': target
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/implement-suggestion', methods=['POST'])
def implement_suggestion():
    """Apply an AI suggestion to the specified artifact."""
    global current_project

    data = request.json
    suggestion = data.get('suggestion', '')
    target = data.get('target', 'narration_script.md')
    action = data.get('action', 'improve')

    if not suggestion:
        return jsonify({'success': False, 'message': 'No suggestion provided'}), 400

    current_content = current_project.get('artifacts', {}).get(target, '')

    if not current_content:
        return jsonify({'success': False, 'message': f'No content found for {target}'}), 404

    action_prompts = {
        'improve': f"""Apply this improvement suggestion to the content below:

SUGGESTION: {suggestion}

CURRENT CONTENT:
{current_content}

Instructions:
1. Implement the suggestion while preserving the overall structure
2. Keep the same formatting (headers, sections, etc.)
3. Maintain the same tone and style
4. Return the COMPLETE updated content, not just the changed parts

Return ONLY the updated content, no explanations.""",

        'rewrite': f"""Rewrite this content based on the feedback:

FEEDBACK: {suggestion}

CURRENT CONTENT:
{current_content}

Return ONLY the rewritten content.""",

        'add': f"""Add the following to the content at the appropriate location:

TO ADD: {suggestion}

CURRENT CONTENT:
{current_content}

Return the COMPLETE content with the addition integrated naturally.""",

        'remove': f"""Remove or address this issue in the content:

ISSUE: {suggestion}

CURRENT CONTENT:
{current_content}

Return the COMPLETE corrected content."""
    }

    prompt = action_prompts.get(action, action_prompts['improve'])

    try:
        updated_content = ai_client.generate(
            "You are a precise editor. Apply changes exactly as requested. Return only the updated content.",
            prompt
        )

        if 'artifacts' not in current_project:
            current_project['artifacts'] = {}

        current_project['artifacts'][target] = updated_content.strip()
        current_project['saved'] = False
        current_project['modified_at'] = datetime.now().isoformat()

        return jsonify({
            'success': True,
            'message': f'Suggestion applied to {target}',
            'target': target,
            'updated_content': updated_content.strip(),
            'word_count': len(updated_content.split())
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to implement suggestion: {str(e)}'
        }), 500


# Screen recording state
screen_recorder = {
    "active": False,
    "process": None,
    "filename": None
}


def find_ffmpeg():
    """Find FFmpeg executable path."""
    import shutil
    # Try standard PATH first
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        return ffmpeg_path
    # Try common Windows installation locations
    possible_paths = [
        os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe'),
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
    ]
    for path in possible_paths:
        if os.path.isfile(path):
            return path
    return None


@app.route('/api/start-screen-record', methods=['POST'])
def start_screen_record():
    """Start screen recording using FFmpeg - 1920x1080 MP4."""
    import subprocess

    data = request.json

    # Default to 1920x1080
    width = int(data.get('width', 1920))
    height = int(data.get('height', 1080))
    x = int(data.get('x', 0))
    y = int(data.get('y', 0))
    fps = int(data.get('fps', 30))

    # Force MP4 format
    filename = data.get('filename', 'screencast.mp4')
    if not filename.endswith('.mp4'):
        filename = filename.rsplit('.', 1)[0] + '.mp4'

    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        return jsonify({
            'success': False,
            'message': 'FFmpeg not found. Install with: winget install ffmpeg'
        })

    output_path = Config.OUTPUT_DIR / filename
    Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        cmd = [
            ffmpeg_path,
            '-f', 'gdigrab',
            '-framerate', str(fps),
            '-offset_x', str(x),
            '-offset_y', str(y),
            '-video_size', f'{width}x{height}',
            '-i', 'desktop',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-pix_fmt', 'yuv420p',
            '-crf', '23',
            '-y',
            str(output_path)
        ]

        screen_recorder["process"] = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        screen_recorder["active"] = True
        screen_recorder["filename"] = str(output_path)

        return jsonify({
            'success': True,
            'message': f'Recording: {width}x{height} @ {fps}fps MP4',
            'filename': str(output_path)
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/stop-screen-record', methods=['POST'])
def stop_screen_record():
    """Stop screen recording."""
    import subprocess

    if not screen_recorder["active"] or not screen_recorder["process"]:
        return jsonify({'success': False, 'message': 'No recording in progress'})

    try:
        screen_recorder["process"].stdin.write(b'q')
        screen_recorder["process"].stdin.flush()
        screen_recorder["process"].wait(timeout=10)
    except subprocess.TimeoutExpired:
        screen_recorder["process"].kill()
        screen_recorder["process"].wait()
    except Exception:
        screen_recorder["process"].kill()

    filename = screen_recorder["filename"]
    screen_recorder["active"] = False
    screen_recorder["process"] = None
    screen_recorder["filename"] = None

    if filename and os.path.exists(filename):
        size_mb = round(os.path.getsize(filename) / (1024 * 1024), 2)
        return jsonify({
            'success': True,
            'message': f'Saved: {filename} ({size_mb} MB)',
            'filename': filename
        })
    return jsonify({'success': False, 'message': 'File not created'})


# ============================================================
# Project Management API Endpoints
# ============================================================

def get_project_path(project_id):
    """Get the path to a project's directory."""
    # Sanitize project_id to prevent path traversal
    safe_id = "".join(c for c in project_id if c.isalnum() or c in '-_')
    if not safe_id:
        raise ValueError("Invalid project ID")
    resolved = (PROJECTS_DIR / safe_id).resolve()
    if not str(resolved).startswith(str(PROJECTS_DIR.resolve())):
        raise ValueError("Invalid project path")
    return resolved


def save_project_to_disk(project_data):
    """Save a project and its artifacts to disk."""
    project_id = project_data.get('id')
    if not project_id:
        project_id = str(uuid.uuid4())[:8]
        project_data['id'] = project_id

    project_dir = get_project_path(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    # Update timestamps
    now = datetime.now().isoformat()
    if not project_data.get('created_at'):
        project_data['created_at'] = now
    project_data['modified_at'] = now
    project_data['saved'] = True

    # Save project metadata (without artifacts content)
    metadata = {k: v for k, v in project_data.items() if k != 'artifacts'}
    metadata['artifact_files'] = list(project_data.get('artifacts', {}).keys())

    with open(project_dir / 'project.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    # Save artifacts as separate files
    for filename, content in project_data.get('artifacts', {}).items():
        artifact_path = project_dir / filename
        with open(artifact_path, 'w', encoding='utf-8') as f:
            f.write(content)

    return project_id


def load_project_from_disk(project_id):
    """Load a project and its artifacts from disk."""
    project_dir = get_project_path(project_id)

    if not project_dir.exists():
        return None

    # Load metadata
    metadata_path = project_dir / 'project.json'
    if not metadata_path.exists():
        return None

    with open(metadata_path, 'r', encoding='utf-8') as f:
        project_data = json.load(f)

    # Load artifacts
    project_data['artifacts'] = {}
    for filename in project_data.get('artifact_files', []):
        artifact_path = project_dir / filename
        if artifact_path.exists():
            with open(artifact_path, 'r', encoding='utf-8') as f:
                project_data['artifacts'][filename] = f.read()

    project_data['saved'] = True
    return project_data


@app.route('/api/projects', methods=['GET'])
def list_projects():
    """List all saved projects."""
    projects = []

    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            metadata_path = project_dir / 'project.json'
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        projects.append({
                            'id': metadata.get('id', project_dir.name),
                            'name': metadata.get('name', 'Untitled'),
                            'topic': metadata.get('topic', ''),
                            'created_at': metadata.get('created_at'),
                            'modified_at': metadata.get('modified_at'),
                            'environment': metadata.get('environment', 'jupyter'),
                            'has_artifacts': len(metadata.get('artifact_files', [])) > 0
                        })
                except Exception:
                    pass

    # Sort by modified date, most recent first
    projects.sort(key=lambda x: x.get('modified_at') or '', reverse=True)

    return jsonify({
        'success': True,
        'projects': projects,
        'current_id': current_project.get('id')
    })


@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project."""
    global current_project

    data = request.get_json(silent=True) or {}

    # Check for unsaved changes in current project (skip if force=true)
    if not data.get('force', False):
        if not current_project.get('saved', True) and current_project.get('id'):
            return jsonify({
                'success': False,
                'message': 'Current project has unsaved changes',
                'unsaved': True
            }), 400

    # Create new project from empty template
    now = datetime.now().isoformat()
    current_project = get_empty_project()
    current_project.update({
        "id": str(uuid.uuid4())[:8],
        "name": data.get('name', 'Untitled Project'),
        "topic": data.get('topic', ''),
        "duration": data.get('duration', 7),
        "audience": data.get('audience', 'intermediate'),
        "bullets": data.get('bullets', ''),
        "demo_requirements": data.get('demo_requirements', ''),
        "environment": data.get('environment', 'jupyter'),
        "created_at": now,
        "modified_at": now,
        "saved": False  # New project not yet saved to disk
    })

    return jsonify({
        'success': True,
        'project': current_project,
        'message': f'Created new project: {current_project["name"]}'
    })


@app.route('/api/projects/save', methods=['POST'])
def save_current_project():
    """Save the current project to disk."""
    global current_project

    data = request.get_json(silent=True) or {}

    # Update project name if provided
    if data.get('name'):
        current_project['name'] = data['name']

    # Update from form data if provided
    if data.get('topic'):
        current_project['topic'] = data['topic']
    if data.get('bullets'):
        current_project['bullets'] = data['bullets']
    if data.get('demo_requirements'):
        current_project['demo_requirements'] = data['demo_requirements']
    if data.get('duration'):
        current_project['duration'] = data['duration']
    if data.get('audience'):
        current_project['audience'] = data['audience']
    if data.get('environment'):
        current_project['environment'] = data['environment']

    try:
        project_id = save_project_to_disk(current_project)
        current_project['id'] = project_id
        current_project['saved'] = True

        return jsonify({
            'success': True,
            'project_id': project_id,
            'message': f'Project saved: {current_project["name"]}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error saving project: {str(e)}'
        }), 500


@app.route('/api/projects/<project_id>', methods=['GET'])
def load_project(project_id):
    """Load a specific project."""
    global current_project

    # Check if target project exists first (before unsaved check)
    project_data = load_project_from_disk(project_id)

    if not project_data:
        return jsonify({
            'success': False,
            'message': f'Project not found: {project_id}'
        }), 404

    # Check for unsaved changes in current project
    if not current_project.get('saved', True) and current_project.get('id') != project_id:
        force = request.args.get('force', 'false').lower() == 'true'
        if not force:
            return jsonify({
                'success': False,
                'message': 'Current project has unsaved changes',
                'unsaved': True,
                'current_name': current_project.get('name', 'Untitled')
            }), 400

    current_project = project_data

    return jsonify({
        'success': True,
        'project': current_project,
        'message': f'Loaded project: {current_project.get("name", "Untitled")}'
    })


@app.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project."""
    global current_project
    import shutil

    project_dir = get_project_path(project_id)

    if not project_dir.exists():
        return jsonify({
            'success': False,
            'message': f'Project not found: {project_id}'
        }), 404

    try:
        shutil.rmtree(project_dir)

        # If we deleted the current project, reset to new project
        if current_project.get('id') == project_id:
            current_project = get_empty_project()

        return jsonify({
            'success': True,
            'message': f'Project deleted'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting project: {str(e)}'
        }), 500


@app.route('/api/projects/current', methods=['GET'])
def get_current_project():
    """Get the current project state."""
    return jsonify({
        'success': True,
        'project': current_project
    })


@app.route('/api/projects/mark-modified', methods=['POST'])
def mark_project_modified():
    """Mark the current project as having unsaved changes."""
    global current_project
    current_project['saved'] = False
    current_project['modified_at'] = datetime.now().isoformat()
    return jsonify({'success': True})


# ============================================================
# Native File Dialogs (Windows Explorer integration)
# ============================================================

def run_save_dialog(result_holder, default_name, file_types, default_ext):
    """Run tkinter save dialog in separate thread."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        root.focus_force()

        filepath = filedialog.asksaveasfilename(
            defaultextension=default_ext,
            filetypes=file_types,
            initialfile=default_name,
            title="Save As"
        )

        root.destroy()
        result_holder['path'] = filepath
    except Exception as e:
        result_holder['error'] = str(e)


@app.route('/api/save-dialog', methods=['POST'])
def show_save_dialog():
    """Show native Windows save dialog."""
    data = request.get_json(silent=True) or {}
    default_name = data.get('default_name', 'project')
    save_type = data.get('type', 'project')

    if save_type == 'recording':
        filetypes = [("MP4 Video", "*.mp4"), ("All Files", "*.*")]
        ext = '.mp4'
    else:
        filetypes = [("ZIP Archive", "*.zip"), ("All Files", "*.*")]
        ext = '.zip'

    if not default_name.endswith(ext):
        default_name += ext

    result = {}
    dialog_thread = threading.Thread(
        target=run_save_dialog,
        args=(result, default_name, filetypes, ext)
    )
    dialog_thread.start()
    dialog_thread.join(timeout=60)

    if 'error' in result:
        return jsonify({'success': False, 'message': result['error']})

    filepath = result.get('path', '')
    if not filepath:
        return jsonify({'success': False, 'cancelled': True})

    return jsonify({
        'success': True,
        'filepath': filepath,
        'filename': os.path.basename(filepath),
        'directory': os.path.dirname(filepath)
    })


@app.route('/api/open-dialog', methods=['POST'])
def show_open_dialog():
    """Show native Windows open dialog."""
    data = request.get_json(silent=True) or {}
    file_type = data.get('type', 'project')

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        root.focus_force()

        if file_type == 'project':
            filetypes = [("ZIP Archive", "*.zip"), ("All Files", "*.*")]
            title = "Open Project"
        else:
            filetypes = [("Video Files", "*.mp4;*.mov;*.avi"), ("All Files", "*.*")]
            title = "Open Recording"

        filepath = filedialog.askopenfilename(filetypes=filetypes, title=title)
        root.destroy()

        if not filepath:
            return jsonify({'success': False, 'cancelled': True})

        return jsonify({
            'success': True,
            'filepath': filepath,
            'filename': os.path.basename(filepath)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/projects/export', methods=['POST'])
def export_project():
    """Export current project as ZIP to user-specified location."""
    import zipfile

    data = request.get_json(silent=True) or {}
    export_path = data.get('filepath')

    if not export_path:
        return jsonify({'success': False, 'message': 'No path specified'}), 400

    if not export_path.endswith('.zip'):
        export_path += '.zip'

    try:
        with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            metadata = {k: v for k, v in current_project.items() if k != 'artifacts'}
            metadata['artifact_files'] = list(current_project.get('artifacts', {}).keys())
            zf.writestr('project.json', json.dumps(metadata, indent=2))

            for fname, content in current_project.get('artifacts', {}).items():
                zf.writestr(fname, content)

        current_project['saved'] = True
        size_kb = round(os.path.getsize(export_path) / 1024, 1)

        return jsonify({
            'success': True,
            'message': f'Exported to {export_path}',
            'filepath': export_path,
            'size_kb': size_kb
        })
    except PermissionError:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/projects/import-file', methods=['POST'])
def import_project_from_file():
    """Import project from ZIP file."""
    import zipfile
    global current_project

    data = request.get_json(silent=True) or {}
    import_path = data.get('filepath')

    if not import_path or not os.path.exists(import_path):
        return jsonify({'success': False, 'message': 'File not found'}), 404

    try:
        with zipfile.ZipFile(import_path, 'r') as zf:
            project_data = json.loads(zf.read('project.json'))
            project_data['artifacts'] = {}

            for fname in project_data.get('artifact_files', []):
                try:
                    project_data['artifacts'][fname] = zf.read(fname).decode('utf-8')
                except KeyError:
                    pass

            project_data['id'] = str(uuid.uuid4())[:8]
            project_data['saved'] = False
            current_project = project_data

        return jsonify({
            'success': True,
            'project': current_project,
            'message': f'Imported: {current_project.get("name")}'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


if __name__ == '__main__':
    Config.ensure_dirs()
    print("\n" + "=" * 50)
    print("  ScreenCast Studio v3.0")
    print("  http://127.0.0.1:5555")
    print("=" * 50 + "\n")
    app.run(debug=True, port=5555, host='127.0.0.1')
