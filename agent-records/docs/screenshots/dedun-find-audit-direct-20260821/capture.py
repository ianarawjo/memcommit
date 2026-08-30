"""Capture direct Dedun, quality Find, and Audit receipts in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/dedun-find-audit-direct-20260821"
COLUMNS = 180
ROWS = 52
QUALITY_MARKER = "QUALITY FIND PAYLOAD:\n"
_SGR_PATTERN = re.compile(r"\x1b\[[0-9;]*m")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

_SUPPORT_PATH = (
    ROOT
    / "agent-records/docs/screenshots/quality-conflict-resolve-handoff-20260816/capture.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "direct_receipt_capture_support",
    _SUPPORT_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_SUPPORT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SUPPORT)
_BASE = _SUPPORT._BASE
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _initialize(
    context_name: str,
    *,
    redundant: bool,
    audit_preview: bool = False,
) -> None:
    from memcommit.core.context import Context, Memory
    from memcommit.persistence.store import MemoryStore

    context = Context(
        uid=(
            "10000000-0000-4000-8000-000000000310"
            if redundant
            else "10000000-0000-4000-8000-000000000320"
        ),
        name=context_name,
    )
    contents = (
        (
            "The parking garage is unavailable after 10 p.m.",
            "Do not enter the parking garage after 22:00.",
            "Emergency exits remain unlocked.",
        )
        if redundant
        else (
            "The main entrance opens at 08:00 every day.",
            "The main entrance remains closed until 09:00 every day.",
            "The main entrance opens at 07:00 every day.",
        )
    )
    if audit_preview:
        contents += ("The main entrance remains closed until 10:00 every day.",)
    suffix = 310 if redundant else 320
    for offset, content in enumerate(contents):
        context.add(
            Memory(
                uid=(
                    f"{20_000_000 + offset:08d}-0000-4000-8000-"
                    f"000000000{suffix + offset}"
                ),
                content=content,
            )
        )
    store = MemoryStore()
    store.create_context(context)
    store.set_current(context.name)


def _initialize_exact_duplicates(context_name: str) -> None:
    from memcommit.core.context import Context, Memory
    from memcommit.persistence.store import MemoryStore

    context = Context(
        uid="10000000-0000-4000-8000-000000000330",
        name=context_name,
    )
    for offset, content in enumerate(
        (
            "Badge access is required.",
            "Badge access is required.",
            "The lobby opens at eight.",
        )
    ):
        context.add(
            Memory(
                uid=(
                    f"{30_000_000 + offset:08d}-0000-4000-8000-000000000{330 + offset}"
                ),
                content=content,
            )
        )
    store = MemoryStore()
    store.create_context(context)
    store.set_current(context.name)


class _Provider:
    def __init__(
        self,
        *,
        redundant: bool,
        delay: float = 0.8,
        audit_findings: bool = False,
    ) -> None:
        from memcommit.providers.types import ProviderIdentity

        self.identity = ProviderIdentity(
            provider="capture",
            model="deterministic-quality-receipt",
        )
        self.last_run = None
        self.redundant = redundant
        self.delay = delay
        self.audit_findings = audit_findings
        self.operations: list[str] = []

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        from memcommit.providers.types import CompletionRun

        assert output_schema is not None
        self.operations.append(operation)
        time.sleep(self.delay)
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            upstream_model=self.identity.model,
            upstream_provider=self.identity.provider,
        )
        if operation == "find_duplicates" and self.redundant:
            payload = json.loads(prompt.split(QUALITY_MARKER, 1)[1])
            candidate_ids = [item["candidate_id"] for item in payload["memories"][:2]]
            return json.dumps(
                {
                    "findings": [
                        {
                            "candidate_ids": candidate_ids,
                            "relation": "SEMANTIC_EQUIVALENT",
                            "reason": (
                                "Both Memories prohibit garage access after "
                                "the same 10 p.m. boundary."
                            ),
                        }
                    ]
                }
            )
        if operation == "find_ambiguities" and self.audit_findings:
            payload = json.loads(prompt.split(QUALITY_MARKER, 1)[1])
            return json.dumps(
                {
                    "findings": [
                        {
                            "candidate_id": candidate["candidate_id"],
                            "interpretation": "SINGLE",
                            "clarification": "REQUIRED",
                            "ordinary_readings": [candidate["content"]],
                            "reason": "The schedule does not identify its time zone.",
                            "question": "Which time zone governs this schedule?",
                        }
                        for candidate in (
                            payload["memories"][0],
                            payload["memories"][2],
                        )
                    ]
                }
            )
        if operation == "find_conflicts" and self.audit_findings:
            payload = json.loads(prompt.split(QUALITY_MARKER, 1)[1])
            return json.dumps(
                {
                    "findings": [
                        {
                            "pair_id": pair["pair_id"],
                            "conflict": "YES",
                            "reason": "The two statements prescribe different schedules.",
                            "question": "Which schedule should govern?",
                        }
                        for pair in (
                            payload["pairs"][0],
                            payload["pairs"][2],
                            payload["pairs"][3],
                            payload["pairs"][5],
                        )
                    ]
                }
            )
        return '{"findings": []}'


def _run_app(args: list[str]) -> int:
    import click

    from memcommit.adapters.console.entrypoint import app

    try:
        returned = app(args=args, prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        return error.exit_code
    return returned if isinstance(returned, int) else 0


def _verification(context_name: str, provider: _Provider) -> str:
    from memcommit.core.context import Memory
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    context = store.load_direct(context_name)
    memory_count = sum(isinstance(item, Memory) for item in context.iter_items())
    commands = [
        checkpoint["command"] for checkpoint in store.list_checkpoints(context.name)
    ]
    return (
        f"VERIFICATION · CONTEXT {context.name} · MEMORIES {memory_count} · "
        f"CHECKPOINT COMMANDS {commands!r} · CURRENT "
        f"{store.current_context_name()} · PROVIDER {provider.operations!r}"
    )


def _pause(label: str) -> None:
    print(label, flush=True)
    sys.stdin.readline()


def _show_verification(context_name: str, provider: _Provider, label: str) -> None:
    """Put the harness's final read-only check on its own terminal canvas."""

    print("\x1b[2J\x1b[H", end="")
    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    print(_verification(context_name, provider))
    _pause(label)


