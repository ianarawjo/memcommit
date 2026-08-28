"""Plan and atomically commit Context graph renames."""

from __future__ import annotations

import copy
from contextlib import ExitStack
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable

from memcommit.core.context import Context
from memcommit.core.context_targeting.naming import (
    validate_portable_context_name,
)
from memcommit.core.context_targeting.navigation import (
    rewrite_context_navigation_names,
)

from ..infrastructure.atomic_io import (
    _canonical_json_digest,
    _reject_duplicate_json_keys,
    _write_bytes_atomic,
    _write_json_atomic,
)
from .models import (
    ConcurrentContextUpdateError,
    ContextRenameBinding,
    ContextRenamePlan,
    ContextRenameResult,
    _PreparedContextRename,
)
from .records import (
    _mapped_context_name,
    _rewrite_checkpoint_record,
    _rewrite_context_pointers,
    _validate_context_header,
    canonical_context_record,
    context_record_digest,
    validate_context_name,
)


class _ContextRenameMixin:
    def _read_context_graph_for_rename(
        self,
    ) -> tuple[
        dict[str, dict[str, object]],
        dict[str, dict[str, dict[str, object]]],
    ]:
        """Read every ordinary record and restorable checkpoint fail-closed."""
        records = self._read_direct_context_records_strict()
        checkpoints: dict[str, dict[str, dict[str, object]]] = {}
        for name in records:
            checkpoint_dir = self._checkpoints_dir(name)
            entries: dict[str, dict[str, object]] = {}
            if checkpoint_dir.exists():
                if checkpoint_dir.is_symlink() or not checkpoint_dir.is_dir():
                    raise ValueError(
                        f"Checkpoints for '{name}' are not a safe directory."
                    )
                for checkpoint_file in sorted(checkpoint_dir.iterdir()):
                    if (
                        checkpoint_file.is_symlink()
                        or not checkpoint_file.is_file()
                        or checkpoint_file.suffix != ".json"
                    ):
                        raise ValueError(
                            f"Checkpoints for '{name}' contain an unsafe entry."
                        )
                    try:
                        with open(checkpoint_file, encoding="utf-8") as file:
                            raw_checkpoint = json.load(
                                file,
                                object_pairs_hook=_reject_duplicate_json_keys,
                            )
                    except (json.JSONDecodeError, ValueError) as error:
                        raise ValueError(
                            f"Checkpoint '{checkpoint_file.name}' for '{name}' "
                            "is invalid JSON."
                        ) from error
                    if (
                        not isinstance(raw_checkpoint, dict)
                        or not isinstance(raw_checkpoint.get("uid"), str)
                        or not isinstance(raw_checkpoint.get("timestamp"), str)
                        or not isinstance(raw_checkpoint.get("snapshot"), dict)
                    ):
                        raise ValueError(
                            f"Checkpoint '{checkpoint_file.name}' for '{name}' "
                            "is invalid."
                        )
                    try:
                        _rewrite_checkpoint_record(
                            raw_checkpoint,
                            moved_names_by_uid={},
                        )
                    except ValueError as error:
                        raise ValueError(
                            f"Checkpoint '{checkpoint_file.name}' for '{name}' "
                            f"is invalid: {error}"
                        ) from error
                    entries[checkpoint_file.name] = raw_checkpoint
            checkpoints[name] = entries

        if not records:
            # Keep the later source-not-found message stable; an empty store is
            # not itself corrupt.
            return records, checkpoints
        return records, checkpoints

    def _assert_rename_destination_available(
        self,
        old_name: str,
        new_name: str,
        *,
        records: dict[str, dict[str, object]],
    ) -> None:
        validate_context_name(old_name)
        validate_portable_context_name(new_name)
        if old_name == new_name:
            raise ValueError(
                f"source and destination Context namespaces are the same: '{old_name}'."
            )
        if old_name.startswith(new_name + "/") or new_name.startswith(old_name + "/"):
            raise ValueError(
                "source and destination Context namespaces overlap: "
                f"'{old_name}' → '{new_name}'."
            )

        source_dir = self._context_dir(old_name)
        destination_dir = self._context_dir(new_name)
        if destination_dir.exists() or destination_dir.is_symlink():
            raise FileExistsError(
                f"destination Context namespace '{new_name}' is already occupied."
            )
        try:
            if source_dir.resolve() == destination_dir.resolve(strict=False):
                raise ValueError(
                    "source and destination Context namespaces resolve to the "
                    "same filesystem location; case-only or normalization-only "
                    "renames are not supported."
                )
        except OSError as error:
            raise ValueError(
                "Context namespace paths cannot be resolved safely."
            ) from error

        mapped_names = {
            mapped
            for name in records
            if (mapped := _mapped_context_name(name, old_name, new_name)) is not None
        }
        occupied = mapped_names & (
            set(records)
            - {
                name
                for name in records
                if _mapped_context_name(name, old_name, new_name) is not None
            }
        )
        if occupied:
            raise FileExistsError(
                f"destination Context namespace '{new_name}' is already occupied."
            )

    @staticmethod
    def _context_graph_digest_for_rename(
        records: dict[str, dict[str, object]],
        checkpoints: dict[str, dict[str, dict[str, object]]],
        state: dict[str, object],
        *,
        ground_records: dict[str, dict[str, object]],
        translation_records: dict[str, dict[str, object]],
        meld_records: dict[str, dict[str, object]],
    ) -> str:
        return _canonical_json_digest(
            {
                "contexts": [
                    {
                        "name": name,
                        "record": records[name],
                        "checkpoints": [
                            {"file": filename, "record": record}
                            for filename, record in sorted(
                                checkpoints.get(name, {}).items()
                            )
                        ],
                    }
                    for name in sorted(records)
                ],
                "state": state,
                "grounds": [
                    {"file": name, "record": record}
                    for name, record in sorted(ground_records.items())
                ],
                "translations": [
                    {"file": name, "record": record}
                    for name, record in sorted(translation_records.items())
                ],
                "melds": [
                    {"file": name, "record": record}
                    for name, record in sorted(meld_records.items())
                ],
            }
        )

    def _ground_contract_names_for_rename(self) -> tuple[str, ...]:
        """Return every named Ground whose file must join rename freshness."""
        if not self.ground_sessions_dir.exists():
            if self.ground_sessions_dir.is_symlink():
                raise ValueError("Grounding session storage is invalid.")
            return ()
        if (
            not self.ground_sessions_dir.is_dir()
            or self.ground_sessions_dir.is_symlink()
        ):
            raise ValueError("Grounding session storage is invalid.")
        names: list[str] = []
        for path in sorted(self.ground_sessions_dir.iterdir()):
            if path.name == ".locks" and path.is_dir() and not path.is_symlink():
                continue
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise ValueError("Grounding session storage is invalid.")
            names.append(path.stem)
        return tuple(names)

    def _read_ground_records_for_rename(
        self,
        contract_names: Iterable[str],
    ) -> dict[str, dict[str, object]]:
        from memcommit.application.operations.ground.model import (
            GroundError,
            GroundSession,
        )

        records: dict[str, dict[str, object]] = {}
        for contract_name in contract_names:
            path = self._ground_session_path(contract_name)
            try:
                with open(path, encoding="utf-8") as file:
                    raw = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                session = GroundSession.from_dict(raw)
            except (
                json.JSONDecodeError,
                GroundError,
                OSError,
                ValueError,
            ) as error:
                raise ValueError(
                    f"Saved Ground '{contract_name}' is invalid."
                ) from error
            if session.contract_name != contract_name:
                raise ValueError(
                    f"Saved Ground '{contract_name}' does not match its file."
                )
            records[path.name] = raw
        return records

    @staticmethod
    def _read_translation_records_for_rename() -> dict[str, dict[str, object]]:
        from memcommit.application.operations.translate.view import (
            TranslationCatalog,
            TranslationView,
            TranslationViewError,
        )
        from memcommit.application.operations.translate.view_store import (
            translation_catalog_path,
            translation_view_path,
            translation_views_dir,
        )

        root = translation_views_dir()
        if not root.exists():
            if root.is_symlink():
                raise ValueError("Translation view storage is invalid.")
            return {}
        if not root.is_dir() or root.is_symlink():
            raise ValueError("Translation view storage is invalid.")
        records: dict[str, dict[str, object]] = {}
        for path in sorted(root.iterdir()):
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise ValueError("Translation view storage is invalid.")
            try:
                with open(path, encoding="utf-8") as file:
                    raw = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                if not isinstance(raw, dict):
                    raise ValueError("Translation artifact must be an object.")
                if "revision" in raw:
                    artifact = TranslationCatalog.from_dict(raw)
                    expected_path = translation_catalog_path(
                        artifact.context_uid,
                        artifact.target_language,
                    )
                else:
                    artifact = TranslationView.from_dict(raw)
                    expected_path = translation_view_path(
                        artifact.context_uid,
                        artifact.target_language,
                        artifact.selected_memory_uid,
                    )
                if expected_path != path:
                    raise ValueError(
                        "Translation artifact does not match its storage key."
                    )
            except (
                json.JSONDecodeError,
                TranslationViewError,
                ValueError,
            ) as error:
                raise ValueError(
                    f"Saved translation artifact '{path.name}' is invalid."
                ) from error
            records[path.name] = raw
        return records

    def _read_meld_records_for_rename(self) -> dict[str, dict[str, object]]:
        """Load every target-keyed Meld artifact into rename freshness."""

        from memcommit.application.operations.meld.model import MeldError, MeldSession

        root = self.meld_sessions_dir
        if not root.exists():
            if root.is_symlink():
                raise ValueError("Meld session storage is invalid.")
            return {}
        if not root.is_dir() or root.is_symlink():
            raise ValueError("Meld session storage is invalid.")
        records: dict[str, dict[str, object]] = {}
        for path in sorted(root.iterdir()):
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise ValueError("Meld session storage is invalid.")
            try:
                with open(path, encoding="utf-8") as file:
                    raw = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                session = MeldSession.from_dict(raw)
            except (json.JSONDecodeError, MeldError, OSError, ValueError) as error:
                raise ValueError(
                    f"Saved Meld session '{path.name}' is invalid."
                ) from error
            if path.stem != session.target.context_uid:
                raise ValueError(
                    f"Saved Meld session '{path.name}' does not match its file."
                )
            records[path.name] = raw
        return records

    def _prepare_context_rename_locked(
        self,
        old_name: str,
        new_name: str,
        *,
        ground_contract_names: Iterable[str],
    ) -> _PreparedContextRename:
        """Build validated pre/post images while graph and item locks are held."""
        records, checkpoints = self._read_context_graph_for_rename()
        if old_name not in records:
            raise FileNotFoundError(f"Context '{old_name}' not found.")
        self._assert_rename_destination_available(
            old_name,
            new_name,
            records=records,
        )

        bindings = tuple(
            ContextRenameBinding(
                old_name=name,
                new_name=_mapped_context_name(name, old_name, new_name) or name,
                context_uid=str(records[name]["uid"]),
            )
            for name in sorted(records)
            if _mapped_context_name(name, old_name, new_name) is not None
        )
        moved_names_by_uid = {
            binding.context_uid: (binding.old_name, binding.new_name)
            for binding in bindings
        }

        post_records: dict[str, dict[str, object]] = {}
        changed_owner_names: list[str] = []
        live_reference_count = 0
        for owner_name, record in records.items():
            pre_probe, _, pre_collisions = _rewrite_context_pointers(
                record,
                moved_names_by_uid={},
                rewrite_owner_name=False,
                require_current_pointer_names=True,
            )
            if pre_probe != record:
                raise ValueError(
                    f"Context '{owner_name}' changed during rename validation."
                )
            post, count, post_collisions = _rewrite_context_pointers(
                record,
                moved_names_by_uid=moved_names_by_uid,
                rewrite_owner_name=True,
                require_current_pointer_names=True,
            )
            introduced = set(post_collisions) - set(pre_collisions)
            if introduced:
                raise ValueError(
                    f"Renaming would give Context '{owner_name}' both an "
                    "ordinary and query-only child named "
                    + ", ".join(repr(name) for name in sorted(introduced))
                    + "."
                )
            post_name = (
                _mapped_context_name(owner_name, old_name, new_name) or owner_name
            )
            _validate_context_header(post, post_name)
            try:
                Context.from_dict(post)
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"Renamed Context '{post_name}' would be invalid."
                ) from error
            post_records[owner_name] = post
            live_reference_count += count
            if post != record:
                changed_owner_names.append(owner_name)

        post_checkpoints: dict[str, dict[str, dict[str, object]]] = {}
        checkpoint_reference_count = 0
        for owner_name, entries in checkpoints.items():
            next_entries: dict[str, dict[str, object]] = {}
            for filename, entry in entries.items():
                _, _, pre_collisions = _rewrite_checkpoint_record(
                    entry,
                    moved_names_by_uid={},
                )
                post, count, post_collisions = _rewrite_checkpoint_record(
                    entry,
                    moved_names_by_uid=moved_names_by_uid,
                )
                introduced = set(post_collisions) - set(pre_collisions)
                if introduced:
                    raise ValueError(
                        f"Renaming would make checkpoint '{filename}' in "
                        f"'{owner_name}' ambiguous with query-only child "
                        + ", ".join(repr(name) for name in sorted(introduced))
                        + "."
                    )
                next_entries[filename] = post
                checkpoint_reference_count += count
            post_checkpoints[owner_name] = next_entries

        if self.state_file.is_symlink() or not self.state_file.is_file():
            raise ValueError("Context state storage is invalid.")
        try:
            with open(self.state_file, encoding="utf-8") as file:
                raw_state = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("Context state storage is invalid JSON.") from error
        if not isinstance(raw_state, dict):
            raise ValueError("Context state storage must contain an object.")
        current_before = raw_state.get("current")
        if current_before is not None and not isinstance(current_before, str):
            raise ValueError("Current Context state is invalid.")
        current_after = current_before
        if isinstance(current_before, str):
            mapped_current = _mapped_context_name(
                current_before,
                old_name,
                new_name,
            )
            if mapped_current is not None:
                if current_before not in records:
                    raise ValueError(
                        "Current Context points inside the source namespace but "
                        "does not identify a stored Context."
                    )
                current_after = mapped_current
        post_state = copy.deepcopy(raw_state)
        post_state["current"] = current_after
        rewrite_context_navigation_names(
            post_state,
            lambda candidate: (
                _mapped_context_name(candidate, old_name, new_name) or candidate
            ),
        )

        pre_digest_by_uid = {
            str(record["uid"]): context_record_digest(record)
            for record in records.values()
        }
        post_record_by_uid = {
            str(record["uid"]): record for record in post_records.values()
        }
        post_digest_by_uid = {
            uid: context_record_digest(record)
            for uid, record in post_record_by_uid.items()
        }
        post_name_by_uid = {
            str(record["uid"]): str(record["name"]) for record in post_records.values()
        }
        changed_uids = {str(records[name]["uid"]) for name in changed_owner_names}
        # Rename rewrites both moved Context headers and inbound Context/Memory
        # reference owners. Validate every changed owner against one frozen
        # policy snapshot while all graph Context locks are still held.
        protection = self.write_protection_state()
        for owner_name in changed_owner_names:
            self._assert_context_record_change_allowed(
                records[owner_name],
                post_records[owner_name],
                state=protection,
            )

        ground_records = self._read_ground_records_for_rename(ground_contract_names)
        post_ground_records: dict[str, dict[str, object]] = {}
        ground_frame_count = 0
        from memcommit.application.operations.ground.model import (
            GroundError,
            GroundSession,
        )

        for filename, record in ground_records.items():
            post = copy.deepcopy(record)
            frames = post.get("frames")
            if isinstance(frames, list):
                for frame in frames:
                    if not isinstance(frame, dict):
                        raise ValueError(
                            f"Saved Ground '{filename}' has an invalid frame."
                        )
                    context_uid = frame.get("context_uid")
                    if context_uid not in changed_uids:
                        continue
                    before_frame = copy.deepcopy(frame)
                    frame["context_name"] = post_name_by_uid[context_uid]
                    # Preserve prior staleness. Only a frame that matched the
                    # exact pre-rename record may follow the metadata-only
                    # digest change to the post-rename record.
                    if frame.get("context_digest") == pre_digest_by_uid[context_uid]:
                        frame["context_digest"] = post_digest_by_uid[context_uid]
                    if frame != before_frame:
                        ground_frame_count += 1
            try:
                GroundSession.from_dict(post)
            except GroundError as error:
                raise ValueError(
                    f"Saved Ground '{filename}' cannot follow this rename."
                ) from error
            post_ground_records[filename] = post

        translation_records = self._read_translation_records_for_rename()
        post_translation_records: dict[str, dict[str, object]] = {}
        translation_artifact_count = 0
        from memcommit.application.operations.translate.view import (
            TranslationCatalog,
            TranslationView,
            TranslationViewError,
        )

        for filename, record in translation_records.items():
            post = copy.deepcopy(record)
            context_uid = post.get("context_uid")
            if isinstance(context_uid, str) and context_uid in changed_uids:
                before_artifact = copy.deepcopy(post)
                post["context_name"] = post_name_by_uid[context_uid]
                if (
                    "context_digest" in post
                    and post.get("context_digest") == pre_digest_by_uid[context_uid]
                ):
                    post["context_digest"] = post_digest_by_uid[context_uid]
                if post != before_artifact:
                    translation_artifact_count += 1
            try:
                if "revision" in post:
                    TranslationCatalog.from_dict(post)
                else:
                    TranslationView.from_dict(post)
            except TranslationViewError as error:
                raise ValueError(
                    f"Saved translation artifact '{filename}' cannot follow "
                    "this rename."
                ) from error
            post_translation_records[filename] = post

        meld_records = self._read_meld_records_for_rename()
        post_meld_records: dict[str, dict[str, object]] = {}
        meld_session_count = 0
        from memcommit.application.operations.compare.ledger.model import (
            comparison_canonical_digest,
        )
        from memcommit.application.operations.meld.model import MeldError, MeldSession

        def rewrite_meld_binding(binding: object) -> bool:
            if not isinstance(binding, dict):
                raise ValueError("Saved Meld session has an invalid Context binding.")
            context_uid = binding.get("context_uid")
            if not isinstance(context_uid, str) or context_uid not in changed_uids:
                return False
            binding["context_name"] = post_name_by_uid[context_uid]
            if binding.get("context_digest") == pre_digest_by_uid[context_uid]:
                binding["context_digest"] = post_digest_by_uid[context_uid]
            return True

        for filename, record in meld_records.items():
            post = copy.deepcopy(record)
            changed = rewrite_meld_binding(post.get("target"))
            frames = post.get("frames")
            if not isinstance(frames, list):
                raise ValueError(f"Saved Meld session '{filename}' has invalid frames.")
            for frame in frames:
                changed = rewrite_meld_binding(frame) or changed
            seed = post.get("comparison_seed")
            if isinstance(seed, dict):
                analysis = seed.get("analysis")
                analysis_frames = (
                    analysis.get("frames") if isinstance(analysis, dict) else None
                )
                if not isinstance(analysis_frames, list):
                    raise ValueError(
                        f"Saved Meld session '{filename}' has an invalid Compare seed."
                    )
                seed_changed = False
                for frame in analysis_frames:
                    seed_changed = rewrite_meld_binding(frame) or seed_changed
                if seed_changed:
                    seed["analysis_digest"] = comparison_canonical_digest(analysis)
                    changed = True
            if changed and post.get("state") == "APPLIED":
                raise ValueError(
                    "An applied Meld target or source cannot be renamed until "
                    "its application is undone."
                )
            try:
                MeldSession.from_dict(post)
            except MeldError as error:
                raise ValueError(
                    f"Saved Meld session '{filename}' cannot follow this rename."
                ) from error
            if changed:
                meld_session_count += 1
            post_meld_records[filename] = post

        graph_digest = self._context_graph_digest_for_rename(
            records,
            checkpoints,
            raw_state,
            ground_records=ground_records,
            translation_records=translation_records,
            meld_records=meld_records,
        )
        plan = ContextRenamePlan(
            old_name=old_name,
            new_name=new_name,
            bindings=bindings,
            changed_owner_names=tuple(sorted(changed_owner_names)),
            reference_count=live_reference_count,
            checkpoint_reference_count=checkpoint_reference_count,
            ground_frame_count=ground_frame_count,
            translation_artifact_count=translation_artifact_count,
            meld_session_count=meld_session_count,
            current_before=current_before,
            current_after=current_after,
            graph_digest=graph_digest,
        )
        return _PreparedContextRename(
            plan=plan,
            records=records,
            post_records=post_records,
            checkpoints=checkpoints,
            post_checkpoints=post_checkpoints,
            state=raw_state,
            post_state=post_state,
            ground_records=ground_records,
            post_ground_records=post_ground_records,
            translation_records=translation_records,
            post_translation_records=post_translation_records,
            meld_records=meld_records,
            post_meld_records=post_meld_records,
        )

    @staticmethod
    def _rename_lock_names(
        records: dict[str, dict[str, object]],
        old_name: str,
        new_name: str,
    ) -> tuple[str, ...]:
        names = set(records)
        names.update(
            mapped
            for name in records
            if (mapped := _mapped_context_name(name, old_name, new_name)) is not None
        )
        # Lock the exact requested destination even when the source scan is
        # corrupt or empty so a cooperative creator cannot claim it between
        # validation and the stable error/result.
        names.add(new_name)
        return tuple(sorted(names))

    def plan_context_rename(
        self,
        old_name: str,
        new_name: str,
    ) -> ContextRenamePlan:
        """Return one exact, read-only namespace migration preview."""
        # The Source may be a legacy name that exists precisely so this
        # migration can retire it. Only the new canonical locator must satisfy
        # the portable creation contract.
        validate_context_name(old_name)
        validate_portable_context_name(new_name)
        with self._context_graph_lock(exclusive=True):
            records, _ = self._read_context_graph_for_rename()
            lock_names = self._rename_lock_names(records, old_name, new_name)
            ground_names = self._ground_contract_names_for_rename()
            with self._context_write_locks(lock_names):
                with self._state_write_lock():
                    with ExitStack() as grounds:
                        for contract_name in ground_names:
                            grounds.enter_context(
                                self._ground_session_write_lock(contract_name)
                            )
                        return self._prepare_context_rename_locked(
                            old_name,
                            new_name,
                            ground_contract_names=ground_names,
                        ).plan

    def _commit_context_rename_locked(
        self,
        prepared: _PreparedContextRename,
    ) -> ContextRenameResult:
        """Publish prepared images with exception rollback under all locks.

        The current prototype guarantees exception atomicity across the graph.
        A durable crash-recovery journal remains a documented boundary, just
        as for the existing multi-Context update transaction.
        """
        plan = prepared.plan
        name_mapping = {binding.old_name: binding.new_name for binding in plan.bindings}
        source_dir = self._context_dir(plan.old_name)
        destination_dir = self._context_dir(plan.new_name)
        destination_parent = destination_dir.parent

        def live_name(owner_name: str) -> str:
            return name_mapping.get(owner_name, owner_name)

        restore_files: dict[Path, bytes] = {}
        changed_context_paths: list[tuple[Path, dict[str, object]]] = []
        changed_checkpoint_paths: list[tuple[Path, dict[str, object]]] = []
        changed_ground_paths: list[tuple[Path, dict[str, object]]] = []
        changed_translation_paths: list[tuple[Path, dict[str, object]]] = []
        changed_meld_paths: list[tuple[Path, dict[str, object]]] = []

        for owner_name in plan.changed_owner_names:
            before_path = self._context_file(owner_name)
            after_path = self._context_file(live_name(owner_name))
            restore_files[after_path] = before_path.read_bytes()
            changed_context_paths.append(
                (after_path, prepared.post_records[owner_name])
            )
        for owner_name, entries in prepared.checkpoints.items():
            for filename, before in entries.items():
                after = prepared.post_checkpoints[owner_name][filename]
                if after == before:
                    continue
                before_path = self._checkpoints_dir(owner_name) / filename
                after_path = self._checkpoints_dir(live_name(owner_name)) / filename
                restore_files[after_path] = before_path.read_bytes()
                changed_checkpoint_paths.append((after_path, after))
        for filename, before in prepared.ground_records.items():
            after = prepared.post_ground_records[filename]
            if after == before:
                continue
            path = self.ground_sessions_dir / filename
            restore_files[path] = path.read_bytes()
            changed_ground_paths.append((path, after))
        if prepared.translation_records:
            from memcommit.application.operations.translate.view_store import (
                translation_views_dir,
            )

            translation_root = translation_views_dir()
            for filename, before in prepared.translation_records.items():
                after = prepared.post_translation_records[filename]
                if after == before:
                    continue
                path = translation_root / filename
                restore_files[path] = path.read_bytes()
                changed_translation_paths.append((path, after))
        for filename, before in prepared.meld_records.items():
            after = prepared.post_meld_records[filename]
            if after == before:
                continue
            path = self.meld_sessions_dir / filename
            restore_files[path] = path.read_bytes()
            changed_meld_paths.append((path, after))
        if prepared.post_state != prepared.state:
            restore_files[self.state_file] = self.state_file.read_bytes()

        timestamp = datetime.now()
        checkpoint_paths: list[Path] = []
        checkpoint_writes: list[tuple[Path, dict[str, object]]] = []
        for owner_name in plan.changed_owner_names:
            owner_after = live_name(owner_name)
            checkpoint_uid = str(uuid.uuid4())
            description = (
                f"Renamed Context namespace '{plan.old_name}' to "
                f"'{plan.new_name}'; updated '{owner_name}'"
                + (
                    f" to '{owner_after}'."
                    if owner_name != owner_after
                    else " references."
                )
            )
            checkpoint = {
                "uid": checkpoint_uid,
                "message": description,
                "timestamp": timestamp.isoformat(),
                "snapshot": canonical_context_record(prepared.post_records[owner_name]),
                "command": "rename",
                "args": {
                    "old_name": plan.old_name,
                    "new_name": plan.new_name,
                    "context_uid": prepared.records[owner_name]["uid"],
                    "owner_before": owner_name,
                    "owner_after": owner_after,
                },
                "description": description,
                "auto": True,
            }
            checkpoint_dir = self._checkpoints_dir(owner_after)
            filename = (
                f"{timestamp.strftime('%Y%m%dT%H%M%S')}-rename-"
                f"{checkpoint_uid[:8]}.json"
            )
            path = checkpoint_dir / filename
            checkpoint_paths.append(path)
            checkpoint_writes.append((path, checkpoint))

        source_moved = False
        try:
            destination_parent.mkdir(parents=True, exist_ok=True)
            # Recheck immediately before publication. Cooperative Context
            # creators are excluded by the graph lock; this explicit check
            # also prevents Path.rename from replacing a pre-existing empty
            # destination directory on platforms that permit that behavior.
            if destination_dir.exists() or destination_dir.is_symlink():
                raise FileExistsError(
                    f"destination Context namespace '{plan.new_name}' is "
                    "already occupied."
                )
            source_dir.rename(destination_dir)
            source_moved = True

            for path, record in changed_context_paths:
                _write_json_atomic(path, record)
            for path, record in changed_checkpoint_paths:
                _write_json_atomic(path, record)
            for path, record in changed_ground_paths:
                _write_json_atomic(path, record)
            for path, record in changed_translation_paths:
                _write_json_atomic(path, record)
            for path, record in changed_meld_paths:
                _write_json_atomic(path, record)
            for path, record in checkpoint_writes:
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists() or path.is_symlink():
                    raise FileExistsError(
                        "Rename checkpoint destination unexpectedly exists."
                    )
                _write_json_atomic(path, record)
            if prepared.post_state != prepared.state:
                _write_json_atomic(self.state_file, prepared.post_state)

            for binding in plan.bindings:
                if self.context_exists(binding.old_name):
                    raise RuntimeError(
                        f"Old Context '{binding.old_name}' remains after rename."
                    )
                renamed = self.load_direct(binding.new_name)
                if renamed.uid != binding.context_uid:
                    raise RuntimeError(
                        f"Renamed Context '{binding.new_name}' changed identity."
                    )
            for owner_name in plan.changed_owner_names:
                expected = canonical_context_record(prepared.post_records[owner_name])
                actual = canonical_context_record(
                    self.load_direct(live_name(owner_name))
                )
                if actual != expected:
                    raise RuntimeError(
                        f"Renamed Context '{live_name(owner_name)}' failed "
                        "post-publication verification."
                    )
            if self._read_state() != prepared.post_state:
                raise RuntimeError(
                    "Current Context state failed post-rename verification."
                )
            for filename, expected in prepared.post_meld_records.items():
                path = self.meld_sessions_dir / filename
                with open(path, encoding="utf-8") as file:
                    actual = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                if actual != expected:
                    raise RuntimeError(
                        f"Meld session '{filename}' failed post-rename verification."
                    )
        except Exception as error:
            rollback_error: Exception | None = None
            for path in checkpoint_paths:
                try:
                    if path.exists() and not path.is_symlink():
                        path.unlink()
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
            for path, original in restore_files.items():
                try:
                    if path.exists() and not path.is_symlink():
                        _write_bytes_atomic(path, original)
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
            if source_moved:
                try:
                    if source_dir.exists() or source_dir.is_symlink():
                        raise RuntimeError(
                            "Source namespace reappeared during rollback."
                        )
                    destination_dir.rename(source_dir)
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
            self._prune_empty_namespace_dirs(destination_parent)
            if rollback_error is not None:
                raise RuntimeError(
                    "Context rename failed and could not be fully rolled back."
                ) from rollback_error
            raise error

        self._prune_empty_namespace_dirs(source_dir.parent)
        return ContextRenameResult(
            renamed_context_count=len(plan.bindings),
            changed_owner_count=len(plan.changed_owner_names),
            reference_count=plan.reference_count,
            checkpoint_reference_count=plan.checkpoint_reference_count,
            ground_frame_count=plan.ground_frame_count,
            translation_artifact_count=plan.translation_artifact_count,
            meld_session_count=plan.meld_session_count,
            current_context=plan.current_after,
        )

    def rename_contexts(
        self,
        plan: ContextRenamePlan,
    ) -> ContextRenameResult:
        """Apply one namespace rename outside concurrent command restores."""
        with self._command_write_lock():
            self._assert_profile_write_allowed()
            return self._rename_contexts_command_locked(plan)

    def _rename_contexts_command_locked(
        self,
        plan: ContextRenamePlan,
    ) -> ContextRenameResult:
        """Apply exactly one previously reviewed Context namespace plan."""
        if not isinstance(plan, ContextRenamePlan):
            raise TypeError("Expected a ContextRenamePlan.")
        validate_context_name(plan.old_name)
        validate_portable_context_name(plan.new_name)
        with self._context_graph_lock(exclusive=True):
            records, _ = self._read_context_graph_for_rename()
            lock_names = self._rename_lock_names(
                records,
                plan.old_name,
                plan.new_name,
            )
            ground_names = self._ground_contract_names_for_rename()
            with self._context_write_locks(lock_names):
                with self._state_write_lock():
                    with ExitStack() as grounds:
                        for contract_name in ground_names:
                            grounds.enter_context(
                                self._ground_session_write_lock(contract_name)
                            )
                        prepared = self._prepare_context_rename_locked(
                            plan.old_name,
                            plan.new_name,
                            ground_contract_names=ground_names,
                        )
                        if prepared.plan != plan:
                            raise ConcurrentContextUpdateError(
                                "The Context graph changed after the rename was "
                                "reviewed; nothing was renamed."
                            )
                        return self._commit_context_rename_locked(prepared)
