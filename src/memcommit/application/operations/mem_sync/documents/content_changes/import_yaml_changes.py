"""Accept string-value edits without guessing YAML key or Memory identity."""

from collections import defaultdict

import yaml

from memcommit.application.operations.mem_sync.model import (
    InboundContextChange,
    SyncConflictError,
    SyncIssue,
    SyncMemoryEffect,
)
from memcommit.models.context import Context
from memcommit.models.memory import Memory

from .source_attribution import validate_source_ranges


def _editable_yaml_tokens(text, conflict):
    tokens = []
    try:
        for token in yaml.scan(text, Loader=yaml.SafeLoader):
            tokens.append(token)
            if len(tokens) > 10_000:
                conflict("match-limit", "Too many YAML tokens for automatic matching.")
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except (yaml.YAMLError, RecursionError) as error:
        conflict("invalid-yaml", f"Cannot parse external YAML: {error}")
    if not isinstance(root, yaml.MappingNode):
        conflict("yaml-structure", "Inbound YAML edits require an existing mapping.")
    editable_ends, key_ends, visited = set(), set(), set()
    pending = [(root, False)]
    while pending:
        node, is_key = pending.pop()
        identity = (id(node), is_key)
        if identity in visited:
            continue
        visited.add(identity)
        if isinstance(node, yaml.ScalarNode):
            if is_key:
                key_ends.add(node.end_mark.index)
            elif node.tag == "tag:yaml.org,2002:str":
                editable_ends.add(node.end_mark.index)
        elif isinstance(node, yaml.MappingNode):
            keys = []
            for key, value in node.value:
                if not isinstance(key, yaml.ScalarNode):
                    conflict(
                        "yaml-structure", "Complex YAML keys require explicit import."
                    )
                keys.append((key.tag, key.value))
                pending.extend(((key, True), (value, False)))
            if len(keys) != len(set(keys)):
                conflict(
                    "yaml-structure", "Repeated YAML keys require explicit resolution."
                )
        elif isinstance(node, yaml.SequenceNode):
            pending.extend((child, False) for child in node.value)
    # An aliased string also used as a key cannot be edited as a value.
    editable_ends.difference_update(key_ends)
    positions = sorted(
        {
            0,
            *(
                mark.index
                for token in tokens
                for mark in (token.start_mark, token.end_mark)
            ),
        }
    )
    offsets = {}
    previous = byte_offset = 0
    for position in positions:
        byte_offset += len(text[previous:position].encode("utf-8"))
        offsets[position] = byte_offset
        previous = position
    return tokens, editable_ends, offsets


def import_yaml_changes(context, baseline_file, external_bytes, ranges, *, path):
    """Prepare existing text-value replacements, preserving raw syntax and UIDs."""

    def conflict(code, message):
        raise SyncConflictError(SyncIssue(code, path, message))

    if max(len(baseline_file), len(external_bytes)) > 2_000_000:
        conflict(
            "match-limit", "Document exceeds the bounded automatic matching limit."
        )
    try:
        old_text, new_text = (
            baseline_file.decode("utf-8"),
            external_bytes.decode("utf-8"),
        )
    except UnicodeError:
        conflict("encoding", "External changes require UTF-8 text.")
    memories, _ = validate_source_ranges(context, baseline_file, ranges, path=path)
    old_tokens, old_editable, old_offsets = _editable_yaml_tokens(old_text, conflict)
    new_tokens, new_editable, new_offsets = _editable_yaml_tokens(new_text, conflict)
    if len(old_tokens) != len(new_tokens):
        conflict("yaml-structure", "YAML keys and structure must remain unchanged.")
    patches = defaultdict(list)
    old_cursor = new_cursor = 0
    for old, new in zip(old_tokens, new_tokens):
        old_start, old_end = old.start_mark.index, old.end_mark.index
        new_start, new_end = new.start_mark.index, new.end_mark.index
        if type(old) is not type(new):
            conflict("yaml-structure", "YAML keys and structure must remain unchanged.")
        if old_text[old_cursor:old_start] != new_text[new_cursor:new_start]:
            conflict(
                "yaml-layout",
                "YAML layout outside string values must remain unchanged.",
            )
        old_raw, new_raw = old_text[old_start:old_end], new_text[new_start:new_end]
        if old_raw != new_raw:
            if not (
                isinstance(old, yaml.tokens.ScalarToken)
                and old_end in old_editable
                and new_end in new_editable
            ):
                conflict(
                    "yaml-structure", "Only existing YAML string values may change."
                )
            start, end = old_offsets[old_start], old_offsets[old_end]
            owners = [span for span in ranges if span.start <= start < end <= span.end]
            if len(owners) != 1:
                conflict(
                    "identity-conflict",
                    "Changed YAML value crosses Memory or generated-layout boundaries.",
                )
            owner = owners[0]
            patches[owner.source.memory_uid].append(
                (
                    owner.source.start + start - owner.start,
                    owner.source.start + end - owner.start,
                    external_bytes[new_offsets[new_start] : new_offsets[new_end]],
                )
            )
        old_cursor, new_cursor = old_end, new_end
    if old_text[old_cursor:] != new_text[new_cursor:]:
        conflict(
            "yaml-layout", "YAML layout outside string values must remain unchanged."
        )
    proposed = Context.from_dict(context.to_dict())
    effects = []
    for uid in memories:
        if uid not in patches:
            continue
        content = memories[uid].content.encode("utf-8")
        for start, end, replacement in reversed(patches[uid]):
            content = content[:start] + replacement + content[end:]
        proposed.replace_memory(Memory(uid, content.decode("utf-8")))
        effects.append(SyncMemoryEffect(context.name, uid, "EDIT"))
    return InboundContextChange(
        context.to_dict(), proposed.to_dict(), (path,), tuple(effects)
    )
