"""Generate recording sessions from parsed scripts."""

import re
from typing import List, Optional, Dict, Any

from src.recording.models import (
    RecordingSession, RecordingCue, CueType, RecordingMode,
    TimelineTrack, TeleprompterSettings,
)


class RecordingSessionGenerator:
    """Generate a structured recording session from a project's script and segments."""

    # Patterns for extracting cue-relevant markers
    VISUAL_CUE_PATTERN = re.compile(r'\[SCREEN:\s*([^\]]+)\]', re.IGNORECASE)
    PAUSE_PATTERN = re.compile(r'\*?\*?\[PAUSE\]\*?\*?', re.IGNORECASE)
    CODE_BLOCK_PATTERN = re.compile(r'```(\w+)?\n(.*?)```', re.DOTALL)
    RUN_CELL_PATTERN = re.compile(r'\*?\*?\[RUN CELL\]\*?\*?', re.IGNORECASE)
    SECTION_PATTERN = re.compile(
        r'^##?\s*(HOOK|OBJECTIVE|CONTENT|SUMMARY|CALL TO ACTION|CTA|IN-VIDEO QUESTION|IVQ)',
        re.IGNORECASE | re.MULTILINE,
    )

    # Words per minute for duration estimates
    WPM = 150

    def generate_session(
        self,
        project_id: str,
        raw_script: str,
        segments: Optional[List[Dict[str, Any]]] = None,
        mode: RecordingMode = RecordingMode.TELEPROMPTER,
    ) -> RecordingSession:
        """Generate a complete recording session from a script.

        Args:
            project_id: The project this session belongs to.
            raw_script: The raw markdown script text.
            segments: Optional pre-parsed segments (list of dicts).
            mode: The initial recording mode.

        Returns:
            A populated RecordingSession.
        """
        cues = self._parse_script_to_cues(raw_script)
        total_duration = sum(c.duration_estimate for c in cues)
        timeline_tracks = self._generate_timeline_tracks(cues)

        return RecordingSession(
            project_id=project_id,
            mode=mode,
            cues=cues,
            timeline_tracks=timeline_tracks,
            total_duration_estimate=round(total_duration, 1),
        )

    def _parse_script_to_cues(self, raw_script: str) -> List[RecordingCue]:
        """Parse the full script into an ordered list of recording cues."""
        cues: List[RecordingCue] = []
        order = 0

        # Split into sections
        parts = self.SECTION_PATTERN.split(raw_script)

        current_section = ""
        for i, part in enumerate(parts):
            upper = part.strip().upper()
            if upper in ("HOOK", "OBJECTIVE", "CONTENT", "SUMMARY",
                         "CALL TO ACTION", "CTA", "IN-VIDEO QUESTION", "IVQ"):
                current_section = upper
                if current_section == "CTA":
                    current_section = "CALL TO ACTION"
                if current_section == "IN-VIDEO QUESTION":
                    current_section = "IVQ"
                continue

            if not part.strip():
                continue

            section_cues = self._parse_section_to_cues(part, current_section, order)
            for cue in section_cues:
                cues.append(cue)
                order += 1

        # Re-number all cues sequentially
        for idx, cue in enumerate(cues):
            cue.order = idx

        return cues

    def _parse_section_to_cues(
        self, text: str, section: str, start_order: int
    ) -> List[RecordingCue]:
        """Parse a single section's text into cues."""
        cues: List[RecordingCue] = []
        order = start_order

        # Extract code blocks and replace with placeholders
        code_blocks: List[str] = []
        def replace_code(match):
            code_blocks.append(match.group(2).strip())
            return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

        processed = self.CODE_BLOCK_PATTERN.sub(replace_code, text)

        # Split into content chunks
        chunks = self._split_content(processed)

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            # Check for code block placeholder
            code_match = re.match(r'__CODE_BLOCK_(\d+)__', chunk)
            if code_match:
                idx = int(code_match.group(1))
                if idx < len(code_blocks):
                    cues.append(RecordingCue(
                        cue_type=CueType.CODE_ACTION,
                        section=section,
                        text=code_blocks[idx],
                        duration_estimate=self._estimate_code_duration(code_blocks[idx]),
                        order=order,
                        notes="Execute code in demo environment",
                    ))
                    order += 1
                continue

            # Check for pause markers
            if self.PAUSE_PATTERN.search(chunk):
                # Strip the pause marker and add remaining text as narration if any
                remaining = self.PAUSE_PATTERN.sub('', chunk).strip()
                if remaining:
                    cues.append(RecordingCue(
                        cue_type=CueType.NARRATION,
                        section=section,
                        text=remaining,
                        duration_estimate=self._estimate_duration(remaining),
                        order=order,
                    ))
                    order += 1
                cues.append(RecordingCue(
                    cue_type=CueType.PAUSE,
                    section=section,
                    text="[PAUSE]",
                    duration_estimate=2.0,
                    order=order,
                    notes="Let the audience absorb the information",
                ))
                order += 1
                continue

            # Check for visual cues
            visual_matches = self.VISUAL_CUE_PATTERN.findall(chunk)
            if visual_matches:
                for vc in visual_matches:
                    cues.append(RecordingCue(
                        cue_type=CueType.VISUAL_CUE,
                        section=section,
                        text=vc.strip(),
                        duration_estimate=1.0,
                        order=order,
                        notes="Switch visual/screen display",
                    ))
                    order += 1
                # Add remaining narration text
                narration_text = self.VISUAL_CUE_PATTERN.sub('', chunk).strip()
                if narration_text:
                    cues.append(RecordingCue(
                        cue_type=CueType.NARRATION,
                        section=section,
                        text=narration_text,
                        duration_estimate=self._estimate_duration(narration_text),
                        order=order,
                    ))
                    order += 1
                continue

            # Check for RUN CELL markers
            if self.RUN_CELL_PATTERN.search(chunk):
                remaining = self.RUN_CELL_PATTERN.sub('', chunk).strip()
                if remaining:
                    cues.append(RecordingCue(
                        cue_type=CueType.NARRATION,
                        section=section,
                        text=remaining,
                        duration_estimate=self._estimate_duration(remaining),
                        order=order,
                    ))
                    order += 1
                cues.append(RecordingCue(
                    cue_type=CueType.CODE_ACTION,
                    section=section,
                    text="[RUN CELL]",
                    duration_estimate=2.0,
                    order=order,
                    notes="Execute the current cell",
                ))
                order += 1
                continue

            # Plain narration
            cues.append(RecordingCue(
                cue_type=CueType.NARRATION,
                section=section,
                text=chunk,
                duration_estimate=self._estimate_duration(chunk),
                order=order,
            ))
            order += 1

        return cues

    def _split_content(self, text: str) -> List[str]:
        """Split section text into logical chunks for cueing.

        Splits on double newlines, code block placeholders, and
        pause/visual markers while keeping them as separate chunks.
        """
        # Split on double newlines first
        paragraphs = re.split(r'\n\n+', text)
        chunks: List[str] = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If paragraph contains a code block placeholder, split around it
            code_parts = re.split(r'(__CODE_BLOCK_\d+__)', para)
            if len(code_parts) > 1:
                for cp in code_parts:
                    cp = cp.strip()
                    if cp:
                        chunks.append(cp)
            else:
                chunks.append(para)

        return chunks

    def _estimate_duration(self, text: str) -> float:
        """Estimate narration duration from word count."""
        # Strip markdown formatting
        clean = re.sub(r'\*\*.*?\*\*', '', text)
        clean = re.sub(r'#+ ', '', clean)
        clean = re.sub(r'\[.*?\]', '', clean)
        words = len(clean.split())
        return round(max(1.0, (words / self.WPM) * 60), 1)

    def _estimate_code_duration(self, code: str) -> float:
        """Estimate how long it takes to type/execute code."""
        lines = [l for l in code.split('\n') if l.strip()]
        # ~3 seconds per line of code (typing + execution)
        return round(max(2.0, len(lines) * 3.0), 1)

    def _generate_timeline_tracks(self, cues: List[RecordingCue]) -> List[TimelineTrack]:
        """Generate timeline tracks from cues for the timeline view."""
        narration_events: List[Dict[str, Any]] = []
        code_events: List[Dict[str, Any]] = []
        visual_events: List[Dict[str, Any]] = []

        current_time = 0.0

        for cue in cues:
            event = {
                "cue_id": cue.id,
                "start_time": round(current_time, 1),
                "duration": cue.duration_estimate,
                "end_time": round(current_time + cue.duration_estimate, 1),
                "text": cue.text[:80],
                "section": cue.section,
            }

            if cue.cue_type == CueType.NARRATION:
                narration_events.append(event)
            elif cue.cue_type in (CueType.CODE_ACTION,):
                code_events.append(event)
            elif cue.cue_type == CueType.VISUAL_CUE:
                visual_events.append(event)
            # Pauses and transitions don't get a dedicated track

            current_time += cue.duration_estimate

        tracks = []
        if narration_events:
            tracks.append(TimelineTrack(
                name="Narration",
                track_type="narration",
                events=narration_events,
            ))
        if code_events:
            tracks.append(TimelineTrack(
                name="Code",
                track_type="code",
                events=code_events,
            ))
        if visual_events:
            tracks.append(TimelineTrack(
                name="Visuals",
                track_type="visual",
                events=visual_events,
            ))

        return tracks
