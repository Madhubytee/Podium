"""Speech transcription with Whisper, with a timestamp on every word.

Two backends, picked with PODIUM_WHISPER_BACKEND:
  - "local"  (default): faster-whisper on the CPU. Free, no key needed.
  - "openai": the OpenAI Whisper API. No model download, about $0.006 per minute.

Word timestamps are what the M4 analyzers need for pace, pauses, and fillers.

Whisper normally "cleans up" disfluencies and drops um/uh. We pass an initial
prompt written in a disfluent style, which is a known way to make Whisper keep
filler words in the transcript.
"""

import os
from functools import lru_cache

from .audio import load_wav

BACKEND = os.getenv("PODIUM_WHISPER_BACKEND", "local")
MODEL_NAME = os.getenv("PODIUM_WHISPER_MODEL", "small.en")
DEVICE = os.getenv("PODIUM_WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("PODIUM_WHISPER_COMPUTE", "int8")
API_MODEL = os.getenv("PODIUM_WHISPER_API_MODEL", "whisper-1")

FILLER_PROMPT = "Umm, so, uh, I was like, you know, thinking about it. Hmm, okay, so, um, here's the thing."


def transcribe(audio_path: str, language: str | None = None) -> dict:
    """Returns {text, language, segments: [{start, end, text}], words: [{text, start, end, conf}]}."""
    if BACKEND == "openai":
        return transcribe_openai(audio_path, language)
    return _transcribe_local(audio_path, language)


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel

    return WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)


def _transcribe_local(audio_path: str, language: str | None) -> dict:
    if language is None and MODEL_NAME.endswith(".en"):
        language = "en"
    # Pass samples, not a path: our WAV is already 16 kHz mono, and this skips
    # faster-whisper's PyAV decoder (newer PyAV releases break its open() call).
    samples, _sr = load_wav(audio_path)
    segments_iter, info = _model().transcribe(
        samples,
        language=language,
        word_timestamps=True,
        initial_prompt=FILLER_PROMPT,
        condition_on_previous_text=False,  # stops the prompt style from snowballing into hallucinations
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    segments, words = [], []
    for seg in segments_iter:
        segments.append({
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
        })
        for w in seg.words or []:
            token = w.word.strip()
            if not token:
                continue
            words.append({
                "text": token,
                "start": round(w.start, 3),
                "end": round(w.end, 3),
                "conf": round(w.probability, 3),
            })

    return {
        "text": " ".join(s["text"] for s in segments).strip(),
        "language": info.language,
        "segments": segments,
        "words": words,
    }


@lru_cache(maxsize=1)
def _client():
    from openai import OpenAI

    return OpenAI()  # reads OPENAI_API_KEY


def transcribe_openai(audio_path: str, language: str | None = None) -> dict:
    """Whisper API. Also used directly by live mode to transcribe each answer."""
    with open(audio_path, "rb") as f:
        resp = _client().audio.transcriptions.create(
            model=API_MODEL,
            file=f,
            language=language or "en",
            prompt=FILLER_PROMPT,
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
        )

    words = [
        # The API doesn't return per-word confidence; 1.0 keeps the clarity metric neutral.
        {"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3), "conf": 1.0}
        for w in (resp.words or []) if w.word.strip()
    ]
    segments = [
        {"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()}
        for s in (resp.segments or [])
    ]
    return {"text": resp.text.strip(), "language": resp.language, "segments": segments, "words": words}
