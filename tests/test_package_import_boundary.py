"""Fresh-process contracts for the public package and operation assembly."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tomllib


REPOSITORY = Path(__file__).parents[1]


def test_repository_requires_an_installed_src_layout():
    metadata = tomllib.loads(
        (REPOSITORY / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert not (REPOSITORY / "memcommit").exists()
    assert (REPOSITORY / "src" / "memcommit" / "__init__.py").is_file()
    assert metadata["tool"]["setuptools"]["package-dir"] == {"": "src"}
    assert metadata["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    uninstalled = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            (
                "import importlib.util; "
                "assert importlib.util.find_spec('memcommit') is None"
            ),
        ],
        cwd=REPOSITORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert uninstalled.returncode == 0, uninstalled.stderr


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
assert 'memcommit.adapters.python_api' not in sys.modules
assert 'memcommit.adapters.python_api.client' not in sys.modules
assert memcommit.MemoryStore.__module__ == 'memcommit.persistence.store'
assert 'MemCommitClient' in dir(memcommit)
assert 'memcommit.adapters.python_api' not in sys.modules
"""
    )

    assert completed.returncode == 0, completed.stderr


def test_one_agent_operation_import_does_not_assemble_registry_or_siblings():
    completed = _run_fresh(
        """
import sys
import memcommit.adapters.agent.add
assert 'memcommit.adapters.agent.registry' not in sys.modules
assert 'memcommit.adapters.agent.query' not in sys.modules
assert 'memcommit.adapters.agent.atomize' not in sys.modules
"""
    )

    assert completed.returncode == 0, completed.stderr


