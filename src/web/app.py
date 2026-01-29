"""Flask web application for ScreenCast Studio."""

import os
from flask import Flask, render_template, request, jsonify, send_file
from pathlib import Path
import tempfile
import json

from ..generators.script_generator import ScriptGenerator
from ..generators.tts_optimizer import TTSOptimizer
from ..generators.demo_generator import DemoGenerator
from ..generators.asset_generator import AssetGenerator

app = Flask(__name__,
            template_folder=str(Path(__file__).parent / 'templates'),
            static_folder=str(Path(__file__).parent / 'static'))

# Initialize generators
script_generator = ScriptGenerator()
tts_optimizer = TTSOptimizer()
demo_generator = DemoGenerator()
asset_generator = AssetGenerator()


@app.route('/')
def index():
    """Home page."""
    return render_template('index.html')


@app.route('/api/generate-script', methods=['POST'])
def api_generate_script():
    """Generate narration script from bullet points."""
    try:
        data = request.json
        bullets = data.get('bullets', '')
        duration = int(data.get('duration', 7))
        topic = data.get('topic', None)

        if not bullets.strip():
            return jsonify({'error': 'Please provide bullet points'}), 400

        script = script_generator.generate(
            bullets=bullets,
            duration_minutes=duration,
            topic=topic
        )

        return jsonify({
            'success': True,
            'script': script.to_markdown(),
            'total_words': script.total_words,
            'estimated_duration': round(script.estimated_duration_minutes, 1),
            'sections': [
                {
                    'name': s.name,
                    'word_count': s.word_count,
                    'duration_seconds': s.duration_seconds
                }
                for s in script.sections
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/optimize-tts', methods=['POST'])
def api_optimize_tts():
    """Optimize script for TTS."""
    try:
        data = request.json
        script = data.get('script', '')
        format_type = data.get('format', 'plain')

        if not script.strip():
            return jsonify({'error': 'Please provide a script'}), 400

        optimized = tts_optimizer.optimize(script)

        if format_type == 'ssml':
            optimized = tts_optimizer.add_ssml_markers(optimized)
        elif format_type == 'elevenlabs':
            optimized = tts_optimizer.add_elevenlabs_markers(optimized)

        changes = tts_optimizer.get_changes_report(script, optimized)

        return jsonify({
            'success': True,
            'optimized': optimized,
            'changes': [{'original': orig, 'replacement': repl} for orig, repl in changes]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-demo', methods=['POST'])
def api_generate_demo():
    """Generate interactive Python demo."""
    try:
        data = request.json
        script = data.get('script', '')
        requirements = data.get('requirements', '')
        title = data.get('title', 'Demo')
        use_ai = data.get('use_ai', False)

        if not script.strip():
            return jsonify({'error': 'Please provide a script'}), 400

        if use_ai:
            demo = demo_generator.generate_with_ai(script, requirements, title)
        else:
            demo = demo_generator.generate(script, requirements, title)

        return jsonify({
            'success': True,
            'code': demo.code,
            'required_files': demo.required_files,
            'sections_count': len(demo.sections)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-asset', methods=['POST'])
def api_generate_asset():
    """Generate supporting assets."""
    try:
        data = request.json
        asset_type = data.get('type', 'csv')
        config = data.get('config', {})

        if asset_type == 'terminal':
            validation_results = config.get('validation_results', [
                {'check': 'Schema validation', 'status': 'pass', 'message': 'All columns present'},
                {'check': 'Null check', 'status': 'fail', 'message': '3 rows with null values'},
                {'check': 'Type validation', 'status': 'pass', 'message': 'All types match'},
            ])
            asset = asset_generator.generate_terminal_output(validation_results)

        elif asset_type == 'csv':
            columns = config.get('columns', ['date', 'id', 'amount', 'category'])
            rows = config.get('rows', 10)
            include_issues = config.get('include_issues', True)
            asset = asset_generator.generate_sample_csv(columns, rows, include_issues)

        elif asset_type == 'yaml':
            asset = asset_generator.generate_lineage_yaml(
                source_table=config.get('source', 'raw_events'),
                transformations=config.get('transformations', [
                    {'name': 'filter_nulls', 'description': 'Remove null rows'},
                    {'name': 'aggregate', 'description': 'Group by category'},
                ]),
                target_table=config.get('target', 'analytics_events'),
            )

        elif asset_type == 'html':
            sections = config.get('sections', [
                {
                    'title': 'Data Quality Checks',
                    'status': 'fail',
                    'items': [
                        {'name': 'Completeness', 'status': 'pass', 'message': '100% complete'},
                        {'name': 'Uniqueness', 'status': 'fail', 'message': '3 duplicates found'},
                    ]
                }
            ])
            asset = asset_generator.generate_html_report(
                title=config.get('title', 'Validation Report'),
                sections=sections,
            )
        else:
            return jsonify({'error': f'Unknown asset type: {asset_type}'}), 400

        return jsonify({
            'success': True,
            'filename': asset.filename,
            'content': asset.content,
            'file_type': asset.file_type
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download', methods=['POST'])
def api_download():
    """Download generated content as a file."""
    try:
        data = request.json
        content = data.get('content', '')
        filename = data.get('filename', 'output.txt')

        # Create temp file
        temp_dir = tempfile.mkdtemp()
        filepath = Path(temp_dir) / filename
        filepath.write_text(content, encoding='utf-8')

        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run_app(host='127.0.0.1', port=5000, debug=True):
    """Run the Flask application."""
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_app()
