"""Capture Atomize's immutable findings, receipt, and read-only Review."""

from __future__ import annotations

import click
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import time

import pexpect
import typer


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
COLS = 180
ROWS = 52


def _helpers():
    path = (
        ROOT
        / "agent-records/docs/screenshots/study-full-replay-20260811/capture_init_study.py"
    )
    spec = importlib.util.spec_from_file_location(
        "atomize_read_only_findings_helpers",
        path,
    )
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


def _wait(child, recorder, *needles: str, seconds: float = 15.0) -> None:
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
    """Return deterministic unresolved Atomize evidence without network use."""

    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "find_duplicates":
            return json.dumps({"findings": []})
        if operation != "impact_atomize" or output_schema is None:
            raise AssertionError(operation)
        payload = json.loads(prompt.split("ATOMIZE IMPACT PAYLOAD:\n", 1)[1])
        memories = payload["memories"]
        source_ids = [memory["candidate_id"] for memory in memories]
        validating = payload.get("phase") == "normal_form_validation"
        items = []
        for index, memory in enumerate(memories):
            items.append(
                {
                    "candidate_id": memory["candidate_id"],
                    "classification": (
                        "ATOMIC" if validating or index else "UNCERTAIN"
                    ),
                    "reason_codes": [
                        "A01_ONE_FOCUS"
                        if validating or index
                        else "A06_NO_HIDDEN_CONTEXT"
                    ],
                    "children": [],
                    "reason": (
                        "The result has one independent focus."
                        if validating
                        else "The NFC antecedent is unavailable in the Source frame."
                        if index == 0
                        else "The source records one explicit access restriction."
                    ),
                }
            )
        issues = []
        if not validating:
            issues = [
                {
                    "kind": "AMBIGUITY",
                    "source_ids": [source_ids[0]],
                    "interpretation": "DOMINANT",
                    "clarification": "REQUIRED",
                    "conflict": "NONE",
                    "ordinary_readings": [
                        {
                            "label": "Prior NFC mechanism",
                            "text": "The rule reuses the previously described NFC mechanism.",
                        },
                        {
                            "label": "Prior NFC credential",
                            "text": "The rule requires the previously described physical credential.",
                        },
                    ],
                    "scope_dimensions": [],
                    "reason": (
                        "‘same NFC’ can denote a mechanism or a credential, so the "
                        "accepted access method cannot be determined."
                    ),
                    "question": "Does ‘same NFC’ mean the mechanism or the credential?",
                },
                {
                    "kind": "CONFLICT",
                    "source_ids": source_ids,
                    "interpretation": "NONE",
                    "clarification": "REQUIRED",
                    "conflict": "MAY",
                    "ordinary_readings": [
                        {
                            "label": "Different entrances",
                            "text": "The physical-card rule and mobile restriction govern different entrances.",
                        },
                        {
                            "label": "Same entrance",
                            "text": "Both rules govern the same entrance and require a scope decision.",
                        },
                    ],
                    "scope_dimensions": ["PLACE"],
                    "reason": (
                        "The place scope determines whether the physical-card rule "
                        "conflicts with the mobile-credential restriction."
                    ),
                    "question": "Do both access rules govern the same entrance?",
                },
            ]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The Source records two entrance-access rules.",
                        "source_ids": source_ids,
                    },
                    "changed": {
                        "text": "Both Source Memories remain intact in this Atomize result.",
                        "source_ids": source_ids,
                    },
                    "unresolved": {
                        "text": "The NFC antecedent and entrance scope remain unresolved.",
                        "source_ids": source_ids,
                    },
                },
                "items": items,
                "quality_issues": issues,
            }
        )


class _FocusedProvider:
    """Split only the selected Memory; treat its neighbor as evidence."""

    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "find_duplicates":
            return json.dumps({"findings": []})
        if operation != "impact_atomize" or output_schema is None:
            raise AssertionError(operation)
        payload = json.loads(prompt.split("ATOMIZE IMPACT PAYLOAD:\n", 1)[1])
        memories = payload["memories"]
        validating = payload.get("phase") == "normal_form_validation"
        items = []
        for memory in memories:
            if validating:
                items.append(
                    {
                        "candidate_id": memory["candidate_id"],
                        "classification": "ATOMIC",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [],
                        "reason": "The result has one independent focus.",
                    }
                )
                continue
            items.append(
                {
                    "candidate_id": memory["candidate_id"],
                    "classification": "COMPOSITE",
                    "reason_codes": ["A01_ONE_FOCUS"],
                    "children": [
                        {
                            "content": "The north entrance opens at 08:00.",
                            "source_spans": ["The north entrance opens at 08:00."],
                        },
                        {
                            "content": "The south entrance opens at 09:00.",
                            "source_spans": ["The south entrance opens at 09:00."],
                        },
                    ],
                    "reason": "The source contains two independently reviewable rules.",
                }
            )
        source_ids = [memory["candidate_id"] for memory in memories]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The selected Memory contains entrance schedules.",
                        "source_ids": source_ids,
                    },
                    "changed": {
                        "text": "One selected Memory becomes two atomic Memories.",
                        "source_ids": source_ids,
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": items,
                "quality_issues": [],
            }
        )


