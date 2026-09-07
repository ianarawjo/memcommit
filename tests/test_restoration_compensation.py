"""A failed inverse does not abandon the remaining restoration records."""

import pytest

from memcommit.persistence.store.command_restoration.compensation import (
    CompensationStack,
    RestorationRollbackError,
)


def test_compensation_continues_after_failed_inverse_and_keeps_original_error(tmp_path):
    source = tmp_path / "context.json"
    archive = tmp_path / "archived-context.json"
    source.write_text("retained context")
    execution_error = OSError("execution failed")
    inverse_error = OSError("workbench restoration failed")

    def fail_inverse():
        raise inverse_error

    with pytest.raises(RestorationRollbackError) as caught:
        with CompensationStack() as compensation:
            compensation.move(source, archive)
            compensation.defer(fail_inverse)
            raise execution_error

    assert source.read_text() == "retained context"
    assert not archive.exists()
    assert caught.value.failures == (inverse_error,)
    assert caught.value.__cause__ is execution_error
