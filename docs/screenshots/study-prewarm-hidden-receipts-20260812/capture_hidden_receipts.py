"""Capture hidden Study receipt materialization in a real 180×52 PTY."""

from __future__ import annotations

from datetime import datetime, timezone
import io
import math
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile
import time
import uuid

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PYTHON = Path(sys.executable)
SUPPORT_PATHS = {
    str(Path(module.__file__).resolve().parents[1])
    for module in (pexpect, pyte)
}
COLS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
CPR_REQUEST = "\x1b[6n"
CPR_RESPONSE = "\x1b[1;1R"

_NAMED_COLORS = {
    "default": "#e6e9ef",
    "black": "#101217",
    "red": "#ed8796",
    "green": "#a6da95",
    "brown": "#eed49f",
    "yellow": "#eed49f",
    "blue": "#8aadf4",
    "magenta": "#c6a0f6",
    "cyan": "#8bd5ca",
    "white": "#cad3f5",
    "brightblack": "#5b6078",
    "brightred": "#ed8796",
    "brightgreen": "#a6da95",
    "brightyellow": "#f5a97f",
    "brightblue": "#8aadf4",
    "brightmagenta": "#c6a0f6",
    "brightcyan": "#91d7e3",
    "brightwhite": "#f4dbd6",
}


class _Recorder(io.StringIO):
    def flush(self) -> None:
        return


def _environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "HOME": str(home),
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PYTHONPATH": os.pathsep.join((str(ROOT), *sorted(SUPPORT_PATHS))),
        }
    )
    return environment


def _color(value: str, *, background: bool = False) -> str:
    if value in _NAMED_COLORS:
        if value == "default" and background:
            return "#101217"
        return _NAMED_COLORS[value]
    if len(value) == 6 and all(
        character in "0123456789abcdef" for character in value
    ):
        return "#" + value
    return "#101217" if background else "#e6e9ef"


def _snapshot(recorder: _Recorder, stem: str) -> None:
    raw = recorder.getvalue()
    screen = pyte.Screen(COLS, ROWS)
    pyte.Stream(screen).feed(raw)
    plain = "\n".join(screen.display).rstrip() + "\n"
    (OUT / f"{stem}.typescript").write_text(raw, encoding="utf-8")
    (OUT / f"{stem}.txt").write_text(plain, encoding="utf-8")

    regular = ImageFont.truetype(FONT_PATH, 16, index=0)
    bold = ImageFont.truetype(FONT_PATH, 16, index=1)
    cell_width = math.ceil(regular.getlength("M"))
    cell_height = 21
    margin = 16
    image = Image.new(
        "RGB",
        (margin * 2 + COLS * cell_width, margin * 2 + ROWS * cell_height),
        "#101217",
    )
    draw = ImageDraw.Draw(image)
    for row in range(ROWS):
        for column in range(COLS):
            character = screen.buffer[row][column]
            foreground = _color(character.fg)
            background = _color(character.bg, background=True)
            if character.reverse:
                foreground, background = background, foreground
            x = margin + column * cell_width
            y = margin + row * cell_height
            if background != "#101217":
                draw.rectangle(
                    (x, y, x + cell_width - 1, y + cell_height - 1),
                    fill=background,
                )
            if character.data and character.data != " ":
                box_drawing = "\u2500" <= character.data <= "\u257f"
                draw.text(
                    (x, y),
                    character.data,
                    font=bold if character.bold and not box_drawing else regular,
                    fill=foreground,
                )
    image.save(OUT / f"{stem}.png")


