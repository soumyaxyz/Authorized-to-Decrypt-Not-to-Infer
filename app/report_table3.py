"""Turns a run_demo.sh log (containing this project's `RESULT {json}`
lines -- see node.py's `_emit_result`) into manuscript.pdf's Table III.

    bash run_demo.sh              # writes demo.log as it runs
    python3 app/report_table3.py demo.log

Nothing here fabricates a number: a check with zero matching RESULT
lines is reported as "n/a", never silently rounded to 0% or 100%. This
only fills Table III (Q2 delivery-substrate checks) -- Table II needs the
generated-laboratory harness described in PLANS.md.
"""

from __future__ import annotations

import json
import re
import sys

RESULT_RE = re.compile(r"^RESULT (\{.*\})\s*$")


def parse_log(lines) -> list:
    results = []
    for line in lines:
        match = RESULT_RE.match(line.rstrip("\n"))
        if match:
            results.append(json.loads(match.group(1)))
    return results


def _rate(results, check, outcome, chain=None) -> str:
    matching = [r for r in results if r["check"] == check and (chain is None or r.get("chain") == chain)]
    if not matching:
        return "n/a"
    hits = sum(1 for r in matching if r["outcome"] == outcome)
    return "{0}/{1} ({2:.0f}%)".format(hits, len(matching), 100 * hits / len(matching))


def _mean_latency(results, check, chain=None) -> "float | None":
    matching = [r["latency_ms"] for r in results if r["check"] == check and "latency_ms" in r
                and (chain is None or r.get("chain") == chain)]
    if not matching:
        return None
    return sum(matching) / len(matching)


def render_table3(results: list) -> str:
    expansions = [r["expansion_ratio"] for r in results if r.get("expansion_ratio") is not None]
    expansion = "{0:.2f}x".format(sum(expansions) / len(expansions)) if expansions else "n/a"

    gate_latency = _mean_latency(results, "gate_round")
    publish_latency = _mean_latency(results, "publish")

    rows = [
        ("Authorized recipient decrypts", _rate(results, "decrypt", "pass")),
        ("Missing required attribute is denied", _rate(results, "decrypt", "denied_policy")),
        ("Ciphertext/blob tampering is detected", _rate(results, "tamper_check", "pass")),
        ("Cross-lab publish/retrieve succeeds", _rate(results, "decrypt", "pass", chain="interlab")),
        ("Semantic-gate latency", "{0:.2f} ms".format(gate_latency) if gate_latency is not None else "n/a"),
        ("End-to-end latency and expansion",
         "{0} ms, {1}".format(
             "{0:.2f}".format(publish_latency) if publish_latency is not None else "n/a", expansion,
         )),
    ]
    lines = ["| Check or measurement | Result |", "|---|---|"]
    lines += ["| {0} | {1} |".format(label, value) for label, value in rows]
    return "\n".join(lines)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    handle = open(path) if path else sys.stdin
    try:
        results = parse_log(handle)
    finally:
        if path:
            handle.close()

    print(render_table3(results))
    if not results:
        print("\n(no RESULT lines found -- run run_demo.sh first and pass its log here)", file=sys.stderr)


if __name__ == "__main__":
    main()