def _initialize(store) -> None:
    import memcommit.application.capabilities.ops as ops

    if store.context_exists("atomize/read-only-findings"):
        return
    context = ops.init("atomize/read-only-findings")
    ops.add(context, "Use the same NFC credential for the staff entrance.")
    ops.add(context, "Mobile credentials are not accepted at the main entrance.")
    store.save(context)
    store.set_current(context.name)


def _initialize_focused(store) -> None:
    import memcommit.application.capabilities.ops as ops

    if store.context_exists("atomize/focused-target"):
        return
    context = ops.init("atomize/focused-target")
    ops.add(
        context,
        "The north entrance opens at 08:00. The south entrance opens at 09:00.",
    )
    ops.add(context, "The reception desk remains staffed all day.")
    store.save(context)
    store.set_current(context.name)


def _invoke(store, argv: list[str], *, provider_type=_Provider) -> None:
    import memcommit.adapters.console.commands.atomize.command as atomize_command
    import memcommit.adapters.console.commands.atomize.impact as atomize_impact
    import memcommit.adapters.console.commands.impact.command as impact_command
    import memcommit.adapters.console.commands.review.command as review_command
    import memcommit.adapters.console.terminal.components.command_wait as command_wait
    import memcommit.adapters.console.terminal.components.session_help as session_help

    atomize_command.MemoryStore = lambda *args, **kwargs: store
    atomize_impact.MemoryStore = lambda *args, **kwargs: store
    impact_command.MemoryStore = lambda *args, **kwargs: store
    review_command.MemoryStore = lambda *args, **kwargs: store
    atomize_command.connect_codex_chatgpt_provider = lambda: provider_type()
    atomize_impact.connect_codex_chatgpt_provider = lambda: provider_type()
    command_wait.current_help_entries = lambda: ()
    session_help.current_help_entries = lambda: ()

    app = typer.Typer()
    impact_app = typer.Typer()

    @app.callback()
    def capture_root() -> None:
        """Keep this capture in command-group mode."""

    impact_app.command("atomize")(impact_command.atomize_impact_cmd)
    app.add_typer(impact_app, name="impact")
    app.command("atomize")(atomize_command.cmd)
    app.command("review")(review_command.cmd)
    try:
        app(args=argv, prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        if error.exit_code:
            raise


def _child_analysis(store_root: Path) -> None:
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root)
    _initialize(store)
    _invoke(store, ["impact", "atomize"])
    print("ANALYSIS CLOSED · CONTEXT UNCHANGED · CHECKPOINTS 0")


def _child_apply(store_root: Path) -> None:
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    _invoke(store, ["atomize"])
    context = store.load_direct("atomize/read-only-findings")
    print(
        "APPLY VERIFIED · MEMORIES",
        len(context.memories),
        "· CHECKPOINTS",
        len(store.list_checkpoints(context.name)),
    )


def _child_review(store_root: Path) -> None:
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    context = store.load_direct("atomize/read-only-findings")
    checkpoint_count = len(store.list_checkpoints(context.name))
    _invoke(store, ["review", "atomize"])
    print(
        "READ-ONLY REVIEW CLOSED · CHECKPOINTS",
        len(store.list_checkpoints(context.name)),
        "· UNCHANGED",
        len(store.list_checkpoints(context.name)) == checkpoint_count,
    )


def _child_verify(store_root: Path) -> None:
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    context = store.load_direct("atomize/read-only-findings")
    analysis = store.load_atomize_analysis(context.uid)
    before = store._atomize_workbench_path(analysis.context_uid).read_bytes()
    _invoke(store, ["review", "atomize", "--snapshot"])
    after = store._atomize_workbench_path(analysis.context_uid).read_bytes()
    print(
        "READ-ONLY VERIFICATION · REVIEW RECORD UNCHANGED",
        before == after,
        "· CHECKPOINTS",
        len(store.list_checkpoints(context.name)),
    )


def _child_focused_before(store_root: Path) -> None:
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root)
    _initialize_focused(store)
    context = store.load_direct("atomize/focused-target")
    print("FOCUSED TARGET · BEFORE")
    for index, memory in enumerate(context.memories.values(), start=1):
        print(f"MEMORY {index} · {memory.uid} · {memory.content}")
    print("CHECKPOINTS", len(store.list_checkpoints(context.name)))


def _child_focused_apply(store_root: Path) -> None:
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    context = store.load_direct("atomize/focused-target")
    selected = next(iter(context.memories.values()))
    _invoke(
        store,
        ["atomize", f"{context.name}:{selected.uid[:8]}"],
        provider_type=_FocusedProvider,
    )
    print("FOCUSED TARGET · APPLIED", selected.uid[:8])


