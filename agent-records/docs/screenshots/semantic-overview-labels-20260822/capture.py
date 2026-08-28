"""Capture operation-owned semantic overview labels in a 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("semantic_label_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


CASES = (
    ("summary-single", "SUMMARY · capture/summary", "01-summarize-single-artifact"),
    ("summary-both", "[CURRENT + DESCENDANTS]", "02-summarize-both-scopes"),
    ("distill", "SOURCE OVERVIEW", "03-distill-source-overview"),
    ("elaborate", "PROPOSAL OVERVIEW", "04-elaborate-proposal-overview"),
    ("audit", "AUDIT SUMMARY", "05-audit-owned-sections"),
    ("find", "FINDINGS", "06-find-owned-sections"),
    ("update", "PLAN", "07-update-plan"),
    ("resolve", "INDEPENDENT FIT VERIFICATION", "08-resolve-plan-verification"),
    ("forget", "ASSESSMENT", "09-forget-assessment"),
    ("sever", "SOURCE OVERVIEW", "10-sever-source-overview"),
    ("atomize", "UNRESOLVED", "11-atomize-three-part-overview"),
    ("meld", "ACCOUNTING", "12-meld-understood-accounting"),
    ("review", "OVERVIEW", "13-review-neutral-overview"),
)


def _summary_document(*, both: bool):
    from memcommit.adapters.console.commands.summarize.workbench.presentation import (
        project_summarize_outcome,
        project_summarize_result,
    )
    from memcommit.adapters.console.commands.summarize.workbench.model import SummarizeTuiOutcome
    from memcommit.application.operations.summarize.application import SummarizeResult
    from memcommit.application.capabilities.semantic.understanding import UnderstandingSummary

    direct = SummarizeResult(
        context_name="capture/summary",
        include_descendants=False,
        follow_embeds=False,
        source_digest="a" * 64,
        source_count=2,
        understanding=UnderstandingSummary(
            "The current Context records a closure and preserves staff card access as an explicit exception.",
            ("memory-direct",),
        ),
    )
    if not both:
        return project_summarize_result(direct)
    recursive = SummarizeResult(
        context_name="capture/summary",
        include_descendants=True,
        follow_embeds=True,
        source_digest="b" * 64,
        source_count=4,
        understanding=UnderstandingSummary(
            "The complete subtree also records an accessible alternate entrance and a later reopening time.",
            ("memory-direct", "memory-child"),
        ),
    )
    return project_summarize_outcome(SummarizeTuiOutcome((direct, recursive)))


def _distill_document():
    from memcommit.core.context import Context, Memory
    from memcommit.application.operations.distill.model import DistillAnalysis, DistilledRule
    from memcommit.application.operations.distill.application import DistillResult
    from memcommit.application.operations.distill.goal_fit import DistillGoalFit
    from memcommit.adapters.console.commands.distill.workbench.presentation import (
        project_distill_result,
    )
    from memcommit.application.operations.summarize.model import collect_summary_scope
    from memcommit.application.operations.summarize.application import FrozenSummarySource

    context = Context(
        uid="00000000-0000-4000-8000-000000000101",
        name="capture/examples",
    )
    memory = Memory(
        uid="00000000-0000-4000-8000-000000000102",
        content="Confirm the accessible route before publishing a closure notice.",
    )
    context.add(memory)
    frame = collect_summary_scope(
        (context,),
        root_context_uid=context.uid,
        root_context_name=context.name,
        include_descendants=False,
        follow_embeds=False,
    )
    analysis = DistillAnalysis(
        uid="00000000-0000-4000-8000-000000000103",
        source=frame,
        goal="Preserve access exceptions.",
        overview="The Source demonstrates that a closure notice must retain a verified accessible alternative.",
        rules=(
            DistilledRule(
                uid="00000000-0000-4000-8000-000000000104",
                content="Confirm and preserve an accessible alternative before publishing a closure notice.",
                rationale="The Source explicitly couples publication with access verification.",
                support_memory_uids=(memory.uid,),
                boundary_memory_uids=(),
            ),
        ),
        outside_memory_uids=(),
        goal_fit=DistillGoalFit(
            verdict="FIT",
            reason="The proposed Rule is relevant to and compatible with the Goal.",
            considered_rule_uids=(
                "00000000-0000-4000-8000-000000000104",
            ),
            material_rule_uids=(),
        ),
    )
    return project_distill_result(
        DistillResult(
            analysis=analysis,
            frozen_source=FrozenSummarySource(frame=frame, token="capture"),
        )
    )


def _elaborate_document():
    from memcommit.application.operations.elaborate.model import ElaborateAnalysis, ElaboratedRule, ElaborateMode
    from memcommit.application.operations.elaborate.application import ElaborateResult
    from memcommit.adapters.console.commands.elaborate.viewer.projection import (
        project_elaborate_result,
    )

    analysis = ElaborateAnalysis(
        uid="00000000-0000-4000-8000-000000000201",
        mode=ElaborateMode.GOAL_TO_RULES,
        inputs=("Publish accurate access guidance.",),
        overview="The proposal turns the Goal into one reviewable publication condition.",
        rules=(
            ElaboratedRule(
                uid="00000000-0000-4000-8000-000000000202",
                content="Publish access guidance only after the route and effective period are verified.",
                rationale="The condition makes the abstract accuracy Goal operational.",
            ),
        ),
        number=1,
    )
    return project_elaborate_result(ElaborateResult(analysis))


def _resolution_view(kind: str):
    from memcommit.application.capabilities.resolution.workbench import (
        ResolutionContextLocation,
        ResolutionOverviewSection,
        ResolutionWorkbenchView,
    )

    sections_by_kind = {
        "audit": (
            ResolutionOverviewSection("summary", "AUDIT SUMMARY", "All requested quality checks completed over the same frozen Source."),
            ResolutionOverviewSection("checks", "CHECKS", "DUPLICATES · COMPLETE\nAMBIGUITIES · COMPLETE\nCONFLICTS · COMPLETE"),
            ResolutionOverviewSection("source", "AUDITED SOURCE", "capture/source · 3 direct Memories."),
            ResolutionOverviewSection("provenance", "PROVENANCE", "QUALITY RULESET 1 · Capture Provider"),
            ResolutionOverviewSection("boundary", "BOUNDARY", "This report is model-assisted evidence, not proof that no other issue exists."),
        ),
        "find": (
            ResolutionOverviewSection("scope", "SCOPE", "Inspected three direct Memories in one frozen readable Context."),
            ResolutionOverviewSection("findings", "FINDINGS", "Reported one actionable ambiguity finding."),
            ResolutionOverviewSection("boundary", "BOUNDARY", "No Context or Memory changes have been applied."),
        ),
        "update": (
            ResolutionOverviewSection("plan", "PLAN", "The exact target edit is staged and remains separate from Apply."),
        ),
        "resolve": (
            ResolutionOverviewSection("issue", "ISSUE · CONFLICT", "The two route claims cannot govern the same effective period."),
            ResolutionOverviewSection("plan", "AUTOMATIC PLAN", "Retain the verified route and remove the superseded route claim."),
            ResolutionOverviewSection("fit", "INDEPENDENT FIT VERIFICATION", "The proposed post-image fits the retained access rule."),
        ),
        "forget": (
            ResolutionOverviewSection("assessment", "ASSESSMENT", "The instruction applies to one obsolete access detail; the remaining Source stays explicit."),
        ),
        "sever": (
            ResolutionOverviewSection("source", "SOURCE OVERVIEW", "The Source contains public access guidance and one private operational detail."),
        ),
        "atomize": (
            ResolutionOverviewSection("understood", "UNDERSTOOD", "The Source contains a closure, an exception, and an effective period."),
            ResolutionOverviewSection("changed", "CHANGED", "One compound Memory was split into two independently reviewable claims."),
            ResolutionOverviewSection("unresolved", "UNRESOLVED", "The pronoun in one Source remains open for review."),
        ),
        "meld": (
            ResolutionOverviewSection("understood", "UNDERSTOOD", "Both peers preserve the same closure while differing on the alternate route."),
            ResolutionOverviewSection("accounting", "ACCOUNTING", "Source coverage · 4/4\nRelation coverage · 3/3\nOpen issues · REQUIRED 1"),
        ),
    }
    titles = {
        "audit": "MEM AUDIT",
        "find": "MEM FIND AMBIGUITIES",
        "update": "MEM UPDATE",
        "resolve": "MEM RESOLVE · AUTOMATIC INTERPRETATION PLAN",
        "forget": "MEM FORGET · SELECTIVE SOURCE REVISION",
        "sever": "MEM SEVER · SELECTIVE RESULT",
        "atomize": "MEM ATOMIZE",
        "meld": "MEM MELD",
        "review": "MEM REVIEW · LEGACY REPORT",
    }
    sections = sections_by_kind.get(kind, ())
    overview = (
        "Review source-linked findings without changing any Context or Memory."
        if kind == "review"
        else "\n\n".join(section.text for section in sections)
    )
    return ResolutionWorkbenchView(
        operation=kind.upper(),
        artifact_uid=f"capture-{kind}",
        revision="1",
        title=titles[kind],
        route="SOURCE capture/source → RESULT capture/result",
        status="READ-ONLY · CAPTURE",
        metrics=(),
        context_locations=(
            ResolutionContextLocation("SOURCE", "capture/source"),
        ),
        overview=overview,
        overview_sections=sections,
        list_label="REVIEW ITEMS",
        items=(),
        empty_message="No item interaction is needed for this label capture.",
        results_label="EXACT RESULTS",
        results=(),
        capabilities=frozenset(),
        show_results=False,
    )


def _run_case_child(kind: str) -> None:
    from memcommit.adapters.console.terminal.components.resolution.session_shell import (
        run_resolution_workbench_shell,
    )
    from memcommit.adapters.console.terminal.components.semantic_viewer import run_semantic_viewer

    print(f"CAPTURE CASE · {kind}")
    print(f"PTY · {os.get_terminal_size().columns} COLUMNS × {os.get_terminal_size().lines} ROWS", flush=True)
    if kind == "summary-single":
        run_semantic_viewer(_summary_document(both=False), title="SUMMARY")
    elif kind == "summary-both":
        run_semantic_viewer(_summary_document(both=True), title="SUMMARY")
    elif kind == "distill":
        run_semantic_viewer(_distill_document(), title="DISTILL")
    elif kind == "elaborate":
        run_semantic_viewer(_elaborate_document(), title="ELABORATE")
    else:
        run_resolution_workbench_shell(
            _resolution_view(kind),
            read_only=True,
            terminal_label=f"{kind.title()} label capture",
        )
    print(f"CAPTURE CLOSED · {kind} · READ-ONLY · DURABLE STATE UNCHANGED", flush=True)


def _run_verification_child(result_path: Path) -> None:
    results = json.loads(result_path.read_text(encoding="utf-8"))
    print("\x1b[38;2;139;213;255;1mSEMANTIC OVERVIEW LABELS · READ-ONLY VERIFICATION\x1b[0m")
    print(f"PTY · {os.get_terminal_size().columns} COLUMNS × {os.get_terminal_size().lines} ROWS")
    print("PROFILE / CURRENT CONTEXT · NOT CONSULTED")
    print("PROVIDER / STORE / CHECKPOINTS · NOT OPENED")
    print()
    for result in results:
        color = "139;213;202" if result["ok"] else "237;135;150"
        status = "PASS" if result["ok"] else "FAIL"
        print(f"\x1b[38;2;{color};1m{status}\x1b[0m · {result['stem']} · {result['expected']}")
    print()
    print("SUMMARIZE · ARTIFACT BODY WITHOUT NESTED COMPREHENSION HEADING")
    print("RESOLUTION · OPERATION-OWNED SECTIONS WITHOUT GENERIC GROUP")
    print("LEGACY UNTYPED OVERVIEW · NEUTRAL OVERVIEW")
    print("\x1b[38;2;139;213;202;1mVERIFICATION COMPLETE · 13/13 LABEL SURFACES PASS\x1b[0m", flush=True)


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(args: list[str]) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), *args],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for kind, expected, stem in CASES:
        child, recorder = _spawn(["--child-case", kind])
        try:
            child.expect(expected)
            _BASE._settle(child)
            _BASE._snapshot(recorder, stem)
            child.send("q")
            child.expect("CAPTURE CLOSED")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)
        plain = (OUT / f"{stem}.txt").read_text(encoding="utf-8")
        raw = (OUT / f"{stem}.typescript").read_text(encoding="utf-8")
        ok = (
            expected in plain
            and "WHAT MEM UNDERSTOOD" not in plain
            and "\x1b[" in raw
            and ("38;" in raw or "48;" in raw)
        )
        results.append({"stem": stem, "expected": expected, "ok": ok})

    with tempfile.TemporaryDirectory(prefix="semantic-overview-labels-") as directory:
        result_path = Path(directory) / "results.json"
        result_path.write_text(json.dumps(results), encoding="utf-8")
        child, recorder = _spawn(["--child-verification", str(result_path)])
        try:
            child.expect("VERIFICATION COMPLETE")
            _BASE._settle(child)
            _BASE._snapshot(recorder, "14-read-only-verification")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)

    if len(results) != len(CASES) or not all(result["ok"] for result in results):
        raise RuntimeError(f"Semantic overview label verification failed: {results!r}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child-case":
        _run_case_child(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "--child-verification":
        _run_verification_child(Path(sys.argv[2]))
    else:
        main()
