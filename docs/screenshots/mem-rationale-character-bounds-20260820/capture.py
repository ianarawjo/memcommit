"""Capture actual Rationale character-budget edge cases in a color PTY."""

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
OUT = ROOT / "docs/screenshots/mem-rationale-character-bounds-20260820"
COLUMNS = 180
ROWS = 52

_COMPACT_PATH = (
    ROOT / "docs/screenshots/mem-rationale-compact-20260820/capture.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "rationale_character_bounds_compact",
    _COMPACT_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_COMPACT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_COMPACT)
_BASE = _COMPACT._BASE
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _stored_context(name: str, contents: list[str]):
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore()
    context = ops.init(name)
    memories = ops.add_many(context, contents)
    store.save(context)
    store.set_current(context.name)
    return store, context, memories


def _run_insufficient() -> None:
    from memcommit.commands import rationale

    store, context, memories = _stored_context(
        "bounds/insufficient",
        ["A", "B"],
    )
    before = context.to_dict()
    connections = 0

    def forbidden():
        nonlocal connections
        connections += 1
        raise AssertionError("insufficient evidence connected the provider")

    rationale.connect_codex_chatgpt_provider = forbidden
    rationale.cmd(memories[0].uid)
    assert connections == 0
    assert store.load_direct(context.name).to_dict() == before
    print(
        "SCENARIO insufficient VERIFIED · SOURCE 2 · LIMIT 1 · "
        "PROVIDER CALLS 0 · STORE UNCHANGED"
    )


def _run_minimum() -> None:
    from memcommit.commands import rationale

    store, context, memories = _stored_context(
        "bounds/minimum",
        ["12345678", "abcdefghi"],
    )
    before = context.to_dict()
    observed: dict[str, int] = {}

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "rationale inference"
            assert output_schema is not None
            limit = output_schema["properties"]["explanation"]["maxLength"]
            observed["limit"] = limit
            payload = json.loads(prompt.split("RATIONALE PAYLOAD:\n", 1)[1])
            return json.dumps(
                {
                    "explanation": "No purpose seen.",
                    "support_ids": [payload["candidates"][0]["candidate_id"]],
                }
            )

    rationale.connect_codex_chatgpt_provider = Provider
    rationale.cmd(memories[0].uid)
    assert observed == {"limit": 16}
    assert store.load_direct(context.name).to_dict() == before
    print(
        "SCENARIO minimum VERIFIED · SOURCE 17 · LIMIT 16 · "
        "OUTPUT 16 · STORE UNCHANGED"
    )


def _run_over_limit() -> None:
    from memcommit.commands import rationale
    from memcommit.rationale_cache import rationale_inference_path

    store, context, memories = _stored_context(
        "bounds/over-limit",
        ["Target fragment.", "Visible neighbor."],
    )
    before = context.to_dict()
    observed: dict[str, int] = {}

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert output_schema is not None
            limit = output_schema["properties"]["explanation"]["maxLength"]
            observed["limit"] = limit
            return json.dumps(
                {
                    "explanation": "P" * (limit + 1),
                    "support_ids": [],
                }
            )

    rationale.connect_codex_chatgpt_provider = Provider
    rationale.cmd(memories[0].uid)
    assert observed == {"limit": 32}
    assert not rationale_inference_path(context.uid, memories[0].uid).exists()
    assert store.load_direct(context.name).to_dict() == before
    print(
        "SCENARIO over-limit VERIFIED · SOURCE 33 · LIMIT 32 · "
        "OUTPUT 33 REJECTED · CACHE ABSENT · STORE UNCHANGED"
    )


def _run_oversized_context() -> None:
    from memcommit.commands import rationale

    contents = ["Large target."] + [
        f"{index:03d}" + (chr(65 + index % 26) * 9_997)
        for index in range(105)
    ]
    store, context, memories = _stored_context(
        "bounds/oversized-context",
        contents,
    )
    before = context.to_dict()
    observed: dict[str, object] = {}
    sentence = (
        "This Memory preserves a stable editing rule that coordinates the "
        "surrounding constraints without duplicating their details. "
    )
    explanation = (sentence * 8)[:480]
    assert len(explanation) == 480

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert output_schema is not None
            payload = json.loads(prompt.split("RATIONALE PAYLOAD:\n", 1)[1])
            observed["candidate_count"] = len(payload["candidates"])
            observed["scope"] = payload["context_scope"]
            observed["limit"] = output_schema["properties"]["explanation"][
                "maxLength"
            ]
            return json.dumps(
                {
                    "explanation": explanation,
                    "support_ids": [payload["candidates"][0]["candidate_id"]],
                }
            )

    rationale.connect_codex_chatgpt_provider = Provider
    rationale.cmd(memories[0].uid)
    assert observed["candidate_count"] == 49
    assert str(observed["scope"]).startswith("nearest readable subtree")
    assert observed["limit"] == 480
    assert store.load_direct(context.name).to_dict() == before
    print(
        "SCENARIO oversized-context VERIFIED · CANDIDATES 49/105 · "
        "LIMIT 480 · OUTPUT 480 · STORE UNCHANGED"
    )


