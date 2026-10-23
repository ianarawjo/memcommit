"""Match deleted and added files by exact content, then bounded chunk overlap."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class FileRename:
    old_path: str
    new_path: str
    similarity: int


def _content_chunks(content):
    content = content.replace(b"\r\n", b"\n")
    chunks = Counter()
    start = 0
    for index, value in enumerate(content, 1):
        if value == 10 or index - start == 64:
            chunk = content[start:index]
            chunks[chunk] += len(chunk)
            start = index
    if start < len(content):
        chunk = content[start:]
        chunks[chunk] += len(chunk)
    return chunks


def detect_file_renames(deleted_files, added_files):
    """Return deterministic one-to-one matches at a 50% similarity threshold.

    Exact bytes take precedence. Remaining pairs are greedily selected by
    descending byte-weighted overlap, then canonical old/new path order.
    Similarity chooses file identity only, never individual Memory identity.
    """
    sources, destinations = set(deleted_files), set(added_files)
    matches = []
    identical = {}
    for path in sorted(added_files):
        identical.setdefault(sha256(added_files[path]).digest(), []).append(path)
    for old in sorted(deleted_files):
        candidates = identical.get(sha256(deleted_files[old]).digest(), ())
        new = next((path for path in candidates if path in destinations), None)
        if new is not None:
            matches.append(FileRename(old, new, 100))
            sources.remove(old)
            destinations.remove(new)
    if len(sources) * len(destinations) > 100_000:
        raise ValueError("Too many file rename candidates for bounded Sync matching.")
    chunks = {("old", path): _content_chunks(deleted_files[path]) for path in sources}
    chunks.update(
        {("new", path): _content_chunks(added_files[path]) for path in destinations}
    )
    candidates = []
    comparison_work = 0
    for old in sorted(sources):
        for new in sorted(destinations):
            maximum = max(len(deleted_files[old]), len(added_files[new]))
            minimum = min(len(deleted_files[old]), len(added_files[new]))
            if not maximum or minimum * 2 < maximum:
                continue
            comparison_work += min(len(chunks["old", old]), len(chunks["new", new]))
            if comparison_work > 4_000_000:
                raise ValueError(
                    "File rename comparison exceeds the bounded chunk budget."
                )
            common = sum((chunks["old", old] & chunks["new", new]).values())
            score = common * 100 // maximum
            if score >= 50:
                candidates.append((-score, old, new))
    for negative_score, old, new in sorted(candidates):
        if old in sources and new in destinations:
            matches.append(FileRename(old, new, -negative_score))
            sources.remove(old)
            destinations.remove(new)
    return tuple(matches)
