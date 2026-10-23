"""Run one process-local Query over local Sources."""

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.application.context_access.access import (
    resolve_context_access,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.capabilities.durable_uid_resolution import (
    is_unresolved_uid_selector,
)
from memcommit.application.capabilities.operand_resolution import (
    ContextOperandNotFoundError,
)
from memcommit.providers.connection import connect_ordinary_query_provider
from memcommit.adapters.console.commands.query.workbench.screen import (
    run_query_workbench,
)
from memcommit.adapters.console.terminal.components.session_help import (
    bind_session_help,
)
from memcommit.application.context_access.readable_contexts import (
    freeze_readable_context_catalog,
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    is_interactive_terminal,
)
from memcommit.adapters.console.commands.query.presentation import (
    render_ordinary_query_response,
)
from memcommit.application.capabilities.context_locator import (
    is_relative_context_locator,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    ContextTraversal,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.query.ordinary_application import (
    OrdinaryQueryRequest,
)
from memcommit.application.operations.query.ordinary_runtime import (
    execute_ordinary_query,
)
from memcommit.application.operations.query.save_answer import (
    SaveQueryAnswerRequest,
)
from memcommit.application.operations.query.save_answer_runtime import (
    execute_save_query_answer,
)
from memcommit.persistence.store import MemoryStore


def _query_ordinary_context(
    store: MemoryStore,
    *,
    context_names: tuple[str | None, ...],
    current_name: str | None,
    question: str,
    traversal: ContextTraversal,
    all_contexts: bool = False,
) -> None:
    """Answer from the same frozen searchable frame used by ordinary Find."""
    accesses = tuple(
        resolve_context_access(
            store,
            context_name,
            current_name=current_name,
        )
        for context_name in context_names
    )
    if not accesses:
        raise ValueError("Select at least one readable Query Context.")
    target_names = tuple(access.access_name for access in accesses)
    if len(set(target_names)) != len(target_names):
        raise ValueError("Query Context roots must be distinct.")
    if all_contexts:
        # PROFILE is only a process-local shortcut. Freeze the concrete public
        # names once so provider work cannot reinterpret --all after current or
        # Profile state changes.
        catalog = freeze_profile_readable_context_catalog(store, accesses[0])
        target_names = tuple(catalog.list_context_names())
    elif len(accesses) == 1:
        catalog = freeze_readable_context_catalog(store, accesses[0])
    else:
        # Multiple explicit roots need the shared Profile catalog only as a
        # namespace. The request below still freezes exactly the named roots.
        catalog = freeze_profile_readable_context_catalog(store, accesses[0])
    request = OrdinaryQueryRequest(
        question=question,
        target_names=target_names,
        include_descendants=traversal.include_descendants,
    )
    with CommandProgress(
        "QUERY",
        "connecting provider",
        total=2,
    ) as progress:
        response = execute_ordinary_query(
            request,
            store=store,
            catalog=catalog,
            provider_factory=connect_ordinary_query_provider,
            observer=lambda stage: (
                progress.update(
                    "answering question",
                    step=2,
                )
                if stage == "ANSWERING"
                else None
            ),
        )
    render_ordinary_query_response(response)


def _open_query_workbench(
    store: MemoryStore,
    *,
    context_name: str | None,
    traversal: ContextTraversal | None = None,
) -> None:
    """Open one blank Query over a frozen local Context catalog."""

    context_snapshot = ContextOperandSnapshot.capture(store)
    resolved = resolve_existing_context_access(
        store,
        context_name,
        current_name=context_snapshot.current_name,
    )
    access = resolved.value
    catalog = freeze_profile_readable_context_catalog(store, access)
    names = tuple(catalog.list_context_names())
    displayed_current = (
        context_snapshot.current_name
        if context_snapshot.current_name in names
        else access.access_name
    )
    annotations = {}

    def run_ordinary(request: OrdinaryQueryRequest):
        return execute_ordinary_query(
            request,
            store=store,
            catalog=catalog,
            provider_factory=connect_ordinary_query_provider,
        )

    initial_descendants = (
        traversal.include_descendants if traversal is not None else True
    )
    workbench_result = run_query_workbench(
        names,
        current_context=displayed_current,
        initial_context=access.access_name,
        run_ordinary=run_ordinary,
        initial_include_descendants=initial_descendants,
        annotations=annotations,
        help_binder=bind_session_help,
        local_context_names=tuple(store.list_context_names()),
        validate_save_location=store.assert_context_creatable,
    )
    if workbench_result is None or workbench_result.status != "SAVE":
        return
    assert workbench_result.response is not None
    assert workbench_result.save_location is not None
    saved = execute_save_query_answer(
        SaveQueryAnswerRequest(
            response=workbench_result.response,
            destination_name=workbench_result.save_location,
        ),
        store=store,
    )
    typer.secho(
        "Saved complete Query answer in new Context "
        f"'{display_escape_text(saved.context_name)}' "
        f"[{saved.context_uid[:8]}].",
        fg=typer.colors.GREEN,
    )


def _resolve_positional_query_target(
    store, selector, *, snapshot, explicit_context_option=False, context_candidates=None
):
    """Resolve explicit target intent before permitting ordinary-question fallback."""
    try:
        return resolve_existing_context_access(
            store,
            selector,
            current_name=snapshot.current_name,
            candidates=context_candidates,
        ).value
    except (FileNotFoundError, ContextOperandNotFoundError):
        if (
            explicit_context_option
            or is_relative_context_locator(selector)
            or is_unresolved_uid_selector(selector)
        ):
            raise
        return None


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(help="Existing Context, or a question for the current Context"),
    ] = None,
    question: Annotated[
        Optional[str], typer.Argument(help="Question for the selected Context")
    ] = None,
    context_name: Annotated[
        Optional[list[str]],
        typer.Option("--context", "-c", help="Context root; repeat for multiple roots"),
    ] = None,
    all_contexts: Annotated[
        bool,
        typer.Option("--all", "-a", help="Query all Contexts in the active Profile"),
    ] = False,
    include_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--descendants/--context-only", help="Include lexical descendants"
        ),
    ] = None,
    direct: Annotated[
        bool, typer.Option("-d", "--direct", help="Query only the selected Context")
    ] = False,
    recursive: Annotated[
        bool, typer.Option("-r", "--recursive", help="Include lexical descendants")
    ] = False,
) -> None:
    try:
        preset = resolve_scope_preset(
            direct=direct, recursive=recursive, default=ContextScopePreset.DIRECT
        )
        traversal = resolve_context_traversal(
            preset=preset, include_descendants=include_descendants
        )
        store = MemoryStore()
        current = store.current_context_name()
        operands = tuple(context_name or ())
        if all_contexts and operands:
            raise ValueError("--all/-a cannot be combined with --context/-c.")
        if question is not None and (operands or all_contexts):
            raise ValueError("Use one question with --context/-c or --all/-a.")
        if selector is None:
            if not is_interactive_terminal():
                raise ValueError("A question is required outside a terminal.")
            if (
                len(operands) > 1
                or all_contexts
                or direct
                or recursive
                or include_descendants is not None
            ):
                raise ValueError("Choose scope in the interactive Query workbench.")
            _open_query_workbench(store, context_name=operands[0] if operands else None)
            return
        if not selector.strip() or (question is not None and not question.strip()):
            raise ValueError("Question must be non-empty.")
        if operands or all_contexts:
            names = operands
            if all_contexts:
                names = tuple(store.list_context_names())
                if not names:
                    raise ValueError("No Contexts are available for Query.")
            _query_ordinary_context(
                store,
                context_names=names,
                current_name=current,
                question=selector,
                traversal=traversal,
                all_contexts=all_contexts,
            )
            return
        selected = None
        try:
            selected = resolve_existing_context_access(
                store, selector, current_name=current
            ).value
        except (FileNotFoundError, ContextOperandNotFoundError):
            if (
                question is not None
                or is_relative_context_locator(selector)
                or is_unresolved_uid_selector(selector)
            ):
                raise
        if selected is not None:
            if question is None:
                if not is_interactive_terminal():
                    raise ValueError(
                        "QUESTION is required outside a terminal for a selected Context."
                    )
                explicit_scope = direct or recursive or include_descendants is not None
                _open_query_workbench(
                    store,
                    context_name=selected.access_name,
                    traversal=traversal if explicit_scope else None,
                )
            else:
                _query_ordinary_context(
                    store,
                    context_names=(selected.access_name,),
                    current_name=current,
                    question=question,
                    traversal=traversal,
                )
        else:
            _query_ordinary_context(
                store,
                context_names=(None,),
                current_name=current,
                question=selector,
                traversal=traversal,
            )
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Query error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1) from error
