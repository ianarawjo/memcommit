"""Load one explicit instruction and Target, then plan and publish Update."""

from dataclasses import dataclass
from typing import Callable

from memcommit.models.context import Context
from memcommit.persistence.store import MemoryStore
from .model import (
    UpdateContextInputs,
    UpdateError,
    UpdateReceipt,
    freeze_update_context_inputs,
    inline_update_context,
    plan_update,
)
from .model.instruction import UpdateInstruction, UpdateRequest
from .model.planning import UpdateProvider
from memcommit.persistence.operations.update.publication_repository import (
    publish_update_transaction,
)


@dataclass(frozen=True)
class PreparedInstructionUpdate:
    inputs: UpdateContextInputs
    source_contexts: tuple[Context, ...]
    target_contexts: tuple[Context, ...]


def prepare_instruction_update(
    store: MemoryStore, request: UpdateRequest
) -> PreparedInstructionUpdate:
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
    instruction = UpdateInstruction(request.instruction)
    source = inline_update_context(instruction.text)
    source_contexts = (source,)
    inputs = freeze_update_context_inputs(
        source_contexts,
        target_contexts,
        inline_source_content=instruction.text,
        instruction=instruction,
        target_include_descendants=request.recursive,
    )
    return PreparedInstructionUpdate(
        inputs=inputs,
        source_contexts=source_contexts,
        target_contexts=target_contexts,
    )


def run_instruction_update(
    store: MemoryStore,
    request: UpdateRequest,
    provider_factory: Callable[[], UpdateProvider],
) -> UpdateReceipt:
    prepared = prepare_instruction_update(store, request)
    inputs = prepared.inputs
    plan = plan_update(
        prepared.source_contexts,
        prepared.target_contexts,
        provider_factory,
        source_memory_selector=inputs.source_memory_uid,
        inline_source_content=inputs.inline_source_content,
        instruction=inputs.instruction,
        target_include_descendants=inputs.target_include_descendants,
    )
    return publish_update_transaction(
        store,
        inputs,
        plan,
    )
