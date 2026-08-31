"""Terminal-independent frozen-plan contract for deterministic Replace."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal, Protocol

from memcommit.application.operations.find.application import (
    FindRequest,
    FindSpan,
    compile_find_pattern,
)


ReplaceMode = Literal["LITERAL", "REGEX"]


class ReplaceError(RuntimeError):
    """Base failure for deterministic Replace."""


class ReplaceInputError(ReplaceError, ValueError):
    """The replacement request or reviewed plan is invalid."""


class ReplaceStalePlanError(ReplaceError):
    """The complete scanned scope changed after review."""


@dataclass(frozen=True, slots=True)
class ReplaceRequest:
    pattern: str
    replacement: str
    target_names: tuple[str, ...]
    include_descendants: bool = False
    follow_embeds: bool = False
    mode: ReplaceMode = "LITERAL"
    ignore_case: bool = False

    def __post_init__(self) -> None:
        try:
            FindRequest(
                pattern=self.pattern,
                target_names=self.target_names,
                include_descendants=self.include_descendants,
                follow_embeds=self.follow_embeds,
                mode=self.mode,
                ignore_case=self.ignore_case,
            )
        except (TypeError, ValueError) as error:
            raise ReplaceInputError(str(error)) from error
        if not isinstance(self.replacement, str):
            raise ReplaceInputError("Replace replacement must be text.")


@dataclass(frozen=True, slots=True)
class ReplaceSourceMemory:
    uid: str
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.uid, str) or not self.uid:
            raise ReplaceError("Replace source Memory UID must be nonblank text.")
        if not isinstance(self.content, str):
            raise ReplaceError("Replace source Memory content must be text.")


@dataclass(frozen=True, slots=True)
class FrozenReplaceContext:
    name: str
    uid: str
    digest: str
    memories: tuple[ReplaceSourceMemory, ...]

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.name, self.uid, self.digest)
        ):
            raise ReplaceError("Replace frozen Context identity is incomplete.")
        if len({memory.uid for memory in self.memories}) != len(self.memories):
            raise ReplaceError("Replace frozen Context repeats a Memory UID.")


@dataclass(frozen=True, slots=True)
class FrozenReplaceSource:
    contexts: tuple[FrozenReplaceContext, ...]
    token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        identities = tuple((context.name, context.uid) for context in self.contexts)
        if not contexts_valid(identities):
            raise ReplaceError("Replace source repeats a Context identity.")


def contexts_valid(identities: tuple[tuple[str, str], ...]) -> bool:
    return (
        bool(identities)
        and len({name for name, _uid in identities}) == len(identities)
        and len({uid for _name, uid in identities}) == len(identities)
    )


@dataclass(frozen=True, slots=True)
class ReplaceMemoryChange:
    memory_uid: str
    before_content: str
    after_content: str
    spans: tuple[FindSpan, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.memory_uid, str) or not self.memory_uid:
            raise ReplaceError("Replace Memory change UID must be nonblank text.")
        if not isinstance(self.before_content, str) or not isinstance(
            self.after_content, str
        ):
            raise ReplaceError("Replace Memory change content must be text.")
        if not self.spans:
            raise ReplaceError("Replace Memory change requires exact spans.")
        previous_end = -1
        for span in self.spans:
            if (
                not isinstance(span, FindSpan)
                or span.start < previous_end
                or self.before_content[span.start : span.end] != span.text
            ):
                raise ReplaceError("Replace spans do not match frozen content.")
            previous_end = span.end

    @property
    def changed(self) -> bool:
        return self.before_content != self.after_content


@dataclass(frozen=True, slots=True)
class ReplaceContextPlan:
    context_name: str
    context_uid: str
    context_digest: str
    scanned_memory_count: int
    matches: tuple[ReplaceMemoryChange, ...]

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.context_name, self.context_uid, self.context_digest)
        ):
            raise ReplaceError("Replace Context plan identity is incomplete.")
        if (
            isinstance(self.scanned_memory_count, bool)
            or not isinstance(self.scanned_memory_count, int)
            or self.scanned_memory_count < len(self.matches)
        ):
            raise ReplaceError("Replace scanned Memory count is invalid.")
        if len({match.memory_uid for match in self.matches}) != len(self.matches):
            raise ReplaceError("Replace Context plan repeats a Memory UID.")

    @property
    def changed_matches(self) -> tuple[ReplaceMemoryChange, ...]:
        return tuple(match for match in self.matches if match.changed)


@dataclass(frozen=True, slots=True)
class FrozenReplacePlan:
    request: ReplaceRequest
    contexts: tuple[ReplaceContextPlan, ...]
    plan_digest: str
    token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.request, ReplaceRequest):
            raise ReplaceError("Replace plan request is invalid.")
        identities = tuple(
            (context.context_name, context.context_uid) for context in self.contexts
        )
        if not contexts_valid(identities):
            raise ReplaceError("Replace plan repeats a Context identity.")
        if (
            not isinstance(self.plan_digest, str)
            or len(self.plan_digest) != 64
            or any(
                character not in "0123456789abcdef" for character in self.plan_digest
            )
        ):
            raise ReplaceError("Replace plan digest is invalid.")

    @property
    def scanned_context_count(self) -> int:
        return len(self.contexts)

    @property
    def scanned_memory_count(self) -> int:
        return sum(context.scanned_memory_count for context in self.contexts)

    @property
    def matched_memory_count(self) -> int:
        return sum(len(context.matches) for context in self.contexts)

    @property
    def changed_memory_count(self) -> int:
        return sum(len(context.changed_matches) for context in self.contexts)

    @property
    def occurrence_count(self) -> int:
        return sum(
            len(match.spans) for context in self.contexts for match in context.matches
        )


@dataclass(frozen=True, slots=True)
class ReplaceCheckpoint:
    context_name: str
    context_uid: str
    checkpoint_uid: str


@dataclass(frozen=True, slots=True)
class ReplaceApplyResult:
    plan_digest: str
    applied: bool
    scanned_context_count: int
    scanned_memory_count: int
    matched_memory_count: int
    changed_memory_count: int
    occurrence_count: int
    checkpoints: tuple[ReplaceCheckpoint, ...]

    def __post_init__(self) -> None:
        if type(self.applied) is not bool:
            raise ReplaceError("Replace Apply state must be a boolean.")
        if self.applied != bool(self.checkpoints):
            raise ReplaceError("Replace Apply checkpoints do not match its effect.")


class ReplacePort(Protocol):
    def freeze(self, request: ReplaceRequest) -> FrozenReplaceSource: ...

    def apply(self, plan: FrozenReplacePlan) -> ReplaceApplyResult: ...


def _replace_spans(content: str, spans: tuple[FindSpan, ...], value: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for span in spans:
        pieces.extend((content[cursor : span.start], value))
        cursor = span.end
    pieces.append(content[cursor:])
    return "".join(pieces)


def _plan_payload(
    request: ReplaceRequest,
    contexts: tuple[ReplaceContextPlan, ...],
) -> dict[str, object]:
    return {
        "version": 1,
        "request": {
            "pattern": request.pattern,
            "replacement": request.replacement,
            "target_names": list(request.target_names),
            "include_descendants": request.include_descendants,
            "follow_embeds": request.follow_embeds,
            "mode": request.mode,
            "ignore_case": request.ignore_case,
        },
        "contexts": [
            {
                "name": context.context_name,
                "uid": context.context_uid,
                "digest": context.context_digest,
                "scanned_memory_count": context.scanned_memory_count,
                "matches": [
                    {
                        "memory_uid": match.memory_uid,
                        "before": match.before_content,
                        "after": match.after_content,
                        "spans": [
                            [span.start, span.end, span.text] for span in match.spans
                        ],
                    }
                    for match in context.matches
                ],
            }
            for context in contexts
        ],
    }


def replace_plan_digest(
    request: ReplaceRequest,
    contexts: tuple[ReplaceContextPlan, ...],
) -> str:
    return hashlib.sha256(
        json.dumps(
            _plan_payload(request, contexts),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def plan_replace(request: ReplaceRequest, *, port: ReplacePort) -> FrozenReplacePlan:
    """Freeze every eligible Context, then compute every exact replacement."""

    if not isinstance(request, ReplaceRequest):
        raise ReplaceInputError("Replace requires a ReplaceRequest.")
    compiled = compile_find_pattern(
        FindRequest(
            pattern=request.pattern,
            target_names=request.target_names,
            include_descendants=request.include_descendants,
            follow_embeds=request.follow_embeds,
            mode=request.mode,
            ignore_case=request.ignore_case,
        )
    )
    frozen = port.freeze(request)
    if not isinstance(frozen, FrozenReplaceSource):
        raise ReplaceError("Replace could not prepare the selected search area.")
    context_plans: list[ReplaceContextPlan] = []
    for context in frozen.contexts:
        changes: list[ReplaceMemoryChange] = []
        for memory in context.memories:
            spans = tuple(
                FindSpan(match.start(), match.end(), match.group(0))
                for match in compiled.finditer(memory.content)
            )
            if not spans:
                continue
            changes.append(
                ReplaceMemoryChange(
                    memory_uid=memory.uid,
                    before_content=memory.content,
                    after_content=_replace_spans(
                        memory.content,
                        spans,
                        request.replacement,
                    ),
                    spans=spans,
                )
            )
        context_plans.append(
            ReplaceContextPlan(
                context_name=context.name,
                context_uid=context.uid,
                context_digest=context.digest,
                scanned_memory_count=len(context.memories),
                matches=tuple(changes),
            )
        )
    contexts = tuple(context_plans)
    return FrozenReplacePlan(
        request=request,
        contexts=contexts,
        plan_digest=replace_plan_digest(request, contexts),
        token=frozen.token,
    )


def apply_replace(
    plan: FrozenReplacePlan,
    *,
    port: ReplacePort,
) -> ReplaceApplyResult:
    """Apply only the exact frozen plan through its owning runtime port."""

    if not isinstance(plan, FrozenReplacePlan):
        raise ReplaceInputError("Replace Apply requires a FrozenReplacePlan.")
    if replace_plan_digest(plan.request, plan.contexts) != plan.plan_digest:
        raise ReplaceInputError("Replace plan content does not match its digest.")
    result = port.apply(plan)
    if not isinstance(result, ReplaceApplyResult):
        raise ReplaceError("Replace runtime returned an invalid Apply result.")
    if (
        result.plan_digest != plan.plan_digest
        or result.scanned_context_count != plan.scanned_context_count
        or result.scanned_memory_count != plan.scanned_memory_count
        or result.matched_memory_count != plan.matched_memory_count
        or result.changed_memory_count != plan.changed_memory_count
        or result.occurrence_count != plan.occurrence_count
    ):
        raise ReplaceError("Replace Apply result does not match its frozen plan.")
    return result


__all__ = [
    "FrozenReplaceContext",
    "FrozenReplacePlan",
    "FrozenReplaceSource",
    "ReplaceApplyResult",
    "ReplaceCheckpoint",
    "ReplaceContextPlan",
    "ReplaceError",
    "ReplaceInputError",
    "ReplaceMemoryChange",
    "ReplaceMode",
    "ReplacePort",
    "ReplaceRequest",
    "ReplaceSourceMemory",
    "ReplaceStalePlanError",
    "apply_replace",
    "plan_replace",
    "replace_plan_digest",
]
