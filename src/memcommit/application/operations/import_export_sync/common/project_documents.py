"""Select Profile documents using one root-scoped, Git-compatible ignore file."""

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from pathspec import GitIgnoreSpec


@dataclass(frozen=True)
class ProjectDocumentRules:
    ignore_bytes: bytes | None = None
    _patterns: GitIgnoreSpec = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        try:
            text = (self.ignore_bytes or b"").decode("utf-8")
        except UnicodeError as error:
            raise ValueError(".memignore must contain UTF-8 text.") from error
        object.__setattr__(
            self, "_patterns", GitIgnoreSpec.from_lines(text.splitlines())
        )

    def excludes(self, path, *, directory=False):
        parts = PurePosixPath(path).parts
        if any(part.casefold() in {".git", ".mem"} for part in parts):
            return True
        if path == ".memignore":
            return True
        # An excluded directory is not visited, so a child negation cannot
        # reinclude its contents without first reincluding the directory.
        directories = len(parts) if directory else len(parts) - 1
        return any(
            self._patterns.match_file("/".join(parts[:depth]) + "/")
            for depth in range(1, directories + 1)
        ) or self._patterns.match_file(path + ("/" if directory else ""))

    @staticmethod
    def supports(path):
        return PurePosixPath(path).suffix.lower() == ".md"
