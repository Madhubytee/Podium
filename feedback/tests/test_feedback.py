import pytest

from feedback import change_facts, score, summarize
from feedback.progress import improvement_pct

SCORING = {"start": 100, "points_per_severity": 15, "area_cap": 25}


def diag(area, severity, count=1, kind="fix"):
    return {"area": area, "severity": severity, "count": count, "kind": kind}


def test_score_starts_at_100_and_ignores_strengths():
    assert score([], SCORING) == 100
    assert score([diag("Pace", 0.5, kind="strength")], SCORING) == 100


def test_score_caps_each_area():
    many_fillers = [diag("Fillers", 1.0, count=40), diag("Fillers", 0.7, count=40)]
    assert score(many_fillers, SCORING) == 75  # capped at 25 points for the area
    assert score(many_fillers + [diag("Pace", 0.6)], SCORING) == 66


def test_improvement_directions():
    assert improvement_pct("filler_per_min", 10, 5) == pytest.approx(50)
    assert improvement_pct("eye_contact_pct", 50, 60) == pytest.approx(20)
    assert improvement_pct("pace_wpm", 190, 170) == pytest.approx(50)   # 40 off target -> 20 off
    assert improvement_pct("pace_wpm", 152, 149) is None               # already on target


def test_change_facts_from_summaries():
    facts = [{"name": "filler_per_min", "value": 4.0, "tags": []},
             {"name": "pause", "value": 2.5, "tags": ["mid_sentence"]},
             {"name": "pause", "value": 0.8, "tags": ["between_sentences"]}]
    now = summarize(facts)
    assert now == {"filler_per_min": 4.0, "lost_place_pauses": 1}
    out = change_facts(now, {"filler_per_min": 8.0, "lost_place_pauses": 3})
    assert {f["tags"][0]: f["value"] for f in out} == {"filler_per_min": 50.0, "lost_place_pauses": 66.7}
