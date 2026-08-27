"""Capture Atomize saved/prepared/provider open in a 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import time

import pexpect
import typer

try:  # Typer 0.27+ vendors Click.
    from typer import _click as click
except ImportError:  # pragma: no cover - older supported Typer
    import click


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLS = 180
ROWS = 52


def _helpers():
    path = (
        ROOT
        / "agent-records/docs/screenshots/study-full-replay-20260811/capture_init_study.py"
    )
    spec = importlib.util.spec_from_file_location("atomize_open_capture_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load PTY capture helpers.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    module.COLS = COLS
    module.ROWS = ROWS
    return module


HELPERS = _helpers()


def _environment() -> dict[str, str]:
    environment = HELPERS._environment()
    environment["PYTHONPATH"] = str(ROOT / "src")
    environment["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    return environment


def _spawn(mode: str, store_root: Path):
    command = (
        f"stty rows {ROWS} cols {COLS}; stty size; "
        f"exec {shlex.join([sys.executable, str(__file__), '--child', mode, str(store_root)])}"
    )
    recorder = HELPERS._Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _wait(child, recorder, *needles: str, seconds: float = 12.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        HELPERS._pump(child, recorder, seconds=0.1)
        visible = HELPERS._visible_text(recorder)
        if all(needle in visible for needle in needles):
            return
        if not child.isalive():
            break
    raise RuntimeError(
        f"PTY did not reach {needles!r}:\n{HELPERS._visible_text(recorder)}"
    )


class _Provider:
    def __init__(self, *, delay: float = 0.0, label: str = "provider"):
        self.delay = delay
        self.label = label

    def complete(self, prompt, *, operation, output_schema=None):
        if operation != "impact_atomize" or output_schema is None:
            raise AssertionError(operation)
        if self.delay:
            time.sleep(self.delay)
        payload = json.loads(prompt.split("ATOMIZE IMPACT PAYLOAD:\n", 1)[1])
        ids = [item["candidate_id"] for item in payload["memories"]]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": f"{self.label} analyzed one independent fact.",
                        "source_ids": ids,
                    },
                    "changed": {
                        "text": "No Memory needs to be split.",
                        "source_ids": ids,
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": [
                    {
                        "candidate_id": uid,
                        "classification": "ATOMIC",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [],
                        "reason": "The source has one independently revisable focus.",
                    }
                    for uid in ids
                ],
                "quality_issues": [],
            }
        )


def _initialize(store):
    import memcommit.application.ops as ops

    if store.context_exists("atomize/open-boundary"):
        return
    context = ops.init("atomize/open-boundary")
    ops.add(context, "The library entrance closes at five.")
    store.save(context)
    store.set_current(context.name)


def _invoke_impact(store, provider_factory, *, refresh: bool = False) -> int:
    import memcommit.commands.impact.command as impact_command
    import memcommit.commands.shared.session_help as session_help

    impact_command.MemoryStore = lambda *args, **kwargs: store
    impact_command.connect_codex_chatgpt_provider = provider_factory
    # Help inventory itself is outside this focused flow; prevent the minimal
    # capture app from pretending it owns the repository-wide command catalog.
    session_help.current_help_entries = lambda: ()
    app = typer.Typer()

    @app.callback()
    def capture_root() -> None:
        """Keep this capture in command-group mode."""

    app.command("impact")(impact_command.cmd)
    args = ["impact", "atomize", "--context", "atomize/open-boundary"]
    if refresh:
        args.append("--refresh")
    try:
        result = app(args=args, prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        return error.exit_code
    return result if isinstance(result, int) else 0


def _child_provider(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _initialize(store)
    code = _invoke_impact(
        store,
        lambda: _Provider(delay=3.0, label="provider"),
    )
    analysis = store.load_atomize_analysis(
        store.load_direct("atomize/open-boundary").uid
    )
    print("PROVIDER CREATE · EXIT", code, "· SAVED", analysis is not None)


def _child_saved(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    before = store.load_atomize_analysis(store.load_direct("atomize/open-boundary").uid)
    code = _invoke_impact(
        store,
        lambda: (_ for _ in ()).throw(AssertionError("saved resume opened a provider")),
    )
    after = store.load_atomize_analysis(store.load_direct("atomize/open-boundary").uid)
    print("SAVED RESUME · EXIT", code, "· SAME ANALYSIS", before.uid == after.uid)


def _child_prepared(store_root: Path) -> None:
    import memcommit.atomize_analysis_runtime as runtime
    from memcommit.atomize import create_atomize_analysis, impact_atomize
    from memcommit.store import MemoryStore
    from memcommit.study_scenarios.legacy.prewarm.atomize import AtomizePrewarmMatch

    store = MemoryStore(root=store_root)
    _initialize(store)
    context = store.load_direct("atomize/open-boundary")
    prepared = create_atomize_analysis(
        context,
        impact_atomize(context, lambda: _Provider(label="prepared")),
    )
    runtime.find_declared_atomize_prewarm = lambda *, store, context: (
        AtomizePrewarmMatch(
            entry_key="capture/atomize",
            analysis=prepared,
            output_context_name="atomize/prepared-output",
        )
    )
    code = _invoke_impact(
        store,
        lambda: (_ for _ in ()).throw(
            AssertionError("exact prewarm opened a provider")
        ),
    )
    saved = store.load_atomize_analysis(context.uid)
    workbench = store.load_atomize_workbench(saved)
    print(
        "PREPARED MATERIALIZATION · EXIT",
        code,
        "· SAME ANALYSIS",
        saved == prepared,
        "· OUTPUT",
        workbench.output_context_name,
    )


def _child_refresh(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    context = store.load_direct("atomize/open-boundary")
    before = store.load_atomize_analysis(context.uid)
    code = _invoke_impact(
        store,
        lambda: _Provider(delay=3.0, label="refresh"),
        refresh=True,
    )
    after = store.load_atomize_analysis(context.uid)
    print("REFRESH · EXIT", code, "· NEW ANALYSIS", before.uid != after.uid)


def _child_stale(store_root: Path) -> None:
    from memcommit.atomize_analysis_application import AtomizeAnalysisOpenRequest
    from memcommit.atomize_analysis_runtime import execute_atomize_analysis_open
    from memcommit.context import Memory
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _initialize(store)
    context = store.load_direct("atomize/open-boundary")
    first = execute_atomize_analysis_open(
        AtomizeAnalysisOpenRequest(context=context),
        store=store,
        provider_factory=lambda: _Provider(label="initial"),
    )
    changed = store.load_for_update(context.name)
    memory = next(item for item in changed.iter_items() if isinstance(item, Memory))
    changed.replace(Memory(uid=memory.uid, content="The entrance now closes at six."))
    store.save(changed)
    code = _invoke_impact(
        store,
        lambda: (_ for _ in ()).throw(AssertionError("stale resume opened a provider")),
    )
    retained = store.load_atomize_analysis(context.uid)
    print(
        "STALE REJECTION · EXIT",
        code,
        "· ORIGINAL RETAINED",
        retained.uid == first.analysis.uid,
    )


def _child_publication_failure(store_root: Path) -> None:
    from memcommit.atomize_analysis_application import AtomizeAnalysisOpenRequest
    from memcommit.atomize_analysis_runtime import execute_atomize_analysis_open
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _initialize(store)
    context = store.load_direct("atomize/open-boundary")
    first = execute_atomize_analysis_open(
        AtomizeAnalysisOpenRequest(context=context),
        store=store,
        provider_factory=lambda: _Provider(label="initial"),
    )
    original_save = MemoryStore.save_atomize_workbench

    def fail_replacement(self, workbench):
        if workbench.analysis_uid != first.analysis.uid:
            raise OSError("injected workbench publication failure")
        return original_save(self, workbench)

    MemoryStore.save_atomize_workbench = fail_replacement
    code = _invoke_impact(
        store,
        lambda: _Provider(label="replacement"),
        refresh=True,
    )
    retained = store.load_atomize_analysis(context.uid)
    workbench = store.load_atomize_workbench(retained)
    print(
        "PAIR RESTORATION · EXIT",
        code,
        "· ORIGINAL ANALYSIS",
        retained.uid == first.analysis.uid,
        "· ORIGINAL WORKBENCH",
        workbench.uid == first.workbench.uid,
    )


def _run_child(mode: str, store_root: Path) -> None:
    {
        "provider": _child_provider,
        "saved": _child_saved,
        "prepared": _child_prepared,
        "refresh": _child_refresh,
        "stale": _child_stale,
        "publication-failure": _child_publication_failure,
    }[mode](store_root)


def _capture_finished(mode: str, root: Path, stem: str, expected: str) -> None:
    child, recorder = _spawn(mode, root)
    try:
        HELPERS._pump(child, recorder, seconds=25, require_eof=True)
    except RuntimeError as error:
        raise RuntimeError(
            f"Capture {stem} failed:\n{HELPERS._visible_text(recorder)}"
        ) from error
    if expected not in recorder.getvalue():
        raise RuntimeError(f"Capture {stem} missed {expected!r}.")
    HELPERS._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-atomize-open-") as directory:
        root = Path(directory) / ".mem"
        child, recorder = _spawn("provider", root)
        _wait(child, recorder, "IMPACT ATOMIZE", "ANALYZING MEMORY STRUCTURE")
        HELPERS._snapshot(recorder, "01-provider-analysis-pending")
        _wait(child, recorder, "WHAT MEM UNDERSTOOD", "ACTIONABLE FINDINGS")
        HELPERS._snapshot(recorder, "02-provider-analysis-workbench")
        child.send("q")
        HELPERS._pump(child, recorder, seconds=15, require_eof=True)
        if "PROVIDER CREATE · EXIT 0 · SAVED True" not in recorder.getvalue():
            raise RuntimeError("Provider analysis did not publish one saved pair.")
        HELPERS._snapshot(recorder, "03-provider-analysis-receipt")

        child, recorder = _spawn("saved", root)
        _wait(child, recorder, "WHAT MEM UNDERSTOOD", "ACTIONABLE FINDINGS")
        HELPERS._snapshot(recorder, "04-saved-resume-workbench")
        child.send("q")
        HELPERS._pump(child, recorder, seconds=15, require_eof=True)
        if "SAVED RESUME · EXIT 0 · SAME ANALYSIS True" not in recorder.getvalue():
            raise RuntimeError("Saved resume changed or re-created the analysis.")
        HELPERS._snapshot(recorder, "05-saved-resume-receipt")

        prepared_root = Path(directory) / "prepared"
        child, recorder = _spawn("prepared", prepared_root)
        _wait(child, recorder, "WHAT MEM UNDERSTOOD", "prepared analyzed")
        HELPERS._snapshot(recorder, "06-exact-prewarm-workbench")
        child.send("q")
        HELPERS._pump(child, recorder, seconds=15, require_eof=True)
        if (
            "PREPARED MATERIALIZATION · EXIT 0 · SAME ANALYSIS True"
            not in recorder.getvalue()
        ):
            raise RuntimeError("Exact prewarm did not materialize provider-free.")
        HELPERS._snapshot(recorder, "07-exact-prewarm-receipt")

        child, recorder = _spawn("refresh", root)
        _wait(child, recorder, "IMPACT ATOMIZE", "ANALYZING MEMORY STRUCTURE")
        HELPERS._snapshot(recorder, "08-explicit-refresh-pending")
        _wait(child, recorder, "WHAT MEM UNDERSTOOD", "refresh analyzed")
        child.send("q")
        HELPERS._pump(child, recorder, seconds=15, require_eof=True)
        if "REFRESH · EXIT 0 · NEW ANALYSIS True" not in recorder.getvalue():
            raise RuntimeError("Explicit refresh did not publish a new analysis.")
        HELPERS._snapshot(recorder, "09-explicit-refresh-receipt")

        _capture_finished(
            "stale",
            Path(directory) / "stale",
            "10-stale-saved-analysis-rejected",
            "STALE REJECTION · EXIT 1 · ORIGINAL RETAINED True",
        )
        _capture_finished(
            "publication-failure",
            Path(directory) / "publication-failure",
            "11-pair-publication-failure-restored",
            "PAIR RESTORATION · EXIT 1 · ORIGINAL ANALYSIS True · ORIGINAL WORKBENCH True",
        )

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "52 180" not in raw or "\x1b[" not in raw or "38;2" not in raw:
        raise RuntimeError("Capture did not preserve the required true-color PTY.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
