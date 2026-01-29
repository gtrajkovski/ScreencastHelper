"""AI-powered environment recommendation."""

from typing import Dict, Optional
from ..config import Environment, DemoType, AudienceLevel
from ..ai.client import AIClient
from ..ai.prompts import ENV_RECOMMENDER


class EnvironmentRecommender:
    """Recommend the best environment for a demo."""

    # Quick recommendations based on demo type
    QUICK_RECOMMENDATIONS = {
        DemoType.DATA_ANALYSIS: {
            "env": Environment.JUPYTER,
            "reason": "Data analysis benefits from Jupyter's cell-by-cell execution and inline visualizations."
        },
        DemoType.CLI_TOOL: {
            "env": Environment.TERMINAL,
            "reason": "CLI tools are best demonstrated in their native terminal environment."
        },
        DemoType.WEB_APP: {
            "env": Environment.VSCODE,
            "reason": "Web development benefits from VS Code's multi-file editing and integrated terminal."
        },
        DemoType.ML_TRAINING: {
            "env": Environment.JUPYTER,
            "reason": "ML training demos benefit from seeing progress and outputs inline."
        },
        DemoType.DATA_PIPELINE: {
            "env": Environment.VSCODE,
            "reason": "Pipeline work involves multiple files and testing."
        },
        DemoType.API_USAGE: {
            "env": Environment.IPYTHON,
            "reason": "API exploration is best in an interactive REPL."
        },
        DemoType.DEBUGGING: {
            "env": Environment.VSCODE,
            "reason": "VS Code's debugger with breakpoints is ideal for debugging demos."
        },
        DemoType.REFACTORING: {
            "env": Environment.PYCHARM,
            "reason": "Large-scale refactoring benefits from PyCharm's powerful refactoring tools."
        },
    }

    def __init__(self):
        self.ai = AIClient()

    def recommend(
        self,
        topic: str,
        demo_type: Optional[DemoType],
        audience: AudienceLevel,
        requirements: str
    ) -> Dict:
        """Get AI-powered environment recommendation."""

        # Quick recommendation if demo type is clear
        if demo_type and demo_type in self.QUICK_RECOMMENDATIONS:
            quick = self.QUICK_RECOMMENDATIONS[demo_type]
            return {
                "recommended": quick["env"],
                "confidence": "high",
                "reason": quick["reason"],
                "alternatives": self._get_alternatives(quick["env"]),
                "settings": self._get_default_settings(quick["env"], audience)
            }

        # AI recommendation for complex cases
        prompt = f"""Recommend the best demo environment:

TOPIC: {topic}
DEMO TYPE: {demo_type.value if demo_type else "Not specified"}
AUDIENCE: {audience.value}
REQUIREMENTS:
{requirements}

Consider:
1. What will be shown (code editing, output, files, visualizations)
2. Audience familiarity with environments
3. Best way to present the content
4. Recording/capture considerations

Recommend one of: Jupyter, VS Code, Terminal, IPython, PyCharm
Explain your reasoning in 2-3 sentences."""

        response = self.ai.generate(ENV_RECOMMENDER, prompt)

        # Parse response to extract recommendation
        env = self._parse_recommendation(response)

        return {
            "recommended": env,
            "confidence": "medium",
            "reason": response,
            "alternatives": self._get_alternatives(env),
            "settings": self._get_default_settings(env, audience)
        }

    def _parse_recommendation(self, response: str) -> Environment:
        """Parse AI response to extract environment."""
        response_lower = response.lower()

        if "jupyter" in response_lower:
            return Environment.JUPYTER
        elif "vs code" in response_lower or "vscode" in response_lower:
            return Environment.VSCODE
        elif "terminal" in response_lower or "shell" in response_lower:
            return Environment.TERMINAL
        elif "ipython" in response_lower or "repl" in response_lower:
            return Environment.IPYTHON
        elif "pycharm" in response_lower:
            return Environment.PYCHARM
        else:
            return Environment.JUPYTER  # Default fallback

    def _get_alternatives(self, primary: Environment) -> list:
        """Get alternative environments."""
        all_envs = list(Environment)
        all_envs.remove(primary)
        return all_envs[:2]  # Return top 2 alternatives

    def _get_default_settings(self, env: Environment, audience: AudienceLevel) -> Dict:
        """Get default settings for environment and audience."""

        base_settings = {
            "theme": "dark",
            "font_size": 14,
            "show_line_numbers": True,
        }

        # Adjust for audience
        if audience == AudienceLevel.BEGINNER:
            base_settings["font_size"] = 16
            base_settings["typing_speed"] = 0.05
        elif audience == AudienceLevel.ADVANCED:
            base_settings["font_size"] = 12
            base_settings["typing_speed"] = 0.02

        # Environment-specific settings
        if env == Environment.JUPYTER:
            base_settings["cell_execution_delay"] = 0.5
            base_settings["show_cell_numbers"] = True
        elif env == Environment.VSCODE:
            base_settings["show_minimap"] = False
            base_settings["show_file_tree"] = True
        elif env == Environment.TERMINAL:
            base_settings["prompt_style"] = "minimal"
            base_settings["clear_between_sections"] = True

        return base_settings
