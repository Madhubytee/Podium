"""Audio extraction: any audio/video file -> 16 kHz mono 16-bit WAV.

16 kHz mono is what Whisper expects, and it's what the M4 analyzers read for
pitch and volume.
"""

import wave
from pathlib import Path

import numpy as np

from .ffmpeg import run_ffmpeg

SAMPLE_RATE = 16_000


def extract_audio(media_path: str, out_path: str) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-i", media_path,
        "-vn",                  # drop video
        "-ac", "1",             # mono
        "-ar", str(SAMPLE_RATE),
        "-c:a", "pcm_s16le",
        out_path,
    ])
    return out_path


def load_wav(path: str) -> tuple[np.ndarray, int]:
    """Read a 16-bit PCM WAV into float32 samples in [-1, 1]."""
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        channels = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, sr
