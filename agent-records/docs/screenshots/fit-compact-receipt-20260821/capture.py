"""Capture Fit's compact receipt route in a real 180×52 PTY."""

from __future__ import annotations

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
BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
ROWS = 52
COLUMNS = 180

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_module("fit_compact_receipt_capture_base", BASE_PATH)
BASE.OUT = OUT


class _Provider:
    calls = 0

    def __init__(self, *, delay: float = 0.0, verdict: str = "YES") -> None:
        self.delay = delay
        self.verdict = verdict

    def complete(self, prompt, *, operation, output_schema=None):
        from memcommit.fit_judgment import FIT_JUDGMENT_PAYLOAD_MARKER

        type(self).calls += 1
        assert operation == "fit_propositions"
        if self.delay:
            time.sleep(self.delay)
        payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
        question = payload["questions"][0]
        aliases = [
            item["proposition_id"]
            for item in (*question["background"], *question["propositions"])
        ]
        yes = self.verdict == "YES"
        return json.dumps(
            {
                "overview": (
                    "The complete proposition set can jointly hold."
                    if yes
                    else "The two propositions cannot jointly hold."
                ),
                "judgments": [
                    {
                        "question_id": "fit",
                        "verdict": self.verdict,
                        "reason": (
                            "The lobby closure and side-entrance access can "
                            "jointly hold."
                            if yes
                            else "The same entrance cannot be closed and open "
                            "through the same period."
                        ),
                        "considered_proposition_ids": aliases,
                        "material_proposition_ids": [] if yes else aliases,
                        "consistent_reading": "",
                        "inconsistent_reading": "",
                    }
                ],
            }
        )


def _use_store_root(root: Path) -> None:
    import memcommit.store as store_module

    store_module.STORE_DIR = root


def _ground_result(*, current: bool):
    from memcommit.fit import FitExample, FitJudgment, FitReport, FitRule
    from memcommit.fit_application import FitResult

    rule_uid = "11111111-1111-1111-1111-111111111111"
    fit_uid = "22222222-2222-2222-2222-222222222222"
    may_uid = "33333333-3333-3333-3333-333333333333"
    no_uid = "44444444-4444-4444-4444-444444444444"
    report = FitReport(
        uid="00000000-0000-0000-0000-000000000005",
        ground_uid="00000000-0000-0000-0000-000000000006",
        ground_name="ticker",
        ground_revision=7,
        ground_digest="a" * 64,
        rules=(FitRule(rule_uid, "r1", "Use one stable abbreviation."),),
        examples=(
            FitExample(
                fit_uid,
                "e1",
                "Apple Inc. may be represented as AAPL.",
                "PROPOSITION",
                (rule_uid,),
            ),
            FitExample(
                may_uid,
                "e2",
                "Axiom AI Technologies may be AAT or AAIT.",
                "PROPOSITION",
                (rule_uid,),
            ),
            FitExample(
                no_uid,
                "e3",
                "One exact symbol must be both AAT and AXAI.",
                "PROPOSITION",
                (rule_uid,),
            ),
        ),
        judgments=(
            FitJudgment(
                fit_uid,
                "FIT",
                (rule_uid,),
                "The abbreviation follows the Rule.",
                "AAPL",
            ),
            FitJudgment(
                may_uid,
                "UNDERDETERMINED",
                (rule_uid,),
                "The Rule does not choose between the two abbreviations.",
                "AAT or AAIT",
            ),
            FitJudgment(
                no_uid,
                "CONTRADICTS",
                (rule_uid,),
                "One exact symbol cannot have both values.",
                "AAT and AXAI",
            ),
        ),
        overview="One passes, one is conditional, and one conflicts.",
        created_at="2026-08-21T12:00:00Z",
    )
    return FitResult(report, current)


def _gate() -> None:
    print("CAPTURE GATE · PRESS V", flush=True)
    sys.stdin.read(1)


def _run_general_child() -> None:
    import memcommit.commands.fit.command as fit_command

    _Provider.calls = 0
    fit_command.connect_semantic_provider = lambda: _Provider(delay=0.8)
    print(
        '$ mem fit "The lobby closes at five." '
        '"Visitors may use the side entrance after five."',
        flush=True,
    )
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    fit_command.cmd(
        [
            "The lobby closes at five.",
            "Visitors may use the side entrance after five.",
        ],
        background=None,
        memory_sources=None,
        context_sources=None,
        ground_name=None,
        receipt=None,
        plain=False,
    )
    print("RECEIPT COMPLETE · VIEWER ROUTE ABSENT")
    print(f"PROVIDER CALLS · {_Provider.calls}")
    print("DURABLE WRITES · 0")
    _gate()


