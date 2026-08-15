"""Store root selection must be lazy at import and frozen per instance."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import memcommit.store as store_module
from memcommit.store import MemoryStore


def test_explicit_root_never_resolves_the_active_profile(tmp_path, monkeypatch):
    def fail() -> Path:
        raise AssertionError("explicit root attempted to read active Profile")

    monkeypatch.setattr(store_module, "resolve_active_store_dir", fail)
    root = tmp_path / "explicit-store"

    store = MemoryStore(root=root, create=False)

    assert store.store_dir == root.absolute()
    assert store.contexts_dir == root.absolute() / "contexts"


def test_profile_backed_store_resolves_once_and_freezes(tmp_path, monkeypatch):
    first = tmp_path / "first-profile"
    second = tmp_path / "second-profile"
    selected = [first]
    calls: list[Path] = []

    def resolve() -> Path:
        calls.append(selected[0])
        return selected[0]

    monkeypatch.setattr(store_module, "resolve_active_store_dir", resolve)
    store = MemoryStore(create=False)
    selected[0] = second

    assert calls == [first]
    assert store.store_dir == first
    assert store.state_file == first / "state.json"
    assert calls == [first]
    assert MemoryStore(create=False).store_dir == second
    assert calls == [first, second]


def test_package_import_and_explicit_client_ignore_invalid_home_profile(tmp_path):
    home = tmp_path / "home"
    registry = home / ".mem-profiles" / "registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text('{"schema_version":999}\n', encoding="utf-8")
    root = tmp_path / "explicit-store"
    repository = Path(__file__).parents[1]
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment["USERPROFILE"] = str(home)
    environment["MEMCOMMIT_TEST_EXPLICIT_ROOT"] = str(root)
    command = (
        "import os; import memcommit; from pathlib import Path; "
        "root = Path(os.environ['MEMCOMMIT_TEST_EXPLICIT_ROOT']); "
        "client = memcommit.MemCommitClient(root=root, create=True); "
        "assert client.store_root == root.resolve()"
    )

    completed = subprocess.run(
        [sys.executable, "-c", command],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
