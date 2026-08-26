"""Capture stored Memory/Context inputs entering general Fit."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
ROWS = 52
COLUMNS = 180

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_module("fit_stored_sources_capture_base", BASE_PATH)
BASE.OUT = OUT


class _Provider:
    calls = 0

    def __init__(self, *, delay: float = 0.0) -> None:
        self.delay = delay

    def complete(self, prompt, *, operation, output_schema=None):
        from memcommit.fit_judgment import FIT_JUDGMENT_PAYLOAD_MARKER

        type(self).calls += 1
        assert operation == "fit_propositions"
        if self.delay:
            time.sleep(self.delay)
        payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
        question = payload["questions"][0]
        aliases = [
            item["proposition_id"]
            for item in (*question["background"], *question["propositions"])
        ]
        return json.dumps(
            {
                "overview": "The exact stored claims were judged together.",
                "judgments": [
                    {
                        "question_id": "fit",
                        "verdict": "YES",
                        "reason": (
                            "The lobby closure and side-entrance access can "
                            "jointly hold."
                        ),
                        "considered_proposition_ids": aliases,
                        "material_proposition_ids": [],
                        "consistent_reading": "",
                        "inconsistent_reading": "",
                    }
                ],
            }
        )


def _use_store_root(root: Path) -> None:
    import memcommit.store as store_module

    store_module.STORE_DIR = root


def _prepare_store(root: Path):
    import memcommit.ops as ops
    from memcommit.store import MemoryStore, context_record_digest

    store = MemoryStore(root=root)
    current = ops.init("fit/current")
    selected = ops.add(current, "The lobby closes at five.")
    policies = ops.init("fit/policies")
    policy = ops.add(policies, "Visitors may use the side entrance after five.")
    store.create_context(current)
    store.create_context(policies)
    store.set_current(current.name)
    digests = {
        current.name: context_record_digest(current),
        policies.name: context_record_digest(policies),
    }
    return store, current, selected, policies, policy, digests


def _print_verification(store, current, policies, digests) -> None:
    from memcommit.commands import show as show_command
    from memcommit.fit_store import FitStore
    from memcommit.store import context_record_digest

    print("VIEWER CLOSED · READ-ONLY VERIFICATION")
    print("$ mem show --context fit/current")
    show_command.cmd(None, context_name=current.name)
    print("$ mem show --context fit/policies")
    show_command.cmd(None, context_name=policies.name)
    current_after = store.load_direct(current.name)
    policies_after = store.load_direct(policies.name)
    print(
        "  CURRENT UNCHANGED · "
        f"{context_record_digest(current_after) == digests[current.name]}"
    )
    print(
        "  POLICIES UNCHANGED · "
        f"{context_record_digest(policies_after) == digests[policies.name]}"
    )
    print(f"  FIT RECEIPTS · {len(FitStore(store).list())}")
    print(f"  PROVIDER CALLS · {_Provider.calls}", flush=True)


def _run_viewer_child(store_root: Path) -> None:
    import memcommit.commands.fit.command as fit_command

    _Provider.calls = 0
    _use_store_root(store_root)
    store, current, selected, policies, _policy, digests = _prepare_store(store_root)
    fit_command.connect_semantic_provider = lambda: _Provider(delay=0.8)
    print(
        f"$ mem fit {selected.uid[:8]} {policies.name} --tui",
        flush=True,
    )
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    fit_command.cmd(
        [selected.uid[:8], policies.name],
        background=None,
        memory_sources=None,
        context_sources=None,
        ground_name=None,
        receipt=None,
        plain=False,
        tui=True,
    )
    _print_verification(store, current, policies, digests)


def _run_overlap_child(store_root: Path) -> None:
    import click
    import memcommit.commands.fit.command as fit_command
    from memcommit.fit_store import FitStore
    from memcommit.store import context_record_digest

    _Provider.calls = 0
    _use_store_root(store_root)
    store, current, selected, _policies, _policy, digests = _prepare_store(store_root)

    def forbidden_provider():
        _Provider.calls += 1
        raise RuntimeError("Overlap capture must fail before provider construction.")

    fit_command.connect_semantic_provider = forbidden_provider
    print(
        f"$ mem fit {selected.uid[:8]} {current.name} --plain",
        flush=True,
    )
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    try:
        fit_command.cmd(
            [selected.uid[:8], current.name],
            background=None,
            memory_sources=None,
            context_sources=None,
            ground_name=None,
            receipt=None,
            plain=True,
            tui=False,
        )
    except click.exceptions.Exit as error:
        print(f"EXIT · {error.exit_code}")
    current_after = store.load_direct(current.name)
    print("OVERLAP FAILURE · READ-ONLY VERIFICATION")
    print(
        "  CURRENT UNCHANGED · "
        f"{context_record_digest(current_after) == digests[current.name]}"
    )
    print(f"  PROVIDER CALLS · {_Provider.calls}")
    print(f"  FIT RECEIPTS · {len(FitStore(store).list())}")
    print("CAPTURE GATE · PRESS V", flush=True)
    sys.stdin.read(1)


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


def _spawn(kind: str, store_root: Path):
    recorder = BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture_viewer(store_root: Path) -> None:
    child, recorder = _spawn("viewer", store_root)
    try:
        BASE._settle(child, seconds=0.3)
        BASE._snapshot(recorder, "01-provider-running")
        BASE._settle(child, seconds=1.2)
        BASE._snapshot(recorder, "02-judgment-entry")
        child.send("\x1b[B")
        BASE._settle(child, seconds=0.25)
        BASE._snapshot(recorder, "03-frozen-stored-inputs")
        child.send("q")
        child.expect("VIEWER CLOSED")
        child.expect("PROVIDER CALLS .* 1")
        child.expect(pexpect.EOF)
        BASE._snapshot(recorder, "04-close-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_overlap(store_root: Path) -> None:
    child, recorder = _spawn("overlap", store_root)
    try:
        child.expect("CAPTURE GATE")
        BASE._settle(child, seconds=0.2)
        BASE._snapshot(recorder, "05-overlap-blocked-before-provider")
        child.send("v\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-fit-stored-") as directory:
        root = Path(directory)
        _capture_viewer(root / "viewer")
        _capture_overlap(root / "overlap")
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain true-color ANSI styles.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        root = Path(sys.argv[3])
        if kind == "viewer":
            _run_viewer_child(root)
        elif kind == "overlap":
            _run_overlap_child(root)
        else:
            raise RuntimeError(f"Unknown capture kind: {kind}")
    else:
        main()
