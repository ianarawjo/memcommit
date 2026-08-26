"""Run and capture one real ticker-example Distill evaluation."""

from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
SPEC = importlib.util.spec_from_file_location("terminal_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.OUT = OUT

COLUMNS = 180
ROWS = 52
MODEL = "gpt-5.6-sol"
REASONING = "none"
SOURCE_NAME = "test/ground/ticker-rule-examples"
RESULT_NAME = "test/ground/ticker-rule-output"
GOAL = (
    "Derive reusable, deterministic rules for generating concise synthetic "
    "ticker symbols from company names and share-class details. Treat every "
    "mapping as a design example, not an official market ticker, and state "
    "important boundaries or exceptions."
)
CASES = (
    "North Star Energy Inc. → NSE",
    "Blue River Holdings LLC → BRH",
    "Cedar Valley Technologies Corporation → CVT",
    "Aurora Robotics Ltd. → AR",
    "Harbor Point Foods PLC → HPF",
    "The Meridian Group Inc. → MG",
    "Lumen Labs LLC → LL",
    "Quanta Systems & Services Inc. → QSS",
    "Atlas 7 Networks Corp. → A7N",
    "3 Rivers Logistics LLC → 3RL",
    "Redwood Inc. → RED",
    "Meridian Corporation → MER",
    "Solstice Ltd. → SOL",
    "International Business Fabricators Inc. → IBF",
    "North Star Energy Inc., Class B → NSE.B",
    "North Star Energy Inc., Class A → NSE.A",
    "Blue River Holdings LLC, Preferred → BRH.P",
    "Acme & Sons Ltd. → AS",
    "Axiom AI Technologies Inc. → AAT",
    "The 5th Avenue Retail Group LLC → 5ARG",
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _clear() -> None:
    print("\x1b[2J\x1b[H", end="")


def _heading(text: str) -> None:
    print(f"\x1b[1;38;2;138;173;244m{text}\x1b[0m")


def _memory(text: str) -> str:
    return f"\x1b[38;2;202;211;245m{text}\x1b[0m"


def _prepare_store(root: Path):
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore(root=root)
    source = ops.init(SOURCE_NAME)
    for case in CASES:
        ops.add(source, case)
    store.create_context(source)
    store.set_current(SOURCE_NAME)
    return store, source


def _input_page() -> None:
    _clear()
    _heading("MEM DISTILL · TICKER EXAMPLE EVALUATION")
    print(f"MODEL · {MODEL} · REASONING {REASONING.upper()} · ISOLATED TEMPORARY STORE")
    print(f"SOURCE · {SOURCE_NAME} · DIRECT · 20 SYNTHETIC CASES")
    print("SOURCE STATUS · LOCAL · READ-ONLY DURING ANALYSIS")
    print()
    for index, case in enumerate(CASES, 1):
        print(_memory(f"{index:02d}. {case}"))
    print()
    print("GOAL")
    print(GOAL)
    print()
    print("R · RUN ACTUAL DISTILL", flush=True)


def _result_pages(result) -> list[list[str]]:
    analysis = result.analysis
    pages: list[list[str]] = []
    rules = list(analysis.rules)
    per_page = 5
    page_count = max(1, math.ceil(len(rules) / per_page))
    alias_by_uid = {
        source.memory_uid: source.alias for source in analysis.source.sources
    }
    for page_index in range(page_count):
        start = page_index * per_page
        batch = rules[start : start + per_page]
        lines = [
            "MEM DISTILL · REVIEWED TICKER RULES",
            f"STATUS · REVIEW ONLY · SOURCE UNCHANGED · PAGE {page_index + 1}/{page_count}",
            f"PROVIDER · {MODEL} · REASONING {REASONING.upper()}",
            f"PROPOSED RULES · {len(rules)} FROM {len(analysis.source.sources)} CASES",
            "",
        ]
        if page_index == 0:
            lines.extend(["WHAT MEM UNDERSTOOD", analysis.overview, ""])
        for ordinal, rule in enumerate(batch, start + 1):
            support = ", ".join(alias_by_uid[uid] for uid in rule.support_memory_uids)
            boundary = ", ".join(alias_by_uid[uid] for uid in rule.boundary_memory_uids)
            lines.extend(
                [
                    f"RULE {ordinal:02d} · {rule.content}",
                    f"  SUPPORT · {support or 'none'}",
                    f"  BOUNDARY · {boundary or 'none'}",
                    f"  GOAL · {'YES' if rule.goal_support else 'NO'}",
                    f"  WHY · {rule.rationale}",
                    "",
                ]
            )
        lines.append("N · NEXT PAGE" if page_index + 1 < page_count else "N · VERIFY AND APPLY TO TEMPORARY RESULT")
        pages.append(lines)
    return pages


def _print_result_page(lines: list[str], *, page: int, total: int) -> None:
    _clear()
    for index, line in enumerate(lines):
        if index == 0 or line.startswith("RULE "):
            _heading(line)
        elif line.startswith("  SUPPORT") or line.startswith("  BOUNDARY"):
            print(_memory(line))
        else:
            print(line)
    print(f"READY RULE PAGE {page}/{total}", flush=True)


def _write_evidence(result, receipt, *, unchanged: bool) -> None:
    analysis = result.analysis
    alias_by_uid = {
        source.memory_uid: source.alias for source in analysis.source.sources
    }
    data = {
        "evaluation": "ticker-example Distill",
        "provider": {
            "name": "codex_chatgpt",
            "model": MODEL,
            "reasoning_effort": REASONING,
        },
        "source": {
            "context": SOURCE_NAME,
            "scope": "DIRECT",
            "cases": list(CASES),
            "unchanged": unchanged,
        },
        "goal": GOAL,
        "analysis": {
            "uid": analysis.uid,
            "digest": analysis.digest,
            "overview": analysis.overview,
            "rules": [
                {
                    "content": rule.content,
                    "goal_support": rule.goal_support,
                    "support": [alias_by_uid[uid] for uid in rule.support_memory_uids],
                    "boundary": [alias_by_uid[uid] for uid in rule.boundary_memory_uids],
                    "rationale": rule.rationale,
                }
                for rule in analysis.rules
            ],
            "outside": [alias_by_uid[uid] for uid in analysis.outside_memory_uids],
        },
        "temporary_apply": {
            "result_context": receipt.output_name,
            "rule_memory_count": len(receipt.result_memory_uids),
            "checkpoint_uid": receipt.checkpoint_uid,
        },
    }
    (OUT / "actual-run.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_child(store_root: Path) -> None:
    from memcommit.commands.distill.command import render_distill
    from memcommit.distill_application import DistillApplyRequest, DistillRequest
    from memcommit.distill_runtime import execute_distill, execute_distill_apply
    from memcommit.query_provider import CodexChatGPTProvider

    store, source = _prepare_store(store_root)
    before = source.to_dict()
    _input_page()
    if sys.stdin.readline().strip().lower() != "r":
        raise RuntimeError("Distill run was not approved by the capture driver.")

    _clear()
    _heading("MEM DISTILL · PROVIDER TURN")
    print(f"MODEL · {MODEL}")
    print(f"REASONING · {REASONING.upper()}")
    print("EXECUTION · WHOLE FRAME ONLY · 20/20 CASES IN ONE BOUNDED TURN")
    print("STATE · RUNNING · NO RESULT PUBLISHED", flush=True)

    provider = CodexChatGPTProvider.connect(
        model=MODEL,
        reasoning_effort=REASONING,
        timeout=300,
    )
    result = execute_distill(
        DistillRequest(context_locator=SOURCE_NAME, goal=GOAL),
        store=store,
        provider_factory=lambda: provider,
    )
    # Exercise the ordinary renderer as part of the captured run even though
    # the screenshots paginate it for a fixed terminal viewport.
    rendered = render_distill(result)
    if "STATUS · REVIEW ONLY · SOURCE UNCHANGED" not in rendered:
        raise RuntimeError("Distill renderer lost its read-only contract.")

    pages = _result_pages(result)
    for index, lines in enumerate(pages, 1):
        _print_result_page(lines, page=index, total=len(pages))
        if sys.stdin.readline().strip().lower() != "n":
            raise RuntimeError("Rule review pagination was interrupted.")

    receipt = execute_distill_apply(
        DistillApplyRequest(result=result, output_name=RESULT_NAME),
        store=store,
    )
    after = store.load_direct(SOURCE_NAME).to_dict()
    output = store.load_direct(RESULT_NAME)
    reviewed = tuple(rule.content for rule in result.analysis.rules)
    materialized = tuple(item.content for item in output.iter_items())
    accounted = {
        uid
        for rule in result.analysis.rules
        for uid in (*rule.support_memory_uids, *rule.boundary_memory_uids)
    } | set(result.analysis.outside_memory_uids)
    available = {item.memory_uid for item in result.analysis.source.sources}
    unchanged = before == after
    _write_evidence(result, receipt, unchanged=unchanged)

    _clear()
    _heading("MEM DISTILL · TICKER EVALUATION VERIFICATION")
    print(f"PROVIDER · CODEX CHATGPT · {MODEL} · REASONING {REASONING.upper()}")
    print(f"SOURCE · {SOURCE_NAME}")
    print(f"SOURCE CASES · {len(CASES)}")
    print(f"DISTILLED RULES · {len(result.analysis.rules)}")
    print(f"EXPLICITLY OUTSIDE · {len(result.analysis.outside_memory_uids)}")
    print(f"EVIDENCE ACCOUNTING · {len(accounted)}/{len(available)} · COMPLETE {accounted == available}")
    print(f"SOURCE BYTE-LOGICAL RECORD UNCHANGED · {unchanged}")
    print(f"TEMPORARY RESULT · {RESULT_NAME}")
    print(f"RESULT MEMORIES · {len(materialized)}")
    print(f"RESULT EXACTLY MATCHES REVIEWED RULES · {materialized == reviewed}")
    print(f"CHECKPOINT · {receipt.checkpoint_uid}")
    print("DURABLE USER PROFILE MUTATION · NONE (TEMPORARY STORE REMOVED)")
    print("EVIDENCE · docs/screenshots/mem-distill-ticker-20260815/actual-run.json")
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


def _settle(child: pexpect.spawn, *, seconds: float = 0.35) -> None:
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
    with tempfile.TemporaryDirectory(prefix="memcommit-distill-ticker-") as directory:
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
            child.expect("RUN ACTUAL DISTILL")
            _settle(child)
            _snapshot(recorder, "01-source-context-and-goal")

            child.sendline("r")
            child.expect("STATE .* RUNNING .* NO RESULT PUBLISHED")
            _settle(child, seconds=0.15)
            _snapshot(recorder, "02-provider-turn-running")

            child.expect(r"READY RULE PAGE (\d+)/(\d+)")
            total = int(child.match.group(2))
            for page in range(1, total + 1):
                if page > 1:
                    child.expect(fr"READY RULE PAGE {page}/{total}")
                _settle(child)
                _snapshot(recorder, f"{page + 2:02d}-reviewed-rules-page-{page:02d}")
                child.sendline("n")

            child.expect("READY VERIFICATION")
            child.expect(pexpect.EOF)
            _snapshot(recorder, f"{total + 3:02d}-verification")
        finally:
            if child.isalive():
                child.close(force=True)

    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[2]))
    else:
        main()
