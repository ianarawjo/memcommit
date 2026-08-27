"""
    Eval runner for semantic operations.
    Loads fixtures, runs the operation N times per case, and reports scores.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from memcommit.context import Context, Memory
from memcommit.application.evaluation.scoring import score_forget, score_integrate, score_stability
from memcommit.application.semantic.llm import LLMClient, LLMError
from memcommit.application.semantic.changes import AddChange, EditChange, ProposedChange, RemoveChange

_DIM  = "\033[2m"
_RESET = "\033[0m"


def _fmt_proposals(props: list[ProposedChange]) -> str:
    """One-line summary of a proposal list, for failure diagnostics."""
    if not props:
        return "(nothing)"
    parts = []
    for p in props:
        if isinstance(p, AddChange):
            preview = p.content[:40]
            ell = "…" if len(p.content) > 40 else ""
            parts.append(f'ADD "{preview}{ell}"')
        elif isinstance(p, RemoveChange):
            parts.append(f"REMOVE [{p.uid[:8]}]")
        elif isinstance(p, EditChange):
            parts.append(f"EDIT [{p.uid[:8]}]")
    return ", ".join(parts)


def _fmt_expected(expected: list[dict]) -> str:
    """One-line summary of an expected-changes list, for failure diagnostics."""
    if not expected:
        return "(nothing)"
    parts = []
    for e in expected:
        op = e["operation"]
        if op == "add":
            parts.append("ADD")
        elif op == "remove":
            parts.append(f"REMOVE [{e.get('uid', '?')[:8]}]")
        elif op == "edit":
            parts.append(f"EDIT [{e.get('uid', '?')[:8]}]")
    return ", ".join(parts)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Threshold for a case to count as "passed"
PASS_PRECISION = 0.8
PASS_RECALL    = 0.8
PASS_STABILITY = 2 / 3  # at least 2/3 runs agree (stored as exact fraction to avoid float boundary issues)


def _build_context(memories: list[dict]) -> Context:
    import uuid
    ctx = Context(uid=str(uuid.uuid4()), name="_eval_")
    for m in memories:
        ctx.add(Memory(uid=m["uid"], content=m["content"]))
    return ctx


def run_forget_eval(
    llm_model: str,
    runs: int = 3,
    print_fn: Callable[[str], None] = print,
) -> dict:
    """
    Run all forget eval cases, each repeated `runs` times.
    Returns a summary dict with per-case and aggregate results.
    """
    import memcommit.application.ops as ops

    fixture_path = FIXTURES_DIR / "forget.json"
    with open(fixture_path) as f:
        fixture = json.load(f)

    cases = fixture["cases"]
    client = LLMClient(model=llm_model)
    total = len(cases) * runs

    print_fn(f"\nRunning eval: forget | model: {llm_model!r} | {len(cases)} cases × {runs} runs = {total} LLM calls\n")

    case_results = []
    passed = 0

    for i, case in enumerate(cases, 1):
        print_fn(f"  [{i}/{len(cases)}] {case['id']}")
        ctx = _build_context(case["memories"])
        expected = case["expected"]
        run_proposals: list[list[ProposedChange]] = []
        run_scores = []

        for r in range(1, runs + 1):
            try:
                proposals, _ = ops.forget(ctx, case["query"], client)
                sc = score_forget(expected, proposals)
                run_proposals.append(proposals)
                run_scores.append(sc)
                p = f"{sc['precision']:.2f}" if sc["precision"] is not None else " — "
                re_ = f"{sc['recall']:.2f}" if sc["recall"] is not None else " — "
                print_fn(f"         run {r}: P={p}  R={re_}")
            except LLMError as e:
                print_fn(f"         run {r}: ERROR — {e}")
                run_scores.append(None)

        valid_scores = [s for s in run_scores if s is not None]
        if not valid_scores:
            print_fn("         → SKIP (all runs errored)\n")
            case_results.append({"id": case["id"], "status": "error"})
            continue

        has_expected_matches = len(expected) > 0
        avg_p = (
            sum(s["precision"] for s in valid_scores if s["precision"] is not None) / len(valid_scores)
            if valid_scores else 0
        )
        avg_r = sum(s["recall"]    for s in valid_scores if s["recall"]    is not None) / len(valid_scores) if valid_scores else 0
        stability = score_stability(run_proposals)

        # Precision is undefined when the expected set is empty (no-match case),
        # so skip precision gating there.
        ok_p   = (avg_p >= PASS_PRECISION) if has_expected_matches else True
        ok_r   = avg_r >= PASS_RECALL
        ok_stab = stability >= PASS_STABILITY
        case_pass = ok_p and ok_r and ok_stab
        if case_pass:
            passed += 1

        verdict = "PASS" if case_pass else "FAIL"
        issues = []
        if has_expected_matches and not ok_p:
            issues.append(f"precision {avg_p:.2f} < {PASS_PRECISION}")
        if not ok_r:
            issues.append(f"recall {avg_r:.2f} < {PASS_RECALL}")
        if not ok_stab:
            issues.append(f"stability {stability:.2f} < {PASS_STABILITY}")
        issue_str = "  (" + ", ".join(issues) + ")" if issues else ""
        print_fn(f"         → {verdict}{issue_str}  [stability={stability:.2f}]\n")

        case_results.append({
            "id": case["id"],
            "status": verdict.lower(),
            "avg_precision": avg_p,
            "avg_recall": avg_r,
            "stability": stability,
        })

    print_fn(f"Overall: {passed}/{len(cases)} cases passed  "
             f"(thresholds: P≥{PASS_PRECISION}, R≥{PASS_RECALL}, stability≥{PASS_STABILITY})\n")

    return {"model": llm_model, "runs": runs, "cases": case_results, "passed": passed, "total": len(cases)}


def run_integrate_eval(
    llm_model: str,
    runs: int = 3,
    print_fn: Callable[[str], None] = print,
) -> dict:
    """
    Run all integrate eval cases, each repeated `runs` times.
    Returns a summary dict with per-case and aggregate results.
    """
    import memcommit.application.ops as ops

    fixture_path = FIXTURES_DIR / "integrate.json"
    with open(fixture_path) as f:
        fixture = json.load(f)

    cases = fixture["cases"]
    client = LLMClient(model=llm_model)
    total = len(cases) * runs

    print_fn(f"\nRunning eval: integrate | model: {llm_model!r} | {len(cases)} cases × {runs} runs = {total} LLM calls\n")

    case_results = []
    passed = 0

    for i, case in enumerate(cases, 1):
        print_fn(f"  [{i}/{len(cases)}] {case['id']}")
        ctx = _build_context(case["memories"])
        expected = case["expected"]
        # Collect run data before printing so pass/fail is known when we render.
        run_proposals: list[list[ProposedChange] | None] = []
        run_scores: list[dict | None] = []
        # (score_line, proposals_or_None) — buffered until we know pass/fail
        run_lines: list[tuple[str, list[ProposedChange] | None]] = []

        for r in range(1, runs + 1):
            try:
                proposals, _ = ops.integrate(ctx, case["new_info"], client)
                sc = score_integrate(expected, proposals)
                run_proposals.append(proposals)
                run_scores.append(sc)
                p   = f"{sc['precision']:.2f}" if sc["precision"] is not None else " — "
                re_ = f"{sc['recall']:.2f}"    if sc["recall"]    is not None else " — "
                add = "✓" if sc["add_correct"] else "✗"
                run_lines.append((f"         run {r}: P={p}  R={re_}  add={add}", proposals))
            except LLMError as e:
                run_scores.append(None)
                run_proposals.append(None)
                run_lines.append((f"         run {r}: ERROR — {e}", None))

        valid_scores = [s for s in run_scores if s is not None]
        if not valid_scores:
            for line, _ in run_lines:
                print_fn(line)
            print_fn("         → SKIP (all runs errored)\n")
            case_results.append({"id": case["id"], "status": "error"})
            continue

        has_expected_non_add = any(e["operation"] != "add" for e in expected)
        avg_p = (
            sum(s["precision"] for s in valid_scores if s["precision"] is not None) / len(valid_scores)
            if valid_scores else 0
        )
        avg_r = (
            sum(s["recall"] for s in valid_scores if s["recall"] is not None) / len(valid_scores)
            if valid_scores else 0
        )
        add_correct_rate = sum(1 for s in valid_scores if s["add_correct"]) / len(valid_scores)
        stability = score_stability(run_proposals)

        ok_p    = (avg_p >= PASS_PRECISION) if has_expected_non_add else True
        ok_r    = avg_r >= PASS_RECALL
        ok_add  = add_correct_rate >= PASS_STABILITY
        ok_stab = stability >= PASS_STABILITY
        case_pass = ok_p and ok_r and ok_add and ok_stab
        if case_pass:
            passed += 1

        # Print run lines, with inline proposed/expected for each run on failure.
        exp_str = _fmt_expected(expected)
        for score_line, props in run_lines:
            print_fn(score_line)
            if not case_pass and props is not None:
                prop_str = _fmt_proposals(props)
                print_fn(
                    f"{_DIM}                 prop: {prop_str:<44}  exp: {exp_str}{_RESET}"
                )

        verdict = "PASS" if case_pass else "FAIL"
        issues = []
        if has_expected_non_add and not ok_p:
            issues.append(f"precision {avg_p:.2f} < {PASS_PRECISION}")
        if not ok_r:
            issues.append(f"recall {avg_r:.2f} < {PASS_RECALL}")
        if not ok_add:
            issues.append(f"add_correct_rate {add_correct_rate:.2f} < {PASS_STABILITY:.2f}")
        if not ok_stab:
            issues.append(f"stability {stability:.2f} < {PASS_STABILITY:.2f}")
        issue_str = "  (" + ", ".join(issues) + ")" if issues else ""
        print_fn(
            f"         → {verdict}{issue_str}"
            f"  [stability={stability:.2f}, add_correct={add_correct_rate:.2f}]"
        )
        print_fn("")

        case_results.append({
            "id": case["id"],
            "status": verdict.lower(),
            "avg_precision": avg_p,
            "avg_recall": avg_r,
            "add_correct_rate": add_correct_rate,
            "stability": stability,
        })

    print_fn(
        f"Overall: {passed}/{len(cases)} cases passed  "
        f"(thresholds: P≥{PASS_PRECISION}, R≥{PASS_RECALL}, "
        f"add_correct≥{PASS_STABILITY}, stability≥{PASS_STABILITY})\n"
    )

    return {
        "model": llm_model,
        "runs": runs,
        "cases": case_results,
        "passed": passed,
        "total": len(cases),
    }
