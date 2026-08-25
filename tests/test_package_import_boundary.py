"""Fresh-process contracts for the public package and operation assembly."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


REPOSITORY = Path(__file__).parents[1]


def _run_fresh(source: str, *, environment: dict[str, str] | None = None):
    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY,
        env=environment,
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
    'memcommit.api._operations.add',
    'memcommit.api._operations.compare',
    'memcommit.api._operations.distill',
    'memcommit.api._operations.elaborate',
    'memcommit.api._operations.embed',
    'memcommit.api._operations.fit',
    'memcommit.api._operations.help',
    'memcommit.api._operations.forget',
    'memcommit.api._operations.ground_distill',
    'memcommit.api._operations.ground_elaborate',
    'memcommit.api._operations.meld',
    'memcommit.api._operations.query',
    'memcommit.api._operations.reference',
    'memcommit.api._operations.show',
    'memcommit.add_application',
    'memcommit.add_runtime',
    'memcommit.atomize_application',
    'memcommit.atomize_analysis_application',
    'memcommit.atomize_analysis_runtime',
    'memcommit.atomize_grounding_application',
    'memcommit.atomize_grounding_runtime',
    'memcommit.atomize_runtime',
    'memcommit.dedup_application',
    'memcommit.dedup_runtime',
    'memcommit.comparison_execution',
    'memcommit.distill_application',
    'memcommit.elaborate_application',
    'memcommit.embed_application',
    'memcommit.fit_application',
    'memcommit.fit_runtime',
    'memcommit.help_application',
    'memcommit.forget_application',
    'memcommit.forget_runtime',
    'memcommit.ground_distill',
    'memcommit.ground_elaborate',
    'memcommit.meld_application',
    'memcommit.meld_runtime',
    'memcommit.operations.add.application',
    'memcommit.operations.add.runtime',
    'memcommit.operations.atomize.application',
    'memcommit.operations.atomize.analysis_application',
    'memcommit.operations.atomize.analysis_runtime',
    'memcommit.operations.atomize.grounding_application',
    'memcommit.operations.atomize.grounding_runtime',
    'memcommit.operations.atomize.runtime',
    'memcommit.operations.dedup.application',
    'memcommit.operations.dedup.runtime',
    'memcommit.operations.query.ordinary_application',
    'memcommit.operations.embed.application',
    'memcommit.operations.embed.runtime',
    'memcommit.operations.fit.application',
    'memcommit.operations.fit.runtime',
    'memcommit.operations.forget.application',
    'memcommit.operations.forget.runtime',
    'memcommit.operations.meld.application',
    'memcommit.operations.meld.runtime',
    'memcommit.operations.reference.application',
    'memcommit.operations.reference.runtime',
    'memcommit.operations.sever.application',
    'memcommit.operations.sever.runtime',
    'memcommit.operations.summarize.application',
    'memcommit.operations.summarize.runtime',
    'memcommit.operations.update.application',
    'memcommit.reference_application',
    'memcommit.sever_application',
    'memcommit.sever_runtime',
    'memcommit.show_application',
    'memcommit.summarize_application',
    'memcommit.summarize_runtime',
    'memcommit.update_application',
)
assert MemCommitClient.__name__ == 'MemCommitClient'
assert not [name for name in blocked if name in sys.modules]
"""
    )

    assert completed.returncode == 0, completed.stderr


def test_private_operation_adapters_do_not_import_the_client_facade():
    completed = _run_fresh(
        """
import importlib
import sys
for name in (
    'memcommit.api._operations.add',
    'memcommit.api._operations.compare',
    'memcommit.api._operations.distill',
    'memcommit.api._operations.elaborate',
    'memcommit.api._operations.embed',
    'memcommit.api._operations.fit',
    'memcommit.api._operations.help',
    'memcommit.api._operations.forget',
    'memcommit.api._operations.ground_distill',
    'memcommit.api._operations.ground_elaborate',
    'memcommit.api._operations.meld',
    'memcommit.api._operations.query',
    'memcommit.api._operations.reference',
    'memcommit.api._operations.show',
):
    importlib.import_module(name)
assert 'memcommit.api.client' not in sys.modules
"""
    )

    assert completed.returncode == 0, completed.stderr


