"""Table I's primary disclosure mechanisms, implemented as pluggable
release policies over the same candidate ladder (gate_candidates.py) and
gates (gate_logical.py, gate_probabilistic.py) -- so comparing mechanisms
measures the release RULE, not a different answer generator (SS III-A).

`q2_selector` is today's node.py behaviour (encrypt-and-publish, no
history or semantic check at all) -- the paper's own baseline, included
here so it can be compared against, not because it is safe.
"""

from __future__ import annotations

from dataclasses import dataclass

from gate_logical import is_logically_opaque
from gate_probabilistic import PosteriorLedger


@dataclass
class Decision:
    mechanism: str
    chosen: object  # a gate_candidates.Candidate
    approved: bool
    round_epsilon: float = 0.0
    reason: str = ""


def q2_selector(ladder, **_kwargs) -> Decision:
    exact = ladder[0]
    return Decision("q2_selector", exact, approved=True, reason="no gate applied")


def explicit_redaction(ladder, protected_triples=frozenset(), **_kwargs) -> Decision:
    """Removes named protected triples verbatim; does not test whether
    the REMAINING triples still jointly entail them -- exactly what
    Figure 1 shows is insufficient."""
    exact = ladder[0]
    redacted = tuple(t for t in exact.response if t not in protected_triples)
    from gate_candidates import Candidate
    return Decision("explicit_redaction", Candidate("exact-redacted", redacted), approved=True)


def task_minimal(ladder, **_kwargs) -> Decision:
    minimal = next(c for c in ladder if c.mode == "minimal")
    return Decision("task_minimal", minimal, approved=True, reason="no inference or history check")


def _opaque(candidate, background, transcript_facts, rules, protected) -> bool:
    return is_logically_opaque(background, transcript_facts | frozenset(candidate.response), rules, protected)


def stateless_censor(ladder, background=frozenset(), rules=(), protected=frozenset(), **_kwargs) -> Decision:
    """Tests the current response against background ALONE, discarding
    prior exchanges -- exactly the gap Figure 1 exploits: S2 looks safe
    in isolation, only S1 u S2 entails the protected fact."""
    for candidate in ladder:
        if is_logically_opaque(background, frozenset(candidate.response), rules, protected):
            return Decision("stateless_censor", candidate, approved=True)
    return Decision("stateless_censor", ladder[-1], approved=True, reason="fell through to refusal")


def stateful_logical(ladder, background=frozenset(), transcript_facts=frozenset(), rules=(),
                      protected=frozenset(), **_kwargs) -> Decision:
    """Checks the FULL accumulated transcript, not just this round --
    Definition 1 applied to background u transcript_facts u candidate."""
    for candidate in ladder:
        if _opaque(candidate, background, transcript_facts, rules, protected):
            return Decision("stateful_logical", candidate, approved=True)
    return Decision("stateful_logical", ladder[-1], approved=True, reason="fell through to refusal")


def hybrid_gate(ladder, background=frozenset(), transcript_facts=frozenset(), rules=(),
                 protected=frozenset(), ledger=None, declared_models=(), secret_pair=None,
                 epsilon_budget=float("inf"), **_kwargs) -> Decision:
    """Logical opacity AND a posterior-odds budget over a persistent
    ledger -- the highest-utility candidate (by ladder order, Eq. 5) that
    clears both gates."""
    ledger = ledger if ledger is not None else PosteriorLedger()
    for candidate in ladder:
        if not _opaque(candidate, background, transcript_facts, rules, protected):
            continue
        round_epsilon = 0.0
        if secret_pair and declared_models:
            round_epsilon = ledger.round_epsilon(declared_models, secret_pair, candidate.mode)
            if ledger.would_exceed(secret_pair, round_epsilon, epsilon_budget):
                continue
        if secret_pair and declared_models:
            ledger.charge(secret_pair, round_epsilon)
        return Decision("hybrid_gate", candidate, approved=True, round_epsilon=round_epsilon)
    return Decision("hybrid_gate", ladder[-1], approved=True, reason="no candidate cleared both gates")


MECHANISMS = {
    "q2_selector": q2_selector,
    "explicit_redaction": explicit_redaction,
    "task_minimal": task_minimal,
    "stateless_censor": stateless_censor,
    "stateful_logical": stateful_logical,
    "hybrid_gate": hybrid_gate,
}
