"""Tests for relative logical opacity (Definition 1) directly reproducing
Figure 1's mosaic attack: S1 and S2 are each opaque against background
alone, but their union is not.
"""

from gate_logical import is_logically_opaque, new_protected_entailments
from gate_rules import Rule

MOSAIC_RULE = Rule(
    body=(("?a", "reserves", "?i"), ("?p", "soleUserOf", "?i")),
    head=("?a", "memberOf", "?p"),
)
PROTECTED = frozenset({("alice", "memberOf", "orchid")})
BACKGROUND = frozenset()
S1 = frozenset({("alice", "reserves", "I")})
S2 = frozenset({("orchid", "soleUserOf", "I")})


def test_s1_alone_is_opaque():
    assert is_logically_opaque(BACKGROUND, S1, (MOSAIC_RULE,), PROTECTED)


def test_s2_alone_is_opaque():
    assert is_logically_opaque(BACKGROUND, S2, (MOSAIC_RULE,), PROTECTED)


def test_s1_and_s2_together_are_not_opaque():
    combined = S1 | S2
    assert not is_logically_opaque(BACKGROUND, combined, (MOSAIC_RULE,), PROTECTED)


def test_new_protected_entailments_reports_the_leaked_fact():
    combined = S1 | S2
    leaked = new_protected_entailments(BACKGROUND, combined, (MOSAIC_RULE,), PROTECTED)
    assert leaked == frozenset({("alice", "memberOf", "orchid")})


def test_already_entailed_facts_are_not_a_new_leak():
    background_with_link = frozenset({("alice", "memberOf", "orchid")})
    assert is_logically_opaque(background_with_link, S1 | S2, (MOSAIC_RULE,), PROTECTED)
