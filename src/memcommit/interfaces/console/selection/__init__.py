"""Operation-neutral selection state shared by console interactions."""

from memcommit.interfaces.console.selection.model import SelectionOption
from memcommit.interfaces.console.selection.state import FlatMultiSelectionState, FlatSelectionState

__all__ = ["FlatMultiSelectionState", "FlatSelectionState", "SelectionOption"]
