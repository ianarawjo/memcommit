"""Capture recursive Share review, Send, cancellation, and stale failure."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("share_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _prepare_topology(home: Path):
    from memcommit.context import Context, Memory
    from memcommit.profile_config import (
        AUTHORING_PROFILE_NAME,
        AUTHORING_PROFILE_UID,
        GRANT_RESOURCE_CONTEXT_TREE,
        AuthorityGrant,
        GrantContextBinding,
        ProfileEntry,
        ProfileRegistry,
        profile_registry_file,
        profile_store_dir,
    )
    from memcommit.store import MemoryStore

    os.environ["HOME"] = str(home)
    sender = ProfileEntry(uid=str(uuid.uuid4()), name="share-sender", kind="MANAGED")
    receiver = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="share-receiver",
        kind="MANAGED",
    )
    sender_store = MemoryStore(root=profile_store_dir(sender))
    receiver_store = MemoryStore(root=profile_store_dir(receiver))

    attachment = Context(uid=str(uuid.uuid4()), name="outbound")
    sender_store.create_context(attachment)
    root = Context(uid=str(uuid.uuid4()), name="practice")
    root.add(Memory(uid=str(uuid.uuid4()), content="Keep the shared plan concise."))
    appointments = Context(uid=str(uuid.uuid4()), name="practice/appointments")
    appointments.add(
        Memory(
            uid=str(uuid.uuid4()),
            content="Send a written follow-up after each appointment.",
        )
    )
    empty = Context(uid=str(uuid.uuid4()), name="practice/empty-lane")
    medication = Context(uid=str(uuid.uuid4()), name="practice/medication")
    medication.add(
        Memory(
            uid=str(uuid.uuid4()),
            content="Confirm medication changes with the prescribing clinician.",
        )
    )
    for context in (root, appointments, empty, medication):
        sender_store.create_context(context)
    sender_store.set_current(root.name)

    endpoints = []
    grants = []
    for public_name, stored_name in (
        ("government/healthcare-agent", "remote/government/healthcare-agent"),
        ("research/archive-agent", "remote/research/archive-agent"),
    ):
        endpoint = Context(uid=str(uuid.uuid4()), name=stored_name)
        receiver_store.create_context(endpoint)
        endpoints.append(endpoint)
        grants.append(
            AuthorityGrant(
                uid=str(uuid.uuid4()),
                revision=1,
                authority_profile_uid=receiver.uid,
                grantee_profile_uid=sender.uid,
                attachment_context_uid=attachment.uid,
                attachment_context_name=attachment.name,
                resource_kind=GRANT_RESOURCE_CONTEXT_TREE,
                resource_uid=endpoint.uid,
                resource_name=endpoint.name,
                public_name=public_name,
                permissions=("SHARE",),
                contexts=(GrantContextBinding(uid=endpoint.uid, name=endpoint.name),),
            )
        )

    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    registry = ProfileRegistry(
        generation=1,
        active_uid=sender.uid,
        profiles=(authoring, sender, receiver),
        grants=tuple(grants),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry.to_dict()) + "\n", encoding="utf-8")
    return sender_store, receiver_store, root


def _received_names(receiver_store) -> tuple[str, ...]:
    return tuple(
        name
        for name in receiver_store.list_context_names()
        if "/received-shares/" in name
    )


def _run_child(home: Path, kind: str) -> None:
    import typer

    from memcommit.commands.share.command import cmd
    from memcommit.context import Context
    from memcommit.profile_config import (
        ProfileRegistry,
        load_profile_registry,
        profile_registry_file,
    )
    from memcommit.share import ShareError, deliver_prepared_share, prepare_share

    sender_store, receiver_store, root = _prepare_topology(home)
    columns, rows = os.get_terminal_size()
    print(f"$ mem share {root.name} -r", flush=True)
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    print("PROFILE · share-sender · CURRENT · practice", flush=True)

    if kind == "unavailable":
        registry = load_profile_registry()
        profile_registry_file().write_text(
            json.dumps(
                ProfileRegistry(
                    generation=registry.generation + 1,
                    active_uid=registry.active_uid,
                    profiles=registry.profiles,
                    grants=(),
                    removed_profile_uids=registry.removed_profile_uids,
                ).to_dict()
            )
            + "\n",
            encoding="utf-8",
        )
        cmd(
            source=root.name,
            recipient="",
            direct=False,
            recursive=True,
        )
        print("UNAVAILABLE VERIFICATION", flush=True)
        print(f"  RECEIVED CONTEXTS · {len(_received_names(receiver_store))}")
        print(f"  SOURCE CONTEXTS · {len(sender_store.list_context_names())}")
        print(f"  CURRENT · {sender_store.current_context_name()}", flush=True)
        return

    if kind in {"send", "cancel"}:
        cmd(
            source=root.name,
            recipient="",
            direct=False,
            recursive=True,
        )
        names = _received_names(receiver_store)
        if kind == "cancel":
            print("CANCEL VERIFICATION", flush=True)
            print(f"  RECEIVED CONTEXTS · {len(names)}", flush=True)
            print(f"  SOURCE CONTEXTS · {len(sender_store.list_context_names())}")
            print(f"  CURRENT · {sender_store.current_context_name()}", flush=True)
            return

        print("CAPTURE GATE · PRESS V FOR READ-ONLY VERIFICATION", flush=True)
        if sys.stdin.read(1).lower() != "v":
            raise RuntimeError("Share verification gate was not acknowledged.")
        names = _received_names(receiver_store)
        print("READ-ONLY RECEIVER VERIFICATION")
        print(f"  RECEIVED CONTEXTS · {len(names)}")
        for name in names:
            received = receiver_store.load_direct(name)
            share = receiver_store.list_checkpoints(name)[0]["args"]["share"]
            print(
                "  MEMBER · "
                f"{name.split('/received-shares/', 1)[1]} · "
                f"MEMORIES {len(tuple(received.iter_items()))} · "
                f"BUNDLE {share['context_index'] + 1}/{share['context_count']}"
            )
        print(f"  SOURCE ROOT MEMORIES · {len(tuple(root.iter_items()))}")
        print(f"  CURRENT · {sender_store.current_context_name()}", flush=True)
        return

    preview = prepare_share(
        root.name,
        "government/healthcare-agent",
        include_descendants=True,
    )
    late = Context(uid=str(uuid.uuid4()), name=root.name + "/late")
    late.add("This member appeared after review.")
    sender_store.create_context(late)
    try:
        deliver_prepared_share(preview)
    except ShareError as error:
        typer.secho("STALE BUNDLE REJECTED", fg=typer.colors.RED, bold=True)
        print(f"  ERROR · {error}")
    else:
        raise RuntimeError("A stale recursive Share unexpectedly succeeded.")
    print("FAIL-CLOSED VERIFICATION")
    print(f"  RECEIVED CONTEXTS · {len(_received_names(receiver_store))}")
    print(f"  SOURCE CONTEXTS · {len(sender_store.list_context_names())}")
    print(f"  CURRENT · {sender_store.current_context_name()}", flush=True)


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


def _spawn(kind: str, home: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(home)],
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


def _capture_send(home: Path) -> None:
    child, recorder = _spawn("send", home)
    try:
        child.expect("Select a Share endpoint")
        _BASE._settle(child)
        _snapshot(recorder, "01-endpoint-choice")

        child.send("\r")
        child.expect("MEM SHARE")
        _BASE._settle(child)
        _snapshot(recorder, "02-recursive-bundle-entry")

        child.send("\x1b[B\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "03-descendant-context-focused")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "04-endpoint-focused")

        child.send("\r")
        child.expect("Select a Share endpoint")
        _BASE._settle(child)
        _snapshot(recorder, "05-endpoint-browse")

        child.send("\x1b[B\r")
        child.expect("MEM SHARE")
        _BASE._settle(child)
        _snapshot(recorder, "06-endpoint-updated")

        child.send("\x1b[B\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "07-descendant-memory-focused")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "08-exact-apply")

        child.send("\r")
        child.expect("CAPTURE GATE")
        _BASE._settle(child)
        _snapshot(recorder, "09-success-receipt")

        child.send("v\r")
        child.expect("READ-ONLY RECEIVER VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "10-read-only-receiver-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_cancel(home: Path) -> None:
    child, recorder = _spawn("cancel", home)
    try:
        child.expect("Select a Share endpoint")
        child.send("\r")
        child.expect("MEM SHARE")
        _BASE._settle(child)
        child.send("\x1b")
        child.expect("CANCEL VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "11-cancelled-bundle-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_stale(home: Path) -> None:
    child, recorder = _spawn("stale", home)
    try:
        child.expect("STALE BUNDLE REJECTED")
        child.expect("FAIL-CLOSED VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "12-stale-membership-failure")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_unavailable(home: Path) -> None:
    child, recorder = _spawn("unavailable", home)
    try:
        child.expect("MEM SHARE")
        _BASE._settle(child)
        _snapshot(recorder, "13-unavailable-entry")
        child.send("\x1b")
        child.expect("UNAVAILABLE VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "14-unavailable-close-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for path in OUT.iterdir():
        if path.suffix in {".png", ".txt", ".typescript"}:
            path.unlink()
    with tempfile.TemporaryDirectory(prefix="mem-share-recursive-") as directory:
        root = Path(directory)
        _capture_send(root / "send")
        _capture_cancel(root / "cancel")
        _capture_stale(root / "stale")
        _capture_unavailable(root / "unavailable")
    streams = tuple(path.read_bytes() for path in OUT.glob("*.typescript"))
    if len(streams) != 14:
        raise RuntimeError("Recursive Share capture set is incomplete.")
    if not any(b"\x1b[" in stream and b"38;" in stream for stream in streams):
        raise RuntimeError("Capture did not retain the expected ANSI colors.")
    if any(b"CAPTURE PTY \xc2\xb7 180x52" not in stream for stream in streams):
        raise RuntimeError("A capture did not preserve the required 180x52 PTY.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[3]), sys.argv[2])
    else:
        main()
