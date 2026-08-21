"""Capture the split Study descriptions from one isolated real CLI run."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shlex
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/init-study-description-split-20260821"
COLUMNS = 180
ROWS = 52
PROFILE_NAME = "description-split-check"

_BASE_PATH = (
    ROOT / "docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "init_study_description_capture_base",
    _BASE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _configure_isolated_profile_root(root: Path) -> None:
    """Redirect the complete Profile/store boundary without changing HOME."""

    import memcommit.config as config_module
    import memcommit.profile_config as profile_config

    authoring = root / "authoring"
    control = root / "profile-control"
    profile_config.default_store_dir = lambda: authoring
    profile_config.profile_control_dir = lambda: control
    config_module.CONFIG_FILE = authoring / "config.json"


def _run_child(arguments: list[str]) -> None:
    capture_root = Path(os.environ["MEMCOMMIT_CAPTURE_ROOT"])
    _configure_isolated_profile_root(capture_root)
    columns, rows = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}")
    print("\x1b[38;2;138;173;244m$\x1b[0m mem " + shlex.join(arguments))

    from memcommit.cli import app

    sys.argv = ["mem", *arguments]
    app()


def _environment(capture_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT),
            "MEMCOMMIT_CAPTURE_ROOT": str(capture_root),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _capture(
    capture_root: Path,
    arguments: list[str],
    stem: str,
    required: tuple[str, ...],
) -> str:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", *arguments],
        cwd=str(ROOT),
        env=_environment(capture_root),
        encoding="utf-8",
        codec_errors="replace",
        timeout=90,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    try:
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)
    child.close()
    if child.exitstatus != 0:
        raise RuntimeError(
            f"Command failed for {stem}: exit={child.exitstatus}, "
            f"signal={child.signalstatus}\n{recorder.getvalue()}"
        )
    raw = recorder.getvalue()
    for text in required:
        if text not in raw:
            raise RuntimeError(f"{stem} did not render required text: {text}")
    if f"CAPTURE PTY · {COLUMNS}x{ROWS}" not in raw:
        raise RuntimeError("Capture child did not verify the 180x52 PTY.")
    if "\x1b[38;2;138;173;244m" not in raw:
        raise RuntimeError("Capture stream did not preserve true-color ANSI output.")
    _BASE._snapshot(recorder, stem)
    return raw


def _write_interaction_log(capture_root: Path) -> None:
    (OUT / "interaction.log").write_text(
        "\n".join(
            (
                f"capture_root={capture_root}",
                f"pty={COLUMNS}x{ROWS}",
                "TERM=xterm-256color",
                "COLORTERM=truecolor",
                "NO_COLOR=unset",
                "profile=description-split-check",
                "01 command=mem profile import-study mutation=creates isolated editable baseline",
                "02 command=mem init-study description-split-check mutation=creates and selects isolated Study run",
                "03 command=mem ls practice/description --direct mutation=none",
                "04 command=mem ls task-1/description --direct mutation=none",
                "05 command=mem ls task-2/description --direct mutation=none",
                "06 command=mem ls task-3/description --direct mutation=none",
                "final_current_context=practice",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.png", "*.txt", "*.typescript", "interaction.log"):
        for path in OUT.glob(pattern):
            path.unlink()

    capture_root = Path(
        tempfile.mkdtemp(prefix="memcommit-init-study-description-split-")
    )
    _capture(
        capture_root,
        ["profile", "import-study"],
        "01-baseline-imported",
        ("study-baseline",),
    )
    _capture(
        capture_root,
        ["init-study", PROFILE_NAME],
        "02-study-run-created",
        (PROFILE_NAME, "practice"),
    )
    practice = _capture(
        capture_root,
        ["ls", "practice/description", "--direct"],
        "03-practice-description",
        ("SITUATION ·", "TASK ·", "practice/source-atomized"),
    )
    task_1 = _capture(
        capture_root,
        ["ls", "task-1/description", "--direct"],
        "04-task-1-description",
        ("SITUATION ·", "TASK ·", "organizational wiki"),
    )
    task_2 = _capture(
        capture_root,
        ["ls", "task-2/description", "--direct"],
        "05-task-2-description",
        ("SITUATION ·", "TASK ·", "two co-advisors"),
    )
    task_3 = _capture(
        capture_root,
        ["ls", "task-3/description", "--direct"],
        "06-task-3-description",
        ("SITUATION ·", "TASK ·", "healthcare agent"),
    )

    for raw in (practice, task_1, task_2, task_3):
        if raw.count("SITUATION ·") != 1 or raw.count("TASK ·") != 1:
            raise RuntimeError("Description did not contain exactly two role rows.")
    _write_interaction_log(capture_root)
    print(capture_root)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--child":
        _run_child(sys.argv[2:])
    else:
        main()
