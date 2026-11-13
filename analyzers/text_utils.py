"""Shared helpers for word-level analysis."""

import re

_PUNCT = re.compile(r"[^\w']+")


def norm(token: str) -> str:
    """Lowercase and strip punctuation: 'Um,' -> 'um'."""
    return _PUNCT.sub("", token.lower())


def ends_sentence(token: str) -> bool:
    return token.strip().endswith((".", "?", "!"))


def find_phrases(words: list[dict], phrases: list[str]) -> list[dict]:
    """Find multi-word phrases in a timestamped word list.

    Returns [{phrase, start, end, index}] where index is the first word's position.
    """
    normed = [norm(w["text"]) for w in words]
    split = sorted((p.split() for p in phrases), key=len, reverse=True)
    hits, i = [], 0
    while i < len(normed):
        for parts in split:
            n = len(parts)
            if normed[i:i + n] == parts:
                hits.append({
                    "phrase": " ".join(parts),
                    "start": words[i]["start"],
                    "end": words[i + n - 1]["end"],
                    "index": i,
                })
                i += n - 1
                break
        i += 1
    return hits


def words_between(words: list[dict], start: float, end: float) -> list[dict]:
    return [w for w in words if w["start"] >= start and w["start"] < end]


def sentences(words: list[dict]) -> list[dict]:
    """Group words into sentences using Whisper's punctuation: [{start, end, first, last}]."""
    out, first = [], 0
    for i, w in enumerate(words):
        if ends_sentence(w["text"]) or i == len(words) - 1:
            out.append({"start": words[first]["start"], "end": w["end"], "first": first, "last": i})
            first = i + 1
    return out
