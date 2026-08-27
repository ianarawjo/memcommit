"""Capture calibrated natural-language Rationale through a real color PTY."""

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
OUT = ROOT / "agent-records/docs/screenshots/mem-rationale-compact-20260820"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
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
    import memcommit.persistence.store as store_module

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
    from typer.testing import CliRunner

    from memcommit.adapters.console.entrypoint import app
    from memcommit.core.context import Memory
    from memcommit.persistence.store import MemoryStore

    runner = CliRunner()
    assert runner.invoke(app, ["init", "rationale/origin"]).exit_code == 0
    source_text = (
        "When I ask to change one expression, leave almost everything else as "
        "it is, including technical or project-specific terms that I selected. "
        "Um... for example, use distribute, not divide, when material is "
        "absorbed into two parts."
    )
    assert runner.invoke(app, ["add", source_text]).exit_code == 0
    parent = next(
        item
        for item in MemoryStore().load_current_direct().iter_items()
        if isinstance(item, Memory)
    )
    chunked = runner.invoke(
        app,
        ["chunk", parent.uid, "--method", "sentences"],
        input="y\n",
    )
    assert chunked.exit_code == 0, chunked.output
    target = next(
        item
        for item in MemoryStore().load_current_direct().iter_items()
        if isinstance(item, Memory) and item.content == "Um..."
    )
    assert runner.invoke(app, ["undo"]).exit_code == 0
    assert runner.invoke(app, ["redo"]).exit_code == 0
    assert runner.invoke(app, ["remove", target.uid]).exit_code == 0
    return target.uid


class _CaptureProvider:
    calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        import json

        assert operation == "rationale provenance"
        assert output_schema is not None
        payload = json.loads(prompt.split("RATIONALE PAYLOAD:\n", 1)[1])
        request = payload["request"]
        assert request["selected_content"] == "Um..."
        assert "When I ask to change one expression" in (
            request["originals"][0]["content"]
        )
        assert payload["ruleset"]["ruleset_version"] == (
            "rationale-natural-provenance-v5"
        )
        type(self).calls += 1
        return json.dumps(
            {
                "provenance": (
                    "“Um...” began as a hesitation between a minimal-change "
                    "instruction and its “distribute, not divide” example. "
                    "Sentence chunking made it a standalone Memory; undo removed "
                    "it, redo restored it, and remove later deleted it."
                )
            },
            ensure_ascii=False,
        )


def _run_child() -> None:
    from memcommit.adapters.console.commands import rationale
    from memcommit.persistence.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="memcommit-rationale-compact-") as temp:
        _isolate_store(Path(temp))
        target_uid = _prepare_fixture()
        before = MemoryStore().load_current_direct().to_dict()
        _CaptureProvider.calls = 0
        rationale.connect_semantic_provider = _CaptureProvider
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        rationale.cmd()
        assert _CaptureProvider.calls == 1
        print(
            f"RATIONALE RECEIPT COMPLETE · TARGET [{target_uid[:8]}] · "
            "NATURAL ORIGIN + LIFECYCLE VISIBLE · PRESS V TO VERIFY"
        )
        input()
        after = MemoryStore().load_current_direct().to_dict()
        assert before == after
        print(
            f"RATIONALE VERIFIED · TARGET [{target_uid[:8]}] · "
            "CURRENT rationale/origin · PROVIDER CALLS 1 · "
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
        child.expect("RATIONALE · SELECT A MEMORY · rationale/origin")
        _BASE._settle(child)
        _snapshot(recorder, "01-target-entry")

        child.send("\t" + (DOWN * 3))
        _BASE._settle(child)
        _snapshot(recorder, "02-target-focused")

        child.send("\r")
        child.expect("RATIONALE RECEIPT COMPLETE")
        _BASE._settle(child)
        _snapshot(recorder, "03-provenance-receipt")

        child.send("v\r")
        child.expect("RATIONALE VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "04-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    plain = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.txt"))
    normalized_plain = " ".join(plain.split())
    assert "PTY 180 52" in raw
    assert "MEMORY" in plain
    assert "PROVENANCE" in plain
    assert (
        "began as a hesitation between a minimal-change instruction" in normalized_plain
    )
    assert "Sentence chunking made it a standalone Memory" in normalized_plain
    assert (
        "undo removed it, redo restored it, and remove later deleted it"
        in normalized_plain
    )
    assert "Um..." in plain
    assert "CREATED via" not in plain
    assert "RATIONALE REPORT" not in plain
    assert "APPARENT PURPOSE" not in plain
    assert "LIMITS" not in plain
    assert "Context(s)" not in plain
    assert "SAVED ANALYSIS" not in plain
    assert "EVIDENCE USED FOR INFERENCE" not in plain
    assert "STORE CONTENT UNCHANGED" in plain
    assert "PROVIDER CALLS 1" in plain
    assert "┏" in raw and "┗" in raw
    assert "38;" in raw
    assert any(
        "7" in codes.split(";") for codes in re.findall("\x1b\\[([0-9;]*)m", raw)
    )


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child()
    else:
        main()
