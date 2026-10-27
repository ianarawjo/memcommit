"""Publish Sync files under Store locks with ordinary exception rollback."""

import base64
from hashlib import sha256
from pathlib import PurePosixPath

from memcommit.persistence.import_export.output import write_output_files
from memcommit.persistence.import_export.source import require_regular_output_path
from memcommit.persistence.store.context_hierarchy import validate_context_hierarchy
from memcommit.persistence.store.infrastructure.atomic_io import _write_bytes_atomic


def encode_bytes(data):
    return None if data is None else base64.b64encode(data).decode("ascii")


def decode_bytes(data):
    return None if data is None else base64.b64decode(data, validate=True)


def sync_store_file_path(store, relative):
    path = PurePosixPath(relative)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {".", ".."} for part in path.parts)
    ):
        raise ValueError("Invalid Sync publication path.")
    if (
        path.parts[0] not in {"contexts", "command-context-archives", "sync"}
        and relative != "state.json"
    ):
        raise ValueError("Sync publication path is outside document state.")
    target = store.store_dir.joinpath(*path.parts)
    for parent in (target, *target.parents):
        if parent == store.store_dir:
            break
        if parent.is_symlink():
            raise ValueError("Sync publication cannot traverse symbolic links.")
    if target.exists() and not target.is_file():
        raise ValueError("Sync publication target is not a regular file.")
    return target


def publish_sync_files(store, root, publication):
    """Check all preimages, publish, and roll back this call on an Exception.

    There is deliberately no process-restart replay. The successful receipt is
    written last; it belongs to this transaction and rolls back with its files.
    """
    observed = []
    final_context_names = set(store.list_context_names())
    for relative, versions in publication["store_files"].items():
        path = sync_store_file_path(store, relative)
        before, after = map(decode_bytes, versions)
        actual = path.read_bytes() if path.exists() else None
        if actual != before:
            raise ValueError(f"Sync Store file changed before publication: {relative}")
        observed.append((path, actual, after, False))
        relative_path = PurePosixPath(relative)
        if (
            relative_path.parts[0] == "contexts"
            and relative_path.name == "context.json"
        ):
            name = "/".join(relative_path.parts[1:-1])
            if after is None:
                final_context_names.discard(name)
            else:
                final_context_names.add(name)
    # Check the complete result, not the transient order of individual writes.
    validate_context_hierarchy(final_context_names)
    for relative, versions in publication["external_files"].items():
        path = require_regular_output_path(root, relative)
        before, after = map(decode_bytes, versions)
        actual = path.read_bytes() if path.exists() else None
        if actual != before:
            raise ValueError(
                f"External file changed before Sync publication: {relative}"
            )
        observed.append((path, actual, after, True))
    observed.sort(
        key=lambda entry: entry[0].is_relative_to(store.store_dir / "sync" / "runs")
    )
    created_directories = {
        parent
        for path, _before, _after, _external in observed
        for parent in path.parents
        if not parent.exists()
    }
    written = []
    try:
        for path, before, after, external in observed:
            if before == after:
                continue
            actual = path.read_bytes() if path.exists() else None
            if actual != before:
                raise ValueError("Sync destination changed after final validation.")
            _replace_sync_file(root, path, before, after, external=external)
            written.append((path, before, after, external))
        for path, _before, after, _external in reversed(written):
            if after is not None:
                continue
            boundary = next(
                (
                    directory
                    for directory in (
                        store.command_context_archives_dir,
                        store.contexts_dir,
                    )
                    if path.is_relative_to(directory)
                ),
                None,
            )
            if boundary is None:
                continue
            parent = path.parent
            while parent != boundary:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
    except Exception:
        for path, before, after, external in reversed(written):
            actual = path.read_bytes() if path.exists() else None
            if actual != after:
                raise RuntimeError(
                    "Sync rollback found an independent file change; recovery requires inspection."
                )
            _replace_sync_file(root, path, after, before, external=external)
        for directory in sorted(
            created_directories, key=lambda path: len(path.parts), reverse=True
        ):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise


def _replace_sync_file(root, path, before, after, *, external):
    if external:
        relative = path.relative_to(root).as_posix()
        write_output_files(
            root,
            ((relative, after),) if after is not None else (),
            removals=(relative,) if after is None else (),
            expected_hashes={
                relative: sha256(before).hexdigest() if before is not None else None
            },
        )
    elif after is None:
        path.unlink(missing_ok=True)
    else:
        _write_bytes_atomic(path, after)
