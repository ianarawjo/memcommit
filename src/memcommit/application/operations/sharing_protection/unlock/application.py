"""Operation-specific Unlock application boundary."""

from memcommit.application.capabilities.write_protection.application import (
    WriteProtectionPort,
    WriteProtectionRequest,
    WriteProtectionResult,
    run_write_protection,
)


def run_unlock(
    request: WriteProtectionRequest,
    *,
    port: WriteProtectionPort,
) -> WriteProtectionResult:
    return run_write_protection(request, protected=False, port=port)


__all__ = ["run_unlock"]

