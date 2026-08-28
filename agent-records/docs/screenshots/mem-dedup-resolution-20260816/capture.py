"""Capture the complete semantic Dedun flow in a real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/docs/screenshots/mem-dedup-resolution-20260816"
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
_SPEC = importlib.util.spec_from_file_location("dedup_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS

QUALITY_MARKER = "QUALITY FIND PAYLOAD:\n"


def _configure_isolated_store(store_root: Path) -> None:
    import memcommit.persistence.store as store_module

    values = {
        "STORE_DIR": store_root,
        "CONTEXTS_DIR": store_root / "contexts",
        "QUERY_SOURCES_DIR": store_root / "query-sources",
        "STATE_FILE": store_root / "state.json",
        "IMPACT_PLAN_FILE": store_root / "impact-plan.json",
        "STAGED_UPDATE_FILE": store_root / "staged-update.json",
        "REVIEW_SESSION_FILE": store_root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": store_root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": store_root / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": store_root / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": store_root / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": store_root / "ground-sessions",
        "MELD_SESSIONS_DIR": store_root / "meld-sessions",
    }
    for name, value in values.items():
        setattr(store_module, name, value)


def _initialize(*, inbound: bool) -> None:
    from memcommit.core.context import Context, Memory, MemoryRef
    from memcommit.persistence.store import MemoryStore

    context = Context(
        uid="10000000-0000-4000-8000-000000000100",
        name="dedup/capture",
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000100",
            content="The office opens at eight on weekdays.",
        )
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000200",
            content="The weekday office opening time is 08:00.",
        )
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000300",
            content="The office closes at 17:00 on weekdays.",
        )
    )
    store = MemoryStore()
    store.create_context(context)
    store.set_current(context.name)
    if inbound:
        observer = Context(
            uid="10000000-0000-4000-8000-000000000200",
            name="dedup/observer",
        )
        observer.add(
            MemoryRef(
                uid="30000000-0000-4000-8000-000000000100",
                target_context_uid=context.uid,
                target_context_name=context.name,
                target_memory_uid="20000000-0000-4000-8000-000000000200",
            )
        )
        store.create_context(observer)


class _Provider:
    def __init__(self) -> None:
        self.operations: list[str] = []

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        assert output_schema is not None
        self.operations.append(operation)
        if operation != "find_duplicates":
            raise AssertionError(operation)
        payload = json.loads(prompt.split(QUALITY_MARKER, 1)[1])
        candidate_by_content = {
            item["content"]: item["candidate_id"] for item in payload["memories"]
        }
        return json.dumps(
            {
                "findings": [
                    {
                        "candidate_ids": [
                            candidate_by_content[
                                "The office opens at eight on weekdays."
                            ],
                            candidate_by_content[
                                "The weekday office opening time is 08:00."
                            ],
                        ],
                        "relation": "SEMANTIC_EQUIVALENT",
                        "reason": (
                            "Both Memories state the same weekday opening time "
                            "without adding a distinct condition."
                        ),
                    }
                ]
            }
        )


def _verification(kind: str, provider: _Provider) -> str:
    from memcommit.core.context import Memory
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    context = store.load_direct("dedup/capture")
    memories = [
        (item.uid, item.content)
        for item in context.iter_items()
        if isinstance(item, Memory)
    ]
    checkpoints = store.list_checkpoints(context.name)
    commands = [checkpoint["command"] for checkpoint in checkpoints]
    return (
        f"{kind.upper()} VERIFICATION · MEMORIES {memories!r} · "
        f"CHECKPOINTS {len(checkpoints)} · COMMANDS {commands!r} · "
        f"PROVIDER OPERATIONS {provider.operations!r}"
    )


def _pause(label: str) -> None:
    print(label, flush=True)
    sys.stdin.readline()


def _run_child(kind: str) -> None:
    import click

    import memcommit.adapters.console.commands.find_duplicates.command as find_command
    import memcommit.application.capabilities.ops as ops
    from memcommit.adapters.console.entrypoint import app
    from memcommit.persistence.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="dedup-resolution-capture-") as directory:
        _configure_isolated_store(Path(directory) / ".mem")
        _initialize(inbound=kind == "inbound")
        provider = _Provider()
        find_command.connect_codex_chatgpt_provider = lambda: provider
        if kind == "stale":
            original_handoff = find_command.run_dedun_resolution

            def stale_handoff(store, *, current_name, handoffs):
                changed = store.load_for_update("dedup/capture")
                ops.add(changed, "A concurrent holiday schedule arrived.")
                store.save(changed, expected_context_digest=changed._store_digest)
                return original_handoff(
                    store,
                    current_name=current_name,
                    handoffs=handoffs,
                )

            find_command.run_dedun_resolution = stale_handoff

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        exit_code = 0
        try:
            returned = app(
                args=["dedun"],
                prog_name="mem",
                standalone_mode=False,
            )
        except click.exceptions.Exit as error:
            exit_code = error.exit_code
        else:
            if isinstance(returned, int):
                exit_code = returned
        print(f"COMMAND EXIT · {exit_code}")
        if kind == "success" and exit_code == 0:
            [checkpoint] = MemoryStore().list_checkpoints("dedup/capture")
            print("POST-APPLICATION REVIEW · PROVIDER FREE", flush=True)
            app(
                args=[
                    "review",
                    "dedun",
                    "--receipt",
                    checkpoint["uid"],
                    "--snapshot",
                ],
                prog_name="mem",
                standalone_mode=False,
            )
        _pause(_verification(kind, provider))


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
        timeout=25,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _enter_finder(child: pexpect.spawn) -> None:
    child.expect("MEM DEDUN · SETUP")
    _BASE._settle(child)
    child.send("\t\t\r")
    child.expect("PROCESS LOCAL")
    _BASE._settle(child, seconds=0.8)


def _confirm_and_handoff(child: pexpect.spawn) -> None:
    child.send("\t\x1b[B\r")
    _BASE._settle(child)
    child.send("\t\r")
    _BASE._settle(child)
    child.send("\t\t\r")


def _select_survivor_and_review(child: pexpect.spawn) -> None:
    child.expect("MEM DEDUN · RESOLUTION SESSION")
    _BASE._settle(child, seconds=0.8)
    # The recommendation is already a complete operation decision. Move from
    # Items to To Do and open the exact Apply confirmation; no Viewer exists.
    child.send("\t\r")
    _BASE._settle(child)


def _capture_success() -> None:
    child, recorder = _spawn("success")
    try:
        child.expect("MEM DEDUN · SETUP")
        _BASE._settle(child)
        _snapshot(recorder, "01-finder-setup-entry")
        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "02-finder-scope")
        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "03-finder-run-approval")
        child.send("\r")
        child.expect("PROCESS LOCAL")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "04-duplicate-report")
        child.send("\t\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "05-duplicate-item")
        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "06-duplicate-detail")
        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "07-finder-responses")
        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "08-link-confirmed")
        child.send("\t\t")
        _BASE._settle(child)
        _snapshot(recorder, "09-dedup-handoff")
        child.send("\r")
        child.expect("MEM DEDUN · RESOLUTION SESSION")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "10-dedup-plan-entry")
        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "11-component-detail")
        child.send("\x1b[B\r")
        _BASE._settle(child)
        _snapshot(recorder, "12-survivor-responses")
        child.send("\x1b[A\r")
        _BASE._settle(child)
        _snapshot(recorder, "13-survivor-selected")
        child.send("\t\t")
        _BASE._settle(child)
        _snapshot(recorder, "14-ready-for-review")
        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "15-exact-apply-review")
        child.send("\r")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "16-success-receipt")
        child.send("\r")
        child.expect("SUCCESS VERIFICATION")
        _BASE._settle(child)
        _snapshot(recorder, "17-read-only-store-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_stale() -> None:
    child, recorder = _spawn("stale")
    try:
        _enter_finder(child)
        _confirm_and_handoff(child)
        child.expect("Dedun error")
        child.expect("STALE VERIFICATION")
        _BASE._settle(child)
        _snapshot(recorder, "18-stale-source-rejected")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_inbound() -> None:
    child, recorder = _spawn("inbound")
    try:
        _enter_finder(child)
        _confirm_and_handoff(child)
        _select_survivor_and_review(child)
        child.send("\r")
        _BASE._settle(child, seconds=1.0)
        _snapshot(recorder, "19-inbound-reference-blocked")
        child.send("q")
        child.expect("INBOUND VERIFICATION")
        _snapshot(recorder, "20-inbound-no-checkpoint-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_success()
    _capture_stale()
    _capture_inbound()
    assert "STATUS · SUCCESS" in (
        OUT / "16-success-receipt.txt"
    ).read_text(encoding="utf-8")
    success = (OUT / "17-read-only-store-verification.txt").read_text(
        encoding="utf-8"
    )
    assert "CHECKPOINTS 1" in success
    assert "COMMANDS ['dedun']" in success
    assert "MEM REVIEW · DEDUN" in success
    assert "POST-APPLICATION REVIEW · PROVIDER FREE" in success
    stale = (OUT / "18-stale-source-rejected.txt").read_text(encoding="utf-8")
    assert "Source changed" in stale
    assert "CHECKPOINTS 0" in stale
    inbound = (OUT / "20-inbound-no-checkpoint-verification.txt").read_text(
        encoding="utf-8"
    )
    assert "CHECKPOINTS 0" in inbound
    assert "00000200" in inbound
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(sys.argv[2])
    else:
        main()
