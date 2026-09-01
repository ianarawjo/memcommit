"""MemoryStore adapter for current candidate Meld session reads."""

from __future__ import annotations

from memcommit.application.operations.meld.model import meld_canonical_digest
from memcommit.application.operations.meld.session import MeldSessionSnapshot
from memcommit.persistence.store import MemoryStore


def open_meld_candidate_session(
    target_context_uid: str,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    """Load one exact Target-scoped session without legacy turn machinery."""

    session = store.load_meld_session(target_context_uid)
    if session is None:
        raise FileNotFoundError(
            f"No saved Meld session for target {target_context_uid!r}."
        )
    return MeldSessionSnapshot(
        session=session,
        version_token=meld_canonical_digest(session.to_dict()),
    )


__all__ = ["open_meld_candidate_session"]
