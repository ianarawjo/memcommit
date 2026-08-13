"""Capture decision-free Update and Atomize approval in a real 180x52 PTY."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLS = 180
ROWS = 52


def _load_capture_helpers():
    path = (
        ROOT
        / "docs"
        / "screenshots"
        / "study-full-replay-20260811"
        / "capture_init_study.py"
    )
    spec = importlib.util.spec_from_file_location("memcommit_capture_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the shared PTY capture helpers.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    module.COLS = COLS
    module.ROWS = ROWS
    return module


HELPERS = _load_capture_helpers()


def _capture_environment() -> dict[str, str]:
    environment = HELPERS._environment()
    environment["PYTHONPATH"] = str(ROOT)
    return environment


def _spawn_child(mode: str, store_root: Path):
    command = (
        f"stty rows {ROWS} cols {COLS}; stty size; "
        f"exec {shlex.join([sys.executable, str(__file__), '--child', mode, str(store_root)])}"
    )
    recorder = HELPERS._Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_capture_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _wait_for(child, recorder, *needles: str, seconds: float = 12.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        HELPERS._pump(child, recorder, seconds=0.12)
        visible = HELPERS._visible_text(recorder)
        if all(needle in visible for needle in needles):
            return
        if not child.isalive():
            break
    raise RuntimeError(
        "PTY did not reach expected state: "
        + ", ".join(repr(needle) for needle in needles)
        + "\n"
        + HELPERS._visible_text(recorder)
    )


def _finish(child, recorder) -> None:
    HELPERS._pump(child, recorder, seconds=10, require_eof=True)


class _UpdateProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        if operation != "update planning":
            raise AssertionError(operation)
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        source_id = payload["source"]["memories"][0]["source_id"]
        target = payload["target"]["memories"][0]
        return json.dumps(
            {
                "edits": [
                    {
                        "target_id": target["target_id"],
                        "new_content": (
                            "The south entrance is open and provides step-free access."
                        ),
                        "source_ids": [source_id],
                        "reason": "The verified access note supersedes the old route.",
                    }
                ],
                "additions": [],
                "removals": [],
            }
        )


class _AtomizeProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        if operation != "impact_atomize":
            raise AssertionError(operation)
        payload = json.loads(prompt.split("ATOMIZE IMPACT PAYLOAD:\n", 1)[1])
        source_id = payload["memories"][0]["candidate_id"]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The note specifies an NFC-based access instruction.",
                        "source_ids": [source_id],
                    },
                    "changed": {
                        "text": "The original Memory remains intact.",
                        "source_ids": [source_id],
                    },
                    "unresolved": {
                        "text": "The antecedent of same NFC remains unresolved.",
                        "source_ids": [source_id],
                    },
                },
                "items": [
                    {
                        "candidate_id": source_id,
                        "classification": "UNCERTAIN",
                        "reason_codes": ["A06_NO_HIDDEN_CONTEXT"],
                        "children": [],
                        "reason": (
                            "Same NFC has no local antecedent, so a safe standalone "
                            "claim cannot be determined."
                        ),
                    }
                ],
                "quality_issues": [
                    {
                        "kind": "AMBIGUITY",
                        "source_ids": [source_id],
                        "interpretation": "DOMINANT",
                        "clarification": "REQUIRED",
                        "conflict": "NONE",
                        "ordinary_readings": [
                            {
                                "label": "Prior NFC mechanism",
                                "text": "Use the previously described NFC mechanism.",
                            },
                            {
                                "label": "Prior NFC credential",
                                "text": "Accept the previously described credential.",
                            },
                        ],
                        "scope_dimensions": [],
                        "reason": (
                            "Same NFC can denote a mechanism or a credential."
                        ),
                        "question": "Does same NFC mean the mechanism or credential?",
                    }
                ],
            }
        )


def _new_context(*, uid: str, name: str, memory_uid: str, content: str):
    from memcommit.context import Context, Memory

    context = Context(uid=uid, name=name)
    context.add(Memory(uid=memory_uid, content=content))
    return context


def _child_update(store_root: Path) -> None:
    from memcommit.commands.update_render import review_update_application
    from memcommit.store import MemoryStore
    from memcommit.update import plan_update

    store = MemoryStore(root=store_root)
    source = _new_context(
        uid="11111111-1111-4111-8111-111111111111",
        name="study/direct-final/source",
        memory_uid="22222222-2222-4222-8222-222222222222",
        content="Use the south entrance for step-free access.",
    )
    target = _new_context(
        uid="33333333-3333-4333-8333-333333333333",
        name="study/direct-final/update-target",
        memory_uid="44444444-4444-4444-8444-444444444444",
        content="The north entrance provides public access.",
    )
    store.save(source)
    store.save(target)
    session = plan_update(source, target, _UpdateProvider, status="staged")
    store.save_staged_update(session, expected_current=None)
    reviewed = review_update_application(
        session,
        incorporate=lambda *_args: (_ for _ in ()).throw(
            AssertionError("The capture does not submit a revision.")
        ),
    )
    if reviewed is None:
        print("UPDATE CLOSED · STAGED RECEIPT RETAINED")
        return
    applied = store.apply_staged_update(reviewed)
    print("\x1b[38;2;166;218;149mUPDATE APPLICATION RECEIPT\x1b[0m")
    print(f"STATUS · {applied.status.upper()}")
    print("TARGET · study/direct-final/update-target")
    print("EXPLICIT FINAL APPROVAL · RECORDED")


def _child_verify_update(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    context = store.load_direct("study/direct-final/update-target")
    memory = next(iter(context.memories.values()))
    session = store.load_staged_update()
    checkpoints = store.list_checkpoints(context.name)
    print("\x1b[38;2;138;173;244mREAD-ONLY UPDATE VERIFICATION\x1b[0m")
    print(f"STATUS · {session.status.upper()}")
    print(f"MEMORY · {memory.content}")
    print(f"UPDATE CHECKPOINTS · {sum(c.get('command') == 'update' for c in checkpoints)}")


def _child_atomize(store_root: Path) -> None:
    from memcommit.atomize import apply_atomize_analysis, create_atomize_analysis, impact_atomize
    from memcommit.atomize_workbench import create_atomize_workbench
    from memcommit.commands.atomize import (
        _atomize_application_audit,
        _record_atomize_workbench_application,
    )
    from memcommit.commands.atomize_workbench_shell import run_atomize_workbench_shell
    from memcommit.context import AutoCheckpoint
    from memcommit.resolution_workbench import ResolutionWorkbenchAction
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    context = _new_context(
        uid="55555555-5555-4555-8555-555555555555",
        name="study/direct-final/atomize-target",
        memory_uid="66666666-6666-4666-8666-666666666666",
        content="Use the same NFC for access.",
    )
    store.save(context)
    analysis = create_atomize_analysis(
        context,
        impact_atomize(context, _AtomizeProvider),
    )
    workbench = create_atomize_workbench(analysis)
    store.save_atomize_analysis(analysis)
    store.save_atomize_workbench(workbench)
    action = run_atomize_workbench_shell(
        workbench,
        analysis,
        save=store.save_atomize_workbench,
        workflow_actions=True,
    )
    if not isinstance(action, ResolutionWorkbenchAction) or action.kind != "ACCEPT":
        print("ATOMIZE CLOSED · ANALYSIS RETAINED")
        return
    audit = _atomize_application_audit(analysis, workbench)
    current = store.load_for_update(context.name)
    result = apply_atomize_analysis(current, analysis)
    store.save(
        current,
        AutoCheckpoint(
            command="atomize",
            args={
                "analysis_uid": analysis.uid,
                "split_count": result.split_count,
                "child_count": result.child_count,
                "preserved_count": result.preserved_count,
                **audit,
                "trace": result.trace_metadata(),
            },
            description=(
                "Applied decision-free Atomize capture with one unresolved finding."
            ),
        ),
    )
    _record_atomize_workbench_application(
        store=store,
        analysis=analysis,
        workbench=workbench,
        output_context_name=context.name,
    )
    print("\x1b[38;2;166;218;149mATOMIZE APPLICATION RECEIPT\x1b[0m")
    print("STATUS · APPLIED AS IS")
    print(f"PRESERVED · {result.preserved_count}")
    print(f"UNRESOLVED AT APPLY · {audit['unresolved_at_apply_count']}")


def _child_verify_atomize(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    context = store.load_direct("study/direct-final/atomize-target")
    memory = next(iter(context.memories.values()))
    analysis = store.load_atomize_analysis(context.uid)
    workbench = store.load_atomize_workbench(analysis)
    checkpoints = store.list_checkpoints(context.name)
    print("\x1b[38;2;138;173;244mREAD-ONLY ATOMIZE VERIFICATION\x1b[0m")
    print(f"MEMORY · {memory.content}")
    print(f"APPLICATION OUTPUT · {workbench.application.output_context_name}")
    print(f"APPLICATION CHECKPOINT · {workbench.application.checkpoint_uid[:8]}")
    print(f"ATOMIZE CHECKPOINTS · {sum(c.get('command') == 'atomize' for c in checkpoints)}")


def _run_child(mode: str, store_root: Path) -> None:
    {
        "update": _child_update,
        "verify-update": _child_verify_update,
        "atomize": _child_atomize,
        "verify-atomize": _child_verify_atomize,
    }[mode](store_root)


def _capture_verification(mode: str, store_root: Path, stem: str, expected: str) -> None:
    child, recorder = _spawn_child(mode, store_root)
    _finish(child, recorder)
    if expected not in recorder.getvalue():
        raise RuntimeError(f"Verification capture {stem} missed {expected!r}.")
    HELPERS._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-direct-final-") as temporary:
        store_root = Path(temporary)

        child, recorder = _spawn_child("update", store_root)
        _wait_for(child, recorder, "REVIEW AND APPLY", "Apply Update")
        HELPERS._snapshot(recorder, "01-update-direct-final-approval")
        child.send("\x1b")
        _wait_for(child, recorder, "WHAT WILL CHANGE", "IMPACT · UPDATE")
        HELPERS._snapshot(recorder, "02-update-back-to-complete-report")
        child.send("a")
        _wait_for(child, recorder, "REVIEW AND APPLY", "Apply Update")
        child.send("\x1b[B\r")
        _finish(child, recorder)
        if "UPDATE APPLICATION RECEIPT" not in recorder.getvalue():
            raise RuntimeError("Update was not explicitly approved and applied.")
        HELPERS._snapshot(recorder, "03-update-application-receipt")
        _capture_verification(
            "verify-update",
            store_root,
            "04-update-read-only-verification",
            "UPDATE CHECKPOINTS · 1",
        )

        child, recorder = _spawn_child("atomize", store_root)
        _wait_for(child, recorder, "REVIEW AND APPLY", "Apply Atomize as is")
        HELPERS._snapshot(recorder, "05-atomize-direct-final-approval")
        child.send("\x1b")
        _wait_for(child, recorder, "WHAT MEM UNDERSTOOD", "ACTIONABLE FINDINGS")
        HELPERS._pump(child, recorder, seconds=0.3)
        HELPERS._snapshot(recorder, "06-atomize-back-to-optional-report")
        child.send("a")
        _wait_for(child, recorder, "REVIEW AND APPLY", "Apply Atomize as is")
        child.send("\x1b[B\r")
        _finish(child, recorder)
        if "ATOMIZE APPLICATION RECEIPT" not in recorder.getvalue():
            raise RuntimeError("Atomize was not explicitly approved and applied.")
        HELPERS._snapshot(recorder, "07-atomize-application-receipt")
        _capture_verification(
            "verify-atomize",
            store_root,
            "08-atomize-read-only-verification",
            "ATOMIZE CHECKPOINTS · 1",
        )

        raw = (OUT / "01-update-direct-final-approval.typescript").read_text(
            encoding="utf-8"
        )
        if "\x1b[" not in raw or "38;2" not in raw:
            raise RuntimeError("Capture did not preserve ANSI true-color output.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(sys.argv[2], Path(sys.argv[3]))
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("usage: capture_decision_free_final.py [--child MODE STORE]")
