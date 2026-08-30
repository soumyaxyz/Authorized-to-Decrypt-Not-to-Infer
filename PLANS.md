# What's left to close this out

Context: `manuscript.pdf` frames this repo as answering three questions.
**Q1** (build the graph) belongs to a separate companion project. **Q2**
(encrypt + deliver an approved fragment) is this repo's original
architecture (`pkg.py`, `crypto.py`, `chain.py`, `storage.py`, `node.py`)
and the paper explicitly freezes it as a narrow delivery substrate. **Q3**
(decide whether the *cumulative* history of approved disclosures is
safe -- the paper's actual contribution, and the "not to infer" half of
its title) had **zero code** anywhere in this repo before this session.

This document is a punch list of what's still needed, ordered so that
research/authorial decisions (which need a human, not more code) come
before mechanical follow-ups (which just need Docker or CI).

## Done this session

- **`gate.py` + `gate_rules.py`, `gate_logical.py`, `gate_probabilistic.py`,
  `gate_candidates.py`, `gate_transcript.py`, `gate_mechanisms.py`,
  `gate_metrics.py`, `gate_pkg_adapter.py`** -- a first working
  implementation of Q3's core equations: Horn-rule closure (`Cn_Sigma`),
  Definition 1 (relative logical opacity), the Eq. 4 candidate ladder,
  the Eq. 7-8 posterior-odds ledger, all six Table I mechanisms, and the
  Eq. 9 LBR metric. Pure stdlib except the rdflib adapter -- no charm-crypto
  or running chain needed, so it's independently testable (and was:
  35 new tests, all passing, including a full reproduction of Figure 1's
  mosaic attack across every mechanism in Table I).
- **`node.py publish-gated`** -- wires the gate into the real Q2 pipeline
  (Fig. 2's architecture): a fragment now goes seed-graph -> gate -> ABE
  encrypt -> IPFS -> chain, selectable by `--mechanism`.
- **Table III instrumentation** -- `node.py` now emits a `RESULT {json}`
  line (outcome, latency, byte sizes) per publish/decrypt/tamper-check/
  gate round; `report_table3.py` turns a `run_demo.sh` log into the
  manuscript's actual Table III, with `n/a` for anything unmeasured
  rather than a fabricated number.
- README updated to explain the Q1/Q2/Q3 split and point at both new
  pieces; `example_gate_policy.json` ships a worked (illustrative)
  Figure-1 policy.

**Not yet verified**: the full Docker/charm-crypto/chain stack isn't
available in the sandbox this was built in (no `docker`, no `charm`
package, no PBC library). Every pure-Python piece above was actually run
and passes; `cmd_publish_gated`'s integration with `crypto.py`/`chain.py`/
`storage.py` was checked by reading, and the rdflib round-trip was
verified directly, but not exercised end-to-end against a live chain and
IPFS node. **Before relying on `publish-gated`, run the existing app test
suite in Docker and then `run_demo.sh`'s new Experiment 5** (see Repo
README's Quick start) to confirm the full pipeline still works.

## 1. Freeze the rule language (research decision, blocks everything else)

The paper's own Appendix A promises "the syntax and semantics of the
chosen Horn, Datalog, or description-logic fragment" as supplementary
material -- that choice isn't made yet. `gate_rules.py` implements plain
conjunctive Horn rules (no negation, no aggregation, no temporal/recency
reasoning). That may or may not be expressive enough for the scenario
inventory in Appendix B (multi-hop path completion, overlapping-query
differencing, correlated attribute prediction, Sybil-style history
splitting). **Decide the fragment's expressiveness first**; only then is
"does `gate_rules.py` need to become a real Datalog engine (e.g.
`pyDatalog`, clingo/ASP) instead of a naive fixpoint" an answerable
engineering question.

## 2. Declare a real Sigma / P / KB / Theta

`example_gate_policy.json` is Figure 1's mosaic in a generic
`(subject, predicate, object)` vocabulary -- illustrative only, not
expressed in `pkg.py`'s actual PKG namespace, and not a real research
artifact. Real experiments need:
- Rules (Sigma) over whatever ontology Q1 actually produces.
- A protected-fact policy (P) -- which relationships/attributes count as
  sensitive, decided by whoever owns the laboratory-graph schema.
- A background-knowledge model (KB) an adversary is assumed to start
  with.
- A declared model family (Theta) for the probabilistic gate -- this is
  itself a modeling/statistics question (what distributions over
  adversary background knowledge are plausible?), not something
  `gate_probabilistic.py` can invent.

## 3. Q1 dependency: the companion simulator isn't finished either

