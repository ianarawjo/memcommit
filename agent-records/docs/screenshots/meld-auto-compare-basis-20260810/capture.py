"""Capture the missing-Compare symmetric Meld path in an isolated real PTY."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

from PIL import Image, ImageDraw, ImageFont
import pexpect
import pyte


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
LEFT = "task-2/advisor1"
RIGHT = "task-2/advisor2"
TARGET = "task-2/participant/proposal-workspace2"
CURRENT = "task-3/local/personal-memory"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


class _Recorder:
    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, value: bytes) -> None:
        self.data.extend(value)

    def flush(self) -> None:
        pass


def _set_store_root(root: Path) -> None:
    import memcommit.store as store_module

    paths = {
        "STORE_DIR": root,
        "CONTEXTS_DIR": root / "contexts",
        "QUERY_SOURCES_DIR": root / "query-sources",
        "STATE_FILE": root / "state.json",
        "IMPACT_PLAN_FILE": root / "impact-plan.json",
        "STAGED_UPDATE_FILE": root / "staged-update.json",
        "REVIEW_SESSION_FILE": root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": root / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": root / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": root / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": root / "ground-sessions",
        "MELD_SESSIONS_DIR": root / "meld-sessions",
    }
    for name, path in paths.items():
        setattr(store_module, name, path)


class _DelayedCompareProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        from memcommit.comparison_provider import COMPARISON_PAYLOAD_MARKER

        if operation != "compare_contexts":
            raise AssertionError(f"Unexpected provider operation: {operation}")
        payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
        reference_id = payload["frames"][0]["memories"][0]["memory_id"]
        compared_id = payload["frames"][1]["memories"][0]["memory_id"]
        # Keep the real wait shell visible long enough to capture its frozen
        # A/B/C contract before the deterministic provider returns.
        time.sleep(10)
        return json.dumps(
            {
                "overview": (
                    "Both advisors define proposal-writing guidance, but "
                    "their compensation and payment-method scopes differ."
                ),
                "reports": {
                    "both": "",
                    "differences": (
                        "Advisor 1 specifies a rate and travel time; Advisor 2 "
                        "specifies supported payment methods."
                    ),
                    "reference_only": "",
                    "compared_only": "",
                },
                "relations": [
                    {
                        "relation_key": "compensation",
                        "reference_memory_ids": [reference_id],
                        "compared_memory_ids": [compared_id],
                        "kind": "CONFLICT",
                        "status": "UNRESOLVED",
                        "summary": "Participant compensation scope differs.",
                        "reason": (
                            "The sources can be combined only after deciding "
                            "whether every supported term belongs in one result."
                        ),
                    }
                ],
                "issues": [
                    {
                        "issue_key": "compensation-policy",
                        "relation_keys": ["compensation"],
                        "priority": "REQUIRED",
                        "title": "Participant compensation policy",
                        "question": (
                            "Should the result retain the rate, travel time, "
                            "and every supported payment method?"
                        ),
                        "why_it_matters": (
                            "Choosing one advisor by order would discard "
                            "supported proposal guidance."
                        ),
                        "options": [
                            {
                                "label": "Keep all supported terms",
                                "text": (
                                    "Retain the hourly rate, travel-time "
                                    "condition, cash, e-transfer, and an "
                                    "equivalent-value gift card."
                                ),
                            },
                            {
                                "label": "Preserve scoped alternatives",
                                "text": (
                                    "Keep the rate and payment-method guidance "
                                    "as separately scoped proposal rules."
                                ),
                            },
                        ],
                    }
                ],
            }
        )


def _run_child(store_root: Path) -> None:
    _set_store_root(store_root)

    import memcommit.application.ops as ops
    from memcommit.cli import app
    from memcommit.commands import meld as meld_command
    from memcommit.comparison_store import load_comparison_analysis
    from memcommit.store import MemoryStore

    store = MemoryStore()
    left = ops.init(LEFT)
    ops.add(left, "Pay CAD 20–30 per hour, including travel time.")
    right = ops.init(RIGHT)
    ops.add(right, "Allow cash, e-transfer, or an equivalent-value gift card.")
    current = ops.init(CURRENT)
    ops.add(current, "Task 3 orientation remains active during Task 2 Meld.")
    for context in (left, right, current):
        store.save(context)
    store.set_current(current.name)

    meld_command.connect_codex_chatgpt_provider = lambda: _DelayedCompareProvider()
    argv = [
        "meld",
        LEFT,
        RIGHT,
        "--left-descendants",
        "--to",
        TARGET,
    ]
    print("$ mem " + " ".join(argv), flush=True)
    app(args=argv, prog_name="mem", standalone_mode=False)

    print("\nCAPTURE GATE · PRESS V FOR READ-ONLY VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Verification gate was not acknowledged.")

    print(f"\n$ mem compare --from {LEFT} --to {RIGHT} --snapshot", flush=True)
    app(
        args=[
            "compare",
            "--from",
            LEFT,
            "--to",
            RIGHT,
            "--reference-descendants",
            "--snapshot",
        ],
        prog_name="mem",
        standalone_mode=False,
    )
    print("\n$ mem status", flush=True)
    app(args=["status"], prog_name="mem", standalone_mode=False)
    print(f"\n$ mem show --context {TARGET}", flush=True)
    app(
        args=["show", "--context", TARGET],
        prog_name="mem",
        standalone_mode=False,
    )

    persisted_left = store.load_direct(LEFT)
    persisted_right = store.load_direct(RIGHT)
    analysis = load_comparison_analysis(
        persisted_left.uid,
        persisted_right.uid,
    )
    target = store.load_direct(TARGET)
    session = store.load_meld_session(target.uid)
    print("\nREAD-ONLY CONTRACT CHECK", flush=True)
    print(f"  PTY · {os.get_terminal_size().columns} columns × {os.get_terminal_size().lines} rows")
    print(f"  CURRENT · {store.current_context_name()} · UNCHANGED")
    print(
        "  ORDERED COMPARE BASIS · "
        + ("SAVED" if analysis is not None else "MISSING")
    )
    print(
        "  COMPARE SCOPE · "
        + (
            str(analysis.include_descendants)
            if analysis is not None
            else "UNAVAILABLE"
        )
    )
    print(f"  RESULT C · {target.name} · {len(tuple(target.iter_items()))} MEMORIES")
    print(
        "  MELD SESSION · "
        + (session.state if session is not None else "MISSING")
        + " · NOT APPLIED"
    )


_ANSI_16 = {
    "black": "#000000",
    "red": "#ed8796",
    "green": "#a6da95",
    "brown": "#eed49f",
    "blue": "#8aadf4",
    "magenta": "#c6a0f6",
    "cyan": "#8bd5ca",
    "white": "#cad3f5",
    "brightblack": "#5b6078",
    "brightred": "#ed8796",
    "brightgreen": "#a6da95",
    "brightbrown": "#eed49f",
    "brightblue": "#8aadf4",
    "brightmagenta": "#c6a0f6",
    "brightcyan": "#8bd5ca",
    "brightwhite": "#ffffff",
}


def _color(value: str, *, background: bool) -> str:
    if value == "default":
        return "#101217" if background else "#e6e9ef"
    if len(value) == 6 and all(char in "0123456789abcdef" for char in value):
        return "#" + value
    return _ANSI_16.get(value, "#101217" if background else "#e6e9ef")


def _render(raw: bytes, stem: str) -> None:
    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.Stream(screen)
    stream.feed(raw.decode("utf-8", errors="replace"))

    regular = ImageFont.truetype(FONT_PATH, 16)
    bold = ImageFont.truetype(FONT_PATH, 16, index=1)
    cell_width = 10
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
            char = screen.buffer[row][column]
            fg = _color(char.fg, background=False)
            bg = _color(char.bg, background=True)
            if char.reverse:
                fg, bg = bg, fg
            x = margin + column * cell_width
            y = margin + row * cell_height
            if bg != "#101217":
                draw.rectangle(
                    (x, y, x + cell_width - 1, y + cell_height - 1),
                    fill=bg,
                )
            if char.data != " ":
                # Menlo's bold face omits some box-drawing glyphs even though
                # its regular face has them; semantic focus color still makes
                # these borders distinct without replacement-character boxes.
                box_drawing = "\u2500" <= char.data <= "\u259f"
                draw.text(
                    (x, y),
                    char.data,
                    font=bold if char.bold and not box_drawing else regular,
                    fill=fg,
                )
    image.save(OUT / f"{stem}.png")
    (OUT / f"{stem}.typescript").write_bytes(raw)
    (OUT / f"{stem}.txt").write_text(
        "\n".join(line.rstrip() for line in screen.display).rstrip() + "\n",
        encoding="utf-8",
    )


def _settle(child: pexpect.spawn, seconds: float = 0.6) -> None:
    """Drain pending PTY paint bytes without waiting for a semantic marker."""

    try:
        child.expect(b"__MEMCOMMIT_UNREACHABLE_CAPTURE_MARKER__", timeout=seconds)
    except pexpect.TIMEOUT:
        pass


def _capture() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    store_root = Path(tempfile.mkdtemp(prefix="mem-meld-auto-basis-"))
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
    recorder = _Recorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", str(store_root)],
        cwd=str(ROOT),
        env=environment,
        dimensions=(ROWS, COLS),
        encoding=None,
        timeout=15,
    )
    child.logfile_read = recorder
    try:
        child.expect(b"MELD REPORT .* BUILDING")
        _settle(child)
        _render(bytes(recorder.data), "01-report-building")

        child.send(b"c")
        _settle(child)
        _render(bytes(recorder.data), "02-context-browser")

        child.send(b"i")
        child.expect(b"MELD CONFIRMED INPUTS .* READ-ONLY")
        _settle(child)
        _render(bytes(recorder.data), "03-frozen-a-b-c")

        child.send(b"r")
        _settle(child)
        _render(bytes(recorder.data), "04-report-restored")

        child.expect(b"CONTEXT LOCATIONS")
        child.expect(b"TO DO")
        _settle(child)
        _render(bytes(recorder.data), "05-seeded-review")

        child.send(b"\t")
        _settle(child, 0.2)
        child.send(b"\x1b[B")
        _settle(child, 0.2)
        child.send(b"\r")
        child.expect(b"MEMORY COLLISION")
        _settle(child)
        _render(bytes(recorder.data), "06-required-issue")

        child.send(b"\t")
        _settle(child, 0.2)
        child.send(b"\r")
        child.expect("✓ Keep all supported ".encode())
        _settle(child)
        _render(bytes(recorder.data), "07-staged-response")

        child.send(b"q")
        child.expect(b"CAPTURE GATE .* PRESS V")
        _settle(child)
        _render(bytes(recorder.data), "08-close-receipt")

        child.send(b"v\r")
        child.expect(b"READ-ONLY CONTRACT CHECK")
        child.expect(b"MELD SESSION .* NOT APPLIED")
        child.expect(pexpect.EOF)
        _render(bytes(recorder.data), "09-read-only-verification")
    finally:
        child.close(force=True)
        shutil.rmtree(store_root)

    raw = bytes(recorder.data)
    if b"38;2;" not in raw and b"48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", type=Path)
    arguments = parser.parse_args()
    if arguments.child is not None:
        _run_child(arguments.child)
    else:
        _capture()


if __name__ == "__main__":
    main()
