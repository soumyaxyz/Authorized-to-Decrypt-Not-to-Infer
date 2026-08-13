"""Tests for the personal knowledge graph: seed construction, selective
disclosure (predicate whitelisting), and on-disk JSON-LD persistence.
"""

from rdflib import RDF, Literal

import pkg as pkg_mod


def test_build_alice_graph_shape():
    g = pkg_mod.build_alice_graph()
    assert len(g) == 34
    names = list(g.objects(pkg_mod.PKG.alice, pkg_mod.PKG.researchInterest))
    assert Literal("Attribute-Based Encryption") in names


def test_select_subgraph_only_includes_whitelisted_predicates():
    g = pkg_mod.build_alice_graph()
    fragment = pkg_mod.select_subgraph(g, pkg_mod.PKG.alice, pkg_mod.PROFILES["collaborator"])

    # allowed: name, memberOf, authoredPaper (+ pulled-in paper triples),
    # researchInterest -- plus rdf:type, which select_subgraph always
    # includes for the subject regardless of the predicate whitelist.
    predicates = {p for _, p, _ in fragment.triples((pkg_mod.PKG.alice, None, None))}
    assert predicates == pkg_mod.PROFILES["collaborator"] | {RDF.type}

    # devices/activity are never traversed for this profile -- not pulled in
    # and filtered, just never reached at all.
    device_triples = list(fragment.triples((pkg_mod.PKG.device1, None, None)))
    assert device_triples == []


def test_select_subgraph_pulls_in_linked_resource_details():
    g = pkg_mod.build_alice_graph()
    fragment = pkg_mod.select_subgraph(g, pkg_mod.PKG.alice, pkg_mod.PROFILES["collaborator"])

    # authoredPaper points at paper resources -- their title/year should
    # come along even though "title"/"year" aren't themselves whitelisted.
    titles = list(fragment.objects(None, pkg_mod.PKG.title))
    assert Literal("Selective Disclosure over Personal Knowledge Graphs") in titles


def test_lab_internal_profile_is_a_superset_of_collaborator():
    assert pkg_mod.PROFILES["collaborator"] <= pkg_mod.PROFILES["lab_internal"]


def test_load_or_seed_graph_persists_to_disk(tmp_path):
    path = tmp_path / "pkg" / "alice.jsonld"
    assert not path.exists()

    g = pkg_mod.load_or_seed_graph(tmp_path)
    assert len(g) == 34
    assert path.exists()


def test_load_or_seed_graph_loads_existing_file_rather_than_reseeding(tmp_path):
    g = pkg_mod.load_or_seed_graph(tmp_path)
    pkg_mod.add_fact(g, pkg_mod.PKG.alice, pkg_mod.PKG.researchInterest, Literal("Quantum Computing"))
    pkg_mod.save_graph(g, tmp_path)

    reloaded = pkg_mod.load_or_seed_graph(tmp_path)
    assert len(reloaded) == 35
    interests = list(reloaded.objects(pkg_mod.PKG.alice, pkg_mod.PKG.researchInterest))
    assert Literal("Quantum Computing") in interests


def test_add_fact_is_idempotent_for_duplicate_triples(tmp_path):
    g = pkg_mod.load_or_seed_graph(tmp_path)
    before = len(g)

    pkg_mod.add_fact(g, pkg_mod.PKG.alice, pkg_mod.PKG.researchInterest, Literal("Duplicate Interest"))
    pkg_mod.add_fact(g, pkg_mod.PKG.alice, pkg_mod.PKG.researchInterest, Literal("Duplicate Interest"))

    assert len(g) == before + 1


def test_owners_are_stored_separately(tmp_path):
    alice = pkg_mod.load_or_seed_graph(tmp_path, owner="alice")
    pkg_mod.add_fact(alice, pkg_mod.PKG.alice, pkg_mod.PKG.role, Literal("PI-updated"))
    pkg_mod.save_graph(alice, tmp_path, owner="alice")

    bob = pkg_mod.load_or_seed_graph(tmp_path, owner="bob")
    assert (tmp_path / "pkg" / "alice.jsonld").exists()
    assert (tmp_path / "pkg" / "bob.jsonld").exists()
    # bob's seed graph is untouched by alice's edit -- separate files.
    assert Literal("PI-updated") not in list(bob.objects(pkg_mod.PKG.alice, pkg_mod.PKG.role))
