"""Tests for the persistent per-coalition transcript H_t."""

from gate_transcript import Transcript


def test_observed_facts_flattens_all_rounds():
    t = Transcript(coalition="dave")
    t.append("q1", (("alice", "reserves", "I"),), "exact")
    t.append("q2", (("orchid", "soleUserOf", "I"),), "exact")

    assert t.observed_facts() == frozenset({
        ("alice", "reserves", "I"),
        ("orchid", "soleUserOf", "I"),
    })


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "gate" / "dave.transcript.json"
    t = Transcript(coalition="dave")
    t.append("q1", (("alice", "reserves", "I"),), "exact")
    t.save(path)

    reloaded = Transcript.load_or_new(path, "dave")
    assert reloaded.coalition == "dave"
    assert reloaded.observed_facts() == t.observed_facts()
    assert reloaded.rounds[0].mode == "exact"


def test_load_or_new_returns_empty_transcript_when_missing(tmp_path):
    path = tmp_path / "gate" / "nobody.transcript.json"
    t = Transcript.load_or_new(path, "nobody")
    assert t.coalition == "nobody"
    assert t.observed_facts() == frozenset()


def test_coalition_pools_rounds_added_by_different_callers(tmp_path):
    # Two "requesters" sharing one coalition file -- SS III-B's point that
    # a per-login history is not a meaningful defense against pooling.
    path = tmp_path / "gate" / "coalition-x.transcript.json"

    dave_view = Transcript.load_or_new(path, "coalition-x")
    dave_view.append("q1", (("alice", "reserves", "I"),), "exact")
    dave_view.save(path)

    charlie_view = Transcript.load_or_new(path, "coalition-x")
    charlie_view.append("q2", (("orchid", "soleUserOf", "I"),), "exact")
    charlie_view.save(path)

    pooled = Transcript.load_or_new(path, "coalition-x")
    assert pooled.observed_facts() == frozenset({
        ("alice", "reserves", "I"),
        ("orchid", "soleUserOf", "I"),
    })
