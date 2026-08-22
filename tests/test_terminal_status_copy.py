"""Cross-operation guardrails for task-oriented terminal status copy."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "memcommit"


def _production_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
    )


def test_retired_implementation_status_phrases_do_not_return() -> None:
    source = _production_source()

    for phrase in (
        "layout only; no authority",
        "READ-ONLY ACTION · APPLIED",
        "MEM GROUND · WORKING · NOT SAVED",
        "NAME-ONLY CHECK · NOT BOUND",
        "STATUS · READ-ONLY · COMPLETE · NO CONTEXT CHANGES",
        "FROZEN INPUTS · RESULT PENDING",
        "SETUP · NOT RUN",
        "TO DO · SETUP ONLY",
    ):
        assert phrase not in source


def test_real_creation_and_permission_boundaries_remain_explicit() -> None:
    ground_source = (
        PACKAGE_ROOT / "commands" / "ground_shell.py"
    ).read_text(encoding="utf-8")
    source_projection = (
        PACKAGE_ROOT / "source_projection" / "presentation.py"
    ).read_text(encoding="utf-8")

    assert "NOT CREATED" in ground_source
    assert 'SourceState.READ_ONLY: "READ ONLY"' in source_projection
