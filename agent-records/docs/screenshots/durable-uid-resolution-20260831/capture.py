"""Capture Find, Search, and Query durable-UID lookup in a real color PTY."""

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
OUT = ROOT / "agent-records/docs/screenshots/durable-uid-resolution-20260831"
MEMORY_UID = "11111111-1111-4111-8111-111111111111"
CONTEXT_UID = "22222222-2222-4222-8222-222222222222"
CONTENT = "Durable UID lookup returns this authorized Memory."

_BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("durable_uid_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def _build_store(store_root: Path):
    from memcommit.core.context import AutoCheckpoint, Context, Memory
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root)
    context = Context(uid=CONTEXT_UID, name="uid-demo")
    context.add(Memory(uid=MEMORY_UID, content=CONTENT))
    store.save(
        context,
        AutoCheckpoint(command="add", args={}, description="UID capture fixture"),
    )
    store.set_current(context.name)
    return store, context


def _catalog(store, context):
    from memcommit.application.context_access.access import resolve_context_access
    from memcommit.application.context_access.readable_contexts import freeze_readable_context_catalog

    access = resolve_context_access(
        store,
        context.name,
        current_name=context.name,
        required_permission="READ",
    )
    return access, freeze_readable_context_catalog(store, access)


def _find_harness(store_root: Path) -> None:
    from memcommit.adapters.console.commands.find.workbench import (
        FindTuiSetup,
        run_find_workbench,
    )
    from memcommit.application.operations.find.runtime import execute_find

    store, context = _build_store(store_root)
    _access, catalog = _catalog(store, context)
    before = store.list_checkpoints(context.name)
    run_find_workbench(
        None,
        setup=FindTuiSetup(
            names=tuple(catalog.list_context_names()),
            current_name=context.name,
            initial_targets=(context.name,),
        ),
        execute=lambda request: execute_find(request, catalog=catalog),
        local_context_names=tuple(store.list_context_names()),
        validate_save_location=store.assert_context_creatable,
    )
    unchanged = store.list_checkpoints(context.name) == before
    print(f"FIND UID READ-ONLY VERIFICATION · CHECKPOINTS UNCHANGED {unchanged}", flush=True)
    print(f"SOURCE · {context.name} [{MEMORY_UID}] · {CONTENT}", flush=True)


def _search_harness(store_root: Path) -> None:
    import memcommit.adapters.console.commands.search.command as search_command

    store, context = _build_store(store_root)
    access, _catalog_value = _catalog(store, context)
    before = store.list_checkpoints(context.name)

    def fail_provider():
        raise AssertionError("UID Search constructed a provider")

    search_command.connect_search_provider = fail_provider
    search_command._open_search_workbench(
        store,
        access,
        current_name=context.name,
        include_descendants=False,
        follow_embeds=False,
        limit=5,
    )
    unchanged = store.list_checkpoints(context.name) == before
    print(f"SEARCH UID READ-ONLY VERIFICATION · CHECKPOINTS UNCHANGED {unchanged}", flush=True)
    print(f"SOURCE · {context.name} [{MEMORY_UID}] · {CONTENT}", flush=True)


def _query_harness(store_root: Path) -> None:
    from memcommit.adapters.console.commands.query.workbench import run_query_workbench
    from memcommit.application.operations.query.ordinary_runtime import execute_ordinary_query

    store, context = _build_store(store_root)
    _access, catalog = _catalog(store, context)
    before = store.list_checkpoints(context.name)

    def fail_provider():
        raise AssertionError("UID Query constructed a provider")

    run_query_workbench(
        tuple(catalog.list_context_names()),
        current_context=context.name,
        initial_context=context.name,
        query_targets=(),
        run_ordinary=lambda request: execute_ordinary_query(
            request,
            store=store,
            catalog=catalog,
            provider_factory=fail_provider,
        ),
        run_granted=lambda _request: None,
        local_context_names=tuple(store.list_context_names()),
        validate_save_location=store.assert_context_creatable,
    )
    unchanged = store.list_checkpoints(context.name) == before
    print(f"QUERY UID READ-ONLY VERIFICATION · CHECKPOINTS UNCHANGED {unchanged}", flush=True)
    print(f"SOURCE · {context.name} [{MEMORY_UID}] · {CONTENT}", flush=True)


def _shell_command(operation: str, store_root: Path) -> str:
    argv = shlex.join(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--harness",
            operation,
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


def _spawn(operation: str, store_root: Path):
    environment = _BASE._environment()
    environment["PROMPT_TOOLKIT_NO_CPR"] = "1"
    environment["PYTHONPATH"] = str(ROOT / "src")
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", _shell_command(operation, store_root)],
        cwd=str(ROOT),
        env=environment,
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(_BASE.ROWS, _BASE.COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _wait_for(child, recorder, text: str, *, timeout: float = 12.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _BASE._pump(child, seconds=0.15)
        plain = _BASE._plain(recorder.getvalue())
        if text in plain:
            return plain
    raise AssertionError(
        f"Timed out waiting for {text!r}.\n{_BASE._plain(recorder.getvalue())}"
    )


def _assert_color(raw: str) -> None:
    assert "52 180" in raw
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None


def _capture_operation(operation: str, first: int) -> int:
    with tempfile.TemporaryDirectory(prefix=f"memcommit-{operation}-uid-") as root:
        child, recorder = _spawn(operation, Path(root))
        number = first
        title = {"find": "MEM FIND", "search": "MEM SEARCH", "query": "MEM QUERY"}[
            operation
        ]
        _wait_for(child, recorder, title)
        _BASE._pump(child, seconds=0.6)
        _BASE._snapshot(recorder, f"{number:02d}-{operation}-entry")
        number += 1

        child.send(MEMORY_UID[:8])
        _BASE._pump(child, seconds=0.35)
        typed = _BASE._snapshot(recorder, f"{number:02d}-{operation}-uid-input")
        assert MEMORY_UID[:8] in typed
        number += 1

        child.send("\r")
        expected = {
            "find": "UID MATCH",
            "search": CONTENT,
            "query": f"UID {MEMORY_UID} identifies memory",
        }[operation]
        result = _wait_for(child, recorder, expected)
        assert CONTENT in result
        _BASE._snapshot(recorder, f"{number:02d}-{operation}-uid-result")
        number += 1

        child.sendcontrol("c")
        verification = _wait_for(
            child,
            recorder,
            f"{operation.upper()} UID READ-ONLY VERIFICATION",
        )
        assert "CHECKPOINTS UNCHANGED True" in verification
        _BASE._snapshot(recorder, f"{number:02d}-{operation}-read-only-verification")
        number += 1
        child.expect(_BASE.pexpect.EOF, timeout=8)
        child.close()
        assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
        _assert_color(recorder.getvalue())
        return number


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    number = 1
    for operation in ("find", "search", "query"):
        number = _capture_operation(operation, number)


def _run_harness(operation: str, store_root: Path) -> None:
    {"find": _find_harness, "search": _search_harness, "query": _query_harness}[
        operation
    ](store_root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", choices=("find", "search", "query"))
    parser.add_argument("store_root", nargs="?", type=Path)
    arguments = parser.parse_args()
    if arguments.harness is not None:
        assert arguments.store_root is not None
        _run_harness(arguments.harness, arguments.store_root)
    else:
        main()
