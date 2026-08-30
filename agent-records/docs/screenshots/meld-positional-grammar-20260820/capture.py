"""Capture the one-, two-, and three-operand Meld grammar in a real PTY."""

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

ONE_INCOMING = "grammar/one/incoming"
CURRENT_BASELINE = "grammar/one/current-baseline"
TWO_INCOMING = "grammar/two/incoming"
TWO_BASELINE = "grammar/two/baseline"
PEER_A = "grammar/three/peer-a"
PEER_B = "grammar/three/peer-b"
RESULT_C = "grammar/three/result-c"

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
    import memcommit.persistence.store as store_module

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
        "GROUND_SESSIONS_DIR": root / "ground-sessions",
        "MELD_SESSIONS_DIR": root / "meld-sessions",
    }
    for name, path in paths.items():
        setattr(store_module, name, path)


class _GrammarProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "compare_contexts":
            from memcommit.application.capabilities.memory_issue_analysis.peer_relations.provider_contract import COMPARISON_PAYLOAD_MARKER

            payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
            left_id = payload["frames"][0]["memories"][0]["memory_id"]
            right_id = payload["frames"][1]["memories"][0]["memory_id"]
            return json.dumps(
                {
                    "overview": (
                        "Both peers describe a review policy, but their "
                        "supported review windows differ."
                    ),
                    "reports": {
                        "both": "",
                        "differences": "The peers name different review windows.",
                        "reference_only": "",
                        "compared_only": "",
                    },
                    "relations": [
                        {
                            "relation_key": "review-window",
                            "reference_memory_ids": [left_id],
                            "compared_memory_ids": [right_id],
                            "kind": "CONFLICT",
                            "status": "UNRESOLVED",
                            "summary": "The supported review windows differ.",
                            "reason": (
                                "A symmetric Result must preserve or reconcile "
                                "both peer-supported windows."
                            ),
                        }
                    ],
                    "issues": [
                        {
                            "issue_key": "review-window",
                            "relation_keys": ["review-window"],
                            "priority": "REQUIRED",
                            "title": "Review window",
                            "question": "Which review windows should Result C retain?",
                            "why_it_matters": (
                                "Choosing one peer by order would invent authority."
                            ),
                            "options": [
                                {
                                    "label": "Retain both windows",
                                    "text": "Preserve both peer-supported windows.",
                                },
                                {
                                    "label": "Keep scoped alternatives",
                                    "text": "Keep each window with its source scope.",
                                },
                            ],
                        }
                    ],
                }
            )

        if operation != "meld_contexts":
            raise AssertionError(f"Unexpected provider operation: {operation}")
        from memcommit.application.operations.meld.provider import MELD_PAYLOAD_MARKER

        payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
        incoming_id = payload["frames"][0]["memories"][0]["memory_id"]
        baseline_id = payload["frames"][1]["memories"][0]["memory_id"]
        return json.dumps(
            {
                "overview": (
                    "Incoming evidence narrows the baseline review window; "
                    "the baseline remains authoritative until Apply."
                ),
                "relations": [
                    {
                        "relation_key": "review-window",
                        "left_memory_ids": [incoming_id],
                        "right_memory_ids": [baseline_id],
                        "kind": "CONFLICT",
                        "status": "UNRESOLVED",
                        "summary": "The incoming review window is narrower.",
                        "reason": "The incoming evidence supplies a correction.",
                    }
                ],
                "issues": [
                    {
                        "issue_key": "review-window",
                        "relation_keys": ["review-window"],
                        "priority": "REQUIRED",
                        "title": "Review window correction",
                        "question": "Should the incoming narrower window replace the baseline?",
                        "why_it_matters": (
                            "Directional authority permits a baseline change "
                            "only after explicit review."
                        ),
                        "options": [
                            {
                                "label": "Use the narrower window",
                                "text": "Apply the incoming correction.",
                            },
                            {
                                "label": "Keep the baseline window",
                                "text": "Retain the authoritative baseline.",
                            },
                        ],
                    }
                ],
                "results": [],
                "ready_to_apply": False,
            }
        )


def _invoke(app, argv: list[str]) -> None:
    print("$ mem " + " ".join(argv), flush=True)
    app(args=argv, prog_name="mem", standalone_mode=False)


def _pause(label: str) -> None:
    print(f"\nCAPTURE PAUSE · {label}", flush=True)
    time.sleep(3)


