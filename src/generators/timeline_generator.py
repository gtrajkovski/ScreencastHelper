"""Timeline Generator - Creates timed event sequences for synchronized playback."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class TimedEvent:
    """A single event in a playback timeline."""
    time: float          # Seconds from segment start
    action: str          # Event type
    params: dict = field(default_factory=dict)


@dataclass
class SegmentTimeline:
    """Complete timeline for one segment."""
    segment_id: int
    events: List[TimedEvent]
    total_duration: float

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "total_duration": self.total_duration,
            "events": [
                {"time": e.time, "action": e.action, "params": e.params}
                for e in self.events
            ]
        }


class TimelineGenerator:
    """Generate timed event timelines for segment playback."""

    def __init__(self, typing_speed_cps: float = 25):
        """
        Args:
            typing_speed_cps: Characters per second for typing estimation
        """
        self.typing_speed = typing_speed_cps

    def generate(self, segment: dict, audio_duration: float) -> SegmentTimeline:
        """Generate a timeline for a single segment.

        Distributes code typing and execution events across the audio duration.

        Args:
            segment: Segment dict with 'id', 'type', 'code_cells' or 'cells', etc.
            audio_duration: Duration of audio in seconds

        Returns:
            SegmentTimeline with ordered events
        """
        seg_id = segment.get('id', 0)
        seg_type = segment.get('type', 'slide')
        events = []

        # Audio start
        events.append(TimedEvent(time=0.0, action='audio_start'))

        if seg_type == 'notebook':
            events.extend(self._generate_notebook_events(segment, audio_duration))
        elif seg_type == 'terminal':
            events.extend(self._generate_terminal_events(segment, audio_duration))
        else:
            events.extend(self._generate_slide_events(segment, audio_duration))

        # Audio end
        events.append(TimedEvent(time=audio_duration, action='audio_end'))
        events.append(TimedEvent(time=audio_duration, action='segment_end'))

        # Sort by time
        events.sort(key=lambda e: e.time)

        return SegmentTimeline(
            segment_id=seg_id,
            events=events,
            total_duration=audio_duration
        )

    def _generate_notebook_events(self, segment: dict,
                                   duration: float) -> List[TimedEvent]:
        """Generate events for notebook-type segments with code cells."""
        events = []
        cells = segment.get('code_cells', segment.get('cells', []))

        if not cells:
            return events

        # Reserve first 10% and last 5% for intro/outro narration
        code_start = duration * 0.10
        code_end = duration * 0.95
        available = code_end - code_start

        # Distribute time across cells
        num_cells = len(cells)
        time_per_cell = available / num_cells

        for i, cell in enumerate(cells):
            cell_start = code_start + i * time_per_cell
            code = cell.get('code', '')
            output = cell.get('output', '')

            # Estimate typing duration
            typing_duration = len(code) / self.typing_speed
            # Cap at 80% of cell time to leave room for execution
            typing_duration = min(typing_duration, time_per_cell * 0.8)

            # Focus cell
            events.append(TimedEvent(
                time=cell_start,
                action='focusCell',
                params={'cellIndex': i, 'cellId': cell.get('id', f'cell_{i}')}
            ))

            # Start typing
            type_start = cell_start + 0.3
            events.append(TimedEvent(
                time=type_start,
                action='startTyping',
                params={
                    'cellIndex': i,
                    'code': code,
                    'duration': typing_duration
                }
            ))

            # Execute cell (after typing completes)
            exec_time = type_start + typing_duration + 0.5
            if exec_time < cell_start + time_per_cell:
                events.append(TimedEvent(
                    time=exec_time,
                    action='executeCell',
                    params={'cellIndex': i}
                ))

                # Show output
                if output:
                    events.append(TimedEvent(
                        time=exec_time + 0.3,
                        action='showOutput',
                        params={'cellIndex': i, 'output': output}
                    ))

        return events

    def _generate_terminal_events(self, segment: dict,
                                   duration: float) -> List[TimedEvent]:
        """Generate events for terminal-type segments."""
        events = []
        cells = segment.get('code_cells', segment.get('cells', []))

        if not cells:
            return events

        code_start = duration * 0.10
        code_end = duration * 0.90
        available = code_end - code_start
        time_per_cmd = available / len(cells)

        for i, cell in enumerate(cells):
            cmd_start = code_start + i * time_per_cmd
            code = cell.get('code', '')
            output = cell.get('output', '')

            typing_duration = len(code) / self.typing_speed
            typing_duration = min(typing_duration, time_per_cmd * 0.6)

            events.append(TimedEvent(
                time=cmd_start,
                action='showPrompt',
                params={'commandIndex': i}
            ))

            events.append(TimedEvent(
                time=cmd_start + 0.2,
                action='startTyping',
                params={'commandIndex': i, 'code': code, 'duration': typing_duration}
            ))

            if output:
                events.append(TimedEvent(
                    time=cmd_start + 0.2 + typing_duration + 0.3,
                    action='showOutput',
                    params={'commandIndex': i, 'output': output}
                ))

        return events

    def _generate_slide_events(self, segment: dict,
                                duration: float) -> List[TimedEvent]:
        """Generate events for slide-type segments (bullet appearance)."""
        events = []
        slide_content = segment.get('slide_content', {})
        bullets = slide_content.get('bullets', [])

        if not bullets:
            return events

        # Stagger bullet appearance across the duration
        delay = duration / (len(bullets) + 1)

        for i, bullet in enumerate(bullets):
            events.append(TimedEvent(
                time=delay * (i + 1),
                action='showBullet',
                params={'index': i, 'text': bullet}
            ))

        return events

    def generate_all(self, segments: List[dict],
                      audio_durations: List[float]) -> List[SegmentTimeline]:
        """Generate timelines for all segments.

        Args:
            segments: List of segment dicts
            audio_durations: Corresponding audio durations in seconds

        Returns:
            List of SegmentTimeline objects
        """
        timelines = []
        for seg, duration in zip(segments, audio_durations):
            timelines.append(self.generate(seg, duration))
        return timelines
