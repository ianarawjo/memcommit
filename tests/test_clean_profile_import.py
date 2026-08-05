"""Clean baseline import contracts for standalone Profiles and Studies."""

from datetime import datetime
import json
from pathlib import Path
import re

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.eval.study_bundle import build_all_study_bundles
from memcommit.profile_config import load_profile_registry, profile_store_dir


runner = CliRunner(mix_stderr=False)


def _baseline_source(root: Path) -> tuple[str, str]:
    context = ops.init("baseline")
    memory = ops.add(context, "Stable imported Memory.")
    directory = root / "contexts" / context.name
    directory.mkdir(parents=True)
    (directory / "context.json").write_text(
        json.dumps(context.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    checkpoints = directory / "checkpoints"
    checkpoints.mkdir()
    (checkpoints / "authoring.json").write_text("{}\n", encoding="utf-8")
    (root / "state.json").write_text(
        json.dumps({"current": context.name}) + "\n",
        encoding="utf-8",
    )
    (root / "query-sessions").mkdir()
    (root / "query-sessions" / "old.json").write_text("{}\n", encoding="utf-8")
    return context.uid, memory.uid


def test_mem_import_preserves_content_identity_but_not_history(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    source = tmp_path / "source"
    context_uid, memory_uid = _baseline_source(source)

    result = runner.invoke(app, ["import", "fresh", "--from", str(source)])

    assert result.exit_code == 0, result.stderr or result.output
    registry = load_profile_registry()
    assert registry.active.name == "authoring"
    profile = registry.by_name("fresh")
    assert profile is not None and profile.source is not None
    assert profile.source["kind"] == "BASELINE_IMPORT"
    assert datetime.fromisoformat(profile.source["imported_at"]).utcoffset() is not None
    assert re.fullmatch(r"[0-9a-f]{64}", profile.source["baseline_sha256"])
    imported = profile_store_dir(profile)
    record = json.loads(
        (imported / "contexts" / "baseline" / "context.json").read_text(
            encoding="utf-8"
        )
    )
    assert record["uid"] == context_uid
    assert memory_uid in record["memories"]
    assert not (imported / "contexts" / "baseline" / "checkpoints").exists()
    assert not (imported / "query-sessions").exists()


def test_init_study_imports_an_isolated_pair_with_empty_history(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    assert any(bundles.rglob("checkpoints/*.json"))
    imported = runner.invoke(
        app,
        ["profile", "import-study", "--from", str(bundles)],
    )
    assert imported.exit_code == 0, imported.stderr or imported.output

    result = runner.invoke(app, ["init-study", "clean-study"])

    assert result.exit_code == 0, result.stderr or result.output
    registry = load_profile_registry()
    profile = registry.by_name("clean-study")
    authority = registry.by_name("clean-study-granted-memory")
    assert profile is not None and authority is not None
    assert [item.name for item in registry.profiles] == [
        "authoring",
        "study-baseline",
        "clean-study",
        "clean-study-granted-memory",
    ]
    assert len(registry.grants) == 8
    assert not any(profile_store_dir(profile).rglob("checkpoints/*.json"))
    assert not any(profile_store_dir(authority).rglob("checkpoints/*.json"))
