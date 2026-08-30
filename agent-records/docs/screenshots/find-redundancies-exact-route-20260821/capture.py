"""Capture the direct-only exact-DUP and complete-DUN CLI routes."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/find-redundancies-exact-route-20260821"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "find_redundancies_direct_capture_base",
    _BASE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _configure_isolated_store(store_root: Path) -> None:
    import memcommit.persistence.store as store_module

    values = {
        "STORE_DIR": store_root,
        "CONTEXTS_DIR": store_root / "contexts",
        "QUERY_SOURCES_DIR": store_root / "query-sources",
        "STATE_FILE": store_root / "state.json",
        "IMPACT_PLAN_FILE": store_root / "impact-plan.json",
        "STAGED_UPDATE_FILE": store_root / "staged-update.json",
        "REVIEW_SESSION_FILE": store_root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": store_root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": store_root / "atomize-workbenches",
        "GROUND_SESSIONS_DIR": store_root / "ground-sessions",
        "MELD_SESSIONS_DIR": store_root / "meld-sessions",
    }
    for name, value in values.items():
        setattr(store_module, name, value)


def _initialize() -> None:
    from memcommit.core.context import Context, Memory
    from memcommit.persistence.store import MemoryStore

    context = Context(
        uid="10000000-0000-4000-8000-000000000210",
        name="quality/exact-route",
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000210",
            content="a is apple",
        )
    )
    context.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000220",
            content="a is apple",
        )
    )
    store = MemoryStore()
    store.create_context(context)
    store.set_current(context.name)


class _ForbiddenProvider:
    def complete(self, *_args, **_kwargs) -> str:
        raise AssertionError("An exact-only frame must not connect a provider.")


def _verification() -> str:
    from memcommit.core.context import Memory
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    context = store.load_direct("quality/exact-route")
    memories = [item for item in context.iter_items() if isinstance(item, Memory)]
    return (
        f"READ-ONLY VERIFICATION · MEMORIES {len(memories)} · "
        f"CHECKPOINTS {len(store.list_checkpoints(context.name))} · "
        f"CURRENT {store.current_context_name()} · PROVIDER CALLS 0"
    )


def _invoke(app, args: list[str]) -> int:
    import click

    try:
        returned = app(args=args, prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        return error.exit_code
    return returned if isinstance(returned, int) else 0


def _run_child() -> None:
    import memcommit.adapters.console.commands.find_redundancies.command as find_command
    from memcommit.adapters.console.entrypoint import app

    with tempfile.TemporaryDirectory(
        prefix="find-redundancies-direct-route-"
    ) as directory:
        _configure_isolated_store(Path(directory) / ".mem")
        _initialize()
        find_command.connect_codex_chatgpt_provider = _ForbiddenProvider

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        print("$ mem find-duplicates")
        print(f"COMMAND EXIT · {_invoke(app, ['find-duplicates'])}")
        print("READY FOR FIND REDUNDANCIES", flush=True)
        sys.stdin.readline()

        print("$ mem find-redundancies")
        print(f"COMMAND EXIT · {_invoke(app, ['find-redundancies'])}")
        print("READY FOR VERIFICATION", flush=True)
        sys.stdin.readline()

        print(_verification(), flush=True)
        sys.stdin.readline()


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
        timeout=25,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> str:
    _BASE._snapshot(recorder, stem)
    return (OUT / f"{stem}.txt").read_text(encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    child, recorder = _spawn()
    try:
        child.expect("READY FOR FIND REDUNDANCIES")
        _BASE._settle(child)
        duplicate_report = _snapshot(recorder, "01-find-duplicates-direct")
        assert "1 exact duplicate group(s)" in duplicate_report
        assert "SURVIVOR" in duplicate_report
        assert "ABSORB" in duplicate_report
        assert "SETUP" not in duplicate_report

        child.send("\r")
        child.expect("READY FOR VERIFICATION")
        _BASE._settle(child)
        redundancy_report = _snapshot(recorder, "02-find-redundancies-direct")
        assert "DUN = DUP / EXACT + SEMANTIC DUN" in redundancy_report
        assert "1 DUP / EXACT link" in redundancy_report
        assert "0 SEMANTIC DUN links" in redundancy_report
        assert "1 connected group" in redundancy_report
        assert "SETUP" not in redundancy_report

        child.send("\r")
        child.expect("READ-ONLY VERIFICATION")
        _BASE._settle(child)
        verification = _snapshot(recorder, "03-read-only-verification")
        assert "MEMORIES 2" in verification
        assert "CHECKPOINTS 0" in verification
        assert "PROVIDER CALLS 0" in verification
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    assert "38;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child()
    else:
        main()
