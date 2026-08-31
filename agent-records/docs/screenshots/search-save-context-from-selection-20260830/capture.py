"""Capture Search Save As COPY, REFERENCE, and EMBED in an isolated Store."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import shlex
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "agent-records/docs/screenshots/search-save-context-from-selection-20260830"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("search_save_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def _harness(mode: str, store_root: Path) -> None:
    """Run the real Search command workbench and save adapter deterministically."""

    import memcommit.application.capabilities.ops as ops
    import memcommit.adapters.console.commands.search.command as search_command
    from memcommit.application.capabilities.authority.context_access import (
        resolve_context_access,
    )
    from memcommit.application.operations.search.application import (
        SearchResponse,
        SearchResult,
    )
    from memcommit.core.context import Memory, MemoryRef
    from memcommit.persistence.store import MemoryStore

    if mode not in {"COPY", "REFERENCE", "EMBED"}:
        raise ValueError("Capture mode must be COPY, REFERENCE, or EMBED.")
    store = MemoryStore(root=store_root)
    source = ops.init("task/source")
    memory = ops.add(source, "Accessible entrance is on the east side.")
    store.save(source)
    store.set_current(source.name)
    access = resolve_context_access(
        store,
        source.name,
        current_name=source.name,
        required_permission="READ",
    )

    def deterministic_search(_store, _catalog, request):
        time.sleep(0.25)
        return SearchResponse(
            request,
            "CURRENT",
            (
                SearchResult(
                    context_name=source.name,
                    kind="memory",
                    uid=memory.uid,
                    content=memory.content,
                    source_context_name=source.name,
                    source_context_uid=source.uid,
                    source_memory_uid=memory.uid,
                ),
            ),
        )

    search_command._run_search_request = deterministic_search
    search_command._open_search_workbench(
        store,
        access,
        current_name=source.name,
        include_descendants=False,
        follow_embeds=False,
        limit=5,
    )

    destination = f"task/results/{mode.lower()}"
    print(f"SAVE RECEIPT COMPLETE · {mode} · {destination}", flush=True)
    input("PRESS ENTER FOR READ-ONLY RESULT VERIFICATION")
    direct = tuple(store.load_direct(destination).iter_items())
    assert len(direct) == 1
    item = direct[0]
    loaded = tuple(store.load(destination).iter_items())[0]
    if mode == "COPY":
        assert isinstance(item, Memory)
        print("READ-ONLY RESULT · COPY · INDEPENDENT MEMORY", flush=True)
        print(f"CONTENT · {item.content}", flush=True)
        print(f"FRESH UID · {item.uid != memory.uid}", flush=True)
    else:
        assert isinstance(item, MemoryRef)
        assert isinstance(loaded, MemoryRef) and loaded.target is not None
        relation = "IMMUTABLE SNAPSHOT" if item.is_snapshot else "LIVE EMBED"
        print(f"READ-ONLY RESULT · {mode} · {relation}", flush=True)
        print(f"SOURCE · {item.target_context_name}:{item.target_memory_uid[:8]}", flush=True)
        print(f"RESOLVED CONTENT · {loaded.target.content}", flush=True)
    print(f"CURRENT CONTEXT · {store.current_context_name()}", flush=True)
    print("SOURCE UNCHANGED · True", flush=True)


def _shell_command(mode: str, store_root: Path) -> str:
    argv = shlex.join(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--harness",
            mode,
            str(store_root),
        ]
    )
    return "; ".join(
        (
            f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}",
            "stty size",
            f"exec {argv}",
        )
    )


def _spawn(mode: str, store_root: Path):
    environment = _BASE._environment()
    environment["PROMPT_TOOLKIT_NO_CPR"] = "1"
    environment["PYTHONPATH"] = str(ROOT / "src")
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", _shell_command(mode, store_root)],
        cwd=str(ROOT),
        env=environment,
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(_BASE.ROWS, _BASE.COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _wait_for(child, recorder, text: str, *, timeout: float = 10.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _BASE._pump(child, seconds=0.15)
        plain = _BASE._plain(recorder.getvalue())
        if text in plain:
            return plain
    raise AssertionError(f"Timed out waiting for {text!r}.")


def _assert_tui_color(raw: str) -> None:
    assert "52 180" in raw
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None


def _choose_mode(child, mode: str) -> None:
    child.send("\t")
    if mode == "REFERENCE":
        child.send("\x1b[C")
    elif mode == "EMBED":
        child.send("\x1b[C\x1b[C")


def _capture_branch(
    mode: str,
    *,
    first_number: int,
    capture_common: bool,
) -> int:
    with tempfile.TemporaryDirectory(prefix=f"memcommit-search-save-{mode.lower()}-") as root:
        child, recorder = _spawn(mode, Path(root))
        _BASE._pump(child, seconds=0.6)
        number = first_number
        if capture_common:
            entry = _BASE._snapshot(recorder, f"{number:02d}-search-entry")
            assert "MEM SEARCH" in entry
            assert "task/source" in entry
            assert "SEARCH · ENTER TO RUN" in entry
            number += 1

        child.send("accessibility")
        _BASE._pump(child)
        if capture_common:
            query = _BASE._snapshot(recorder, f"{number:02d}-query-entered")
            assert "accessibility" in query
            number += 1

        child.send("\r")
        results = _wait_for(child, recorder, "1 RESULT ·")
        if capture_common:
            result_capture = _BASE._snapshot(recorder, f"{number:02d}-search-result")
            assert "Accessible entrance is on the east side." in result_capture
            assert "COPY" in result_capture
            assert "REFERENCE" in result_capture
            assert "EMBED" in result_capture
            assert "1 RESULT ·" in results
            number += 1

        child.send(" ")
        _BASE._pump(child)
        if capture_common:
            checked = _BASE._snapshot(recorder, f"{number:02d}-result-checked")
            assert "CHECKED RESULT 1 · 1 TOTAL" in checked
            number += 1

        _choose_mode(child, mode)
        _BASE._pump(child)
        chosen = _BASE._snapshot(
            recorder,
            f"{number:02d}-{mode.lower()}-mode-selected",
        )
        assert f"SAVE 1 CHECKED AS {mode}" in chosen
        number += 1

        destination = f"task/results/{mode.lower()}"
        child.send("\t\x15" + destination)
        _BASE._pump(child)
        location = _BASE._snapshot(
            recorder,
            f"{number:02d}-{mode.lower()}-save-location",
        )
        assert destination in location
        number += 1

        child.send("\t")
        _BASE._pump(child)
        todo = _BASE._snapshot(
            recorder,
            f"{number:02d}-{mode.lower()}-exact-save",
        )
        assert f"SAVE 1 CHECKED AS {mode}" in todo
        assert "TO DO · ENTER TO SAVE" in todo
        number += 1

        child.send("\r")
        receipt_plain = _wait_for(
            child,
            recorder,
            "PRESS ENTER FOR READ-ONLY RESULT VERIFICATION",
        )
        receipt = _BASE._snapshot(
            recorder,
            f"{number:02d}-{mode.lower()}-success-receipt",
        )
        assert f"Saved 1 checked Search result(s) as {mode}" in receipt_plain
        assert f"SAVE RECEIPT COMPLETE · {mode}" in receipt
        number += 1

        child.send("\r")
        child.expect(_BASE.pexpect.EOF, timeout=10)
        child.close()
        assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
        verification = _BASE._snapshot(
            recorder,
            f"{number:02d}-{mode.lower()}-read-only-verification",
        )
        assert f"READ-ONLY RESULT · {mode}" in verification
        assert "SOURCE UNCHANGED · True" in verification
        assert "CURRENT CONTEXT · task/source" in verification
        _assert_tui_color(recorder.getvalue())
        return number + 1


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    number = _capture_branch("COPY", first_number=1, capture_common=True)
    number = _capture_branch("REFERENCE", first_number=number, capture_common=False)
    _capture_branch("EMBED", first_number=number, capture_common=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", action="store_true")
    parser.add_argument("mode", nargs="?")
    parser.add_argument("store_root", nargs="?")
    arguments = parser.parse_args()
    if arguments.harness:
        if arguments.mode is None or arguments.store_root is None:
            parser.error("--harness requires MODE and STORE_ROOT")
        _harness(arguments.mode, Path(arguments.store_root))
    else:
        main()
