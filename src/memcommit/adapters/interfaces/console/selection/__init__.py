"""Operation-neutral selection state shared by console interactions."""

from memcommit.adapters.interfaces.console.selection.model import SelectionOption
from memcommit.adapters.interfaces.console.selection.state import FlatMultiSelectionState, FlatSelectionState

__all__ = ["FlatMultiSelectionState", "FlatSelectionState", "SelectionOption"]
