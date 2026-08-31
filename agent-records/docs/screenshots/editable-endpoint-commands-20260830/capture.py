"""Capture every editable Endpoint Setup command in real 180x52 color PTYs."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("endpoint_command_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _print_terminal() -> None:
    size = os.get_terminal_size()
    print(f"PTY · {size.columns} columns × {size.lines} rows", flush=True)
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError("Capture PTY dimensions are not 180×52.")


def _update() -> None:
    from memcommit.adapters.console.commands.update.workbench.model import (
        UpdateEndpointSetup,
    )
    from memcommit.adapters.console.commands.update.workbench.setup import (
        choose_update_endpoint_setup,
    )

    _print_terminal()
    result = choose_update_endpoint_setup(
        UpdateEndpointSetup(
            names=("capture/source", "capture/target"),
            source_name="capture/source",
            target_name="capture/target",
            current_context="capture/source",
        ),
        memory_loader=lambda _role, _name: (),
    )
    print(f"\nSETUP RECEIPT · UPDATE · {result!r}")
    print("PROVIDER CALLS · 0 · DURABLE STATE · UNCHANGED", flush=True)


def _branch() -> None:
    from memcommit.adapters.console.commands.create_copy_connect.branch.endpoint_setup import choose_branch_creation

    _print_terminal()
    result = choose_branch_creation(
        ("capture/alpha", "capture/beta"),
        current="capture/alpha",
        suggest_name=lambda source: f"{source}/branch",
        validate_name=lambda _name: None,
    )
    print(f"\nSETUP RECEIPT · BRANCH · {result!r}")
    print("CONTEXTS CREATED · 0 · CURRENT CONTEXT · UNCHANGED", flush=True)


def _meld() -> None:
    from memcommit.adapters.console.commands.meld.endpoint_setup import (
        MeldTuiSetup,
        choose_meld_endpoint_setup,
    )

    _print_terminal()
    result = choose_meld_endpoint_setup(
        MeldTuiSetup(
            names=(
                "capture/incoming",
                "capture/baseline",
                "capture/empty",
            ),
            left_name="capture/incoming",
            right_name="capture/baseline",
            eligible_target_names=frozenset({"capture/empty"}),
            current_context="capture/incoming",
        ),
        memory_loader=lambda _role, _name: (),
    )
    print(f"\nSETUP RECEIPT · MELD · {result!r}")
    print("PROVIDER CALLS · 0 · SESSION · NOT STARTED · DURABLE STATE · UNCHANGED", flush=True)


def _sever() -> None:
    from memcommit.adapters.console.commands.sever.endpoint_setup import (
        SeverTuiSetup,
        choose_sever_endpoint_setup,
    )

    _print_terminal()
    result = choose_sever_endpoint_setup(
        SeverTuiSetup(
            names=("capture/source", "capture/criteria"),
            local_names=("capture/source",),
            selectable_names=frozenset({"capture/source", "capture/criteria"}),
            source_name="capture/source",
            criteria_name="capture/criteria",
            current_context="capture/source",
        )
    )
    print(f"\nSETUP RECEIPT · SEVER · {result!r}")
    print("PROVIDER CALLS · 0 · SESSION · NOT STARTED · DURABLE STATE · UNCHANGED", flush=True)


def _child(kind: str) -> None:
    {"update": _update, "branch": _branch, "meld": _meld, "sever": _sever}[kind]()


def _spawn(kind: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
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


def _capture_update() -> None:
    child, recorder = _spawn("update")
    try:
        child.expect("NEW UPDATE")
        _BASE._settle(child)
        _snapshot(recorder, "01-update-entry")
        child.send("\x1b[B" * 2 + "\x15--from capture/target --to missing")
        _BASE._settle(child)
        _snapshot(recorder, "02-update-invalid-command")
        child.send(
            "\x15--from capture/target --to capture/source "
            "--source-descendants"
        )
        _BASE._settle(child)
        _snapshot(recorder, "03-update-command-reprojects-upper-fields")
        child.send("\r")
        child.expect("SETUP RECEIPT .* UPDATE")
        child.expect("DURABLE STATE .* UNCHANGED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "04-update-receipt-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_simple(
    kind: str,
    title: str,
    keys_to_command: str,
    arguments: str,
    stems: tuple[str, str, str],
) -> None:
    child, recorder = _spawn(kind)
    try:
        child.expect(title)
        _BASE._settle(child)
        _snapshot(recorder, stems[0])
        child.send(keys_to_command + "\x15" + arguments)
        _BASE._settle(child)
        _snapshot(recorder, stems[1])
        child.send("\r")
        child.expect(f"SETUP RECEIPT .* {kind.upper()}")
        child.expect("UNCHANGED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, stems[2])
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_update()
    _capture_simple(
        "branch",
        "MEM BRANCH",
        "\t" * 5,
        "capture/beta/new-branch --from capture/beta --source-descendants",
        (
            "05-branch-entry",
            "06-branch-command-reprojects-upper-fields",
            "07-branch-receipt-verification",
        ),
    )
    _capture_simple(
        "meld",
        "NEW MELD",
        "\t" * 9,
        "capture/baseline capture/incoming --left-descendants",
        (
            "08-meld-entry",
            "09-meld-command-reprojects-upper-fields",
            "10-meld-receipt-verification",
        ),
    )
    _capture_simple(
        "sever",
        "NEW SEVER",
        "\x1b[B" * 3,
        "capture/criteria capture/source capture/result --criteria-descendants",
        (
            "11-sever-entry",
            "12-sever-command-reprojects-upper-fields",
            "13-sever-receipt-verification",
        ),
    )
    raw = (OUT / "01-update-entry.typescript").read_text(encoding="utf-8")
    if "\x1b[" not in raw or "38;" not in raw:
        raise RuntimeError("Capture did not retain expected ANSI foreground styles.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _child(sys.argv[2])
    else:
        main()