def test_selected_show_loads_only_its_read_operation_assembly(tmp_path):
    environment = os.environ.copy()
    environment["MEMCOMMIT_IMPORT_TEST_ROOT"] = str(tmp_path / "store")
    completed = _run_fresh(
        """
import os
from pathlib import Path
import sys
import memcommit.ops as ops
from memcommit.api import MemCommitClient
from memcommit.store import MemoryStore

root = Path(os.environ['MEMCOMMIT_IMPORT_TEST_ROOT'])
store = MemoryStore(root=root)
context = ops.init('show/import-boundary')
ops.add(context, 'visible')
store.save(context)
store.set_current(context.name)
result = MemCommitClient(root=root).show()
assert result.name == context.name
assert 'memcommit.api._operations.show' in sys.modules
assert 'memcommit.show_application' in sys.modules
assert 'memcommit.show_runtime' in sys.modules
assert 'memcommit.api._operations.add' not in sys.modules
assert 'memcommit.api._operations.query' not in sys.modules
assert 'memcommit.api._operations.compare' not in sys.modules
assert 'memcommit.api._operations.meld' not in sys.modules
assert 'memcommit.operations.query.ordinary_application' not in sys.modules
""",
        environment=environment,
    )

    assert completed.returncode == 0, completed.stderr


def test_selected_help_loads_only_catalog_discovery_and_never_the_store(tmp_path):
    environment = os.environ.copy()
    environment["MEMCOMMIT_IMPORT_TEST_ROOT"] = str(tmp_path / "missing-store")
    completed = _run_fresh(
        """
import os
from pathlib import Path
import sys
from memcommit.api import MemCommitClient

root = Path(os.environ['MEMCOMMIT_IMPORT_TEST_ROOT'])
client = MemCommitClient(root=root)
result = client.describe_operation('compare')
assert result.name == 'compare'
assert not root.exists()
assert 'memcommit.api._operations.help' in sys.modules
assert 'memcommit.help_application' in sys.modules
assert 'memcommit.api._operations.add' not in sys.modules
assert 'memcommit.api._operations.query' not in sys.modules
assert 'memcommit.api._operations.compare' not in sys.modules
assert 'memcommit.api._operations.meld' not in sys.modules
assert 'memcommit.comparison_execution' not in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.operations.meld.application' not in sys.modules
assert 'memcommit.operations.meld.runtime' not in sys.modules
""",
        environment=environment,
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
    'memcommit.elaborate',
    'memcommit.elaborate_application',
):
    importlib.import_module(name)
from memcommit.api import MemCommitClient
assert MemCommitClient.__name__ == 'MemCommitClient'
"""
    )

    assert completed.returncode == 0, completed.stderr


def test_selected_add_loads_only_its_operation_assembly(tmp_path):
    environment = os.environ.copy()
    environment["MEMCOMMIT_IMPORT_TEST_ROOT"] = str(tmp_path / "store")
    completed = _run_fresh(
        """
import os
from pathlib import Path
import sys
from memcommit.api import AddInputError, MemCommitClient
client = MemCommitClient(
    root=Path(os.environ['MEMCOMMIT_IMPORT_TEST_ROOT']),
    create=True,
)
try:
    client.add_memories('not-a-sequence')
except AddInputError:
    pass
else:
    raise AssertionError('invalid Add input unexpectedly succeeded')
assert 'memcommit.api._operations.add' in sys.modules
assert 'memcommit.operations.add.application' in sys.modules
assert 'memcommit.operations.add.runtime' in sys.modules
assert 'memcommit.add_application' not in sys.modules
assert 'memcommit.add_runtime' not in sys.modules
assert 'memcommit.api._operations.query' not in sys.modules
assert 'memcommit.api._operations.meld' not in sys.modules
assert 'memcommit.api._operations.compare' not in sys.modules
assert 'memcommit.api._operations.fit' not in sys.modules
assert 'memcommit.api._operations.distill' not in sys.modules
assert 'memcommit.api._operations.elaborate' not in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.operations.meld.application' not in sys.modules
assert 'memcommit.operations.meld.runtime' not in sys.modules
assert 'memcommit.operations.query.ordinary_application' not in sys.modules
assert 'memcommit.ground_distill' not in sys.modules
""",
        environment=environment,
    )

    assert completed.returncode == 0, completed.stderr


def test_selected_query_loads_only_its_operation_assembly(tmp_path):
    environment = os.environ.copy()
    environment["MEMCOMMIT_IMPORT_TEST_ROOT"] = str(tmp_path / "store")
    completed = _run_fresh(
        """