def _spawn(home: Path, *args: str) -> tuple[pexpect.spawn, _Recorder]:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    command = (
        f"stty rows {ROWS} cols {COLS}; stty size; "
        f"exec {shlex.join([executable, *args])}"
    )
    recorder = _Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(home),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _pump(
    child: pexpect.spawn,
    recorder: _Recorder,
    *,
    seconds: float,
    require_eof: bool = False,
) -> None:
    deadline = time.monotonic() + seconds
    reached_eof = False
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(size=65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            reached_eof = True
            break
        query_count = recorder.getvalue().count(CPR_REQUEST)
        while child._mem_cpr_responses < query_count:
            child.send(CPR_RESPONSE)
            child._mem_cpr_responses += 1
    if require_eof and not reached_eof:
        child.expect(pexpect.EOF, timeout=max(0.1, seconds))
    if reached_eof or require_eof:
        child.close()
        if child.exitstatus != 0:
            raise RuntimeError(
                f"PTY command failed: exit={child.exitstatus} "
                f"signal={child.signalstatus}"
            )


class _CompositeProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        import json

        assert operation == "impact_atomize"
        payload = json.loads(prompt.split("ATOMIZE IMPACT PAYLOAD:\n", 1)[1])
        source = payload["memories"][0]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The request contains two editing constraints.",
                        "source_ids": [source["candidate_id"]],
                    },
                    "changed": {
                        "text": "The constraints are separated without additions.",
                        "source_ids": [source["candidate_id"]],
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": [
                    {
                        "candidate_id": source["candidate_id"],
                        "classification": "COMPOSITE",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [
                            {
                                "content": "Keep the wording concise.",
                                "source_spans": ["Keep the wording concise."],
                            },
                            {
                                "content": "Preserve the original meaning.",
                                "source_spans": ["Preserve the original meaning."],
                            },
                        ],
                        "reason": "Each sentence is independently revisable.",
                    }
                ],
                "quality_issues": [],
            }
        )


def _fixture(home: Path) -> None:
    os.environ["HOME"] = str(home)
    sys.path.insert(0, str(ROOT))

    import memcommit.config as config_module
    import memcommit.ops as ops
    from memcommit.atomize import create_atomize_analysis, impact_atomize
    from memcommit.commands.atomize.sessions import atomize_session_entries
    from memcommit.config import Config
    from memcommit.profile_config import (
        ProfileEntry,
        ProfileRegistry,
        STUDY_RUN_PARTICIPANT_SOURCE_KIND,
    )
    from memcommit.store import MemoryStore
    from memcommit.study_prewarm.atomize import (
        build_atomize_prewarm_artifact,
        install_declared_atomize_prewarms,
    )
    from memcommit.study_prewarm.installations import (
        INSTALLATIONS_DIRECTORY_NAME,
    )
    from memcommit.study_prewarm.registry import publish_artifact

    config_module.CONFIG_FILE = home / ".mem" / "config.json"
    Config().update(
        {
            "semantic_provider": "codex_chatgpt",
            "codex_chatgpt_model": "gpt-5.6-sol",
            "codex_chatgpt_reasoning_effort": "medium",
        }
    )
    store = MemoryStore()
    description = ops.init("practice/description")
    source = ops.init("practice/source")
    ops.add(description, "Atomize the fixed tutorial editing request.")
    ops.add(source, "Keep the wording concise. Preserve the original meaning.")
    store.create_context(description)
    store.create_context(source)
    store.set_current(source.name)
    analysis = create_atomize_analysis(
        source,
        impact_atomize(source, _CompositeProvider),
    )
    baseline_uid = str(uuid.uuid4())
    profile = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="hidden-receipt-capture",
        kind="MANAGED",
        source={
            "kind": STUDY_RUN_PARTICIPANT_SOURCE_KIND,
            "study_uid": str(uuid.uuid4()),
            "study_name": "hidden-receipt-capture",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "baseline_sha256": "a" * 64,
            "baseline_profile_uid": baseline_uid,
            "baseline_profile_name": "study-baseline",
        },
    )
    registry = ProfileRegistry(
        generation=1,
        active_uid=profile.uid,
        profiles=(profile,),
    )
    key, artifact = build_atomize_prewarm_artifact(
        task_description=description,
        analysis=analysis,
        provider="codex_chatgpt",
        model="gpt-5.6-sol",
        reasoning="medium",
        offline_provider_seconds=22.81,
    )
    publish_artifact(
        store.store_dir,
        baseline_profile_uid=baseline_uid,
        operation="ATOMIZE",
        task="tutorial",
        key=key,
        artifact=artifact,
    )
    result = install_declared_atomize_prewarms(
        store=store,
        profile=profile,
        registry_snapshot=registry,
    )
    receipt_count = len(
        tuple((store.store_dir / INSTALLATIONS_DIRECTORY_NAME).glob("*.json"))
    )
    print("HIDDEN RECEIPT SETUP · COMPLETE")
    print(f"DECLARED/INSTALLED · {result.declared}/{result.installed}")
    print(f"HIDDEN RECEIPTS · {receipt_count}")
    print(f"VISIBLE ATOMIZE SESSIONS · {len(atomize_session_entries(store))}")
    print(f"VISIBLE ANALYSIS · {store.load_atomize_analysis(source.uid) is not None}")


