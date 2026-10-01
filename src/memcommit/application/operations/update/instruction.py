"""Load one explicit instruction and Target, then plan and publish Update."""

from dataclasses import dataclass
from typing import Callable

from memcommit.application.authorization import ContextUse, authorize_context_use
from memcommit.application.capabilities.memory_report_targeting import (
    freeze_memory_report_readable_catalog,
    resolve_readable_memory_target,
)
from memcommit.application.context_access.access import (
    ContextAccess,
    GrantedReadStore,
    freeze_granted_context_binding,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.core.context import Context, Memory
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator
from memcommit.core.context_targeting.uid_locator import resolve_exact_or_unique_uid
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
from .publication import publish_update


@dataclass(frozen=True)
class PreparedInstructionUpdate:
    inputs: UpdateContextInputs
    source: Context
    target: Context
    allowed_target_uses: frozenset[ContextUse]


def _load(access: ContextAccess, store: MemoryStore) -> Context:
    reader = GrantedReadStore(access) if access.is_granted else store
    name = access.access_name if access.is_granted else access.context_name
    return reader.load_direct(name)


def _load_instruction_memory(
    store: MemoryStore,
    operand: str,
    *,
    current_name: str | None,
) -> tuple[Context, Memory, ContextAccess]:
    locator = parse_direct_memory_locator(operand)
    if locator.context_locator is not None:
        access = resolve_existing_context_access(
            store,
            locator.context_locator,
            current_name=current_name,
            required_permission="READ",
        ).value
    else:
        catalog = freeze_memory_report_readable_catalog(store, current=current_name)
        if catalog is None:
            raise UpdateError("No readable Memory is available for --memory.")
        selected = resolve_readable_memory_target(catalog, locator.memory_selector)
        access = selected.access
    authorize_context_use(access, ContextUse.READ)
    source = _load(access, store)
    memory = resolve_exact_or_unique_uid(
        (item for item in source.iter_items() if isinstance(item, Memory)),
        locator.memory_selector,
        uid=lambda item: item.uid,
        label="Instruction Memory",
    )
    return source, memory, access


def prepare_instruction_update(
    store: MemoryStore, request: UpdateRequest
) -> PreparedInstructionUpdate:
    if not isinstance(request, UpdateRequest):
        raise TypeError("Update requires a typed request.")
    # Relative input and Target locators share one current-Context snapshot.
    current_name = store.current_context_name()
    target_name = request.target if request.target is not None else current_name
    if target_name is None:
        raise UpdateError("No current Target Context. Supply --to CONTEXT.")
    target_access = resolve_existing_context_access(
        store,
        target_name,
        current_name=current_name,
        required_permission="READ",
    ).value
    target_authorization = authorize_context_use(target_access, ContextUse.READ)
    target = _load(target_access, store)
    source_access = None
    source_memory_uid = None
    if request.memory is not None:
        source, memory, source_access = _load_instruction_memory(
            store,
            request.memory,
            current_name=current_name,
        )
        # Compare identities, not public spelling: another Grant alias must not
        # make a Memory inside the Target look like an independent instruction.
        if source.uid == target.uid:
            raise UpdateError(
                "--memory must select a Memory outside the Target Context."
            )
        instruction = UpdateInstruction(memory.content)
        source_memory_uid = memory.uid
    else:
        instruction = UpdateInstruction(request.instruction)
        # The existing planner uses a process-local alias frame for provenance.
        # It is never saved as a Context or presented as a stored Memory.
        source = inline_update_context(instruction.text)
    inputs = freeze_update_context_inputs(
        source,
        target,
        source_memory_selector=source_memory_uid,
        inline_source_content=instruction.text if request.memory is None else None,
        granted_source=freeze_granted_context_binding(source_access)
        if source_access is not None and source_access.is_granted
        else None,
        granted_target=freeze_granted_context_binding(target_access)
        if target_access.is_granted
        else None,
        instruction=instruction,
    )
    return PreparedInstructionUpdate(
        inputs, source, target, target_authorization.allowed
    )


def run_instruction_update(
    store: MemoryStore,
    request: UpdateRequest,
    provider_factory: Callable[[], UpdateProvider],
) -> UpdateReceipt:
    prepared = prepare_instruction_update(store, request)
    inputs = prepared.inputs
    plan = plan_update(
        prepared.source,
        prepared.target,
        provider_factory,
        source_memory_selector=inputs.source_memory_uid,
        inline_source_content=inputs.inline_source_content,
        granted_source=inputs.granted_source,
        granted_target=inputs.granted_target,
        allowed_target_uses=prepared.allowed_target_uses,
        instruction=inputs.instruction,
    )
    return publish_update(store, inputs, plan)