def test_public_client_import_does_not_assemble_operation_implementations():
    completed = _run_fresh(
        """
import sys
from memcommit.adapters.python_api import MemCommitClient
blocked = (
    'memcommit.adapters.python_api._operations.add',
    'memcommit.adapters.python_api._operations.compare',
    'memcommit.adapters.python_api._operations.distill',
    'memcommit.adapters.python_api._operations.makemore',
    'memcommit.adapters.python_api._operations.embed',
    'memcommit.adapters.python_api._operations.fit',
    'memcommit.adapters.python_api._operations.help',
    'memcommit.adapters.python_api._operations.forget',
    'memcommit.adapters.python_api._operations.ground_distill',
    'memcommit.adapters.python_api._operations.ground_makemore',
    'memcommit.adapters.python_api._operations.meld',
    'memcommit.adapters.python_api._operations.query',
    'memcommit.adapters.python_api._operations.reference',
    'memcommit.adapters.python_api._operations.show',
    'memcommit.add_application',
    'memcommit.add_runtime',
    'memcommit.atomize_application',
    'memcommit.atomize_analysis_application',
    'memcommit.atomize_analysis_runtime',
    'memcommit.atomize_runtime',
    'memcommit.atomize',
    'memcommit.atomize_normal_form',
    'memcommit.atomize_resolution_adapter',
    'memcommit.atomize_result_adapter',
    'memcommit.atomize_workbench',
    'memcommit.dedup_application',
    'memcommit.dedup_runtime',
    'memcommit.exact_dedup',
    'memcommit.exact_dedup_application',
    'memcommit.comparison_execution',
    'memcommit.comparison_summary',
    'memcommit.comparison_summary_application',
    'memcommit.comparison_summary_provider',
    'memcommit.comparison_summary_rules',
    'memcommit.distill_application',
    'memcommit.distill_runtime',
    'memcommit.makemore_application',
    'memcommit.makemore_runtime',
    'memcommit.makemore_add_runtime',
    'memcommit.embed_application',
    'memcommit.fit_application',
    'memcommit.fit_runtime',
    'memcommit.fit',
    'memcommit.fit_coherence',
    'memcommit.fit_judgment',
    'memcommit.fit_store',
    'memcommit.find_application',
    'memcommit.find_runtime',
    'memcommit.find_materialization_application',
    'memcommit.find_materialization_runtime',
    'memcommit.help_application',
    'memcommit.help_lookup_application',
    'memcommit.forget_application',
    'memcommit.forget_runtime',
    'memcommit.ground_distill',
    'memcommit.ground_makemore',
    'memcommit.meld_application',
    'memcommit.meld_runtime',
    'memcommit.meld_application_flow',
    'memcommit.meld_assessment_application',
    'memcommit.meld_resolution_application',
    'memcommit.meld_restart_application',
    'memcommit.meld_session_application',
    'memcommit.meld_start_application',
    'memcommit.query_application',
    'memcommit.query_runtime',
    'memcommit.granted_query_application',
    'memcommit.granted_query_runtime',
    'memcommit.query_reference_application',
    'memcommit.query_reference_runtime',
    'memcommit.review_report',
    'memcommit.sever',
    'memcommit.sever_provider',
    'memcommit.sever_resolution_adapter',
    'memcommit.sever_store',
    'memcommit.translate',
    'memcommit.translation_view',
    'memcommit.translation_view_store',
    'memcommit.literal_find_application',
    'memcommit.literal_find_runtime',
    'memcommit.application.operations.add.application',
    'memcommit.application.operations.add.runtime',
    'memcommit.application.operations.atomize.application',
    'memcommit.application.operations.atomize.analysis_application',
    'memcommit.application.operations.atomize.analysis_runtime',
    'memcommit.application.operations.atomize.grounding_application',
    'memcommit.application.operations.atomize.grounding_runtime',
    'memcommit.application.operations.atomize.runtime',
    'memcommit.application.operations.atomize.domain',
    'memcommit.application.operations.atomize.grounding',
    'memcommit.application.operations.atomize.grounding_meld_adapter',
    'memcommit.application.operations.atomize.grounding_provider',
    'memcommit.application.operations.atomize.normal_form',
    'memcommit.application.operations.atomize.resolution_adapter',
    'memcommit.application.operations.atomize.result_adapter',
    'memcommit.application.operations.atomize.records',
    'memcommit.application.operations.chunk.application',
    'memcommit.application.operations.chunk.domain',
    'memcommit.application.operations.chunk.runtime',
    'memcommit.application.operations.clear.application',
    'memcommit.application.operations.clear.runtime',
    'memcommit.application.operations.compare.compare_summary',
    'memcommit.application.operations.compare.application',
    'memcommit.application.operations.compare.provider_contract',
    'memcommit.application.operations.compare.compare_rules',
    'memcommit.application.operations.dedun.application',
    'memcommit.application.operations.dedun.runtime',
    'memcommit.application.operations.dedup.application',
    'memcommit.application.operations.distill.application',
    'memcommit.application.operations.distill.runtime',
    'memcommit.application.operations.makemore.application',
    'memcommit.application.operations.makemore.runtime',
    'memcommit.application.operations.makemore.add_runtime',
    'memcommit.application.operations.contexts.application',
    'memcommit.application.operations.contexts.runtime',
    'memcommit.application.operations.query.ordinary_application',
    'memcommit.application.operations.embed.application',
    'memcommit.application.operations.embed.runtime',
    'memcommit.application.operations.fit.application',
    'memcommit.application.operations.fit.runtime',
    'memcommit.application.operations.fit.coherence',
    'memcommit.application.operations.fit.ground_report',
    'memcommit.application.operations.fit.store',
    'memcommit.application.operations.forget.application',
    'memcommit.application.operations.forget.runtime',
    'memcommit.application.operations.find.application',
    'memcommit.application.operations.find.runtime',
    'memcommit.application.operations.meld.apply',
    'memcommit.application.operations.meld.runtime',
    'memcommit.application.operations.meld.application',
    'memcommit.application.operations.meld.planning',
    'memcommit.application.operations.meld.proposal_iteration',
    'memcommit.application.operations.meld.preparation',
    'memcommit.application.operations.help.application',
    'memcommit.application.operations.help.lookup_application',
    'memcommit.application.operations.query.granted_application',
    'memcommit.application.operations.query.granted_runtime',
    'memcommit.application.operations.query.ordinary_runtime',
    'memcommit.application.operations.query.reference_application',
    'memcommit.application.operations.query.reference_runtime',
    'memcommit.application.operations.redo.runtime',
    'memcommit.application.operations.reference.application',
    'memcommit.application.operations.revert.application',
    'memcommit.application.operations.revert.runtime',
    'memcommit.application.operations.reference.runtime',
    'memcommit.application.operations.sever.application',
    'memcommit.application.operations.sever.runtime',
    'memcommit.application.operations.sever.model',
    'memcommit.application.operations.sever.provider',
    'memcommit.application.operations.sever.resolution_adapter',
    'memcommit.application.operations.sever.session_store',
    'memcommit.application.operations.show.application',
    'memcommit.application.operations.show.runtime',
    'memcommit.application.operations.search.application',
    'memcommit.application.operations.search.runtime',
    'memcommit.application.operations.search.save_context',
    'memcommit.application.capabilities.save_context_from_selection.application',
    'memcommit.application.capabilities.save_context_from_selection.runtime',
    'memcommit.application.operations.summarize.application',
    'memcommit.application.operations.summarize.runtime',
    'memcommit.application.operations.update.materialization',
    'memcommit.application.operations.undo.runtime',
    'memcommit.application.operations.translate.runtime',
    'memcommit.application.operations.translate.application',
    'memcommit.application.operations.translate.catalog_application',
    'memcommit.application.operations.translate.materialization',
    'memcommit.application.operations.translate.view',
    'memcommit.application.operations.translate.view_store',
    'memcommit.application.operations.trace.application',
    'memcommit.application.operations.trace.runtime',
    'memcommit.application.capabilities.history.query.context_history_slicing',
    'memcommit.application.operations.trace.granted_view',
    'memcommit.application.operations.trace.reference_lineage',
    'memcommit.application.capabilities.history.reconstruction.history_graph_reconstruction',
    'memcommit.application.capabilities.history.model.topology',
    'memcommit.application.capabilities.history.reconstruction.memory_history_reconstruction',
    'memcommit.application.capabilities.history.query.memory_history_slicing',
    'memcommit.application.capabilities.reviewing.report',
    'memcommit.reference_application',
    'memcommit.sever_application',
    'memcommit.sever_runtime',
    'memcommit.show_application',
    'memcommit.show_runtime',
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
    'memcommit.adapters.python_api._operations.add',
    'memcommit.adapters.python_api._operations.compare',
    'memcommit.adapters.python_api._operations.distill',
    'memcommit.adapters.python_api._operations.makemore',
    'memcommit.adapters.python_api._operations.embed',
    'memcommit.adapters.python_api._operations.fit',
    'memcommit.adapters.python_api._operations.help',
    'memcommit.adapters.python_api._operations.forget',
    'memcommit.adapters.python_api._operations.ground_distill',
    'memcommit.adapters.python_api._operations.ground_makemore',
    'memcommit.adapters.python_api._operations.meld',
    'memcommit.adapters.python_api._operations.query',
    'memcommit.adapters.python_api._operations.reference',
    'memcommit.adapters.python_api._operations.show',
):
    importlib.import_module(name)
assert 'memcommit.adapters.python_api.client' not in sys.modules
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
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import MemCommitClient
from memcommit.persistence.store import MemoryStore

root = Path(os.environ['MEMCOMMIT_IMPORT_TEST_ROOT'])
store = MemoryStore(root=root)
context = ops.init('show/import-boundary')
ops.add(context, 'visible')
store.save(context)
store.set_current(context.name)
result = MemCommitClient(root=root).show()
assert result.name == context.name
assert 'memcommit.adapters.python_api._operations.show' in sys.modules
assert 'memcommit.application.operations.show.application' in sys.modules
assert 'memcommit.application.operations.show.runtime' in sys.modules
assert 'memcommit.show_application' not in sys.modules
assert 'memcommit.show_runtime' not in sys.modules
assert 'memcommit.adapters.python_api._operations.add' not in sys.modules
assert 'memcommit.adapters.python_api._operations.query' not in sys.modules
assert 'memcommit.adapters.python_api._operations.compare' not in sys.modules
assert 'memcommit.adapters.python_api._operations.meld' not in sys.modules
assert 'memcommit.application.operations.query.ordinary_application' not in sys.modules
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
from memcommit.adapters.python_api import MemCommitClient

root = Path(os.environ['MEMCOMMIT_IMPORT_TEST_ROOT'])
client = MemCommitClient(root=root)
result = client.describe_operation('compare')
assert result.name == 'compare'
assert not root.exists()
assert 'memcommit.adapters.python_api._operations.help' in sys.modules
assert 'memcommit.application.operations.help.application' in sys.modules
assert 'memcommit.application.operations.help.lookup_application' not in sys.modules
assert 'memcommit.help_application' not in sys.modules
assert 'memcommit.help_lookup_application' not in sys.modules
assert 'memcommit.adapters.python_api._operations.add' not in sys.modules
assert 'memcommit.adapters.python_api._operations.query' not in sys.modules
assert 'memcommit.adapters.python_api._operations.compare' not in sys.modules
assert 'memcommit.adapters.python_api._operations.meld' not in sys.modules
assert 'memcommit.comparison_execution' not in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.application.operations.meld.apply' not in sys.modules
assert 'memcommit.application.operations.meld.runtime' not in sys.modules
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
        if (
            fullname == 'memcommit.application.operations.ground'
            or fullname.startswith('memcommit.application.operations.ground.')
        ):
            raise ImportError(f'blocked Ground integration: {fullname}')
        return None

sys.meta_path.insert(0, NoGround())
for name in (
    'memcommit.application.operations.atomize.domain',
    'memcommit.application.operations.update.model',
    'memcommit.application.operations.distill.model',
    'memcommit.application.operations.distill.application',
    'memcommit.application.operations.distill.runtime',
    'memcommit.application.operations.makemore.model',
    'memcommit.application.operations.makemore.application',
    'memcommit.application.operations.makemore.runtime',
    'memcommit.application.operations.makemore.add_runtime',
):
    importlib.import_module(name)
from memcommit.adapters.python_api import MemCommitClient
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
from memcommit.adapters.python_api import AddInputError, MemCommitClient
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
assert 'memcommit.adapters.python_api._operations.add' in sys.modules
assert 'memcommit.application.operations.add.application' in sys.modules
assert 'memcommit.application.operations.add.runtime' in sys.modules
assert 'memcommit.add_application' not in sys.modules
assert 'memcommit.add_runtime' not in sys.modules
assert 'memcommit.adapters.python_api._operations.query' not in sys.modules
assert 'memcommit.adapters.python_api._operations.meld' not in sys.modules
assert 'memcommit.adapters.python_api._operations.compare' not in sys.modules
assert 'memcommit.adapters.python_api._operations.fit' not in sys.modules
assert 'memcommit.adapters.python_api._operations.distill' not in sys.modules
assert 'memcommit.adapters.python_api._operations.makemore' not in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.application.operations.meld.apply' not in sys.modules
assert 'memcommit.application.operations.meld.runtime' not in sys.modules
assert 'memcommit.application.operations.query.ordinary_application' not in sys.modules
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
from memcommit.adapters.python_api import MemCommitClient, QueryInputError

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
assert 'memcommit.adapters.python_api._operations.query' in sys.modules
assert 'memcommit.application.operations.query.ordinary_application' in sys.modules
assert 'memcommit.adapters.python_api._operations.add' not in sys.modules
assert 'memcommit.application.operations.add.application' not in sys.modules
assert 'memcommit.application.operations.add.runtime' not in sys.modules
assert 'memcommit.add_application' not in sys.modules
assert 'memcommit.add_runtime' not in sys.modules
assert 'memcommit.adapters.python_api._operations.meld' not in sys.modules
assert 'memcommit.adapters.python_api._operations.compare' not in sys.modules
assert 'memcommit.adapters.python_api._operations.fit' not in sys.modules
assert 'memcommit.adapters.python_api._operations.distill' not in sys.modules
assert 'memcommit.adapters.python_api._operations.makemore' not in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.application.operations.meld.apply' not in sys.modules
assert 'memcommit.application.operations.meld.runtime' not in sys.modules
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
from memcommit.adapters.python_api import MeldContextError, MemCommitClient

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
assert 'memcommit.adapters.python_api._operations.meld' in sys.modules
assert 'memcommit.application.operations.meld.apply' in sys.modules
assert 'memcommit.application.operations.meld.runtime' in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.adapters.python_api._operations.add' not in sys.modules
assert 'memcommit.application.operations.add.application' not in sys.modules
assert 'memcommit.application.operations.add.runtime' not in sys.modules
assert 'memcommit.add_application' not in sys.modules
assert 'memcommit.add_runtime' not in sys.modules
assert 'memcommit.adapters.python_api._operations.query' not in sys.modules
assert 'memcommit.application.operations.query.ordinary_application' not in sys.modules
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
from memcommit.adapters.python_api import CompareContextError, MemCommitClient

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
assert 'memcommit.adapters.python_api._operations.compare' in sys.modules
assert 'memcommit.application.capabilities.memory_issue_analysis.peer_relations.execution' in sys.modules
assert 'memcommit.adapters.python_api._operations.add' not in sys.modules
assert 'memcommit.application.operations.add.application' not in sys.modules
assert 'memcommit.application.operations.add.runtime' not in sys.modules
assert 'memcommit.add_application' not in sys.modules
assert 'memcommit.add_runtime' not in sys.modules
assert 'memcommit.adapters.python_api._operations.query' not in sys.modules
assert 'memcommit.application.operations.query.ordinary_application' not in sys.modules
assert 'memcommit.adapters.python_api._operations.meld' not in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.application.operations.meld.apply' not in sys.modules
assert 'memcommit.application.operations.meld.runtime' not in sys.modules
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
from memcommit.adapters.python_api import ForgetContextError, MemCommitClient

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
assert 'memcommit.adapters.python_api._operations.forget' in sys.modules
assert 'memcommit.application.operations.forget.application' in sys.modules
assert 'memcommit.application.operations.forget.runtime' in sys.modules
assert 'memcommit.forget_application' not in sys.modules
assert 'memcommit.forget_runtime' not in sys.modules
assert 'memcommit.adapters.python_api._operations.add' not in sys.modules
assert 'memcommit.application.operations.add.application' not in sys.modules
assert 'memcommit.application.operations.add.runtime' not in sys.modules
assert 'memcommit.add_application' not in sys.modules
assert 'memcommit.add_runtime' not in sys.modules
assert 'memcommit.adapters.python_api._operations.query' not in sys.modules
assert 'memcommit.application.operations.query.ordinary_application' not in sys.modules
assert 'memcommit.adapters.python_api._operations.meld' not in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.application.operations.meld.apply' not in sys.modules
assert 'memcommit.application.operations.meld.runtime' not in sys.modules
assert 'memcommit.adapters.python_api._operations.update' not in sys.modules
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
from memcommit.adapters.python_api import MemCommitClient, SemanticInputError

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
assert 'memcommit.adapters.python_api._operations.fit' in sys.modules
assert 'memcommit.application.operations.fit.application' in sys.modules
assert 'memcommit.application.operations.fit.runtime' in sys.modules
assert 'memcommit.application.operations.fit.coherence' in sys.modules
assert 'memcommit.application.operations.fit.ground_report' in sys.modules
assert 'memcommit.application.operations.fit.judgment' in sys.modules
assert 'memcommit.application.operations.fit.store' in sys.modules
assert 'memcommit.fit_application' not in sys.modules
assert 'memcommit.fit_runtime' not in sys.modules
assert 'memcommit.fit' not in sys.modules
assert 'memcommit.fit_coherence' not in sys.modules
assert 'memcommit.fit_judgment' not in sys.modules
assert 'memcommit.fit_store' not in sys.modules
assert 'memcommit.adapters.python_api._operations.distill' not in sys.modules
assert 'memcommit.adapters.python_api._operations.makemore' not in sys.modules
assert 'memcommit.adapters.python_api._operations.ground_distill' not in sys.modules
assert 'memcommit.adapters.python_api._operations.ground_makemore' not in sys.modules
assert 'memcommit.ground_distill' not in sys.modules
assert 'memcommit.ground_makemore' not in sys.modules
""",
        environment=environment,
    )

    assert completed.returncode == 0, completed.stderr


