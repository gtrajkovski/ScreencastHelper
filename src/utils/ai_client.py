"""Anthropic API client wrapper for ScreenCast Studio."""

import anthropic
from ..config import Config


class AIClient:
    """Wrapper for Claude API calls."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = Config.MODEL

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = Config.MAX_TOKENS,
        temperature: float = 0.7
    ) -> str:
        """Generate text using Claude API.

        Args:
            system_prompt: Instructions for the AI
            user_prompt: User's input/request
            max_tokens: Maximum response length
            temperature: Creativity level (0-1)

        Returns:
            Generated text response
        """
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature
        )
        return message.content[0].text

    def generate_script(self, bullets: str, duration_minutes: int = 7) -> str:
        """Generate narration script from bullet points."""
        target_words = duration_minutes * Config.WORDS_PER_MINUTE

        system_prompt = """You are an expert technical educator creating screencast narration scripts.

Your scripts follow the Coursera video structure:
1. HOOK (10%): Start with relatable problem or question, first-person anecdote
2. OBJECTIVE (10%): "By the end of this video, you'll be able to..." with 2-3 specific goals
3. CONTENT (60%): Core teaching with concrete examples, visual cues in [brackets]
4. SUMMARY (10%): Restate key takeaways, connect back to hook
5. CTA (10%): Name specific next activity, create momentum

Writing style:
- Conversational but professional tone
- First-person narrative ("I've seen...", "In my experience...")
- Active voice throughout
- Include [visual cues] for screen actions
- Add [PAUSE] markers for emphasis
- Include specific numbers in examples"""

        user_prompt = f"""Create a {duration_minutes}-minute narration script (~{target_words} words) from these bullet points:

{bullets}

Format the output as:
## HOOK
[narration]

## OBJECTIVE
[narration]

## CONTENT
[narration with [visual cues] and [PAUSE] markers]

## SUMMARY
[narration]

## CALL TO ACTION
[narration]"""

        return self.generate(system_prompt, user_prompt)

    def generate_demo_code(self, script: str, demo_requirements: str) -> str:
        """Generate interactive Python demo from script."""

        system_prompt = """You are an expert at creating interactive Python demo scripts for screencasts.

Your demos have these characteristics:
1. Teleprompter mode - print narration text before each action
2. ENTER prompts - pause between actions for recording
3. Visual feedback - use rich library for colorful output
4. File operations - automatically open/display relevant files
5. Simulated typing - create authentic coding feel

Key patterns:
- def pause(msg="Press ENTER..."): input(f"\\n   [{msg}]")
- Print "NARRATION:" before each script segment
- Include section markers (## SECTION 1, ## SECTION 2)
- Add comments explaining what each section demonstrates
- Use realistic variable names and data"""

        user_prompt = f"""Create an interactive Python demo script based on this narration:

{script}

Demo requirements:
{demo_requirements}

The script should:
1. Print narration segments before actions
2. Pause for ENTER between major actions
3. Display colorful output using rich library
4. Include section headers matching the script
5. Have a main() function with if __name__ == "__main__" guard"""

        return self.generate(system_prompt, user_prompt, max_tokens=8192)