def _run_child(store_root: Path) -> None:
    _set_store_root(store_root)

    import memcommit.application.capabilities.ops as ops
    from memcommit.adapters.console.entrypoint import app
    from memcommit.adapters.console.commands import meld as meld_command
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    contexts = []
    for name, content in (
        (ONE_INCOMING, "Use the narrower reviewed window."),
        (CURRENT_BASELINE, "Use the broad default review window."),
        (TWO_INCOMING, "Use the revised approval window."),
        (TWO_BASELINE, "Use the original approval window."),
        (PEER_A, "Peer A supports a seven-day review window."),
        (PEER_B, "Peer B supports a fourteen-day review window."),
    ):
        context = ops.init(name)
        ops.add(context, content)
        contexts.append(context)
        store.save(context)
    store.set_current(CURRENT_BASELINE)
    meld_command.connect_codex_chatgpt_provider = lambda: _GrammarProvider()

    _invoke(app, ["meld", "--help"])
    _pause("HELP COMPLETE")

    _invoke(app, ["meld", ONE_INCOMING])
    _pause("ONE-OPERAND CLOSED")

    _invoke(app, ["meld", TWO_INCOMING, TWO_BASELINE])
    _pause("TWO-OPERAND CLOSED")

    _invoke(app, ["meld", PEER_A, PEER_B, RESULT_C])
    _pause("THREE-OPERAND CLOSED")

    print("\n$ mem status", flush=True)
    app(args=["status"], prog_name="mem", standalone_mode=False)
    print(f"\n$ mem show --context {RESULT_C}", flush=True)
    app(
        args=["show", "--context", RESULT_C],
        prog_name="mem",
        standalone_mode=False,
    )
    print("\nREAD-ONLY GRAMMAR CHECK", flush=True)
    print(
        f"  PTY · {os.get_terminal_size().columns} columns × "
        f"{os.get_terminal_size().lines} rows"
    )
    print(f"  CURRENT · {store.current_context_name()} · UNCHANGED")
    for target_name, expected_mode in (
        (CURRENT_BASELINE, "DIRECTIONAL"),
        (TWO_BASELINE, "DIRECTIONAL"),
        (RESULT_C, "SYMMETRIC"),
    ):
        target = store.load_direct(target_name)
        session = store.load_meld_session(target.uid)
        print(
            f"  {target_name} · {expected_mode} · "
            f"{session.state if session is not None else 'MISSING'} · "
            f"{len(tuple(target.iter_items()))} MEMORY"
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
    pyte.Stream(screen).feed(raw.decode("utf-8", errors="replace"))
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
    try:
        child.expect(b"__MEMCOMMIT_UNREACHABLE_CAPTURE_MARKER__", timeout=seconds)
    except pexpect.TIMEOUT:
        pass


def _capture() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    store_root = Path(tempfile.mkdtemp(prefix="mem-meld-positional-grammar-"))
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
        timeout=20,
    )
    child.logfile_read = recorder
    try:
        child.expect(b"CAPTURE PAUSE .* HELP COMPLETE")
        _settle(child)
        _render(bytes(recorder.data), "01-help-positional-forms")

        child.expect(b"MEM MELD .* DIRECTIONAL")
        child.expect(b"TO DO")
        _settle(child)
        _render(bytes(recorder.data), "02-one-operand-current-baseline")
        child.send(b"q")
        child.expect(b"CAPTURE PAUSE .* ONE-OPERAND CLOSED")
        _settle(child)
        _render(bytes(recorder.data), "03-one-operand-close-receipt")

        child.expect(b"MEM MELD .* DIRECTIONAL")
        child.expect(b"TO DO")
        _settle(child)
        _render(bytes(recorder.data), "04-two-operand-directional")
        child.send(b"q")
        child.expect(b"CAPTURE PAUSE .* TWO-OPERAND CLOSED")
        _settle(child)
        _render(bytes(recorder.data), "05-two-operand-close-receipt")

        child.expect(b"MEM MELD .* SYMMETRIC")
        child.expect(b"TO DO")
        _settle(child)
        _render(bytes(recorder.data), "06-three-operand-symmetric")
        child.send(b"q")
        child.expect(b"CAPTURE PAUSE .* THREE-OPERAND CLOSED")
        _settle(child)
        _render(bytes(recorder.data), "07-three-operand-close-receipt")

        child.expect(b"READ-ONLY GRAMMAR CHECK")
        child.expect(b"grammar/three/result-c .* SYMMETRIC")
        child.expect(pexpect.EOF)
        _render(bytes(recorder.data), "08-read-only-verification")
    finally:
        child.close(force=True)
        shutil.rmtree(store_root)

    raw = bytes(recorder.data)
    if b"38;2;" not in raw:
        raise RuntimeError("PTY stream did not contain true-color foreground ANSI.")
    if b"48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain true-color background ANSI.")


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
