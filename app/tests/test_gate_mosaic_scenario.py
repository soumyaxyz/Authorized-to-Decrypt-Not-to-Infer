"""End-to-end reproduction of manuscript.pdf Figure 1: every mechanism in
Table I run over the same two-round mosaic (Alice reserves instrument I;
I is the sole use of project Orchid this week), showing which ones leak
the protected "Alice is a member of Orchid" relationship and which don't
-- the concrete claim behind the paper's title.
"""

import pytest

from gate import GatePolicy, run_round
from gate_logical import is_logically_opaque
from gate_metrics import leakage_breach_rate
from gate_probabilistic import DeclaredModel, PosteriorLedger
from gate_rules import Rule
from gate_transcript import Transcript

MOSAIC_RULE = Rule(
    body=(("?a", "reserves", "?i"), ("?p", "soleUserOf", "?i")),
    head=("?a", "memberOf", "?p"),
)
PROTECTED = frozenset({("alice", "memberOf", "orchid")})
S1 = frozenset({("alice", "reserves", "I")})
S2 = frozenset({("orchid", "soleUserOf", "I")})

LEAKY_MECHANISMS = ["q2_selector", "explicit_redaction", "task_minimal", "stateless_censor"]
SAFE_MECHANISMS = ["stateful_logical", "hybrid_gate"]


def _run_mosaic(mechanism: str) -> Transcript:
    policy = GatePolicy(rules=(MOSAIC_RULE,), protected=PROTECTED, background=frozenset())
    transcript = Transcript(coalition="dave")
    run_round(mechanism, policy, transcript, S1, "reserves")
    run_round(mechanism, policy, transcript, S2, "soleUserOf")
    return transcript


@pytest.mark.parametrize("mechanism", LEAKY_MECHANISMS)
def test_ad_hoc_mechanisms_leak_the_mosaic(mechanism):
    transcript = _run_mosaic(mechanism)
    assert not is_logically_opaque(frozenset(), transcript.observed_facts(), (MOSAIC_RULE,), PROTECTED)
    assert leakage_breach_rate(frozenset(), transcript.observed_facts(), (MOSAIC_RULE,), PROTECTED) == 1.0


@pytest.mark.parametrize("mechanism", SAFE_MECHANISMS)
def test_history_aware_mechanisms_block_the_mosaic(mechanism):
    transcript = _run_mosaic(mechanism)
    assert is_logically_opaque(frozenset(), transcript.observed_facts(), (MOSAIC_RULE,), PROTECTED)
    assert leakage_breach_rate(frozenset(), transcript.observed_facts(), (MOSAIC_RULE,), PROTECTED) == 0.0


@pytest.mark.parametrize("mechanism", SAFE_MECHANISMS)
def test_round_one_alone_is_unaffected(mechanism):
    # Blocking round 2 shouldn't have blocked round 1 -- S1 alone is safe.
    transcript = _run_mosaic(mechanism)
    assert transcript.rounds[0].response == tuple(sorted(S1))
    assert transcript.rounds[0].mode == "exact"


@pytest.mark.parametrize("mechanism", SAFE_MECHANISMS)
def test_round_two_is_generalized_rather_than_flatly_refused(mechanism):
    # A safer rung of the candidate ladder exists (generalizing the object
    # breaks the join the mosaic rule needs) -- the gate should use it
    # instead of falling all the way to a blank refusal.
    transcript = _run_mosaic(mechanism)
    assert transcript.rounds[1].mode == "generalized"
    assert transcript.rounds[1].response != ()


def test_hybrid_gate_probabilistic_budget_can_block_even_when_logically_opaque():
    # No rules/protected facts at all -- isolates the probabilistic gate.
    # Every non-refusal mode is declared far more likely under secretA
    # than secretB; only "refusal" is equally likely under both, so a
    # tight budget forces the gate down to refusal even though nothing
    # here is logically unsafe.
    model = DeclaredModel(
        name="toy",
        likelihoods={
            "secretA": {"exact": 0.99, "minimal": 0.99, "generalized": 0.9, "aggregate": 0.9, "refusal": 0.5},
            "secretB": {"exact": 0.01, "minimal": 0.01, "generalized": 0.1, "aggregate": 0.1, "refusal": 0.5},
        },
    )
    policy = GatePolicy(
        rules=(), protected=frozenset(), background=frozenset(),
        declared_models=(model,), secret_pair=("secretA", "secretB"),
        epsilon_budget=0.05,
    )
    transcript = Transcript(coalition="tight-budget")
    decision = run_round("hybrid_gate", policy, transcript, S1, "reserves", PosteriorLedger())
    assert decision.chosen.mode == "refusal"


def test_hybrid_gate_allows_release_within_a_generous_budget():
    model = DeclaredModel(
        name="toy",
        likelihoods={"secretA": {"exact": 0.6}, "secretB": {"exact": 0.4}},
    )
    policy = GatePolicy(
        rules=(), protected=frozenset(), background=frozenset(),
        declared_models=(model,), secret_pair=("secretA", "secretB"),
        epsilon_budget=10.0,
    )
    transcript = Transcript(coalition="loose-budget")
    decision = run_round("hybrid_gate", policy, transcript, S1, "reserves", PosteriorLedger())
    assert decision.chosen.mode == "exact"
