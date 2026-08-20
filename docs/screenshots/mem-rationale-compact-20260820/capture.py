"""Capture the compact Rationale report through a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-rationale-compact-20260820"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"

_BASE_PATH = (
    ROOT / "docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("rationale_compact_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS
# Menlo has no Hangul glyphs. Keep its terminal metrics and use a system font
# only for Korean glyphs so the real PTY's cell alignment stays intact.
_BASE.HANGUL_FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"


def _isolate_store(root: Path) -> None:
    import memcommit.store as store_module

    store_dir = root / ".mem"
    assignments = {
        "STORE_DIR": store_dir,
        "CONTEXTS_DIR": store_dir / "contexts",
        "QUERY_SOURCES_DIR": store_dir / "query-sources",
        "STATE_FILE": store_dir / "state.json",
        "IMPACT_PLAN_FILE": store_dir / "impact-plan.json",
        "STAGED_UPDATE_FILE": store_dir / "staged-update.json",
        "REVIEW_SESSION_FILE": store_dir / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": store_dir / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": store_dir / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": store_dir / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": store_dir / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": store_dir / "ground-sessions",
        "MELD_SESSIONS_DIR": store_dir / "meld-sessions",
    }
    for name, value in assignments.items():
        setattr(store_module, name, value)


def _prepare_fixture() -> str:
    import memcommit.ops as ops
    from memcommit.context import AutoCheckpoint, Memory
    from memcommit.store import MemoryStore

    store = MemoryStore()
    context = ops.init("rationale/korean")
    source = ops.add(
        context,
        "나중에 문장을 다듬어 달라고 하면 구조와 인용 필요 표시는 유지하고, "
        "문제가 되는 표현만 바꾼다.",
    )
    store.save(
        context,
        AutoCheckpoint(command="add", args={}, description="초안 규칙 추가"),
    )
    source_position = context.ordered_uids().index(source.uid)
    context.remove(source.uid)
    target = Memory(
        uid="20000000-0000-4000-8000-000000000001",
        content=(
            "나중에 문장을 다듬어 달라고 하면 전체 구조와 인용 필요 표시는 "
            "유지하고, 문제가 되는 표현만 바꾼다."
        ),
    )
    context.add(target, position=source_position)
    reason = (
        "문장 다듬기 요청이 전체 재작성으로 번지지 않도록 구조와 인용 표시를 "
        "보존하는 검토 원칙을 기록하기 위해 유지했다."
    )
    store.save(
        context,
        AutoCheckpoint(
            command="atomize",
            args={
                "trace": {
                    "schema_version": 1,
                    "operation_id": "compact-korean-provenance",
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
            description="기록 이유가 있는 검토 원칙 적용",
        ),
    )
    store.set_current(context.name)
    return target.uid


def _run_child() -> None:
    from memcommit.commands import rationale
    from memcommit.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="memcommit-rationale-compact-") as temp:
        _isolate_store(Path(temp))
        target_uid = _prepare_fixture()
        before = MemoryStore().load_current_direct().to_dict()
        assert not hasattr(rationale, "connect_codex_chatgpt_provider")
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        rationale.cmd()
        after = MemoryStore().load_current_direct().to_dict()
        assert before == after
        print(
            f"RATIONALE CLOSED · TARGET [{target_uid[:8]}] · "
            "CURRENT rationale/korean · PROVIDER CALLS 0 · "
            "CACHE UNTOUCHED · STORE CONTENT UNCHANGED"
        )


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


def _spawn() -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
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

    child, recorder = _spawn()
    try:
        child.expect("RATIONALE · SELECT A MEMORY · rationale/korean")
        _BASE._settle(child)
        _snapshot(recorder, "01-target-entry")

        child.send("\t" + DOWN)
        _BASE._settle(child)
        _snapshot(recorder, "02-target-focused")

        child.send("\r")
        child.expect("RATIONALE REPORT")
        _BASE._settle(child)
        _snapshot(recorder, "03-compact-report")

        child.send("q")
        child.expect("RATIONALE CLOSED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "04-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    plain = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.txt"))
    assert "PTY 180 52" in raw
    assert "MEMORY" in plain
    assert "PROVENANCE — latest recorded reason" in plain
    assert "검토 원칙을 기록하기 위해 유지했다" in plain
    assert "APPARENT PURPOSE" not in plain
    assert "LIMITS" not in plain
    assert "Context(s)" not in plain
    assert "SAVED ANALYSIS" not in plain
    assert "EVIDENCE USED FOR INFERENCE" not in plain
    assert "STORE CONTENT UNCHANGED" in plain
    assert "PROVIDER CALLS 0" in plain
    assert "┏" in raw and "┗" in raw
    assert "38;" in raw
    assert any(
        "7" in codes.split(";") for codes in re.findall("\x1b\\[([0-9;]*)m", raw)
    )


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT))
        _run_child()
    else:
        main()
