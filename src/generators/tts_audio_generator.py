"""TTS Audio Generator - Creates MP3 audio from narration text using Edge TTS."""

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class AudioSegment:
    """Result of generating audio for one segment."""
    segment_id: int
    section: str
    text: str
    audio_path: str
    duration_seconds: float
    file_size_bytes: int


@dataclass
class GeneratedAudio:
    """Result of generating audio for all segments."""
    segments: List[AudioSegment]
    total_duration_seconds: float
    output_dir: str


class TTSAudioGenerator:
    """Generate TTS audio files using Microsoft Edge TTS."""

    def __init__(self, voice: str = "en-US-AriaNeural", rate: str = "+0%", pitch: str = "+0Hz"):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    async def generate_segment(self, segment_id: int, section: str,
                                text: str, output_path: str) -> AudioSegment:
        """Generate audio for a single segment.

        Args:
            segment_id: Segment index
            section: WWHAA section name
            text: Narration text to synthesize
            output_path: Path to save MP3 file

        Returns:
            AudioSegment with duration and file metadata
        """
        import edge_tts

        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch
        )
        await communicate.save(output_path)

        # Read duration from generated file
        duration_seconds = self._get_mp3_duration(output_path)
        file_size = os.path.getsize(output_path)

        return AudioSegment(
            segment_id=segment_id,
            section=section,
            text=text,
            audio_path=output_path,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size
        )

    async def generate_all(self, segments: List[dict], output_dir: str) -> GeneratedAudio:
        """Generate audio for all segments.

        Args:
            segments: List of segment dicts with 'id', 'section', 'narration' keys
            output_dir: Directory to save MP3 files

        Returns:
            GeneratedAudio with all segment results
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        results = []

        for seg in segments:
            seg_id = seg['id']
            section = seg.get('section', 'CONTENT')
            narration = seg.get('narration', '')
            if isinstance(narration, dict):
                narration = narration.get('text', '')

            if not narration.strip():
                continue

            filename = f"{seg_id:02d}_{section.lower()}.mp3"
            output_path = str(Path(output_dir) / filename)

            audio_seg = await self.generate_segment(
                segment_id=seg_id,
                section=section,
                text=narration,
                output_path=output_path
            )
            results.append(audio_seg)

        total_duration = sum(s.duration_seconds for s in results)

        return GeneratedAudio(
            segments=results,
            total_duration_seconds=total_duration,
            output_dir=output_dir
        )

    def generate_sync(self, segments: List[dict], output_dir: str) -> GeneratedAudio:
        """Synchronous wrapper for generate_all()."""
        return asyncio.run(self.generate_all(segments, output_dir))

    @staticmethod
    def _get_mp3_duration(filepath: str) -> float:
        """Get MP3 duration in seconds using mutagen."""
        try:
            from mutagen.mp3 import MP3
            audio = MP3(filepath)
            return audio.info.length
        except Exception:
            # Fallback: estimate from file size (128kbps ~ 16KB/sec)
            size = os.path.getsize(filepath)
            return size / 16000

    @staticmethod
    def list_voices_sync() -> List[dict]:
        """List available Edge TTS voices (English only)."""
        async def _list():
            import edge_tts
            voices = await edge_tts.list_voices()
            return [
                {
                    "id": v["ShortName"],
                    "name": v["FriendlyName"],
                    "language": v["Locale"],
                    "gender": v["Gender"]
                }
                for v in voices
                if v["Locale"].startswith("en-")
            ]
        return asyncio.run(_list())