def _run_general_no_child() -> None:
    import memcommit.commands.fit.command as fit_command

    _Provider.calls = 0
    fit_command.connect_semantic_provider = lambda: _Provider(verdict="NO")
    print(
        '$ mem fit "The main entrance closes from five until ten." '
        '"The main entrance stays open until ten."',
        flush=True,
    )
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    fit_command.cmd(
        [
            "The main entrance closes from five until ten.",
            "The main entrance stays open until ten.",
        ],
        background=None,
        memory_sources=None,
        context_sources=None,
        ground_name=None,
        receipt=None,
        plain=False,
    )
    print("RELATION SIDES · p1 ↔ p2")
    print(f"PROVIDER CALLS · {_Provider.calls}")
    print("DURABLE WRITES · 0")
    _gate()


def _run_ground_projection_child(*, current: bool) -> None:
    from memcommit.adapters.interfaces.cli.fit import render_fit_plain

    command = (
        "$ mem fit --ground ticker"
        if current
        else "$ mem fit --ground ticker --receipt 00000000-0000-0000-0000-000000000005"
    )
    print(command)
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    render_fit_plain(_ground_result(current=current))
    print("FITTING EXAMPLE e1 EXPANDED · NO")
    print("PROJECTION FIXTURE DURABLE WRITES · 0")
    _gate()


def _prepare_overlap_store(root: Path):
    import memcommit.application.ops as ops
    from memcommit.store import MemoryStore, context_record_digest

    store = MemoryStore(root=root)
    current = ops.init("fit/current")
    selected = ops.add(current, "The lobby closes at five.")
    store.create_context(current)
    store.set_current(current.name)
    return store, current, selected, context_record_digest(current)


def _run_overlap_child(store_root: Path) -> None:
    import memcommit.commands.fit.command as fit_command
    from memcommit.fit_store import FitStore
    from memcommit.store import context_record_digest

    _Provider.calls = 0
    _use_store_root(store_root)
    store, current, selected, before_digest = _prepare_overlap_store(store_root)

    fit_command.connect_semantic_provider = _Provider
    print(f"$ mem fit {selected.uid[:8]} {current.name}")
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    fit_command.cmd(
        [selected.uid[:8], current.name],
        background=None,
        memory_sources=None,
        context_sources=None,
        ground_name=None,
        receipt=None,
        plain=False,
    )
    print("REPEATED COORDINATE · TWO OPERATOR OPERANDS · READ-ONLY VERIFICATION")
    print(
        "  CURRENT UNCHANGED · "
        f"{context_record_digest(store.load_direct(current.name)) == before_digest}"
    )
    print(f"  PROVIDER CALLS · {_Provider.calls}")
    print(f"  FIT RECEIPTS · {len(FitStore(store).list())}")
    _gate()


def _run_three_operands_child(store_root: Path) -> None:
    import memcommit.commands.fit.command as fit_command
    import memcommit.application.ops as ops
    from memcommit.fit_store import FitStore
    from memcommit.store import MemoryStore

    _Provider.calls = 0
    _use_store_root(store_root)
    store = MemoryStore(root=store_root)
    contexts = []
    for name, content in (
        ("context-a", "Claim from Context A."),
        ("context-b", "Claim from Context B."),
        ("context-c", "Claim from Context C."),
    ):
        context = ops.init(name)
        ops.add(context, content)
        store.create_context(context)
        contexts.append(context)
    store.set_current(contexts[0].name)
    fit_command.connect_semantic_provider = _Provider
    print("$ mem fit context-a context-b context-c")
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    fit_command.cmd(
        [context.name for context in contexts],
        background=None,
        memory_sources=None,
        context_sources=None,
        ground_name=None,
        receipt=None,
        plain=False,
    )
    print("OPERATOR OPERANDS · 3")
    print(f"PROVIDER CALLS · {_Provider.calls}")
    print(f"FIT RECEIPTS · {len(FitStore(store).list())}")
    _gate()


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


