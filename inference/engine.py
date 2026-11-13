"""Forward chaining inference engine over the knowledge base.

1. Keep only rules for this occasion.
2. Loop: every rule whose conditions match fires, and its key is asserted back
   into the fact base as a new fact. Repeat until a pass fires nothing new, so
   rules can build on each other.
3. Rules that fired can suppress lower-level rules (e.g. "nervous rushing"
   replaces "too fast" + "too many fillers").
4. Conflict resolution (rule 16): rank fixes by severity x occasion weight,
   boosted by how many times the issue happened, and demoted if it has been a
   focus area for the last few takes without improving. Top 2 = focus areas.
5. Every diagnosis keeps the ids of the facts that caused it, for the
   "Why this feedback?" button and the video clips.
"""

from dataclasses import dataclass, field

from knowledge_base import Fact, FactBase, KnowledgeBase, Rule

CLIP_PAD_S = 1.5
MAX_CLIPS = 3
MAX_MOMENT_S = 30.0
MAX_CLIP_S = 10.0  # neighbouring moments merge into one clip up to this length


@dataclass
class Diagnosis:
    rule_id: int
    key: str
    name: str
    area: str
    kind: str
    severity: float
    score: float
    count: int
    why: str
    tip: str
    drill: str
    fact_ids: list[int]
    explanation: list[str]
    moments: list[dict] = field(default_factory=list)
    stale: bool = False

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class InferenceResult:
    focus: list[Diagnosis]
    secondary: list[Diagnosis]
    strengths: list[Diagnosis]
    suppressed: list[Diagnosis]
    trace: list[str]

    def to_dict(self) -> dict:
        return {
            "focus": [d.to_dict() for d in self.focus],
            "secondary": [d.to_dict() for d in self.secondary],
            "strengths": [d.to_dict() for d in self.strengths],
            "suppressed": [d.to_dict() for d in self.suppressed],
            "trace": self.trace,
        }


class InferenceEngine:
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def run(self, facts: FactBase, occasion: str | None = None,
            recent_focus: list[list[int]] | None = None) -> InferenceResult:
        """`recent_focus` = focus rule ids of previous takes, oldest first."""
        occasion = occasion or facts.value("occasion")
        active = self.kb.for_occasion(occasion)
        trace = [f"occasion={occasion}: {len(active)} of {len(self.kb.rules)} rules apply"]

        fired: dict[int, Diagnosis] = {}
        changed, passes = True, 0
        while changed:
            changed = False
            passes += 1
            for rule in active:
                if rule.id in fired:
                    continue
                match = _eval(rule.condition, facts)
                if not match.ok:
                    continue
                fired[rule.id] = self._diagnose(rule, match, facts, occasion)
                facts.add(Fact(name=rule.key, value=True, source="engine"))
                trace.append(f"pass {passes}: rule {rule.id} ({rule.key}) fired: " + "; ".join(match.why))
                changed = True

        suppressed_ids = {s for d in fired.values() for s in self.kb.rule(d.rule_id).suppresses if s in fired}
        for s in sorted(suppressed_ids):
            trace.append(f"rule {s} ({fired[s].key}) suppressed by a higher level diagnosis")

        cr = self.kb.conflict_resolution
        stale_after = int(cr.get("stale_after_takes", 3))
        history = (recent_focus or [])[-stale_after:]
        for d in fired.values():
            if d.kind == "fix" and len(history) >= stale_after and all(d.rule_id in ids for ids in history):
                d.stale = True
                d.score *= float(cr.get("stale_penalty", 0.5))
                trace.append(f"rule {d.rule_id} was a focus area {stale_after} takes in a row; moving on")

        live = [d for d in fired.values() if d.rule_id not in suppressed_ids]
        fixes = sorted((d for d in live if d.kind == "fix"), key=lambda d: d.score, reverse=True)
        strengths = sorted((d for d in live if d.kind == "strength"), key=lambda d: d.score, reverse=True)
        n = int(cr.get("focus_count", 2))
        return InferenceResult(
            focus=fixes[:n], secondary=fixes[n:], strengths=strengths,
            suppressed=[fired[i] for i in sorted(suppressed_ids)], trace=trace,
        )

    def _diagnose(self, rule: Rule, match: "_Match", facts: FactBase, occasion) -> Diagnosis:
        evidence = match.facts
        if rule.moments:
            moment_match = _eval(rule.moments, facts)
            if moment_match.facts:
                evidence = moment_match.facts
        count = max(1, len([f for f in evidence if _is_moment(f)]))

        cr = self.kb.conflict_resolution
        boost = min(float(cr.get("count_boost", 0.1)) * (count - 1), float(cr.get("max_count_boost", 1.0)))
        score = rule.severity * rule.weight_for(occasion) * (1 + boost)

        ids = sorted({f.id for f in match.facts} | {f.id for f in evidence})
        return Diagnosis(
            rule_id=rule.id, key=rule.key, name=rule.name, area=rule.area, kind=rule.kind,
            severity=rule.severity, score=round(score, 3), count=count,
            why=rule.then.get("why", ""), tip=rule.then.get("tip", ""), drill=rule.then.get("drill", ""),
            fact_ids=ids, explanation=match.why, moments=_moments(evidence),
        )


