"""Tests for the Horn-rule closure engine (Cn_Sigma) gate_logical.py's
Definition 1 check is built on.
"""

from gate_rules import Rule, closure

MOSAIC_RULE = Rule(
    body=(("?a", "reserves", "?i"), ("?p", "soleUserOf", "?i")),
    head=("?a", "memberOf", "?p"),
)


def test_closure_includes_original_facts():
    facts = frozenset({("alice", "reserves", "I")})
    result = closure(facts, ())
    assert facts <= result


def test_single_rule_application_derives_head():
    facts = frozenset({
        ("alice", "reserves", "I"),
        ("orchid", "soleUserOf", "I"),
    })
    result = closure(facts, (MOSAIC_RULE,))
    assert ("alice", "memberOf", "orchid") in result


def test_incomplete_body_derives_nothing_new():
    facts = frozenset({("alice", "reserves", "I")})
    result = closure(facts, (MOSAIC_RULE,))
    assert result == facts


def test_closure_is_a_fixpoint_chained_rules():
    # a chain of two rules, each needing the other's output
    step1 = Rule(body=(("?x", "a", "?y"),), head=("?x", "b", "?y"))
    step2 = Rule(body=(("?x", "b", "?y"),), head=("?x", "c", "?y"))
    facts = frozenset({("x", "a", "y")})
    result = closure(facts, (step1, step2))
    assert ("x", "b", "y") in result
    assert ("x", "c", "y") in result


def test_closure_does_not_duplicate_or_loop_forever():
    facts = frozenset({("x", "a", "y")})
    identity_rule = Rule(body=(("?s", "a", "?o"),), head=("?s", "a", "?o"))
    result = closure(facts, (identity_rule,))
    assert result == facts
