"""
    Scoring functions for semantic operation evaluation.
    All scoring is uid-level (no LLM judge required).
"""
from __future__ import annotations

from memcommit.application.semantic.changes import AddChange, EditChange, ProposedChange, RemoveChange


def score_forget(
    expected: list[dict],
    proposals: list[ProposedChange],
) -> dict:
    """
    Score a forget result at the uid level.

    Returns a dict with keys:
      precision   — correct proposals / total proposals  (None if no proposals)
      recall      — correct proposals / total expected   (None if nothing expected)
      tp, fp, fn  — raw counts
      details     — per-uid verdict ("tp", "fp", "fn")
    """
    expected_remove = {e["uid"] for e in expected if e["operation"] == "remove"}
    expected_edit   = {e["uid"] for e in expected if e["operation"] == "edit"}
    expected_all    = expected_remove | expected_edit

    proposed_remove = {c.uid for c in proposals if isinstance(c, RemoveChange)}
    proposed_edit   = {c.uid for c in proposals if isinstance(c, EditChange)}
    proposed_all    = proposed_remove | proposed_edit

    tp = len(proposed_all & expected_all)
    fp = len(proposed_all - expected_all)
    fn = len(expected_all - proposed_all)

    precision = tp / len(proposed_all) if proposed_all else None
    recall    = tp / len(expected_all) if expected_all else (1.0 if not proposed_all else 0.0)

    details = {}
    for uid in expected_all | proposed_all:
        if uid in expected_all and uid in proposed_all:
            details[uid] = "tp"
        elif uid in proposed_all:
            details[uid] = "fp"
        else:
            details[uid] = "fn"

    return {
        "precision": precision,
        "recall": recall,
        "tp": tp, "fp": fp, "fn": fn,
        "details": details,
    }


def score_stability(results: list[list[ProposedChange]]) -> float:
    """
    Measure how consistent the LLM is across N runs of the same case.

    Returns the fraction of runs whose change-key set matches the majority set
    (1.0 = perfectly stable, 0.0 = every run different).

    AddChange has no uid; it is fingerprinted as the sentinel ``"__add__"`` so
    that two runs that both propose an add are counted as agreeing.
    """
    if not results:
        return 1.0

    def _key(c: ProposedChange) -> str:
        return "__add__" if isinstance(c, AddChange) else c.uid  # type: ignore[union-attr]

    key_sets = [frozenset(_key(c) for c in run) for run in results]
    from collections import Counter
    counts = Counter(key_sets)
    majority_count = counts.most_common(1)[0][1]
    return majority_count / len(results)


def score_integrate(
    expected: list[dict],
    proposals: list[ProposedChange],
) -> dict:
    """
    Score an integrate result.

    Non-add operations (edit/remove) are scored by uid using the same
    precision/recall logic as ``score_forget``.  The add decision is scored
    as a binary flag: correct when ``expected_add == proposed_add``.

    Returns a dict with all keys from ``score_forget`` plus:
      add_expected  — True if an add was expected
      add_proposed  — True if an add was proposed
      add_correct   — True when the two agree
    """
    expected_add = any(e["operation"] == "add" for e in expected)
    expected_non_add = [e for e in expected if e["operation"] != "add"]

    proposed_add = any(isinstance(p, AddChange) for p in proposals)
    proposed_non_add = [p for p in proposals if not isinstance(p, AddChange)]

    base = score_forget(expected_non_add, proposed_non_add)
    return {
        **base,
        "add_expected": expected_add,
        "add_proposed": proposed_add,
        "add_correct":  expected_add == proposed_add,
    }