def _run_dedun_child(*, no_change: bool) -> None:
    import memcommit.adapters.console.commands.find_redundancies.command as find_command
    from memcommit.persistence.store import MemoryStore

    context_name = "quality/no-change" if no_change else "quality/direct-dedun"
    with tempfile.TemporaryDirectory(prefix="direct-dedun-capture-") as directory:
        _SUPPORT._configure_isolated_store(Path(directory) / ".mem")
        _initialize(context_name, redundant=not no_change)
        provider = _Provider(redundant=not no_change)
        find_command.connect_codex_chatgpt_provider = lambda: provider
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        exit_code = _run_app(["dedun"])
        print(f"COMMAND EXIT · {exit_code}")
        print(_verification(context_name, provider))
        if no_change:
            _pause("DEDUN NO-CHANGE READY")
            return
        store = MemoryStore()
        receipt_uid = store.list_checkpoints(context_name)[0]["uid"]
        _pause("DEDUN RECEIPT READY")
        review_exit = _run_app(
            ["review", "dedun", "--receipt", receipt_uid, "--snapshot"]
        )
        print(f"REVIEW EXIT · {review_exit}")
        print(_verification(context_name, provider))
        _pause("DEDUN REVIEW READY")
        interactive_review_exit = _run_app(
            ["review", "dedun", "--receipt", receipt_uid]
        )
        print(f"INTERACTIVE REVIEW EXIT · {interactive_review_exit}")
        print(_verification(context_name, provider))
        _pause("DEDUN INTERACTIVE REVIEW CLOSED")
        _show_verification(context_name, provider, "DEDUN VERIFICATION READY")


