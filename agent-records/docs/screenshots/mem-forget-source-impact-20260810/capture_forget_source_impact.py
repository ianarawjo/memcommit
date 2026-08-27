"""Capture Forget's exact Source-aware Impact review through a real color PTY."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROWS = 52
COLUMNS = 180
CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CAPTURE_SUPPORT_DIR = (
    CAPTURE_DIR.parent / "mem-forget-flagless-setup-20260810"
)
INSTRUCTION = (
    "Forget the previous west-entrance desk location and obsolete access code; "
    "keep general accessibility guidance."
)
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
if str(CAPTURE_SUPPORT_DIR) not in sys.path:
    sys.path.insert(0, str(CAPTURE_SUPPORT_DIR))

import capture_forget_setup as capture_support  # noqa: E402


capture_support.CAPTURE_DIR = CAPTURE_DIR
capture_support.ROWS = ROWS
capture_support.COLUMNS = COLUMNS


def _source_context():
    from memcommit.context import Context, Memory

    context = Context(
        uid="10000000-0000-4000-8000-000000000001",
        name="beta",
    )
    for uid, content in (
        (
            "20000001-0000-4000-8000-000000000001",
            "The desk was previously beside the west entrance. "
            "The route remains step-free.",
        ),
        (
            "20000002-0000-4000-8000-000000000002",
            "The obsolete access code was 4815.",
        ),
        (
            "20000003-0000-4000-8000-000000000003",
            "Visitors should verify the step-free route before arrival.",
        ),
    ):
        context.add(Memory(uid=uid, content=content))
    return context


class DeterministicForgetProvider:
    model = "capture-forget-source-impact"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "forget"
        assert output_schema is not None
        self.calls += 1
        messages = json.loads(prompt.split("FORGET CHAT MESSAGES:\n", 1)[1])
        payload = json.loads(
            messages[1]["content"].split("FORGET PAYLOAD:\n", 1)[1]
        )
        decisions = (
            (
                "EDIT",
                "The route remains step-free.",
                "Remove the old desk location while retaining accessibility guidance.",
            ),
            (
                "DELETE",
                "",
                "The instruction explicitly covers the obsolete access code.",
            ),
            (
                "KEEP",
                payload["source"]["memories"][2]["content"],
                "This is general accessibility guidance to retain.",
            ),
        )
        return json.dumps(
            {
                "overview": (
                    "Remove the obsolete location and code while preserving "
                    "general step-free guidance."
                ),
                "candidates": [
                    {
                        "source_memory_id": source["item_id"],
                        "decision": decision,
                        "proposed_content": content,
                        "rationale": rationale,
                        "criterion_item_ids": ["k1"],
                    }
                    for source, (decision, content, rationale) in zip(
                        payload["source"]["memories"],
                        decisions,
                        strict=True,
                    )
                ],
            }
        )


def _child(*, cancel: bool) -> None:
    import memcommit.adapters.console.commands.forget.command as forget_command

    rows, columns = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    context = _source_context()
    original = context.to_dict()
    provider = DeterministicForgetProvider()

    # This focused harness starts at the changed review boundary. It still uses
    # the production provider decoder, ForgetReview, Impact projection, shared
    # Resolution shell, and apply_changes path; only the unrelated wait screen
    # is bypassed because its full command capture already exists separately.
    forget_command.run_command_wait = (
        lambda _operation, _stage, *, work, **_kwargs: work(None)
    )
    changes = forget_command._run_resolution_forget(context, INSTRUCTION, provider)

    if cancel:
        print("REVIEW CANCEL VERIFICATION · READ-ONLY")
        print(f"PROVIDER CALLS · {provider.calls}")
        print(f"SOURCE UNCHANGED · {'YES' if context.to_dict() == original else 'NO'}")
        return

    print("APPLY VERIFICATION · IN-MEMORY HARNESS")
    print(f"PROVIDER CALLS · {provider.calls}")
    print(f"REVIEWED CHANGES · {len(changes)}")
    for index, memory in enumerate(context.memories.values(), start=1):
        print(f"SOURCE {index} · {memory.content}")


def _spawn(environment: dict[str, str], *, cancel: bool):
    import pexpect

    arguments = [str(Path(__file__).resolve()), "--child"]
    if cancel:
        arguments.append("--cancel")
    return pexpect.spawn(
        sys.executable,
        arguments,
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )


def _capture_review(environment: dict[str, str]) -> bytearray:
    raw = bytearray()
    child = _spawn(environment, cancel=False)
    capture_support._wait_for(child, raw, b"IMPACT", timeout=8)
    capture_support._render_snapshot("01-review-entry", bytes(raw))

    child.send(b"\x1b[B" * 3)
    capture_support._settle(child, raw)
    capture_support._render_snapshot("02-edit-focused", bytes(raw))

    child.send(b"\x1b[B")
    capture_support._settle(child, raw)
    capture_support._render_snapshot("03-drop-focused", bytes(raw))

    child.send(b"\x1b[B")
    capture_support._settle(child, raw)
    capture_support._render_snapshot("04-keep-focused", bytes(raw))

    child.send(b"\t\x1b[B\r")
    capture_support._wait_for(child, raw, b"WHY THIS ACTION", timeout=5)
    capture_support._render_snapshot("05-decision-detail", bytes(raw))

    child.send(b"a")
    capture_support._settle(child, raw, delay=0.5)
    capture_support._render_snapshot("06-final-review", bytes(raw))

    child.send(b"\x1b[F")
    capture_support._settle(child, raw)
    capture_support._render_snapshot("07-exact-apply", bytes(raw))

    child.send(b"\r")
    capture_support._wait_for(child, raw, b"APPLY VERIFICATION", timeout=5)
    capture_support._render_snapshot("08-apply-verification", bytes(raw))
    child.close()
    if child.exitstatus not in {0, None}:
        raise RuntimeError(f"Apply capture child exited with {child.exitstatus}.")
    return raw


def _capture_cancel(environment: dict[str, str]) -> bytearray:
    raw = bytearray()
    child = _spawn(environment, cancel=True)
    capture_support._wait_for(child, raw, b"IMPACT", timeout=8)
    child.send(b"q")
    capture_support._wait_for(child, raw, b"REVIEW CANCEL", timeout=5)
    capture_support._render_snapshot("09-cancel-verification", bytes(raw))
    child.close()
    if child.exitstatus not in {0, None}:
        raise RuntimeError(f"Cancel capture child exited with {child.exitstatus}.")
    return raw


def _parent() -> None:
    environment = dict(os.environ)
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    combined = bytes(
        _capture_review(environment) + _capture_cancel(environment)
    )
    if b"\x1b[" not in combined:
        raise RuntimeError("PTY streams did not contain ANSI control sequences.")
    if b"38;2;" not in combined and b"38;5;" not in combined:
        raise RuntimeError("PTY streams did not contain foreground color styles.")


if __name__ == "__main__":
    if sys.argv[1:] in (["--child"], ["--child", "--cancel"]):
        _child(cancel="--cancel" in sys.argv)
    elif not sys.argv[1:]:
        _parent()
    else:
        raise SystemExit(
            "usage: capture_forget_source_impact.py [--child [--cancel]]"
        )
