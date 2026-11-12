"""Locate and run ffmpeg / ffprobe.

Prefers a system install on PATH; falls back to the binary bundled with the
`imageio-ffmpeg` package so teammates don't need to install ffmpeg by hand.
"""

import json
import shutil
import subprocess
from functools import lru_cache


class FFmpegError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def ffmpeg_path() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise FFmpegError(
            "ffmpeg not found. Install it (https://ffmpeg.org) or `pip install imageio-ffmpeg`."
        ) from exc


def run_ffmpeg(args: list[str]) -> None:
    cmd = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(f"ffmpeg failed: {result.stderr.strip()}")


def probe(media_path: str) -> dict:
    """Return {duration_s, has_audio, has_video} for a media file.

    Uses ffprobe when available; otherwise parses `ffmpeg -i` output (the
    imageio-ffmpeg bundle ships without ffprobe).
    """
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type",
             "-of", "json", media_path],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise FFmpegError(f"ffprobe failed: {result.stderr.strip()}")
        info = json.loads(result.stdout)
        kinds = {s.get("codec_type") for s in info.get("streams", [])}
        duration = info.get("format", {}).get("duration")
        return {
            "duration_s": float(duration) if duration not in (None, "N/A") else None,
            "has_audio": "audio" in kinds,
            "has_video": "video" in kinds,
        }

    result = subprocess.run([ffmpeg_path(), "-hide_banner", "-i", media_path],
                            capture_output=True, text=True)
    err = result.stderr
    duration = None
    for line in err.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            stamp = line.split(",")[0].split("Duration:")[1].strip()
            if stamp != "N/A":
                h, m, s = stamp.split(":")
                duration = int(h) * 3600 + int(m) * 60 + float(s)
    return {
        "duration_s": duration,
        "has_audio": "Audio:" in err,
        "has_video": "Video:" in err,
    }
