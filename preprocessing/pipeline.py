"""M3 entry point: turn one recording into the inputs every analyzer needs.

Output contract (consumed by M4 analyzers):

{
  "media_path": str,          # original upload
  "duration_s": float,
  "has_video": bool,
  "audio": {"path": str, "sample_rate": 16000},
  "transcript": {
      "text": str, "language": str,
      "segments": [{"start", "end", "text"}],
      "words": [{"text", "start", "end", "conf"}],
  },
  "frames": [{"t": float, "path": str}],   # empty when there is no video
  "frame_fps": float,
}
"""

import json
from pathlib import Path

from .audio import SAMPLE_RATE, extract_audio
from .ffmpeg import probe
from .frames import DEFAULT_FPS, extract_frames
from .transcribe import transcribe


class PreprocessError(RuntimeError):
    pass


def preprocess(media_path: str, work_dir: str, fps: float = DEFAULT_FPS,
               language: str | None = None, on_step=None) -> dict:
    """Run audio extraction, transcription, and frame extraction.

    `on_step(name)` is an optional progress callback ("audio", "transcript", "frames").
    The result is also written to `<work_dir>/preprocessed.json`.
    """
    step = on_step or (lambda _name: None)
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)

    info = probe(media_path)
    if not info["has_audio"]:
        raise PreprocessError("This recording has no audio track, so there's nothing to coach.")

    step("audio")
    audio_path = extract_audio(media_path, str(work / "audio.wav"))

    step("transcript")
    transcript = transcribe(audio_path, language=language)

    frames = []
    if info["has_video"]:
        step("frames")
        frames = extract_frames(media_path, str(work / "frames"), fps=fps)

    duration = info["duration_s"]
    if duration is None:  # browser-recorded webm often has no duration header
        duration = _wav_duration(audio_path)

    result = {
        "media_path": str(media_path),
        "duration_s": round(duration, 3),
        "has_video": bool(frames),
        "audio": {"path": audio_path, "sample_rate": SAMPLE_RATE},
        "transcript": transcript,
        "frames": frames,
        "frame_fps": fps,
    }
    (work / "preprocessed.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _wav_duration(path: str) -> float:
    import wave

    with wave.open(path, "rb") as wf:
        return wf.getnframes() / wf.getframerate()
