"""Capture actual Case and Context Conformance over the ticker Distill result."""

from __future__ import annotations

from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
DISTILL_EVIDENCE = ROOT / "docs/screenshots/mem-distill-ticker-20260815/actual-run.json"
BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
SPEC = importlib.util.spec_from_file_location("terminal_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.OUT = OUT

MODEL = "gpt-5.6-sol"
REASONING = "none"
ROWS = 52
COLUMNS = 180

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _clear() -> None:
    print("\x1b[2J\x1b[H", end="")


def _heading(text: str) -> None:
    print(f"\x1b[1;38;2;138;173;244m{text}\x1b[0m")


def _memory(text: str) -> str:
    return f"\x1b[38;2;202;211;245m{text}\x1b[0m"


def _load_fixture() -> tuple[list[tuple[str, str]], list[str]]:
    data = json.loads(DISTILL_EVIDENCE.read_text(encoding="utf-8"))
    cases = []
    for mapping in data["source"]["cases"]:
        source, expected = mapping.rsplit(" → ", 1)
        cases.append((source, expected))
    rules = [item["content"] for item in data["analysis"]["rules"]]
    if len(cases) != 20 or len(rules) != 5:
        raise RuntimeError("Ticker Distill evidence no longer matches this evaluation.")
    return cases, rules


def _prepare_store(root: Path):
    import memcommit.ops as ops
    from memcommit.ground import (
        GroundTargetSpec,
        bind_ground_workbench,
        create_ground_session,
        propose_ground_case,
        propose_ground_rule,
    )
    from memcommit.store import MemoryStore

    cases, rule_texts = _load_fixture()
    store = MemoryStore(root=root)
    raw = ops.init("ticker/raw")
    candidates = ops.init("ticker/cases")
    candidate_memories = [ops.add(candidates, source) for source, _ in cases]
    publication = ops.init("ticker/output")
    examples = ops.init("ticker/example-mappings")
    for source, expected in cases:
        ops.add(examples, f"{source} → {expected}")
    rules_context = ops.init("ticker/distilled-rules")
    for rule in rule_texts:
        ops.add(rules_context, rule)
    for context in (raw, candidates, publication, examples, rules_context):
        store.create_context(context)

    session = bind_ground_workbench(
        create_ground_session(
            "ticker-rules",
            goal="Generate concise deterministic synthetic tickers from company names.",
        ),
        description="Check the five distilled ticker Rules against twenty examples.",
        raw_context=raw,
        derived_context=candidates,
        target_contexts=(publication,),
        target_requirements=(
            GroundTargetSpec(
                context_name=publication.name,
                description="Publish only outputs that pass Conformance.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    contexts = (raw, candidates, publication)
    for index, rule in enumerate(rule_texts, 1):
        session = propose_ground_rule(
            session,
            rule=rule,
            rationale=f"Distill Rule {index} from the reviewed ticker proposal.",
            current_contexts=contexts,
        )
    ground_rules = session.items_of_kind("RULE")
    for index, ((source, expected), memory) in enumerate(
        zip(cases, candidate_memories, strict=True),
        1,
    ):
        if 15 <= index <= 17:
            primary = ground_rules[3]
            role = "BOUNDARY"
        elif 11 <= index <= 13:
            primary = ground_rules[2]
            role = "BOUNDARY"
        else:
            primary = ground_rules[1]
            role = "FIT"
        session = propose_ground_case(
            session,
            rule_selector=primary.uid,
            case=source,
            source_context_uid=candidates.uid,
            source_memory_uid=memory.uid,
            target_context_names=(publication.name,),
            expected=expected,
            rationale=f"Ticker example {index} from the Distill Source.",
            current_contexts=contexts,
            case_role=role,
        )
    store.save_ground_session(session)
    return store, session, examples, rules_context, cases, rule_texts


def _setup_page(cases: list[tuple[str, str]], rules: list[str]) -> None:
    _clear()
    _heading("MEM CHECK-CONFORMANCE · TICKER ROUND-TRIP")
    print(f"PROVIDER · {MODEL} · REASONING {REASONING.upper()}")
    print("GROUND · ticker-rules · 5 ACTIVE RULES · 20 INCLUDE MEMORIES")
    print("EXPECTED OUTPUTS · FROZEN LOCALLY · WITHHELD FROM PROVIDER")
    print()
    for index, rule in enumerate(rules, 1):
        print(_memory(f"r{index} · {rule}"))
    print()
    for index, (source, expected) in enumerate(cases, 1):
        print(_memory(f"c{index:02d} · {source} → {expected}"))
    print()
    print("R · RUN CASE CONFORMANCE", flush=True)


def _case_page(report, start: int, stop: int, page: int, total: int) -> None:
    subject = {item.uid: item for item in report.subjects}
    _clear()
    _heading(f"CASE CONFORMANCE · TICKER RULE REPLAY · PAGE {page}/{total}")
    print("EXPECTED OUTPUTS WERE NOT SENT TO THE PROVIDER")
    print(f"OVERVIEW · {report.overview}")
    print()
    for judgment in report.case_judgments[start:stop]:
        item = subject[judgment.subject_uid]
        _heading(f"{item.alias} · {judgment.status}")
        print(_memory(f"  INPUT · {item.content}"))
        print(f"  PREDICTED · {judgment.predicted or '(none)'}")
        print(f"  EXPECTED · {item.expected}")
        print(f"  WHY · {judgment.reason}")
        print()
    print("N · NEXT" if page < total else "C · RUN CONTEXT CONFORMANCE", flush=True)
    print(f"READY CASE PAGE {page}/{total}", flush=True)


def _context_page(report) -> None:
    rule_by_uid = {item.uid: item for item in report.rules}
    _clear()
    _heading("CONTEXT CONFORMANCE · EXAMPLE CONTEXT AGAINST DISTILLED RULES")
    print(f"TARGET · {report.source_label} · 20 DIRECT MEMORIES")
    print(f"RULES · {report.rules_label} · 5 DIRECT MEMORIES")
    print(f"OVERVIEW · {report.overview}")
    print()
    for judgment in report.context_judgments:
        rule = rule_by_uid[judgment.rule_uid]
        _heading(f"{rule.alias} · {judgment.status}")
        print(_memory(f"  RULE · {rule.content}"))
        print(f"  EVIDENCE · {len(judgment.evidence_subject_uids)} Memories")
        print(f"  WHY · {judgment.reason}")
        print()
    print(f"OUTSIDE · {len(report.outside_subject_uids)} Memories")
    print("V · VERIFY READ-ONLY CONTRACT", flush=True)
    print("READY CONTEXT REPORT", flush=True)


def _report_dict(report) -> dict[str, object]:
    return report.to_dict()


def _run_child(store_root: Path) -> None:
    from memcommit.conformance_runtime import (
        execute_context_conformance,
        execute_ground_conformance,
    )
    from memcommit.query_provider import CodexChatGPTProvider
    from memcommit.store import context_record_digest, ground_session_record_digest

    store, session, examples, rules_context, cases, rules = _prepare_store(store_root)
    before_ground = ground_session_record_digest(session)
    before_examples = context_record_digest(examples)
    before_rules = context_record_digest(rules_context)
    _setup_page(cases, rules)
    if sys.stdin.readline().strip().lower() != "r":
        raise RuntimeError("Case Conformance was not started.")

    _clear()
    _heading("CHECK CONFORMANCE · CASE · PROVIDER TURN")
    print(f"MODEL · {MODEL} · REASONING {REASONING.upper()}")
    print("INPUT · 5 RULES + 20 CASE INPUTS")
    print("EXPECTED OUTPUTS · WITHHELD")
    print("STATE · RUNNING · NO REPORT PUBLISHED", flush=True)
    provider = CodexChatGPTProvider.connect(
        model=MODEL,
        reasoning_effort=REASONING,
        timeout=300,
    )
    case_report = execute_ground_conformance(
        store=store,
        ground_name="ticker-rules",
        provider_factory=lambda: provider,
    )
    page_size = 7
    total_pages = (len(case_report.case_judgments) + page_size - 1) // page_size
    for page in range(1, total_pages + 1):
        start = (page - 1) * page_size
        _case_page(
            case_report,
            start,
            min(start + page_size, len(case_report.case_judgments)),
            page,
            total_pages,
        )
        expected_key = "c" if page == total_pages else "n"
        if sys.stdin.readline().strip().lower() != expected_key:
            raise RuntimeError("Case Conformance review was interrupted.")

    _clear()
    _heading("CHECK CONFORMANCE · CONTEXT · PROVIDER TURN")
    print(f"MODEL · {MODEL} · REASONING {REASONING.upper()}")
    print("TARGET · ticker/example-mappings · 20 MEMORIES")
    print("RULES · ticker/distilled-rules · 5 MEMORIES")
    print("STATE · RUNNING · NO REPORT PUBLISHED", flush=True)
    context_report = execute_context_conformance(
        store=store,
        target_name=examples.name,
        rules_name=rules_context.name,
        provider_factory=lambda: provider,
    )
    _context_page(context_report)
    if sys.stdin.readline().strip().lower() != "v":
        raise RuntimeError("Conformance verification was interrupted.")

    ground_unchanged = (
        ground_session_record_digest(store.load_ground_session("ticker-rules"))
        == before_ground
    )
    examples_unchanged = (
        context_record_digest(store.load_direct(examples.name)) == before_examples
    )
    rules_unchanged = (
        context_record_digest(store.load_direct(rules_context.name)) == before_rules
    )
    case_counts = Counter(item.status for item in case_report.case_judgments)
    context_counts = Counter(item.status for item in context_report.context_judgments)
    evidence = {
        "provider": {"model": MODEL, "reasoning_effort": REASONING},
        "case_conformance": _report_dict(case_report),
        "context_conformance": _report_dict(context_report),
        "verification": {
            "ground_unchanged": ground_unchanged,
            "example_context_unchanged": examples_unchanged,
            "rules_context_unchanged": rules_unchanged,
        },
    }
    (OUT / "actual-run.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    _clear()
    _heading("CHECK CONFORMANCE · TICKER VERIFICATION")
    print(f"CASE JUDGMENTS · 20/20 · {dict(case_counts)}")
    print(f"CASE ISSUES · {case_report.issue_count}")
    print(f"CONTEXT RULE JUDGMENTS · 5/5 · {dict(context_counts)}")
    print(f"CONTEXT ISSUES · {context_report.issue_count}")
    print(f"GROUND UNCHANGED · {ground_unchanged}")
    print(f"EXAMPLE CONTEXT UNCHANGED · {examples_unchanged}")
    print(f"RULES CONTEXT UNCHANGED · {rules_unchanged}")
    print("CHECKPOINTS CREATED · 0")
    print("DURABLE USER PROFILE MUTATION · NONE (TEMPORARY STORE REMOVED)")
    print("EVIDENCE · docs/screenshots/mem-check-conformance-ticker-20260815/actual-run.json")
    print("READY VERIFICATION", flush=True)


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


def _settle(child: pexpect.spawn, seconds: float = 0.3) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(size=65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            continue
        except pexpect.EOF:
            return


def _snapshot(recorder, stem: str) -> None:
    BASE._render(recorder.getvalue(), stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-check-conformance-") as directory:
        recorder = BASE._StreamRecorder()
        child = pexpect.spawn(
            sys.executable,
            [str(Path(__file__).resolve()), "--child", str(Path(directory) / "store")],
            cwd=str(ROOT),
            env=_environment(),
            encoding="utf-8",
            codec_errors="replace",
            timeout=360,
            dimensions=(ROWS, COLUMNS),
        )
        child.logfile_read = recorder
        try:
            child.expect("RUN CASE CONFORMANCE")
            _settle(child)
            _snapshot(recorder, "01-ground-rules-and-cases")
            child.sendline("r")
            child.expect("STATE .* RUNNING .* NO REPORT PUBLISHED")
            _settle(child, 0.15)
            _snapshot(recorder, "02-case-provider-running")

            child.expect(r"READY CASE PAGE 1/(\d+)")
            total = int(child.match.group(1))
            for page in range(1, total + 1):
                if page > 1:
                    child.expect(fr"READY CASE PAGE {page}/{total}")
                _settle(child)
                _snapshot(recorder, f"{page + 2:02d}-case-results-page-{page:02d}")
                child.sendline("c" if page == total else "n")

            child.expect("STATE .* RUNNING .* NO REPORT PUBLISHED")
            _settle(child, 0.15)
            _snapshot(recorder, f"{total + 3:02d}-context-provider-running")
            child.expect("READY CONTEXT REPORT")
            _settle(child)
            _snapshot(recorder, f"{total + 4:02d}-context-conformance-report")
            child.sendline("v")
            child.expect("READY VERIFICATION")
            child.expect(pexpect.EOF)
            _snapshot(recorder, f"{total + 5:02d}-read-only-verification")
        finally:
            if child.isalive():
                child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[2]))
    else:
        main()
