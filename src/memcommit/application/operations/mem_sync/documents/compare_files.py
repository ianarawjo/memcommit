"""Three-way outbound comparison; external changes are never silently overwritten."""

from hashlib import sha256


def compare_sync_files(projected, external, baseline=None, interrupted=None):
    previous = dict(baseline.files) if baseline else None
    conflicts = []
    for path in set(projected) | set(external) | set(previous or {}):
        wanted, actual = projected.get(path), external.get(path)
        if wanted == actual:
            continue
        if interrupted and path in interrupted:
            before, after = interrupted[path]
            digest = sha256(actual).hexdigest() if actual is not None else None
            if digest not in {before, after}:
                conflicts.append(path)
            continue
        if previous is not None and actual != previous.get(path):
            conflicts.append(path)
    if conflicts:
        raise ValueError(
            "External Sync changes conflict; keep the files and resolve before retrying: "
            + ", ".join(sorted(conflicts))
        )
    return tuple(
        sorted(
            path
            for path in external
            if path not in projected and external[path] is not None
        )
    )
