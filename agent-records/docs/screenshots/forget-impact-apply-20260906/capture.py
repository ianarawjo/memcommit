"""Capture direct Forget approval in an isolated, actual 180x52 color PTY.

Run with a Python that provides pexpect, pyte and Pillow. The CLI child uses
this repository's .venv, so capture-only packages are not project dependencies.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
INSTRUCTION = "Forget the obsolete desk location and access code; keep accessibility guidance."
CONTENTS = (
    "The desk was beside the west entrance. The route remains step-free.",
    "The obsolete access code was 4815.",
    "Visitors should verify the step-free route before arrival.",
)


def child_main(sandbox: Path, scenario: str) -> None:
    from memcommit.application.operations.profile import config
    config.default_store_dir = lambda: sandbox / "store"
    config.profile_control_dir = lambda: sandbox / "profiles"
    from memcommit.application.capabilities import ops
    from memcommit.persistence.store import MemoryStore
    from memcommit.adapters.console.entrypoint import app
    from memcommit.adapters.console.commands.forget import command
    from memcommit.adapters.console.commands.forget.workbench import screen
    import click

    active = MemoryStore()
    owner = active
    if scenario == "granted":
        import uuid
        authority = config.ProfileEntry(uid=str(uuid.uuid4()), name="authority", kind="MANAGED")
        authoring = config.ProfileEntry(uid=config.AUTHORING_PROFILE_UID, name=config.AUTHORING_PROFILE_NAME, kind="AUTHORING")
        registry = config.ProfileRegistry(generation=1, active_uid=authoring.uid, profiles=(authoring, authority), grants=())
        registry_path = config.profile_registry_file()
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(json.dumps(registry.to_dict()) + "\n")
        owner = MemoryStore(root=config.profile_store_dir(authority))
        participant = ops.init("participant")
        ops.add(participant, "Participant-owned Memory stays unchanged.")
        active.create_context(participant)
        active.set_current(participant.name)
    context = ops.init("notes")
    ops.add_many(context, list(CONTENTS))
    owner.create_context(context)
    owner.set_current(context.name)
    if scenario == "granted":
        from memcommit.application.operations.profile.model import create_authority_grant
        create_authority_grant(authority_name="authority", grantee_name=config.AUTHORING_PROFILE_NAME, resource_name="notes", permissions=("READ", "UPDATE", "DELETE"))
    else:
        active.set_current(context.name)
    source_name = "granted/authority/notes" if scenario == "granted" else "notes"
    before = owner.load_direct("notes").to_dict()
    checkpoints = owner.list_checkpoints("notes")
    participant_before = active.load_direct("participant").to_dict() if scenario == "granted" else None

    class Provider:
        calls = 0
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "forget" and output_schema is not None
            self.calls += 1
            if scenario == "apply":
                (sandbox / "provider-entered").touch()
                deadline = time.monotonic() + 45
                while not (sandbox / "release-provider").exists():
                    if time.monotonic() > deadline:
                        raise RuntimeError("Fixture response was not released.")
                    time.sleep(0.05)
            messages = json.loads(prompt.split("FORGET CHAT MESSAGES:\n", 1)[1])
            payload = json.loads(messages[1]["content"].split("FORGET PAYLOAD:\n", 1)[1])
            records = []
            for index, source in enumerate(payload["source"]["memories"]):
                if scenario == "noop" or index == 2:
                    decision, text, reason = "KEEP", source["content"], "Retain the general accessibility guidance."
                elif index == 0:
                    decision, text, reason = "EDIT", "The route remains step-free.", "Remove the obsolete desk location and retain the independent guidance."
                else:
                    decision, text, reason = "DELETE", "", "The instruction covers the obsolete access code."
                records.append({"source_memory_id": source["item_id"], "decision": decision, "proposed_content": text, "rationale": reason, "criterion_item_ids": ["k1"]})
            return json.dumps({"overview": "Retain accessibility guidance and remove the obsolete location and code.", "candidates": records})

    provider = Provider()
    command.connect_codex_chatgpt_provider = lambda: provider
    if scenario == "stale":
        original = screen.run_resolution_workbench_shell
        def with_concurrent_write(*args, **kwargs):
            action = original(*args, **kwargs)
            current = owner.load_direct("notes")
            ops.add(current, "A concurrent writer added this Memory during inspection.")
            owner.save(current)
            return action
        screen.run_resolution_workbench_shell = with_concurrent_write

    assert os.get_terminal_size() == (180, 52)
    print(f"LIVE PTY 180 x 52 · isolated authoring · current {active.current_context_name()} · {scenario}", flush=True)
    instruction = "Keep everything unchanged." if scenario == "noop" else INSTRUCTION
    print(f'$ mem forget "{instruction}" --from {source_name}', flush=True)
    code = 0
    try:
        returned = app(prog_name="mem", args=["forget", instruction, "--from", source_name], standalone_mode=False)
        if isinstance(returned, int):
            code = returned
    except click.exceptions.Exit as error:
        code = error.exit_code
    print(f"CAPTURE COMMAND RETURNED · exit {code}", flush=True)
    assert code == (1 if scenario == "stale" else 0)
    if scenario != "noop":
        sys.stdin.readline()  # Harness gate separating receipt and read-only verification.
        print("\x1b[2J\x1b[H", end="", flush=True)
    print(f"$ mem show {source_name} --direct", flush=True)
    app(prog_name="mem", args=["show", source_name, "--direct"], standalone_mode=False)
    after = owner.load_direct("notes")
    values = [m.content for m in after.iter_items()]
    if scenario in {"apply", "granted"}:
        assert values == ["The route remains step-free.", CONTENTS[2]]
        assert len(owner.list_checkpoints("notes")) == len(checkpoints) + 1
        outcome = "one edit, one removal, one retained Memory; one owner checkpoint"
    else:
        assert all(text in values for text in CONTENTS)
        assert owner.list_checkpoints("notes") == checkpoints
        if scenario == "stale":
            assert len(values) == 4
            outcome = "stale Apply rejected; original Memories and concurrent addition preserved; no checkpoint"
        else:
            assert after.to_dict() == before
            outcome = "Source unchanged; no checkpoint or application receipt"
    if participant_before is not None:
        assert active.load_direct("participant").to_dict() == participant_before
        assert active.list_checkpoints("participant") == []
        outcome += "; participant unchanged"
    assert provider.calls == 1
    print("VERIFIED · " + outcome, flush=True)
    print("PROVIDER · one deterministic fixture response; no external service", flush=True)


def main() -> None:
    import pexpect
    spec = importlib.util.spec_from_file_location("terminal_capture_renderer", ROOT / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py")
    assert spec and spec.loader
    render = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render)
    render.OUT = OUT
    env = os.environ.copy()
    env.pop("NO_COLOR", None)
    env.update({"TERM": "xterm-256color", "COLORTERM": "truecolor", "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT", "PROMPT_TOOLKIT_NO_CPR": "1", "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1", "PYTHONPATH": str(ROOT / "src")})
    steps = []
    def capture_scenario(scenario):
        with tempfile.TemporaryDirectory(prefix="mem-forget-impact-") as temp:
            sandbox = Path(temp)
            recorder = render._StreamRecorder()
            child = pexpect.spawn(str(ROOT / ".venv/bin/python"), [str(Path(__file__).resolve()), "--child", str(sandbox), scenario], cwd=str(ROOT), env=env, dimensions=(52,180), encoding="utf-8", codec_errors="replace", timeout=20)
            child.logfile_read = recorder
            def wait(text):
                render._wait_for_visible(child, recorder, text, seconds=20)
                render._pump(child, seconds=0.3)
            def snap(label, keys, durable):
                stem = f"{len(steps)+1:02d}-{label}"
                render._snapshot(recorder, stem)
                steps.append({"image":stem+".png", "scenario":scenario, "keys":keys, "durable":durable})
                print("CAPTURED " + stem, flush=True)
            try:
                if scenario == "apply":
                    deadline=time.monotonic()+20
                    while not (sandbox/"provider-entered").exists():
                        render._pump(child,seconds=0.1)
                        if time.monotonic()>deadline:raise RuntimeError("No provider entry")
                    snap("analysis-entry", "explicit command; no keys", "fixture setup only")
                    (sandbox/"release-provider").touch()
                if scenario == "noop":
                    child.expect(pexpect.EOF, timeout=20)
                    child.close()
                    assert child.exitstatus == 0
                    snap("noop-receipt-and-verification", "explicit all-KEEP command, then read-only Show", "none")
                else:
                    wait("IMPACT · FORGET")
                    snap(scenario+"-impact", "provider response; no keys", "none; complete process-local batch only")
                    if scenario == "cancel":
                        child.send("\x1b")
                    else:
                        child.send("\x1b[Z")
                        render._pump(child,seconds=0.4)
                        if scenario == "apply":snap("apply-focused", "Shift-Tab", "none")
                        child.send("\r")
                    wait("CAPTURE COMMAND RETURNED")
                    snap(scenario+"-receipt", "Escape" if scenario=="cancel" else "Enter on Apply", "owner edit/removal/checkpoint" if scenario in {"apply","granted"} else "none from Forget; stale scenario preserves a concurrent write")
                    child.send("\r")
                    child.expect(pexpect.EOF, timeout=20)
                    child.close()
                    assert child.exitstatus == 0
                    snap(scenario+"-verification", "harness gate Enter; mem show notes --direct", "none")
                raw=recorder.getvalue()
                assert "LIVE PTY 180 x 52" in raw
                if scenario != "noop":
                    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);",raw)
                    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);",raw)
            except BaseException:
                print("\n".join(render._screen(recorder.getvalue()).display).rstrip(),flush=True)
                raise
            finally:
                if child.isalive():child.close(force=True)
    for scenario in ("apply","cancel","granted","noop","stale"):
        capture_scenario(scenario)
    (OUT/"interaction.json").write_text(json.dumps({"base_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"viewport":[180,52],"profile":"isolated virtual authoring; separate isolated authority for granted scenario","current_context":"notes; participant for granted scenario","command":'mem forget "'+INSTRUCTION+'" --from notes',"provenance":"actual color-preserving PTY stream rendered with pyte/Pillow; deterministic provider only","steps":steps},ensure_ascii=False,indent=2)+"\n")


if __name__ == "__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--child":child_main(Path(sys.argv[2]),sys.argv[3])
    else:main()
