"""Physical ownership contracts for canonical History verification."""

from pathlib import Path

import memcommit.application.capabilities.history.verification as verification
from memcommit.application.capabilities.history.verification.frame import (
    _Frame,
)
from memcommit.application.capabilities.history.verification.model import (
    MemoryState,
)
from memcommit.application.capabilities.history.verification.validators.branch import (
    _recorded_branch_transition,
)
from memcommit.application.capabilities.history.verification.validators.meld import (
    _meld_change_evidence,
)
from memcommit.application.capabilities.history.verification.validators.merge import (
    _recorded_merge_transition,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_ROOT = REPOSITORY_ROOT / "src/memcommit/application/capabilities/history/verification"


def test_retained_record_verification_has_focused_physical_owners() -> None:
    expected = {
        "__init__.py",
        "checkpoint.py",
        "frame.py",
        "model.py",
        "validators/__init__.py",
        "validators/add.py",
        "validators/atomize.py",
        "validators/branch.py",
        "validators/chunk.py",
        "validators/meld.py",
        "validators/merge.py",
    }

    assert not VERIFICATION_ROOT.with_suffix(".py").exists()
    assert {
        path.relative_to(VERIFICATION_ROOT).as_posix()
        for path in VERIFICATION_ROOT.rglob("*.py")
    } == expected


def test_history_verification_facade_preserves_narrow_owner_identity() -> None:
    assert verification.MemoryState is MemoryState
    assert verification._Frame is _Frame
    assert verification._recorded_branch_transition is _recorded_branch_transition
    assert verification._meld_change_evidence is _meld_change_evidence
    assert verification._recorded_merge_transition is _recorded_merge_transition
