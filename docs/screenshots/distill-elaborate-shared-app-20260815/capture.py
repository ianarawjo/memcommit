"""Capture Distill and Elaborate over their shared application/TUI paths."""

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
DOWN = "\x1b[B"
RIGHT = "\x1b[C"
SHIFT_TAB = "\x1b[Z"
TAB = "\t"

BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
SPEC = importlib.util.spec_from_file_location("semantic_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.OUT = OUT
BASE.COLUMNS = COLUMNS
BASE.ROWS = ROWS


class CaptureProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        assert output_schema is not None
        if operation == "distill_context":
            from memcommit.distill import DISTILL_PAYLOAD_MARKER

            payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
            aliases = [item["memory_id"] for item in payload["source"]["memories"]]
            return json.dumps(
                {
                    "overview": (
                        "The examples support a confirmation Rule while the "
                        "contrast limits when action is allowed."
                    ),
                    "rules": [
                        {
                            "content": "Act only after the person explicitly confirms the selected option.",
                            "rationale": "The confirmed Case supports action and the mention-only Case bounds it.",
                            "support_memory_ids": aliases[:1],
                            "boundary_memory_ids": aliases[1:2],
                        }
                    ],
                    "outside_memory_ids": aliases[2:],
                }
            )
        from memcommit.elaborate import ELABORATE_PAYLOAD_MARKER

        payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
        if payload["mode"] == "GOAL_TO_RULES":
            return json.dumps(
                {
                    "overview": "One suggested Rule makes the Goal reviewable.",
                    "rules": [
                        {
                            "content": "Confirm the selected option before acting.",
                            "rationale": "This operationalizes the Goal without claiming evidence.",
                        }
                    ],
                }
            )
        return json.dumps(
            {
                "overview": "A fit and a boundary make the Rule easier to test.",
                "cases": [
                    {
                        "proposition": "The person explicitly confirms option A.",
                        "expected": "Proceed with option A.",
                        "rationale": "This is an ordinary fitting Case.",
                        "case_role": "FIT",
                        "source_rule_index": 1,
                    },
                    {
                        "proposition": "The person mentions option A without confirming it.",
                        "expected": "Do not proceed yet.",
                        "rationale": "This distinguishes mention from confirmation.",
                        "case_role": "BOUNDARY",
                        "source_rule_index": 1,
                    },
                ],
            }
        )


def _configure_store(root: Path):
    import memcommit.store as store_module

    store_module.STORE_DIR = root
    return store_module.MemoryStore(root=root)


def _prepare_source(root: Path):
    import memcommit.ops as ops

    store = _configure_store(root)
    source = ops.init("capture/cases")
    ops.add(source, "The person explicitly confirmed option A before it was used.")
    ops.add(source, "The person mentioned option A but did not confirm it.")
    store.create_context(source)
    store.set_current(source.name)
    return store, source


def _source_bytes(store, source) -> bytes:
    return store._context_file(source.name).read_bytes()


def _run_distill_review(root: Path, *, cancel: bool) -> None:
    from memcommit.cli import app
    from memcommit.commands import distill as command

    store, source = _prepare_source(root)
    before = _source_bytes(store, source)
    provider = CaptureProvider()
    copied: list[str] = []
    command.connect_semantic_provider = lambda: provider
    command.write_system_clipboard = copied.append
    print(
        '$ mem distill capture/cases --goal "Confirm before acting." '
        '--save-as capture/rules --tui',
        flush=True,
    )
    app(
        args=[
            "distill",
            "capture/cases",
            "--goal",
            "Confirm before acting.",
            "--save-as",
            "capture/rules",
            "--tui",
        ],
        prog_name="mem",
        standalone_mode=False,
    )
    assert _source_bytes(store, source) == before
    assert not store.context_exists("capture/rules")
    if cancel:
        assert provider.calls == 0 and copied == []
        print("CANCEL VERIFIED · PROVIDER CALLS 0 · SOURCE UNCHANGED", flush=True)
    else:
        assert provider.calls == 1
        assert len(copied) == 2
        assert copied[0].startswith("RULE 1 · Act only after")
        assert "WHAT MEM UNDERSTOOD" in copied[1]
        print(
            "REVIEW VERIFIED · FOCUSED + WHOLE COPY · RESULT NOT CREATED · "
            "SOURCE UNCHANGED",
            flush=True,
        )


def _run_distill_apply(root: Path) -> None:
    from memcommit.cli import app
    from memcommit.commands import distill as command

    store, source = _prepare_source(root)
    before = _source_bytes(store, source)
    provider = CaptureProvider()
    command.connect_semantic_provider = lambda: provider
    print(
        "$ mem distill capture/cases --save-as capture/rules --apply --plain",
        flush=True,
    )
    app(
        args=[
            "distill",
            "capture/cases",
            "--save-as",
            "capture/rules",
            "--apply",
            "--plain",
        ],
        prog_name="mem",
        standalone_mode=False,
    )
    assert _source_bytes(store, source) == before
    result = store.load_direct("capture/rules")
    checkpoints = store.list_checkpoints(result.name)
    assert len(result.memories) == 1 and checkpoints[0]["command"] == "distill"
    print("$ mem show --context capture/rules", flush=True)
    app(
        args=["show", "--context", "capture/rules"],
        prog_name="mem",
        standalone_mode=False,
    )
    print(
        "APPLY + READ-ONLY VERIFICATION · ONE RESULT RULE · ONE DISTILL "
        "CHECKPOINT · SOURCE UNCHANGED",
        flush=True,
    )


def _prepare_ground_distill(root: Path):
    from memcommit.context import Context, Memory
    from memcommit.ground import (
        GroundTargetSpec,
        bind_ground_workbench,
        create_ground_session,
    )

    store = _configure_store(root)
    raw = Context(uid="00000000-0000-4000-8000-000000000301", name="capture/raw")
    candidates = Context(
        uid="00000000-0000-4000-8000-000000000302",
        name="capture/candidates",
    )
    candidates.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000311",
            content="The person explicitly confirmed option A before it was used.",
        )
    )
    candidates.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000312",
            content="The person mentioned option A but did not confirm it.",
        )
    )
    target = Context(
        uid="00000000-0000-4000-8000-000000000303",
        name="capture/target",
    )
    for context in (raw, candidates, target):
        store.create_context(context)
    session = bind_ground_workbench(
        create_ground_session(
            "capture-ground",
            goal="Confirm a chosen option before acting.",
        ),
        description="Review one confirmation Rule.",
        raw_context=raw,
        derived_context=candidates,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Publish one reviewed Rule.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    store.save_ground_session(session)
    return store, session, (raw, candidates, target)


def _run_ground_distill(root: Path) -> None:
    from memcommit.cli import app
    from memcommit.commands import distill as command
    from memcommit.store import ground_session_record_digest

    store, session, contexts = _prepare_ground_distill(root)
    before_ground = ground_session_record_digest(session)
    before_contexts = {
        context.name: store._context_file(context.name).read_bytes()
        for context in contexts
    }
    provider = CaptureProvider()
    command.connect_semantic_provider = lambda: provider
    print("$ mem distill --ground capture-ground --tui", flush=True)
    app(
        args=["distill", "--ground", "capture-ground", "--tui"],
        prog_name="mem",
        standalone_mode=False,
    )
    after_ground = store.load_ground_session(session.contract_name)
    assert after_ground is not None
    assert ground_session_record_digest(after_ground) == before_ground
    assert all(
        store._context_file(name).read_bytes() == content
        for name, content in before_contexts.items()
    )
    assert provider.calls == 1
    print(
        "GROUND DISTILL VERIFIED · EXACT FROZEN SOURCE · NO APPLY · "
        "GROUND + CONTEXTS UNCHANGED",
        flush=True,
    )


def _run_elaborate(root: Path, *, rules: bool) -> None:
    from memcommit.cli import app
    from memcommit.commands import elaborate as command

    store, source = _prepare_source(root)
    before = _source_bytes(store, source)
    provider = CaptureProvider()
    copied: list[str] = []
    command.connect_semantic_provider = lambda: provider
    command.write_system_clipboard = copied.append
    args = (
        ["elaborate", "--rule", "Confirm the selected option before acting.", "--tui"]
        if rules
        else ["elaborate", "--goal", "Confirm before acting.", "--tui"]
    )
    print("$ mem " + " ".join(args[1:]), flush=True)
    app(args=args, prog_name="mem", standalone_mode=False)
    assert provider.calls == 1 and len(copied) == 2
    assert _source_bytes(store, source) == before
    assert len(store.list_context_names()) == 1
    assert "[Suggested] [Unverified]" in copied[0]
    assert "WHAT MEM UNDERSTOOD" in copied[1]
    print(
        "ELABORATE VERIFIED · FOCUSED + WHOLE COPY · SUGGESTED + UNVERIFIED · "
        "NO CONTEXT OR GROUND CHANGE",
        flush=True,
    )


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


def _spawn(kind: str, root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    BASE._snapshot(recorder, stem)


def _capture_distill_review(root: Path) -> None:
    child, recorder = _spawn("distill-review", root)
    try:
        child.expect("MEM DISTILL")
        BASE._settle(child)
        _snapshot(recorder, "01-distill-context-entry")
        child.send(SHIFT_TAB + RIGHT)
        BASE._settle(child)
        _snapshot(recorder, "02-distill-descendants-selected")
        child.send(TAB * 2)
        BASE._settle(child)
        _snapshot(recorder, "03-distill-run-ready")
        child.send("s")
        child.expect("SOURCE UNCHANGED")
        BASE._settle(child)
        _snapshot(recorder, "04-distill-reviewed-result")
        child.send(DOWN * 4 + "y")
        BASE._settle(child)
        _snapshot(recorder, "05-distill-focused-rule-copied")
        child.send("Y")
        BASE._settle(child)
        _snapshot(recorder, "06-distill-whole-proposal-copied")
        child.send("q")
        child.expect("Create 'capture/rules'")
        child.send("n\r")
        child.expect("REVIEW VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "07-distill-not-created-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_distill_cancel(root: Path) -> None:
    child, recorder = _spawn("distill-cancel", root)
    try:
        child.expect("MEM DISTILL")
        child.send("q")
        child.expect("CANCEL VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-distill-cancel-before-provider")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_distill_apply(root: Path) -> None:
    child, recorder = _spawn("distill-apply", root)
    try:
        child.expect("Created Distill Result")
        child.expect(r"APPLY \+ READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "09-distill-apply-and-show-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_ground_distill(root: Path) -> None:
    child, recorder = _spawn("ground-distill", root)
    try:
        child.expect("SOURCE FROZEN BY CALLER")
        BASE._settle(child)
        _snapshot(recorder, "10-ground-distill-frozen-source")
        # These keys would retarget ordinary Distill. The locked branch keeps
        # the run action and exact request unchanged.
        child.send(SHIFT_TAB + RIGHT + "s")
        child.expect("SOURCE UNCHANGED")
        BASE._settle(child)
        _snapshot(recorder, "10-ground-distill-reviewed-result")
        child.send("q")
        child.expect("GROUND DISTILL VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "10-ground-distill-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_elaborate(kind: str, root: Path, stem: str) -> None:
    child, recorder = _spawn(kind, root)
    try:
        child.expect("ELABORATE ·")
        BASE._settle(child)
        _snapshot(recorder, f"{stem}-result")
        child.send(DOWN * 3 + "y")
        BASE._settle(child)
        _snapshot(recorder, f"{stem}-focused-copied")
        child.send("Yq")
        child.expect("ELABORATE VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, f"{stem}-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # The capture set is ordered evidence, so a renumbered state must not leave
    # an obsolete image that looks like part of the current interaction log.
    for path in OUT.iterdir():
        if path.suffix in {".png", ".txt", ".typescript"}:
            path.unlink()
    with tempfile.TemporaryDirectory(prefix="distill-elaborate-capture-") as directory:
        root = Path(directory)
        _capture_distill_review(root / "review" / ".mem")
        _capture_distill_cancel(root / "cancel" / ".mem")
        _capture_distill_apply(root / "apply" / ".mem")
        _capture_ground_distill(root / "ground" / ".mem")
        _capture_elaborate("elaborate-goal", root / "goal" / ".mem", "11-elaborate-goal")
        _capture_elaborate("elaborate-rules", root / "rules" / ".mem", "12-elaborate-rules")
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "\x1b[" not in raw or "38;" not in raw or "48;" not in raw:
        raise RuntimeError("Capture did not retain foreground and background ANSI styles.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT))
        child_kind = sys.argv[2]
        child_root = Path(sys.argv[3])
        if child_kind == "distill-review":
            _run_distill_review(child_root, cancel=False)
        elif child_kind == "distill-cancel":
            _run_distill_review(child_root, cancel=True)
        elif child_kind == "distill-apply":
            _run_distill_apply(child_root)
        elif child_kind == "ground-distill":
            _run_ground_distill(child_root)
        elif child_kind == "elaborate-goal":
            _run_elaborate(child_root, rules=False)
        elif child_kind == "elaborate-rules":
            _run_elaborate(child_root, rules=True)
        else:
            raise SystemExit(f"unknown child kind: {child_kind}")
    else:
        main()
