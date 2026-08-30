"""Tests for the LBR metric (Eq. 9), independent of the mosaic scenario
covered end-to-end in test_gate_mosaic_scenario.py.
"""

from gate_metrics import leakage_breach_rate
from gate_rules import Rule

RULE = Rule(body=(("?a", "reserves", "?i"), ("?p", "soleUserOf", "?i")), head=("?a", "memberOf", "?p"))
PROTECTED = frozenset({("alice", "memberOf", "orchid")})


def test_no_hidden_protected_facts_gives_zero_lbr():
    background = frozenset({("alice", "memberOf", "orchid")})  # already known
    assert leakage_breach_rate(background, frozenset(), (RULE,), PROTECTED) == 0.0


def test_full_leak_gives_lbr_of_one():
    final = frozenset({("alice", "reserves", "I"), ("orchid", "soleUserOf", "I")})
    assert leakage_breach_rate(frozenset(), final, (RULE,), PROTECTED) == 1.0


def test_partial_leak_across_multiple_protected_facts():
    protected = frozenset({
        ("alice", "memberOf", "orchid"),
        ("bob", "memberOf", "orchid"),
    })
    final = frozenset({("alice", "reserves", "I"), ("orchid", "soleUserOf", "I")})
    assert leakage_breach_rate(frozenset(), final, (RULE,), protected) == 0.5


def test_no_leak_gives_zero_lbr():
    final = frozenset({("alice", "reserves", "I")})  # missing the other half
    assert leakage_breach_rate(frozenset(), final, (RULE,), PROTECTED) == 0.0
