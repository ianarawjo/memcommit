"""Load one explicit instruction and Target, then plan and publish Update."""

from typing import Callable

from memcommit.persistence.store import ProfileStore
from .model import (
    UpdateError,
    UpdateReceipt,
    collect_update_inputs,
    plan_update,
)
from .model.instruction import UpdateRequest
from .model.planning import UpdateProvider
from memcommit.persistence.operations.update.publication_repository import (
    publish_update_transaction,
)


def run_instruction_update(
    store: ProfileStore,
    request: UpdateRequest,
    provider_factory: Callable[[], UpdateProvider],
) -> UpdateReceipt:
    """Freeze the current Target, plan one instruction, and publish its changes."""
    if not isinstance(request, UpdateRequest):
        raise TypeError("Update requires a typed request.")
    current_name = store.current_context_name()
    if current_name is None:
        raise UpdateError("No current Context. Run 'mem switch' or 'mem init' first.")
    target_contexts = (
        store.load_context_and_descendants(current_name)
        if request.recursive
        else (store.load_direct(current_name),)
    )
    planning_inputs = collect_update_inputs(
        (),
        target_contexts,
        instruction=request.instruction,
        target_include_descendants=request.recursive,
    )
    plan = plan_update(planning_inputs, provider_factory)
    return publish_update_transaction(
        store,
        planning_inputs.execution_inputs,
        plan,
    )
