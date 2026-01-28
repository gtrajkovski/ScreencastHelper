"""Optimize scripts for text-to-speech engines."""

import re
from typing import Dict, List, Tuple
from ..config import Config


class TTSOptimizer:
    """Optimize text for natural TTS pronunciation."""

    def __init__(self, custom_replacements: Dict[str, str] = None):
        """Initialize with optional custom replacements."""
        self.replacements = {**Config.TTS_REPLACEMENTS}
        if custom_replacements:
            self.replacements.update(custom_replacements)

    def optimize(self, text: str) -> str:
        """Apply all optimizations to text.

        Args:
            text: Raw script text

        Returns:
            TTS-optimized text
        """
        # Step 1: Remove visual cues (they're for the recording, not TTS)
        text = self._remove_visual_cues(text)

        # Step 2: Apply word replacements
        text = self._apply_replacements(text)

        # Step 3: Handle numbers and decimals
        text = self._optimize_numbers(text)

        # Step 4: Add pronunciation hints
        text = self._add_pronunciation_hints(text)

        # Step 5: Normalize whitespace
        text = self._normalize_whitespace(text)

        return text

    def _remove_visual_cues(self, text: str) -> str:
        """Remove [bracketed] visual cues."""
        # Keep [PAUSE] but remove other cues
        text = re.sub(r'\[(?!PAUSE)[^\]]+\]', '', text)
        return text

    def _apply_replacements(self, text: str) -> str:
        """Apply word/phrase replacements."""
        for original, replacement in self.replacements.items():
            # Case-insensitive replacement for acronyms
            if original.isupper():
                text = re.sub(rf'\b{original}\b', replacement, text)
            else:
                text = text.replace(original, replacement)
        return text

    def _optimize_numbers(self, text: str) -> str:
        """Make numbers more natural for speech."""
        # Percentages: 95% -> "95 percent"
        text = re.sub(r'(\d+)%', r'\1 percent', text)

        # Version numbers: v1.2 -> "version 1 point 2"
        text = re.sub(r'\bv(\d+)\.(\d+)\b', r'version \1 point \2', text)

        return text

    def _add_pronunciation_hints(self, text: str) -> str:
        """Add hints for commonly mispronounced words."""
        hints = {
            "numpy": "num-pie",
            "PyTorch": "pie-torch",
            "scikit": "sigh-kit",
            "Jupyter": "joo-piter",
            "regex": "reg-ex",
            "tuple": "too-pull",
            "params": "parameters",
        }

        for word, hint in hints.items():
            # Only replace if not already in parentheses
            if f"({hint})" not in text:
                text = re.sub(rf'\b{word}\b(?!\s*\()', f'{word}', text)

        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Clean up whitespace for cleaner TTS input."""
        # Remove extra newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Remove leading/trailing whitespace from lines
        text = '\n'.join(line.strip() for line in text.split('\n'))
        return text.strip()

    def get_changes_report(self, original: str, optimized: str) -> List[Tuple[str, str]]:
        """Generate a report of changes made.

        Args:
            original: Original text
            optimized: Optimized text

        Returns:
            List of (original, replacement) tuples
        """
        changes = []
        for original_word, replacement in self.replacements.items():
            if original_word in original and replacement in optimized:
                changes.append((original_word, replacement))
        return changes

    def add_ssml_markers(self, text: str) -> str:
        """Add SSML markers for advanced TTS engines.

        Note: This is for TTS engines that support SSML (like Amazon Polly,
        Google Cloud TTS). ElevenLabs uses different markup.
        """
        # Convert [PAUSE] to SSML break
        text = re.sub(r'\[PAUSE\]', '<break time="500ms"/>', text)

        # Wrap in speak tags
        return f'<speak>{text}</speak>'

    def add_elevenlabs_markers(self, text: str) -> str:
        """Add markers optimized for ElevenLabs TTS.

        ElevenLabs uses natural punctuation rather than SSML.
        """
        # Convert [PAUSE] to ellipsis (natural pause)
        text = text.replace('[PAUSE]', '...')

        # Add commas before "and" in lists for better pacing
        text = re.sub(r'(\w+)\s+and\s+(\w+)', r'\1, and \2', text)

        return text
