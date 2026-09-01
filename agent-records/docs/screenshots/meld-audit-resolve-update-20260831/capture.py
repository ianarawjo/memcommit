"""Capture Meld's Audit -> Resolve -> Update -> post-Audit -> Apply path."""

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


class _MeldCaptureProvider:
    """Deterministic semantic boundary with gates around transient stages."""

    def __init__(self, kind: str) -> None:
        from memcommit.providers.types import ProviderIdentity

        self.identity = ProviderIdentity(provider="capture", model="meld-candidate")
        self.kind = kind
        self.last_run = None
        self._conflict_calls = 0
        self._update_calls = 0

    def _record(self, operation: str) -> None:
        from memcommit.providers.types import CompletionRun

        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            upstream_model="meld-candidate",
            upstream_provider="capture",
        )

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        del output_schema
        from memcommit.application.operations.fit.judgment import (
            FIT_JUDGMENT_OPERATION,
            FIT_JUDGMENT_PAYLOAD_MARKER,
        )
        from memcommit.application.operations.meld.coverage import (
            MELD_COVERAGE_OPERATION,
        )

        self._record(operation)
        if operation in {"find_duplicates", "find_ambiguities"}:
            return json.dumps({"findings": []})

        if operation == FIT_JUDGMENT_OPERATION:
            payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
            aliases = [
                item["proposition_id"]
                for item in payload["questions"][0]["propositions"]
            ]
            return json.dumps(
                {
                    "overview": "The complete candidate can jointly hold.",
                    "judgments": [
                        {
                            "question_id": "fit",
                            "verdict": "YES",
                            "reason": "The candidate remains jointly interpretable.",
                            "considered_proposition_ids": aliases,
                            "material_proposition_ids": [],
                            "consistent_reading": "",
                            "inconsistent_reading": "",
                        }
                    ],
                }
            )

        if operation == "find_conflicts":
            self._conflict_calls += 1
            payload = json.loads(prompt.split("QUALITY FIND PAYLOAD:\n", 1)[1])
            pairs = payload["pairs"]
            if self._conflict_calls == 1:
                if self.kind == "clean":
                    return json.dumps({"findings": []})
                return json.dumps(
                    {
                        "findings": [
                            {
                                "pair_id": pairs[0]["pair_id"],
                                "conflict": "YES",
                                "reason": (
                                    "The general punctuation rule does not state "
                                    "whether named greetings are in scope."
                                ),
                                "question": "Which rule governs named greetings?",
                            },
                            {
                                "pair_id": pairs[-1]["pair_id"],
                                "conflict": "YES",
                                "reason": (
                                    "The exception and house rule do not identify "
                                    "the same greeting scope."
                                ),
                                "question": "Which greetings belong to the exception?",
                            },
                        ]
                    }
                )

            print("\nPOST-IMAGE AUDIT GATE · PRESS C", flush=True)
            if sys.stdin.readline().strip().lower() != "c":
                raise RuntimeError("Post-image Audit gate was not acknowledged.")
            if self.kind == "clean":
                return json.dumps({"findings": []})
            return json.dumps(
                {
                    "findings": [
                        {
                            "pair_id": pairs[0]["pair_id"],
                            "conflict": "YES",
                            "reason": (
                                "The complete result still leaves the named-greeting "
                                "exception unresolved."
                            ),
                            "question": "Should named greetings remain exceptions?",
                        }
                    ]
                }
            )

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
                            "direction": directions[index % len(directions)],
                        }
                        for index, item in enumerate(payload["audit"]["items"])
                    ]
                }
            )

        if operation == "update planning":
            self._update_calls += 1
            print("\nUPDATE PROVIDER GATE · PRESS U", flush=True)
            if sys.stdin.readline().strip().lower() != "u":
                raise RuntimeError("Update planning gate was not acknowledged.")
            if self._update_calls > 1:
                return json.dumps({"edits": [], "additions": [], "removals": []})
            payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
            source_ids = [
                memory["source_id"] for memory in payload["source"]["memories"]
            ]
            targets = payload["target"]["memories"]
            general = next(
                item
                for item in targets
                if item["content"] == "Named greetings always end with a period."
            )
            house = next(
                item
                for item in targets
                if item["content"] == "All greetings follow the house punctuation rule."
            )
            return json.dumps(
                {
                    "edits": [
                        {
                            "target_id": general["target_id"],
                            "new_content": (
                                "General greetings end with a period; named greetings "
                                "may omit punctuation."
                            ),
                            "source_ids": source_ids,
                            "reason": "Represent the confirmed named-greeting exception.",
                        },
                        {
                            "target_id": house["target_id"],
                            "new_content": (
                                "Non-named greetings follow the house punctuation rule."
                            ),
                            "source_ids": source_ids,
                            "reason": "Apply the supplied scope across the full candidate.",
                        },
                    ],
                    "additions": [],
                    "removals": [],
                }
            )

        if operation == MELD_COVERAGE_OPERATION:
            payload = json.loads(prompt.split("MELD COVERAGE PAYLOAD:\n", 1)[1])
            result_uids = [item["result_memory_uid"] for item in payload["post_image"]]
            return json.dumps(
                {
                    "overview": "Every frozen Source claim remains represented.",
                    "judgments": [
                        {
                            "claim_id": claim["claim_id"],
                            "status": "REPRESENTED",
                            "result_memory_uids": [
                                result_uids[index % len(result_uids)]
                            ],
                            "reason": "The complete post-image retains this claim.",
                        }
                        for index, claim in enumerate(payload["source_claims"])
                    ],
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
    from memcommit.adapters.console.commands.meld import entrypoint as meld_entrypoint
    from memcommit.adapters.console.commands.meld.workflow import (
        workflow as meld_workflow,
    )
    from memcommit.core.context import Context, Memory
    from memcommit.persistence.store import MemoryStore

    size = os.get_terminal_size()
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError(f"unexpected PTY size: {size.columns}x{size.lines}")

    store_root = Path(tempfile.mkdtemp(prefix="memcommit-meld-capture-")) / ".mem"
    _install_store(store_root)
    store = MemoryStore()
    incoming = Context(
        "10000000-0000-4000-8000-000000000001",
        "capture/meld/incoming",
    )
    incoming.add(
        Memory(
            "10000000-0000-4000-8000-000000000011",
            "Named greetings always end with a period.",
        )
    )
    baseline = Context(
        "20000000-0000-4000-8000-000000000002",
        "capture/meld/baseline",
    )
    baseline.add(
        Memory(
            "20000000-0000-4000-8000-000000000021",
            "Named greetings may omit punctuation.",
        )
    )
    baseline.add(
        Memory(
            "20000000-0000-4000-8000-000000000022",
            "All greetings follow the house punctuation rule.",
        )
    )
    store.create_context(incoming)
    store.create_context(baseline)
    store.set_current(baseline.name)

    provider = _MeldCaptureProvider(kind)
    meld_entrypoint.connect_codex_chatgpt_provider = lambda: provider
    meld_workflow.connect_codex_chatgpt_provider = lambda: provider
    target_name = "capture/meld/result"
    print(
        f"$ mem meld {incoming.name} {baseline.name} --to {target_name}",
        flush=True,
    )
    print(
        f"PTY · {size.columns}×{size.lines} · PROFILE isolated · CURRENT {baseline.name}",
        flush=True,
    )
    meld_entrypoint.cmd(left=incoming.name, right=baseline.name, to=target_name)

    print("CAPTURE GATE · PRESS V FOR POST-MELD CONTEXT", flush=True)
    if sys.stdin.readline().strip().lower() != "v":
        raise RuntimeError("Post-Meld Context gate was not acknowledged.")
    target = store.load_direct(target_name)
    saved = store.load_meld_session(target.uid)
    assert saved is not None and saved.candidate_review is not None
    assert saved.application is not None
    checkpoint = next(
        item
        for item in store.list_checkpoints(target_name)
        if item["uid"] == saved.application.checkpoint_uid
    )
    checkpoint_args = checkpoint["args"]
    meld_args = checkpoint_args.get("meld", checkpoint_args)
    print("\nCONTEXT AFTER MELD")
    for item in target.iter_items():
        if isinstance(item, Memory):
            print(f"  [{item.uid}] {item.content}")
    print(f"  SOURCES UNCHANGED · {incoming.name} + {baseline.name}")
    print(f"  CHECKPOINT COMMAND · {checkpoint['command']}")
    print(
        "  FINALIZED INPUTS · "
        + json.dumps(meld_args["decisions"], ensure_ascii=False)
    )
    print(
        "  UNRESOLVED AUDIT KEYS · "
        + str(len(meld_args["unresolved_audit_keys"]))
    )
    print(f"  SAVED SESSION STATE · {saved.state}")


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
    raw = recorder.getvalue()
    base._render(raw, stem)
    screen = base.pyte.Screen(COLUMNS, ROWS)
    base.pyte.Stream(screen).feed(raw)
    blinking_beam_is_active = (
        raw.rfind("\x1b[5 q") > raw.rfind("\x1b[0 q") and not screen.cursor.hidden
    )
    if blinking_beam_is_active:
        regular = base.ImageFont.truetype(base.FONT_PATH, 16, index=0)
        cell_width = base.math.ceil(regular.getlength("M"))
        cell_height = 21
        margin = 16
        image_path = OUT / f"{stem}.png"
        image = base.Image.open(image_path)
        draw = base.ImageDraw.Draw(image)
        x = margin + screen.cursor.x * cell_width + 1
        y = margin + screen.cursor.y * cell_height + 2
        draw.line((x, y, x, y + cell_height - 5), fill="#cad3f5", width=2)
        image.save(image_path)
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
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    recorder = _StreamRecorder()
    child.logfile_read = recorder
    return child, recorder


def _capture() -> None:
    child, recorder = _spawn("conflict")
    try:
        child.expect("MELD")
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

        child.send(DOWN)
        _settle(child)
        _snapshot(recorder, "04-intent-inline-field")

        child.send("The exception applies only to named greetings.")
        _settle(child)
        child.send("\r" + DOWN * 4)
        _settle(child)
        _snapshot(recorder, "05-finalize-two-decisions")

        child.send("\r")
        child.expect("UPDATE PROVIDER GATE")
        _settle(child)
        _snapshot(recorder, "06-whole-candidate-update")

        child.send("u\r")
        child.expect("POST-IMAGE AUDIT GATE")
        _settle(child)
        _snapshot(recorder, "07-post-image-audit")

        child.send("c\r")
        child.expect("MELD")
        _settle(child)
        _snapshot(recorder, "08-new-conflict-next-round")

        child.send(DOWN * 2 + "\r")
        _settle(child)
        _snapshot(recorder, "09-force-selected")

        child.send(DOWN + "\r")
        child.expect("UPDATE PROVIDER GATE")
        _settle(child)
        _snapshot(recorder, "10-second-update")

        child.send("u\r")
        child.expect("POST-IMAGE AUDIT GATE")
        _settle(child)
        _snapshot(recorder, "11-force-post-image-audit")

        child.send("c\r")
        child.expect("CAPTURE GATE")
        _settle(child)
        _snapshot(recorder, "12-applied-unresolved-receipt")

        child.send("v\r")
        child.expect(pexpect.EOF)
        child.close()
        if child.exitstatus != 0:
            raise RuntimeError(
                f"Meld capture child exited {child.exitstatus}.\n"
                + recorder.getvalue()[-4_000:]
            )
        _snapshot(recorder, "13-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_clean() -> None:
    child, recorder = _spawn("clean")
    try:
        child.expect("UPDATE PROVIDER GATE")
        _settle(child)
        _snapshot(recorder, "14-no-issue-direct-update")

        child.send("u\r")
        child.expect("POST-IMAGE AUDIT GATE")
        _settle(child)
        _snapshot(recorder, "15-no-issue-post-image-audit")

        child.send("c\r")
        child.expect("CAPTURE GATE")
        _settle(child)
        _snapshot(recorder, "16-no-issue-applied-receipt")

        child.send("v\r")
        child.expect(pexpect.EOF)
        child.close()
        if child.exitstatus != 0:
            raise RuntimeError(
                f"Clean Meld capture child exited {child.exitstatus}.\n"
                + recorder.getvalue()[-4_000:]
            )
        _snapshot(recorder, "17-no-issue-read-only-verification")
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
    _capture()
    _capture_clean()

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")
    if "\x1b[5 q" not in raw:
        raise RuntimeError("PTY stream did not request the blinking beam cursor.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(sys.argv[2])
    else:
        main()
