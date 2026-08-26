"""Capture terminal-independent List and Contexts output in a real color PTY."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/mem-static-list-contexts-20260820"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("static_context_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _run(command: str, completion: str) -> str:
    recorder = _BASE._StreamRecorder()
    shell_command = f"""
set -eu
stty rows {ROWS} cols {COLUMNS} onlcr
printf 'LIVE COLOR PTY · '
stty size
before="$(mem pwd)"
printf 'CURRENT CONTEXT · %s\n' "$before"
printf '\n$ {command}\n'
{command}
after="$(mem pwd)"
test "$before" = "$after"
printf '\n{completion} · CURRENT UNCHANGED · %s\n' "$after"
""".strip()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", shell_command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    try:
        child.expect(completion)
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)
    return recorder.getvalue()


def _snapshot(raw: str, stem: str) -> None:
    recorder = _BASE._StreamRecorder()
    recorder.write(raw)
    _BASE._snapshot(recorder, stem)


def _first_viewport(raw: str) -> str:
    # This is an exact prefix of the real stream, equivalent to viewing the
    # first scrollback page. The complete stream remains beside the image.
    return "".join(raw.splitlines(keepends=True)[: ROWS - 2])


def _grant_viewport(raw: str) -> str:
    """Return the real stream prefix through the first ownership transition."""

    lines = raw.splitlines(keepends=True)
    first_grant = next(
        index for index, line in enumerate(lines) if "GRANT" in line
    )
    next_local_root = next(
        index
        for index, line in enumerate(lines[first_grant + 1 :], first_grant + 1)
        if re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line).strip() == "task-2"
    )
    # Replaying from command entry preserves the real cursor and wrapping
    # state; an isolated middle slice can begin after a wrapped physical row.
    return "".join(lines[: next_local_root + 2])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    list_raw = _run("mem list", "LIST COMPLETE")
    _snapshot(list_raw, "01-list-static-current-context")

    contexts_raw = _run("mem contexts", "CONTEXTS COMPLETE")
    first_page = _first_viewport(contexts_raw)
    _snapshot(first_page, "02-contexts-static-catalog-first-page")
    (OUT / "02-contexts-static-catalog-first-page.full.typescript").write_text(
        contexts_raw,
        encoding="utf-8",
    )
    _snapshot(_grant_viewport(contexts_raw), "03-contexts-grant-capabilities")
    _snapshot(contexts_raw, "04-contexts-static-catalog-verification")

    combined = list_raw + contexts_raw
    contexts_plain = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", contexts_raw)
    current_match = re.search(r"CURRENT CONTEXT · ([^\r\n]+)", list_raw)
    assert current_match is not None
    current = current_match.group(1)
    assert "52 180" in list_raw and "52 180" in contexts_raw
    assert f"Context: {current}" in list_raw
    assert f"*        {current}" in contexts_plain
    assert "GRANT  task-1/campus-wiki" in contexts_plain
    assert "READ + QUERY + EDIT + DELETE + EXPORT" in contexts_plain
    assert "PERMISSIONS" not in contexts_plain
    assert "ANALYSIS" not in contexts_plain
    context_lines = contexts_plain.splitlines()
    participant_index = next(
        index
        for index, line in enumerate(context_lines)
        if line.strip() == "task-1/participant"
    )
    campus_index = next(
        index
        for index, line in enumerate(context_lines)
        if "GRANT  task-1/campus-wiki  " in line
    )
    task_two_index = next(
        index
        for index, line in enumerate(context_lines)
        if line.strip() == "task-2"
    )
    assert participant_index < campus_index < task_two_index
    assert f"LIST COMPLETE · CURRENT UNCHANGED · {current}" in list_raw
    assert f"CONTEXTS COMPLETE · CURRENT UNCHANGED · {current}" in contexts_raw
    sgr_codes = re.findall("\x1b\\[([0-9;]*)m", combined)
    assert sgr_codes
    assert any("32" in codes.split(";") for codes in sgr_codes)
    assert "\x1b[38;2;139;213;202m" in contexts_raw


if __name__ == "__main__":
    main()
