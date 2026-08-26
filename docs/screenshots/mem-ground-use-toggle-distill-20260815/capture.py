"""Capture one exact Ground USE toggle and its Distill exposure boundary."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
SPEC = importlib.util.spec_from_file_location("ground_use_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.OUT = OUT
ROWS = 52
COLUMNS = 180

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _PayloadProvider:
    def __init__(self) -> None:
        self.payload = None

    def complete(self, prompt, *, operation, output_schema=None):
        from memcommit.distill import DISTILL_PAYLOAD_MARKER

        self.payload = json.loads(prompt.split(DISTILL_PAYLOAD_MARKER, 1)[1])
        memories = self.payload["source"]["memories"]
        rule = {
            "content": "Use the reviewed ticker for the company.",
            "rationale": "The enabled Example supports it.",
            "support_memory_ids": [memories[0]["memory_id"]],
            "boundary_memory_ids": [],
        }
        rule_properties = (
            output_schema.get("properties", {})
            .get("rules", {})
            .get("items", {})
            .get("properties", {})
            if isinstance(output_schema, dict)
            else {}
        )
        if "goal_support" in rule_properties:
            rule["goal_support"] = False
        return json.dumps(
            {
                "overview": "Only enabled Ground Examples reached Distill.",
                "rules": [rule],
                "outside_memory_ids": [
                    memory["memory_id"] for memory in memories[1:]
                ],
            }
        )


def _prepare_store(root: Path):
    import memcommit.ops as ops
    from memcommit.ground import (
        GroundTargetSpec,
        bind_ground_workbench,
        create_ground_session,
        propose_ground_example,
        propose_ground_rule,
        upgrade_ground_to_propositions,
    )
    from memcommit.store import MemoryStore

    store = MemoryStore(root=root)
    raw = ops.init("toggle/raw")
    candidates = ops.init("toggle/examples")
    apple = ops.add(candidates, "Apple Inc.")
    google = ops.add(candidates, "Google LLC")
    target = ops.init("toggle/rules")
    for context in (raw, candidates, target):
        store.create_context(context)
    contexts = (raw, candidates, target)
    session = bind_ground_workbench(
        create_ground_session(
            "ticker-use",
            goal="Distill ticker Rules only from enabled reviewed Examples.",
        ),
        description="Choose which ticker Examples participate in Distill.",
        raw_context=raw,
        derived_context=candidates,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Publish reviewed ticker Rules.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    session = upgrade_ground_to_propositions(session)
    session = propose_ground_rule(
        session,
        rule="Use the reviewed synthetic ticker for each company.",
        rationale="The Examples define the intended transformation.",
        current_contexts=contexts,
    )
    rule = session.items_of_kind("RULE")[0]
    for source, ticker in ((apple, "AAPL"), (google, "GOOG")):
        session = propose_ground_example(
            session,
            proposition=(
                f'Applying the ticker Rules to "{source.content}" '
                f'produces "{ticker}".'
            ),
            rule_selectors=(rule.uid,),
            source_context_uid=candidates.uid,
            source_memory_uid=source.uid,
            target_context_names=(target.name,),
            input_text=source.content,
            expected_output=ticker,
            rationale="One reviewed synthetic ticker Example.",
            current_contexts=contexts,
            disposition="INCLUDE",
        )
    store.save_ground_session(session)
    return store, session


def _run_child(store_root: Path) -> None:
    # The exact approval launches `python -m memcommit.cli`; point both the TUI
    # and that child process at the same isolated default Profile Store.
    os.environ["HOME"] = str(store_root.parent)

    from memcommit.commands.ground.command import (
        _apply_named_ground_proposal,
        _ground_example_use_proposal,
    )
    from memcommit.commands.ground.named_shell import run_named_ground_shell
    from memcommit.ground_distill import execute_ground_distill, freeze_ground_distill

    store, session = _prepare_store(store_root)
    print("$ mem ground ticker-use", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    result = run_named_ground_shell(
        session,
        interpret=lambda *_args: (_ for _ in ()).throw(
            RuntimeError("Capture does not submit Ground dialogue.")
        ),
        apply=_apply_named_ground_proposal,
        prepare_use_toggle=_ground_example_use_proposal,
        reload_session=lambda name: store.load_ground_session(name),
        require_tty=True,
    )

    saved = store.load_ground_session(session.contract_name)
    assert saved is not None
    provider = _PayloadProvider()
    frozen = freeze_ground_distill(store, ground_name=session.contract_name)
    distilled = execute_ground_distill(
        frozen,
        store=store,
        provider_factory=lambda: provider,
    )
    memories = provider.payload["source"]["memories"]
    print("GROUND CLOSED · DURABLE AND PROVIDER-INPUT VERIFICATION")
    print(f"  SHELL RESULT · {result.status}")
    print(f"  GROUND REVISION · {session.revision} -> {saved.revision}")
    print(
        "  SAVED USE · "
        + " · ".join(
            f"c{index}={item.disposition}"
            for index, item in enumerate(saved.items_of_kind("CASE"), 1)
        )
    )
    print(f"  DISTILL SOURCE KIND · {frozen.source_kind}")
    print(f"  PROVIDER EXAMPLES · {len(memories)}")
    print(
        "  PROVIDER CONTENT · "
        + " | ".join(memory["content"] for memory in memories)
    )
    print(
        "  EXCLUDED GOOGLE TEXT PRESENT · "
        + str(any("Google LLC" in memory["content"] for memory in memories))
    )
    print(f"  DISTILLED RULES · {len(distilled.distill.analysis.rules)}", flush=True)


def _environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "HOME": str(home),
            # A temporary HOME isolates the default Store but would otherwise
            # hide the invoking interpreter's user-site capture dependencies.
            "PYTHONPATH": os.pathsep.join((str(ROOT), *sys.path)),
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(store_root: Path):
    recorder = BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", str(store_root)],
        cwd=str(ROOT),
        env=_environment(store_root.parent),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-ground-use-") as directory:
        store_root = Path(directory) / ".mem"
        child, recorder = _spawn(store_root)
        try:
            BASE._settle(child, seconds=0.8)
            child.send("\t\t\t\t\x1b[B")
            BASE._settle(child, seconds=0.4)
            BASE._snapshot(recorder, "01-selected-google-use-on")

            child.send(" ")
            BASE._settle(child, seconds=0.4)
            BASE._snapshot(recorder, "02-exact-use-off-approval")

            child.send("a")
            BASE._settle(child, seconds=0.8)
            BASE._snapshot(recorder, "03-use-off-applied")

            child.send("q")
            child.expect("GROUND CLOSED .* PROVIDER-INPUT VERIFICATION")
            BASE._settle(child, seconds=0.3)
            BASE._snapshot(recorder, "04-distill-provider-verification")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain true-color ANSI styles.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[2]))
    else:
        main()
