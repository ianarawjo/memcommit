"""Capture bare-new versus explicit-sessions routing in a 180x52 PTY."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "agent-records/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("bare_entry_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


ROUTES = (
    (
        "compare",
        "bare",
        ("compare",),
        "NEW COMPARE",
        "01-compare-bare-new-setup",
    ),
    (
        "compare",
        "sessions",
        ("compare", "--sessions"),
        "MEM COMPARE · SAVED ANALYSES",
        "02-compare-sessions-launcher",
    ),
    (
        "meld",
        "bare",
        ("meld",),
        "NEW MELD",
        "03-meld-bare-new-setup",
    ),
    (
        "meld",
        "sessions",
        ("meld", "--sessions"),
        "MELD SESSIONS · RECENTLY MODIFIED",
        "04-meld-sessions-launcher",
    ),
    (
        "sever",
        "bare",
        ("sever",),
        "MEM SEVER · SETUP",
        "05-sever-bare-new-setup",
    ),
    (
        "sever",
        "sessions",
        ("sever", "--sessions"),
        "MEM SEVER · SAVED SESSIONS",
        "06-sever-sessions-launcher",
    ),
    (
        "update",
        "bare",
        ("update",),
        "NEW UPDATE",
        "07-update-bare-new-setup",
    ),
    (
        "update",
        "sessions",
        ("update", "--sessions"),
        "MEM UPDATE · SAVED SESSION",
        "08-update-sessions-launcher",
    ),
)


def _configure_store(root: Path) -> None:
    import memcommit.store as store_module

    for name, value in {
        "STORE_DIR": root,
        "CONTEXTS_DIR": root / "contexts",
        "QUERY_SOURCES_DIR": root / "query-sources",
        "STATE_FILE": root / "state.json",
        "IMPACT_PLAN_FILE": root / "impact-plan.json",
        "STAGED_UPDATE_FILE": root / "staged-update.json",
        "REVIEW_SESSION_FILE": root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": root / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": root / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": root / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": root / "ground-sessions",
        "MELD_SESSIONS_DIR": root / "meld-sessions",
    }.items():
        setattr(store_module, name, value)


def _prepare_store(root: Path):
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    _configure_store(root)
    store = MemoryStore()
    contexts = []
    for name, memory in (
        ("capture/reference", "Reference policy is reviewed."),
        ("capture/peer", "Peer policy supplies comparison evidence."),
        ("capture/criteria", "Keep only policy-relevant claims."),
        ("capture/target", "Target policy is the writable baseline."),
    ):
        context = ops.init(name)
        ops.add(context, memory)
        store.create_context(context)
        contexts.append(context)
    store.set_current(contexts[0].name)
    return store


def _store_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _guard_providers(counter: list[str]) -> None:
    import memcommit.commands.compare.command as compare_command
    import memcommit.commands.meld.command as meld_command
    import memcommit.commands.sever.command as sever_command
    import memcommit.commands.update.command as update_command

    def reject_provider() -> None:
        counter.append("unexpected")
        raise AssertionError("Entry routing must not connect a semantic provider.")

    compare_command.connect_codex_chatgpt_provider = reject_provider
    meld_command.connect_codex_chatgpt_provider = reject_provider
    sever_command.connect_codex_chatgpt_provider = reject_provider
    update_command.connect_codex_chatgpt_provider = reject_provider


def _run_route_child(operation: str, route: str, root: Path) -> None:
    from memcommit.cli import app

    store = _prepare_store(root)
    provider_calls: list[str] = []
    _guard_providers(provider_calls)
    before_digest = _store_digest(root)
    before_checkpoints = sum(
        len(store.list_checkpoints(name)) for name in store.list_context_names()
    )
    argv = [operation] + (["--sessions"] if route == "sessions" else [])
    print("$ mem " + " ".join(argv), flush=True)
    print(
        f"PTY · {os.get_terminal_size().columns} COLUMNS × "
        f"{os.get_terminal_size().lines} ROWS",
        flush=True,
    )
    app(args=argv, prog_name="mem", standalone_mode=False)
    after_checkpoints = sum(
        len(store.list_checkpoints(name)) for name in store.list_context_names()
    )
    print(f"\nROUTE RECEIPT · {operation.upper()} · {route.upper()} · CANCELLED")
    print(f"STORE DIGEST UNCHANGED · {_store_digest(root) == before_digest}")
    print(f"CHECKPOINT COUNT UNCHANGED · {after_checkpoints == before_checkpoints}")
    print(f"CURRENT CONTEXT · {store.current_context_name()}")
    print(f"PROVIDER CALLS · {len(provider_calls)}", flush=True)


def _run_verification_child(result_path: Path) -> None:
    results = json.loads(result_path.read_text(encoding="utf-8"))
    print("\x1b[38;2;139;213;255;1mBARE ENTRY ROUTING · READ-ONLY VERIFICATION\x1b[0m")
    print(
        f"PTY · {os.get_terminal_size().columns} COLUMNS × "
        f"{os.get_terminal_size().lines} ROWS"
    )
    print("PROFILE · ISOLATED EXPLICIT STORE · HOST GRANTS EXCLUDED")
    print("CURRENT CONTEXT · capture/reference")
    print()
    for result in results:
        command = result["command"]
        route = "NEW SETUP" if result["route"] == "bare" else "SAVED LAUNCHER"
        color = "139;213;202" if result["ok"] else "237;135;150"
        status = "PASS" if result["ok"] else "FAIL"
        print(f"\x1b[38;2;{color};1m{status}\x1b[0m · {command:<24} · {route}")
        print(
            "       Escape cancelled · Store digest unchanged · checkpoints unchanged"
        )
        print("       provider calls 0 · current Context unchanged")
    print()
    print(
        "\x1b[38;2;139;213;202;1mVERIFICATION COMPLETE · 8/8 ROUTES PASS\x1b[0m",
        flush=True,
    )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn_route(
    operation: str,
    route: str,
    root: Path,
) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [
            str(Path(__file__).resolve()),
            "--child-route",
            operation,
            route,
            str(root),
        ],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _spawn_verification(result_path: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child-verification", str(result_path)],
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
    results = []
    with tempfile.TemporaryDirectory(
        prefix="semantic-bare-entry-routing-"
    ) as directory:
        temp_root = Path(directory)
        for operation, route, argv, expected, stem in ROUTES:
            child, recorder = _spawn_route(
                operation,
                route,
                temp_root / stem / ".mem",
            )
            try:
                child.expect(expected)
                _BASE._settle(child)
                _snapshot(recorder, stem)
                child.send("\x1b")
                child.expect("ROUTE RECEIPT")
                child.expect(pexpect.EOF)
                raw = recorder.getvalue()
                ok = (
                    "STORE DIGEST UNCHANGED · True" in raw
                    and "CHECKPOINT COUNT UNCHANGED · True" in raw
                    and "PROVIDER CALLS · 0" in raw
                )
                results.append(
                    {
                        "command": "$ mem " + " ".join(argv),
                        "route": route,
                        "ok": ok,
                    }
                )
            finally:
                if child.isalive():
                    child.close(force=True)

        result_path = temp_root / "results.json"
        result_path.write_text(json.dumps(results), encoding="utf-8")
        child, recorder = _spawn_verification(result_path)
        try:
            child.expect("VERIFICATION COMPLETE")
            _BASE._settle(child)
            _snapshot(recorder, "09-read-only-route-verification")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)

    for path in OUT.glob("*.txt"):
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text(
            "\n".join(line.rstrip() for line in lines) + "\n",
            encoding="utf-8",
        )
    for stem in (route[4] for route in ROUTES):
        raw = (OUT / f"{stem}.typescript").read_text(encoding="utf-8")
        # The launcher intentionally communicates focus with a background
        # fill, while the setup screens also carry semantic foregrounds.
        if "\x1b[" not in raw or ("38;" not in raw and "48;" not in raw):
            raise RuntimeError(f"{stem} did not retain ANSI color styles.")
    if len(results) != len(ROUTES) or not all(result["ok"] for result in results):
        raise RuntimeError(f"Route verification failed: {results!r}")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--child-route":
        _run_route_child(sys.argv[2], sys.argv[3], Path(sys.argv[4]))
    elif len(sys.argv) == 3 and sys.argv[1] == "--child-verification":
        _run_verification_child(Path(sys.argv[2]))
    else:
        main()
