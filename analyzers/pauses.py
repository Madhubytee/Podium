"""Pauses between words.

A pause inside a sentence usually means the speaker lost their place; a pause
between sentences is a breath or deliberate emphasis.
"""

from .text_utils import ends_sentence

PAUSE_S = 0.6       # guide: anything over 0.6 s is a pause
LONG_PAUSE_S = 2.0


def analyze_pauses(words: list[dict], exclude: list[tuple[float, float]] = ()) -> dict:
    """Gaps that overlap an `exclude` span (Oli talking) aren't the speaker's pauses."""
    pauses = []
    for prev, nxt in zip(words, words[1:]):
        start, end = prev["end"], nxt["start"]
        gap = end - start
        if gap < PAUSE_S:
            continue
        if any(s < end and e > start for s, e in exclude):
            continue
        between = ends_sentence(prev["text"]) or prev["text"].strip().endswith((",", ";", ":"))
        pauses.append({
            "start": round(start, 2), "end": round(end, 2), "duration": round(gap, 2),
            "tags": ["between_sentences" if between else "mid_sentence"]
                    + (["long"] if gap >= LONG_PAUSE_S else []),
        })

    speaking_min = max((words[-1]["end"] - words[0]["start"]) / 60, 1 / 60) if words else 0
    durations = [p["duration"] for p in pauses]
    between = [p for p in pauses if "between_sentences" in p["tags"]]
    return {
        "count": len(pauses),
        "per_minute": round(len(pauses) / speaking_min, 2) if speaking_min else 0.0,
        "between_per_minute": round(len(between) / speaking_min, 2) if speaking_min else 0.0,
        "avg_s": round(sum(durations) / len(durations), 2) if durations else 0.0,
        "longest_s": max(durations, default=0.0),
        "instances": pauses,
    }
