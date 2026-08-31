"""MemoryStore composition for Lock."""

from memcommit.application.capabilities.write_protection.application import (
    WriteProtectionRequest,
    WriteProtectionResult,
)
from memcommit.application.capabilities.write_protection.runtime import (
    MemoryStoreWriteProtectionPort,
)
from memcommit.application.operations.sharing_protection.lock.application import run_lock
from memcommit.persistence.store import MemoryStore


def execute_lock(
    store: MemoryStore,
    request: WriteProtectionRequest,
) -> WriteProtectionResult:
    return run_lock(request, port=MemoryStoreWriteProtectionPort(store))


__all__ = ["execute_lock"]

