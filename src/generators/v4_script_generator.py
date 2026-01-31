"""AI Script Generator for ScreenCast Studio v4.0.

Generates complete WWHAA+IVQ-structured video scripts using Claude API
with full context injection (audience, environment, style, duration)
following Coursera short course development guidelines.
"""

from typing import Optional, Dict, Any


# =====================================================
# BLOOM'S TAXONOMY VERBS
# =====================================================
BLOOMS_TAXONOMY_VERBS = {
    "remember": ["define", "list", "identify", "name", "recall", "recognize"],
    "understand": ["describe", "explain", "summarize", "interpret", "classify", "compare"],
    "apply": ["apply", "demonstrate", "implement", "solve", "use", "compute"],
    "analyze": ["analyze", "compare", "contrast", "distinguish", "examine", "categorize"],
    "evaluate": ["assess", "evaluate", "critique", "judge", "justify", "recommend"],
    "create": ["create", "design", "develop", "construct", "formulate", "produce"]
}


# =====================================================
# SYSTEM PROMPT
# =====================================================
SCRIPT_SYSTEM_PROMPT = """You are an expert instructional designer creating screencast video scripts \
for Coursera programming courses, following Coursera's official course development guidelines. \
You produce scripts where the instructor demonstrates real, working code while explaining concepts.

YOUR ROLE:
- Generate professional, engaging screencast video scripts with live code execution
- Follow the WWHAA+IVQ structure (HOOK, OBJECTIVE, CONTENT, IVQ, SUMMARY, CTA)
- All code MUST be syntactically correct, runnable Python that produces the stated outputs
- Create content appropriate for the specified audience level

STRUCTURE REQUIREMENTS:
1. Start output with a METADATA TABLE in this exact format:
   | Field | Value |
   |-------|-------|
   | Course | [course name] |
   | Lesson | [lesson number] - [lesson title] |
   | Video | [video number] - [video title] |
   | Learning Objective | [LO text] |
   | Duration | [X] minutes |
   | Environment | [Jupyter Notebook / VS Code / Terminal] |

2. Then use EXACT markdown headers in this order: ## HOOK, ## OBJECTIVE, ## CONTENT, ## IVQ, ## SUMMARY, ## CTA

SECTION RULES:

## HOOK (30-60 seconds):
- Open with a relatable problem or real-world scenario
- Use a first-person anecdote when possible ("Last week, I was working on...")
- NEVER start with generic intros ("Hi, welcome to...", "In this video...")
- No code yet — create urgency or curiosity about the topic
- Use [SCREEN: ...] cues to indicate what's visible

## OBJECTIVE (30-45 seconds):
- Begin with exactly: "By the end of this video, you'll be able to:"
- List 2-3 measurable objectives using Bloom's Taxonomy action verbs
- Each objective must be specific and assessable

## CONTENT (primary teaching section):
- Organize into 3-4 clearly labeled subsections (### Segment N: Title)
- Use transition phrases: "Now that we've covered X, let's move to Y"
- Every concept needs a concrete example with real numbers/data
- Define every technical term on first use

SCREENCAST FORMAT for each code segment:
- Start with [SCREEN: ...] cue indicating what's visible
- Add **NARRATION:** label before narration text explaining what we're about to do
- Mark code execution with **[RUN CELL]** before the code fence
- Use ```python code fences for all code blocks — code must be runnable
- ALWAYS include **OUTPUT:** block after each code cell showing expected output
- Add **NARRATION:** after output to explain what happened and what it means
- Use **[PAUSE]** markers for moments to let output sink in
- Separate code segments with --- CELL BREAK ---

CODE CELL MARKERS:
- **[RUN CELL]** — Code to be executed live
- **[TYPE]** — Code being typed character by character
- **[SHOW]** — Code already visible, just highlighting
- **[PAUSE]** — Moment to let output sink in

SCREEN CUES:
- [SCREEN: Jupyter Notebook - new cell]
- [SCREEN: Highlight line N]
- [SCREEN: Zoom to output area]
- [SCREEN: Terminal window]
- [SCREEN: File explorer showing data folder]

NARRATION STYLE:
- During code: explain WHAT you're typing and WHY ("I'm importing pandas because...")
- After output: explain what the output MEANS ("So we can see we have 252 rows...")
- Transitions: "Now that we have our data loaded, let's..."

## IVQ (In-Video Question, 30-60 seconds):
- Present one multiple-choice question testing a key concept from CONTENT
- Use [SCREEN: Question overlay] cue
- Format exactly as:
  **Question:** [question text]
  A) [option]
  B) [option]
  C) [option]
  D) [option]
  **Correct Answer:** [letter]
  **Feedback A:** [Correct/Incorrect. Explain WHY in 1-2 sentences]
  **Feedback B:** [Correct/Incorrect. Explain WHY in 1-2 sentences]
  **Feedback C:** [Correct/Incorrect. Explain WHY in 1-2 sentences]
  **Feedback D:** [Correct/Incorrect. Explain WHY in 1-2 sentences]
- All four options must have similar length
- Correct answer must NOT always be the longest or shortest option
- NEVER use "All of the above" or "None of the above"
- NO emojis in feedback — use "Correct." or "Incorrect." only

## SUMMARY (30-45 seconds):
- Recap 2-3 key takeaways from the content
- Reinforce the learning objectives stated in OBJECTIVE
- NO new information in this section

## CTA (15-30 seconds):
- Name the SPECIFIC next activity (practice quiz, reading, hands-on activity)
- Keep it brief and actionable

CODE REQUIREMENTS:
- All code must actually run — no pseudocode, no placeholders
- Syntactically correct Python that produces the stated outputs
- Self-contained — each segment should work independently
- Use common libraries (pandas, numpy, sklearn, matplotlib)
- Include realistic variable names and data (not foo/bar)
- Never use placeholder data — always create realistic examples

TONE AND VOICE:
- Conversational but professional
- First-person for personal examples ("When I work with DataFrames, I...")
- Second-person for learner instructions ("You'll want to check...")
- Active voice throughout
- Define technical terms on first use

QUALITY RULES:
- Content must be completely standalone — NO references to other videos, modules, or lessons
- No paywalled links or inaccessible resources
- Balanced answer distribution in IVQ (correct answer should vary across videos)

OUTPUT FORMAT:
Your response must start with the metadata table, then ## HOOK.
Do not include explanations, notes, or meta-commentary outside the script."""


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
        "hook": "30 seconds",
        "objective": "15 seconds",
        "content": "1 minute 30 seconds",
        "ivq": "30 seconds",
        "summary": "15 seconds",
        "cta": "10 seconds",
        "guidance": "Very focused. ONE key concept. 1-2 code examples max. IVQ tests the single core concept."
    },
    5: {
        "hook": "30 seconds",
        "objective": "30 seconds",
        "content": "2 minutes 45 seconds",
        "ivq": "45 seconds",
        "summary": "30 seconds",
        "cta": "20 seconds",
        "guidance": "Standard format. 2-3 code examples. Clear progression. IVQ tests application of main concept."
    },
    7: {
        "hook": "40 seconds",
        "objective": "40 seconds",
        "content": "4 minutes",
        "ivq": "50 seconds",
        "summary": "40 seconds",
        "cta": "20 seconds",
        "guidance": "In-depth coverage. 3-4 code examples. Include edge cases. IVQ tests deeper understanding."
    },
    10: {
        "hook": "60 seconds",
        "objective": "45 seconds",
        "content": "6 minutes",
        "ivq": "60 seconds",
        "summary": "45 seconds",
        "cta": "30 seconds",
        "guidance": "Comprehensive. Multiple concepts. Full workflow. IVQ tests synthesis of multiple concepts."
    }
}


