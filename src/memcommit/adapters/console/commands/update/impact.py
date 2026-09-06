"""Update-owned console adapter for directional and saved Impact."""

from __future__ import annotations

import sys

import typer

from memcommit.application.authorization import ContextUse, authorize_context_use
from memcommit.adapters.console.commands.impact.sessions import (
    ImpactSessionPresentation,
    run_saved_impact_handoff_loop,
    update_impact_presentation,
)
from memcommit.adapters.console.commands.update.render import (
    render_plan,
)
from memcommit.adapters.console.commands.update.workbench.application import (
    run_update_workbench,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.context_access.access import (
    GrantedReadStore,
    freeze_granted_context_binding,
    resolve_context_access,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
)
from memcommit.adapters.console.commands.update.endpoint_operands import (
    resolve_update_endpoint_accesses,
)
from memcommit.application.operations.update.model import (
    UpdateError,
    plan_update,
    required_update_context_uses,
    session_matches,
)
from memcommit.application.capabilities.context_scope_loading import load_context_scope
from memcommit.core.context_targeting.uid_locator import resolve_exact_or_unique_uid
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)


def open_saved_update_impact(
    store: MemoryStore,
    *,
    session_uid: str | None,
) -> None:
    from memcommit.persistence.operations.update.receipt_repository import (
        UpdateReceiptRepository,
    )

    current = store.load_staged_update() or store.load_impact_plan()
    receipts = UpdateReceiptRepository(store)
    retained = receipts.list()
    if current is None and not retained:
        raise ValueError(
            "No saved Update or directional Impact plan exists. Run "
            "'mem impact --from SOURCE --to TARGET' first."
        )
    retained_uids = {candidate.uid for candidate in retained}
    if session_uid is None:
        session = current or retained[0]
    else:
        candidates = retained
        if current is not None and current.uid not in retained_uids:
            candidates = (*retained, current)
        session = resolve_exact_or_unique_uid(
            candidates,
            session_uid,
            uid=lambda candidate: candidate.uid,
            label="Saved Update Impact artifact",
        )
    selected_is_retained = session.uid in retained_uids

    def load_presentation() -> ImpactSessionPresentation:
        if selected_is_retained:
            return update_impact_presentation(receipts.load(session.uid))
        current = store.load_staged_update() or store.load_impact_plan()
        if current is None or current.uid != session.uid:
            raise ValueError(
                "The saved Update changed while returning from Apply. Reopen it."
            )
        return update_impact_presentation(current)

    def open_owning_workflow() -> None:
        # Re-enter through Update's public command boundary so the exact live
        # endpoints, grants, operation digest, and final Apply confirmation are
        # checked again after leaving this immutable Impact projection.
        from memcommit.adapters.console.commands.update.command import cmd as update_cmd

        update_cmd(
            source_name=session.source_name,
            target_name=session.target_name,
            replace_stage=False,
            source_descendants=session.source_include_descendants,
            target_descendants=session.target_include_descendants,
        )

    run_saved_impact_handoff_loop(
        load_presentation=load_presentation,
        open_owning_workflow=open_owning_workflow,
        kind="update",
    )


def run_directional_update_impact(
    *,
    store: MemoryStore,
    current_name: str | None,
    source_name: str | None,
    target_name: str | None,
    source_memory: str | None = None,
    target_memory: str | None = None,
    source_descendants: bool = False,
    target_descendants: bool = False,
) -> None:
    """Preview one explicit or current-filled directional endpoint pair."""

    try:
        endpoints = resolve_update_endpoint_accesses(
            store,
            source_locator=source_name,
            target_locator=target_name,
            current=current_name,
        )
        source_access = endpoints.source.value
        target_access = endpoints.target.value
        authorize_context_use(source_access, ContextUse.READ)
        target_authorization = authorize_context_use(
            target_access,
            ContextUse.READ,
        )
        source_store = (
            GrantedReadStore(source_access) if source_access.is_granted else store
        )
        target_store = (
            GrantedReadStore(target_access) if target_access.is_granted else store
        )
        source = load_context_scope(
            source_store,
            (
                source_access.access_name
                if source_access.is_granted
                else source_access.context_name
            ),
            include_descendants=source_descendants,
        )
        target = load_context_scope(
            target_store,
            (
                target_access.access_name
                if target_access.is_granted
                else target_access.context_name
            ),
            include_descendants=target_descendants,
        )
        granted_source = (
            freeze_granted_context_binding(source_access)
            if source_access.is_granted
            else None
        )
        granted_target = (
            freeze_granted_context_binding(target_access)
            if target_access.is_granted
            else None
        )
        with CommandProgress(
            "IMPACT UPDATE",
            "connecting provider",
            total=2,
        ) as progress:
            progress.update("planning memory changes", step=2)
            session = plan_update(
                source,
                target,
                # Keep connection lazy so Update's complete authority and
                # semantic-disclosure preflight runs first. A nested live
                # Grant must fail without contacting a provider at all.
                connect_codex_chatgpt_provider,
                status="impact",
                source_include_descendants=source_descendants,
                target_include_descendants=target_descendants,
                granted_source=granted_source,
                granted_target=granted_target,
                source_memory_selector=source_memory,
                target_memory_selector=target_memory,
                allowed_target_uses=target_authorization.allowed,
            )

        authorize_context_use(
            target_access,
            required_update_context_uses(session.operations),
        )

        # Provider latency is not an authorization lease. Re-resolve both
        # endpoints and rebuild both projections before publishing the plan.
        with authority_grant_snapshot_lock() as registry:
            current_source_access = resolve_context_access(
                store,
                endpoints.source.name,
                current_name=current_name,
                required_permission="READ",
                registry=registry,
            )
            current_target_access = resolve_context_access(
                store,
                endpoints.target.name,
                current_name=current_name,
                required_permission="READ",
                registry=registry,
            )
            authorize_context_use(current_source_access, ContextUse.READ)
            authorize_context_use(
                current_target_access,
                required_update_context_uses(session.operations),
            )
            current_source_store = (
                GrantedReadStore(
                    current_source_access,
                    registry=registry,
                )
                if current_source_access.is_granted
                else store
            )
            current_target_store = (
                GrantedReadStore(
                    current_target_access,
                    registry=registry,
                )
                if current_target_access.is_granted
                else store
            )
            current_source = load_context_scope(
                current_source_store,
                (
                    current_source_access.access_name
                    if current_source_access.is_granted
                    else current_source_access.context_name
                ),
                include_descendants=source_descendants,
            )
            current_target = load_context_scope(
                current_target_store,
                (
                    current_target_access.access_name
                    if current_target_access.is_granted
                    else current_target_access.context_name
                ),
                include_descendants=target_descendants,
            )
            current_granted_source = (
                freeze_granted_context_binding(current_source_access)
                if current_source_access.is_granted
                else None
            )
            current_granted_target = (
                freeze_granted_context_binding(current_target_access)
                if current_target_access.is_granted
                else None
            )
            if not session_matches(
                session,
                current_source,
                current_target,
                granted_source=current_granted_source,
                granted_target=current_granted_target,
            ):
                raise UpdateError(
                    "An update endpoint or grant changed while planning; "
                    "no preview was saved."
                )
            store.save_impact_plan(session)
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        UpdateError,
        ValueError,
    ) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if sys.stdin.isatty() and sys.stdout.isatty():
        run_update_workbench(session)
    else:
        render_plan(session, staged=False)


__all__ = ["open_saved_update_impact", "run_directional_update_impact"]
