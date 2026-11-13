"""Filler word detection: um, uh, like, you know, so, basically, actually, kind of."""

from collections import Counter

from .text_utils import ends_sentence, find_phrases, norm

SOUND_FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "ahh", "hmm", "mm", "mhm"}
PHRASE_FILLERS = ["you know", "i mean", "kind of", "sort of", "basically", "actually", "literally"]
# "like" and "so" are only fillers when used as verbal padding, not "I like it" / "so that".
CONTEXT_FILLERS = {"like", "so"}


def _is_padding(words: list[dict], i: int) -> bool:
    token = words[i]["text"].strip()
    prev = words[i - 1]["text"] if i > 0 else "."
    return token.endswith(",") or ends_sentence(prev) or prev.strip().endswith(",")


def analyze_fillers(words: list[dict], speaking_minutes: float) -> dict:
    instances = []
    for i, w in enumerate(words):
        t = norm(w["text"])
        if t in SOUND_FILLERS or (t in CONTEXT_FILLERS and _is_padding(words, i)):
            instances.append({"word": t, "start": w["start"], "end": w["end"], "index": i})

    for hit in find_phrases(words, PHRASE_FILLERS):
        instances.append({"word": hit["phrase"], "start": hit["start"], "end": hit["end"], "index": hit["index"]})

    instances.sort(key=lambda x: x["start"])
    return {
        "count": len(instances),
        "per_minute": round(len(instances) / speaking_minutes, 2) if speaking_minutes > 0 else 0.0,
        "by_word": dict(Counter(x["word"] for x in instances).most_common()),
        "instances": instances,
    }
