"""Recording service — FFmpeg integration for video processing.

Provides optional FFmpeg-based operations:
- Merge audio + video
- Concatenate segments
- Trim segments
- Screen capture via gdigrab
- Check FFmpeg availability

Degrades gracefully when FFmpeg is not installed.
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Tuple


def find_ffmpeg() -> Optional[str]:
    """Find FFmpeg binary in PATH or common install locations."""
    # Check PATH first
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg

    # Check common Windows install locations
    common_paths = [
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe"),
    ]
    for p in common_paths:
        if p.exists():
            return str(p)

    # Check winget install location
    local_app = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet"
    if local_app.exists():
        for ffmpeg_exe in local_app.rglob("ffmpeg.exe"):
            return str(ffmpeg_exe)

    return None


def is_ffmpeg_available() -> bool:
    """Check if FFmpeg is available on the system."""
    return find_ffmpeg() is not None


def get_ffmpeg_version() -> Optional[str]:
    """Get FFmpeg version string, or None if unavailable."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return None
    try:
        result = subprocess.run(
            [ffmpeg, "-version"],
            capture_output=True, text=True, timeout=10
        )
        first_line = result.stdout.split("\n")[0]
        return first_line
    except Exception:
        return None


def merge_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    overwrite: bool = True,
) -> Tuple[bool, str]:
    """Merge an audio file with a video file.

    Args:
        video_path: Path to video file (e.g., .webm)
        audio_path: Path to audio file (e.g., .mp3)
        output_path: Path for merged output
        overwrite: Whether to overwrite existing output

    Returns:
        (success, message) tuple
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False, "FFmpeg not found"

    if not Path(video_path).exists():
        return False, f"Video file not found: {video_path}"
    if not Path(audio_path).exists():
        return False, f"Audio file not found: {audio_path}"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg,
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
    ]
    if overwrite:
        cmd.append("-y")
    cmd.append(output_path)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return True, f"Merged to {output_path}"
        return False, f"FFmpeg error: {result.stderr[-500:]}"
    except subprocess.TimeoutExpired:
        return False, "FFmpeg timed out"
    except Exception as e:
        return False, str(e)


def concatenate_segments(
    input_paths: List[str],
    output_path: str,
    overwrite: bool = True,
) -> Tuple[bool, str]:
    """Concatenate multiple video/audio segments into one file.

    Args:
        input_paths: List of paths to input files (same format)
        output_path: Path for concatenated output
        overwrite: Whether to overwrite existing output

    Returns:
        (success, message) tuple
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False, "FFmpeg not found"

    if not input_paths:
        return False, "No input files provided"

    for p in input_paths:
        if not Path(p).exists():
            return False, f"File not found: {p}"

    # Create concat list file
    list_path = Path(output_path).parent / "_concat_list.txt"
    with open(list_path, "w") as f:
        for p in input_paths:
            # FFmpeg concat demuxer needs forward slashes
            safe = str(Path(p).resolve()).replace("\\", "/")
            f.write(f"file '{safe}'\n")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg,
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-c", "copy",
    ]
    if overwrite:
        cmd.append("-y")
    cmd.append(output_path)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        list_path.unlink(missing_ok=True)
        if result.returncode == 0:
            return True, f"Concatenated {len(input_paths)} files to {output_path}"
        return False, f"FFmpeg error: {result.stderr[-500:]}"
    except subprocess.TimeoutExpired:
        list_path.unlink(missing_ok=True)
        return False, "FFmpeg timed out"
    except Exception as e:
        list_path.unlink(missing_ok=True)
        return False, str(e)


def trim_segment(
    input_path: str,
    output_path: str,
    start_seconds: float = 0,
    end_seconds: Optional[float] = None,
    overwrite: bool = True,
) -> Tuple[bool, str]:
    """Trim a video/audio file to a time range.

    Args:
        input_path: Path to input file
        output_path: Path for trimmed output
        start_seconds: Start time in seconds
        end_seconds: End time in seconds (None = to end of file)
        overwrite: Whether to overwrite existing output

    Returns:
        (success, message) tuple
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False, "FFmpeg not found"

    if not Path(input_path).exists():
        return False, f"File not found: {input_path}"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg,
        "-i", input_path,
        "-ss", str(start_seconds),
    ]
    if end_seconds is not None:
        cmd.extend(["-to", str(end_seconds)])
    cmd.extend(["-c", "copy"])
    if overwrite:
        cmd.append("-y")
    cmd.append(output_path)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return True, f"Trimmed to {output_path}"
        return False, f"FFmpeg error: {result.stderr[-500:]}"
    except subprocess.TimeoutExpired:
        return False, "FFmpeg timed out"
    except Exception as e:
        return False, str(e)


def start_screen_capture(
    output_path: str,
    width: int = 1920,
    height: int = 1080,
    offset_x: int = 0,
    offset_y: int = 0,
    fps: int = 30,
) -> Tuple[Optional[subprocess.Popen], str]:
    """Start FFmpeg gdigrab screen capture as a background process.

    The returned Popen has stdin=PIPE so the caller can send b'q' to
    gracefully stop recording.

    Args:
        output_path: Path for the output .mp4 file
        width: Capture width in pixels
        height: Capture height in pixels
        offset_x: Horizontal offset from top-left of desktop
        offset_y: Vertical offset from top-left of desktop
        fps: Frames per second

    Returns:
        (process, error_message) — process is a Popen on success, None on failure
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return None, "FFmpeg not found"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg, '-y',
        '-f', 'gdigrab',
        '-framerate', str(fps),
        '-offset_x', str(offset_x),
        '-offset_y', str(offset_y),
        '-video_size', f'{width}x{height}',
        '-i', 'desktop',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p',
        '-crf', '23',
        str(output_path),
    ]

    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creation_flags,
        )
        return process, ""
    except Exception as e:
        return None, str(e)


def stop_screen_capture(process: subprocess.Popen, timeout: int = 10) -> bool:
    """Gracefully stop an FFmpeg screen capture process.

    Sends 'q' to stdin, waits for clean shutdown.  Falls back to kill().

    Returns True if the process exited cleanly.
    """
    if process is None or process.poll() is not None:
        return True

    try:
        process.stdin.write(b'q')
        process.stdin.flush()
        process.wait(timeout=timeout)
        return True
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
        return False
