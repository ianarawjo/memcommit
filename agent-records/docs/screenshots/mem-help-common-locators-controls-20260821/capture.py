"""Capture shared locator syntax and real Help controls in a color PTY."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shlex
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/mem-help-common-locators-controls-20260821"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT
_BASE.COLUMNS = 180
_BASE.ROWS = 52


def _close(child: object) -> None:
    child.send("q")
    child.expect(_BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def _spawn_plain(executable: str):
    argv = shlex.join([executable, "help"])
    command = (
        f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}; stty size; "
        f"exec {argv} </dev/null | rg '^(edit|embed|reference) '"
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
    _BASE._pump(child, seconds=0.9)
    entry = _BASE._snapshot(recorder, "01-common-locators-and-keys")
    assert "COMMON LOCATORS" in entry
    assert "../PATH" in entry
    assert "CONTEXT:UID" in entry
    assert "../3:ca562047" in entry
    assert "PgUp / PgDn" in entry
    assert "Esc / Q / Ctrl-C" in entry

    child.send("\x1b[Z")
    _BASE._pump(child)
    view = _BASE._snapshot(recorder, "02-view-arrow-focus")
    assert "INVENTORY VIEW" in view
    assert "VIEW: ←/→ choose" in view

    child.send("\x1b[Z" + "\x1b[C" * 3)
    _BASE._pump(child)
    korean = _BASE._snapshot(recorder, "03-korean-locator-and-key-guide")
    assert "✓ KO" in korean
    assert "직접 소유 Context와 Memory UID 또는 prefix를 구분" in korean
    assert "앞이나 뒤로 10행 이동" in korean
    _BASE._assert_color(recorder.getvalue())
    _close(child)

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)
    child.send("\t" + "\x1b[B" * 5 + "\x1b[C" + "\x1b[B" * 2)
    _BASE._pump(child, seconds=0.8)
    qualified = _BASE._snapshot(recorder, "04-embed-qualified-locator-form")
    assert "▾ mem embed" in qualified
    assert "mem embed [UID]" in qualified
    assert "mem embed [source_context]:[UID]" in qualified
    assert "Target defaults to current Context" in qualified

    child.send("\x1b[B" * 4)
    _BASE._pump(child)
    compatibility = _BASE._snapshot(recorder, "05-embed-from-compatibility-form")
    assert "--from [source_context]" in compatibility
    assert "compatibility live Memory link" in compatibility
    _BASE._assert_color(recorder.getvalue())
    _close(child)

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)
    child.send("\t" + "\x1b[B" * 4 + "\x1b[C" + "\x1b[B" * 2)
    _BASE._pump(child, seconds=0.8)
    reference = _BASE._snapshot(recorder, "06-reference-qualified-locator-form")
    assert "▾ mem reference" in reference
    assert "mem reference [UID]" in reference
    assert "mem reference [source_context]:[UID]" in reference
    assert "Target defaults to current Context" in reference
    _BASE._assert_color(recorder.getvalue())
    _close(child)

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)
    child.send("\t" * 3 + "\x1b[C")
    _BASE._pump(child, seconds=0.8)
    edit = _BASE._snapshot(recorder, "07-edit-qualified-locator-form")
    assert "▾ mem edit" in edit
    assert "mem edit [UID_or_CONTEXT:UID]" in edit
    _BASE._assert_color(recorder.getvalue())
    _close(child)

    child, recorder = _spawn_plain(executable)
    child.expect(_BASE.pexpect.EOF, timeout=10)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    verification = _BASE._snapshot(recorder, "08-plain-read-only-verification")
    assert "edit" in verification
    assert "embed" in verification
    assert "reference" in verification


if __name__ == "__main__":
    main()
