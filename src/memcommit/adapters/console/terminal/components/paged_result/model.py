"""Operation-neutral state for a fixed-size result window."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PagedResultState:
    """Keep one focused item visible inside stable, discrete pages."""

    item_count: int
    page_size: int = 10
    selected_index: int = 0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.item_count, int)
            or isinstance(self.item_count, bool)
            or self.item_count < 1
        ):
            raise ValueError("Paged results require at least one item.")
        if (
            not isinstance(self.page_size, int)
            or isinstance(self.page_size, bool)
            or self.page_size < 1
        ):
            raise ValueError("Paged result size must be a positive integer.")
        if not 0 <= self.selected_index < self.item_count:
            raise ValueError("Paged result selection is outside the item set.")

    @property
    def page_start(self) -> int:
        """Return the zero-based first item in the selected discrete page."""

        return (self.selected_index // self.page_size) * self.page_size

    @property
    def page_stop(self) -> int:
        """Return the exclusive zero-based end of the selected page."""

        return min(self.page_start + self.page_size, self.item_count)

    @property
    def visible_indices(self) -> range:
        return range(self.page_start, self.page_stop)

    @property
    def showing_label(self) -> str:
        """Describe both the visible range and the complete frozen cardinality."""

        return f"SHOWING {self.page_start + 1}–{self.page_stop} OF {self.item_count}"

    def move(self, delta: int) -> bool:
        """Move one item without wrapping across the frozen result boundary."""

        if delta not in {-1, 1}:
            raise ValueError("Paged result movement must be -1 or 1.")
        candidate = self.selected_index + delta
        if not 0 <= candidate < self.item_count:
            return False
        self.selected_index = candidate
        return True

    def move_page(self, delta: int) -> bool:
        """Move one page while retaining the row position where possible."""

        if delta not in {-1, 1}:
            raise ValueError("Paged result page movement must be -1 or 1.")
        candidate = min(
            max(0, self.selected_index + (delta * self.page_size)),
            self.item_count - 1,
        )
        if candidate == self.selected_index:
            return False
        self.selected_index = candidate
        return True

    def move_to_boundary(self, *, end: bool) -> bool:
        candidate = self.item_count - 1 if end else 0
        if candidate == self.selected_index:
            return False
        self.selected_index = candidate
        return True