def test_selected_standalone_makemore_does_not_load_ground(tmp_path):
    environment = os.environ.copy()
    environment["MEMCOMMIT_IMPORT_TEST_ROOT"] = str(tmp_path / "store")
    completed = _run_fresh(
        """
import json
import os
from pathlib import Path
import sys
from memcommit.adapters.python_api import MemCommitClient

class Provider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == 'makemore'
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
result = client.makemore(goal='Confirm before acting.', number=1)
assert result.rules[0].content == 'Confirm the option before acting.'
assert 'memcommit.adapters.python_api._operations.makemore' in sys.modules
assert 'memcommit.application.operations.makemore.application' in sys.modules
assert 'memcommit.application.operations.makemore.runtime' in sys.modules
assert 'memcommit.application.operations.makemore.add_runtime' not in sys.modules
assert 'memcommit.makemore_application' not in sys.modules
assert 'memcommit.makemore_runtime' not in sys.modules
assert 'memcommit.makemore_add_runtime' not in sys.modules
assert 'memcommit.adapters.python_api._operations.ground_makemore' not in sys.modules
assert 'memcommit.adapters.python_api._operations.ground_distill' not in sys.modules
assert 'memcommit.ground_makemore' not in sys.modules
assert 'memcommit.ground_distill' not in sys.modules
assert 'memcommit.distill_application' not in sys.modules
assert 'memcommit.distill_runtime' not in sys.modules
assert 'memcommit.application.operations.distill.application' not in sys.modules
assert 'memcommit.application.operations.distill.runtime' not in sys.modules
assert 'memcommit.meld_application' not in sys.modules
assert 'memcommit.meld_runtime' not in sys.modules
assert 'memcommit.application.operations.meld.apply' not in sys.modules
assert 'memcommit.application.operations.meld.runtime' not in sys.modules
""",
        environment=environment,
    )

    assert completed.returncode == 0, completed.stderr


def test_root_and_api_lazy_exports_preserve_real_object_identity():
    completed = _run_fresh(
        """
import memcommit
import memcommit.adapters.python_api as api
assert memcommit.MemCommitClient is api.MemCommitClient
assert set(memcommit.__all__) <= set(dir(memcommit))
assert set(api.__all__) <= set(dir(api))
"""
    )

    assert completed.returncode == 0, completed.stderr