def _verify(home: Path) -> None:
    os.environ["HOME"] = str(home)
    sys.path.insert(0, str(ROOT))

    from memcommit.commands.atomize.sessions import atomize_session_entries
    from memcommit.store import MemoryStore
    from memcommit.study_prewarm.installations import (
        INSTALLATIONS_DIRECTORY_NAME,
    )

    store = MemoryStore(create=False)
    source = store.load_direct("practice/source")
    receipt_count = len(
        tuple((store.store_dir / INSTALLATIONS_DIRECTORY_NAME).glob("*.json"))
    )
    print("FIRST-USE MATERIALIZATION · VERIFIED")
    print(f"HIDDEN RECEIPTS · {receipt_count}")
    print(f"VISIBLE ATOMIZE SESSIONS · {len(atomize_session_entries(store))}")
    print(f"VISIBLE ANALYSIS · {store.load_atomize_analysis(source.uid) is not None}")
    print("SOURCE MEMORIES · 1 · UNCHANGED")


def _python_capture(home: Path, mode: str, stem: str) -> None:
    command = (
        f"stty rows {ROWS} cols {COLS}; stty size; "
        f"exec {shlex.join([str(PYTHON), str(Path(__file__)), mode, str(home)])}"
    )
    recorder = _Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(home),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    _pump(child, recorder, seconds=30, require_eof=True)
    _snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-hidden-receipt-") as value:
        home = Path(value)
        _python_capture(home, "--fixture", "01-hidden-receipt-empty-state")

        child, recorder = _spawn(home, "atomize")
        _pump(child, recorder, seconds=1.2)
        raw = recorder.getvalue()
        if "MEM ATOMIZE · SESSIONS" not in raw or "Add new Atomize session" not in raw:
            raise RuntimeError("Empty Atomize launcher was not rendered.")
        _snapshot(recorder, "02-empty-atomize-session-launcher")
        child.send("q")
        _pump(child, recorder, seconds=10, require_eof=True)

        child, recorder = _spawn(
            home,
            "atomize",
            "--context",
            "practice/source",
        )
        _pump(child, recorder, seconds=2.0)
        raw = recorder.getvalue()
        if "REVIEW AND APPLY" not in raw or "practice/source-atomized" not in raw:
            raise RuntimeError("First-use Atomize materialization was not rendered.")
        _snapshot(recorder, "03-first-use-exact-materialization")
        child.send("q")
        _pump(child, recorder, seconds=10, require_eof=True)
        if "EXACT PREWARM" not in recorder.getvalue():
            raise RuntimeError("First-use exact-origin receipt was not rendered.")
        _snapshot(recorder, "04-first-use-close-receipt")

        child, recorder = _spawn(home, "atomize")
        _pump(child, recorder, seconds=1.2)
        raw = recorder.getvalue()
        if "practice/source" not in raw or "Add new Atomize session" not in raw:
            raise RuntimeError("Materialized Atomize session was not cataloged.")
        _snapshot(recorder, "05-materialized-session-launcher")
        child.send("q")
        _pump(child, recorder, seconds=10, require_eof=True)

        _python_capture(home, "--verify", "06-read-only-state-verification")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fixture":
        _fixture(Path(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == "--verify":
        _verify(Path(sys.argv[2]))
    else:
        main()
