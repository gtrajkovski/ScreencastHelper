"""AI Code Generator for ScreenCast Studio v4.0.

Generates individual code snippets for video segments.
"""

from typing import Optional, Dict, Any


CODE_SYSTEM_PROMPT = """You are an expert Python developer writing educational code examples.

YOUR ROLE:
- Generate clean, working Python code for video demonstrations
- Code must be correct and run without errors
- Include realistic sample data when needed
- Format output for clear visibility in screencasts

STRICT REQUIREMENTS:
1. Code must be syntactically correct Python
2. Include all necessary imports at the top
3. Use realistic variable names and data
4. Show expected output as a comment block
5. Keep code concise but complete
6. Add brief inline comments for complex lines only
7. Do NOT include markdown code fences

OUTPUT FORMAT:
Return ONLY the Python code followed by output.
Start directly with import statements or code.
End with:
# OUTPUT:
# <expected output here>"""


def generate_code(
    ai_client,
    description: str,
    language: str = "python",
    context: Optional[str] = None,
    environment: str = "jupyter",
    include_output: bool = True
) -> Dict[str, Any]:
    """Generate a code snippet for a video segment.

    Args:
        ai_client: AIClient instance with generate(system, user) method.
        description: What the code should do.
        language: Programming language (default: python).
        context: Previous code or data context.
        environment: jupyter | vscode | terminal.
        include_output: Whether to include expected output.

    Returns:
        Dict with 'success', 'code', and 'output' fields.
    """
    if not description or not description.strip():
        return {"success": False, "error": "Description is required", "code": None, "output": None}

    user_prompt = f"Generate {language} code that: {description}\n\nEnvironment: {environment}\n"

    if context and context.strip():
        user_prompt += f"""
Previous code context (variables/data already defined):
```
{context}
```
Continue from this context - do not redefine existing variables.
"""

    if include_output:
        user_prompt += """
After the code, add on a new line:
# OUTPUT:
# <show the expected output here, formatted clearly>
"""

    user_prompt += "\nGenerate only the code. No markdown fences. Start directly with code."

    try:
        raw_code = ai_client.generate(CODE_SYSTEM_PROMPT, user_prompt).strip()

        # Remove any markdown fences if AI included them
        if raw_code.startswith("```"):
            lines = raw_code.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            raw_code = "\n".join(lines)

        # Parse output section if present
        if "# OUTPUT:" in raw_code:
            parts = raw_code.split("# OUTPUT:", 1)
            code = parts[0].strip()
            output_lines = parts[1].strip().split("\n")
            output = "\n".join(line.lstrip("# ").rstrip() for line in output_lines)
        else:
            code = raw_code
            output = None

        return {
            "success": True,
            "code": code,
            "output": output,
            "language": language
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "code": None,
            "output": None
        }
