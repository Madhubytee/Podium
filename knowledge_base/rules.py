"""Rule and KnowledgeBase: the experts' IF/THEN rules, loaded from rules.json."""

import json
from dataclasses import dataclass, field
from pathlib import Path

RULES_PATH = Path(__file__).with_name("rules.json")

OPS = {">", ">=", "<", "<=", "==", "!=", "between", "in"}
WINDOWS = {"first_15s", "first_20pct", "last_20pct"}
KINDS = {"fix", "strength"}


class RuleError(ValueError):
    pass


@dataclass
class Rule:
    id: int
    key: str
    name: str
    area: str
    kind: str
    severity: float
    occasions: list[str]
    condition: dict
    then: dict
    moments: dict | None = None
    suppresses: list[int] = field(default_factory=list)
    occasion_weight: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        try:
            rule = cls(
                id=d["id"], key=d["key"], name=d["name"], area=d["area"], kind=d["kind"],
                severity=float(d["severity"]), occasions=d.get("occasions", ["all"]),
                condition=d["if"], then=d["then"], moments=d.get("moments"),
                suppresses=d.get("suppresses", []), occasion_weight=d.get("occasion_weight", {}),
            )
        except KeyError as exc:
            raise RuleError(f"rule {d.get('id', '?')} is missing {exc}") from exc
        rule.validate()
        return rule

    def applies_to(self, occasion: str | None) -> bool:
        return "all" in self.occasions or occasion in self.occasions

    def weight_for(self, occasion: str | None) -> float:
        return float(self.occasion_weight.get(occasion, 1.0))

    def validate(self) -> None:
        if self.kind not in KINDS:
            raise RuleError(f"rule {self.id}: kind must be one of {sorted(KINDS)}")
        if not 0 <= self.severity <= 1:
            raise RuleError(f"rule {self.id}: severity must be between 0 and 1")
        _check_condition(self.condition, self.id)
        if self.moments:
            _check_condition(self.moments, self.id)


def _check_condition(cond: dict, rule_id: int) -> None:
    if "all" in cond or "any" in cond:
        for sub in cond.get("all", []) + cond.get("any", []):
            _check_condition(sub, rule_id)
        return
    if "not" in cond:
        _check_condition(cond["not"], rule_id)
        return
    if "fact" not in cond:
        raise RuleError(f"rule {rule_id}: condition needs 'fact', 'all', 'any', or 'not': {cond}")
    if "op" in cond:
        if cond["op"] not in OPS:
            raise RuleError(f"rule {rule_id}: unknown op {cond['op']!r}")
        if "value" not in cond:
            raise RuleError(f"rule {rule_id}: op {cond['op']!r} needs a value")
        if cond["op"] == "between" and not (isinstance(cond["value"], list) and len(cond["value"]) == 2):
            raise RuleError(f"rule {rule_id}: 'between' needs [low, high]")
    if cond.get("within") and cond["within"] not in WINDOWS:
        raise RuleError(f"rule {rule_id}: unknown window {cond['within']!r}")


class KnowledgeBase:
    def __init__(self, rules: list[Rule], conflict_resolution: dict, scoring: dict):
        self.rules = rules
        self.conflict_resolution = conflict_resolution
        self.scoring = scoring
        ids = [r.id for r in rules]
        if len(ids) != len(set(ids)):
            raise RuleError("rule ids must be unique")
        keys = [r.key for r in rules]
        if len(keys) != len(set(keys)):
            raise RuleError("rule keys must be unique")

    @classmethod
    def load(cls, path: str | Path = RULES_PATH) -> "KnowledgeBase":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeBase":
        return cls(
            rules=[Rule.from_dict(r) for r in data["rules"]],
            conflict_resolution=data.get("conflict_resolution", {}),
            scoring=data.get("scoring", {}),
        )

    def for_occasion(self, occasion: str | None) -> list[Rule]:
        return [r for r in self.rules if r.applies_to(occasion)]

    def rule(self, rule_id: int) -> Rule:
        return next(r for r in self.rules if r.id == rule_id)
