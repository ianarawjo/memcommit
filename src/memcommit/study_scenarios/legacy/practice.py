"""Native Context data for the preserved participant-only Practice task."""

from memcommit.application.operations.resource_import.documents.codec import (
    read_document,
)
from memcommit.core.context import Context, Memory

from .fixtures import default_fixture_root


def load_practice_contexts() -> tuple[Context, ...]:
    contexts = []
    for name in ("practice", "practice/description", "practice/source"):
        path = default_fixture_root() / "native" / "practice" / name / "context.json"
        context = read_document(path).value
        if not isinstance(context, Context) or context.name != name:
            raise ValueError("Legacy Practice Context placement changed.")
        if any(not isinstance(item, Memory) for item in context.iter_items()):
            raise ValueError("Legacy Practice input must contain owned Memories.")
        contexts.append(context)
    return tuple(contexts)
