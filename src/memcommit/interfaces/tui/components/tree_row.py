"""Shared marker grammar for navigable hierarchy rows."""


def navigable_tree_row_prefix(
    *,
    selected: bool,
    current: bool = False,
    depth: int = 0,
    branch: str = "·",
) -> str:
    """Return the shared Switch-style prefix for one navigable hierarchy row."""
    if depth < 0:
        raise ValueError("Navigable tree row depth cannot be negative.")
    if not isinstance(branch, str) or not branch or "\n" in branch:
        raise ValueError("Navigable tree row branch must be one visible token.")
    pointer = "›" if selected else " "
    active = "*" if current else " "
    return f"{pointer} {active} {'  ' * depth}{branch} "
