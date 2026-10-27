"""Use one Profile-relative namespace for documents and lexical directories."""

from memcommit.application.operations.import_export_sync.common.conversion import (
    render_context_documents,
)
from memcommit.application.operations.import_export_sync.common.model import MemContent


def context_document_is_excluded(context, rules):
    state = context.corresponding_document_metadata
    path = state.path if state else context.name + ".md"
    return rules.excludes(context.name) or rules.excludes(
        path, directory=bool(state and state.role == "directory")
    )


def prepare_sync_document_units(content: MemContent):
    units = []
    for context in content.contexts:
        state = context.corresponding_document_metadata
        directories = (state.path,) if state and state.role == "directory" else ()
        files = render_context_documents(MemContent((context,), content.attached_data))
        units.append((context, (context.name,), files, directories))
    return tuple(units)
