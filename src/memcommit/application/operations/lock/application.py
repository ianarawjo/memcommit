"""Operation-specific Lock application boundary."""

from memcommit.application.capabilities.write_protection.application import (
    WriteProtectionPort,
    WriteProtectionRequest,
    WriteProtectionResult,
    run_write_protection,
)


def run_lock(
    request: WriteProtectionRequest,
    *,
    port: WriteProtectionPort,
) -> WriteProtectionResult:
    return run_write_protection(request, protected=True, port=port)


__all__ = ["run_lock"]

