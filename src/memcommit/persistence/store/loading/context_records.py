"""Load local Memory-only Context records."""

from __future__ import annotations

import json

from memcommit.core.context_name_validation import validate_context_name
from memcommit.models.context import Context
from memcommit.persistence.store.lookup.context_names import (
    list_context_and_descendant_names,
)

from ..infrastructure.atomic_io import _reject_duplicate_json_keys
from ..context_memory.records import _validate_context_header


class _ContextLoadingMixin:
    def load(self, name: str) -> Context:
        """Load one complete Context from its persisted record."""
        validate_context_name(name)
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        with open(self._context_file(name), encoding="utf-8") as file:
            data = json.load(file, object_pairs_hook=_reject_duplicate_json_keys)
        data = _validate_context_header(data, name)
        try:
            context = Context.from_dict(data)
            return context
        except (KeyError, TypeError) as error:
            raise ValueError(
                f"Context file for '{name}' has an invalid Memory structure: {error}"
            ) from error

    def load_direct(self, name: str) -> Context:
        """Read the selected Context's complete Memory frame."""
        return self.load(name)

    def load_context_record_bytes(self, name: str) -> bytes:
        """Read the exact saved bytes needed to roll back a failed publication."""
        return self._context_file(name).read_bytes()

    def load_context_and_descendants(self, context_name: str) -> tuple[Context, ...]:
        root_context = self.load(context_name)
        context_names = list_context_and_descendant_names(
            (context_name,),
            self.list_context_names(sort_order="alphabetical"),
        )
        # The selected root supplies receipt and analysis identity.
        return (
            root_context,
            *(self.load(name) for name in context_names if name != context_name),
        )

    def load_for_update(self, name: str) -> Context:
        """Read the Memory frame for an operation that will save its changes."""
        return self.load(name)

    def load_current(self) -> Context:
        name = self.current_context_name()
        if not name:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        return self.load(name)

    def load_current_direct(self) -> Context:
        """Load the current Context through the non-resolving direct path."""
        name = self.current_context_name()
        if not name:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        return self.load_direct(name)

    def load_all_contexts(self) -> tuple[Context, ...]:
        """Load and validate all Contexts in this Profile."""
        record_paths = self.scan_context_catalog()

        contexts: list[Context] = []
        uid_owners: dict[str, str] = {}
        for name, context_file in record_paths:
            try:
                with open(context_file, encoding="utf-8") as file:
                    raw = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
                raise ValueError(f"Context '{name}' is invalid JSON.") from error
            record = _validate_context_header(raw, name)
            # Validate the complete local frame before including its identity.
            try:
                context = Context.from_dict(record)
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"Context '{name}' has an invalid direct record: {error}"
                ) from error
            uid = record["uid"]
            previous = uid_owners.get(uid)
            if previous is not None:
                raise ValueError(
                    f"Ordinary Context uid is duplicated by '{previous}' and '{name}'."
                )
            uid_owners[uid] = name
            contexts.append(context)
        return tuple(contexts)

    def _read_direct_context_records_strict(
        self,
    ) -> dict[str, dict[str, object]]:
        """Return validated canonical records for native publication planning."""
        return {context.name: context.to_dict() for context in self.load_all_contexts()}
