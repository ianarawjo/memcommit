"""Build lossless Merge candidates and retain their original item evidence."""

from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Mapping

from memcommit.models.context import Context
from memcommit.models.memory import Memory


@dataclass(frozen=True)
class CandidateOrigin:
    """An occurrence is distinct from its original identity and lineage identity."""

    uid: str
    frame: str
    context_uid: str
    context_name: str
    item_uid: str
    identity_uid: str
    placement: str
    record_json: str

    def record(self) -> dict:
        return json.loads(self.record_json)


@dataclass(frozen=True)
class MergeCandidate:
    """Detached Memory union; reviewed owner records drive materialization."""

    record_json: str
    origins: tuple[CandidateOrigin, ...]
    frame_order: tuple[str, ...]

    def __post_init__(self) -> None:
        record = json.loads(self.record_json)
        if Context.from_dict(record).to_dict() != record:
            raise ValueError("Merge candidate must contain a canonical Context record.")
        if not self.frame_order or len(set(self.frame_order)) != len(self.frame_order):
            raise ValueError("Merge candidate frames must be unique and ordered.")
        if tuple(record["order"]) != tuple(origin.uid for origin in self.origins):
            raise ValueError("Merge candidate origins must cover its exact item order.")
        for origin in self.origins:
            if any(
                not isinstance(value, str) or not value
                for value in asdict(origin).values()
            ):
                raise ValueError("Merge candidate origin is incomplete.")
            if origin.frame not in self.frame_order:
                raise ValueError("Merge candidate origin names an unknown frame.")
            original = origin.record()
            if original["uid"] != origin.item_uid:
                raise ValueError("Merge candidate original identity changed.")
            projected = dict(original, uid=origin.uid)
            if record["memories"][origin.uid] != projected:
                raise ValueError("Merge candidate lost original item evidence.")

    @property
    def revision(self) -> str:
        return digest(self.to_dict())

    def context(self) -> Context:
        # No loaders: this record is analysis input, never a readable namespace.
        return Context.from_dict(json.loads(self.record_json))

    def origin(self, uid: str) -> CandidateOrigin:
        return next(origin for origin in self.origins if origin.uid == uid)

    def original_item(self, uid: str):
        origin = self.origin(uid)
        record = {
            "uid": origin.context_uid,
            "name": origin.context_name,
            "memories": {origin.item_uid: origin.record()},
            "order": [origin.item_uid],
        }
        return Context.from_dict(record).memories[origin.item_uid]

    def to_dict(self) -> dict:
        return {
            "context": json.loads(self.record_json),
            "origins": [asdict(origin) for origin in self.origins],
            "frame_order": list(self.frame_order),
        }

    @classmethod
    def from_dict(cls, value: object) -> MergeCandidate:
        if not isinstance(value, dict) or set(value) != {
            "context",
            "origins",
            "frame_order",
        }:
            raise ValueError("Invalid Merge candidate record.")
        if not isinstance(value["origins"], list) or not isinstance(
            value["frame_order"], list
        ):
            raise ValueError("Invalid Merge candidate origins or frames.")
        return cls(
            encode(value["context"]),
            tuple(CandidateOrigin(**item) for item in value["origins"]),
            tuple(value["frame_order"]),
        )


def combine_contexts(
    contexts: tuple[Context, ...],
    *,
    placement: str,
    identities: Mapping[tuple[int, str], str] | None = None,
    uid: str | None = None,
    name: str = "merge-candidate",
) -> MergeCandidate:
    """Retain every direct occurrence, with baseline/earlier frames first.

    A Merge-owned lineage map may equate fresh occurrences. It is evidence,
    not permission to overwrite a member before review.
    """
    if not contexts or not placement:
        raise ValueError("Merge candidate requires frames and a destination placement.")
    identities = dict(identities or {})
    keys = {
        (index, item.uid)
        for index, context in enumerate(contexts)
        for item in context.iter_memories()
    }
    if not set((identities or {})) <= keys:
        raise ValueError("Merge lineage names an unavailable candidate occurrence.")
    records = tuple(context.to_dict() for context in contexts)
    identity = digest(
        {
            "records": records,
            "placement": placement,
            "identities": sorted(
                (index, item, value) for (index, item), value in identities.items()
            ),
        }
    )
    candidate = Context(
        uid=uid or str(uuid.uuid5(uuid.NAMESPACE_URL, identity)), name=name
    ).to_dict()
    frames = tuple(f"frame:{index}" for index in range(len(contexts)))
    origins = []
    for index, record in enumerate(records):
        for item_uid in record["order"]:
            original = record["memories"][item_uid]
            # Preserve valid first occurrences, including baseline Memory UIDs.
            # Duplicate and legacy slots need distinct canonical analysis IDs.
            try:
                canonical = str(uuid.UUID(item_uid)) == item_uid
            except ValueError:
                canonical = False
            occurrence = (
                item_uid
                if canonical and item_uid not in candidate["memories"]
                else str(
                    uuid.uuid5(uuid.NAMESPACE_URL, f"{identity}:{index}:{item_uid}")
                )
            )
            candidate["memories"][occurrence] = dict(original, uid=occurrence)
            candidate["order"].append(occurrence)
            origins.append(
                CandidateOrigin(
                    occurrence,
                    frames[index],
                    record["uid"],
                    record["name"],
                    item_uid,
                    identities.get((index, item_uid), item_uid),
                    placement,
                    encode(original),
                )
            )
    return MergeCandidate(encode(candidate), tuple(origins), frames)


def rebase_candidate(previous: MergeCandidate, context: Context) -> MergeCandidate:
    """Keep surviving origin identities while inspecting their current post-image.

    The previous Audit retains original bytes; this revision records transformed
    bytes. New result items receive their own identities, never invented ancestry.
    """
    old = {origin.uid: origin for origin in previous.origins}
    record = context.to_dict()
    origins = []
    for uid in record["order"]:
        item = record["memories"][uid]
        prior = old.get(uid)
        if prior is not None:
            origins.append(
                CandidateOrigin(
                    uid,
                    prior.frame,
                    prior.context_uid,
                    prior.context_name,
                    prior.item_uid,
                    prior.identity_uid,
                    prior.placement,
                    encode(dict(item, uid=prior.item_uid)),
                )
            )
        else:
            origins.append(
                CandidateOrigin(
                    uid,
                    previous.frame_order[-1],
                    context.uid,
                    context.name,
                    uid,
                    uid,
                    previous.origins[0].placement if previous.origins else context.name,
                    encode(item),
                )
            )
    return MergeCandidate(encode(record), tuple(origins), previous.frame_order)


def copy_direct_item(
    item: Memory,
    *,
    memory_uid: str | None = None,
) -> Memory:
    """Copy a direct item without sharing a writable Memory value."""

    if isinstance(item, Memory):
        return Memory(uid=memory_uid or item.uid, content=item.content)
    if memory_uid is not None:
        raise ValueError("Only a Memory may receive a new Merge occurrence UID.")
    raise TypeError("Merge received an unsupported direct item.")


def copy_direct_context(context: Context) -> Context:
    """Copy one direct Context record while preserving canonical order."""

    copied = Context(uid=context.uid, name=context.name)
    # Merge changes direct items; it must retain the Target's export layout
    # and attachment membership rather than silently turning it into plain text.
    copied.corresponding_document_metadata = deepcopy(
        context.corresponding_document_metadata
    )
    copied.asset_metadata = deepcopy(context.asset_metadata)
    for item in context.iter_memories():
        copied.add(copy_direct_item(item))
    return copied


def encode(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: object) -> str:
    return hashlib.sha256(encode(value).encode()).hexdigest()