# --- condition evaluation -------------------------------------------------

@dataclass
class _Match:
    ok: bool
    facts: list[Fact] = field(default_factory=list)
    why: list[str] = field(default_factory=list)


def _compare(op: str, actual, expected) -> bool:
    try:
        if op == ">":
            return actual > expected
        if op == ">=":
            return actual >= expected
        if op == "<":
            return actual < expected
        if op == "<=":
            return actual <= expected
        if op == "==":
            return actual == expected
        if op == "!=":
            return actual != expected
        if op == "between":
            return expected[0] <= actual <= expected[1]
        if op == "in":
            return actual in expected
    except TypeError:
        return False
    raise ValueError(f"unknown op {op}")


def _in_window(f: Fact, window: str, facts: FactBase) -> bool:
    if not f.timed:
        return False
    start, end = facts.speech_span
    length = max(end - start, 1e-6)
    if window == "first_15s":
        return f.start < start + 15
    if window == "first_20pct":
        return f.start < start + 0.2 * length
    if window == "last_20pct":
        return f.start >= start + 0.8 * length
    return False


def _eval(cond: dict, facts: FactBase) -> _Match:
    if "all" in cond:
        parts = [_eval(c, facts) for c in cond["all"]]
        ok = all(p.ok for p in parts)
        return _Match(ok, [f for p in parts for f in p.facts] if ok else [], [w for p in parts for w in p.why])
    if "any" in cond:
        parts = [p for p in (_eval(c, facts) for c in cond["any"]) if p.ok]
        return _Match(bool(parts), [f for p in parts for f in p.facts], [w for p in parts for w in p.why])
    if "not" in cond:
        inner = _eval(cond["not"], facts)
        return _Match(not inner.ok, [], [f"not ({'; '.join(inner.why) or _describe(cond['not'])})"])

    name = cond["fact"]
    candidates = facts.get(name)
    if "tag" in cond:
        candidates = [f for f in candidates if cond["tag"] in f.tags]
    if "within" in cond:
        candidates = [f for f in candidates if _in_window(f, cond["within"], facts)]
    if "same_time_as" in cond:
        others = facts.get(cond["same_time_as"])
        candidates = [f for f in candidates if any(f.overlaps(o) for o in others)]
    if not candidates:
        return _Match(False, [], [f"no {name} facts"])

    if "op" in cond:
        matching = [f for f in candidates if _compare(cond["op"], f.value, cond["value"])]
    else:
        matching = list(candidates)

    min_count = int(cond.get("min_count", 1))
    ok = len(matching) >= min_count
    if ok and "min_ratio" in cond:
        ok = len(matching) / len(candidates) >= float(cond["min_ratio"])

    if len(candidates) == 1 and "op" in cond:
        why = f"{name} = {_fmt(candidates[0].value)} ({cond['op']} {_fmt(cond['value'])})"
    else:
        why = f"{len(matching)} of {len(candidates)} {name} facts match {_describe(cond)}"
    return _Match(ok, matching if ok else [], [why])


def _describe(cond: dict) -> str:
    if "op" in cond:
        return f"{cond['fact']} {cond['op']} {_fmt(cond['value'])}"
    return cond.get("fact", "?")


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, bool):
        return str(v).lower()
    return str(v)


def _is_moment(f: Fact) -> bool:
    """A specific moment (a filler, a pause), not a whole-take summary like filler_per_min."""
    return f.timed and (f.end - f.start) <= MAX_MOMENT_S


def _moments(evidence: list[Fact]) -> list[dict]:
    """Clip windows around the evidence, padded and merged, worst (longest) first."""
    spans = sorted(((max(0.0, f.start - CLIP_PAD_S), f.end + CLIP_PAD_S, f) for f in evidence if _is_moment(f)),
                   key=lambda s: (s[0], s[1]))
    merged: list[list] = []
    for start, end, f in spans:
        if merged and start <= merged[-1][1] and max(merged[-1][1], end) - merged[-1][0] <= MAX_CLIP_S:
            merged[-1][1] = max(merged[-1][1], end)
            merged[-1][2].append(f.id)
        else:
            merged.append([start, end, [f.id]])
    merged.sort(key=lambda m: (len(m[2]), m[1] - m[0]), reverse=True)
    return [{"start": round(s, 2), "end": round(e, 2), "fact_ids": ids} for s, e, ids in merged[:MAX_CLIPS]]
