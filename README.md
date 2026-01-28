# ScreenCast Studio

AI-powered screencast production assistant that transforms screencast production from manual work into a streamlined, AI-assisted workflow.

## Features

- **Script Generator**: Generate full narration scripts from bullet points following Coursera structure
- **TTS Optimizer**: Optimize scripts for text-to-speech with pronunciation fixes
- **Demo Generator**: Create interactive Python demos with ENTER prompts synced to narration
- **Asset Generator**: Generate mock terminal output, CSV files, YAML configs, and HTML reports

## Installation

```bash
# Clone the repository
git clone https://github.com/gtrajkovski/ScreencastHelper.git
cd ScreencastHelper

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=your_api_key_here
```

## Usage

### Initialize a Project

```bash
python -m src.ui.cli init-project my-screencast
```

### Generate Script from Bullets

```bash
python -m src.ui.cli generate-script input/bullets.txt --output script.md --duration 7
```

### Optimize for TTS

```bash
python -m src.ui.cli optimize-tts script.md --output script_tts.txt --format plain
```

### Generate Interactive Demo

```bash
python -m src.ui.cli generate-demo script.md "Show data validation workflow" --output demo.py
```

### Generate Assets

```bash
# Terminal output
python -m src.ui.cli generate-assets terminal --output-dir assets

# Sample CSV
python -m src.ui.cli generate-assets csv --output-dir assets

# YAML lineage
python -m src.ui.cli generate-assets yaml --output-dir assets

# HTML report
python -m src.ui.cli generate-assets html --output-dir assets
```

## Project Structure

```
ScreencastHelper/
    src/
        generators/
            script_generator.py    # AI script from bullets
            tts_optimizer.py       # Pronunciation fixes
            demo_generator.py      # Interactive Python scripts
            asset_generator.py     # Terminal, CSV, YAML, HTML
        templates/                 # Output templates
        ui/
            cli.py                 # Command-line interface
        utils/
            ai_client.py           # Claude API wrapper
            file_handler.py        # File operations
        config.py                  # Settings and defaults
    tests/                         # Test suite
    examples/                      # Sample projects
```

## Running Tests

```bash
pytest tests/ -v
```

## License

MIT
