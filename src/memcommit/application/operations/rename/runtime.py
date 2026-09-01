"""MemoryStore implementation of Context namespace Rename."""

from __future__ import annotations

from dataclasses import dataclass, replace

from memcommit.application.capabilities.operand_resolution import (
    freeze_local_context_operand_candidates,
    resolve_existing_context_operand,
)
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.capabilities.durable_uid_resolution import (
    is_unresolved_uid_selector,
)
from memcommit.application.operations.rename.application import (
    RenameBinding,
    RenamePlan,
    RenameRequest,
    RenameResult,
    apply_rename,
    plan_rename,
)
from memcommit.application.operations.profile.config import (
    ProfileRegistry,
    load_profile_registry,
)
from memcommit.application.operations.profile.model.grants import (
    _assert_access_name_available,
)
from memcommit.application.operations.profile.model._storage import (
    ProfileError,
    _registry_lock,
    _write_registry,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store.context_memory.models import ContextRenamePlan


@dataclass(frozen=True)
class _GrantPlacementRenameToken:
    generation: int
    bindings: tuple[RenameBinding, ...]


class ContextOrGrantPlacementRenamePort:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def freeze(self, request: RenameRequest) -> RenamePlan:
        if is_unresolved_uid_selector(request.old_locator):
            return self._freeze_context(request)
        old_name = resolve_context_locator(
            request.old_locator,
            current=request.current_context_name,
        )
        try:
            validate_portable_context_name(old_name)
        except ValueError as error:
            raise ValueError(
                "General Context rename requires a portable existing Context "
                "name; use 'mem profile migrate-context' for a nonportable "
                "legacy source."
            ) from error
        if self._store.context_exists(old_name):
            return self._freeze_context(request)
        return self._freeze_grant_placement(old_name, request.new_name)

    def _freeze_context(self, request: RenameRequest) -> RenamePlan:
        old_name = resolve_existing_context_operand(
            freeze_local_context_operand_candidates(self._store),
            request.old_locator,
            current=request.current_context_name,
        ).name
        token = self._store.plan_context_rename(old_name, request.new_name)
        return RenamePlan(
            subject="CONTEXT_NAMESPACE",
            old_name=token.old_name,
            new_name=token.new_name,
            bindings=tuple(
                RenameBinding(
                    old_name=binding.old_name,
                    new_name=binding.new_name,
                    context_uid=binding.context_uid,
                )
                for binding in token.bindings
            ),
            changed_owner_count=len(token.changed_owner_names),
            reference_count=token.reference_count,
            checkpoint_reference_count=token.checkpoint_reference_count,
            translation_artifact_count=token.translation_artifact_count,
            meld_session_count=token.meld_session_count,
            current_before=token.current_before,
            current_after=token.current_after,
            graph_digest=token.graph_digest,
            token=token,
        )

    def _freeze_grant_placement(
        self,
        old_name: str,
        new_name: str,
    ) -> RenamePlan:
        validate_portable_context_name(new_name)
        if old_name == new_name:
            raise ValueError("Rename destination must differ from its source.")
        registry = load_profile_registry()
        active = registry.active
        selected = tuple(
            placement
            for placement in registry.grant_placements
            if placement.grantee_profile_uid == active.uid
            and (
                placement.access_name == old_name
                or placement.access_name.startswith(old_name + "/")
            )
        )
        if not any(placement.access_name == old_name for placement in selected):
            raise FileNotFoundError(
                f"Context or granted access '{old_name}' does not exist."
            )
        selected_uids = {placement.grant_uid for placement in selected}
        bindings = tuple(
            RenameBinding(
                old_name=placement.access_name,
                new_name=new_name + placement.access_name[len(old_name) :],
                grant_uid=placement.grant_uid,
            )
            for placement in sorted(selected, key=lambda item: item.access_name)
        )
        for binding in bindings:
            _assert_access_name_available(
                registry,
                grantee=active,
                access_name=binding.new_name,
                replacing_uid=binding.grant_uid,
            )
            if any(
                placement.grantee_profile_uid == active.uid
                and placement.grant_uid not in selected_uids
                and placement.access_name.casefold() == binding.new_name.casefold()
                for placement in registry.grant_placements
            ):
                raise FileExistsError(
                    f"Granted access '{binding.new_name}' already exists."
                )
        token = _GrantPlacementRenameToken(registry.generation, bindings)
        current_context = self._store.current_context_name()
        return RenamePlan(
            subject="GRANT_PLACEMENT",
            old_name=old_name,
            new_name=new_name,
            bindings=bindings,
            changed_owner_count=0,
            reference_count=0,
            checkpoint_reference_count=0,
            translation_artifact_count=0,
            meld_session_count=0,
            current_before=current_context,
            current_after=current_context,
            graph_digest=str(registry.generation),
            token=token,
        )

    def apply(self, plan: RenamePlan) -> RenameResult:
        token = plan.token
        if isinstance(token, _GrantPlacementRenameToken):
            return self._apply_grant_placement(plan, token)
        if not isinstance(token, ContextRenamePlan):
            raise TypeError("Rename plan token is invalid.")
        result = self._store.rename_contexts(token)
        return RenameResult(
            subject="CONTEXT_NAMESPACE",
            old_name=plan.old_name,
            new_name=plan.new_name,
            renamed_context_count=result.renamed_context_count,
            renamed_placement_count=0,
            changed_owner_count=result.changed_owner_count,
            reference_count=result.reference_count,
            checkpoint_reference_count=result.checkpoint_reference_count,
            translation_artifact_count=result.translation_artifact_count,
            meld_session_count=result.meld_session_count,
            current_context=result.current_context,
        )

    def _apply_grant_placement(
        self,
        plan: RenamePlan,
        token: _GrantPlacementRenameToken,
    ) -> RenameResult:
        with _registry_lock():
            registry = load_profile_registry()
            if registry.generation != token.generation:
                raise ProfileError(
                    "Granted Context access changed after review; nothing was renamed."
                )
            names_by_grant_uid = {
                binding.grant_uid: binding
                for binding in token.bindings
                if binding.grant_uid is not None
            }
            current = {
                placement.grant_uid: placement
                for placement in registry.grant_placements
                if placement.grant_uid in names_by_grant_uid
            }
            if len(current) != len(names_by_grant_uid) or any(
                current[grant_uid].access_name != binding.old_name
                for grant_uid, binding in names_by_grant_uid.items()
            ):
                raise ProfileError(
                    "Granted Context access changed after review; nothing was renamed."
                )
            placements = tuple(
                replace(
                    placement,
                    access_name=names_by_grant_uid[placement.grant_uid].new_name,
                )
                if placement.grant_uid in names_by_grant_uid
                else placement
                for placement in registry.grant_placements
            )
            updated = ProfileRegistry(
                generation=registry.generation + 1,
                active_uid=registry.active_uid,
                profiles=registry.profiles,
                grants=registry.grants,
                removed_profile_uids=registry.removed_profile_uids,
                grant_placements=placements,
            )
            _write_registry(updated)
        return RenameResult(
            subject="GRANT_PLACEMENT",
            old_name=plan.old_name,
            new_name=plan.new_name,
            renamed_context_count=0,
            renamed_placement_count=len(token.bindings),
            changed_owner_count=0,
            reference_count=0,
            checkpoint_reference_count=0,
            translation_artifact_count=0,
            meld_session_count=0,
            current_context=self._store.current_context_name(),
        )


def prepare_rename(store: MemoryStore, request: RenameRequest) -> RenamePlan:
    return plan_rename(request, port=ContextOrGrantPlacementRenamePort(store))


def execute_rename(store: MemoryStore, plan: RenamePlan) -> RenameResult:
    return apply_rename(plan, port=ContextOrGrantPlacementRenamePort(store))


__all__ = [
    "ContextOrGrantPlacementRenamePort",
    "execute_rename",
    "prepare_rename",
]
