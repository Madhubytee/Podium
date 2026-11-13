"""Engine tests with hand written facts, no media needed."""

import pytest

from inference import InferenceEngine
from knowledge_base import Fact, FactBase, KnowledgeBase, RuleError


def f(name, value, start=None, end=None, tags=None, source="transcript"):
    return Fact(name=name, value=value, start=start, end=end, tags=tags or [], source=source)


def base_facts(occasion, wpm=150, fillers_per_min=1.0, duration=90.0):
    return [
        f("occasion", occasion, source="setup"),
        f("duration_s", duration, 0, duration),
        f("word_count", int(wpm * duration / 60), 0, duration),
        f("pace_wpm", wpm, 0, duration),
        f("filler_per_min", fillers_per_min, 0, duration),
    ]


@pytest.fixture(scope="module")
def engine():
    return InferenceEngine(KnowledgeBase.load())


def keys(diags):
    return [d.key for d in diags]


def test_real_rules_file_loads():
    kb = KnowledgeBase.load()
    assert {r.id for r in kb.rules} >= set(range(1, 16)) | {17}
    assert kb.conflict_resolution["rule"] == 16


def test_good_take_gets_strengths_not_fixes(engine):
    result = engine.run(FactBase(base_facts("presentation")))
    assert result.focus == []
    assert {"good_pace", "few_fillers"} <= set(keys(result.strengths))


def test_too_fast_fires_with_clip_moments(engine):
    facts = base_facts("interview", wpm=185) + [f("pace_window", 190, 30, 45), f("pace_window", 140, 45, 60)]
    result = engine.run(FactBase(facts))
    top = result.focus[0]
    assert top.key == "too_fast"
    assert top.moments == [{"start": 28.5, "end": 46.5, "fact_ids": [6]}]
    assert "pace_wpm = 185 (> 170)" in top.explanation


def test_forward_chaining_and_suppression(engine):
    """Rushing + weak opening -> 'nerves at the start', which replaces both."""
    facts = base_facts("pitch", wpm=175, fillers_per_min=4.5) + [f("has_hook", False, 0, 15),
                                                                 f("has_cta_end", True, 72, 90)]
    result = engine.run(FactBase(facts))
    assert result.focus[0].key == "nerves_at_start"
    suppressed = set(keys(result.suppressed))
    assert {"nervous_rushing", "weak_opening", "too_fast"} <= suppressed
    assert "nervous_rushing" not in keys(result.focus + result.secondary)
    order = [line for line in result.trace if "fired" in line]
    assert [i for i, line in enumerate(order) if "(nerves_at_start) fired" in line][0] > max(
        i for i, line in enumerate(order) if "(nervous_rushing) fired" in line or "(weak_opening) fired" in line)


def test_occasion_filter(engine):
    """A pitch never gets the STAR interview rule, and an interview never gets the call-to-action rule."""
    long_answer = [f("answer", 150.0, 10, 160)]
    pitch = engine.run(FactBase(base_facts("pitch") + long_answer + [f("has_cta_end", False, 72, 90)]))
    assert "long_answer" not in keys(pitch.focus + pitch.secondary)
    assert "no_call_to_action" in keys(pitch.focus)

    interview = engine.run(FactBase(base_facts("interview") + long_answer + [f("has_cta_end", False, 72, 90)]))
    assert "long_answer" in keys(interview.focus)
    assert "no_call_to_action" not in keys(interview.focus + interview.secondary)


def test_tagged_count_condition(engine):
    one = [f("pause", 2.5, 10, 12.5, tags=["mid_sentence"])]
    two = one + [f("pause", 3.0, 40, 43, tags=["mid_sentence"]), f("pause", 4.0, 50, 54, tags=["between_sentences"])]
    assert "lost_place" not in keys(engine.run(FactBase(base_facts("speech") + one)).focus)
    result = engine.run(FactBase(base_facts("speech") + two))
    lost = next(d for d in result.focus + result.secondary if d.key == "lost_place")
    assert lost.count == 2  # the between-sentences pause doesn't count


def test_camera_off_means_no_body_language_rules(engine):
    result = engine.run(FactBase(base_facts("interview") + [f("camera_on", False, source="video")]))
    assert not any(d.area == "Body language" for d in result.focus + result.secondary + result.strengths)


def test_conflict_resolution_ranks_by_severity_and_count(engine):
    fillers = [f("filler", "um", t, t + 0.3) for t in range(5, 85, 5)]
    facts = base_facts("interview", wpm=180, fillers_per_min=10.7) + fillers + [f("eye_contact_pct", 50.0)]
    result = engine.run(FactBase(facts))
    assert keys(result.focus) == ["filler_heavy", "low_eye_contact"]
    assert "too_fast" in keys(result.secondary)
    assert len(result.focus) == 2


def test_stale_focus_moves_on(engine):
    facts = base_facts("speech", fillers_per_min=8) + [f("eye_contact_pct", 55.0)]
    fresh = engine.run(FactBase(facts))
    assert fresh.focus[0].key == "filler_heavy"
    stale = engine.run(FactBase(facts), recent_focus=[[3], [3], [3]])
    assert stale.focus[0].key == "low_eye_contact"
    assert next(d for d in stale.focus + stale.secondary if d.key == "filler_heavy").stale


def test_improvement_rule(engine):
    facts = base_facts("speech") + [f("metric_change", 22.0, tags=["filler_per_min"], source="progress")]
    assert "improved" in keys(engine.run(FactBase(facts)).strengths)


def test_ratio_condition(engine):
    drops = [f("sentence_end_drop", d, i * 5, i * 5 + 0.5, source="audio") for i, d in enumerate([9, 8, 7, 2, 1])]
    assert "trailing_off" in keys(engine.run(FactBase(base_facts("speech") + drops)).focus)
    few = drops[:1] + [f("sentence_end_drop", 1, 40, 40.5)] * 4
    assert "trailing_off" not in keys(engine.run(FactBase(base_facts("speech") + few)).focus)


def test_bad_rule_is_rejected():
    bad = {"rules": [{"id": 1, "key": "x", "name": "x", "area": "x", "kind": "fix", "severity": 0.5,
                      "if": {"fact": "pace_wpm", "op": "bigger", "value": 1}, "then": {}}]}
    with pytest.raises(RuleError):
        KnowledgeBase.from_dict(bad)
