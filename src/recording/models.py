"""Data models for the Recording Studio feature."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class RecordingMode(Enum):
    TELEPROMPTER = "teleprompter"
    CUE_SYSTEM = "cue_system"
    REHEARSAL = "rehearsal"
    TIMELINE = "timeline"


class CueType(Enum):
    NARRATION = "narration"
    CODE_ACTION = "code_action"
    VISUAL_CUE = "visual_cue"
    PAUSE = "pause"
    TRANSITION = "transition"


@dataclass
class RecordingCue:
    """A single cue in the recording session."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    cue_type: CueType = CueType.NARRATION
    section: str = ""
    text: str = ""
    duration_estimate: float = 0.0
    order: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "cue_type": self.cue_type.value,
            "section": self.section,
            "text": self.text,
            "duration_estimate": self.duration_estimate,
            "order": self.order,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecordingCue":
        data = dict(data)
        if "cue_type" in data and isinstance(data["cue_type"], str):
            try:
                data["cue_type"] = CueType(data["cue_type"])
            except ValueError:
                data["cue_type"] = CueType.NARRATION
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class TeleprompterSettings:
    """Settings for the teleprompter display."""
    font_size: int = 32
    scroll_speed: float = 1.0
    line_height: float = 1.8
    mirror: bool = False
    highlight_current: bool = True
    countdown_seconds: int = 3
    auto_scroll: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "font_size": self.font_size,
            "scroll_speed": self.scroll_speed,
            "line_height": self.line_height,
            "mirror": self.mirror,
            "highlight_current": self.highlight_current,
            "countdown_seconds": self.countdown_seconds,
            "auto_scroll": self.auto_scroll,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeleprompterSettings":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class RehearsalResult:
    """Result of a rehearsal run."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    actual_duration: float = 0.0
    target_duration: float = 0.0
    section_timings: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def pace_ratio(self) -> float:
        if self.target_duration == 0:
            return 0.0
        return self.actual_duration / self.target_duration

    @property
    def pace_feedback(self) -> str:
        ratio = self.pace_ratio
        if ratio == 0:
            return "no data"
        if ratio < 0.85:
            return "too fast"
        if ratio > 1.15:
            return "too slow"
        return "good pace"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "actual_duration": self.actual_duration,
            "target_duration": self.target_duration,
            "pace_ratio": round(self.pace_ratio, 2),
            "pace_feedback": self.pace_feedback,
            "section_timings": self.section_timings,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RehearsalResult":
        data = dict(data)
        data.pop("pace_ratio", None)
        data.pop("pace_feedback", None)
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class TimelineTrack:
    """A track in the recording timeline."""
    name: str = ""
    track_type: str = "narration"  # narration, code, visual, audio
    events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "track_type": self.track_type,
            "events": self.events,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineTrack":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class RecordingSession:
    """Complete recording session with cues, settings, and results."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_id: str = ""
    mode: RecordingMode = RecordingMode.TELEPROMPTER
    cues: List[RecordingCue] = field(default_factory=list)
    teleprompter_settings: TeleprompterSettings = field(default_factory=TeleprompterSettings)
    timeline_tracks: List[TimelineTrack] = field(default_factory=list)
    rehearsals: List[RehearsalResult] = field(default_factory=list)
    total_duration_estimate: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "mode": self.mode.value,
            "cues": [c.to_dict() for c in self.cues],
            "teleprompter_settings": self.teleprompter_settings.to_dict(),
            "timeline_tracks": [t.to_dict() for t in self.timeline_tracks],
            "rehearsals": [r.to_dict() for r in self.rehearsals],
            "total_duration_estimate": self.total_duration_estimate,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecordingSession":
        data = dict(data)
        if "mode" in data and isinstance(data["mode"], str):
            try:
                data["mode"] = RecordingMode(data["mode"])
            except ValueError:
                data["mode"] = RecordingMode.TELEPROMPTER

        cues_data = data.pop("cues", [])
        tp_data = data.pop("teleprompter_settings", {})
        tracks_data = data.pop("timeline_tracks", [])
        rehearsals_data = data.pop("rehearsals", [])

        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        session = cls(**filtered)
        session.cues = [RecordingCue.from_dict(c) for c in cues_data]
        session.teleprompter_settings = TeleprompterSettings.from_dict(tp_data) if tp_data else TeleprompterSettings()
        session.timeline_tracks = [TimelineTrack.from_dict(t) for t in tracks_data]
        session.rehearsals = [RehearsalResult.from_dict(r) for r in rehearsals_data]
        return session
