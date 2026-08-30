"""Evaluation metrics from manuscript.pdf SS V-D. Only LBR (Eq. 9) is
implemented here -- it is a pure function of two closures and needs no
attacker model or generated laboratory data. Attack success, excess
disclosure, and gate latency need the generated-laboratory harness
described in PLANS.md.
"""

from __future__ import annotations

from gate_rules import Rule, Triple, closure


def leakage_breach_rate(
    background: "frozenset[Triple]",
    final_transcript: "frozenset[Triple]",
    rules: "tuple[Rule, ...]",
    protected: "frozenset[Triple]",
) -> float:
    """Eq. 9: fraction of initially-hidden protected propositions newly
    entailed by the final transcript. Returns 0.0 when every protected
    proposition was already entailed by KB alone -- there is nothing left
    to leak, so an empty denominator is not a division error."""
    initial = closure(background, rules) & protected
    hidden_initially = protected - initial
    if not hidden_initially:
        return 0.0
    final = closure(background | final_transcript, rules) & protected
    newly_entailed = final - initial
    return len(newly_entailed & hidden_initially) / len(hidden_initially)
