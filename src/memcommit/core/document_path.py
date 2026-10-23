"""Validate relative document and asset paths without filesystem access."""

from pathlib import PurePosixPath


def relative_document_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("Document path must be a nonempty relative POSIX path.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError(f"Document path escapes its package: {value!r}.")
    if any(part.casefold() in {".mem", ".git"} for part in path.parts):
        raise ValueError("Document paths cannot claim internal .mem or .git state.")
    if any(":" in part for part in path.parts):
        raise ValueError(f"Document path contains an invalid segment: {value!r}.")
    return value
