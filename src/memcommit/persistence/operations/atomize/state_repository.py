"""Persist Atomize analyses, workbenches, and retained session history."""

from __future__ import annotations
import json
import uuid
from pathlib import Path


from ...store.infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_json_atomic,
)
from ...store.infrastructure.protection import _profile_write_guarded


class _AtomizeStateStoreMixin:
    """Own Atomize-specific persisted working state."""

    def _atomize_analysis_path(self, context_uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid atomize analysis Context uid.") from error
        if canonical != context_uid:
            raise ValueError("Invalid atomize analysis Context uid.")
        if self.atomize_analyses_dir.is_symlink():
            raise ValueError("Atomize analysis storage cannot be a symbolic link.")
        if (
            self.atomize_analyses_dir.exists()
            and not self.atomize_analyses_dir.is_dir()
        ):
            raise ValueError("Atomize analysis storage is invalid.")
        return self.atomize_analyses_dir / f"{canonical}.json"

    def load_atomize_analysis(self, context_uid: str):
        """Return one Context's latest saved atomize preview, or None."""
        from memcommit.application.operations.atomize.domain import (
            AtomizeAnalysisSession,
            AtomizeImpactError,
        )

        path = self._atomize_analysis_path(context_uid)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Atomize analysis storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = AtomizeAnalysisSession.from_dict(data)
            if session.context_uid != context_uid:
                raise ValueError(
                    "Saved atomize analysis Context identity does not match "
                    "its storage key."
                )
            return session
        except (
            json.JSONDecodeError,
            ValueError,
            AtomizeImpactError,
        ) as error:
            raise ValueError("Saved atomize analysis is invalid.") from error

    @_profile_write_guarded
    def save_atomize_analysis(self, session) -> None:
        """Atomically persist a validated, non-applying atomize preview."""

        from memcommit.application.operations.atomize.domain import (
            AtomizeAnalysisSession,
        )

        if not isinstance(session, AtomizeAnalysisSession):
            raise TypeError("Expected an AtomizeAnalysisSession.")

        with self._atomize_session_write_lock(session.context_uid):
            self._save_atomize_analysis_locked(session)

    def _save_atomize_analysis_locked(self, session) -> None:
        """Persist one analysis while its Context-scoped CAS lock is held."""

        from memcommit.application.operations.atomize.domain import (
            AtomizeAnalysisSession,
            AtomizeImpactError,
        )

        self._assert_profile_write_allowed()
        if not isinstance(session, AtomizeAnalysisSession):
            raise TypeError("Expected an AtomizeAnalysisSession.")
        path = self._atomize_analysis_path(session.context_uid)
        if self.atomize_analyses_dir.exists() and (
            not self.atomize_analyses_dir.is_dir()
            or self.atomize_analyses_dir.is_symlink()
        ):
            raise ValueError("Atomize analysis storage is invalid.")
        self.atomize_analyses_dir.mkdir(parents=True, exist_ok=True)
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Atomize analysis storage is invalid.")
        data = session.to_dict()
        try:
            AtomizeAnalysisSession.from_dict(data)
        except AtomizeImpactError as error:
            raise ValueError("Atomize analysis is invalid.") from error
        _write_json_atomic(path, data)

    @_profile_write_guarded
    def delete_atomize_analysis(self, context_uid: str) -> None:
        """Remove one derived analysis artifact during failed save-as cleanup."""
        with self._atomize_session_write_lock(context_uid):
            path = self._atomize_analysis_path(context_uid)
            if path.exists():
                if not path.is_file() or path.is_symlink():
                    raise ValueError("Atomize analysis storage is invalid.")
                path.unlink()

    def _atomize_workbench_path(self, context_uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid atomize workbench Context uid.") from error
        if canonical != context_uid:
            raise ValueError("Invalid atomize workbench Context uid.")
        if self.atomize_workbenches_dir.is_symlink():
            raise ValueError("Atomize workbench storage cannot be a symbolic link.")
        if (
            self.atomize_workbenches_dir.exists()
            and not self.atomize_workbenches_dir.is_dir()
        ):
            raise ValueError("Atomize workbench storage is invalid.")
        return self.atomize_workbenches_dir / f"{canonical}.json"

    def load_atomize_workbench(self, analysis):
        """Load mutable state only against one exact saved analysis."""
        from memcommit.application.operations.atomize.domain import (
            AtomizeAnalysisSession,
        )
        from memcommit.application.operations.atomize.records import (
            AtomizeRecordError,
            AtomizeReviewRecord,
            atomize_review_issue_projection,
        )

        if not isinstance(analysis, AtomizeAnalysisSession):
            raise TypeError("Expected an AtomizeAnalysisSession.")
        active_analysis = self.load_atomize_analysis(analysis.context_uid)
        if active_analysis is None or active_analysis.uid != analysis.uid:
            try:
                _archived_analysis, workbench, _path = (
                    self.load_atomize_session_history(
                        analysis.context_uid,
                        analysis.uid,
                    )
                )
            except FileNotFoundError:
                return None
            return workbench
        path = self._atomize_workbench_path(analysis.context_uid)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Atomize workbench storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = AtomizeReviewRecord.from_dict(
                data,
                issues=atomize_review_issue_projection(analysis),
            )
            if (
                session.analysis_uid != analysis.uid
                or session.context_uid != analysis.context_uid
            ):
                raise ValueError(
                    "Saved atomize workbench identity does not match its "
                    "analysis or storage key."
                )
            return session
        except (
            json.JSONDecodeError,
            AtomizeRecordError,
            ValueError,
        ) as error:
            raise ValueError("Saved atomize workbench is invalid.") from error

    @_profile_write_guarded
    def save_atomize_workbench(self, session) -> None:
        """Atomically persist one Context-bound mutable workbench."""
        from memcommit.application.operations.atomize.records import (
            AtomizeReviewRecord,
        )

        if not isinstance(session, AtomizeReviewRecord):
            raise TypeError("Expected an AtomizeReviewRecord.")
        with self._atomize_session_write_lock(session.context_uid):
            self._save_atomize_workbench_locked(session)

    def _save_atomize_workbench_locked(self, session) -> None:
        """Persist one workbench while its Context-scoped CAS lock is held."""
        from memcommit.application.operations.atomize.records import (
            AtomizeRecordError,
            AtomizeReviewRecord,
            atomize_review_issue_projection,
        )

        self._assert_profile_write_allowed()
        if not isinstance(session, AtomizeReviewRecord):
            raise TypeError("Expected an AtomizeReviewRecord.")
        path = self._atomize_workbench_path(session.context_uid)
        if self.atomize_workbenches_dir.exists() and (
            not self.atomize_workbenches_dir.is_dir()
            or self.atomize_workbenches_dir.is_symlink()
        ):
            raise ValueError("Atomize workbench storage is invalid.")
        self.atomize_workbenches_dir.mkdir(parents=True, exist_ok=True)
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Atomize workbench storage is invalid.")
        data = session.to_dict()
        try:
            AtomizeReviewRecord.from_dict(
                data,
                issues=session.issues,
            )
        except AtomizeRecordError as error:
            raise ValueError("Atomize workbench is invalid.") from error
        analysis = self.load_atomize_analysis(session.context_uid)
        if analysis is None or not session.matches_analysis(
            analysis_uid=analysis.uid,
            context_uid=analysis.context_uid,
            context_name=analysis.context_name,
            context_digest=analysis.context_digest,
            issues=atomize_review_issue_projection(analysis),
        ):
            raise ValueError("Atomize workbench does not match the saved analysis.")
        _write_json_atomic(path, data)

    @_profile_write_guarded
    def delete_atomize_workbench(self, context_uid: str) -> None:
        """Remove derived UI state during failed save-as cleanup."""
        with self._atomize_session_write_lock(context_uid):
            path = self._atomize_workbench_path(context_uid)
            if path.exists():
                if not path.is_file() or path.is_symlink():
                    raise ValueError("Atomize workbench storage is invalid.")
                path.unlink()

    def _atomize_session_history_path(
        self,
        context_uid: str,
        analysis_uid: str,
    ) -> Path:
        try:
            canonical_context = str(uuid.UUID(context_uid))
            canonical_analysis = str(uuid.UUID(analysis_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid Atomize session history identity.") from error
        if canonical_context != context_uid or canonical_analysis != analysis_uid:
            raise ValueError("Invalid Atomize session history identity.")
        return (
            self.atomize_session_history_dir
            / canonical_context
            / f"{canonical_analysis}.json"
        )

    @_profile_write_guarded
    def archive_atomize_session(self, analysis, workbench) -> bool:
        """Retain one displaced analysis/workbench pair under its analysis UID."""

        from memcommit.application.operations.atomize.domain import (
            AtomizeAnalysisSession,
            AtomizeImpactError,
        )
        from memcommit.application.operations.atomize.records import (
            AtomizeRecordError,
            AtomizeReviewRecord,
            atomize_review_issue_projection,
        )

        if not isinstance(analysis, AtomizeAnalysisSession):
            raise TypeError("Expected an AtomizeAnalysisSession.")
        if workbench is not None and not isinstance(
            workbench,
            AtomizeReviewRecord,
        ):
            raise TypeError("Expected an AtomizeReviewRecord.")
        analysis_data = analysis.to_dict()
        try:
            AtomizeAnalysisSession.from_dict(analysis_data)
            if workbench is not None:
                restored_workbench = AtomizeReviewRecord.from_dict(
                    workbench.to_dict(),
                    issues=atomize_review_issue_projection(analysis),
                )
                if not restored_workbench.matches_analysis(
                    analysis_uid=analysis.uid,
                    context_uid=analysis.context_uid,
                    context_name=analysis.context_name,
                    context_digest=analysis.context_digest,
                    issues=atomize_review_issue_projection(analysis),
                ):
                    raise ValueError(
                        "Atomize workbench does not match its retained analysis."
                    )
        except (AtomizeImpactError, AtomizeRecordError) as error:
            raise ValueError("Atomize session history is invalid.") from error
        path = self._atomize_session_history_path(
            analysis.context_uid,
            analysis.uid,
        )
        if self.atomize_session_history_dir.exists() and (
            not self.atomize_session_history_dir.is_dir()
            or self.atomize_session_history_dir.is_symlink()
        ):
            raise ValueError("Atomize session history is invalid.")
        if path.parent.exists() and (
            not path.parent.is_dir() or path.parent.is_symlink()
        ):
            raise ValueError("Atomize session history is invalid.")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": 1,
            "analysis": analysis_data,
            "workbench": workbench.to_dict() if workbench is not None else None,
        }
        if path.exists() or path.is_symlink():
            if not path.is_file() or path.is_symlink():
                raise ValueError("Atomize session history is invalid.")
            with open(path, encoding="utf-8") as handle:
                retained = json.load(
                    handle,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            if retained != data:
                raise ValueError("Atomize session history is immutable.")
            return False
        _write_json_atomic(path, data)
        return True

    @_profile_write_guarded
    def delete_atomize_session_history(
        self,
        context_uid: str,
        analysis_uid: str,
    ) -> None:
        """Remove an archive created by a failed latest-pair publication."""

        path = self._atomize_session_history_path(context_uid, analysis_uid)
        if not path.exists():
            return
        if not path.is_file() or path.is_symlink():
            raise ValueError("Atomize session history is invalid.")
        path.unlink()
        try:
            path.parent.rmdir()
        except OSError:
            pass
        try:
            self.atomize_session_history_dir.rmdir()
        except OSError:
            pass

    def load_atomize_session_history(
        self,
        context_uid: str,
        analysis_uid: str,
    ):
        """Load one immutable displaced Atomize pair and its exact path."""

        from memcommit.application.operations.atomize.domain import (
            AtomizeAnalysisSession,
            AtomizeImpactError,
        )
        from memcommit.application.operations.atomize.records import (
            AtomizeRecordError,
            AtomizeReviewRecord,
            atomize_review_issue_projection,
        )

        path = self._atomize_session_history_path(context_uid, analysis_uid)
        if not path.exists():
            raise FileNotFoundError(
                f"Atomize analysis '{analysis_uid}' is unavailable."
            )
        if not path.is_file() or path.is_symlink():
            raise ValueError("Atomize session history is invalid.")
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(
                    handle,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            if not isinstance(data, dict) or set(data) != {
                "schema_version",
                "analysis",
                "workbench",
            }:
                raise ValueError("Atomize session history is invalid.")
            if data["schema_version"] != 1:
                raise ValueError("Atomize session history is invalid.")
            analysis = AtomizeAnalysisSession.from_dict(data["analysis"])
            if analysis.context_uid != context_uid or analysis.uid != analysis_uid:
                raise ValueError("Atomize session history identity is invalid.")
            workbench_data = data["workbench"]
            workbench = (
                None
                if workbench_data is None
                else AtomizeReviewRecord.from_dict(
                    workbench_data,
                    issues=atomize_review_issue_projection(analysis),
                )
            )
            if workbench is not None and not workbench.matches_analysis(
                analysis_uid=analysis.uid,
                context_uid=analysis.context_uid,
                context_name=analysis.context_name,
                context_digest=analysis.context_digest,
                issues=atomize_review_issue_projection(analysis),
            ):
                raise ValueError("Atomize session history identity is invalid.")
            return analysis, workbench, path
        except (
            json.JSONDecodeError,
            AtomizeImpactError,
            AtomizeRecordError,
            TypeError,
            ValueError,
        ) as error:
            raise ValueError("Atomize session history is invalid.") from error

    def list_atomize_session_history(self) -> tuple:
        """Return every immutable displaced Atomize pair."""

        root = self.atomize_session_history_dir
        if not root.exists():
            return ()
        if not root.is_dir() or root.is_symlink():
            raise ValueError("Atomize session history is invalid.")
        records = []
        for context_dir in sorted(root.iterdir(), key=lambda item: item.name):
            if not context_dir.is_dir() or context_dir.is_symlink():
                raise ValueError("Atomize session history is invalid.")
            for path in sorted(context_dir.glob("*.json")):
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Atomize session history is invalid.")
                if path != self._atomize_session_history_path(
                    context_dir.name,
                    path.stem,
                ):
                    raise ValueError("Atomize session history is invalid.")
                records.append(
                    self.load_atomize_session_history(
                        context_dir.name,
                        path.stem,
                    )
                )
        return tuple(records)
