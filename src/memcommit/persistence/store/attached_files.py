"""Immutable attached-file bytes; Context records own paths and membership."""

from pathlib import Path
import hashlib
import re

from .infrastructure.atomic_io import _write_bytes_atomic


def _path(store_root, file_id):
    if not isinstance(file_id, str) or re.fullmatch(r"[0-9a-f]{64}", file_id) is None:
        raise ValueError("Invalid attached-file identity.")
    directory = Path(store_root) / "attached-files"
    if directory.is_symlink():
        raise ValueError("Attached-file storage must not be a symbolic link.")
    return directory / file_id


def save_attached_file(store_root, data: bytes) -> str:
    file_id = hashlib.sha256(data).hexdigest()
    path = _path(store_root, file_id)
    if path.exists():
        read_attached_file(store_root, file_id)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_bytes_atomic(path, data)
    return file_id


def read_attached_file(store_root, file_id: str) -> bytes:
    path = _path(store_root, file_id)
    if path.is_symlink():
        raise ValueError("Attached-file content must not be a symbolic link.")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != file_id:
        raise ValueError(f"Attached-file content is damaged: {file_id}")
    return data
