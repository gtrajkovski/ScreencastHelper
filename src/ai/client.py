"""Claude API client for ScreenCast Studio."""

import anthropic
from typing import Generator, List, Dict
from ..config import Config


class AIClient:
    """Wrapper for Claude API with conversation support."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = Config.MODEL
        self.conversation_history: List[Dict[str, str]] = []

    def chat(self, user_message: str, system_prompt: str = None) -> str:
        """Send a chat message and get response."""
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt or "You are a helpful screencast production assistant.",
            messages=self.conversation_history
        )

        assistant_message = response.content[0].text
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        return assistant_message

    def chat_stream(self, user_message: str, system_prompt: str = None) -> Generator[str, None, None]:
        """Stream a chat response."""
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        full_response = ""

        with self.client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=system_prompt or "You are a helpful screencast production assistant.",
            messages=self.conversation_history
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                yield text

        self.conversation_history.append({
            "role": "assistant",
            "content": full_response
        })

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """One-shot generation (no conversation history)."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
