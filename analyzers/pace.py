"""Speaking pace in words per minute, overall and over time."""

WINDOW_S = 15.0
FAST_WPM = 170
SLOW_WPM = 100


def analyze_pace(words: list[dict], exclude: list[tuple[float, float]] = ()) -> dict:
    """`exclude` lists time spans to ignore (e.g. while Oli is asking a question)."""
    if len(words) < 2:
        return {"wpm": 0.0, "timeline": [], "fast_segments": [], "slow_segments": []}

    speaking_s = (words[-1]["end"] - words[0]["start"]) - sum(e - s for s, e in exclude)
    speaking_s = max(speaking_s, 1.0)
    wpm = len(words) / (speaking_s / 60)

    timeline, fast, slow = [], [], []
    t, end = words[0]["start"], words[-1]["end"]
    while t < end:
        w_end = min(t + WINDOW_S, end)
        span = w_end - t
        n = sum(1 for w in words if t <= w["start"] < w_end)
        if span >= 5 and n > 0:
            rate = n / (span / 60)
            timeline.append({"t": round(t, 2), "wpm": round(rate, 1)})
            seg = {"start": round(t, 2), "end": round(w_end, 2), "wpm": round(rate, 1)}
            if rate > FAST_WPM:
                fast.append(seg)
            elif rate < SLOW_WPM:
                slow.append(seg)
        t += WINDOW_S

    return {
        "wpm": round(wpm, 1),
        "speaking_s": round(speaking_s, 2),
        "timeline": timeline,
        "fast_segments": fast,
        "slow_segments": slow,
    }
