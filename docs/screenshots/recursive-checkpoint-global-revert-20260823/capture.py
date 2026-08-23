"""Capture one globally addressed recursive Checkpoint/Revert/Undo path."""

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
sys.path.insert(0, str(ROOT))
COLUMNS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
DOWN = "\x1b[B"
ESCAPE = "\x1b"
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


def _save_add(store, context, content: str) -> None:
    import memcommit.ops as ops
    from memcommit.context import AutoCheckpoint

    ops.add(context, content)
    store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={"content": content},
            description=f"Added {content}",
        ),
    )


def _prepare_store(store_dir: Path) -> None:
    import memcommit.ops as ops
    from memcommit.context import AutoCheckpoint
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_dir)
    root = ops.init("demo/recovery")
    store.save(
        root,
        AutoCheckpoint(
            command="init",
            args={"name": root.name},
            description="Initialized recursive recovery root",
        ),
    )
    _save_add(store, root, "root baseline")

    child = ops.init("demo/recovery/child")
    store.save(
        child,
        AutoCheckpoint(
            command="init",
            args={"name": child.name},
            description="Initialized recursive recovery child",
        ),
    )
    _save_add(store, child, "child baseline")
    store.set_current(root.name)


def _run_checkpoint(store_dir: Path) -> None:
    _configure_store(store_dir)
    from memcommit.commands.checkpoint import cmd

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    cmd(
        context_option="demo/recovery",
        message_option="recursive baseline",
        recursive=True,
    )


def _recursive_checkpoint_uid(store_dir: Path) -> str:
    _configure_store(store_dir)
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    for checkpoint in store.list_checkpoints("demo/recovery"):
        args = checkpoint.get("args")
        if (
            checkpoint.get("command") == "checkpoint"
            and isinstance(args, dict)
            and isinstance(args.get("checkpoint_set"), dict)
        ):
            return str(checkpoint["uid"])
    raise RuntimeError("Recursive checkpoint was not recorded.")


def _mutate_after_checkpoint(store_dir: Path) -> int:
    _configure_store(store_dir)
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    root = store.load_direct("demo/recovery")
    child = store.load_direct("demo/recovery/child")
    _save_add(store, root, "root newer")
    _save_add(store, child, "child newer")
    checkpoint_uid = _recursive_checkpoint_uid(store_dir)
    entries = store.list_checkpoints(root.name)
    return next(
        index for index, entry in enumerate(entries) if entry["uid"] == checkpoint_uid
    )


def _run_revert(store_dir: Path) -> None:
    _configure_store(store_dir)
    from memcommit.commands.revert import cmd

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    cmd()


def _run_undo(store_dir: Path) -> None:
    _configure_store(store_dir)
    from memcommit.commands.undo import cmd

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    cmd()


def _memory_contents(store, name: str) -> list[str]:
    from memcommit.context import Memory

    context = store.load_direct(name)
    return [item.content for item in context.iter_items() if isinstance(item, Memory)]


def _run_verification(store_dir: Path, expected: str) -> None:
    _configure_store(store_dir)
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    root = _memory_contents(store, "demo/recovery")
    child = _memory_contents(store, "demo/recovery/child")
    if expected == "baseline":
        verified = root == ["root baseline"] and child == ["child baseline"]
        title = "READ-ONLY GROUP REVERT VERIFICATION"
    else:
        verified = root == ["root baseline", "root newer"] and child == [
            "child baseline",
            "child newer",
        ]
        title = "READ-ONLY GROUP UNDO VERIFICATION"
    print(title)
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    print(f"Current Context: {store.current_context_name()}")
    print(f"demo/recovery: {root}")
    print(f"demo/recovery/child: {child}")
    print(f"BOTH CONTEXTS {expected.upper()}: {verified}")


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PYTHONPATH": os.pathsep.join(
                (str(ROOT), environment.get("PYTHONPATH", ""))
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
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _pump(child: pexpect.spawn, recorder: _Recorder, *, seconds: float = 0.6) -> None:
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


def _capture_child(stem: str, *args: str, expect: str) -> str:
    child, recorder = _spawn(*args)
    try:
        child.expect(expect)
        child.expect(pexpect.EOF)
        _snapshot(recorder, stem)
        return recorder.getvalue()
    finally:
        if child.isalive():
            child.close(force=True)


def _capture(store_dir: Path) -> None:
    checkpoint_raw = _capture_child(
        "01-recursive-checkpoint-receipt",
        "--checkpoint",
        str(store_dir),
        expect="Revert: mem revert",
    )
    checkpoint_uid = _recursive_checkpoint_uid(store_dir)
    assert f"Revert: mem revert {checkpoint_uid} --keep" in checkpoint_raw
    selected_row = _mutate_after_checkpoint(store_dir)

    child, recorder = _spawn("--revert", str(store_dir))
    try:
        child.expect("REVERT · demo/recovery")
        _pump(child, recorder)
        _snapshot(recorder, "02-history-entry")

        if selected_row:
            child.send(DOWN * selected_row)
            _pump(child, recorder)
        _snapshot(recorder, "03-recursive-unit-focused")

        child.send("\r")
        _pump(child, recorder)
        _snapshot(recorder, "04-complete-unit-command-review")
        command_review = (OUT / "04-complete-unit-command-review.txt").read_text(
            encoding="utf-8"
        )
        assert (
            f"mem revert {checkpoint_uid} --context demo/recovery --keep"
            in command_review
        )
        assert "FOCUS PROPOSED COMMAND" in command_review
        assert "The complete checkpoint unit will restore 2 Contexts" in command_review
        assert "demo/recovery/child" in command_review

        child.send(ESCAPE)
        _pump(child, recorder)
        _snapshot(recorder, "05-keep-all-policy-review")
        assert "FOCUS HISTORY" in (OUT / "05-keep-all-policy-review.txt").read_text(
            encoding="utf-8"
        )

        child.send("\r")
        _pump(child, recorder)
        child.send("\r")
        child.expect("Reverted checkpoint unit")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "06-group-revert-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    _capture_child(
        "07-read-only-revert-verification",
        "--verify",
        str(store_dir),
        "baseline",
        expect="BOTH CONTEXTS BASELINE: True",
    )
    _capture_child(
        "08-group-undo-receipt",
        "--undo",
        str(store_dir),
        expect="Undid command",
    )
    _capture_child(
        "09-read-only-undo-verification",
        "--verify",
        str(store_dir),
        "newer",
        expect="BOTH CONTEXTS NEWER: True",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="memcommit-recursive-revert-capture-"
    ) as temporary:
        store_dir = Path(temporary) / "store"
        _prepare_store(store_dir)
        _capture(store_dir)
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--checkpoint":
        _run_checkpoint(Path(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == "--revert":
        _run_revert(Path(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == "--undo":
        _run_undo(Path(sys.argv[2]))
    elif len(sys.argv) == 4 and sys.argv[1] == "--verify":
        _run_verification(Path(sys.argv[2]), sys.argv[3])
    else:
        main()