REQUIRED_SECTIONS = ["## HOOK", "## OBJECTIVE", "## CONTENT", "## IVQ", "## SUMMARY", "## CTA"]


def build_script_prompt(
    topic: str,
    duration_minutes: int = 5,
    style: str = "tutorial",
    environment: str = "jupyter",
    audience: str = "intermediate",
    learning_objectives: Optional[str] = None,
    sample_code: Optional[str] = None,
    notes: Optional[str] = None,
    course_name: Optional[str] = None,
    lesson_number: Optional[int] = None,
    video_number: Optional[int] = None,
    format_type: Optional[str] = None
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
- IVQ: {duration_info['ivq']}
- SUMMARY: {duration_info['summary']}
- CTA: {duration_info['cta']}

Content guidance: {duration_info['guidance']}
"""

    # Metadata context for the metadata table
    if course_name or lesson_number or video_number:
        prompt += f"""
**VIDEO METADATA** (use these values in the metadata table):
- Course Name: {course_name or '[Course Name]'}
- Lesson Number: {lesson_number or '[N]'}
- Video Number: {video_number or '[N]'}
- Format: {format_type or style}
"""

    if learning_objectives and learning_objectives.strip():
        prompt += f"""
**LEARNING OBJECTIVES** (use these exactly):
{learning_objectives}
"""
    else:
        prompt += """
**LEARNING OBJECTIVES**: Generate 2-3 clear, measurable objectives using Bloom's Taxonomy verbs.
Format: "By the end of this video, you'll be able to:" followed by objectives starting with action verbs.
"""

    # Bloom's taxonomy reference
    prompt += """
**BLOOM'S TAXONOMY VERB REFERENCE** (use appropriate level for objectives):
- Remember: define, list, identify, name, recall
- Understand: describe, explain, summarize, interpret
- Apply: apply, demonstrate, implement, solve
- Analyze: analyze, compare, contrast, distinguish
- Evaluate: assess, evaluate, critique, judge
- Create: create, design, develop, construct
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
Now generate the complete script. Start with the metadata table, then ## HOOK. No preamble."""
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
    notes: Optional[str] = None,
    course_name: Optional[str] = None,
    lesson_number: Optional[int] = None,
    video_number: Optional[int] = None,
    format_type: Optional[str] = None
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
        course_name: Optional Coursera course name for metadata table.
        lesson_number: Optional lesson number for metadata table.
        video_number: Optional video number for metadata table.
        format_type: Optional format (screencast/slide/mixed) for metadata table.

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
        notes=notes,
        course_name=course_name,
        lesson_number=lesson_number,
        video_number=video_number,
        format_type=format_type
    )

    try:
        script_text = ai_client.generate(SCRIPT_SYSTEM_PROMPT, user_prompt)

        # Validate output has required sections
        missing = [s for s in REQUIRED_SECTIONS if s not in script_text]
        if missing:
            fix_prompt = (
                f"{user_prompt}\n\n"
                f"IMPORTANT: Your previous attempt was missing these sections: {', '.join(missing)}. "
                "You MUST include ALL sections: ## HOOK, ## OBJECTIVE, ## CONTENT, ## IVQ, ## SUMMARY, ## CTA."
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
