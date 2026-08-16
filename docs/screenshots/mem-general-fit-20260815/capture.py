"""Capture the general proposition Fit command and read-only Viewer."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
ROWS = 52
COLUMNS = 180

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_base():
    spec = importlib.util.spec_from_file_location("general_fit_capture_base", BASE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    return module


BASE = _load_base()


class _DelayedMayProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "fit_propositions"
        assert output_schema is not None
        time.sleep(1.2)
        marker = "FIT PROPOSITION PAYLOAD:\n"
        payload = json.loads(prompt.split(marker, 1)[1])
        question = payload["questions"][0]
        aliases = [
            item["proposition_id"]
            for item in (*question["background"], *question["propositions"])
        ]
        return json.dumps(
            {
                "overview": "The entrance referent changes the outcome.",
                "judgments": [
                    {
                        "question_id": "fit",
                        "verdict": "MAY",
                        "reason": (
                            "The statements coexist if the second proposition "
                            "means the staff entrance, but conflict if it means "
                            "the main entrance."
                        ),
                        "considered_proposition_ids": aliases,
                        "material_proposition_ids": aliases,
                        "consistent_reading": (
                            "Staff use the separate staff entrance after 6 p.m."
                        ),
                        "inconsistent_reading": (
                            "Staff use the closed main entrance after 6 p.m."
                        ),
                    }
                ],
            }
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
        }
    )
    return environment


def _child() -> None:
    import memcommit.commands.fit as fit_command

    copied: list[str] = []
    fit_command.connect_semantic_provider = _DelayedMayProvider
    fit_command.write_system_clipboard = copied.append
    print(
        '$ mem fit "The main entrance is closed after 5 p.m." '
        '"Staff may use the entrance after 6 p.m." '
        '--background "The building has separate main and staff entrances."',
        flush=True,
    )
    fit_command.cmd(
        [
            "The main entrance is closed after 5 p.m.",
            "Staff may use the entrance after 6 p.m.",
        ],
        background=["The building has separate main and staff entrances."],
        ground_name=None,
        receipt=None,
        plain=False,
        tui=True,
    )
    print("GENERAL FIT CLOSED · READ-ONLY VERIFICATION")
    print("  VERDICT · MAY")
    print(f"  CLIPBOARD PROJECTIONS · {len(copied)}")
    print("  DURABLE WRITES · 0", flush=True)


def _capture() -> None:
    recorder = BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    try:
        child.expect("mem fit")
        BASE._settle(child, seconds=0.25)
        BASE._snapshot(recorder, "01-provider-running")
        BASE._settle(child, seconds=1.5)
        BASE._snapshot(recorder, "02-judgment-entry")
        child.send("\x1b[B")
        BASE._settle(child, seconds=0.2)
        BASE._snapshot(recorder, "03-complete-input-focused")
        child.send("\x1b[B")
        BASE._settle(child, seconds=0.2)
        BASE._snapshot(recorder, "04-readings-focused")
        child.send("y")
        BASE._settle(child, seconds=0.2)
        BASE._snapshot(recorder, "05-focused-copy")
        child.send("Y")
        BASE._settle(child, seconds=0.2)
        BASE._snapshot(recorder, "06-complete-copy")
        child.send("q")
        child.expect("GENERAL FIT CLOSED")
        child.expect(pexpect.EOF)
        BASE._snapshot(recorder, "07-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


if __name__ == "__main__":
    if "--child" in sys.argv:
        _child()
    else:
        _capture()
