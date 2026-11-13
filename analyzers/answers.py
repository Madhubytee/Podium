"""Per-question breakdown for live sessions (interview, pitch Q&A, debate).

Answer length = time from Oli finishing a question to the user's last word.
"""

from .language import star_parts
from .text_utils import words_between


def analyze_answers(words: list[dict], oli_turns: list[dict], duration_s: float) -> dict:
    """`oli_turns` = [{start, end, text}] seconds into the recording when Oli spoke."""
    if not oli_turns:
        return {"available": False, "items": []}

    turns = sorted(oli_turns, key=lambda q: q["start"])
    items = []
    for i, q in enumerate(turns):
        asked_until = q.get("end") or q["start"]
        span_end = turns[i + 1]["start"] if i + 1 < len(turns) else duration_s
        ans = words_between(words, asked_until, span_end)
        if not ans:
            items.append({"question": q["text"], "start": asked_until, "end": span_end,
                          "duration_s": 0.0, "word_count": 0, "star": [], "skipped": True})
            continue
        text = " ".join(w["text"] for w in ans)
        items.append({
            "question": q["text"],
            "start": round(asked_until, 2),
            "end": round(ans[-1]["end"], 2),
            "duration_s": round(ans[-1]["end"] - asked_until, 1),
            "word_count": len(ans),
            "star": star_parts(text),
            "skipped": False,
        })

    answered = [a for a in items if not a["skipped"]]
    return {
        "available": True,
        "count": len(answered),
        "items": items,
        "star_ratio": round(sum(1 for a in answered if len(a["star"]) >= 3) / len(answered), 2) if answered else 0.0,
    }
