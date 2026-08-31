"""Capture read-only Provider entry and explicit route actions in real PTYs."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
sys.path.insert(0, str(ROOT / "src"))

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("provider_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    dependency_paths = [
        value for value in sys.path if value and "site-packages" in value
    ]
    environment.update(
        {
            "HOME": str(home),
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": os.pathsep.join((str(ROOT / "src"), *dependency_paths)),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PROMPT_TOOLKIT_NO_CPR": "1",
        }
    )
    return environment


def _write_machine_config(home: Path) -> None:
    directory = home / ".mem"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(
        json.dumps(
            {
                "semantic_provider": "codex_chatgpt",
                "codex_chatgpt_model": "gpt-5.6-sol",
                "codex_chatgpt_reasoning_effort": "none",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_study_registry(home: Path) -> None:
    from memcommit.providers.policy import (
        STUDY_PROVIDER_POLICY_DIGEST,
        STUDY_PROVIDER_POLICY_VERSION,
    )
    from memcommit.application.operations.profile.config import (
        AUTHORING_PROFILE_NAME,
        AUTHORING_PROFILE_UID,
        ProfileEntry,
        ProfileRegistry,
    )

    participant = ProfileEntry(
        uid="10000000-0000-4000-8000-000000000001",
        name="provider-study",
        kind="MANAGED",
        source={
            "kind": "STUDY_RUN",
            "study_uid": "20000000-0000-4000-8000-000000000001",
            "study_name": "provider-study",
            "created_at": "2026-08-23T12:00:00+00:00",
            "baseline_sha256": "0" * 64,
            "baseline_profile_uid": "30000000-0000-4000-8000-000000000001",
            "baseline_profile_name": "study-baseline",
            "provider_policy_version": STUDY_PROVIDER_POLICY_VERSION,
            "provider_policy_digest": STUDY_PROVIDER_POLICY_DIGEST,
        },
    )
    registry = ProfileRegistry(
        generation=1,
        active_uid=participant.uid,
        profiles=(
            ProfileEntry(
                uid=AUTHORING_PROFILE_UID,
                name=AUTHORING_PROFILE_NAME,
                kind="AUTHORING",
            ),
            participant,
        ),
    )
    directory = home / ".mem-profiles"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "registry.json").write_text(
        json.dumps(registry.to_dict(), indent=2),
        encoding="utf-8",
    )


def _run_mem_child(arguments: list[str]) -> None:
    size = os.get_terminal_size()
    print(f"PTY {size.columns} {size.lines}", flush=True)
    os.execvpe("mem", ["mem", *arguments], os.environ)


def _run_study_verification_child(home: Path) -> None:
    size = os.get_terminal_size()
    print(f"PTY {size.columns} {size.lines}", flush=True)
    completed = subprocess.run(
        ["mem", "provider", "status"],
        check=False,
        text=True,
        env=os.environ,
    )
    route_directory = home / ".mem-profiles" / "provider-routes"
    route_count = (
        len(tuple(route_directory.glob("*.json"))) if route_directory.exists() else 0
    )
    print(f"PROFILE ROUTE SIDECARS · {route_count}", flush=True)
    raise SystemExit(completed.returncode)


def _spawn_mem(home: Path, *arguments: str):
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child-mem", *arguments],
        cwd=str(ROOT),
        env=_environment(home),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _spawn_study_verification(home: Path):
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--verify-study", str(home)],
        cwd=str(ROOT),
        env=_environment(home),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _capture_general(home: Path) -> None:
    child, recorder = _spawn_mem(home, "provider")
    try:
        child.expect("PROFILE PROVIDER ROUTES")
        child.expect("mode: general · editable")
        child.expect("contact_status: not_contacted")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "01-general-read-only-overview")
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn_mem(
        home,
        "provider",
        "use",
        "ollama",
        "--model",
        "qwen3.6:35b-a3b",
        "--thinking",
        "auto",
    )
    try:
        child.expect("Profile provider route: authoring · default")
        child.expect("Verify with 'mem provider probe'.")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "02-general-explicit-use-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn_mem(home, "provider")
    try:
        child.expect("PROFILE PROVIDER ROUTES")
        child.expect("ollama · model qwen3.6:35b-a3b")
        child.expect("source: profile_default")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "03-general-updated-overview")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_study(home: Path) -> None:
    child, recorder = _spawn_mem(home, "provider")
    try:
        child.expect("PROFILE PROVIDER ROUTES")
        child.expect("profile: provider-study")
        child.expect("mode: study · locked")
        child.expect("study_config: study-provider-config-v1")
        child.expect("configure: unavailable in a Study Profile")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "04-study-read-only-overview")
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn_mem(
        home,
        "provider",
        "use",
        "ollama",
        "--model",
        "qwen:latest",
    )
    try:
        child.expect("Provider configuration is fixed for this Study Profile")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "05-study-edit-rejected")
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn_study_verification(home)
    try:
        child.expect("profile_mode: study")
        child.expect("provider: codex_chatgpt")
        child.expect("PROFILE ROUTE SIDECARS · 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "06-study-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory(
            prefix="memcommit-provider-general-capture-"
        ) as general_directory,
        tempfile.TemporaryDirectory(
            prefix="memcommit-provider-study-capture-"
        ) as study_directory,
    ):
        general_home = Path(general_directory)
        study_home = Path(study_directory)
        _write_machine_config(general_home)
        _write_machine_config(study_home)
        _write_study_registry(study_home)
        _capture_general(general_home)
        _capture_study(study_home)

    stems = (
        "01-general-read-only-overview",
        "02-general-explicit-use-receipt",
        "03-general-updated-overview",
        "04-study-read-only-overview",
        "05-study-edit-rejected",
        "06-study-read-only-verification",
    )
    captures = tuple(OUT / f"{stem}.typescript" for stem in stems)
    raw = "".join(path.read_text(encoding="utf-8") for path in captures)
    assert all(
        "PTY 180 52" in path.read_text(encoding="utf-8") for path in captures
    )
    assert "\x1b[31m" in raw or "\x1b[38;" in raw
    assert "doesn't support cursor position requests" not in raw

    for stem in ("01-general-read-only-overview", "03-general-updated-overview"):
        bare = (OUT / f"{stem}.typescript").read_text(encoding="utf-8")
        assert "\x1b[?1049h" not in bare
        assert "PRESS ENTER" not in bare
    study_bare = (OUT / "04-study-read-only-overview.typescript").read_text(
        encoding="utf-8"
    )
    assert "\x1b[?1049h" not in study_bare
    assert "PRESS ENTER" not in study_bare
    assert "probe pinned default" not in study_bare.lower()

    initial = (OUT / "01-general-read-only-overview.txt").read_text(
        encoding="utf-8"
    )
    assert "GENERAL · EDITABLE" in initial.upper()
    receipt = (OUT / "02-general-explicit-use-receipt.txt").read_text(
        encoding="utf-8"
    )
    assert "Profile provider route: authoring · default" in receipt
    updated = (OUT / "03-general-updated-overview.txt").read_text(encoding="utf-8")
    assert "source: profile_default" in updated
    locked = (OUT / "04-study-read-only-overview.txt").read_text(encoding="utf-8")
    assert "mode: study · locked" in locked
    rejected = (OUT / "05-study-edit-rejected.txt").read_text(encoding="utf-8")
    assert "fixed for this Study Profile" in rejected
    verified = (OUT / "06-study-read-only-verification.txt").read_text(
        encoding="utf-8"
    )
    assert "PROFILE ROUTE SIDECARS · 0" in verified


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--child-mem":
        _run_mem_child(sys.argv[2:])
    elif len(sys.argv) == 3 and sys.argv[1] == "--verify-study":
        _run_study_verification_child(Path(sys.argv[2]))
    else:
        main()
