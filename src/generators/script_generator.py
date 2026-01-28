"""Generate narration scripts from bullet points."""

import re
from typing import Optional, List
from dataclasses import dataclass
from ..utils.ai_client import AIClient
from ..config import Config


@dataclass
class ScriptSection:
    """A section of the narration script."""
    name: str
    content: str
    duration_seconds: int
    word_count: int


@dataclass
class GeneratedScript:
    """Complete generated script with metadata."""
    raw_text: str
    sections: List[ScriptSection]
    total_words: int
    estimated_duration_minutes: float

    def to_markdown(self) -> str:
        """Export script as markdown."""
        return self.raw_text

    def to_tts_text(self) -> str:
        """Export script optimized for TTS (no visual cues)."""
        # Remove visual cues in brackets
        text = re.sub(r'\[.*?\]', '', self.raw_text)
        # Remove section headers
        text = re.sub(r'^##.*$', '', text, flags=re.MULTILINE)
        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


class ScriptGenerator:
    """Generate narration scripts from bullet points."""

    def __init__(self):
        self.ai_client = AIClient()

    def generate(
        self,
        bullets: str,
        duration_minutes: int = 7,
        topic: Optional[str] = None,
        audience_level: str = "intermediate"
    ) -> GeneratedScript:
        """Generate a complete narration script.

        Args:
            bullets: Bullet points or outline
            duration_minutes: Target video duration
            topic: Optional topic/title for context
            audience_level: beginner/intermediate/advanced

        Returns:
            GeneratedScript with sections and metadata
        """
        # Add context to bullets if topic provided
        if topic:
            bullets = f"Topic: {topic}\nAudience Level: {audience_level}\n\nKey Points:\n{bullets}"

        # Generate raw script
        raw_text = self.ai_client.generate_script(bullets, duration_minutes)

        # Parse into sections
        sections = self._parse_sections(raw_text, duration_minutes)

        # Calculate totals
        total_words = sum(s.word_count for s in sections)
        estimated_duration = total_words / Config.WORDS_PER_MINUTE

        return GeneratedScript(
            raw_text=raw_text,
            sections=sections,
            total_words=total_words,
            estimated_duration_minutes=estimated_duration
        )

    def _parse_sections(self, text: str, duration_minutes: int) -> List[ScriptSection]:
        """Parse script text into sections."""
        sections = []
        section_pattern = r'## (HOOK|OBJECTIVE|CONTENT|SUMMARY|CALL TO ACTION)\n(.*?)(?=## |$)'

        for match in re.finditer(section_pattern, text, re.DOTALL):
            name = match.group(1)
            content = match.group(2).strip()
            word_count = len(content.split())

            # Estimate duration based on structure percentages
            name_key = name.lower().replace(" ", "_")
            if name_key == "call_to_action":
                name_key = "cta"
            pct = Config.SCRIPT_STRUCTURE.get(name_key, {}).get("duration_pct", 0.2)
            duration_seconds = int(duration_minutes * 60 * pct)

            sections.append(ScriptSection(
                name=name,
                content=content,
                duration_seconds=duration_seconds,
                word_count=word_count
            ))

        return sections

    def regenerate_section(
        self,
        script: GeneratedScript,
        section_name: str,
        feedback: str
    ) -> GeneratedScript:
        """Regenerate a specific section with feedback."""
        system_prompt = f"""Rewrite only the {section_name} section of this script based on feedback.
Keep the same style and structure, but address the feedback."""

        user_prompt = f"""Current script:
{script.raw_text}

Feedback for {section_name} section:
{feedback}

Provide only the rewritten {section_name} section."""

        new_section = self.ai_client.generate(system_prompt, user_prompt)

        # Replace section in raw text
        pattern = f'## {section_name}\n.*?(?=## |$)'
        new_raw = re.sub(pattern, f'## {section_name}\n{new_section}\n\n',
                        script.raw_text, flags=re.DOTALL)

        return GeneratedScript(
            raw_text=new_raw,
            sections=self._parse_sections(new_raw, 7),
            total_words=len(new_raw.split()),
            estimated_duration_minutes=len(new_raw.split()) / Config.WORDS_PER_MINUTE
        )
