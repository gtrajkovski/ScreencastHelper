"""Command-line interface for ScreenCast Studio."""

import json
import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..generators.script_generator import ScriptGenerator
from ..generators.tts_optimizer import TTSOptimizer
from ..generators.demo_generator import DemoGenerator
from ..generators.asset_generator import AssetGenerator
from ..config import Config

app = typer.Typer(
    name="screencast-studio",
    help="AI-powered screencast production assistant"
)
console = Console()


@app.command()
def generate_script(
    bullets_file: Path = typer.Argument(..., help="Path to bullet points file"),
    output: Path = typer.Option(Path("script.md"), help="Output file path"),
    duration: int = typer.Option(7, help="Target duration in minutes"),
    topic: str = typer.Option(None, help="Topic/title for context"),
):
    """Generate narration script from bullet points."""

    if not bullets_file.exists():
        console.print(f"[red]Error: File not found: {bullets_file}[/red]")
        raise typer.Exit(1)

    bullets = bullets_file.read_text(encoding='utf-8')

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating script...", total=None)

        generator = ScriptGenerator()
        script = generator.generate(
            bullets=bullets,
            duration_minutes=duration,
            topic=topic
        )

        progress.update(task, completed=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(script.to_markdown(), encoding='utf-8')

    console.print(Panel(
        f"[green]Script generated successfully![/green]\n\n"
        f"Output: {output}\n"
        f"Words: {script.total_words}\n"
        f"Estimated duration: {script.estimated_duration_minutes:.1f} minutes",
        title="Script Generation Complete"
    ))


@app.command()
def optimize_tts(
    script_file: Path = typer.Argument(..., help="Path to script file"),
    output: Path = typer.Option(Path("script_tts.txt"), help="Output file path"),
    format: str = typer.Option("plain", help="Output format: plain, ssml, elevenlabs"),
):
    """Optimize script for text-to-speech."""

    if not script_file.exists():
        console.print(f"[red]Error: File not found: {script_file}[/red]")
        raise typer.Exit(1)

    script = script_file.read_text(encoding='utf-8')
    optimizer = TTSOptimizer()

    optimized = optimizer.optimize(script)

    if format == "ssml":
        optimized = optimizer.add_ssml_markers(optimized)
    elif format == "elevenlabs":
        optimized = optimizer.add_elevenlabs_markers(optimized)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(optimized, encoding='utf-8')

    # Show changes
    changes = optimizer.get_changes_report(script, optimized)

    console.print(Panel(
        f"[green]TTS optimization complete![/green]\n\n"
        f"Output: {output}\n"
        f"Changes made: {len(changes)}",
        title="TTS Optimization"
    ))

    if changes:
        console.print("\n[bold]Replacements made:[/bold]")
        for original, replacement in changes[:10]:  # Show first 10
            console.print(f"  {original} -> {replacement}")


@app.command()
def generate_demo(
    script_file: Path = typer.Argument(..., help="Path to script file"),
    requirements: str = typer.Argument(..., help="Demo requirements description"),
    output: Path = typer.Option(Path("demo.py"), help="Output file path"),
    title: str = typer.Option("Demo", help="Demo title"),
    use_ai: bool = typer.Option(False, help="Use AI for sophisticated demo generation"),
):
    """Generate interactive Python demo from script."""

    if not script_file.exists():
        console.print(f"[red]Error: File not found: {script_file}[/red]")
        raise typer.Exit(1)

    script = script_file.read_text(encoding='utf-8')

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating demo...", total=None)

        generator = DemoGenerator()

        if use_ai:
            demo = generator.generate_with_ai(script, requirements, title)
        else:
            demo = generator.generate(script, requirements, title, output.name)

        progress.update(task, completed=True)

    demo.save(str(output))

    console.print(Panel(
        f"[green]Demo generated successfully![/green]\n\n"
        f"Output: {output}\n"
        f"Required files: {', '.join(demo.required_files) or 'None'}",
        title="Demo Generation Complete"
    ))


@app.command()
def generate_assets(
    asset_type: str = typer.Argument(..., help="Asset type: terminal, csv, yaml, html"),
    output_dir: Path = typer.Option(Path("assets"), help="Output directory"),
    config_file: Path = typer.Option(None, help="Optional JSON config for asset"),
):
    """Generate supporting assets (terminal output, CSV, YAML, HTML)."""

    output_dir.mkdir(parents=True, exist_ok=True)
    generator = AssetGenerator()

    # Load config if provided
    config = {}
    if config_file and config_file.exists():
        config = json.loads(config_file.read_text(encoding='utf-8'))

    if asset_type == "terminal":
        validation_results = config.get('validation_results', [
            {'check': 'Schema validation', 'status': 'pass', 'message': 'All columns present'},
            {'check': 'Null check', 'status': 'fail', 'message': '3 rows with null values'},
            {'check': 'Type validation', 'status': 'pass', 'message': 'All types match'},
        ])
        asset = generator.generate_terminal_output(validation_results)

    elif asset_type == "csv":
        columns = config.get('columns', ['date', 'id', 'amount', 'category'])
        rows = config.get('rows', 10)
        asset = generator.generate_sample_csv(columns, rows)

    elif asset_type == "yaml":
        asset = generator.generate_lineage_yaml(
            source_table=config.get('source', 'raw_events'),
            transformations=config.get('transformations', [
                {'name': 'filter_nulls', 'description': 'Remove null rows'},
                {'name': 'aggregate', 'description': 'Group by category'},
            ]),
            target_table=config.get('target', 'analytics_events'),
        )

    elif asset_type == "html":
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
        asset = generator.generate_html_report(
            title=config.get('title', 'Validation Report'),
            sections=sections,
        )
    else:
        console.print(f"[red]Unknown asset type: {asset_type}[/red]")
        raise typer.Exit(1)

    filepath = asset.save(output_dir)

    console.print(Panel(
        f"[green]Asset generated![/green]\n\n"
        f"Type: {asset_type}\n"
        f"Output: {filepath}",
        title="Asset Generation Complete"
    ))


@app.command()
def init_project(
    name: str = typer.Argument(..., help="Project name"),
    output_dir: Path = typer.Option(Path("."), help="Parent directory for project"),
):
    """Initialize a new screencast project."""

    project_dir = output_dir / name

    if project_dir.exists():
        console.print(f"[red]Error: Directory already exists: {project_dir}[/red]")
        raise typer.Exit(1)

    # Create project structure
    (project_dir / "input").mkdir(parents=True)
    (project_dir / "output" / "scripts").mkdir(parents=True)
    (project_dir / "output" / "demos").mkdir(parents=True)
    (project_dir / "output" / "assets").mkdir(parents=True)

    # Create template files
    (project_dir / "input" / "bullets.txt").write_text("""# Screencast Bullet Points

Topic: [Your Topic Here]

## Key Points
- Point 1
- Point 2
- Point 3

## Demo Requirements
- Show: [what to demonstrate]
- Data: [sample data needed]
- Output: [expected results]
""", encoding='utf-8')

    (project_dir / "README.md").write_text(f"""# {name}

Screencast project created with ScreenCast Studio.

## Quick Start

1. Edit `input/bullets.txt` with your content
2. Generate script: `screencast-studio generate-script input/bullets.txt`
3. Optimize for TTS: `screencast-studio optimize-tts output/scripts/script.md`
4. Generate demo: `screencast-studio generate-demo output/scripts/script.md "your requirements"`
5. Generate assets: `screencast-studio generate-assets terminal`

## Project Structure

```
{name}/
    input/
        bullets.txt      # Your bullet points
    output/
        scripts/         # Generated narration scripts
        demos/           # Interactive Python demos
        assets/          # Terminal output, CSV, YAML, HTML
    README.md
```
""", encoding='utf-8')

    console.print(Panel(
        f"[green]Project initialized![/green]\n\n"
        f"Directory: {project_dir}\n\n"
        f"Next steps:\n"
        f"1. cd {project_dir}\n"
        f"2. Edit input/bullets.txt\n"
        f"3. Run: screencast-studio generate-script input/bullets.txt",
        title="Project Created"
    ))


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
