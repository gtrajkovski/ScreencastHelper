"""Script parser for ScreenCast Studio v5.0.

Parses WWHAA+IVQ structured markdown scripts into canonical Segment objects.
"""

import re
from typing import List
from .models import Segment, SegmentType


# Sections recognized by the parser
KNOWN_SECTIONS = {"HOOK", "OBJECTIVE", "CONTENT", "IVQ", "SUMMARY", "CTA", "CALL TO ACTION"}


def parse_script_to_segments(script: str) -> List[Segment]:
    """Parse a video script into canonical Segment objects.

    Supports formats:
    - ## SECTION or ### SECTION headers (HOOK, OBJECTIVE, CONTENT, etc.)
    - **Segment Title** for segment titles
    - [Visual cue in brackets]
    - ```python code blocks```
    - IVQ markers: **Question:** or ## IVQ / ### IN-VIDEO QUESTION
    - --- CELL BREAK --- separators
    - **NARRATION:** labels
    - **OUTPUT:** blocks
    - **[RUN CELL]**, **[TYPE]**, **[SHOW]**, **[PAUSE]** markers
    """
    if not script or not script.strip():
        return []

    segments = []
    current_section = ""
    current_segment = None
    in_code_block = False
    code_buffer = []
    order = 0

    lines = script.split("\n")

    for line in lines:
        stripped = line.strip()

        # Skip cell break separators
        if stripped.startswith("---") and "CELL BREAK" in stripped.upper():
            continue

        # Handle code blocks
        if stripped.startswith("```"):
            if in_code_block:
                if current_segment:
                    existing = current_segment.code or ""
                    new_code = "\n".join(code_buffer)
                    if existing:
                        current_segment.code = existing + "\n\n" + new_code
                    else:
                        current_segment.code = new_code
                    if not current_segment.type == SegmentType.IVQ:
                        current_segment.type = SegmentType.SCREENCAST
                code_buffer = []
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_buffer.append(line)
            continue

        # Section headers: ## HOOK, ### CONTENT, ## CALL TO ACTION, etc.
        section_match = re.match(r'^#{2,3}\s+(.+)$', stripped)
        if section_match:
            header_text = section_match.group(1).strip()
            header_upper = header_text.upper()

            # Check for IVQ / IN-VIDEO QUESTION first (special type)
            if header_upper == "IVQ" or header_upper.startswith("IVQ ") or header_upper.startswith("IVQ:") or "IN-VIDEO" in header_upper:
                current_section = "IVQ"
                if current_segment:
                    segments.append(current_segment)
                current_segment = Segment(
                    type=SegmentType.IVQ,
                    section="IVQ",
                    title="In-Video Question",
                    order=order,
                )
                order += 1
                continue

            # Check if this is a known section header (exact or prefix match only)
            is_section = False
            for known in KNOWN_SECTIONS:
                if known == "IVQ":
                    continue  # Already handled above
                # Match "## HOOK", "## HOOK — Intro", but NOT "## Hooking Into Events"
                if header_upper == known or header_upper.startswith(known + " ") or header_upper.startswith(known + ":") or header_upper.startswith(known + "\t"):
                    current_section = known
                    if current_section == "CALL TO ACTION":
                        current_section = "CTA"
                    is_section = True
                    break

            if is_section:
                # Start a new segment for this section
                if current_segment:
                    segments.append(current_segment)
                current_segment = Segment(
                    section=current_section,
                    title=current_section.title(),
                    order=order,
                )
                order += 1
                continue

            # Not a known section — treat as a segment title within current section
            if current_segment:
                segments.append(current_segment)
            current_segment = Segment(
                section=current_section,
                title=header_text,
                order=order,
            )
            order += 1
            continue

        # Segment sub-headers: ### Segment N: Title
        sub_match = re.match(r'^###\s+Segment\s+\d+[:\s]+(.+)$', stripped, re.IGNORECASE)
        if sub_match:
            if current_segment:
                segments.append(current_segment)
            current_segment = Segment(
                section=current_section,
                title=sub_match.group(1).strip(),
                order=order,
            )
            order += 1
            continue

        # IVQ question: **Question:** ... (text continues after **)
        question_match = re.match(r'^\*\*Question:\*\*\s*(.+)$', stripped)
        if question_match and current_segment and current_segment.type == SegmentType.IVQ:
            current_segment.question = question_match.group(1).strip()
            continue

        # Bold segment titles: **Title Text**
        bold_match = re.match(r'^\*\*([^*]+)\*\*\s*$', stripped)
        if bold_match:
            title_text = bold_match.group(1).strip()

            # Skip marker labels (NARRATION:, OUTPUT:, RUN CELL, etc.)
            if title_text.upper() in ("NARRATION:", "OUTPUT:", "[RUN CELL]", "[TYPE]",
                                       "[SHOW]", "[PAUSE]"):
                continue

            # IVQ question detection
            if title_text.startswith("Question:"):
                if current_segment and current_segment.type == SegmentType.IVQ:
                    current_segment.question = title_text.replace("Question:", "").strip()
                continue

            # Start new segment with this title
            if current_segment:
                segments.append(current_segment)
            current_segment = Segment(
                section=current_section,
                title=title_text,
                order=order,
            )
            order += 1
            continue

        # Inline bold markers we should skip
        if stripped.startswith("**NARRATION:**") or stripped.startswith("**OUTPUT:**"):
            # Narration label — the text after it is narration
            after = stripped.split(":**", 1)
            if len(after) > 1 and after[1].strip() and current_segment:
                if current_segment.narration:
                    current_segment.narration += "\n" + after[1].strip()
                else:
                    current_segment.narration = after[1].strip()
            continue

        if stripped in ("**[RUN CELL]**", "**[TYPE]**", "**[SHOW]**", "**[PAUSE]**"):
            continue

        # Visual cues [SCREEN: ...] or [anything in brackets]
        visual_match = re.match(r'^\[(.+)\]$', stripped)
        if visual_match and current_segment:
            cue = visual_match.group(1)
            if current_segment.visual_cue:
                current_segment.visual_cue += " | " + cue
            else:
                current_segment.visual_cue = cue
            continue

        # IVQ answer options: A) ... B) ... etc.
        option_match = re.match(r'^([A-D])\)\s+(.+)$', stripped)
        if option_match and current_segment and current_segment.type == SegmentType.IVQ:
            if current_segment.options is None:
                current_segment.options = []
            current_segment.options.append({
                "letter": option_match.group(1),
                "text": option_match.group(2),
            })
            continue

        # IVQ correct answer
        correct_match = re.match(r'^\*\*Correct Answer:\*\*\s*([A-D])', stripped)
        if correct_match and current_segment and current_segment.type == SegmentType.IVQ:
            current_segment.correct_answer = correct_match.group(1)
            continue

        # IVQ feedback
        feedback_match = re.match(r'^\*\*Feedback ([A-D]):\*\*\s*(.+)$', stripped)
        if feedback_match and current_segment and current_segment.type == SegmentType.IVQ:
            if current_segment.feedback is None:
                current_segment.feedback = {}
            current_segment.feedback[feedback_match.group(1)] = feedback_match.group(2)
            continue

        # Metadata table rows — skip
        if stripped.startswith("|") and stripped.endswith("|"):
            continue

        # Regular narration text
        if stripped and current_segment:
            if current_segment.narration:
                current_segment.narration += "\n" + stripped
            else:
                current_segment.narration = stripped

    # Append last segment
    if current_segment:
        segments.append(current_segment)

    # Estimate durations (150 words per minute)
    for seg in segments:
        if seg.narration:
            words = len(seg.narration.split())
            seg.duration_estimate = round((words / 150) * 60, 1)

    return segments
