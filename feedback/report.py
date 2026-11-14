"""Build the results page for one take from the engine's diagnoses and the raw metrics."""

from .progress import KEY_METRICS, improvement_pct

METRIC_LABELS = {
    "pace_wpm": "Pace (words/min)",
    "filler_per_min": "Fillers per minute",
    "eye_contact_pct": "Eye contact %",
    "pitch_sd_hz": "Pitch variation (Hz)",
    "clarity": "Clarity",
    "hedge_count": "Hedges",
    "lost_place_pauses": "Lost-place pauses",
}


def score(diagnoses: list[dict], scoring: dict) -> int:
    """Start at 100 and subtract severity x count per fix, capped per area so one
    problem can't sink the whole score."""
    start = scoring.get("start", 100)
    per = scoring.get("points_per_severity", 15)
    cap = scoring.get("area_cap", 25)
    by_area: dict[str, float] = {}
    for d in diagnoses:
        if d["kind"] != "fix":
            continue
        penalty = d["severity"] * per * (1 + 0.1 * min(d["count"] - 1, 10))
        by_area[d["area"]] = min(cap, by_area.get(d["area"], 0) + penalty)
    return max(0, round(start - sum(by_area.values())))


def build_report(*, rehearsal: dict, take: dict, analysis: dict, result: dict, summary: dict,
                 previous: list[dict], scoring: dict) -> dict:
    m = analysis["metrics"]
    fixes = result["focus"] + result["secondary"]
    take_score = score(fixes, scoring)
    strengths = result["strengths"]
    # Praise for improving beats any other strength (guide: Oli opens with praise).
    strengths.sort(key=lambda d: d["key"] != "improved")

    last = previous[-1] if previous else None
    progress = None
    if last:
        progress = {
            "previous_take": last["number"],
            "previous_score": last["score"],
            "score_change": take_score - (last["score"] or 0),
            "metrics": [
                {"metric": k, "label": METRIC_LABELS[k], "before": last["summary"][k], "after": summary[k],
                 "improvement_pct": _round(improvement_pct(k, last["summary"][k], summary[k]))}
                for k in KEY_METRICS if k in summary and k in last["summary"]
            ],
            "resolved": [r for r in last["focus_rule_ids"] if r not in {d["rule_id"] for d in fixes}],
        }

    return {
        "take": {"id": take["id"], "number": take["number"], "mode": take["mode"],
                 "duration_s": m["duration_s"]},
        "rehearsal": {"id": rehearsal["id"], "title": rehearsal["title"], "occasion": rehearsal["occasion"]},
        "score": take_score,
        "headline": _headline(take_score, result, progress),
        "focus": result["focus"],
        "secondary": result["secondary"],
        "strength": strengths[0] if strengths else None,
        "other_strengths": strengths[1:],
        "suppressed": result["suppressed"],
        "summary": summary,
        "camera": "on" if m["vision"].get("available") else "off",
        "charts": _charts(m),
        "transcript": _annotated_transcript(analysis),
        "answers": m["answers"]["items"] if m["answers"]["available"] else [],
        "progress": progress,
        "trace": result["trace"],
    }


def _round(v):
    return None if v is None else round(v, 1) + 0.0  # + 0.0 turns -0.0 into 0.0


def _headline(take_score: int, result: dict, progress: dict | None) -> str:
    if progress and any((x["improvement_pct"] or 0) > 15 for x in progress["metrics"]):
        best = max(progress["metrics"], key=lambda x: x["improvement_pct"] or 0)
        return f"Hoo hoo! Your {best['label'].lower()} got {best['improvement_pct']:.0f}% better since take {progress['previous_take']}."
    if not result["focus"]:
        return "Hoo! That was a strong take. Nothing big to fix, so let's polish."
    first = result["focus"][0]["name"].lower()
    if take_score >= 80:
        return f"Nice work! One thing will make it even better: {first}."
    if take_score >= 60:
        return f"Good start. Let's focus on {first} first."
    return f"Every great speaker starts here. We'll tackle {first} first, one fix at a time."


def _charts(m: dict) -> dict:
    fillers = m["fillers"]
    dur = max(m["duration_s"], 1)
    buckets = {}
    for f in fillers["instances"]:
        b = int(f["start"] // 30) * 30
        buckets[b] = buckets.get(b, 0) + 1
    filler_timeline = [{"t": t, "per_min": round(buckets.get(t, 0) * 2, 1)} for t in range(0, int(dur) + 1, 30)]

    voice, vis = m["voice"], m["vision"]
    return {
        "pace": m["pace"]["timeline"],
        "fillers_over_time": filler_timeline,
        "fillers_by_word": fillers["by_word"],
        "energy": voice.get("energy_timeline", []),
        "pitch": voice.get("pitch"),
        "eye_contact": {"pct": vis.get("eye_contact_pct"), "timeline": vis.get("timeline", [])}
        if vis.get("available") else None,
    }


def _annotated_transcript(analysis: dict) -> list[dict]:
    """Words with tags (filler, hedge, unclear), plus markers for long pauses and trailing sentences."""
    words = analysis["words"]
    tags: dict[int, set] = {}
    m = analysis["metrics"]
    for f in m["fillers"]["instances"]:
        tags.setdefault(f["index"], set()).add("filler")
    for h in m["hedges"] + m["apologies"]:
        tags.setdefault(h["index"], set()).add("hedge")

    pauses = {round(p["start"], 2): p for p in m["pauses"]["instances"] if p["duration"] >= 1.0}
    trailing = [t for t in m["voice"].get("trailing", []) if t["drop_db"] > 6]

    out = []
    for i, w in enumerate(words):
        t = set(tags.get(i, set()))
        if w.get("conf", 1) < 0.4:
            t.add("unclear")
        if any(tr["start"] <= w["start"] < tr["end"] for tr in trailing):
            t.add("trailing")
        item = {"text": w["text"], "start": w["start"], "end": w["end"], "tags": sorted(t)}
        p = pauses.get(round(w["end"], 2))
        if p:
            item["pause_after"] = {"duration": p["duration"], "tags": p["tags"]}
        out.append(item)
    return out
