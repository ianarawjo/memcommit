"""Combine loaded Contexts with their retained asset bytes."""

from memcommit.persistence.store.attached_files import read_attached_file
from .model import MemContent


def load_context_documents(store, contexts):
    attached = {
        asset.sha256: read_attached_file(store.store_dir, asset.sha256)
        for context in contexts
        for asset in context.asset_metadata
    }
    return MemContent(contexts, attached)
