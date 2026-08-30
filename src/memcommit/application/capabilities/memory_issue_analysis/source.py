"""Freeze exact, provenance-preserving Memory Issue detection Sources."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Literal, Sequence

from memcommit.application.capabilities.authority.context_access import (
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.application.capabilities.authority.source_use_policy import (
    authorize_combination,
)
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.application.operations.review.model import direct_context_digest
from memcommit.core.context import Context, Memory
from memcommit.core.context_targeting.readable_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.persistence.store import MemoryStore


QualityFindSelectionMode = Literal["SINGLE", "MULTIPLE"]


class QualityFindSourceError(ValueError):
    """A Memory Issue finder cannot freeze or revalidate its Source."""


def _direct_memories(context: Context) -> tuple[Memory, ...]:
    return tuple(item for item in context.iter_items() if isinstance(item, Memory))


@dataclass(frozen=True)
class QualityFindSourceFrame:
    """One frozen, provenance-preserving aggregate finding frame.

    Context cardinality and lexical reach are setup choices. Execution uses the
    exact effective Context set recorded here and flattens only directly owned
    Memories into one provider frame. The owner map remains local so findings
    can show the real Context for each Memory without fabricating ownership on
    the temporary aggregate Context.
    """

    contexts: tuple[Context, ...]
    context_names: tuple[str, ...]
    context_digests: tuple[str, ...]
    target_names: tuple[str, ...]
    selection_mode: QualityFindSelectionMode
    include_descendants: bool
    profile_selected: bool
    digest: str

    @classmethod
    def create(
        cls,
        contexts: Sequence[Context],
        *,
        context_names: Sequence[str] | None = None,
        target_names: Sequence[str] | None = None,
        selection_mode: QualityFindSelectionMode = "SINGLE",
        include_descendants: bool = False,
        profile_selected: bool = False,
    ) -> "QualityFindSourceFrame":
        values = tuple(contexts)
        names = (
            tuple(context.name for context in values)
            if context_names is None
            else tuple(context_names)
        )
        targets = names if target_names is None else tuple(target_names)
        if (
            not values
            or len(values) != len(names)
            or len(set(names)) != len(names)
            or any(not isinstance(name, str) or not name for name in names)
        ):
            raise QualityFindSourceError(
                "Quality finder source requires distinct readable Context names."
            )
        if len({context.uid for context in values}) != len(values):
            raise QualityFindSourceError(
                "Quality finder targets resolve the same Context more than once."
            )
        if (
            selection_mode not in {"SINGLE", "MULTIPLE"}
            or type(include_descendants) is not bool
            or type(profile_selected) is not bool
        ):
            raise QualityFindSourceError("Invalid quality finder range settings.")
        if (
            len(set(targets)) != len(targets)
            or any(not isinstance(name, str) or not name for name in targets)
            or not set(targets) <= set(names)
            or (profile_selected and targets)
            or (not profile_selected and not targets)
            or (
                selection_mode == "SINGLE"
                and not profile_selected
                and len(targets) != 1
            )
        ):
            raise QualityFindSourceError("Invalid quality finder target roots.")

        memory_uids: set[str] = set()
        for context in values:
            for memory in _direct_memories(context):
                if memory.uid in memory_uids:
                    # Findings identify inputs by durable Memory UID. Allowing
                    # an alias collision would make owner provenance ambiguous.
                    raise QualityFindSourceError(
                        "Quality finder source contains a repeated Memory uid."
                    )
                memory_uids.add(memory.uid)
        digests = tuple(direct_context_digest(context) for context in values)
        encoded = json.dumps(
            {
                "contexts": [
                    {"uid": context.uid, "name": name, "digest": digest}
                    for context, name, digest in zip(values, names, digests)
                ],
                "targets": list(targets),
                "selection_mode": selection_mode,
                "include_descendants": include_descendants,
                "profile_selected": profile_selected,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return cls(
            contexts=values,
            context_names=names,
            context_digests=digests,
            target_names=targets,
            selection_mode=selection_mode,
            include_descendants=include_descendants,
            profile_selected=profile_selected,
            digest=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        )

    @property
    def memory_count(self) -> int:
        return sum(len(_direct_memories(context)) for context in self.contexts)

    @property
    def route(self) -> str:
        if len(self.context_names) == 1:
            return self.context_names[0]
        return f"{len(self.context_names)} CONTEXTS"

    @property
    def memory_context_names(self) -> dict[str, str]:
        return {
            memory.uid: context_name
            for context, context_name in zip(self.contexts, self.context_names)
            for memory in _direct_memories(context)
        }

    @property
    def memory_ordinals(self) -> dict[str, int]:
        return {
            memory.uid: ordinal
            for context in self.contexts
            for ordinal, memory in enumerate(_direct_memories(context), start=1)
        }

    def analysis_context(self) -> Context:
        """Build the temporary direct-Memory Context supplied to one finder."""

        aggregate = Context(
            uid=str(uuid.uuid5(uuid.NAMESPACE_URL, f"memcommit:quality:{self.digest}")),
            name=(
                self.context_names[0]
                if len(self.context_names) == 1
                else f"QUALITY FIND FRAME · {len(self.context_names)} CONTEXTS"
            ),
        )
        for context in self.contexts:
            for memory in _direct_memories(context):
                aggregate.add(Memory(memory.uid, memory.content))
        return aggregate

    def matches(self, contexts: Sequence[Context]) -> bool:
        values = tuple(contexts)
        return (
            len(values) == len(self.contexts)
            and tuple(context.uid for context in values)
            == tuple(context.uid for context in self.contexts)
            and tuple(context.name for context in values)
            == tuple(context.name for context in self.contexts)
            and tuple(direct_context_digest(context) for context in values)
            == self.context_digests
        )


def freeze_quality_find_source(
    store: MemoryStore,
    context_name: str | None,
    *,
    current_name: str | None,
    all_readable: bool = False,
    registry: ProfileRegistry | None = None,
) -> QualityFindSourceFrame:
    """Resolve authority and freeze one exact or Profile-wide Source frame."""

    if all_readable and context_name is not None:
        raise ValueError(
            "All-readable Memory Issue detection cannot use an explicit Context."
        )
    access = resolve_context_access(
        store,
        None if all_readable else context_name,
        current_name=current_name,
        required_permission="READ",
        registry=registry,
    )
    if all_readable:
        catalog = freeze_profile_readable_context_catalog(
            store,
            access,
            registry=registry,
            include_query_routes=False,
        )
        names = tuple(catalog.list_context_names())
        accesses = tuple(catalog.access_for(name) for name in names)
        # Provider inference derives from every frozen contributor. Grant
        # authority must therefore be checked before any Source is disclosed.
        authorize_combination(accesses)
        return QualityFindSourceFrame.create(
            tuple(catalog.load_direct(name) for name in names),
            context_names=names,
            target_names=(),
            selection_mode="MULTIPLE",
            include_descendants=False,
            profile_selected=True,
        )

    authorize_combination((access,))
    context = (
        GrantedReadStore(access, registry=registry).load_direct(access.display_name)
        if access.is_granted
        else access.store.load_direct(access.context_name)
    )
    return QualityFindSourceFrame.create(
        (context,),
        context_names=(access.display_name,),
        target_names=(access.display_name,),
        selection_mode="SINGLE",
    )


__all__ = [
    "QualityFindSelectionMode",
    "QualityFindSourceError",
    "QualityFindSourceFrame",
    "freeze_quality_find_source",
]
