"""Voice analysis: how it was said. Pitch with parselmouth (Praat), volume from RMS.

Thresholds (what counts as monotone, too quiet, ...) live in the knowledge base,
not here; this module only measures.
"""

import numpy as np
import parselmouth

from preprocessing import load_wav

ENERGY_WINDOW_S = 5.0
TAIL_S = 0.5  # guide: drop over the last 0.5 s of each sentence catches trailing off


def analyze_voice(audio_path: str, sentences: list[dict]) -> dict:
    samples, sr = load_wav(audio_path)
    if len(samples) < sr // 2:
        return {"available": False}

    snd = parselmouth.Sound(samples.astype(np.float64), sampling_frequency=sr)
    pitch = snd.to_pitch(time_step=0.01)
    f0 = pitch.selected_array["frequency"]
    times = pitch.xs()
    voiced = f0 > 0

    out = {"available": bool(voiced.sum() > 50)}
    if out["available"]:
        v = f0[voiced]
        out["pitch"] = {
            "mean_hz": round(float(v.mean()), 1),
            "sd_hz": round(float(v.std()), 1),
            "range_hz": round(float(np.percentile(v, 95) - np.percentile(v, 5)), 1),
        }

    # Volume: RMS in 50 ms frames, as dBFS.
    hop = int(0.05 * sr)
    n = len(samples) // hop
    rms = np.sqrt(np.mean(samples[: n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    db_t = (np.arange(n) + 0.5) * 0.05
    speech = db > (np.percentile(db, 95) - 30)
    out["volume"] = {"mean_db": round(float(db[speech].mean()), 1) if speech.any() else None}

    out["trailing"] = _trailing_off(db_t, db, sentences)
    out["energy_timeline"] = _energy_timeline(db_t, db, speech, times, f0)
    return out


def _trailing_off(db_t: np.ndarray, db: np.ndarray, sentences: list[dict]) -> list[dict]:
    """Sentences whose last 0.5 s is much quieter than the rest of the sentence."""
    out = []
    for s in sentences:
        if s["end"] - s["start"] < 1.5:
            continue
        cut = s["end"] - TAIL_S
        body = db[(db_t >= s["start"]) & (db_t < cut)]
        tail = db[(db_t >= cut) & (db_t < s["end"])]
        if len(body) and len(tail):
            drop = float(np.median(body) - np.median(tail))
            out.append({"start": round(cut, 2), "end": round(s["end"], 2), "drop_db": round(drop, 1)})
    return out


def _energy_timeline(db_t, db, speech, pitch_t, f0) -> list[dict]:
    """Loudness plus pitch movement per 5 s, for the report's energy line."""
    out, t, end = [], 0.0, db_t[-1] if len(db_t) else 0
    while t < end:
        m = (db_t >= t) & (db_t < t + ENERGY_WINDOW_S) & speech
        p = (pitch_t >= t) & (pitch_t < t + ENERGY_WINDOW_S) & (f0 > 0)
        if m.any():
            out.append({
                "t": round(t, 1),
                "db": round(float(db[m].mean()), 1),
                "pitch_sd_hz": round(float(f0[p].std()), 1) if p.sum() > 5 else None,
            })
        t += ENERGY_WINDOW_S
    return out
