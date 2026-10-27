"""Create initial native Context records for an unpublished project Store."""

from .native_documents import decode_context


def import_context_records(destination, entries, *, make_current=None):
    """Publish validated native records; callers own project setup and receipts."""
    entries = tuple(entries)
    contexts = tuple(decode_context(context.to_dict()) for context, _ in entries)
    if len({context.name for context in contexts}) != len(contexts) or len(
        {context.uid for context in contexts}
    ) != len(contexts):
        raise ValueError("Native Context input repeats a name or identity.")
    existing_uids = {
        destination.load_direct(name).uid
        for name in destination.list_context_names()
    }
    if existing_uids.intersection(context.uid for context in contexts):
        raise ValueError("Native Context identity already exists in this Store.")
    return destination.create_missing_contexts(
        tuple(
            (context, entry[1])
            for context, entry in zip(contexts, entries, strict=True)
        ),
        require_all_new=True,
        make_current=make_current,
    )
