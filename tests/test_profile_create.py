"""Empty managed Profile creation contracts for CLI and picker routes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest

import memcommit.application.operations.profile.model as profiles_module
from memcommit.commands.profile.picker import (
    ProfilePickerAction,
    ProfilePickerEntry,
    _creation_review,
    choose_profile,
)
from memcommit.application.operations.profile.config import (
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
    profile_stores_dir,
)
from memcommit.application.operations.profile.model import ProfileError, create_profile
from memcommit.persistence.store import MemoryStore


ROOT = Path(__file__).resolve().parents[1]


def _mem(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "memcommit.adapters.console.entrypoint", *args],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_profile_create_cli_supports_empty_select_then_first_context(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    initialized = _mem(tmp_path, "init", "authoring-notes")
    assert initialized.returncode == 0, initialized.stderr

    created = _mem(tmp_path, "profile", "create", "fresh-work")

    assert created.returncode == 0, created.stderr
    assert "Created empty Profile 'fresh-work'." in created.stdout
    assert "Active Profile unchanged: authoring" in created.stdout
    assert "mem profile use fresh-work" in created.stdout
    assert "mem init CONTEXT" in created.stdout
    registry = load_profile_registry()
    fresh = registry.by_name("fresh-work")
    assert fresh is not None
    assert fresh.kind == "MANAGED"
    assert fresh.source is not None
    assert fresh.source["kind"] == "EMPTY_PROFILE"
    assert registry.active.name == "authoring"
    root = profile_store_dir(fresh)
    assert sorted(path.relative_to(root).as_posix() for path in root.rglob("*")) == [
        "contexts",
        "state.json",
    ]
    assert json.loads((root / "state.json").read_text()) == {"current": None}

    selected = _mem(tmp_path, "profile", "use", "fresh-work")
    empty_current = _mem(tmp_path, "profile", "current")
    first_context = _mem(tmp_path, "init", "inbox")
    final_current = _mem(tmp_path, "profile", "current")

    assert selected.returncode == 0, selected.stderr
    assert "Selected profile 'fresh-work'." in selected.stdout
    assert empty_current.returncode == 0, empty_current.stderr
    assert "Current Context: (none)" in empty_current.stdout
    assert first_context.returncode == 0, first_context.stderr
    assert "Initialized context 'inbox'." in first_context.stdout
    assert final_current.returncode == 0, final_current.stderr
    assert "Profile: fresh-work" in final_current.stdout
    assert "Current Context: inbox" in final_current.stdout


def test_create_profile_rejects_casefold_collision_and_stale_picker_generation(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    MemoryStore()
    first = create_profile("Fresh")
    generation = load_profile_registry().generation

    with pytest.raises(ProfileError, match="already exists"):
        create_profile("fresh")
    with pytest.raises(ProfileError, match="changed after create review"):
        create_profile("later", expected_generation=generation - 1)

    registry = load_profile_registry()
    assert [profile.name for profile in registry.visible_profiles] == [
        "authoring",
        "Fresh",
    ]
    assert registry.active.name == "authoring"
    assert profile_store_dir(first.profile).is_dir()


def test_create_profile_rolls_back_store_when_registry_publish_fails(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    MemoryStore()

    def fail_registry_write(_registry) -> None:
        raise OSError("registry unavailable")

    monkeypatch.setattr(profiles_module, "_write_registry", fail_registry_write)

    with pytest.raises(OSError, match="registry unavailable"):
        create_profile("rolled-back")

    assert not profile_registry_file().exists()
    assert list(profile_stores_dir().iterdir()) == []


def test_profile_picker_n_reviews_one_exact_empty_profile_creation():
    entries = (
        ProfilePickerEntry(
            name="authoring",
            uid="authoring-uid",
            context_count=1,
            current_context="notes",
        ),
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("nnew-profile\ra")
        selected = choose_profile(
            entries,
            current="authoring",
            registry_generation=8,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == ProfilePickerAction(
        kind="CREATE_PROFILE",
        name="new-profile",
        uid=None,
        registry_generation=8,
        row_index=1,
    )
    review = _creation_review(selected)
    assert review.argv == ("mem", "profile", "create", "new-profile")
    assert "Keep the current Profile selected." in review.effects


def test_profile_help_lists_empty_create_command(tmp_path):
    result = _mem(tmp_path, "profile", "--help")

    assert result.returncode == 0, result.stderr
    assert "create" in result.stdout
    assert "Create one empty managed Profile without selecting it." in result.stdout
