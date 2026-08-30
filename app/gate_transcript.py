"""Persistent per-coalition transcript H_t (manuscript.pdf Eq. 3) -- the
security object the logical and probabilistic gates check against, not
just the current round's response. Keyed by a declared coalition id:
pooling identities into one transcript models SS III-B's point that "a
per-login history is not a meaningful defense against transcript
pooling" when collusion is in scope.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gate_rules import Triple


@dataclass
class Round:
    query: str
    response: tuple
    mode: str  # "exact" | "minimal" | "generalized" | "aggregate" | "refusal"

    def to_dict(self) -> dict:
        return {"query": self.query, "response": [list(t) for t in self.response], "mode": self.mode}

    @staticmethod
    def from_dict(data: dict) -> "Round":
        return Round(
            query=data["query"],
            response=tuple(tuple(t) for t in data["response"]),
            mode=data["mode"],
        )


@dataclass
class Transcript:
    coalition: str
    rounds: list = field(default_factory=list)

    def observed_facts(self) -> "frozenset[Triple]":
        facts = set()
        for round_ in self.rounds:
            facts.update(round_.response)
        return frozenset(facts)

    def append(self, query: str, response: tuple, mode: str) -> None:
        self.rounds.append(Round(query, response, mode))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"coalition": self.coalition, "rounds": [r.to_dict() for r in self.rounds]}
        path.write_text(json.dumps(payload, indent=2))

    @staticmethod
    def load_or_new(path: Path, coalition: str) -> "Transcript":
        if not path.exists():
            return Transcript(coalition=coalition)
        data = json.loads(path.read_text())
        return Transcript(
            coalition=data["coalition"],
            rounds=[Round.from_dict(r) for r in data["rounds"]],
        )
