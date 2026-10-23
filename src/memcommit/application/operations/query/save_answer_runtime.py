"""MemoryStore binding for saving a completed Query answer."""

from __future__ import annotations

import uuid

from memcommit.application.operations.query.save_answer import (
    SaveQueryAnswerError,
    SaveQueryAnswerPort,
    SaveQueryAnswerRequest,
    SaveQueryAnswerResult,
    save_query_answer,
)
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.core.context_name_validation import validate_context_name
from memcommit.persistence.store import MemoryStore


class MemoryStoreSaveQueryAnswerPort(SaveQueryAnswerPort):
    """Create one require-new local Context from already disclosed output."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def save(self, request: SaveQueryAnswerRequest) -> SaveQueryAnswerResult:
        validate_context_name(request.destination_name)
        self._store.assert_context_creatable(request.destination_name)

        response = request.response
        answer = Memory(uid=str(uuid.uuid4()), content=response.answer)
        output = Context(uid=str(uuid.uuid4()), name=request.destination_name)
        output.add(answer)
        source = {
            "kind": "READABLE_CONTEXTS",
            "target_names": list(response.request.target_names),
            "grounded": response.grounded,
        }
        question = response.request.question
        checkpoint = AutoCheckpointRequest(
            command="query",
            command_details={
                "context_creation": {
                    "version": 1,
                    "context_uid": output.uid,
                    "context_name": output.name,
                },
                "save_query_answer": {
                    "version": 1,
                    "question": question,
                    "source": source,
                    "answer_memory_uid": answer.uid,
                    "output": output.name,
                },
            },
        )
        created_checkpoint = self._store.create_context(output, checkpoint)
        if created_checkpoint is None:
            raise SaveQueryAnswerError(
                "No checkpoint was returned when saving the Query answer."
            )
        return SaveQueryAnswerResult(
            context_name=output.name,
            context_uid=output.uid,
            checkpoint_uid=created_checkpoint.uid,
            memory_uid=answer.uid,
        )


def execute_save_query_answer(
    request: SaveQueryAnswerRequest,
    *,
    store: MemoryStore,
) -> SaveQueryAnswerResult:
    return save_query_answer(
        request,
        port=MemoryStoreSaveQueryAnswerPort(store),
    )


__all__ = ["MemoryStoreSaveQueryAnswerPort", "execute_save_query_answer"]
