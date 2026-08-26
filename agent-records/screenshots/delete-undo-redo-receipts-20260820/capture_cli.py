"""Run the real mem CLI against the isolated receipt-capture Store."""

from __future__ import annotations

import os
import sys
from pathlib import Path


repository_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repository_root))

import memcommit.store as store_module  # noqa: E402


capture_store = os.environ.get("MEMCOMMIT_CAPTURE_STORE")
if not capture_store:
    raise RuntimeError("MEMCOMMIT_CAPTURE_STORE is required for this capture.")

# Patch only this process's default store boundary before the CLI is imported.
# The captured commands therefore exercise normal adapters without touching the
# active Profile or the person's real ~/.mem data.
store_module.STORE_DIR = Path(capture_store)

from memcommit.cli import app  # noqa: E402


app()
