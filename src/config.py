"""Configuration management for ScreenCast Studio."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""

    # API Settings
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4096

    # Script Defaults
    DEFAULT_DURATION_MINUTES = 7
    WORDS_PER_MINUTE = 150  # Average speaking pace

    # Coursera Structure
    SCRIPT_STRUCTURE = {
        "hook": {"duration_pct": 0.10, "description": "Relatable problem or question"},
        "objective": {"duration_pct": 0.10, "description": "By the end of this video..."},
        "content": {"duration_pct": 0.60, "description": "Core teaching content"},
        "summary": {"duration_pct": 0.10, "description": "Key takeaways"},
        "cta": {"duration_pct": 0.10, "description": "Call to action for next activity"}
    }

    # TTS Pronunciation Fixes
    TTS_REPLACEMENTS = {
        # Acronyms - spell out
        "ML": "M-L",
        "API": "A-P-I",
        "ROC": "R-O-C",
        "AUC": "A-U-C",
        "CSV": "C-S-V",
        "JSON": "J-SON",
        "YAML": "YAML",  # Already pronounceable
        "SQL": "S-Q-L",
        "CLI": "C-L-I",
        "SDK": "S-D-K",
        "LLM": "L-L-M",

        # Python-specific
        "sklearn": "scikit-learn",
        "GridSearchCV": "Grid Search C-V",
        "n_estimators": "n underscore estimators",
        "max_depth": "max underscore depth",
        "pd.read_csv": "pandas read C-S-V",
        "df.head()": "dataframe dot head",
        "__init__": "dunder init",

        # Punctuation for natural speech
        "—": ", ",  # Em-dash to comma
        "...": ", ",  # Ellipsis to pause
        " - ": ", ",  # Spaced dash to comma
    }

    # Output Directories
    OUTPUT_DIR = Path("output")
    ASSETS_DIR = OUTPUT_DIR / "assets"

    @classmethod
    def ensure_dirs(cls):
        """Create output directories if they don't exist."""
        cls.OUTPUT_DIR.mkdir(exist_ok=True)
        cls.ASSETS_DIR.mkdir(exist_ok=True)
