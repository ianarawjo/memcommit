"""Three-way outbound comparison; external changes are never silently overwritten."""


def classify_sync_changes(projected, external, baseline, *, source_changed):
    """Classify direction without timestamps, writes or identity guesses."""
    if external == dict(baseline.files):
        return "OUTBOUND" if source_changed else "UNCHANGED"
    if projected == external:
        return "CONVERGED"
    return "CONFLICT" if source_changed else "INBOUND"


def compare_sync_files(projected, external, baseline=None):
    previous = dict(baseline.files) if baseline else None
    conflicts = []
    for path in set(projected) | set(external) | set(previous or {}):
        wanted, actual = projected.get(path), external.get(path)
        if wanted == actual:
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
