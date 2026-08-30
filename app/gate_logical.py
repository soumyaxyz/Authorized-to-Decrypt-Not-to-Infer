"""Relative logical opacity (manuscript.pdf Definition 1, Eq. 6):

    Cn_Sigma(KB u H_t) n P == Cn_Sigma(KB) n P

An extension is opaque when it introduces no NEW protected entailment
under the declared rule theory Sigma -- not when its own triples merely
avoid naming a protected fact directly. That distinction is exactly what
Figure 1's mosaic defeats: S1 and S2 are each opaque against KB alone,
but S1 u S2 is not.
"""

from __future__ import annotations

from gate_rules import Rule, Triple, closure


def protected_entailments(
    background: "frozenset[Triple]", rules: "tuple[Rule, ...]", protected: "frozenset[Triple]"
) -> "frozenset[Triple]":
    return closure(background, rules) & protected


def is_logically_opaque(
    background: "frozenset[Triple]",
    extension: "frozenset[Triple]",
    rules: "tuple[Rule, ...]",
    protected: "frozenset[Triple]",
) -> bool:
    before = protected_entailments(background, rules, protected)
    after = protected_entailments(background | extension, rules, protected)
    return before == after


def new_protected_entailments(
    background: "frozenset[Triple]",
    extension: "frozenset[Triple]",
    rules: "tuple[Rule, ...]",
    protected: "frozenset[Triple]",
) -> "frozenset[Triple]":
    """Diagnostic only: which protected facts would newly become
    derivable. Not the full minimal-derivation trace SS III-B describes
    keeping ("minimal derivations are retained so an unsafe candidate can
    be transformed rather than rejected blindly") -- just the delta set,
    enough to explain a rejection without proving it is the smallest one."""
    before = protected_entailments(background, rules, protected)
    after = protected_entailments(background | extension, rules, protected)
    return after - before