import os
from pathlib import Path
import sys
from memcommit.api import MemCommitClient, QueryInputError

client = MemCommitClient(
    root=Path(os.environ['MEMCOMMIT_IMPORT_TEST_ROOT']),
    create=True,
)
try:
    client.query_ordinary('Question?', context_names=())
except QueryInputError:
    pass
else:
    raise AssertionError('invalid Query target set unexpectedly succeeded')
assert 'memcommit.api._operations.query' in sys.modules
assert 'memcommit.operations.query.ordinary_application' in sys.modules
assert 'memcommit.api._operations.add' not in sys.modules
assert 'memcommit.operations.add.application' not in sys.modules
assert 'memcommit.operations.add.runtime' not in sys.modules
assert 'memcommit.add_application' not in sys.modules
assert 'memcommit.add_runtime' not in sys.modules
assert 'memcommit.api._operations.meld' not in sys.modules
assert 'memcommit.api._operations.compare' not in sys.modules
assert 'memcommit.api._operations.fit' not in sys.modules
assert 'memcommit.api._operations.distill' not in sys.modules
assert 'memcommit.api._operations.elaborate' not in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.operations.meld.application' not in sys.modules
assert 'memcommit.operations.meld.runtime' not in sys.modules
""",
        environment=environment,
    )

    assert completed.returncode == 0, completed.stderr


def test_selected_meld_loads_only_its_operation_assembly(tmp_path):
    environment = os.environ.copy()
    environment["MEMCOMMIT_IMPORT_TEST_ROOT"] = str(tmp_path / "store")
    completed = _run_fresh(
        """
import os
from pathlib import Path
import sys
from memcommit.api import MeldContextError, MemCommitClient

client = MemCommitClient(
    root=Path(os.environ['MEMCOMMIT_IMPORT_TEST_ROOT']),
    create=True,
)
try:
    client.open_meld('missing')
except MeldContextError:
    pass
else:
    raise AssertionError('missing Meld target unexpectedly opened')
assert 'memcommit.api._operations.meld' in sys.modules
assert 'memcommit.operations.meld.application' in sys.modules
assert 'memcommit.operations.meld.runtime' in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.api._operations.add' not in sys.modules
assert 'memcommit.operations.add.application' not in sys.modules
assert 'memcommit.operations.add.runtime' not in sys.modules
assert 'memcommit.add_application' not in sys.modules
assert 'memcommit.add_runtime' not in sys.modules
assert 'memcommit.api._operations.query' not in sys.modules
assert 'memcommit.operations.query.ordinary_application' not in sys.modules
""",
        environment=environment,
    )

    assert completed.returncode == 0, completed.stderr


def test_selected_compare_loads_only_its_operation_assembly(tmp_path):
    environment = os.environ.copy()
    environment["MEMCOMMIT_IMPORT_TEST_ROOT"] = str(tmp_path / "store")
    completed = _run_fresh(
        """
import os
from pathlib import Path
import sys
from memcommit.api import CompareContextError, MemCommitClient

client = MemCommitClient(
    root=Path(os.environ['MEMCOMMIT_IMPORT_TEST_ROOT']),
    create=True,
)
try:
    client.open_comparison('00000000-0000-0000-0000-000000000001')
except CompareContextError:
    pass
else:
    raise AssertionError('missing Compare analysis unexpectedly opened')
assert 'memcommit.api._operations.compare' in sys.modules
assert 'memcommit.comparison_execution' in sys.modules
assert 'memcommit.api._operations.add' not in sys.modules
assert 'memcommit.operations.add.application' not in sys.modules
assert 'memcommit.operations.add.runtime' not in sys.modules
assert 'memcommit.add_application' not in sys.modules
assert 'memcommit.add_runtime' not in sys.modules
assert 'memcommit.api._operations.query' not in sys.modules
assert 'memcommit.operations.query.ordinary_application' not in sys.modules
assert 'memcommit.api._operations.meld' not in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.operations.meld.application' not in sys.modules
assert 'memcommit.operations.meld.runtime' not in sys.modules
""",
        environment=environment,
    )

    assert completed.returncode == 0, completed.stderr


def test_selected_forget_loads_only_its_operation_assembly(tmp_path):
    environment = os.environ.copy()
    environment["MEMCOMMIT_IMPORT_TEST_ROOT"] = str(tmp_path / "store")
    completed = _run_fresh(
        """