def _spawn(kind: str, store_root: Path):
    recorder = BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture(kind: str, store_root: Path, stem: str, *, running=False) -> None:
    child, recorder = _spawn(kind, store_root)
    try:
        if running:
            BASE._settle(child, seconds=0.3)
            BASE._snapshot(recorder, "01-provider-running")
        child.expect("CAPTURE GATE")
        BASE._settle(child, seconds=0.15)
        BASE._snapshot(recorder, stem)
        child.send("v\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    from memcommit.adapters.interfaces.console.theme import (
        SemanticColorRole,
        semantic_color_rgb,
    )

    def styled_judgment(label: str, role: SemanticColorRole) -> str:
        red, green, blue = semantic_color_rgb(role)
        return f"\x1b[38;2;{red};{green};{blue}m\x1b[1m{label}\x1b[0m"

    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "txt", "typescript"):
        (OUT / f"05-overlap-blocked-before-provider.{suffix}").unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-fit-receipt-") as directory:
        root = Path(directory)
        _capture("general", root / "general", "02-yes-receipt", running=True)
        _capture("issues", root / "issues", "03-issue-only-ground-receipt")
        _capture("stale", root / "stale", "04-stale-summary-only")
        _capture("overlap", root / "overlap", "05-repeated-operands-fit-yes")
        _capture("general-no", root / "general-no", "06-general-no-relation-receipt")
        _capture("three", root / "three", "07-three-context-operands")
    canvases = {
        path.name: path.read_text(encoding="utf-8") for path in OUT.glob("*.txt")
    }
    streams = {
        path.name: path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    }
    if not canvases or any("PTY · 180×52" not in text for text in canvases.values()):
        raise RuntimeError("A Fit receipt capture did not retain the 180×52 PTY.")
    if (
        "FIT · YES · [TARGETS: PROPOSITION p1, p2]"
        not in canvases["02-yes-receipt.txt"]
    ):
        raise RuntimeError("The compact YES receipt was not captured.")
    if (
        styled_judgment("YES", SemanticColorRole.JUDGMENT_YES)
        not in streams["02-yes-receipt.typescript"]
    ):
        raise RuntimeError("The shared green YES token was not captured.")
    issue_text = canvases["03-issue-only-ground-receipt.txt"]
    if "FIT · NO · [TARGETS: GROUND ticker] · 1/3" not in issue_text:
        raise RuntimeError("The whole Ground verdict was not captured.")
    if "? MAY" not in issue_text or "! NO" not in issue_text:
        raise RuntimeError("The issue-only Ground receipt was not captured.")
    issue_stream = streams["03-issue-only-ground-receipt.typescript"]
    if (
        styled_judgment("MAY", SemanticColorRole.JUDGMENT_MAY) not in issue_stream
        or styled_judgment("NO", SemanticColorRole.JUDGMENT_NO) not in issue_stream
    ):
        raise RuntimeError("The shared MAY/NO judgment colors were not captured.")
    if "[RULE r1] [MEMORY 11111111]" not in issue_text or (
        "↔ [EXAMPLE e3] [MEMORY 44444444]" not in issue_text
    ):
        raise RuntimeError("The Ground issue receipt omitted one relation side.")
    repeated_text = canvases["05-repeated-operands-fit-yes.txt"]
    if "[TARGETS: CONTEXT fit/current, MEMORY " not in repeated_text:
        raise RuntimeError("The mixed Fit target groups were not captured.")
    no_text = canvases["06-general-no-relation-receipt.txt"]
    if "FIT · NO · [TARGETS: PROPOSITION p1, p2]" not in no_text:
        raise RuntimeError("The general NO target summary was not captured.")
    if (
        styled_judgment("NO", SemanticColorRole.JUDGMENT_NO)
        not in streams["06-general-no-relation-receipt.typescript"]
    ):
        raise RuntimeError("The shared red NO token was not captured.")
    stale_stream = streams["04-stale-summary-only.typescript"]
    if "STALE" not in stale_stream or "\x1b[" in stale_stream:
        raise RuntimeError("The STALE receipt must remain neutral and ANSI-free.")
    three_text = canvases["07-three-context-operands.txt"]
    if "[TARGETS: CONTEXT context-a, context-b, context-c]" not in three_text:
        raise RuntimeError("The three-Context target summary was not captured.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        root = Path(sys.argv[3])
        if kind == "general":
            _run_general_child()
        elif kind == "general-no":
            _run_general_no_child()
        elif kind == "issues":
            _run_ground_projection_child(current=True)
        elif kind == "stale":
            _run_ground_projection_child(current=False)
        elif kind == "overlap":
            _run_overlap_child(root)
        elif kind == "three":
            _run_three_operands_child(root)
        else:
            raise RuntimeError(f"Unknown capture kind: {kind}")
    else:
        main()
