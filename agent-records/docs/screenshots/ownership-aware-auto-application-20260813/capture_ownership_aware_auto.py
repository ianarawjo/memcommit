"""Capture ownership-aware auto-application in a real 180x52 PTY."""

from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
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
        / "agent-records" / "docs"
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
    environment["PYTHONPATH"] = str(ROOT / "src")
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


class _EmptyUpdateProvider:
    def complete(self, _prompt, *, operation, output_schema=None):
        del output_schema
        if operation != "update planning":
            raise AssertionError(operation)
        return json.dumps({"edits": [], "additions": [], "removals": []})


def _new_context(*, uid: str, name: str, memory_uid: str, content: str):
    from memcommit.context import Context, Memory

    context = Context(uid=uid, name=name)
    context.add(Memory(uid=memory_uid, content=content))
    return context


def _child_update(store_root: Path) -> None:
    from memcommit.adapters.console.commands.update.render import review_update_application
    from memcommit.persistence.store import MemoryStore
    from memcommit.application.operations.update.model import plan_update

    store = MemoryStore(root=store_root)
    source = _new_context(
        uid="11111111-1111-4111-8111-111111111111",
        name="study/ownership-auto/source",
        memory_uid="22222222-2222-4222-8222-222222222222",
        content="Use the south entrance for step-free access.",
    )
    target = _new_context(
        uid="33333333-3333-4333-8333-333333333333",
        name="study/ownership-auto/update-target",
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
    print("TARGET · study/ownership-auto/update-target")
    print("REVIEW WINDOW · SKIPPED · NO REQUIRED DECISIONS · LOCAL TARGET")
    print("RECOVERY · mem undo")


def _child_verify_update(store_root: Path) -> None:
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    context = store.load_direct("study/ownership-auto/update-target")
    memory = next(iter(context.memories.values()))
    session = store.load_staged_update()
    checkpoints = store.list_checkpoints(context.name)
    print("\x1b[38;2;138;173;244mREAD-ONLY UPDATE VERIFICATION\x1b[0m")
    print(f"STATUS · {session.status.upper()}")
    print(f"MEMORY · {memory.content}")
    print(f"UPDATE CHECKPOINTS · {sum(c.get('command') == 'update' for c in checkpoints)}")


def _child_undo_update(store_root: Path) -> None:
    from memcommit.adapters.console.commands.shared.restoration_present import render_command_restore_receipt
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    result = store.restore_recent_context_command("undo")
    render_command_restore_receipt(result)
    context = store.load_direct("study/ownership-auto/update-target")
    memory = next(iter(context.memories.values()))
    session = store.load_staged_update()
    print("RECOVERY VERIFICATION · LOCAL UPDATE")
    print(f"STATUS · {session.status.upper()}")
    print(f"MEMORY · {memory.content}")


def _child_granted_update(store_root: Path) -> None:
    from memcommit.adapters.console.commands.update.render import review_update_application
    from memcommit.persistence.store import MemoryStore
    from memcommit.application.operations.update.model import GrantedUpdateTarget, plan_update

    store = MemoryStore(root=store_root)
    source = _new_context(
        uid="77777777-7777-4777-8777-777777777777",
        name="study/granted-review/source",
        memory_uid="88888888-8888-4888-8888-888888888888",
        content="Use the south entrance for step-free access.",
    )
    target = _new_context(
        uid="99999999-9999-4999-8999-999999999999",
        name="shared/granted-review/target",
        memory_uid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        content="The north entrance provides public access.",
    )
    store.save(source)
    store.save(target)
    staged = plan_update(source, target, _UpdateProvider, status="staged")
    staged = replace(
        staged,
        granted_target=GrantedUpdateTarget(
            public_name="shared/granted-review/target",
            grantee_profile_uid="11111111-1111-4111-8111-111111111111",
            authority_profile_uid="22222222-2222-4222-8222-222222222222",
            attachment_context_uid="attachment-context",
            attachment_context_name="shared",
            grant_uid="33333333-3333-4333-8333-333333333333",
            grant_revision=1,
            grant_digest="a" * 64,
            resource_uid=target.uid,
            resource_name=target.name,
            authority_context_name=target.name,
            permissions=("READ", "UPDATE"),
        ),
    )
    store.save_staged_update(staged, expected_current=None)
    reviewed = review_update_application(
        staged,
        incorporate=lambda *_args: (_ for _ in ()).throw(
            AssertionError("The capture does not submit a revision.")
        ),
    )
    if reviewed is not None:
        raise RuntimeError("Granted Update must not accept without exact approval.")
    current = store.load_direct(target.name)
    memory = next(iter(current.memories.values()))
    print("GRANTED UPDATE CLOSED · STAGED RECEIPT RETAINED")
    print("AUTHORITY TARGET · UNCHANGED")
    print(f"MEMORY · {memory.content}")


def _child_granted_update_noop(store_root: Path) -> None:
    from memcommit.adapters.console.commands.update.render import review_update_application
    from memcommit.persistence.store import MemoryStore
    from memcommit.application.operations.update.model import GrantedUpdateTarget, plan_update

    store = MemoryStore(root=store_root)
    source = _new_context(
        uid="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        name="study/granted-noop/source",
        memory_uid="cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        content="The current access notice is already correct.",
    )
    target = _new_context(
        uid="dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        name="shared/granted-noop/target",
        memory_uid="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        content="The current access notice is already correct.",
    )
    store.save(source)
    store.save(target)
    target_before = target.to_dict()
    staged = plan_update(source, target, _EmptyUpdateProvider, status="staged")
    staged = replace(
        staged,
        granted_target=GrantedUpdateTarget(
            public_name=target.name,
            grantee_profile_uid="11111111-1111-4111-8111-111111111111",
            authority_profile_uid="22222222-2222-4222-8222-222222222222",
            attachment_context_uid="attachment-context",
            attachment_context_name="shared",
            grant_uid="33333333-3333-4333-8333-333333333333",
            grant_revision=1,
            grant_digest="a" * 64,
            resource_uid=target.uid,
            resource_name=target.name,
            authority_context_name=target.name,
            permissions=("READ", "UPDATE"),
        ),
    )
    store.save_staged_update(staged, expected_current=None)
    reviewed = review_update_application(
        staged,
        incorporate=lambda *_args: (_ for _ in ()).throw(
            AssertionError("The capture does not submit a revision.")
        ),
    )
    if reviewed is None or reviewed.operations:
        raise RuntimeError("A granted zero-change Update must accept as no mutation.")
    if store.load_direct(target.name).to_dict() != target_before:
        raise RuntimeError("Reviewing a granted zero-change Update changed its target.")
    if store.list_checkpoints(target.name):
        raise RuntimeError("A granted zero-change review created a Context checkpoint.")
    print("\x1b[38;2;166;218;149mZERO-CHANGE UPDATE RECEIPT\x1b[0m")
    print("STATUS · ACCEPTED FOR COMPLETION")
    print("TARGET · shared/granted-noop/target")
    print("REVIEW WINDOW · SKIPPED · ZERO OPERATIONS")
    print("MUTATION BOUNDARY · NONE")
    print("CONTEXT CHECKPOINTS · 0")


def _run_child(mode: str, store_root: Path) -> None:
    {
        "update": _child_update,
        "verify-update": _child_verify_update,
        "undo-update": _child_undo_update,
        "granted-update": _child_granted_update,
        "granted-update-noop": _child_granted_update_noop,
    }[mode](store_root)


def _capture_verification(mode: str, store_root: Path, stem: str, expected: str) -> None:
    child, recorder = _spawn_child(mode, store_root)
    _finish(child, recorder)
    if expected not in recorder.getvalue():
        raise RuntimeError(f"Verification capture {stem} missed {expected!r}.")
    HELPERS._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-ownership-auto-") as temporary:
        store_root = Path(temporary)

        child, recorder = _spawn_child("update", store_root)
        _finish(child, recorder)
        if "REVIEW WINDOW · SKIPPED" not in recorder.getvalue():
            raise RuntimeError("Local decision-free Update did not auto-apply.")
        HELPERS._snapshot(recorder, "01-update-local-auto-application")
        _capture_verification(
            "verify-update",
            store_root,
            "02-update-read-only-verification",
            "UPDATE CHECKPOINTS · 1",
        )
        _capture_verification(
            "undo-update",
            store_root,
            "03-update-undo-recovery",
            "STATUS · UNDONE",
        )

        child, recorder = _spawn_child("granted-update", store_root / "granted")
        _wait_for(child, recorder, "REVIEW AND APPLY", "Apply Update")
        HELPERS._snapshot(recorder, "04-granted-update-final-review")
        child.send("\x1b")
        _wait_for(child, recorder, "WHAT WILL CHANGE", "IMPACT · UPDATE")
        HELPERS._snapshot(recorder, "05-granted-update-back-to-report")
        child.send("q")
        _finish(child, recorder)
        if "AUTHORITY TARGET · UNCHANGED" not in recorder.getvalue():
            raise RuntimeError("Closing granted Update changed its target.")
        HELPERS._snapshot(recorder, "06-granted-update-cancelled-unchanged")

        _capture_verification(
            "granted-update-noop",
            store_root / "granted-noop",
            "09-granted-update-noop-no-mutation",
            "MUTATION BOUNDARY · NONE",
        )

        raw = (OUT / "04-granted-update-final-review.typescript").read_text(
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
