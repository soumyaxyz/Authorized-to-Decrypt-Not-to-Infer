"""Tests for turning a run_demo.sh log's RESULT lines into Table III."""

from report_table3 import parse_log, render_table3

SAMPLE_LOG = """\
[laba] published 'collaborator' fragment (policy: (RESEARCHER@LABA)) as share #0 on intra chain -- cid=Qm123
RESULT {"lab": "laba", "check": "publish", "outcome": "pass", "latency_ms": 120.5, "chain": "intra", "bytes_plaintext": 500, "bytes_ciphertext": 900, "expansion_ratio": 1.8}
[laba] bob decrypted share #0 successfully -- 4 JSON-LD node(s) recovered
RESULT {"lab": "laba", "check": "decrypt", "outcome": "pass", "latency_ms": 80.0, "chain": "intra", "holder": "bob"}
[labb] dave decrypted share #0 successfully -- 4 JSON-LD node(s) recovered
RESULT {"lab": "labb", "check": "decrypt", "outcome": "pass", "latency_ms": 95.0, "chain": "interlab", "holder": "dave"}
[labb] charlie DENIED: attributes do not satisfy the access policy
RESULT {"lab": "labb", "check": "decrypt", "outcome": "denied_policy", "latency_ms": 60.0, "chain": "interlab", "holder": "charlie"}
[labb] eve DENIED: no key was ever issued to them
RESULT {"lab": "labb", "check": "decrypt", "outcome": "denied_no_key", "latency_ms": 5.0, "chain": "interlab", "holder": "eve"}
[labb] tamper check: corrupted blob correctly rejected (hash mismatch)
RESULT {"lab": "labb", "check": "tamper_check", "outcome": "pass", "latency_ms": 70.0, "chain": "interlab"}
"""


def test_parse_log_extracts_only_result_lines():
    results = parse_log(SAMPLE_LOG.splitlines())
    assert len(results) == 6
    assert all("check" in r for r in results)


def test_parse_log_ignores_non_result_lines():
    results = parse_log(["not a result line", "RESULT not-json"])
    assert results == []


def test_render_table3_computes_decrypt_pass_rate():
    results = parse_log(SAMPLE_LOG.splitlines())
    table = render_table3(results)
    # 2 of 4 decrypt attempts passed (bob, dave); charlie/eve were denied.
    assert "2/4 (50%)" in table


def test_render_table3_computes_denied_policy_rate():
    results = parse_log(SAMPLE_LOG.splitlines())
    table = render_table3(results)
    assert "1/4 (25%)" in table


def test_render_table3_computes_tamper_and_crosslab_rates():
    results = parse_log(SAMPLE_LOG.splitlines())
    table = render_table3(results)
    assert "1/1 (100%)" in table  # tamper check
    # cross-lab (interlab) decrypt pass: dave only, out of 3 interlab decrypts
    assert "1/3 (33%)" in table


def test_render_table3_reports_na_for_missing_checks():
    table = render_table3([])
    assert table.count("n/a") >= 4
