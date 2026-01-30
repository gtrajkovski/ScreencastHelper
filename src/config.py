"""Configuration for ScreenCast Studio v2.0."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


class Environment(Enum):
    """Available demo environments."""
    JUPYTER = "jupyter"
    VSCODE = "vscode"
    TERMINAL = "terminal"
    IPYTHON = "ipython"
    PYCHARM = "pycharm"


class AudienceLevel(Enum):
    """Target audience levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class DemoType(Enum):
    """Types of demos."""
    DATA_ANALYSIS = "data_analysis"
    CLI_TOOL = "cli_tool"
    WEB_APP = "web_app"
    ML_TRAINING = "ml_training"
    DATA_PIPELINE = "data_pipeline"
    API_USAGE = "api_usage"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"


@dataclass
class DatasetConfig:
    """Configuration for a dataset."""
    name: str
    filename: str
    columns: List[Dict[str, str]]  # [{"name": "id", "type": "int", "desc": "..."}]
    rows: int
    issues: Optional[Dict] = None  # {"nulls": 0.01, "duplicates": 10, ...}
    relationships: Optional[Dict] = None  # {"foreign_key": "users.user_id"}


@dataclass
class EnvironmentConfig:
    """Configuration for demo environment."""
    name: str  # Environment name as string (jupyter, terminal, etc.)
    theme: str = "dark"
    font_size: int = 14
    show_line_numbers: bool = True
    auto_scroll: bool = True
    typing_speed: float = 0.03
    cell_execution_delay: float = 0.5
    custom_settings: Dict = field(default_factory=dict)

    @property
    def env_type(self) -> Environment:
        """Get Environment enum from name."""
        try:
            return Environment(self.name)
        except ValueError:
            return Environment.JUPYTER


@dataclass
class ProjectConfig:
    """Full project configuration."""
    topic: str
    duration_minutes: int
    audience: AudienceLevel
    demo_type: DemoType
    bullets: str
    demo_requirements: str
    environment: EnvironmentConfig
    datasets: List[DatasetConfig]


class Config:
    """Global configuration."""

    # API
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    MODEL = os.getenv("MODEL", "claude-sonnet-4-20250514")
    MAX_TOKENS = 4096

    # Paths
    OUTPUT_DIR = Path("output")
    TEMPLATES_DIR = Path("templates")

    # Defaults
    DEFAULT_DURATION = 7
    WORDS_PER_MINUTE = 150

    # TTS Audio Generation (v4.0)
    TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural")
    TTS_RATE = os.getenv("TTS_RATE", "+0%")
    TTS_PITCH = os.getenv("TTS_PITCH", "+0Hz")

    # TTS Fixes
    TTS_FIXES = TTS_REPLACEMENTS = {
        "O(n^2)": "O of n squared",
        "O(n)": "O of n",
        "O(1)": "O of 1",
        "O(log n)": "O of log n",
        "O(n log n)": "O of n log n",
        "cProfile": "c-Profile",
        "I/O": "I-O",
        "API": "A-P-I",
        "APIs": "A-P-Is",
        "CPU": "C-P-U",
        "GPU": "G-P-U",
        "RAM": "R-A-M",
        "ML": "M-L",
        "AI": "A-I",
        "CSV": "C-S-V",
        "JSON": "Jason",
        "YAML": "YAML",
        "SQL": "S-Q-L",
        "NoSQL": "No S-Q-L",
        "CLI": "C-L-I",
        "GUI": "G-U-I",
        "IDE": "I-D-E",
        "OOP": "O-O-P",
        "py-spy": "pie-spy",
        "pytest": "pie-test",
        "sklearn": "scikit-learn",
        "pandas": "pandas",
        "numpy": "num-pie",
        "scipy": "sigh-pie",
        "matplotlib": "mat-plot-lib",
        "seaborn": "sea-born",
        ".py": " dot pie",
        ".csv": " dot C-S-V",
        ".json": " dot Jason",
        ".yaml": " dot YAML",
        ".ipynb": " dot i-pie-n-b",
        "list.append()": "list dot append",
        "dict[]": "dict brackets",
        "df.head()": "dataframe dot head",
        "df.describe()": "dataframe dot describe",
        "pd.read_csv": "pandas read C-S-V",
        "__init__": "dunder init",
        "__main__": "dunder main",
        "—": ", ",
        "...": ", ",
        " - ": ", ",
    }

    # Environment recommendations
    ENV_RECOMMENDATIONS = {
        DemoType.DATA_ANALYSIS: Environment.JUPYTER,
        DemoType.CLI_TOOL: Environment.TERMINAL,
        DemoType.WEB_APP: Environment.VSCODE,
        DemoType.ML_TRAINING: Environment.JUPYTER,
        DemoType.DATA_PIPELINE: Environment.VSCODE,
        DemoType.API_USAGE: Environment.IPYTHON,
        DemoType.DEBUGGING: Environment.VSCODE,
        DemoType.REFACTORING: Environment.PYCHARM,
    }

    # Script structure
    SCRIPT_STRUCTURE = {
        "hook": {"duration_pct": 0.10, "description": "Relatable problem or question"},
        "objective": {"duration_pct": 0.10, "description": "By the end of this video..."},
        "content": {"duration_pct": 0.60, "description": "Core teaching content"},
        "summary": {"duration_pct": 0.10, "description": "Key takeaways"},
        "cta": {"duration_pct": 0.10, "description": "Call to action for next activity"}
    }

    @classmethod
    def ensure_dirs(cls):
        """Create output directories."""
        cls.OUTPUT_DIR.mkdir(exist_ok=True)
        (cls.OUTPUT_DIR / "data").mkdir(exist_ok=True)
        (cls.OUTPUT_DIR / "notebooks").mkdir(exist_ok=True)
        (cls.OUTPUT_DIR / "scripts").mkdir(exist_ok=True)
        return cls.OUTPUT_DIR
