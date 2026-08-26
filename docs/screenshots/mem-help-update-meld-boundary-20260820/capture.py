"""Capture the shared Update-versus-Meld Help boundary in a real PTY."""

from __future__ import annotations

import importlib
from pathlib import Path
import shlex
import shutil
import sys


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-help-update-meld-boundary-20260820"
sys.path.insert(0, str(ROOT / "src"))
HELP_CATEGORY_GROUPS = importlib.import_module(
    "memcommit.commands.help_inventory.command"
).HELP_CATEGORY_GROUPS

_BASE_PATH = ROOT / "docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def _close(child: object) -> None:
    child.send("q")
    child.expect(_BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def _spawn_public_verification() -> tuple[object, object]:
    code = (
        "from memcommit.help_application import describe_operation_detail; "
        "[(print(name, detail.kind.value), print(detail.body)) "
        "for name in ('update', 'meld') "
        "for detail in (describe_operation_detail(name, 'update-vs-meld'),)]"
    )
    command = (
        f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}; stty size; "
        f"exec python -c {shlex.quote(code)}"
    )
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_BASE._environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=10,
        dimensions=(_BASE.ROWS, _BASE.COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)

    semantic_commands = next(
        commands
        for category, commands in HELP_CATEGORY_GROUPS
        if category == "SEMANTIC TRANSFORMATIONS"
    )
    update_steps = semantic_commands.index("update")

    # Move from the initial Browse category to Semantic Transformations, then
    # from Atomize to Update.
    child.send("\t" * 4 + "\x1b[B" * update_steps)
    _BASE._pump(child, seconds=0.8)
    entry = _BASE._snapshot(recorder, "01-update-meld-collapsed")
    assert "▸ mem update" in entry
    assert "UPDATE VS. MELD" not in entry
    _BASE._assert_color(recorder.getvalue())

    child.send("\x1b[C")
    _BASE._pump(child, seconds=0.8)
    update = _BASE._snapshot(recorder, "02-update-note-expanded")
    assert "▾ mem update" in update
    assert "UPDATE VS. MELD" in update
    assert "Update is revision-oriented" in update
    assert "Meld is merge-oriented" in update

    child.send("\x1b[D")
    _BASE._pump(child, seconds=0.3)
    child.send("\x1b[B")
    _BASE._pump(child, seconds=0.3)
    child.send("\x1b[C")
    _BASE._pump(child, seconds=0.8)
    meld = _BASE._snapshot(recorder, "03-meld-note-expanded")
    assert "▾ mem meld" in meld
    assert "UPDATE VS. MELD" in meld
    assert "Update is revision-oriented" in meld
    assert "Meld is merge-oriented" in meld
    _close(child)

    verify_child, verify_recorder = _spawn_public_verification()
    verify_child.expect(_BASE.pexpect.EOF, timeout=10)
    verify_child.close()
    assert verify_child.exitstatus == 0, (
        verify_child.exitstatus,
        verify_child.signalstatus,
    )
    verification = _BASE._snapshot(
        verify_recorder,
        "04-read-only-public-verification",
    )
    assert "update SEMANTIC_BOUNDARY" in verification
    assert "meld SEMANTIC_BOUNDARY" in verification
    assert verification.count("Update is revision-oriented") == 2
    assert verification.count("Meld is merge-oriented") == 2


if __name__ == "__main__":
    main()
