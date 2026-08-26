"""Capture complete natural Rationale narratives under each length unit."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-rationale-character-bounds-20260820"
COLUMNS = 180
ROWS = 52

_COMPACT_PATH = ROOT / "docs/screenshots/mem-rationale-compact-20260820/capture.py"
_SPEC = importlib.util.spec_from_file_location(
    "rationale_lifecycle_receipt_compact",
    _COMPACT_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_COMPACT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_COMPACT)
_BASE = _COMPACT._BASE
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


_SCENARIOS = {
    "complete": (
        40,
        "words",
        (
            "“Um...” began as a hesitation between a minimal-change instruction "
            "and its “distribute, not divide” example. Sentence chunking made it "
            "a standalone Memory; undo removed it, redo restored it, and remove "
            "later deleted it."
        ),
    ),
    "characters": (
        150,
        "characters",
        (
            "“Um...” came from between an instruction and its example. Sentence "
            "chunking isolated it; undo removed it, redo restored it, and remove "
            "deleted it."
        ),
    ),
    "bytes": (
        150,
        "bytes",
        (
            '"Um..." sat between an instruction and example. Sentence chunking '
            "isolated it; undo removed it, redo restored it, then remove deleted it."
        ),
    ),
    "words": (
        24,
        "words",
        (
            "“Um...” separated an instruction from its example. Sentence chunking "
            "isolated it; undo removed it, redo restored it, and remove deleted it."
        ),
    ),
}


def _run_child(scenario: str) -> None:
    import json

    from memcommit.commands import rationale
    from memcommit.rationale_rules import RationaleLimitUnit
    from memcommit.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix=f"memcommit-rationale-{scenario}-") as temp:
        _COMPACT._isolate_store(Path(temp))
        target_uid = _COMPACT._prepare_fixture()
        before = MemoryStore().load_current_direct().to_dict()
        limit, raw_unit, expected = _SCENARIOS[scenario]

        class Provider:
            calls = 0

            def complete(self, prompt, *, operation, output_schema=None):
                assert operation == "rationale provenance"
                assert output_schema is not None
                payload = json.loads(prompt.split("RATIONALE PAYLOAD:\n", 1)[1])
                assert payload["request"]["length"] == {
                    "target": max(1, (limit * 90) // 100),
                    "limit": limit,
                    "unit": raw_unit,
                }
                type(self).calls += 1
                return json.dumps({"provenance": expected}, ensure_ascii=False)

        rationale.connect_semantic_provider = Provider
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        rationale.cmd(
            target_uid,
            limit=limit,
            unit=RationaleLimitUnit(raw_unit),
        )
        assert Provider.calls == 1
        print(
            f"SCENARIO {scenario} RECEIPT · LIMIT {limit} {raw_unit.upper()} · "
            "PRESS V TO VERIFY"
        )
        input()
        assert MemoryStore().load_current_direct().to_dict() == before
        print(
            f"SCENARIO {scenario} VERIFIED · PROVIDER CALLS 1 · "
            "CACHE UNTOUCHED · STORE UNCHANGED"
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

    for index, scenario in enumerate(_SCENARIOS, start=1):
        child, recorder = _spawn(scenario)
        receipt_stem = f"{index * 2 - 1:02d}-{scenario}-receipt"
        verification_stem = f"{index * 2:02d}-{scenario}-verification"
        try:
            child.expect(f"SCENARIO {scenario} RECEIPT")
            _BASE._settle(child)
            _snapshot(recorder, receipt_stem)

            child.send("v\r")
            child.expect(f"SCENARIO {scenario} VERIFIED")
            child.expect(pexpect.EOF)
            _snapshot(recorder, verification_stem)
        finally:
            if child.isalive():
                child.close(force=True)

    raw = "".join(
        output_path.read_text(encoding="utf-8")
        for output_path in OUT.glob("*.typescript")
    )
    combined = "".join(
        output_path.read_text(encoding="utf-8") for output_path in OUT.glob("*.txt")
    )
    normalized_combined = " ".join(combined.split())
    assert raw.count("PTY 180 52") >= len(_SCENARIOS)
    assert "APPARENT PURPOSE" not in combined
    assert "RATIONALE REPORT" not in combined
    assert "PROVIDER CALLS 1" in combined
    assert "CACHE UNTOUCHED" in combined
    for _limit, _unit, expected in _SCENARIOS.values():
        assert " ".join(expected.split()) in normalized_combined
    assert "CREATED via" not in combined
    assert "clipped" not in combined


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(sys.argv[2])
    else:
        main()
