"""Turn analyzer measurements into timed facts for the inference engine.

A fact is one measured thing, with when it happened:
    {"name": "pause", "value": 3.6, "start": 12.4, "end": 16.0, "source": "audio", "tags": ["mid_sentence"]}

Fact names are the vocabulary rules.json is written in; see knowledge_base/FACTS.md.
"""


def fact(name, value, start=None, end=None, source="transcript", tags=None) -> dict:
    return {"name": name, "value": value, "start": start, "end": end, "source": source, "tags": tags or []}


def setup_facts(context: dict) -> list[dict]:
    out = [fact("occasion", context.get("occasion"), source="setup"),
           fact("mode", context.get("mode"), source="setup")]
    if context.get("audience"):
        out.append(fact("audience", context["audience"], source="setup"))
    if context.get("time_limit_s"):
        out.append(fact("time_limit_s", context["time_limit_s"], source="setup"))
    return out


def transcript_facts(m: dict, context: dict) -> list[dict]:
    dur = m["duration_s"]
    out = [fact("duration_s", dur, 0, dur), fact("word_count", m["word_count"], 0, dur)]
    if context.get("time_limit_s"):
        out.append(fact("time_used_ratio", round(dur / context["time_limit_s"], 2), 0, dur))

    pace = m["pace"]
    if m["word_count"] >= 2:
        out.append(fact("pace_wpm", pace["wpm"], m["speech_start"], m["speech_end"]))
    out += [fact("pace_window", p["wpm"], p["t"], p["t"] + 15) for p in pace["timeline"]]

    fil = m["fillers"]
    out += [fact("filler", f["word"], f["start"], f["end"], tags=[f["word"]]) for f in fil["instances"]]
    out += [fact("filler_count", fil["count"], 0, dur), fact("filler_per_min", fil["per_minute"], 0, dur)]

    pz = m["pauses"]
    out += [fact("pause", p["duration"], p["start"], p["end"], source="audio", tags=p["tags"]) for p in pz["instances"]]
    out += [fact("pause_per_min", pz["per_minute"], 0, dur, source="audio"),
            fact("emphasis_pause_per_min", pz["between_per_minute"], 0, dur, source="audio")]

    cl = m["clarity"]
    if cl["avg_conf"] is not None:
        out.append(fact("clarity", cl["avg_conf"], 0, dur))
    out += [fact("unclear_word", u["word"], u["start"], u["end"]) for u in cl["unclear"]]

    for name, key in (("hedge", "hedges"), ("apology", "apologies")):
        out += [fact(name, h["word"], h["start"], h["end"]) for h in m[key]]
        out.append(fact(f"{name}_count", len(m[key]), 0, dur))

    c = m["content"]
    out.append(fact("has_hook", c["has_hook"], m["speech_start"], c["opening_end"]))
    out.append(fact("has_cta_end", c["has_cta_end"], round(0.8 * dur, 2), dur))
    out += [fact("cta", x["word"], x["start"], x["end"]) for x in c["cta_instances"]]

    ans = m["answers"]
    if ans["available"]:
        for a in ans["items"]:
            if not a["skipped"]:
                out.append(fact("answer", a["duration_s"], a["start"], a["end"], tags=a["star"]))
        out.append(fact("star_ratio", ans["star_ratio"], 0, dur))
    return out


def voice_facts(v: dict) -> list[dict]:
    if not v.get("available"):
        return []
    out = []
    if "pitch" in v:
        out += [fact("pitch_sd_hz", v["pitch"]["sd_hz"], source="audio"),
                fact("pitch_range_hz", v["pitch"]["range_hz"], source="audio"),
                fact("pitch_mean_hz", v["pitch"]["mean_hz"], source="audio")]
    if v["volume"]["mean_db"] is not None:
        out.append(fact("volume_db", v["volume"]["mean_db"], source="audio"))
    out += [fact("sentence_end_drop", t["drop_db"], t["start"], t["end"], source="audio") for t in v["trailing"]]
    out += [fact("energy", e["db"], e["t"], e["t"] + 5, source="audio") for e in v["energy_timeline"]]
    return out


def vision_facts(v: dict) -> list[dict]:
    if not v.get("available"):
        return [fact("camera_on", False, source="video")]
    out = [fact("camera_on", True, source="video")]
    for key in ("eye_contact_pct", "looking_down_pct", "smiles_per_min", "face_animated_pct",
                "gesture_pct", "hands_still_pct", "sway_per_10s"):
        out.append(fact(key, v[key], source="video"))
    out += [fact("looking_away", round(s["end"] - s["start"], 1), s["start"], s["end"], source="video")
            for s in v["looking_away_spans"]]
    out += [fact("sway", 1, s["start"], s["end"], source="video") for s in v["sway_events"]]
    return out
