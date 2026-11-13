"""Progress across takes: the second kind of fact, "change since last time"."""

# metric -> how "better" is defined
KEY_METRICS = {
    "pace_wpm": ("target", 150),
    "filler_per_min": ("lower", None),
    "eye_contact_pct": ("higher", None),
    "pitch_sd_hz": ("higher", None),
    "clarity": ("higher", None),
    "hedge_count": ("lower", None),
    "lost_place_pauses": ("lower", None),
}


def summarize(facts: list[dict]) -> dict:
    """The headline numbers of one take, from its facts."""
    first = {}
    for f in facts:
        first.setdefault(f["name"], f["value"])
    out = {k: first[k] for k in KEY_METRICS if k in first and isinstance(first[k], (int, float))}
    out["lost_place_pauses"] = sum(
        1 for f in facts if f["name"] == "pause" and "mid_sentence" in f["tags"] and f["value"] >= 2.0)
    for k in ("duration_s", "word_count", "filler_count", "pause_per_min", "looking_down_pct", "gesture_pct"):
        if k in first:
            out[k] = first[k]
    return out


def improvement_pct(metric: str, before: float, after: float) -> float | None:
    """Positive = better. None when the change can't be measured meaningfully."""
    direction, target = KEY_METRICS[metric]
    if direction == "target":
        gap_before, gap_after = abs(before - target), abs(after - target)
        if gap_before < 5:
            return None
        return 100 * (gap_before - gap_after) / gap_before
    if before == 0:
        return None if after == 0 or direction == "higher" else -100.0
    change = 100 * (after - before) / abs(before)
    return change if direction == "higher" else -change


def change_facts(current: dict, previous: dict) -> list[dict]:
    out = []
    for metric in KEY_METRICS:
        if metric in current and metric in previous:
            pct = improvement_pct(metric, previous[metric], current[metric])
            if pct is not None:
                out.append({"name": "metric_change", "value": round(pct, 1), "start": None, "end": None,
                            "source": "progress", "tags": [metric]})
    return out
