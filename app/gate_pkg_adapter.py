"""Adapter between rdflib graphs (Q1/Q2's representation, pkg.py) and the
(subject, predicate, object)-string triples the gate's rule engine
operates on. Kept as a thin, separate module rather than folded into
gate_rules.py so the gate itself stays RDF-library-agnostic -- Sigma/P/KB
are declared once per deployment and shouldn't have to change shape if
the storage layer ever does.
"""

from __future__ import annotations

from rdflib import Graph, Literal, URIRef

from gate_rules import Triple


def graph_to_triples(graph: Graph) -> "frozenset[Triple]":
    return frozenset((str(s), str(p), str(o)) for s, p, o in graph)


def triples_to_graph(triples) -> Graph:
    """Best-effort reconstruction: an http(s)-looking string becomes a
    URIRef, anything else -- including a gate-generated "class:..." or
    "aggregate:..." placeholder -- becomes a Literal. Enough for a
    generalized/aggregate candidate to still serialize as valid JSON-LD;
    not a claim that it round-trips back to the original typed literals
    (XSD dates, gYear, etc.) that select_subgraph produced."""
    g = Graph()
    for s, p, o in triples:
        subject = URIRef(s)
        predicate = URIRef(p)
        obj = URIRef(o) if o.startswith("http") else Literal(o)
        g.add((subject, predicate, obj))
    return g
