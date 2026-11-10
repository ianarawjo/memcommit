"""Reconcile enabled Profiles without choosing a conflicting version."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from memcommit.application.operations.profile.config import (
    load_profile_registry,
    profile_store_dir,
)
from memcommit.persistence.operations.mem_sync.automatic import (
    read_automatic_settings,
    sync_operation_lock,
    write_automatic_record,
    write_automatic_settings,
)

from ..model import SyncConflictChoiceRequired, SyncResult
from ..publication import publish_profile_changes
from ..runtime import prepare_sync_plan


@dataclass(frozen=True)
class AutomaticSyncOutcome:
    state: str
    message: str = ""
    result: SyncResult | None = None


def configure_automatic_sync(store, enabled: bool):
    """Consent is fresh and Profile-local; obsolete settings never enable it."""
    if type(enabled) is not bool:
        raise ValueError("Automatic Sync enabled must be a boolean.")
    with sync_operation_lock(store):
        profile_uid = next(
            (
                profile.uid
                for profile in load_profile_registry().profiles
                if profile_store_dir(profile).absolute() == store.store_dir.absolute()
            ),
            None,
        )
        if enabled:
            current = read_automatic_settings(store)
            if current.enabled and current.profile_uid == profile_uid:
                return current
        settings = write_automatic_settings(store, enabled, profile_uid=profile_uid)
        record_automatic_outcome(
            store, AutomaticSyncOutcome("waiting" if enabled else "off")
        )
        return settings


def automatic_owner_matches(store, settings) -> bool:
    """A copied, moved, removed, or reassigned Profile cannot inherit a worker."""
    if store.store_dir.is_symlink() or not store.store_dir.is_dir():
        return False
    if settings.profile_uid is None:
        return True
    for profile in load_profile_registry().profiles:
        if (
            profile.uid == settings.profile_uid
            and profile_store_dir(profile).absolute() == store.store_dir.absolute()
        ):
            from memcommit.application.operations.profile.project_root import (
                validate_profile_marker,
            )

            # Workers retain a Store opened without creation, so repeat the
            # ordinary Store ownership check before trusting that frozen path.
            validate_profile_marker(profile)
            return True
    return False


def record_automatic_outcome(store, outcome, *, trigger=None):
    write_automatic_record(
        store,
        "automatic-status.json",
        {
            "state": outcome.state,
            "message": outcome.message,
            "trigger": trigger,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "run_uid": outcome.result.run_uid if outcome.result is not None else None,
        },
    )


def synchronize_automatically(store, *, trigger, generation=None):
    """Skip an unchanged plan; ordinary explicit Sync keeps its checkpoint behavior."""
    if trigger not in ("ENABLED", "FILE_CHANGE", "COMMAND_START", "COMMAND_END"):
        raise ValueError("Invalid automatic Sync trigger.")
    with sync_operation_lock(store):
        settings = read_automatic_settings(store)
        if not settings.enabled or (
            generation is not None and generation != settings.generation
        ):
            return AutomaticSyncOutcome("off")
        try:
            if not automatic_owner_matches(store, settings):
                raise ValueError(
                    "Automatic Sync Profile ownership changed; enable it again at the current root."
                )
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
            # A foreign Store cannot receive even our scheduling status. Return
            # the diagnostic to the caller without writing into its namespace.
            return AutomaticSyncOutcome("error", str(error))
        try:
            plan = prepare_sync_plan(store, store.store_dir.parent)
            if plan.conflicts:
                raise SyncConflictChoiceRequired(
                    "Both mem and Markdown changed. Run 'mem sync' to choose a version."
                )
            changed = bool(plan.profile_changes.changes) or any(
                effect.action != "UNCHANGED"
                and not (
                    effect.action == "REMOVE"
                    and dict(export.previous_hashes)[effect.path] is None
                )
                for export in plan.exports
                for effect in export.effects
            )
            result = (
                publish_profile_changes(
                    store,
                    store.store_dir.parent,
                    plan,
                    trigger=trigger,
                )
                if changed
                else None
            )
            outcome = AutomaticSyncOutcome(
                "synced" if result is not None else "idle", result=result
            )
        except SyncConflictChoiceRequired as error:
            outcome = AutomaticSyncOutcome("conflict", str(error))
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
            outcome = AutomaticSyncOutcome("error", str(error))
        record_automatic_outcome(store, outcome, trigger=trigger)
        return outcome