import os
from pathlib import Path
import sys
from memcommit.api import ForgetContextError, MemCommitClient

client = MemCommitClient(
    root=Path(os.environ['MEMCOMMIT_IMPORT_TEST_ROOT']),
    create=True,
)
try:
    client.analyze_forget('Forget the obsolete detail.', context_name='missing')
except ForgetContextError:
    pass
else:
    raise AssertionError('missing Forget Source unexpectedly analyzed')
assert 'memcommit.api._operations.forget' in sys.modules
assert 'memcommit.operations.forget.application' in sys.modules
assert 'memcommit.operations.forget.runtime' in sys.modules
assert 'memcommit.forget_application' not in sys.modules
assert 'memcommit.forget_runtime' not in sys.modules
assert 'memcommit.api._operations.add' not in sys.modules
assert 'memcommit.operations.add.application' not in sys.modules
assert 'memcommit.operations.add.runtime' not in sys.modules
assert 'memcommit.add_application' not in sys.modules
assert 'memcommit.add_runtime' not in sys.modules
assert 'memcommit.api._operations.query' not in sys.modules
assert 'memcommit.operations.query.ordinary_application' not in sys.modules
assert 'memcommit.api._operations.meld' not in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.operations.meld.application' not in sys.modules
assert 'memcommit.operations.meld.runtime' not in sys.modules
assert 'memcommit.api._operations.update' not in sys.modules
assert 'memcommit.update_planning_application' not in sys.modules
""",
        environment=environment,
    )

    assert completed.returncode == 0, completed.stderr


def test_selected_fit_loads_no_context_or_ground_operation(tmp_path):
    environment = os.environ.copy()
    environment["MEMCOMMIT_IMPORT_TEST_ROOT"] = str(tmp_path / "store")
    completed = _run_fresh(
        """
import os
from pathlib import Path
import sys
from memcommit.api import MemCommitClient, SemanticInputError

client = MemCommitClient(
    root=Path(os.environ['MEMCOMMIT_IMPORT_TEST_ROOT']),
    create=True,
)
try:
    client.fit(())
except SemanticInputError:
    pass
else:
    raise AssertionError('empty Fit unexpectedly succeeded')
assert 'memcommit.api._operations.fit' in sys.modules
assert 'memcommit.operations.fit.application' in sys.modules
assert 'memcommit.operations.fit.runtime' in sys.modules
assert 'memcommit.fit_application' not in sys.modules
assert 'memcommit.fit_runtime' not in sys.modules
assert 'memcommit.api._operations.distill' not in sys.modules
assert 'memcommit.api._operations.elaborate' not in sys.modules
assert 'memcommit.api._operations.ground_distill' not in sys.modules
assert 'memcommit.api._operations.ground_elaborate' not in sys.modules
assert 'memcommit.ground_distill' not in sys.modules
assert 'memcommit.ground_elaborate' not in sys.modules
""",
        environment=environment,
    )

    assert completed.returncode == 0, completed.stderr


def test_selected_standalone_elaborate_does_not_load_ground(tmp_path):
    environment = os.environ.copy()
    environment["MEMCOMMIT_IMPORT_TEST_ROOT"] = str(tmp_path / "store")
    completed = _run_fresh(
        """
import json
import os
from pathlib import Path
import sys
from memcommit.api import MemCommitClient

class Provider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == 'elaborate'
        return json.dumps({
            'overview': 'One Rule makes the Goal reviewable.',
            'rules': [{
                'content': 'Confirm the option before acting.',
                'rationale': 'This operationalizes the Goal.',
            }],
        })

client = MemCommitClient(
    root=Path(os.environ['MEMCOMMIT_IMPORT_TEST_ROOT']),
    create=True,
    semantic_provider_factory=Provider,
)
result = client.elaborate(goal='Confirm before acting.', number=1)
assert result.rules[0].content == 'Confirm the option before acting.'
assert 'memcommit.api._operations.elaborate' in sys.modules
assert 'memcommit.elaborate_application' in sys.modules
assert 'memcommit.api._operations.ground_elaborate' not in sys.modules
assert 'memcommit.api._operations.ground_distill' not in sys.modules
assert 'memcommit.ground_elaborate' not in sys.modules
assert 'memcommit.ground_distill' not in sys.modules
assert 'memcommit.distill_application' not in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.operations.meld.application' not in sys.modules
assert 'memcommit.operations.meld.runtime' not in sys.modules
""",
        environment=environment,
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
