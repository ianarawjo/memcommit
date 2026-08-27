"""Capture location-first Revert and its reviewed history policy in a real PTY."""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
COLUMNS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
DOWN = "\x1b[B"
RIGHT = "\x1b[C"
BACKSPACE = "\x7f"
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


def _configure_store(store_dir: Path) -> None:
    import memcommit.store as store_module

    store_module.STORE_DIR = store_dir
    store_module.CONTEXTS_DIR = store_dir / "contexts"
    store_module.STATE_FILE = store_dir / "state.json"
    store_module.QUERY_SOURCES_DIR = store_dir / "query-sources"
    store_module.IMPACT_PLAN_FILE = store_dir / "impact-plan.json"
    store_module.STAGED_UPDATE_FILE = store_dir / "staged-update.json"
    store_module.REVIEW_SESSION_FILE = store_dir / "review-session.json"
    store_module.ATOMIZE_ANALYSES_DIR = store_dir / "atomize-analyses"
    store_module.ATOMIZE_WORKBENCHES_DIR = store_dir / "atomize-workbenches"
    store_module.ATOMIZE_GROUNDING_SESSIONS_DIR = store_dir / "atomize-groundings"
    store_module.ATOMIZE_GROUNDING_HISTORY_DIR = store_dir / "atomize-grounding-history"
    store_module.GROUND_SESSIONS_DIR = store_dir / "ground-sessions"
    store_module.MELD_SESSIONS_DIR = store_dir / "meld-sessions"


def _prepare_store(store_dir: Path) -> tuple[str, ...]:
    import memcommit.application.ops as ops
    from memcommit.context import AutoCheckpoint
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_dir)
    participant = ops.init("task-1/participant")
    store.save(participant)

    recovery = ops.init("task-1/recovery")
    analysis_uid = "00000000-0000-4000-8000-000000000001"
    store.save(
        recovery,
        AutoCheckpoint(
            command="init",
            args={
                "name": recovery.name,
                "source_analysis_uid": analysis_uid,
            },
            description="Initialized recovery Context before applying atomize",
        ),
    )
    ops.add(recovery, "Keep this first recovery Memory.")
    store.save(
        recovery,
        AutoCheckpoint(
            command="atomize",
            args={"analysis_uid": analysis_uid},
            description="Applied atomize to create first recovery Memory",
        ),
    )
    ops.add(recovery, "Remove this newer recovery Memory.")
    store.save(
        recovery,
        AutoCheckpoint(
            command="add",
            args={"content": "Remove this newer recovery Memory."},
            description="Added newer recovery Memory",
        ),
    )
    original_uids = tuple(
        checkpoint["uid"] for checkpoint in store.list_checkpoints(recovery.name)
    )
    store.set_current(participant.name)
    return original_uids


def _run_revert(store_dir: Path) -> None:
    _configure_store(store_dir)
    from memcommit.commands.revert.command import cmd

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    cmd()


def _run_verification(store_dir: Path, original_uids: tuple[str, ...]) -> None:
    _configure_store(store_dir)
    from memcommit.context import Memory
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    target = store.load_direct("task-1/recovery")
    checkpoints = store.list_checkpoints(target.name)
    retained = {checkpoint["uid"] for checkpoint in checkpoints}
    contents = [
        item.content for item in target.iter_items() if isinstance(item, Memory)
    ]
    print("READ-ONLY REVERT VERIFICATION")
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    print(f"Current Context: {store.current_context_name()}")
    print(f"Target Context: {target.name}")
    print(f"Target Memories: {contents}")
    print(f"Visible checkpoints: {len(checkpoints)}")
    print(
        "Commands, recent first: " + ", ".join(str(cp["command"]) for cp in checkpoints)
    )
    print(
        "KEEP ALL VERIFIED: "
        + str(set(original_uids).issubset(retained))
        + " · CURRENT POINTER UNCHANGED: "
        + str(store.current_context_name() == "task-1/participant")
    )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PYTHONPATH": os.pathsep.join(
                (str(ROOT / "src"), environment.get("PYTHONPATH", ""))
            ),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _color(value: str, *, background: bool = False) -> str:
    if value in _NAMED_COLORS:
        if value == "default" and background:
            return "#101217"
        return _NAMED_COLORS[value]
    if len(value) == 6 and all(character in "0123456789abcdef" for character in value):
        return "#" + value
    return "#101217" if background else "#e6e9ef"


def _render(raw: str, stem: str) -> None:
    screen = pyte.Screen(COLUMNS, ROWS)
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
        (margin * 2 + COLUMNS * cell_width, margin * 2 + ROWS * cell_height),
        "#101217",
    )
    draw = ImageDraw.Draw(image)
    for row in range(ROWS):
        for column in range(COLUMNS):
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


def _snapshot(recorder: _Recorder, stem: str) -> None:
    _render(recorder.getvalue(), stem)


def _spawn(*args: str) -> tuple[pexpect.spawn, _Recorder]:
    command = (
        f"stty rows {ROWS} cols {COLUMNS}; stty size; "
        f"exec {shlex.join([sys.executable, str(Path(__file__).resolve()), *args])}"
    )
    recorder = _Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _pump(child: pexpect.spawn, recorder: _Recorder, *, seconds: float = 0.5) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(size=65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            return
        query_count = recorder.getvalue().count(CPR_REQUEST)
        while child._mem_cpr_responses < query_count:
            child.send(CPR_RESPONSE)
            child._mem_cpr_responses += 1


def _capture(store_dir: Path, original_uids: tuple[str, ...]) -> None:
    child, recorder = _spawn("--child", str(store_dir))
    try:
        child.expect("REVERT · SELECT A CONTEXT")
        _pump(child, recorder)
        _snapshot(recorder, "01-context-picker-empty-current")

        child.send("\r")
        child.expect("No checkpoints for this Context yet")
        _pump(child, recorder)
        _snapshot(recorder, "02-empty-history-view")

        child.send(BACKSPACE)
        _pump(child, recorder)
        child.send(DOWN + RIGHT)
        child.expect_exact("[created]")
        _pump(child, recorder)
        _snapshot(recorder, "03-created-atomize-boundary")

        child.send("\r")
        child.expect("REVERT · task-1/recovery")
        _pump(child, recorder)
        _snapshot(recorder, "04-recovery-checkpoints")

        child.send(DOWN * 2)
        _pump(child, recorder)
        _snapshot(recorder, "05-target-impact-preview")

        child.send("\r")
        _pump(child, recorder)
        _snapshot(recorder, "06-discard-newer-policy")

        child.send(RIGHT)
        _pump(child, recorder)
        _snapshot(recorder, "07-keep-all-policy")

        child.send("\r")
        _pump(child, recorder)
        _snapshot(recorder, "08-exact-apply")

        child.send("\r")
        child.expect("Reverted Context")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "09-success-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    verification_args = (
        "--verify",
        str(store_dir),
        *original_uids,
    )
    verify, verify_recorder = _spawn(*verification_args)
    try:
        verify.expect("KEEP ALL VERIFIED: True")
        verify.expect("CURRENT POINTER UNCHANGED: True")
        verify.expect(pexpect.EOF)
        _snapshot(verify_recorder, "10-read-only-verification")
    finally:
        if verify.isalive():
            verify.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-revert-capture-") as temporary:
        store_dir = Path(temporary) / "store"
        original_uids = _prepare_store(store_dir)
        _capture(store_dir, original_uids)
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_revert(Path(sys.argv[2]))
    elif len(sys.argv) >= 4 and sys.argv[1] == "--verify":
        _run_verification(Path(sys.argv[2]), tuple(sys.argv[3:]))
    else:
        main()