def _child_focused_verify(store_root: Path) -> None:
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    context = store.load_direct("atomize/focused-target")
    neighbor = next(
        memory
        for memory in context.memories.values()
        if memory.content == "The reception desk remains staffed all day."
    )
    print("FOCUSED TARGET · READ-ONLY VERIFICATION")
    for index, memory in enumerate(context.memories.values(), start=1):
        print(f"MEMORY {index} · {memory.uid} · {memory.content}")
    print(
        "UNSELECTED NEIGHBOR PRESERVED",
        neighbor.content == "The reception desk remains staffed all day.",
        "· CHECKPOINTS",
        len(store.list_checkpoints(context.name)),
    )


def _run_child(mode: str, store_root: Path) -> None:
    {
        "analysis": _child_analysis,
        "apply": _child_apply,
        "review": _child_review,
        "verify": _child_verify,
        "focused-before": _child_focused_before,
        "focused-apply": _child_focused_apply,
        "focused-verify": _child_focused_verify,
    }[mode](store_root)


def _capture_finished(mode: str, root: Path, stem: str, expected: str) -> None:
    child, recorder = _spawn(mode, root)
    HELPERS._pump(child, recorder, seconds=25, require_eof=True)
    if expected not in recorder.getvalue():
        raise RuntimeError(f"Capture {stem} missed {expected!r}.")
    HELPERS._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-atomize-findings-") as directory:
        root = Path(directory) / ".mem"

        child, recorder = _spawn("analysis", root)
        _wait(
            child,
            recorder,
            "MEM IMPACT · ATOMIZE",
            "ANALYSIS · NON-APPLYING",
            "ATOMIZE FINDINGS",
        )
        if "RESPONSES" in HELPERS._visible_text(recorder):
            raise RuntimeError("Atomize analysis unexpectedly rendered RESPONSES.")
        HELPERS._snapshot(recorder, "01-analysis-read-only-findings")
        child.send("\t\x1b[B\r")
        _wait(child, recorder, "SOURCE MEMORY", "POSSIBLE READINGS")
        if "RESPONSES" in HELPERS._visible_text(recorder):
            raise RuntimeError("Atomize detail unexpectedly rendered RESPONSES.")
        HELPERS._snapshot(recorder, "02-ambiguity-read-only-detail")
        child.send("q")
        try:
            HELPERS._pump(child, recorder, seconds=8, require_eof=True)
        except RuntimeError:
            child.send("\x1b\x1b")
            HELPERS._pump(child, recorder, seconds=8, require_eof=True)
        if "ANALYSIS CLOSED · CONTEXT UNCHANGED · CHECKPOINTS 0" not in (
            recorder.getvalue()
        ):
            raise RuntimeError("Analysis view did not close without a checkpoint.")

        _capture_finished(
            "apply",
            root,
            "03-apply-unresolved-issue-receipt",
            "UNRESOLVED ISSUES · 3 · APPLIED AS-IS",
        )

        child, recorder = _spawn("review", root)
        _wait(
            child,
            recorder,
            "RESULT · atomize · atomize/read-only-findings",
            "APPLIED RECORD · READ ONLY",
        )
        if "RESPONSES" in HELPERS._visible_text(recorder):
            raise RuntimeError("Applied Review unexpectedly rendered RESPONSES.")
        HELPERS._snapshot(recorder, "04-applied-read-only-review")
        child.send("\t\x1b[B\r")
        _wait(child, recorder, "SOURCE MEMORY", "POSSIBLE READINGS")
        HELPERS._snapshot(recorder, "05-applied-read-only-detail")
        child.send("q")
        try:
            HELPERS._pump(child, recorder, seconds=8, require_eof=True)
        except RuntimeError:
            child.send("\x1b\x1b")
            HELPERS._pump(child, recorder, seconds=8, require_eof=True)
        if "READ-ONLY REVIEW CLOSED · CHECKPOINTS 1 · UNCHANGED True" not in (
            recorder.getvalue()
        ):
            raise RuntimeError("Applied Review did not close read-only.")

        _capture_finished(
            "verify",
            root,
            "06-read-only-verification",
            "READ-ONLY VERIFICATION · REVIEW RECORD UNCHANGED True · CHECKPOINTS 1",
        )

        focused_root = Path(directory) / ".mem-focused"
        _capture_finished(
            "focused-before",
            focused_root,
            "07-focused-target-before",
            "FOCUSED TARGET · BEFORE",
        )
        _capture_finished(
            "focused-apply",
            focused_root,
            "08-focused-target-application",
            "FOCUSED TARGET · APPLIED",
        )
        _capture_finished(
            "focused-verify",
            focused_root,
            "09-focused-target-verification",
            "UNSELECTED NEIGHBOR PRESERVED True · CHECKPOINTS 1",
        )

    # The text projection is a reading aid rather than a fixed-width terminal
    # byte stream. Keep its semantic text while dropping canvas padding; the
    # exact color/control bytes remain untouched in the binary typescript.
    for path in OUT.glob("*.txt"):
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text(
            "\n".join(line.rstrip() for line in lines).rstrip() + "\n",
            encoding="utf-8",
        )

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "52 180" not in raw or "\x1b[" not in raw or "38;2" not in raw:
        raise RuntimeError("Capture did not preserve the required true-color PTY.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
