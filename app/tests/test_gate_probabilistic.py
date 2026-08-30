"""Tests for the posterior-odds ledger (Eq. 7-8)."""

import math

import pytest

from gate_probabilistic import DeclaredModel, PosteriorLedger

MODEL = DeclaredModel(
    name="toy",
    likelihoods={
        "orchid": {"released": 0.9, "refused": 0.1},
        "other": {"released": 0.1, "refused": 0.9},
    },
)
PAIR = ("orchid", "other")


def test_round_epsilon_matches_hand_computed_log_ratio():
    ledger = PosteriorLedger()
    eps = ledger.round_epsilon((MODEL,), PAIR, "released")
    assert eps == pytest.approx(abs(math.log(0.9) - math.log(0.1)))


def test_round_epsilon_takes_worst_case_over_declared_models():
    tame_model = DeclaredModel(
        name="tame",
        likelihoods={"orchid": {"released": 0.5}, "other": {"released": 0.5}},
    )
    ledger = PosteriorLedger()
    eps = ledger.round_epsilon((tame_model, MODEL), PAIR, "released")
    # the sharper (MODEL) model dominates the worst-case bound
    assert eps == pytest.approx(abs(math.log(0.9) - math.log(0.1)))


def test_charge_accumulates_across_rounds_per_eq8():
    ledger = PosteriorLedger()
    eps1 = ledger.round_epsilon((MODEL,), PAIR, "released")
    ledger.charge(PAIR, eps1)
    eps2 = ledger.round_epsilon((MODEL,), PAIR, "refused")
    ledger.charge(PAIR, eps2)

    cumulative = ledger.cumulative_epsilon[ledger._pair_key(PAIR)]
    assert cumulative == pytest.approx(eps1 + eps2)


def test_would_exceed_respects_budget():
    ledger = PosteriorLedger()
    eps = ledger.round_epsilon((MODEL,), PAIR, "released")
    assert not ledger.would_exceed(PAIR, eps, budget=eps + 0.01)
    assert ledger.would_exceed(PAIR, eps, budget=eps - 0.01)


def test_ledger_serialization_roundtrip():
    ledger = PosteriorLedger()
    eps = ledger.round_epsilon((MODEL,), PAIR, "released")
    ledger.charge(PAIR, eps)

    restored = PosteriorLedger.from_dict(ledger.to_dict())
    assert restored.cumulative_epsilon == ledger.cumulative_epsilon
