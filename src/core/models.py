"""Canonical data models for ScreenCast Studio v5.0."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
import uuid


class SegmentType(Enum):
    SLIDE = "slide"
    SCREENCAST = "screencast"
    IVQ = "ivq"


class SegmentStatus(Enum):
    DRAFT = "draft"
    RECORDED = "recorded"
    APPROVED = "approved"


@dataclass
class Segment:
    """Canonical segment model supporting all segment types."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: SegmentType = SegmentType.SLIDE
    section: str = ""
    title: str = ""
    narration: str = ""
    visual_cue: str = ""
    code: Optional[str] = None
    duration_estimate: Optional[float] = None
    status: SegmentStatus = SegmentStatus.DRAFT

    # Recording data
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    recorded_duration: Optional[float] = None

    # IVQ-specific fields
    question: Optional[str] = None
    options: Optional[List[Dict[str, str]]] = None
    correct_answer: Optional[str] = None
    feedback: Optional[Dict[str, str]] = None

    # Metadata
    order: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "section": self.section,
            "title": self.title,
            "narration": self.narration,
            "visual_cue": self.visual_cue,
            "code": self.code,
            "duration_estimate": self.duration_estimate,
            "status": self.status.value,
            "audio_path": self.audio_path,
            "video_path": self.video_path,
            "recorded_duration": self.recorded_duration,
            "question": self.question,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "feedback": self.feedback,
            "order": self.order,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Segment":
        data = dict(data)
        if "type" in data and isinstance(data["type"], str):
            try:
                data["type"] = SegmentType(data["type"])
            except ValueError:
                data["type"] = SegmentType.SLIDE
        if "status" in data and isinstance(data["status"], str):
            try:
                data["status"] = SegmentStatus(data["status"])
            except ValueError:
                data["status"] = SegmentStatus.DRAFT
        # Filter to only known fields to handle schema evolution
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class Project:
    """Unified project model with disk persistence."""
    id: str = field(default_factory=lambda: f"proj_{uuid.uuid4().hex[:12]}")
    title: str = "Untitled Project"
    description: str = ""

    # Content
    raw_script: str = ""
    segments: List[Segment] = field(default_factory=list)

    # Configuration
    target_duration: int = 7
    environment: str = "jupyter"
    audience_level: str = "intermediate"
    style: str = "tutorial"

    # Generated assets
    tts_script: str = ""
    timeline: Optional[Dict[str, Any]] = None
    datasets: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    schema_version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "raw_script": self.raw_script,
            "segments": [s.to_dict() for s in self.segments],
            "target_duration": self.target_duration,
            "environment": self.environment,
            "audience_level": self.audience_level,
            "style": self.style,
            "tts_script": self.tts_script,
            "timeline": self.timeline,
            "datasets": self.datasets,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        data = dict(data)
        segments_data = data.pop("segments", [])
        # Filter to only known fields to handle schema evolution
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        project = cls(**filtered)
        project.segments = [Segment.from_dict(s) for s in segments_data]
        return project
