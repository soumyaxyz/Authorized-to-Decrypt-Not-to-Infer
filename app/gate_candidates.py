"""Candidate ladder (manuscript.pdf Eq. 4): the fixed set of response
shapes a disclosure round chooses among, so that mechanisms in
gate_mechanisms.py differ only in which member of this same pool they
release -- not in how creative their answer generator is (SS III-A:
"this prevents an especially capable answer generator from being
confused with an especially safe security mechanism").

`generalized` and `aggregate` here are deliberately simple stand-ins
(coarsen-the-object / count-instead-of-list) -- the paper's own
generalization semantics (entity-to-class, time/location coarsening,
batching) is a modeling decision for the declared ontology, not
something this module can invent generically. See PLANS.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from gate_rules import Triple


@dataclass(frozen=True)
class Candidate:
    mode: str
    response: tuple


def build_candidate_ladder(full_facts: "frozenset[Triple]", query_predicate: str) -> tuple:
    """`full_facts` is everything the publisher is willing to consider
    releasing this round (e.g. Q2's already-whitelisted profile
    fragment) -- the ladder only ever narrows or coarsens that set, it
    never adds facts outside it. Ordered highest-utility (exact) to
    lowest (refusal), matching Eq. 5's preference order."""
    exact = tuple(sorted(full_facts))

    minimal = tuple(sorted(t for t in full_facts if t[1] == query_predicate))

    generalized = tuple(sorted(
        (t[0], t[1], "class:" + t[1]) if t[1] == query_predicate else t
        for t in full_facts
    ))

    matching_count = sum(1 for t in full_facts if t[1] == query_predicate)
    aggregate = (("aggregate:" + query_predicate, "count", str(matching_count)),) if matching_count else ()

    refusal = ()

    return (
        Candidate("exact", exact),
        Candidate("minimal", minimal),
        Candidate("generalized", generalized),
        Candidate("aggregate", aggregate),
        Candidate("refusal", refusal),
    )
