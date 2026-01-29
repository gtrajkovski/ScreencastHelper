"""Environment modules for ScreenCast Studio."""

from .base import BaseEnvironment, DemoStep
from .jupyter import JupyterEnvironment
from .terminal import TerminalEnvironment
from .recommender import EnvironmentRecommender

__all__ = [
    "BaseEnvironment",
    "DemoStep",
    "JupyterEnvironment",
    "TerminalEnvironment",
    "EnvironmentRecommender"
]
