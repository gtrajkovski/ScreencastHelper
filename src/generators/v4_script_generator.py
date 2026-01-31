"""AI Script Generator for ScreenCast Studio v4.0.

Generates complete WWHAA-structured video scripts using Claude API
with full context injection (audience, environment, style, duration).
"""

from typing import Optional, Dict, Any


# =====================================================
# SYSTEM PROMPT
# =====================================================
SCRIPT_SYSTEM_PROMPT = """You are an expert instructional designer creating video scripts for Coursera programming courses.

YOUR ROLE:
- Generate professional, engaging screencast video scripts
- Follow the WWHAA structure adapted for video format
- Write code that is correct, realistic, and educational
- Create content appropriate for the specified audience level

STRICT REQUIREMENTS:
1. Use EXACT markdown headers: ## HOOK, ## OBJECTIVE, ## CONTENT, ## SUMMARY, ## CTA
2. Keep timing constraints for each section
3. Include [VISUAL CUE: description] markers for production
4. Use ```python code fences for all code blocks
5. For Jupyter environment, format code as discrete cells with clear breaks
6. Include realistic output/results after code execution
7. Never use placeholder data - always create realistic examples
8. Avoid generic phrases like "In this video" for hooks - start with a compelling problem
9. Include [PAUSE] markers where natural pauses should occur

OUTPUT FORMAT:
Your response must be ONLY the script content, starting with ## HOOK.
Do not include explanations, notes, or meta-commentary."""


# =====================================================
# CONTEXT DICTIONARIES
# =====================================================
AUDIENCE_CONTEXT = {
    "beginner": """
AUDIENCE: Complete beginners with no Python experience
- Explain every concept before using it
- Define technical terms when first introduced
- Use simple, relatable analogies
- Keep code examples minimal (3-5 lines max per cell)
- Include common errors and how to avoid them
- Speak slowly and clearly in narration""",
    "intermediate": """
AUDIENCE: Intermediate learners with basic Python knowledge
- Assume familiarity with variables, loops, functions
- Focus on practical application, not syntax basics
- Show realistic, production-relevant code
- Include best practices and common patterns
- Moderate pace - efficient but clear""",
    "advanced": """
AUDIENCE: Advanced developers seeking specialized knowledge
- Skip basic explanations
- Focus on nuances, edge cases, performance
- Show complex, real-world implementations
- Include optimization techniques
- Reference documentation and advanced resources
- Faster pace, more technical depth"""
}

ENVIRONMENT_CONTEXT = {
    "jupyter": """
ENVIRONMENT: Jupyter Notebook
- Structure code as discrete cells with clear breaks
- Show cell execution counts [1], [2], etc.
- Include markdown cells for section headers
- Show output directly below code cells
- Use df.head() to preview DataFrames
- Clear visual separation between cells""",
    "vscode": """
ENVIRONMENT: VS Code Editor
- Write as a single Python script file
- Use # %% cell markers for sections
- Include terminal commands as separate snippets
- Show file tree structure when relevant
- Reference typical project organization""",
    "terminal": """
ENVIRONMENT: Terminal / Command Line
- Focus on CLI commands and output
- Show prompt ($ or >>>)
- Include command flags and options
- Demonstrate piping and chaining
- Show realistic terminal output"""
}

STYLE_CONTEXT = {
    "tutorial": """
STYLE: Step-by-Step Tutorial
- Narration explains each step BEFORE showing it
- "First, we'll... [show code]. Now let's..."
- Explicit transitions between steps
- Summarize what was accomplished after each major step
- Include "checkpoint" moments""",
    "demo": """
STYLE: Live Demo
- Code-first approach - show it working, then explain
- Natural flow - as if typing live
- Brief explanations as you type
- Focus on seeing it work, not explaining theory
- Fast-paced but followable""",
    "conceptual": """
STYLE: Conceptual Explanation with Code
- Start with the WHY before the HOW
- Use visualizations and diagrams [VISUAL CUE]
- Code serves to illustrate concepts
- More talking, less typing
- Connect to broader principles"""
}

DURATION_STRUCTURE = {
    3: {
        "hook": "20 seconds",
        "objective": "15 seconds",
        "content": "2 minutes",
        "summary": "15 seconds",
        "cta": "10 seconds",
        "guidance": "Very focused. ONE key concept. 1-2 code examples max."
    },
    5: {
        "hook": "30 seconds",
        "objective": "30 seconds",
        "content": "3 minutes 30 seconds",
        "summary": "30 seconds",
        "cta": "20 seconds",
        "guidance": "Standard format. 2-3 code examples. Clear progression."
    },
    7: {
        "hook": "40 seconds",
        "objective": "40 seconds",
        "content": "5 minutes",
        "summary": "40 seconds",
        "cta": "20 seconds",
        "guidance": "In-depth coverage. 3-4 code examples. Include edge cases."
    },
    10: {
        "hook": "60 seconds",
        "objective": "45 seconds",
        "content": "7 minutes",
        "summary": "45 seconds",
        "cta": "30 seconds",
        "guidance": "Comprehensive. Multiple concepts. Full workflow demonstration."
    }
}


