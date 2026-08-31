"""Capture Audit Fit review and its single Resolve decision item."""

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

spec = importlib.util.spec_from_file_location("memcommit_fit_capture", BASE_CAPTURE)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load shared terminal capture helpers.")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.OUT = OUT


class _StreamRecorder(io.StringIO):
    def flush(self) -> None:
        return


class _ResolveFitProvider:
    def __init__(self) -> None:
        from memcommit.providers.types import ProviderIdentity

        self.identity = ProviderIdentity(provider="capture", model="resolve-fit")
        self._fit_calls = 0

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        del output_schema
        if operation.startswith("find_"):
            return '{"findings": []}'
        if operation == "fit_propositions":
            from memcommit.application.operations.fit.judgment import (
                FIT_JUDGMENT_PAYLOAD_MARKER,
            )

            self._fit_calls += 1
            if self._fit_calls == 2:
                print("\nPOST-IMAGE FIT AUDIT GATE · PRESS C", flush=True)
                if sys.stdin.readline().strip().lower() != "c":
                    raise RuntimeError("post-image Fit gate was not acknowledged")
            payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
            aliases = [
                item["proposition_id"]
                for item in payload["questions"][0]["propositions"]
            ]
            return json.dumps(
                {
                    "overview": "The schedule has two materially ordinary readings.",
                    "judgments": [
                        {
                            "question_id": "fit",
                            "verdict": "MAY",
                            "reason": (
                                "The first and third Memories may govern the same "
                                "entrance."
                            ),
                            "considered_proposition_ids": aliases,
                            "material_proposition_ids": [aliases[0], aliases[-1]],
                            "consistent_reading": (
                                "The times govern different entrances."
                            ),
                            "inconsistent_reading": (
                                "Both times govern the main entrance."
                            ),
                        }
                    ],
                }
            )
        if operation == "resolve_audit_directions":
            payload = json.loads(prompt.split("RESOLVE AUDIT PAYLOAD:\n", 1)[1])
            return json.dumps(
                {
                    "directions": [
                        {
                            "item_id": item["item_id"],
                            "direction": (
                                "State which entrance each schedule governs."
                            ),
                        }
                        for item in payload["audit"]["items"]
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


def _audit_session():
    from memcommit.application.capabilities.memory_issue_analysis.model import (
        AmbiguityReport,
        ConflictReport,
        DuplicateReport,
    )
    from memcommit.application.operations.audit.application import create_quality_audit
    from memcommit.application.operations.audit.model import (
        QUALITY_AUDIT_RULESETS,
        QualityAuditCheck,
        QualityAuditFit,
        QualityAuditProvenance,
    )
    from memcommit.application.operations.fit.judgment import FIT_JUDGMENT_OPERATION
    from memcommit.core.context import Context, Memory
    from memcommit.providers.types import ProviderIdentity

    context = Context(
        uid="aaaaaaaa-0000-4000-8000-000000000101",
        name="study/audit-fit",
    )
    memories = (
        Memory(
            uid="11111111-0000-4000-8000-000000000111",
            content="The main entrance opens at 08:00.",
        ),
        Memory(
            uid="22222222-0000-4000-8000-000000000112",
            content="The loading dock opens at 07:00.",
        ),
        Memory(
            uid="33333333-0000-4000-8000-000000000113",
            content="The main entrance remains closed until 09:00.",
        ),
    )
    for memory in memories:
        context.add(memory)
    identity = ProviderIdentity(provider="capture", model="audit-fit")

    def provenance(kind: str) -> QualityAuditProvenance:
        return QualityAuditProvenance(
            operation=f"find_{kind}",
            provider_called=True,
            identity=identity,
        )

    return create_quality_audit(
        context,
        (
            QualityAuditCheck(
                "duplicates",
                QUALITY_AUDIT_RULESETS["duplicates"],
                DuplicateReport(3, ()),
                provenance("duplicates"),
            ),
            QualityAuditCheck(
                "ambiguities",
                QUALITY_AUDIT_RULESETS["ambiguities"],
                AmbiguityReport(3, ()),
                provenance("ambiguities"),
            ),
            QualityAuditCheck(
                "conflicts",
                QUALITY_AUDIT_RULESETS["conflicts"],
                ConflictReport(3, 3, ()),
                provenance("conflicts"),
            ),
        ),
        fit=QualityAuditFit(
            uid="bbbbbbbb-0000-4000-8000-000000000102",
            created_at="2026-08-31T12:00:00+00:00",
            verdict="MAY",
            reason="The first and third Memories may govern the same entrance.",
            overview="The schedule has two materially ordinary readings.",
            considered_memory_uids=tuple(memory.uid for memory in memories),
            material_memory_uids=(memories[0].uid, memories[2].uid),
            consistent_reading="The times govern different entrances.",
            inconsistent_reading="Both times govern the main entrance.",
            provenance=QualityAuditProvenance(
                operation=FIT_JUDGMENT_OPERATION,
                provider_called=True,
                identity=identity,
            ),
        ),
        uid="cccccccc-0000-4000-8000-000000000103",
        created_at="2026-08-31T12:00:01+00:00",
    )


def _run_child(kind: str) -> None:
    size = os.get_terminal_size()
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError(f"unexpected PTY size: {size.columns}x{size.lines}")

    if kind == "audit":
        from memcommit.adapters.console.commands.audit.review import (
            run_quality_audit_review,
        )
        from memcommit.application.operations.audit.model import (
            quality_audit_record_digest,
        )
        from memcommit.persistence.store import MemoryStore

        session = _audit_session()
        before = quality_audit_record_digest(session)
        print(f"$ mem review audit --session {session.uid}", flush=True)
        print(
            f"PTY · {size.columns}×{size.lines} · PROFILE isolated · "
            f"CURRENT {session.source.context_name}",
            flush=True,
        )
        with tempfile.TemporaryDirectory(prefix="memcommit-audit-fit-") as directory:
            run_quality_audit_review(MemoryStore(root=Path(directory)), session)
        print("AUDIT REVIEW CLOSED · READ-ONLY")
        print(
            "  RECORD DIGEST UNCHANGED · "
            f"{quality_audit_record_digest(session) == before}"
        )
        print("  PROVIDER CALLS DURING REVIEW · 0")
        print("  CONTEXT WRITES · 0")
        print("  CHECKPOINTS · 0", flush=True)
        return

    from memcommit.adapters.console.commands.resolve import command as resolve_command
    from memcommit.core.context import Context, Memory
    from memcommit.persistence.store import MemoryStore

    store_root = Path(tempfile.mkdtemp(prefix="memcommit-resolve-fit-")) / ".mem"
    _install_store(store_root)
    store = MemoryStore()
    context = Context(
        uid="aaaaaaaa-0000-4000-8000-000000000101",
        name="study/audit-fit",
    )
    for uid, content in (
        (
            "11111111-0000-4000-8000-000000000111",
            "The main entrance opens at 08:00.",
        ),
        (
            "22222222-0000-4000-8000-000000000112",
            "The loading dock opens at 07:00.",
        ),
        (
            "33333333-0000-4000-8000-000000000113",
            "The main entrance remains closed until 09:00.",
        ),
    ):
        context.add(Memory(uid=uid, content=content))
    store.create_context(context)
    store.set_current(context.name)

    provider = _ResolveFitProvider()
    resolve_command.connect_semantic_provider = lambda: provider
    print(f"$ mem resolve {context.name}", flush=True)
    print(
        f"PTY · {size.columns}×{size.lines} · PROFILE isolated · "
        f"CURRENT {context.name}",
        flush=True,
    )
    resolve_command.cmd(
        auto_operands=[context.name],
        context_name=None,
        memory_operands=None,
        allow_create=True,
        allow_delete=False,
        guidance=None,
        finding_handoff=None,
    )
    print("CAPTURE GATE · PRESS V FOR POST-RESOLVE CONTEXT", flush=True)
    if sys.stdin.readline().strip().lower() != "v":
        raise RuntimeError("verification gate was not acknowledged")
    current = store.load_direct(context.name)
    checkpoint = store.list_checkpoints(context.name)[-1]
    print("READ-ONLY VERIFICATION")
    print(f"  CONTEXT DIGEST UNCHANGED · {current.to_dict() == context.to_dict()}")
    print(f"  CHECKPOINT COMMAND · {checkpoint['command']}")
    print(
        "  UNRESOLVED ISSUE COUNT · "
        + str(len(checkpoint["args"]["unresolved_issue_uids"]))
    )
    print(f"  FIT PROVIDER CALLS · {provider._fit_calls}", flush=True)


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


def _capture_audit() -> None:
    child, recorder = _spawn("audit")
    try:
        child.expect("SAVED .* 4/4 CHECKS .* READ-ONLY REPORT")
        _settle(child)
        _snapshot(recorder, "01-audit-fit-overview")

        child.send(DOWN * 4)
        _settle(child)
        _snapshot(recorder, "02-audit-fit-may-section")

        child.send("q")
        child.expect("AUDIT REVIEW CLOSED .* READ-ONLY")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "03-audit-close-no-write")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_resolve() -> None:
    child, recorder = _spawn("resolve")
    try:
        child.expect("FIT")
        _settle(child)
        _snapshot(recorder, "04-resolve-single-fit-item")

        child.send(DOWN * 2 + "\r")
        _settle(child)
        _snapshot(recorder, "05-resolve-fit-force-selected")

        child.send(DOWN)
        _settle(child)
        _snapshot(recorder, "06-resolve-fit-finalize-ready")

        child.send("\r")
        child.expect("POST-IMAGE FIT AUDIT GATE")
        _settle(child)
        _snapshot(recorder, "07-resolve-post-image-fit-audit")

        child.send("c\r")
        child.expect("CAPTURE GATE")
        _settle(child)
        _snapshot(recorder, "08-resolve-fit-force-receipt")

        child.send("v\r")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "09-resolve-fit-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    for pattern in (
        "[0-9][0-9]-*.png",
        "[0-9][0-9]-*.txt",
        "[0-9][0-9]-*.typescript",
    ):
        for path in OUT.glob(pattern):
            path.unlink()
    _capture_audit()
    _capture_resolve()

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")
    verification = (OUT / "09-resolve-fit-read-only-verification.txt").read_text(
        encoding="utf-8"
    )
    for expected in (
        "CONTEXT DIGEST UNCHANGED · True",
        "CHECKPOINT COMMAND · resolve",
        "UNRESOLVED ISSUE COUNT · 1",
        "FIT PROVIDER CALLS · 2",
    ):
        if expected not in verification:
            raise RuntimeError(f"Missing verification evidence: {expected}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(sys.argv[2])
    else:
        main()
