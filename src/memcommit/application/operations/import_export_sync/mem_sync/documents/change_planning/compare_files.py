"""Classify changes against the last successful Sync agreement."""


def classify_sync_changes(projected, external, baseline, *, source_changed):
    """Classify direction without timestamps, writes or identity guesses."""
    if external == dict(baseline.files):
        return "OUTBOUND" if source_changed else "UNCHANGED"
    if projected == external:
        return "CONVERGED"
    return "CONFLICT" if source_changed else "INBOUND"
