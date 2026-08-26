"""Capture live natural-language Help lookup results in a real PTY."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import shlex
import shutil
import sys

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/screenshots/mem-help-natural-language-20260820"
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "agent-records/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


CASES = (
    (
        "01-ranked-compare",
        "두 Context의 차이를 보고 싶어",
        ("mem compare",),
    ),
    (
        "02-ranked-compare-search",
        "두 Context를 비교하고 관련 Memories도 의미로 찾고 싶어",
        ("mem compare", "mem search"),
    ),
    (
        "03-ranked-metaphorical-conflict",
        "메모리들이 서로 싸우고 있는지 좀 봐줘",
        ("mem find-conflicts",),
    ),
    (
        "04-ranked-unrelated",
        "🦆 보라색 냉장고가 달에서 왈츠를 춘다 ??? 123",
        (),
    ),
    (
        "05-ranked-generic-answer-language-query",
        "답 해결할 수 있는 문장",
        ("mem query",),
    ),
)

THINKING_REQUEST = "how can I update those campus wiki from mine?"


def _spawn_lookup(
    executable: str,
    request: str,
) -> tuple[pexpect.spawn, object]:
    argv = shlex.join([executable, "help", request])
    # Keep the size check in the raw stream, then clear it from the terminal
    # canvas so each image contains only the command's final visible result.
    command = (
        f"stty rows {ROWS} cols {COLUMNS}; stty size; "
        "printf '\\033[2J\\033[H'; "
        f"exec {argv}"
    )
    recorder = _BASE._Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_BASE._environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=60,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _assert_focused_contract(plain: str, expected_names: tuple[str, ...]) -> None:
    for name in expected_names:
        assert name in plain
    positions = [plain.index(name) for name in expected_names]
    assert positions == sorted(positions)
    ordered_names = re.findall(
        r"(?m)^mem ([a-z][a-z0-9-]*) ",
        plain,
    )
    assert len(ordered_names) == 3
    assert len(set(ordered_names)) == 3
    assert "WHEN ·" in plain
    for forbidden in (
        "WHY",
        "FLOW",
        "EFFECT",
        "FORM 1",
        "Overview",
        "Command line",
    ):
        assert forbidden not in plain


def _capture_lookup(
    executable: str,
    *,
    stem: str,
    request: str,
    expected_names: tuple[str, ...],
) -> None:
    child, recorder = _spawn_lookup(executable, request)
    child.expect(pexpect.EOF, timeout=60)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    raw = recorder.getvalue()
    assert "52 180" in raw
    plain = _BASE._snapshot(recorder, stem)
    _assert_focused_contract(plain, expected_names)


def _capture_thinking_path(executable: str) -> None:
    """Capture the transient liveness line and its cleared final result."""

    child, recorder = _spawn_lookup(executable, THINKING_REQUEST)
    child.expect("MEM HELP · 1/1 · THINKING", timeout=15)
    thinking = _BASE._snapshot(recorder, "00a-campus-wiki-thinking")
    assert "MEM HELP · 1/1 · THINKING" in thinking

    child.expect(pexpect.EOF, timeout=60)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    raw = recorder.getvalue()
    assert "52 180" in raw
    result = _BASE._snapshot(recorder, "00b-campus-wiki-result")
    _assert_focused_contract(result, ("mem update",))
    assert "THINKING" not in result


def _capture_study_copy_block(executable: str) -> None:
    from memcommit.help_application import describe_operation

    request = describe_operation("query").summary
    child, recorder = _spawn_lookup(executable, request)
    child.expect(pexpect.EOF, timeout=15)
    child.close()
    assert child.exitstatus == 1, (child.exitstatus, child.signalstatus)
    raw = recorder.getvalue()
    assert "52 180" in raw
    plain = _BASE._snapshot(recorder, "06-study-exact-copy-blocked")
    assert "Study lookup requires original task wording" in plain
    assert "at least 50%" in plain
    assert "mem query" not in plain


def _verify_color_capable_help(executable: str) -> None:
    """Prove missing focused-row color is an application choice, not the PTY."""

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)
    raw = recorder.getvalue()
    assert "52 180" in raw
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None
    child.send("q")
    child.expect(pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.interfaces.tui.operations.help.study_copy_guard import (
        active_profile_is_study,
    )

    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    if not active_profile_is_study():
        raise RuntimeError("capture requires an active init-study Profile")
    OUT.mkdir(parents=True, exist_ok=True)

    _verify_color_capable_help(executable)
    _capture_thinking_path(executable)
    for stem, request, expected_names in CASES:
        _capture_lookup(
            executable,
            stem=stem,
            request=request,
            expected_names=expected_names,
        )
    _capture_study_copy_block(executable)


if __name__ == "__main__":
    main()
