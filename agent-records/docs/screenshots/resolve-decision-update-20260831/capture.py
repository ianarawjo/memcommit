"""Capture Resolve decisions through Update planning, verification, and Apply."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE_CAPTURE = (
    ROOT
    / "agent-records/docs/screenshots/compact-execution-decisions-20260822/capture.py"
)
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location("memcommit_compact_capture", BASE_CAPTURE)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load the shared terminal capture helpers.")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.OUT = OUT


class _StreamRecorder(io.StringIO):
    def flush(self) -> None:
        return


class _ResolveCaptureProvider:
    def __init__(self, kind: str) -> None:
        from memcommit.providers.types import ProviderIdentity

        self.kind = kind
        self.identity = ProviderIdentity(provider="capture", model="resolve-audit")
        self._conflict_calls = 0

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        if operation in {"find_duplicates", "find_ambiguities"}:
            return json.dumps({"findings": []})

        if operation == "resolve_audit_directions":
            payload = json.loads(prompt.split("RESOLVE AUDIT PAYLOAD:\n", 1)[1])
            directions = (
                "Named greetings remain exceptions to the general rule.",
                "The exception applies only to named greetings.",
            )
            return json.dumps(
                {
                    "directions": [
                        {
                            "item_id": item["item_id"],
                            "direction": directions[index],
                        }
                        for index, item in enumerate(payload["audit"]["items"])
                    ]
                }
            )

        if operation == "update planning":
            print("\nUPDATE PROVIDER GATE · PRESS U", flush=True)
            if sys.stdin.readline().strip().lower() != "u":
                raise RuntimeError("Update planning gate was not acknowledged.")
            payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
            source_ids = [memory["source_id"] for memory in payload["source"]["memories"]]
            targets = payload["target"]["memories"]
            first = next(
                target
                for target in targets
                if target["content"] == "Named greetings always end with a period."
            )
            third = next(
                target
                for target in targets
                if target["content"] == "All greetings follow the house punctuation rule."
            )
            return json.dumps(
                {
                    "edits": [
                        {
                            "target_id": first["target_id"],
                            "new_content": (
                                "General greetings end with a period; named greetings "
                                "may omit punctuation."
                            ),
                            "source_ids": source_ids,
                            "reason": "Represent the confirmed named-greeting exception.",
                        },
                        {
                            "target_id": third["target_id"],
                            "new_content": (
                                "Non-named greetings follow the house punctuation rule."
                            ),
                            "source_ids": source_ids,
                            "reason": "Apply the supplied intent across the complete Context.",
                        },
                    ],
                    "additions": [],
                    "removals": [],
                }
            )

        if operation == "find_conflicts":
            payload = json.loads(prompt.split("QUALITY FIND PAYLOAD:\n", 1)[1])
            self._conflict_calls += 1
            if self._conflict_calls == 1:
                pairs = payload["pairs"]
                findings = [
                    {
                        "pair_id": pairs[0]["pair_id"],
                        "conflict": "YES",
                        "reason": (
                            "The general rule does not say whether named greetings "
                            "are in scope."
                        ),
                        "question": "Which rule governs named greetings?",
                    }
                ]
                if self.kind == "success":
                    findings.append(
                        {
                            "pair_id": pairs[-1]["pair_id"],
                            "conflict": "YES",
                            "reason": (
                                "The house rule and exception do not identify the "
                                "same greeting scope."
                            ),
                            "question": "Which greetings are in the exception?",
                        }
                    )
                return json.dumps({"findings": findings})

            print("\nPOST-IMAGE AUDIT GATE · PRESS C", flush=True)
            if sys.stdin.readline().strip().lower() != "c":
                raise RuntimeError("Audit verification gate was not acknowledged.")
            if self.kind == "success":
                return json.dumps({"findings": []})
            return json.dumps(
                {
                    "findings": [
                        {
                            "pair_id": payload["pairs"][0]["pair_id"],
                            "conflict": "YES",
                            "reason": "The forced punctuation scope remains unresolved.",
                            "question": "Should named greetings be an exception?",
                        }
                    ]
                }
            )
        raise AssertionError(operation)


def _install_store(root: Path) -> None:
    import memcommit.persistence.store as store_module

    store_module.STORE_DIR = root
    store_module.CONTEXTS_DIR = root / "contexts"
    store_module.STATE_FILE = root / "state.json"
    store_module.QUERY_SOURCES_DIR = root / "query-sources"
    store_module.IMPACT_PLAN_FILE = root / "impact-plan.json"
    store_module.STAGED_UPDATE_FILE = root / "staged-update.json"
    store_module.REVIEW_SESSION_FILE = root / "review-session.json"
    store_module.ATOMIZE_ANALYSES_DIR = root / "atomize-analyses"
    store_module.ATOMIZE_WORKBENCHES_DIR = root / "atomize-workbenches"
    store_module.MELD_SESSIONS_DIR = root / "meld-sessions"


def _run_child(kind: str) -> None:
    from memcommit.adapters.console.commands.resolve import (
        command as resolve_command,
    )
    from memcommit.core.context import Context, Memory
    from memcommit.persistence.store import MemoryStore

    size = os.get_terminal_size()
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError(f"unexpected PTY size: {size.columns}x{size.lines}")

    store_root = Path(tempfile.mkdtemp(prefix=f"memcommit-resolve-{kind}-")) / ".mem"
    _install_store(store_root)
    store = MemoryStore()
    context = Context(
        "aaaaaaaa-0000-4000-8000-000000000101",
        "capture/resolve",
    )
    context.add(
        Memory(
            "11111111-0000-4000-8000-000000000111",
            "Named greetings always end with a period.",
        )
    )
    context.add(
        Memory(
            "22222222-0000-4000-8000-000000000112",
            "Named greetings may omit punctuation.",
        )
    )
    context.add(
        Memory(
            "33333333-0000-4000-8000-000000000113",
            "All greetings follow the house punctuation rule.",
        )
    )
    store.create_context(context)
    store.set_current(context.name)

    provider = _ResolveCaptureProvider(kind)
    resolve_command.connect_semantic_provider = lambda: provider
    print(f"$ mem resolve {context.name}", flush=True)
    print(f"PTY · {size.columns}×{size.lines} · PROFILE isolated · CURRENT {context.name}", flush=True)
    resolve_command.cmd(
        auto_operands=[context.name],
        context_name=None,
        memory_operands=None,
        allow_create=True,
        allow_delete=False,
        guidance=None,
        finding_handoff=None,
    )

    print("CAPTURE GATE · PRESS V FOR READ-ONLY VERIFICATION", flush=True)
    if sys.stdin.readline().strip().lower() != "v":
        raise RuntimeError("Read-only verification gate was not acknowledged.")
    current = store.load_direct(context.name)
    checkpoint = store.list_checkpoints(context.name)[-1]
    print("\nREAD-ONLY RESULT VERIFICATION")
    for item in current.iter_items():
        if isinstance(item, Memory):
            print(f"  [{item.uid}] {item.content}")
    print(f"  CHECKPOINT COMMAND · {checkpoint['command']}")
    print(
        "  FINALIZED INPUTS · "
        + json.dumps(checkpoint["args"]["finalized_inputs"], ensure_ascii=False)
    )
    print(
        "  UNRESOLVED ISSUE COUNT · "
        + str(len(checkpoint["args"]["unresolved_issue_uids"]))
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
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _settle(child: pexpect.spawn, seconds: float = 0.5) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(size=65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            continue
        except pexpect.EOF:
            return


def _snapshot(recorder: _StreamRecorder, stem: str) -> None:
    base._render(recorder.getvalue(), stem)
    plain_path = OUT / f"{stem}.txt"
    plain = plain_path.read_text(encoding="utf-8")
    plain_path.write_text(
        "\n".join(line.rstrip() for line in plain.splitlines()).rstrip() + "\n",
        encoding="utf-8",
    )


def _spawn(kind: str) -> tuple[pexpect.spawn, _StreamRecorder]:
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    recorder = _StreamRecorder()
    child.logfile_read = recorder
    return child, recorder


def _capture_success() -> None:
    child, recorder = _spawn("success")
    try:
        child.expect("RESOLVE")
        _settle(child)
        _snapshot(recorder, "01-entry-first-conflict")

        child.send("\r")
        _settle(child)
        child.send(DOWN * 4)
        _settle(child)
        _snapshot(recorder, "02-confirmed-first-next-row")

        child.send("\r")
        _settle(child)
        _snapshot(recorder, "03-next-second-conflict")

        child.send(DOWN + "\r")
        _settle(child)
        _snapshot(recorder, "04-intent-selected-inline-field")

        child.send("The exception applies only to named greetings.")
        _settle(child)
        child.send("\r" + DOWN * 4)
        _settle(child)
        _snapshot(recorder, "05-intent-entered-finalize-ready")

        child.send("\r")
        child.expect("UPDATE PROVIDER GATE")
        _settle(child)
        _snapshot(recorder, "06-update-planning")

        child.send("u\r")
        child.expect("POST-IMAGE AUDIT GATE")
        _settle(child)
        _snapshot(recorder, "07-post-image-audit-check")

        child.send("c\r")
        child.expect("CAPTURE GATE")
        _settle(child)
        _snapshot(recorder, "08-applied-receipt")

        child.send("v\r")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "09-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_force() -> None:
    child, recorder = _spawn("force")
    try:
        child.expect("RESOLVE")
        _settle(child)
        child.send(DOWN * 2 + "\r")
        _settle(child)
        _snapshot(recorder, "10-force-selected")

        child.send(DOWN + "\r")
        child.expect("POST-IMAGE AUDIT GATE")
        _settle(child)
        _snapshot(recorder, "11-force-post-image-check")

        child.send("c\r")
        child.expect("CAPTURE GATE")
        _settle(child)
        _snapshot(recorder, "12-force-unresolved-receipt")

        child.send("v\r")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "13-force-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    for pattern in ("[0-9][0-9]-*.png", "[0-9][0-9]-*.txt", "[0-9][0-9]-*.typescript"):
        for path in OUT.glob(pattern):
            path.unlink()
    _capture_success()
    _capture_force()

    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(sys.argv[2])
    else:
        main()
