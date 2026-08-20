"""Capture concise command-attempt outcomes in an isolated real color PTY."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-operation-attempt-outcomes-20260820"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("attempt_outcome_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _write_isolated_mem_wrapper(directory: Path) -> Path:
    executable = directory / "mem"
    executable.write_text(
        f"""#!{sys.executable}
import os
from pathlib import Path

import memcommit.profile_config as profile_config

capture_store = Path(os.environ["MEMCOMMIT_CAPTURE_STORE"])
capture_profiles = Path(os.environ["MEMCOMMIT_CAPTURE_PROFILES"])
profile_config.default_store_dir = lambda: capture_store
profile_config.profile_control_dir = lambda: capture_profiles
profile_config.profile_stores_dir = lambda: capture_profiles / "stores"
profile_config.profile_registry_file = lambda: capture_profiles / "registry.json"
profile_config.profile_registry_lock_file = lambda: capture_profiles / "registry.lock"

import memcommit.store as store_module

store_module.STORE_DIR = capture_store

from memcommit.cli import app

app()
""",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


def _environment(
    *,
    wrapper_dir: Path,
    store_dir: Path,
    profile_dir: Path,
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.pop("MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT),
            "PATH": str(wrapper_dir) + os.pathsep + environment["PATH"],
            "MEMCOMMIT_CAPTURE_STORE": str(store_dir),
            "MEMCOMMIT_CAPTURE_PROFILES": str(profile_dir),
        }
    )
    return environment


def _run(environment: dict[str, str], *arguments: str) -> str:
    completed = subprocess.run(
        ("mem", *arguments),
        cwd=ROOT,
        env=environment,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Fixture command failed ({shlex.join(('mem', *arguments))}): "
            f"{completed.stderr}"
        )
    return completed.stdout


def _fixture(environment: dict[str, str]) -> tuple[str, str]:
    _run(environment, "init", "outcome-demo")
    cancellable = _run(
        environment,
        "add",
        "The first sentence is retained. The second sentence is retained.",
    )
    unchanged = _run(environment, "add", "One indivisible clause")

    def uid(output: str) -> str:
        match = re.search(r"\[([0-9a-f-]{8,36})\]", output)
        if match is None:
            raise RuntimeError(f"Could not recover fixture Memory UID: {output!r}")
        return match.group(1)

    return uid(cancellable), uid(unchanged)


def _context_bytes(store_dir: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(store_dir)): path.read_bytes()
        for path in sorted(store_dir.rglob("context.json"))
    }


def _shell_command(command: str, completion: str) -> str:
    return "\n".join(
        (
            "set +e",
            f"stty rows {ROWS} cols {COLUMNS}",
            "printf 'LIVE COLOR PTY · '",
            "stty size",
            f"printf '\n$ {command}\n'",
            command,
            "outcome_capture_code=$?",
            f"printf '\n{completion} · EXIT %s\n' \"$outcome_capture_code\"",
            "exit 0",
        )
    )


def _capture_complete(
    command: str,
    *,
    completion: str,
    stem: str,
    environment: dict[str, str],
) -> str:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", _shell_command(command, completion)],
        cwd=str(ROOT),
        env=environment,
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    try:
        child.expect(completion)
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    raw = recorder.getvalue()
    assert "52 180" in raw
    _BASE._snapshot(recorder, stem)
    return raw


def _capture_cancel(
    memory_uid: str,
    *,
    environment: dict[str, str],
) -> tuple[str, str]:
    command = shlex.join(("mem", "chunk", memory_uid))
    completion = "CHUNK CANCEL COMPLETE"
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", _shell_command(command, completion)],
        cwd=str(ROOT),
        env=environment,
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    try:
        child.expect_exact("Apply? [y/n]:")
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            try:
                child.read_nonblocking(65_536, timeout=0.05)
            except pexpect.TIMEOUT:
                pass
        _BASE._snapshot(recorder, "02-chunk-cancel-review")
        review_raw = recorder.getvalue()

        child.sendline("n")
        child.expect(completion)
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    _BASE._snapshot(recorder, "03-chunk-cancelled")
    return review_raw, recorder.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="mem-operation-attempt-outcomes-capture-"
    ) as temporary:
        temporary_root = Path(temporary)
        wrapper_dir = temporary_root / "bin"
        wrapper_dir.mkdir()
        _write_isolated_mem_wrapper(wrapper_dir)
        store_dir = temporary_root / "store"
        environment = _environment(
            wrapper_dir=wrapper_dir,
            store_dir=store_dir,
            profile_dir=temporary_root / "profiles",
        )
        cancellable_uid, unchanged_uid = _fixture(environment)
        before = _context_bytes(store_dir)

        no_change = _capture_complete(
            shlex.join(("mem", "chunk", unchanged_uid)),
            completion="CHUNK NO CHANGE COMPLETE",
            stem="01-chunk-no-change",
            environment=environment,
        )
        review, cancelled = _capture_cancel(
            cancellable_uid,
            environment=environment,
        )
        failed = _capture_complete(
            shlex.join(("mem", "chunk", "--method", "invalid-method")),
            completion="CHUNK FAILURE COMPLETE",
            stem="04-chunk-parser-failure",
            environment=environment,
        )
        operation_log = _capture_complete(
            shlex.join(("mem", "log", "--operations", "--limit", "20")),
            completion="OPERATION LOG COMPLETE",
            stem="05-operation-log-outcomes",
            environment=environment,
        )

        after = _context_bytes(store_dir)
        assert before == after
        assert "no changes made" in no_change
        assert "Apply?" in review
        assert "Aborted" in cancelled
        assert "Invalid value" in failed
        for label in ("NO CHANGE", "CANCELLED", "FAILED"):
            assert label in operation_log
        for hidden in ("COMPLETED", "APPLIED", "NOT DISPATCHED"):
            assert hidden not in operation_log
        color_evidence = no_change + review + cancelled + failed + operation_log
        assert re.search(
            r"\x1b\[(?:3[0-7]|9[0-7]|38;(?:2|5);)",
            color_evidence,
        ) is not None
        assert "\x1b[?1049h" not in operation_log


if __name__ == "__main__":
    main()
