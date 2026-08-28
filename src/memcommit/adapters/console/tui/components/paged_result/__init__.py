"""Compact, non-full-screen navigation for bounded result rows."""

from memcommit.adapters.console.tui.components.paged_result.model import PagedResultState
from memcommit.adapters.console.tui.components.paged_result.screen import (
    PagedResultRenderer,
    run_paged_result,
)

__all__ = ["PagedResultRenderer", "PagedResultState", "run_paged_result"]
