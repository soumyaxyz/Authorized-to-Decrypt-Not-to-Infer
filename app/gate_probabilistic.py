"""Posterior-odds ledger (manuscript.pdf SS IV-C, Eq. 7-8): charges each
APPROVED round's worst-case change in relative likelihood between a
declared secret pair against a persistent, cumulative budget, rather
than judging a response in isolation -- the transcript-level analogue of
the logical gate in gate_logical.py.

This is a worked implementation over a small, explicitly declared model
family Theta the caller supplies (`DeclaredModel`) -- estimating a
realistic Theta from actual laboratory data is a research question this
module does not answer (see PLANS.md), not something it invents.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeclaredModel:
    """One theta in Theta. `likelihoods[secret_label][response_key]` must
    hold Pr_theta[y = response_key | secret_label] for whatever finite
    alphabet of modeled responses this deployment declares (e.g. a
    candidate's `mode` from gate_candidates.py: "exact", "generalized",
    "refusal", ...)."""

    name: str
    likelihoods: dict

    def likelihood(self, secret_label: str, response_key: str) -> float:
        return self.likelihoods[secret_label].get(response_key, 1e-9)


@dataclass
class PosteriorLedger:
    """Cumulative epsilon per (coalition, protected pair) -- persisted
    alongside the Transcript it is keyed to, so a new conversation cannot
    reset it (SS III: "persistent state that cannot be reset by starting
    a new conversation")."""

    cumulative_epsilon: dict = field(default_factory=dict)

    @staticmethod
    def _pair_key(pair) -> str:
        return "{0}|{1}".format(*pair)

    def round_epsilon(self, models, pair, response_key: str) -> float:
        """The worst case over every declared model of the round's
        log-likelihood-ratio -- the "uniform conditional bound" Theorem 1
        requires before it may sum across rounds (SS IV-D)."""
        secret_i, secret_j = pair
        worst = 0.0
        for model in models:
            p_i = model.likelihood(secret_i, response_key)
            p_j = model.likelihood(secret_j, response_key)
            worst = max(worst, abs(math.log(p_i) - math.log(p_j)))
        return worst

    def would_exceed(self, pair, round_epsilon: float, budget: float) -> bool:
        current = self.cumulative_epsilon.get(self._pair_key(pair), 0.0)
        return current + round_epsilon > budget

    def charge(self, pair, round_epsilon: float) -> float:
        key = self._pair_key(pair)
        updated = self.cumulative_epsilon.get(key, 0.0) + round_epsilon
        self.cumulative_epsilon[key] = updated
        return updated

    def to_dict(self) -> dict:
        return dict(self.cumulative_epsilon)

    @staticmethod
    def from_dict(data: dict) -> "PosteriorLedger":
        return PosteriorLedger(cumulative_epsilon=dict(data))
