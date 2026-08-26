"""Capture the UID-selector reservation in the ordinary Context Init TUI."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "agent-records/screenshots/study-cpr-input-20260810/capture_study_cpr.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_module("context_init_uid_capture_base", BASE_PATH)
BASE.OUT = OUT
_base_environment = BASE._environment


def _true_color_environment(home: Path) -> dict[str, str]:
    environment = _base_environment(home)
    environment["PROMPT_TOOLKIT_COLOR_DEPTH"] = "DEPTH_24_BIT"
    return environment


BASE._environment = _true_color_environment


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="memcommit-context-init-uid-"
    ) as temporary:
        home = Path(temporary) / "home"
        home.mkdir()
        child, recorder = BASE._spawn(home, "init")
        BASE._pump(child, recorder, seconds=0.8)
        assert "NEW CONTEXT NAME" in recorder.getvalue()
        BASE._snapshot(recorder, "01-name-entry")

        child.send("\x15deadbeef")
        BASE._pump(child, recorder, seconds=0.4)
        BASE._snapshot(recorder, "02-uid-shaped-name-entered")

        child.send("\r")
        BASE._pump(child, recorder, seconds=0.5)
        assert "Memory UUID or visible UID prefix" in recorder.getvalue()
        BASE._snapshot(recorder, "03-uid-shaped-name-rejected")

        child.send("\x15fit/deadbeef")
        BASE._pump(child, recorder, seconds=0.4)
        BASE._snapshot(recorder, "04-namespaced-name-entered")

        child.send("\r")
        BASE._pump(child, recorder, seconds=20, require_eof=True)
        assert "Initialized context 'fit/deadbeef'." in recorder.getvalue()
        BASE._snapshot(recorder, "05-init-success")

        BASE._capture_read_only(
            home,
            ("show", "--context", "fit/deadbeef"),
            stem="06-read-only-verification",
            expected=("Context: fit/deadbeef", "Memories 0"),
        )

    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain true-color ANSI styles.")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    main()
