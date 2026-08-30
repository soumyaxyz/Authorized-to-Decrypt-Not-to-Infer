"""Horn-rule closure engine implementing Cn_Sigma(.), the entailment
operator Definition 1 (manuscript.pdf SS IV-B) is stated in terms of.
Facts are (subject, predicate, object) string triples; a rule fires when
every pattern in its body matches some fact under one consistent
variable binding (a token beginning with '?' is a variable). Forward
chaining to a fixpoint -- the declared rule sets this project uses stay
small enough that naive fixpoint iteration is plenty; nothing here is
Datalog-optimized, and nothing here freezes what SS III-B calls "the
restricted rule language" -- that choice belongs in the paper's own
supplementary material (see PLANS.md).
"""

from __future__ import annotations

from typing import NamedTuple, Tuple

Triple = Tuple[str, str, str]


class Rule(NamedTuple):
    """`body` is a tuple of triple patterns; `head` is one triple pattern.
    E.g. Figure 1's rule -- reserve(a,i) and soleUserOf(p,i) => memberOf(a,p):
        Rule(
            body=(("?a", "reserves", "?i"), ("?p", "soleUserOf", "?i")),
            head=("?a", "memberOf", "?p"),
        )
    """
    body: tuple
    head: tuple


def _is_var(token: str) -> bool:
    return token.startswith("?")


def _match(pattern: Triple, fact: Triple, bindings: dict) -> "dict | None":
    extended = dict(bindings)
    for pattern_token, fact_token in zip(pattern, fact):
        if _is_var(pattern_token):
            if pattern_token in extended and extended[pattern_token] != fact_token:
                return None
            extended[pattern_token] = fact_token
        elif pattern_token != fact_token:
            return None
    return extended


def _substitute(pattern: Triple, bindings: dict) -> Triple:
    return tuple(bindings.get(token, token) for token in pattern)


def _apply_rule(rule: Rule, facts: "frozenset[Triple]") -> "set[Triple]":
    """Every head instance derivable from `facts` in one application of `rule`."""
    derived = set()

    def extend(body_index: int, bindings: dict) -> None:
        if body_index == len(rule.body):
            derived.add(_substitute(rule.head, bindings))
            return
        pattern = rule.body[body_index]
        for fact in facts:
            next_bindings = _match(pattern, fact, bindings)
            if next_bindings is not None:
                extend(body_index + 1, next_bindings)

    extend(0, {})
    return derived


def closure(facts: "frozenset[Triple]", rules: "tuple[Rule, ...]") -> "frozenset[Triple]":
    """Cn_Sigma(facts): forward-chain every rule against the growing fact
    set until nothing new is derived."""
    current = set(facts)
    changed = True
    while changed:
        changed = False
        frozen = frozenset(current)
        for rule in rules:
            for derived in _apply_rule(rule, frozen):
                if derived not in current:
                    current.add(derived)
                    changed = True
    return frozenset(current)
