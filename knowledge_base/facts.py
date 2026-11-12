"""Fact and FactBase: everything the analyzers measured, each with when it happened."""

from dataclasses import dataclass, field


@dataclass
class Fact:
    name: str
    value: object
    start: float | None = None
    end: float | None = None
    source: str = "transcript"
    tags: list[str] = field(default_factory=list)
    id: int | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Fact":
        return cls(name=d["name"], value=d["value"], start=d.get("start"), end=d.get("end"),
                   source=d.get("source", "transcript"), tags=list(d.get("tags") or []), id=d.get("id"))

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "value": self.value, "start": self.start,
                "end": self.end, "source": self.source, "tags": self.tags}

    @property
    def timed(self) -> bool:
        return self.start is not None and self.end is not None

    def overlaps(self, other: "Fact") -> bool:
        return self.timed and other.timed and self.start < other.end and other.start < self.end


class FactBase:
    """All facts for one take. Facts get sequential ids so diagnoses can cite them."""

    def __init__(self, facts=()):
        self._facts: list[Fact] = []
        self._by_name: dict[str, list[Fact]] = {}
        for f in facts:
            self.add(f)

    def add(self, f) -> Fact:
        if isinstance(f, dict):
            f = Fact.from_dict(f)
        f.id = len(self._facts) + 1
        self._facts.append(f)
        self._by_name.setdefault(f.name, []).append(f)
        return f

    def get(self, name: str) -> list[Fact]:
        return self._by_name.get(name, [])

    def has(self, name: str) -> bool:
        return name in self._by_name

    def value(self, name: str, default=None):
        found = self.get(name)
        return found[0].value if found else default

    def by_id(self, fact_id: int) -> Fact:
        return self._facts[fact_id - 1]

    def all(self) -> list[Fact]:
        return list(self._facts)

    def __len__(self) -> int:
        return len(self._facts)

    @property
    def speech_span(self) -> tuple[float, float]:
        """(start, end) of the take, used for time windows like first_15s."""
        pace = self.get("pace_wpm")
        if pace and pace[0].timed:
            return pace[0].start, pace[0].end
        return 0.0, float(self.value("duration_s", 0.0) or 0.0)