def _run_long_provenance() -> None:
    import memcommit.ops as ops
    from memcommit.commands import rationale
    from memcommit.context import AutoCheckpoint, Memory
    from memcommit.provenance import build_trace
    from memcommit.rationale import build_rationale
    from memcommit.store import MemoryStore

    store = MemoryStore()
    context = ops.init("bounds/long-provenance")
    source = ops.add(context, "Initial " + ("A" * 240))
    store.save(
        context,
        AutoCheckpoint(command="add", args={}, description="Added long Memory"),
    )
    source_position = context.ordered_uids().index(source.uid)
    context.remove(source.uid)
    target = Memory(
        uid="10000000-0000-4000-8000-000000000001",
        content="Current " + ("B" * 240),
    )
    context.add(target, position=source_position)
    reason = (
        "This Memory was retained because the reviewed local rule needs one "
        "stable statement of purpose without repeating the surrounding "
        "inventory. "
    ) * 4
    store.save(
        context,
        AutoCheckpoint(
            command="atomize",
            args={
                "trace": {
                    "schema_version": 1,
                    "operation_id": "long-rationale-operation",
                    "changes": [
                        {
                            "kind": "SPLIT",
                            "source_uids": [source.uid],
                            "result_uids": [target.uid],
                            "reason": reason,
                            "reason_codes": ["A01_ONE_FOCUS"],
                        }
                    ],
                }
            },
            description="Applied a long recorded rationale",
        ),
    )
    store.set_current(context.name)
    before = context.to_dict()
    report = build_rationale(
        store,
        context,
        build_trace(store, context, target.uid),
        None,
    )
    assert report.provenance_source_character_count > 320
    assert report.provenance_character_limit == 320
    assert report.recorded_reason_events
    rationale.cmd(target.uid, recorded_only=True)
    assert store.load_direct(context.name).to_dict() == before
    print(
        "SCENARIO long-provenance VERIFIED · SOURCE "
        f"{report.provenance_source_character_count} · LIMIT 320 · "
        "STORE UNCHANGED"
    )


SCENARIOS = {
    "insufficient": _run_insufficient,
    "minimum": _run_minimum,
    "over-limit": _run_over_limit,
    "oversized-context": _run_oversized_context,
    "long-provenance": _run_long_provenance,
}


def _run_child(scenario: str) -> None:
    with tempfile.TemporaryDirectory(prefix=f"memcommit-rationale-{scenario}-") as temp:
        _COMPACT._isolate_store(Path(temp))
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        SCENARIOS[scenario]()


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


def _spawn(scenario: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", scenario],
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
    _BASE._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(pattern):
            path.unlink()

    cases = (
        ("insufficient", "WHY — insufficient Context"),
        ("minimum", "WHY — inferred from Context, not recorded"),
        ("over-limit", "WHY — unavailable"),
        ("oversized-context", "WHY — inferred from Context, not recorded"),
        ("long-provenance", "WHY — not requested"),
    )
    for index, (scenario, expected) in enumerate(cases, start=1):
        child, recorder = _spawn(scenario)
        try:
            child.expect("RATIONALE REPORT")
            _BASE._settle(child)
            _snapshot(recorder, f"{index * 2 - 1:02d}-{scenario}-report")

            child.send("q")
            child.expect(f"SCENARIO {scenario} VERIFIED")
            child.expect(pexpect.EOF)
            _snapshot(recorder, f"{index * 2:02d}-{scenario}-verification")
        finally:
            if child.isalive():
                child.close(force=True)

        report_text = (OUT / f"{index * 2 - 1:02d}-{scenario}-report.txt").read_text(
            encoding="utf-8"
        )
        raw_text = (
            OUT / f"{index * 2 - 1:02d}-{scenario}-report.typescript"
        ).read_text(encoding="utf-8")
        assert expected in report_text
        assert "PTY 180 52" in raw_text
        assert "┏" in raw_text and "┗" in raw_text
        assert "38;" in raw_text

    combined = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.txt"))
    assert "PPPPPP" not in combined
    assert "PROVIDER CALLS 0" in combined
    assert "OUTPUT 33 REJECTED" in combined
    assert "CANDIDATES 49/105" in combined
    assert "LIMIT 320" in combined
    assert "LIMITS" not in combined
    assert "Context(s)" not in combined


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT))
        _run_child(sys.argv[2])
    else:
        main()