The sibling repo referenced by the paper (Epistemic-Society, "Paper 1")
is itself mid-development (active `tinytroupe.*.log` files and evolving
`docs/evaluation_design.md` as of this session). Tier 2 (generated
laboratory episodes, SS V-B) needs its oracle graph `G*_L` and
reconstructed graph `Ĝ_L` exports. Until that exists:
- The cross-repo contract (how Epistemic-Society's `D_obs(T)`/
  `G_ground_truth` export maps into this repo's triple representation)
  isn't written. It's a natural extension of `gate_pkg_adapter.py`, but
  shouldn't be built against a moving target -- confirm Epistemic-Society's
  export format is stable first.

## 4. Attacker implementations (SS V-C) -- none exist

Fixed requester, greedy information-gain policy, symbolic multi-hop
planner, Bayesian expected-information-gain policy, adaptive differencing
requester, two colluding identities, and an LLM red team. Each is a
nontrivial algorithm (the Bayesian and differencing ones especially) that
also needs Tier 2's generated worlds to run against meaningfully --
substantial standalone research/engineering effort, not a follow-up patch.

## 5. Remaining metrics (SS V-D)

- **Already obtainable now**: gate latency (`gate_round` RESULT lines),
  LBR (`gate_metrics.leakage_breach_rate`).
- **Blocked on item 4**: attacker success at a preregistered posterior
  threshold, rounds to first breach, excess disclosure.
- **Blocked on item 2 (a calibrated Theta)**: worst empirical cumulative
  log-odds amplification.
- **Blocked on an "answer key" per task** (an eval-design decision, not
  engineering): task completion / answer correctness, safe-oracle regret
  (the "exact safe oracle" mechanism in Table I also isn't implemented
  yet -- it needs the same answer keys to define "highest-utility safe
  response").

## 6. The three evaluation tiers, at paper scale

- **Tier 1 (exact micro-worlds, SS V-A)**: this session implemented *one*
  worked example end to end (Figure 1's mosaic, all six mechanisms,
  `test_gate_mosaic_scenario.py`) as a template proving the equations are
  correctly wired up. The paper's actual Tier 1 needs the full scenario
  inventory from Appendix B (direct requests, multi-hop ontology
  inference, overlapping-query differencing, refusal leakage, correlated
  attributes, two-identity pooling, Sybil-style history splitting) each
  precisely specified -- a research-design task before it's an
  engineering one.
- **Tier 2 (generated laboratory episodes)**: blocked on item 3.
- **Tier 3 (Q2 integration, Table III)**: implemented this session
  (`report_table3.py`) -- just needs someone to actually run
  `run_demo.sh` in a Docker-enabled environment to produce real numbers.

## 7. Run the demo somewhere with Docker

This sandbox has no `docker` binary and no `charm` package (charm-crypto
needs a compiled PBC library this environment doesn't have), so nothing
in `app/`'s existing crypto/chain/IPFS path -- nor the new
`publish-gated` integration -- could be executed end-to-end here, only
read and unit-tested piece by piece. Run:
```bash
docker build -t pkg-app-test ./app && docker run --rm -e PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pkg-app-test python3 -m pytest tests/ -v
bash run_demo.sh
python3 app/report_table3.py demo.log
```

## 8. `FIGURE_PLAN.md`

Referenced by the paper (SS VI) as already specifying the privacy-utility
plots. It doesn't exist in this repo, Epistemic-Society, or anywhere else
findable. Needs authoring once items 4-6 fix what the primary metrics and
comparisons actually are.

## 9. Formal proofs (Appendix A)

Inductive logical-opacity proof, conditional-history likelihood-ratio
composition proof, treatment of nonzero delta, and an exhaustive
equivalence check between the implementation and possible-world semantics
on micro-worlds. Mathematical exposition -- a writing task for the paper's
author. The "exhaustive equivalence check" could become an extension of
`test_gate_rules.py`/`test_gate_logical.py` once item 1 (the rule
language) is frozen, but the proof itself isn't code.

## 10. Paper placeholders

Every bracketed placeholder (abstract's numerical headline, SS VI's
narrative paragraphs, Table II's `[value]` cells, Table III's
`[pass rate]`/`[value]` cells, the conclusion's final sentence) waits on
items 4-7 producing real numbers. Not a coding task -- listed here only so
it isn't forgotten as the actual last step.

## 11. Housekeeping

Epistemic-Society's `README.md`/`handoff.md` still refer to this repo by
its old name, `Personal-Knowlege-Graph-Sharing` (confirmed same content
via `app/pkg.py`'s schema) -- worth a quick pass to update those
references now that this repo is `Authorized-to-Decrypt-Not-to-Infer` on
GitHub, so the two-paper program's cross-links don't go stale.

## Out of scope by the paper's own design (already tracked, not new)

Production identity/PKI, credential revocation, storage availability,
endpoint security, and validator-set hardening -- SS VIII says these
"bound the systems claim but do not erase the semantic problem." Already
listed in this README's "Known POC simplifications"; nothing new to add
here.
