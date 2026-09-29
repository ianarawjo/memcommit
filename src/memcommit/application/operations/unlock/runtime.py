"""MemoryStore composition for Unlock."""

from memcommit.application.capabilities.write_protection.application import (
    WriteProtectionRequest,
    WriteProtectionResult,
)
from memcommit.application.capabilities.write_protection.runtime import (
    MemoryStoreWriteProtectionPort,
)
from memcommit.application.operations.unlock.application import run_unlock
from memcommit.persistence.store import MemoryStore


def execute_unlock(
    store: MemoryStore,
    request: WriteProtectionRequest,
) -> WriteProtectionResult:
    return run_unlock(request, port=MemoryStoreWriteProtectionPort(store))


__all__ = ["execute_unlock"]

