"""Concise Profile-selection command contract."""

from __future__ import annotations

import shutil

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.profile_config import load_profile_registry, profile_registry_file
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _prepare_authoring() -> None:
    store = MemoryStore()
    store.save(ops.init("authoring-notes"))
    store.set_current("authoring-notes")


def test_profile_name_shorthand_uses_the_existing_selection_boundary(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring()

    def unexpected_picker(*args, **kwargs):
        raise AssertionError("profile NAME must not open the picker")

    monkeypatch.setattr(
        "memcommit.commands.profile.choose_profile",
        unexpected_picker,
    )

    shorthand = runner.invoke(app, ["profile", "authoring"])
    explicit = runner.invoke(app, ["profile", "use", "authoring"])

    assert shorthand.exit_code == explicit.exit_code == 0
    assert shorthand.output == explicit.output
    assert "Already using profile 'authoring'." in shorthand.output
    assert not profile_registry_file().exists()


def test_profile_name_shorthand_selects_a_managed_profile(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring()
    source = tmp_path / "managed-source"
    shutil.copytree(isolated_store, source)
    imported = runner.invoke(
        app,
        ["profile", "import", "managed", "--from", str(source)],
    )
    assert imported.exit_code == 0, imported.output

    selected = runner.invoke(app, ["profile", "managed"])

    assert selected.exit_code == 0, selected.output
    assert "Selected profile 'managed'." in selected.output
    assert load_profile_registry().active.name == "managed"


def test_profile_name_shorthand_reports_the_same_missing_profile_error(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring()

    shorthand = runner.invoke(app, ["profile", "missing-profile"])
    explicit = runner.invoke(
        app,
        ["profile", "use", "missing-profile"],
    )

    assert shorthand.exit_code == explicit.exit_code == 1
    assert shorthand.stderr == explicit.stderr
    assert "does not exist" in shorthand.stderr
    assert load_profile_registry().active.name == "authoring"


def test_profile_subcommands_keep_precedence_over_the_name_shorthand(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring()

    def unexpected_use(name):
        raise AssertionError(f"subcommand was routed through use: {name}")

    monkeypatch.setattr(
        "memcommit.commands.profile._use_profile",
        unexpected_use,
    )

    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0, result.output
    assert "* authoring" in result.output


def test_profile_use_without_a_name_keeps_the_interactive_picker(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring()
    monkeypatch.setattr(
        "memcommit.commands.profile._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.profile.choose_profile",
        lambda entries, *, current: "authoring",
    )

    result = runner.invoke(app, ["profile", "use"])

    assert result.exit_code == 0, result.output
    assert "Already using profile 'authoring'." in result.output
