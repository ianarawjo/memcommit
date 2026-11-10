"""One explicit instruction for the current Context and optional descendants."""

from dataclasses import dataclass

from .changes import UpdateError


@dataclass(frozen=True, slots=True)
class UpdateRequest:
    instruction: str
    recursive: bool = False

    def __post_init__(self):
        if not isinstance(self.instruction, str) or not self.instruction.strip():
            raise UpdateError("An Update instruction must be nonblank text.")
        if type(self.recursive) is not bool:
            raise UpdateError("Update recursive scope must be boolean.")
