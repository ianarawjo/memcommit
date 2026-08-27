"""Keep ordinary Context Init separate from Study initialization."""

from __future__ import annotations

from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app


runner = CliRunner(mix_stderr=False)


def test_init_help_is_context_only_while_init_study_remains_public():
    init_help = runner.invoke(app, ["init", "--help"])
    root_help = runner.invoke(app, ["--help"])

    assert init_help.exit_code == 0, init_help.stderr or init_help.output
    assert "new Context" in init_help.output
    assert "--study" not in init_help.output
    assert "--from-profile" not in init_help.output
    assert root_help.exit_code == 0, root_help.stderr or root_help.output
    assert "init-study" in root_help.output


def test_init_rejects_removed_study_options():
    study = runner.invoke(app, ["init", "--study"])
    baseline = runner.invoke(
        app,
        ["init", "ordinary", "--from-profile", "custom-baseline"],
    )

    assert study.exit_code == 2
    assert "No such option: --study" in study.stderr
    assert baseline.exit_code == 2
    assert "No such option: --from-profile" in baseline.stderr
