"""Q3: the stateful semantic gate between graph construction (Q1) and
encrypted delivery (Q2) -- manuscript.pdf SS III, Fig. 2/3. This module
ties gate_candidates/gate_logical/gate_probabilistic/gate_mechanisms
together into the one call node.py's `publish-gated` command makes per
round.

Not a claim that this engine matches the paper's frozen supplementary-
material semantics (SS III-B: "detailed proof obligations and the
restricted rule language belong in the supplementary material") -- it is
a first working implementation of the same equations (Definition 1,
Eq. 5, Eq. 7-8) at small, declared scale, so the mechanisms in Table I
can actually be run and compared instead of only specified. See
PLANS.md for what still needs a research decision before this drives
real experiments.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gate_candidates import build_candidate_ladder
from gate_mechanisms import MECHANISMS, Decision
from gate_probabilistic import DeclaredModel, PosteriorLedger
from gate_rules import Rule
from gate_transcript import Transcript


@dataclass
class GatePolicy:
    """Sigma (rules), P (protected triples), KB (background facts), and
    the declared probabilistic model family Theta -- all of it must be
    supplied by whoever deploys the gate, never invented by this module
    (SS IV-A: "every claim is relative to P, Sigma, KB, Theta... and the
    modeled observables")."""

    rules: tuple = ()
    protected: frozenset = frozenset()
    background: frozenset = frozenset()
    declared_models: tuple = ()
    secret_pair: object = None
    epsilon_budget: float = float("inf")

    @staticmethod
    def load(path: Path) -> "GatePolicy":
        """A missing policy file means Sigma/P/KB are all empty, so every
        mechanism degrades to "nothing protected, always approve" -- a
        safe default (nothing to block), not a substitute for actually
        declaring a policy."""
        if not path.exists():
            return GatePolicy()
        data = json.loads(path.read_text())
        rules = tuple(
            Rule(body=tuple(tuple(p) for p in r["body"]), head=tuple(r["head"]))
            for r in data.get("rules", [])
        )
        protected = frozenset(tuple(t) for t in data.get("protected", []))
        background = frozenset(tuple(t) for t in data.get("background", []))
        declared_models = tuple(
            DeclaredModel(name=m["name"], likelihoods=m["likelihoods"])
            for m in data.get("declared_models", [])
        )
        secret_pair = tuple(data["secret_pair"]) if "secret_pair" in data else None
        epsilon_budget = data.get("epsilon_budget", float("inf"))
        return GatePolicy(rules, protected, background, declared_models, secret_pair, epsilon_budget)


def run_round(
    mechanism: str,
    policy: GatePolicy,
    transcript: Transcript,
    full_facts: frozenset,
    query_predicate: str,
    ledger: "PosteriorLedger | None" = None,
) -> Decision:
    if mechanism not in MECHANISMS:
        raise ValueError("unknown mechanism {0!r}; choose one of {1}".format(mechanism, sorted(MECHANISMS)))

    ladder = build_candidate_ladder(full_facts, query_predicate)
    decision = MECHANISMS[mechanism](
        ladder,
        background=policy.background,
        transcript_facts=transcript.observed_facts(),
        rules=policy.rules,
        protected=policy.protected,
        protected_triples=policy.protected,
        ledger=ledger,
        declared_models=policy.declared_models,
        secret_pair=policy.secret_pair,
        epsilon_budget=policy.epsilon_budget,
    )
    transcript.append(query_predicate, decision.chosen.response, decision.chosen.mode)
    return decision
