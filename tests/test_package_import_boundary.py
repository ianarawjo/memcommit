"""Fresh-process contracts for the public package and operation assembly."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPOSITORY = Path(__file__).parents[1]


def _run_fresh(source: str):
    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )


def test_root_import_does_not_assemble_public_client_or_api():
    completed = _run_fresh(
        """
import sys
import memcommit
assert 'memcommit.api' not in sys.modules
assert 'memcommit.api.client' not in sys.modules
assert memcommit.MemoryStore.__module__ == 'memcommit.store'
assert 'MemCommitClient' in dir(memcommit)
assert 'memcommit.api' not in sys.modules
"""
    )

    assert completed.returncode == 0, completed.stderr


def test_public_client_import_does_not_assemble_operation_implementations():
    completed = _run_fresh(
        """
import sys
from memcommit.api import MemCommitClient
blocked = (
    'memcommit.add_application',
    'memcommit.meld_application',
    'memcommit.operations.query.ordinary_application',
)
assert MemCommitClient.__name__ == 'MemCommitClient'
assert not [name for name in blocked if name in sys.modules]
"""
    )

    assert completed.returncode == 0, completed.stderr


def test_internal_standalone_modules_remain_importable_without_ground():
    completed = _run_fresh(
        """
import importlib
import importlib.abc
import sys

class NoGround(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'memcommit.ground' or fullname.startswith('memcommit.ground_'):
            raise ImportError(f'blocked Ground integration: {fullname}')
        return None

sys.meta_path.insert(0, NoGround())
for name in (
    'memcommit.atomize',
    'memcommit.update',
    'memcommit.distill',
    'memcommit.distill_application',
):
    importlib.import_module(name)
from memcommit.api import MemCommitClient
assert MemCommitClient.__name__ == 'MemCommitClient'
"""
    )

    assert completed.returncode == 0, completed.stderr


def test_selecting_add_loads_add_without_query_or_meld(tmp_path):
    completed = _run_fresh(
        f"""
import sys
from memcommit.api import AddInputError, MemCommitClient
client = MemCommitClient(root={str(tmp_path / 'store')!r}, create=True)
try:
    client.add_memories('not-a-sequence')
except AddInputError:
    pass
else:
    raise AssertionError('invalid Add input unexpectedly succeeded')
assert 'memcommit.add_application' in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.operations.query.ordinary_application' not in sys.modules
assert 'memcommit.ground_distill' not in sys.modules
"""
    )

    assert completed.returncode == 0, completed.stderr


def test_root_and_api_lazy_exports_preserve_real_object_identity():
    completed = _run_fresh(
        """
import memcommit
import memcommit.api as api
assert memcommit.MemCommitClient is api.MemCommitClient
assert set(memcommit.__all__) <= set(dir(memcommit))
assert set(api.__all__) <= set(dir(api))
"""
    )

    assert completed.returncode == 0, completed.stderr