REQUIRED_SECTIONS = ["## HOOK", "## OBJECTIVE", "## CONTENT", "## SUMMARY", "## CTA"]


def build_script_prompt(
    topic: str,
    duration_minutes: int = 5,
    style: str = "tutorial",
    environment: str = "jupyter",
    audience: str = "intermediate",
    learning_objectives: Optional[str] = None,
    sample_code: Optional[str] = None,
    notes: Optional[str] = None
) -> str:
    """Build a full-context user prompt for script generation."""
    if duration_minutes not in DURATION_STRUCTURE:
        duration_minutes = 5

    duration_info = DURATION_STRUCTURE[duration_minutes]
    audience_ctx = AUDIENCE_CONTEXT.get(audience, AUDIENCE_CONTEXT["intermediate"])
    env_ctx = ENVIRONMENT_CONTEXT.get(environment, ENVIRONMENT_CONTEXT["jupyter"])
    style_ctx = STYLE_CONTEXT.get(style, STYLE_CONTEXT["tutorial"])

    prompt = f"""Create a {duration_minutes}-minute screencast video script about:

**TOPIC**: {topic}
{audience_ctx}
{env_ctx}
{style_ctx}

**TIMING GUIDE**:
- HOOK: {duration_info['hook']}
- OBJECTIVE: {duration_info['objective']}
- CONTENT: {duration_info['content']}
- SUMMARY: {duration_info['summary']}
- CTA: {duration_info['cta']}

Content guidance: {duration_info['guidance']}
"""

    if learning_objectives and learning_objectives.strip():
        prompt += f"""
**LEARNING OBJECTIVES** (use these exactly):
{learning_objectives}
"""
    else:
        prompt += """
**LEARNING OBJECTIVES**: Generate 2-3 clear, measurable objectives starting with "By the end of this video, you'll be able to..."
"""

    if sample_code and sample_code.strip():
        prompt += f"""
**REFERENCE DATA/CODE** (incorporate this into examples):
```
{sample_code}
```
"""

    if notes and notes.strip():
        prompt += f"""
**ADDITIONAL REQUIREMENTS**:
{notes}
"""

    prompt += """
Now generate the complete script. Start directly with ## HOOK - no preamble."""
    return prompt


def generate_script(
    ai_client,
    topic: str,
    duration_minutes: int = 5,
    style: str = "tutorial",
    environment: str = "jupyter",
    audience: str = "intermediate",
    learning_objectives: Optional[str] = None,
    sample_code: Optional[str] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Generate a complete video script using Claude API.

    Args:
        ai_client: AIClient instance with generate(system, user) method.
        topic: What the video should teach.
        duration_minutes: Target video length (3, 5, 7, or 10).
        style: tutorial | demo | conceptual.
        environment: jupyter | vscode | terminal.
        audience: beginner | intermediate | advanced.
        learning_objectives: Optional custom learning objectives.
        sample_code: Optional reference code/data.
        notes: Optional additional instructions.

    Returns:
        Dict with 'success', 'script', and 'metadata'.
    """
    if not topic or not topic.strip():
        return {"success": False, "error": "Topic is required", "script": None, "metadata": None}

    user_prompt = build_script_prompt(
        topic=topic,
        duration_minutes=duration_minutes,
        style=style,
        environment=environment,
        audience=audience,
        learning_objectives=learning_objectives,
        sample_code=sample_code,
        notes=notes
    )

    try:
        script_text = ai_client.generate(SCRIPT_SYSTEM_PROMPT, user_prompt)

        # Validate output has required sections
        missing = [s for s in REQUIRED_SECTIONS if s not in script_text]
        if missing:
            fix_prompt = (
                f"{user_prompt}\n\n"
                f"IMPORTANT: Your previous attempt was missing these sections: {', '.join(missing)}. "
                "You MUST include ALL sections: ## HOOK, ## OBJECTIVE, ## CONTENT, ## SUMMARY, ## CTA."
            )
            script_text = ai_client.generate(SCRIPT_SYSTEM_PROMPT, fix_prompt)

        return {
            "success": True,
            "script": script_text,
            "metadata": {
                "topic": topic,
                "duration_minutes": duration_minutes,
                "style": style,
                "environment": environment,
                "audience": audience,
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "script": None,
            "metadata": None
        }
