"""Persisted Update session lifecycle and stale-input validation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from memcommit.application.capabilities.semantic.goal_focus import FrozenGoalFocus, GoalFocusError
from memcommit.core.context import Context

from .changes import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    UpdateError,
    UpdateOperation,
    _is_sha256,
    _operation_from_dict,
    _require_exact_keys,
    _require_string,
    _require_uuid,
    _sha256_json,
    operation_digest,
)
from .inputs import (
    GrantedUpdateTarget,
    _fingerprint_contexts,
    _inline_update_source_digest,
    collect_update_inputs,
    inline_update_context,
)
from .receipts import ContextFingerprint, UpdateApplicationReceipt


UPDATE_SCHEMA_VERSION = 7
UPDATE_INLINE_MEMORY_SCHEMA_VERSION = 8
UPDATE_GOAL_FOCUS_SCHEMA_VERSION = 9
UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION = 10
UpdateStatus = Literal["impact", "staged", "applied", "undone"]


@dataclass(frozen=True)
class UpdateSession:
    uid: str
    status: UpdateStatus
    created_at: str
    source_uid: str
    source_name: str
    source_digest: str
    source_contexts: tuple[ContextFingerprint, ...]
    target_uid: str
    target_name: str
    target_digest: str
    target_contexts: tuple[ContextFingerprint, ...]
    operations: tuple[UpdateOperation, ...]
    source_include_descendants: bool = False
    target_include_descendants: bool = False
    source_memory_uid: str | None = None
    target_memory_uid: str | None = None
    inline_source_content: str | None = None
    granted_source: GrantedUpdateTarget | None = None
    granted_target: GrantedUpdateTarget | None = None
    goal_focus: FrozenGoalFocus | None = None
    application: UpdateApplicationReceipt | None = None

    def with_status(self, status: UpdateStatus) -> UpdateSession:
        if status not in {"impact", "staged"}:
            raise ValueError(
                "Only impact or staged status can be assigned without an "
                "application receipt."
            )
        return replace(self, status=status, application=None)

    def with_application(
        self,
        application: UpdateApplicationReceipt,
    ) -> UpdateSession:
        if self.status != "staged":
            raise ValueError("Only a staged update can receive an application receipt.")
        if application.operation_digest != operation_digest(self.operations):
            raise ValueError(
                "Application receipt does not match the update operations."
            )
        return replace(
            self,
            status="applied",
            application=application,
        )

    def with_restored_application(self, *, applied: bool) -> UpdateSession:
        """Project one exact retained receipt across command Undo or Redo."""
        expected = "undone" if applied else "applied"
        if self.status != expected or self.application is None:
            raise ValueError("Update application is not in the expected restore state.")
        return replace(self, status="applied" if applied else "undone")

    def to_dict(self) -> dict[str, object]:
        focused = (
            self.source_memory_uid is not None or self.target_memory_uid is not None
        )
        inline = self.inline_source_content is not None
        if self.goal_focus is not None:
            schema_version = (
                UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION
                if inline
                else UPDATE_GOAL_FOCUS_SCHEMA_VERSION
            )
        else:
            schema_version = (
                UPDATE_INLINE_MEMORY_SCHEMA_VERSION
                if inline
                else UPDATE_SCHEMA_VERSION if focused else 6
            )
        source: dict[str, object] = {
            "uid": self.source_uid,
            "name": self.source_name,
            "digest": self.source_digest,
            "contexts": [context.to_dict() for context in self.source_contexts],
            "include_descendants": self.source_include_descendants,
            "access": (
                None if self.granted_source is None else self.granted_source.to_dict()
            ),
        }
        target: dict[str, object] = {
            "uid": self.target_uid,
            "name": self.target_name,
            "digest": self.target_digest,
            "contexts": [context.to_dict() for context in self.target_contexts],
            "include_descendants": self.target_include_descendants,
            "access": (
                None if self.granted_target is None else self.granted_target.to_dict()
            ),
        }
        if focused or inline or self.goal_focus is not None:
            source["memory_uid"] = self.source_memory_uid
            target["memory_uid"] = self.target_memory_uid
        if inline:
            source_context = inline_update_context(self.inline_source_content)
            inline_memory = next(iter(source_context.memories.values()))
            if (
                self.source_uid != source_context.uid
                or self.source_name != source_context.name
            ):
                raise ValueError(
                    "Inline Update Source identity does not match its content."
                )
            source["inline_memory"] = {
                "uid": inline_memory.uid,
                "content": inline_memory.content,
            }
        result = {
            "schema_version": schema_version,
            "uid": self.uid,
            "status": self.status,
            "created_at": self.created_at,
            "source": source,
            "target": target,
            "operations": [operation.to_dict() for operation in self.operations],
            "application": (
                self.application.to_dict() if self.application is not None else None
            ),
        }
        if self.goal_focus is not None:
            result["goal_focus"] = self.goal_focus.receipt_record()
        return result

    @classmethod
    def from_dict(cls, value: object) -> UpdateSession:
        if not isinstance(value, dict):
            raise ValueError("Invalid update session.")
        schema_version = value.get("schema_version")
        if schema_version == 1:
            data = _require_exact_keys(
                value,
                {
                    "schema_version",
                    "uid",
                    "status",
                    "created_at",
                    "source",
                    "target",
                    "operations",
                },
                "update session",
            )
            application = None
        elif schema_version in {
            2,
            3,
            4,
            5,
            6,
            UPDATE_SCHEMA_VERSION,
            UPDATE_INLINE_MEMORY_SCHEMA_VERSION,
            UPDATE_GOAL_FOCUS_SCHEMA_VERSION,
            UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION,
        }:
            keys = {
                "schema_version",
                "uid",
                "status",
                "created_at",
                "source",
                "target",
                "operations",
                "application",
            }
            if schema_version in {
                UPDATE_GOAL_FOCUS_SCHEMA_VERSION,
                UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION,
            }:
                keys.add("goal_focus")
            data = _require_exact_keys(
                value,
                keys,
                "update session",
            )
            application = (
                None
                if data["application"] is None
                else UpdateApplicationReceipt.from_dict(data["application"])
            )
        else:
            raise ValueError("Unsupported update session schema version.")
        status = data["status"]
        if status not in {"impact", "staged", "applied", "undone"}:
            raise ValueError("Invalid update session status.")
        if (status in {"applied", "undone"}) != (application is not None):
            raise ValueError("Invalid update application state.")

        source_keys = {"uid", "name", "digest", "contexts"}
        if schema_version == 5:
            source_keys.add("access")
        elif schema_version == 6:
            source_keys.update({"access", "include_descendants"})
        elif schema_version in {
            UPDATE_SCHEMA_VERSION,
            UPDATE_GOAL_FOCUS_SCHEMA_VERSION,
        }:
            source_keys.update({"access", "include_descendants", "memory_uid"})
        elif schema_version in {
            UPDATE_INLINE_MEMORY_SCHEMA_VERSION,
            UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION,
        }:
            source_keys.update(
                {"access", "include_descendants", "memory_uid", "inline_memory"}
            )
        source = _require_exact_keys(data["source"], source_keys, "update source")
        target_keys = {"uid", "name", "digest", "contexts"}
        if schema_version in {4, 5}:
            target_keys.add("access")
        elif schema_version == 6:
            target_keys.update({"access", "include_descendants"})
        elif schema_version in {
            UPDATE_SCHEMA_VERSION,
            UPDATE_INLINE_MEMORY_SCHEMA_VERSION,
            UPDATE_GOAL_FOCUS_SCHEMA_VERSION,
            UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION,
        }:
            target_keys.update({"access", "include_descendants", "memory_uid"})
        target = _require_exact_keys(data["target"], target_keys, "update target")
        granted_source = (
            None
            if schema_version < 5 or source["access"] is None
            else GrantedUpdateTarget.from_dict(source["access"])
        )
        granted_target = (
            None
            if schema_version < 4
            else (
                None
                if target["access"] is None
                else GrantedUpdateTarget.from_dict(target["access"])
            )
        )
        if not _is_sha256(source["digest"]) or not _is_sha256(target["digest"]):
            raise ValueError("Invalid update input digest.")
        if not isinstance(source["contexts"], list) or not isinstance(
            target["contexts"],
            list,
        ):
            raise ValueError("Invalid update Context fingerprints.")
        if not isinstance(data["operations"], list):
            raise ValueError("Invalid update operations.")
        source_include_descendants = (
            source["include_descendants"]
            if schema_version
            in {
                6,
                UPDATE_SCHEMA_VERSION,
                UPDATE_INLINE_MEMORY_SCHEMA_VERSION,
                UPDATE_GOAL_FOCUS_SCHEMA_VERSION,
                UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION,
            }
            else False
        )
        target_include_descendants = (
            target["include_descendants"]
            if schema_version
            in {
                6,
                UPDATE_SCHEMA_VERSION,
                UPDATE_INLINE_MEMORY_SCHEMA_VERSION,
                UPDATE_GOAL_FOCUS_SCHEMA_VERSION,
                UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION,
            }
            else False
        )
        source_memory_uid = (
            (
                None
                if source["memory_uid"] is None
                else _require_uuid(
                    source["memory_uid"],
                    "selected Source Memory uid",
                )
            )
            if schema_version
            in {
                UPDATE_SCHEMA_VERSION,
                UPDATE_INLINE_MEMORY_SCHEMA_VERSION,
                UPDATE_GOAL_FOCUS_SCHEMA_VERSION,
                UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION,
            }
            else None
        )
        target_memory_uid = (
            (
                None
                if target["memory_uid"] is None
                else _require_uuid(
                    target["memory_uid"],
                    "selected Target Memory uid",
                )
            )
            if schema_version
            in {
                UPDATE_SCHEMA_VERSION,
                UPDATE_INLINE_MEMORY_SCHEMA_VERSION,
                UPDATE_GOAL_FOCUS_SCHEMA_VERSION,
                UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION,
            }
            else None
        )
        inline_source_content: str | None = None
        if schema_version in {
            UPDATE_INLINE_MEMORY_SCHEMA_VERSION,
            UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION,
        }:
            inline_record = _require_exact_keys(
                source["inline_memory"],
                {"uid", "content"},
                "inline update Memory",
            )
            inline_source_content = _require_string(
                inline_record["content"],
                "inline update Memory content",
            )
            inline_context = inline_update_context(inline_source_content)
            inline_memory = next(iter(inline_context.memories.values()))
            if (
                _require_uuid(
                    inline_record["uid"],
                    "inline update Memory uid",
                )
                != inline_memory.uid
                or source["uid"] != inline_context.uid
                or source["name"] != inline_context.name
            ):
                raise ValueError("Invalid inline Update Source identity.")
        if (
            type(source_include_descendants) is not bool
            or type(target_include_descendants) is not bool
            or (
                source_memory_uid is not None and not isinstance(source_memory_uid, str)
            )
            or (
                target_memory_uid is not None and not isinstance(target_memory_uid, str)
            )
        ):
            raise ValueError("Invalid update descendant scope.")
        if schema_version in {
            UPDATE_INLINE_MEMORY_SCHEMA_VERSION,
            UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION,
        }:
            inline_context = inline_update_context(inline_source_content or "")
            inline_fingerprints = _fingerprint_contexts([inline_context])
            if (
                source_include_descendants
                or source_memory_uid is not None
                or granted_source is not None
                or source["digest"] != _inline_update_source_digest(inline_context)
                or tuple(
                    ContextFingerprint.from_dict(item) for item in source["contexts"]
                )
                != inline_fingerprints
            ):
                raise ValueError("Invalid inline Update Source frame.")

        operations = tuple(_operation_from_dict(item) for item in data["operations"])
        if source_memory_uid is not None and any(
            any(ref.memory_uid != source_memory_uid for ref in operation.source_refs)
            for operation in operations
        ):
            raise ValueError(
                "Focused update operation cites an out-of-scope Source Memory."
            )
        if target_memory_uid is not None and any(
            isinstance(operation, AddOperation)
            or operation.memory_uid != target_memory_uid
            for operation in operations
        ):
            raise ValueError("Focused update operation targets an out-of-scope Memory.")
        if schema_version < 3 and any(
            isinstance(operation, RemoveOperation) for operation in operations
        ):
            # Removal was not part of the approval contract represented by
            # legacy sessions, so accepting one there would misstate what an
            # older schema could have authorized.
            raise ValueError("Legacy update sessions cannot contain remove operations.")
        edit_targets = {
            (operation.owner_context_uid, operation.memory_uid)
            for operation in operations
            if isinstance(operation, EditOperation)
        }
        if len(edit_targets) != sum(
            isinstance(operation, EditOperation) for operation in operations
        ):
            raise ValueError("Duplicate edit target in update session.")
        operation_identities = [
            (operation.owner_context_uid, operation.memory_uid)
            for operation in operations
        ]
        if len(operation_identities) != len(set(operation_identities)):
            raise ValueError("Duplicate Memory uid in update session.")
        if (
            application is not None
            and application.operation_digest != operation_digest(operations)
        ):
            raise ValueError(
                "Update application receipt does not match its operations."
            )
        if application is not None:
            target_contexts = tuple(
                ContextFingerprint.from_dict(item) for item in target["contexts"]
            )
            if [
                (context.uid, context.name) for context in application.target_contexts
            ] != [(context.uid, context.name) for context in target_contexts]:
                raise ValueError("Applied target Context identities changed.")
            operation_owners = {
                (operation.owner_context_uid, operation.owner_context_name)
                for operation in operations
            }
            checkpoint_owners = {
                (checkpoint.context_uid, checkpoint.context_name)
                for checkpoint in application.checkpoints
            }
            if operation_owners != checkpoint_owners:
                raise ValueError(
                    "Update checkpoints do not cover every affected Context."
                )

        try:
            goal_focus = (
                FrozenGoalFocus.from_receipt_record(data["goal_focus"])
                if schema_version
                in {
                    UPDATE_GOAL_FOCUS_SCHEMA_VERSION,
                    UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION,
                }
                else None
            )
        except GoalFocusError as error:
            raise ValueError("Invalid Update Goal focus.") from error

        return cls(
            uid=_require_uuid(data["uid"], "update session uid"),
            status=status,
            created_at=_require_string(
                data["created_at"],
                "update creation time",
            ),
            source_uid=_require_string(source["uid"], "source Context uid"),
            source_name=_require_string(source["name"], "source Context name"),
            source_digest=source["digest"],
            source_contexts=tuple(
                ContextFingerprint.from_dict(item) for item in source["contexts"]
            ),
            target_uid=_require_string(target["uid"], "target Context uid"),
            target_name=_require_string(target["name"], "target Context name"),
            target_digest=target["digest"],
            target_contexts=tuple(
                ContextFingerprint.from_dict(item) for item in target["contexts"]
            ),
            operations=operations,
            source_include_descendants=source_include_descendants,
            target_include_descendants=target_include_descendants,
            source_memory_uid=source_memory_uid,
            target_memory_uid=target_memory_uid,
            inline_source_content=inline_source_content,
            granted_source=granted_source,
            granted_target=granted_target,
            goal_focus=goal_focus,
            application=application,
        )


def inline_update_session_source(session: UpdateSession) -> Context | None:
    """Reconstruct and validate a saved process-local Update Source."""

    if not isinstance(session, UpdateSession):
        raise TypeError("Inline Update reconstruction requires an UpdateSession.")
    if session.inline_source_content is None:
        return None
    source = inline_update_context(session.inline_source_content)
    if (
        source.uid != session.source_uid
        or source.name != session.source_name
        or session.source_digest != _inline_update_source_digest(source)
        or session.source_contexts != _fingerprint_contexts([source])
        or session.source_include_descendants
        or session.source_memory_uid is not None
        or session.granted_source is not None
    ):
        raise UpdateError("Inline Update Source no longer matches its saved frame.")
    return source


def update_session_record_digest(session: UpdateSession) -> str:
    """Hash the complete saved Update revision used by one semantic turn."""

    if not isinstance(session, UpdateSession):
        raise TypeError("Update session digest requires an UpdateSession.")
    return _sha256_json(session.to_dict())
def session_matches(
    session: UpdateSession,
    source: Context,
    target: Context,
    *,
    granted_source: GrantedUpdateTarget | None = None,
    granted_target: GrantedUpdateTarget | None = None,
) -> bool:
    """Return whether an impact plan still describes the exact A/B inputs."""
    if (
        session.source_uid != source.uid
        or session.source_name != source.name
        or session.target_uid != target.uid
        or session.target_name != target.name
        or session.granted_source != granted_source
        or session.granted_target != granted_target
    ):
        return False
    try:
        inputs = collect_update_inputs(
            source,
            target,
            source_memory_selector=session.source_memory_uid,
            target_memory_selector=session.target_memory_uid,
        )
    except UpdateError:
        return False
    return (
        session.source_memory_uid == inputs.source_memory_uid
        and session.target_memory_uid == inputs.target_memory_uid
        and session.source_digest == inputs.source_digest
        and session.target_digest == inputs.target_digest
        and session.source_contexts == inputs.source_contexts
        and session.target_contexts == inputs.target_context_fingerprints
    )


def applied_session_matches(
    session: UpdateSession,
    source: Context,
    target: Context,
    *,
    granted_source: GrantedUpdateTarget | None = None,
    granted_target: GrantedUpdateTarget | None = None,
) -> bool:
    """Return whether A and the locally applied B still match the receipt."""
    application = session.application
    if (
        session.status != "applied"
        or application is None
        or session.source_uid != source.uid
        or session.source_name != source.name
        or session.target_uid != target.uid
        or session.target_name != target.name
        or session.granted_source != granted_source
        or session.granted_target != granted_target
    ):
        return False
    try:
        inputs = collect_update_inputs(
            source,
            target,
            source_memory_selector=session.source_memory_uid,
            target_memory_selector=session.target_memory_uid,
        )
    except UpdateError:
        return False
    return (
        session.source_memory_uid == inputs.source_memory_uid
        and session.target_memory_uid == inputs.target_memory_uid
        and session.source_digest == inputs.source_digest
        and session.source_contexts == inputs.source_contexts
        and application.target_digest == inputs.target_digest
        and application.target_contexts == inputs.target_context_fingerprints
        and application.operation_digest == operation_digest(session.operations)
    )


def count_operations(session: UpdateSession) -> tuple[int, int, int]:
    """Return (edit_count, addition_count, removal_count)."""
    return (
        sum(isinstance(operation, EditOperation) for operation in session.operations),
        sum(isinstance(operation, AddOperation) for operation in session.operations),
        sum(isinstance(operation, RemoveOperation) for operation in session.operations),
    )
