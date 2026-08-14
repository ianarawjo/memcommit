"""Compatibility contracts for the two Study initialization spellings."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.commands.init as init_command
import memcommit.ops as ops
from memcommit.cli import app
from memcommit.eval.study_bundle import build_all_study_bundles
from memcommit.profile_config import load_profile_registry
from memcommit.profiles import STUDY_BASELINE_PROFILE_NAME
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


class _UnexpectedContextStore:
    def __init__(self, *args, **kwargs):
        raise AssertionError("Study routing must not construct a Context store")


def test_init_study_option_delegates_to_the_existing_study_command(
    monkeypatch,
):
    calls: list[tuple[str | None, str]] = []

    def run_study(*, name, baseline_profile):
        calls.append((name, baseline_profile))
        print("study route reached")

    monkeypatch.setattr(init_command, "MemoryStore", _UnexpectedContextStore)
    monkeypatch.setattr(init_command.init_study_command, "cmd", run_study)

    result = runner.invoke(app, ["init", "--study"])

    assert result.exit_code == 0, result.stderr or result.output
    assert result.output == "study route reached\n"
    assert calls == [(None, STUDY_BASELINE_PROFILE_NAME)]


def test_init_study_option_forwards_explicit_name_and_baseline(monkeypatch):
    calls: list[tuple[str | None, str]] = []

    def run_study(*, name, baseline_profile):
        calls.append((name, baseline_profile))

    monkeypatch.setattr(init_command, "MemoryStore", _UnexpectedContextStore)
    monkeypatch.setattr(init_command.init_study_command, "cmd", run_study)

    result = runner.invoke(
        app,
        [
            "init",
            "pilot-001",
            "--study",
            "--from-profile",
            "custom-baseline",
        ],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert calls == [("pilot-001", "custom-baseline")]


def test_init_study_option_rejects_context_parent_mode_before_any_route(
    monkeypatch,
):
    calls: list[object] = []

    monkeypatch.setattr(init_command, "MemoryStore", _UnexpectedContextStore)
    monkeypatch.setattr(
        init_command.init_study_command,
        "cmd",
        lambda **kwargs: calls.append(kwargs),
    )

    result = runner.invoke(app, ["init", "pilot-001", "--study", "--parents"])

    assert result.exit_code == 2
    assert "--study cannot be combined with --parents" in result.stderr
    assert calls == []


def test_init_rejects_study_baseline_without_study_before_context_setup(
    monkeypatch,
):
    monkeypatch.setattr(init_command, "MemoryStore", _UnexpectedContextStore)

    result = runner.invoke(
        app,
        ["init", "ordinary", "--from-profile", "custom-baseline"],
    )

    assert result.exit_code == 2
    assert "--from-profile requires --study" in result.stderr


def test_init_help_exposes_study_route_without_removing_init_study():
    init_help = runner.invoke(app, ["init", "--help"])
    root_help = runner.invoke(app, ["--help"])

    assert init_help.exit_code == 0, init_help.stderr or init_help.output
    assert "--study" in init_help.output
    assert "--from-profile" in init_help.output
    assert root_help.exit_code == 0, root_help.stderr or root_help.output
    assert "init-study" in root_help.output


def test_init_study_option_runs_the_real_study_initialization_path(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    authoring_store = MemoryStore()
    authoring_store.save(ops.init("authoring-notes"))
    authoring_store.set_current("authoring-notes")
    bundle_root = tmp_path / "bundles"
    build_all_study_bundles(bundle_root)
    imported = runner.invoke(
        app,
        ["profile", "import-study", "--from", str(bundle_root)],
    )
    assert imported.exit_code == 0, imported.stderr or imported.output

    result = runner.invoke(app, ["init", "option-route", "--study"])

    assert result.exit_code == 0, result.stderr or result.output
    assert "Initialized Study run 'option-route'." in result.output
    assert "Participant Profile: option-route" in result.output
    assert "Granted-memory Profile: option-route-granted-memory" in result.output
    registry = load_profile_registry()
    assert registry.active.name == "option-route"
    participant = registry.by_name("option-route")
    authority = registry.by_name("option-route-granted-memory")
    assert participant is not None and authority is not None
    assert participant.source is not None and authority.source is not None
    assert participant.source["kind"] == "STUDY_RUN"
    assert authority.source["kind"] == "STUDY_RUN_GRANTED_MEMORY"
    assert participant.source["study_uid"] == authority.source["study_uid"]
