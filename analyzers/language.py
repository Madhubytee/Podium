"""What was said: hedging, apologies, hooks, calls to action, STAR structure, clarity."""

import re

from .text_utils import find_phrases, words_between

HEDGES = [
    "i think", "i guess", "i feel like", "i believe", "maybe", "probably", "perhaps",
    "possibly", "might be", "i'm not sure", "not sure", "somewhat", "in my opinion", "i think maybe",
]
APOLOGIES = ["sorry", "i'm sorry", "i apologize", "excuse me", "my bad", "pardon me"]
CALL_TO_ACTION = [
    "we're asking", "we are asking", "asking for", "we're raising", "we are raising", "looking for",
    "invest", "join us", "sign up", "reach out", "partner with", "next step", "next steps",
    "i'd love", "we'd love", "would love", "let's", "get in touch", "back us",
    "seeking", "ask you", "support us", "try it",
]
HOOK_CUES = ["imagine", "what if", "did you know", "picture this", "raise your hand", "how many of you"]
STAR_CUES = {
    "situation": ["situation", "at the time", "when i was", "back when", "context"],
    "task": ["my task", "my role", "i was responsible", "the goal", "i needed to", "we needed to"],
    "action": ["i decided", "i built", "i led", "i created", "so i", "i implemented", "i reached out", "my approach"],
    "result": ["as a result", "the result", "in the end", "we ended up", "which led to", "outcome",
               "percent", "%", "increased", "reduced"],
}


def phrase_instances(words: list[dict], phrases: list[str]) -> list[dict]:
    return [{"word": h["phrase"], "start": h["start"], "end": h["end"], "index": h["index"]}
            for h in find_phrases(words, phrases)]


def analyze_content(words: list[dict]) -> dict:
    if not words:
        return {"has_hook": False, "has_cta_end": False, "cta_instances": [], "opening_end": 0.0}

    start, end = words[0]["start"], words[-1]["end"]
    opening_end = start + max(15.0, 0.15 * (end - start))
    opening_text = " ".join(w["text"] for w in words_between(words, start, opening_end)).lower()
    has_hook = (
        "?" in opening_text
        or bool(re.search(r"\d", opening_text))
        or any(cue in opening_text for cue in HOOK_CUES)
    )

    closing_from = start + 0.8 * (end - start)
    ctas = [c for c in phrase_instances(words, CALL_TO_ACTION) if c["start"] >= closing_from]
    return {"has_hook": has_hook, "has_cta_end": bool(ctas), "cta_instances": ctas,
            "opening_end": round(opening_end, 2)}


def clarity(words: list[dict]) -> dict:
    """Average Whisper word confidence; low confidence usually means mumbling."""
    if not words:
        return {"avg_conf": None, "unclear": []}
    unclear = [{"word": w["text"], "start": w["start"], "end": w["end"]} for w in words if w["conf"] < 0.4]
    return {"avg_conf": round(sum(w["conf"] for w in words) / len(words), 3), "unclear": unclear}


def star_parts(text: str) -> list[str]:
    lowered = text.lower()
    return [part for part, cues in STAR_CUES.items() if any(c in lowered for c in cues)]