def _run_find_child() -> None:
    import memcommit.adapters.console.commands.find_redundancies.command as find_command

    context_name = "quality/direct-find"
    with tempfile.TemporaryDirectory(prefix="direct-find-capture-") as directory:
        _SUPPORT._configure_isolated_store(Path(directory) / ".mem")
        _initialize(context_name, redundant=True)
        provider = _Provider(redundant=True)
        find_command.connect_codex_chatgpt_provider = lambda: provider
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        exit_code = _run_app(["find-redundancies"])
        print(f"COMMAND EXIT · {exit_code}")
        print(_verification(context_name, provider))
        _pause("FIND REPORT READY")


def _run_find_exact_child() -> None:
    context_name = "quality/direct-find-exact"
    with tempfile.TemporaryDirectory(prefix="direct-find-exact-capture-") as directory:
        _SUPPORT._configure_isolated_store(Path(directory) / ".mem")
        _initialize_exact_duplicates(context_name)
        provider = _Provider(redundant=False, delay=0)
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        exit_code = _run_app(["find-duplicates"])
        print(f"COMMAND EXIT · {exit_code}")
        print(_verification(context_name, provider))
        _pause("FIND EXACT REPORT READY")


def _run_audit_child() -> None:
    import memcommit.adapters.console.commands.audit.command as audit_command
    from memcommit.application.operations.audit.session_store import QualityAuditStore
    from memcommit.persistence.store import MemoryStore

    context_name = "quality/direct-audit"
    with tempfile.TemporaryDirectory(prefix="direct-audit-capture-") as directory:
        _SUPPORT._configure_isolated_store(Path(directory) / ".mem")
        _initialize(context_name, redundant=False, audit_preview=True)
        provider = _Provider(
            redundant=False,
            delay=1.0,
            audit_findings=True,
        )
        audit_command.connect_codex_chatgpt_provider = lambda: provider
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        exit_code = _run_app(["audit"])
        print(f"COMMAND EXIT · {exit_code}")
        print(_verification(context_name, provider))
        session = QualityAuditStore(MemoryStore()).list()[0]
        _pause("AUDIT RECEIPT READY")
        review_exit = _run_app(
            ["review", "audit", "--session", session.uid, "--snapshot"]
        )
        print(f"REVIEW EXIT · {review_exit}")
        print(_verification(context_name, provider))
        _pause("AUDIT REVIEW READY")
        _show_verification(context_name, provider, "AUDIT VERIFICATION READY")


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(kind: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> str:
    _BASE._snapshot(recorder, stem)
    return (OUT / f"{stem}.txt").read_text(encoding="utf-8")


def _last_token_styles(stream: str, token: str) -> tuple[str, ...]:
    """Return SGRs active for the last rendered instance of one token."""

    token_offset = stream.rfind(token)
    assert token_offset >= 0, f"missing rendered token: {token}"
    matches = tuple(_SGR_PATTERN.finditer(stream, 0, token_offset))
    assert matches, f"missing ANSI style before rendered token: {token}"
    reset_offset = max(
        (index for index, match in enumerate(matches) if match.group() == "\x1b[0m"),
        default=-1,
    )
    return tuple(match.group() for match in matches[reset_offset + 1 :])


def _capture_dedun() -> None:
    child, recorder = _spawn("dedun")
    try:
        child.expect("MEM DEDUN · 1/1 · ANALYZING DIRECT MEMORIES")
        _BASE._settle(child, seconds=0.15)
        _snapshot(recorder, "01-dedun-direct-progress")
        child.expect("DEDUN RECEIPT READY")
        receipt = _snapshot(recorder, "02-dedun-applied-receipt")
        assert "absorbed 1 redundant direct item(s)" in receipt
        assert "mem review dedun --receipt" in receipt
        child.send("\r")
        child.expect("DEDUN REVIEW READY")
        review = _snapshot(recorder, "03-dedun-checkpoint-review")
        assert "STATUS · APPLIED" in review
        assert "SEMANTIC_EQUIVALENT" in review
        child.send("\r")
        child.expect("SURVIVOR")
        _BASE._settle(child, seconds=0.15)
        interactive_review = _snapshot(
            recorder,
            "03b-dedun-interactive-review",
        )
        assert "SURVIVOR" in interactive_review
        assert "ABSORB" in interactive_review
        child.send("q")
        child.expect("DEDUN INTERACTIVE REVIEW CLOSED")
        child.send("\r")
        child.expect("DEDUN VERIFICATION READY")
        final = _snapshot(recorder, "04-dedun-read-only-verification")
        assert "MEMORIES 2" in final
        assert "CHECKPOINT COMMANDS ['dedun']" in final
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_no_change() -> None:
    child, recorder = _spawn("no-change")
    try:
        child.expect("MEM DEDUN · 1/1 · ANALYZING DIRECT MEMORIES")
        _BASE._settle(child, seconds=0.15)
        _snapshot(recorder, "05-dedun-no-change-progress")
        child.expect("DEDUN NO-CHANGE READY")
        no_change = _snapshot(recorder, "06-dedun-no-change-receipt")
        assert "No redundancies" in no_change
        assert "CHECKPOINT COMMANDS []" in no_change
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_find() -> None:
    child, recorder = _spawn("find")
    try:
        child.expect("MEM FIND REDUNDANCIES · 1/1 · ANALYZING DIRECT MEMORIES")
        _BASE._settle(child, seconds=0.15)
        _snapshot(recorder, "07-find-direct-progress")
        child.expect("FIND REPORT READY")
        report = _snapshot(recorder, "08-find-read-only-report")
        assert "DUN GROUP  1/1 · 2 Memories · SEMANTIC DUN" in report
        assert "CLEANUP MAP · READY FOR REVIEW" in report
        assert "SURVIVOR" in report and "ABSORB" in report
        assert "FIRST" not in report and "LATER" not in report
        assert "LEFT" not in report and "RIGHT" not in report
        assert "CHECKPOINT COMMANDS []" in report
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_find_exact() -> None:
    child, recorder = _spawn("find-exact")
    try:
        child.expect("FIND EXACT REPORT READY")
        report = _snapshot(recorder, "08b-find-duplicates-exact-report")
        assert "1 exact group · 1 proposed absorption" in report
        assert "SHARED CONTENT" not in report
        assert "CLEANUP MAP" not in report
        assert report.count("Badge access is required.") == 2
        assert "SURVIVOR" in report and "ABSORB" in report
        assert "FIRST" not in report and "LATER" not in report
        assert "Apply exact cleanup with mem dedup" in report
        assert "CHECKPOINT COMMANDS []" in report
        assert "PROVIDER []" in report
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_audit() -> None:
    child, recorder = _spawn("audit")
    try:
        child.expect("MEM AUDIT · 1/3 · FINDING REDUNDANCIES")
        _BASE._settle(child, seconds=0.15)
        _snapshot(recorder, "09-audit-duplicates-progress")
        child.expect("MEM AUDIT · 2/3 · FINDING AMBIGUITIES")
        _BASE._settle(child, seconds=0.15)
        _snapshot(recorder, "10-audit-ambiguities-progress")
        child.expect("MEM AUDIT · 3/3 · FINDING CONFLICTS")
        _BASE._settle(child, seconds=0.15)
        _snapshot(recorder, "11-audit-conflicts-progress")
        child.expect("AUDIT RECEIPT READY")
        receipt = _snapshot(recorder, "12-audit-saved-receipt")
        assert "Audit saved: 3 quality checks" in receipt
        assert "Source: quality/direct-audit · 4 memories" in receipt
        assert "REDUNDANCIES   4 MEMORIES CHECKED · 0 GROUPS" in receipt
        assert "AMBIGUITIES    2/4 MEMORIES FLAGGED" in receipt
        assert "? UNDERSPECIFIED · [MEMORY 20000000]" in receipt
        assert "CONFLICTS      4/4 MEMORIES INVOLVED · 4/6 PAIRS FLAGGED" in receipt
        assert receipt.count("! CONFLICT · [MEMORY") == 3
        assert "… 1 more" in receipt
        assert "Review full audit:" in receipt
        assert "mem review audit --session" in receipt
        from memcommit.adapters.console.terminal.core.theme import (
            SemanticColorRole,
            memory_object_color_rgb,
            semantic_color_rgb,
        )

        stream = (OUT / "12-audit-saved-receipt.typescript").read_text(encoding="utf-8")
        for role, token in (
            (SemanticColorRole.QUALITY_DUPLICATE, "REDUNDANCIES"),
            (SemanticColorRole.QUALITY_AMBIGUITY, "AMBIGUITIES"),
            (SemanticColorRole.QUALITY_AMBIGUITY, "UNDERSPECIFIED"),
            (SemanticColorRole.QUALITY_CONFLICT, "CONFLICTS"),
            (SemanticColorRole.QUALITY_CONFLICT, "CONFLICT"),
        ):
            red, green, blue = semantic_color_rgb(role)
            expected_style = f"\x1b[38;2;{red};{green};{blue}m"
            assert expected_style in _last_token_styles(stream, token)
        memory_red, memory_green, memory_blue = memory_object_color_rgb()
        assert f"\x1b[38;2;{memory_red};{memory_green};{memory_blue}m" in stream
        child.send("\r")
        child.expect("AUDIT REVIEW READY")
        review = _snapshot(recorder, "13-audit-saved-review")
        assert "SAVED · 3/3 CHECKS" in review
        assert "SOURCE · quality/direct-audit · 4 direct Memories" in review
        assert "SNAPSHOT · [20000000]" in review
        assert "FROZEN SOURCE" not in review
        child.send("\r")
        child.expect("AUDIT VERIFICATION READY")
        final = _snapshot(recorder, "14-audit-read-only-verification")
        assert "MEMORIES 4" in final
        assert "CHECKPOINT COMMANDS []" in final
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_dedun()
    _capture_no_change()
    _capture_find()
    _capture_find_exact()
    _capture_audit()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    # These line-oriented routes intentionally have no focused-control
    # background. Verify their real green success and yellow semantic-result
    # foregrounds instead of requiring a TUI-only background sequence.
    assert "\x1b[32m" in raw
    assert "\x1b[33m" in raw
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.adapters.console.terminal.core.theme import (
        SemanticColorRole,
        semantic_color_rgb,
    )

    for role in (SemanticColorRole.ADD, SemanticColorRole.REMOVE):
        red, green, blue = semantic_color_rgb(role)
        code = f"\x1b[38;2;{red};{green};{blue}m"
        assert code in raw

    expected_styles = {}
    for role, token in (
        (SemanticColorRole.ADD, "SURVIVOR"),
        (SemanticColorRole.REMOVE, "ABSORB"),
    ):
        red, green, blue = semantic_color_rgb(role)
        expected_styles[token] = f"\x1b[38;2;{red};{green};{blue}m"
    for stem in (
        "03-dedun-checkpoint-review",
        "08-find-read-only-report",
        "08b-find-duplicates-exact-report",
    ):
        stream = (OUT / f"{stem}.typescript").read_text(encoding="utf-8")
        for token, expected_style in expected_styles.items():
            assert expected_style in _last_token_styles(stream, token)

    # prompt-toolkit may lower shared RGB values to terminal-palette indexes.
    # Verify the final Viewer render itself owns two distinct non-reset styles;
    # unit tests separately prove their impact.add/impact.remove classification.
    interactive_stream = (OUT / "03b-dedun-interactive-review.typescript").read_text(
        encoding="utf-8"
    )
    survivor_styles = _last_token_styles(interactive_stream, "SURVIVOR")
    absorb_styles = _last_token_styles(interactive_stream, "ABSORB")
    assert survivor_styles
    assert absorb_styles
    assert survivor_styles != absorb_styles


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        if sys.argv[2] == "dedun":
            _run_dedun_child(no_change=False)
        elif sys.argv[2] == "no-change":
            _run_dedun_child(no_change=True)
        elif sys.argv[2] == "find":
            _run_find_child()
        elif sys.argv[2] == "find-exact":
            _run_find_exact_child()
        elif sys.argv[2] == "audit":
            _run_audit_child()
        else:
            raise SystemExit(f"unknown child kind: {sys.argv[2]}")
    else:
        main()
