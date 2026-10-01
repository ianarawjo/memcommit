"""One explicit Update instruction, independent of its stored or inline origin."""

from dataclasses import dataclass

from .changes import UpdateError


@dataclass(frozen=True, slots=True)
class UpdateInstruction:
    text: str

    def __post_init__(self):
        if not isinstance(self.text, str) or not self.text.strip():
            raise UpdateError("An Update instruction must be nonblank text.")


@dataclass(frozen=True, slots=True)
class UpdateRequest:
    instruction: str | None = None
    memory: str | None = None
    target: str | None = None

    def __post_init__(self):
        if (self.instruction is None) == (self.memory is None):
            raise UpdateError("Supply one instruction or --memory UID, not both.")
        if self.instruction is not None:
            UpdateInstruction(self.instruction)
        for name in ("memory", "target"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise UpdateError(f"Update {name} must be nonblank text.")
