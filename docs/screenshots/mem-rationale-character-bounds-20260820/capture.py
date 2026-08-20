"""Capture provenance-only Rationale boundaries in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import uuid

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-rationale-character-bounds-20260820"
COLUMNS = 180
ROWS = 52

_COMPACT_PATH = (
    ROOT / "docs/screenshots/mem-rationale-compact-20260820/capture.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "rationale_provenance_bounds_compact",
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


def _recorded_context(name: str, *, content: str, reason: str, target_uid: str):
    import memcommit.ops as ops
    from memcommit.context import AutoCheckpoint, Memory
    from memcommit.store import MemoryStore

    store = MemoryStore()
    context = ops.init(name)
    source = ops.add(context, "초안 " + content)
    store.save(
        context,
        AutoCheckpoint(command="add", args={}, description="초안 추가"),
    )
    source_position = context.ordered_uids().index(source.uid)
    context.remove(source.uid)
    target = Memory(uid=target_uid, content=content)
    context.add(target, position=source_position)
    store.save(
        context,
        AutoCheckpoint(
            command="atomize",
            args={
                "trace": {
                    "schema_version": 1,
                    "operation_id": str(uuid.uuid4()),
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
            description="기록 이유 적용",
        ),
    )
    store.set_current(context.name)
    return store, context, target


def _guard_provenance_only() -> None:
    import memcommit.rationale as rationale_engine
    from memcommit.commands import rationale

    assert not hasattr(rationale, "connect_codex_chatgpt_provider")

    def forbidden(*args, **kwargs):
        raise AssertionError("provenance-only capture touched inference cache")

    rationale_engine.load_rationale_inference = forbidden
    rationale_engine.save_rationale_inference = forbidden


def _run_no_reason() -> None:
    from memcommit.commands import rationale
    from memcommit.rationale_cache import rationale_inference_path

    store, context, memories = _stored_context(
        "provenance/no-reason",
        ["아직 기록 이유가 없는 한국어 Memory다."],
    )
    before = context.to_dict()
    _guard_provenance_only()
    rationale.cmd(memories[0].uid)
    assert store.load_direct(context.name).to_dict() == before
    assert not rationale_inference_path(context.uid, memories[0].uid).exists()
    print(
        "SCENARIO no-reason VERIFIED · PROVIDER CALLS 0 · CACHE UNTOUCHED · "
        "STORE UNCHANGED"
    )


def _run_recorded_reason() -> None:
    from memcommit.commands import rationale
    from memcommit.rationale_cache import rationale_inference_path

    reason = "중복된 초안 규칙을 하나의 검토 기준으로 합치기 위해 유지했다."
    store, context, target = _recorded_context(
        "provenance/recorded-reason",
        content="문장 검토에서는 구조와 인용 표시를 보존한다.",
        reason=reason,
        target_uid="30000000-0000-4000-8000-000000000001",
    )
    before = context.to_dict()
    _guard_provenance_only()
    rationale.cmd(target.uid)
    assert store.load_direct(context.name).to_dict() == before
    assert not rationale_inference_path(context.uid, target.uid).exists()
    print(
        f"SCENARIO recorded-reason VERIFIED · REASON {len(reason)} CHARS · "
        "PROVIDER CALLS 0 · CACHE UNTOUCHED · STORE UNCHANGED"
    )


def _run_oversized_context() -> None:
    from memcommit.commands import rationale
    from memcommit.rationale_cache import rationale_inference_path

    korean_fill = "가나다라마바사아자차카타파하"
    contents = ["큰 Context에서도 이 대상의 기록 이유만 확인한다."] + [
        f"{index:03d}" + (korean_fill[index % len(korean_fill)] * 9_997)
        for index in range(105)
    ]
    store, context, memories = _stored_context(
        "provenance/oversized-context",
        contents,
    )
    before = context.to_dict()
    _guard_provenance_only()
    rationale.cmd(memories[0].uid)
    assert store.load_direct(context.name).to_dict() == before
    assert not rationale_inference_path(context.uid, memories[0].uid).exists()
    print(
        "SCENARIO oversized-context VERIFIED · MEMORIES 106 · "
        "SEMANTIC SOURCE OVER 1000000 · PROVIDER CALLS 0 · CACHE UNTOUCHED · "
        "STORE UNCHANGED"
    )


def _run_long_provenance() -> None:
    from memcommit.commands import rationale
    from memcommit.rationale_cache import rationale_inference_path

    reason = (
        "검토된 로컬 규칙의 목적을 주변 항목과 중복 없이 한 문장으로 남기기 위해 "
        "이 Memory를 유지했다. "
    ) * 7
    store, context, target = _recorded_context(
        "provenance/long-reason",
        content="현재 " + ("나" * 240),
        reason=reason,
        target_uid="40000000-0000-4000-8000-000000000001",
    )
    before = context.to_dict()
    _guard_provenance_only()
    rationale.cmd(target.uid)
    assert store.load_direct(context.name).to_dict() == before
    assert not rationale_inference_path(context.uid, target.uid).exists()
    print(
        f"SCENARIO long-reason VERIFIED · REASON {len(reason)} CHARS · "
        "PROJECTION LIMIT 320 · PROVIDER CALLS 0 · CACHE UNTOUCHED · "
        "STORE UNCHANGED"
    )


_RUNNERS = {
    "no-reason": _run_no_reason,
    "recorded-reason": _run_recorded_reason,
    "oversized-context": _run_oversized_context,
    "long-reason": _run_long_provenance,
}


def _run_child(scenario: str) -> None:
    with tempfile.TemporaryDirectory(
        prefix=f"memcommit-rationale-{scenario}-"
    ) as temp:
        _COMPACT._isolate_store(Path(temp))
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        _RUNNERS[scenario]()


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
        for output_path in OUT.glob(pattern):
            output_path.unlink()

    cases = (
        ("no-reason", "PROVENANCE — no reason recorded"),
        ("recorded-reason", "PROVENANCE — recorded reason"),
        ("oversized-context", "PROVENANCE — no reason recorded"),
        ("long-reason", "PROVENANCE — recorded reason"),
    )
    for index, (scenario, expected) in enumerate(cases, start=1):
        child, recorder = _spawn(scenario)
        report_stem = f"{index * 2 - 1:02d}-{scenario}-report"
        receipt_stem = f"{index * 2:02d}-{scenario}-verification"
        try:
            child.expect("RATIONALE REPORT")
            _BASE._settle(child)
            plain = _BASE.pyte.Screen(COLUMNS, ROWS)
            _BASE.pyte.Stream(plain).feed(recorder.getvalue())
            assert expected in "\n".join(plain.display)
            _snapshot(recorder, report_stem)

            child.send("q")
            child.expect(f"SCENARIO {scenario} VERIFIED")
            child.expect(pexpect.EOF)
            _snapshot(recorder, receipt_stem)
        finally:
            if child.isalive():
                child.close(force=True)

    raw = "".join(
        output_path.read_text(encoding="utf-8")
        for output_path in OUT.glob("*.typescript")
    )
    combined = "".join(
        output_path.read_text(encoding="utf-8")
        for output_path in OUT.glob("*.txt")
    )
    assert raw.count("PTY 180 52") >= len(cases)
    assert "APPARENT PURPOSE" not in combined
    assert "PROVIDER CALLS 0" in combined
    assert "CACHE UNTOUCHED" in combined
    assert "중복된 초안 규칙을 하나의 검토 기준으로 합치기 위해 유지했다." in combined
    assert "SEMANTIC SOURCE OVER 1000000" in combined
    assert "PROJECTION LIMIT 320" in combined
    assert "LIMITS" not in combined
    assert "Context(s)" not in combined


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT))
        _run_child(sys.argv[2])
    else:
        main()
