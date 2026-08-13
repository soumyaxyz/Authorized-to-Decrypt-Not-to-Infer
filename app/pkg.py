"""A personal knowledge graph, persisted to disk as JSON-LD, plus
selective-disclosure logic: choosing a policy-relevant subgraph to share
rather than encrypting the whole graph or an arbitrary file.

The graph is not rebuilt from scratch on every run. `load_or_seed_graph`
loads whatever's already persisted for an owner, seeding it from a small
starter graph only the first time a lab ever runs. `add_fact` +
`save_graph` accumulate new triples across runs -- the same write path an
agentic maintainer would eventually use.
"""

from pathlib import Path

from rdflib import Graph, Namespace, URIRef, Literal, RDF
from rdflib.namespace import FOAF, XSD

PKG = Namespace("http://pkg.example.org/ns#")


def build_alice_graph() -> Graph:
    g = Graph()
    g.bind("pkg", PKG)
    g.bind("foaf", FOAF)

    alice = PKG.alice
    g.add((alice, RDF.type, FOAF.Person))
    g.add((alice, FOAF.name, Literal("Alice Chen")))
    g.add((alice, FOAF.mbox, URIRef("mailto:alice@laba.example.org")))
    g.add((alice, PKG.memberOf, PKG.LabA))
    g.add((alice, PKG.role, Literal("PI")))

    papers = [
        (PKG.paper1, "Selective Disclosure over Personal Knowledge Graphs", 2026),
        (PKG.paper2, "CP-ABE for Federated Research Data Sharing", 2025),
        (PKG.paper3, "Auditable Off-Chain Storage via Content-Addressed Metadata", 2024),
    ]
    for paper, title, year in papers:
        g.add((paper, RDF.type, PKG.Paper))
        g.add((paper, PKG.title, Literal(title)))
        g.add((paper, PKG.year, Literal(year, datatype=XSD.gYear)))
        g.add((alice, PKG.authoredPaper, paper))

    for interest in [
        "Federated Knowledge Graphs",
        "Attribute-Based Encryption",
        "Blockchain Systems",
    ]:
        g.add((alice, PKG.researchInterest, Literal(interest)))

    devices = [
        (PKG.device1, "Dell Precision 7770", "SN-88213-XJ", "10.0.4.22"),
        (PKG.device2, "NVIDIA DGX Station", "SN-77120-QA", "10.0.4.45"),
    ]
    for device, model, serial, ip in devices:
        g.add((device, RDF.type, PKG.Device))
        g.add((device, PKG.deviceModel, Literal(model)))
        g.add((device, PKG.deviceSerial, Literal(serial)))
        g.add((device, PKG.ipAddress, Literal(ip)))
        g.add((alice, PKG.hasDevice, device))

    activity = PKG.activity1
    g.add((activity, RDF.type, PKG.ResearchActivity))
    g.add((activity, PKG.activityType, Literal("grant-review")))
    g.add((activity, PKG.activityDate, Literal("2026-06-01", datatype=XSD.date)))
    g.add((alice, PKG.hasActivity, activity))

    return g


def _graph_path(data_dir, owner: str = "alice") -> Path:
    return Path(data_dir) / "pkg" / f"{owner}.jsonld"


def load_or_seed_graph(data_dir, owner: str = "alice") -> Graph:
    """Load `owner`'s persisted graph from `data_dir/pkg/<owner>.jsonld`.
    The first time a lab runs, that file doesn't exist yet, so this seeds
    it from the built-in starter graph and persists that as the baseline --
    every run after that loads what's actually on disk, including
    whatever `add_fact` has appended since."""
    path = _graph_path(data_dir, owner)
    g = Graph()
    g.bind("pkg", PKG)
    g.bind("foaf", FOAF)
    if path.exists():
        g.parse(data=path.read_text(encoding="utf-8"), format="json-ld")
    else:
        g += build_alice_graph()
        save_graph(g, data_dir, owner)
    return g


def save_graph(graph: Graph, data_dir, owner: str = "alice") -> None:
    path = _graph_path(data_dir, owner)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph.serialize(format="json-ld", indent=2), encoding="utf-8")


def add_fact(graph: Graph, subject: URIRef, predicate: URIRef, obj) -> None:
    graph.add((subject, predicate, obj))


def select_subgraph(graph: Graph, subject: URIRef, allowed_predicates: set) -> Graph:
    """Keep only `subject`'s triples for whitelisted predicates, plus the
    full description of any URIRef object reached through one of them (e.g.
    a paper's title/year). A predicate left off the whitelist -- hasDevice,
    say -- is never traversed, so that node's data never enters the
    fragment, rather than being pulled in and then filtered out.
    """
    frag = Graph()
    frag.bind("pkg", PKG)
    frag.bind("foaf", FOAF)

    type_triple = next(graph.triples((subject, RDF.type, None)), None)
    if type_triple:
        frag.add(type_triple)

    for predicate, obj in graph.predicate_objects(subject):
        if predicate not in allowed_predicates:
            continue
        frag.add((subject, predicate, obj))
        if isinstance(obj, URIRef):
            for triple in graph.triples((obj, None, None)):
                frag.add(triple)

    return frag


PROFILES = {
    "collaborator": {
        FOAF.name,
        PKG.memberOf,
        PKG.authoredPaper,
        PKG.researchInterest,
    },
    "lab_internal": {
        FOAF.name,
        FOAF.mbox,
        PKG.memberOf,
        PKG.role,
        PKG.authoredPaper,
        PKG.researchInterest,
        PKG.hasDevice,
        PKG.hasActivity,
    },
}


if __name__ == "__main__":
    g = build_alice_graph()
    print(f"Full PKG: {len(g)} triples\n")

    fragment = select_subgraph(g, PKG.alice, PROFILES["collaborator"])
    print(f"'collaborator' fragment: {len(fragment)} triples "
          f"(devices/activity excluded)\n")
    print(fragment.serialize(format="json-ld", indent=2))
