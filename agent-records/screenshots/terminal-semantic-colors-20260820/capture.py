"""Capture the shared History semantic-action colors in a real color PTY."""

from __future__ import annotations

import importlib.util
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]
BASE_PATH = ROOT / "agent-records/screenshots/revert-history-policy-20260813/capture.py"


def _load_revert_capture():
    spec = importlib.util.spec_from_file_location(
        "terminal_semantic_color_revert_capture",
        BASE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the production Revert capture harness.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    return module


def main() -> None:
    capture = _load_revert_capture()
    capture.main()

    recovery = (OUT / "04-recovery-checkpoints.typescript").read_text(
        encoding="utf-8"
    )
    preview = (OUT / "05-target-impact-preview.typescript").read_text(
        encoding="utf-8"
    )
    combined = recovery + preview

    assert "52 180" in combined
    assert "\x1b[?1049h" in combined
    assert "38;2;138;173;244" in combined  # CREATE/ADD action blue.
    assert "38;2;237;135;150" in preview  # Removal impact red.
    assert "\x1b[0;1;7m" in combined  # Focus overrides the action foreground.


if __name__ == "__main__":
    main()
