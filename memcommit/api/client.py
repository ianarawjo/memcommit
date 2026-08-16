"""Stable Python entry point over reviewed MemCommit application boundaries."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api._support.providers import (
    connect_ordinary_provider,
    connect_route_provider,
)
from memcommit.api.add import AddMemoriesResult
from memcommit.api.errors import (
    QueryConfigurationError,
)
from memcommit.api.meld import (
    MeldApplyResult as PublicMeldApplyResult,
    MeldSessionResult,
)
from memcommit.api.query import (
    GrantedQueryResult,
    OrdinaryQueryResult,
    QueryProviderConfig,
    ReferenceQueryResult,
)
from memcommit.context import QueryContextRef
from memcommit.profile_config import (
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.store import MemoryStore


ProviderFactory = Callable[[], object]
RouteProviderFactory = Callable[[str], object]
StageObserver = Callable[[str], None]


class MemCommitClient:
    """Own one frozen Store boundary and provider configuration snapshot.

    Provider objects remain per-call resources. The client itself owns no open
    endpoint or terminal resource and therefore requires no explicit close.
    """

    def __init__(
        self,
        *,
        root: str | Path | None = None,
        profile: str | None = None,
        create: bool = False,
        query_config: QueryProviderConfig | None = None,
        ordinary_provider_factory: ProviderFactory | None = None,
        query_route_provider_factory: RouteProviderFactory | None = None,
        semantic_provider_factory: ProviderFactory | None = None,
    ) -> None:
        if root is not None and profile is not None:
            raise QueryConfigurationError(
                "Choose either an explicit Store root or a Profile, not both."
            )
        if not isinstance(create, bool):
            raise QueryConfigurationError("Client create must be a boolean.")
        try:
            config = query_config or QueryProviderConfig()
        except (TypeError, ValueError) as error:
            raise_public(QueryConfigurationError, error)
        if not isinstance(config, QueryProviderConfig):
            raise QueryConfigurationError("query_config must be a QueryProviderConfig.")

        registry: ProfileRegistry | None = None
        selected_profile: ProfileEntry | None = None
        try:
            if root is None:
                registry = load_profile_registry()
                if profile is None:
                    selected_profile = registry.active
                else:
                    selected_profile = registry.by_name(profile)
                    if selected_profile is None or registry.is_removed(
                        selected_profile
                    ):
                        raise QueryConfigurationError(
                            f"Profile {profile!r} is not available."
                        )
                store_root = profile_store_dir(selected_profile)
            else:
                store_root = Path(root).expanduser().absolute()
        except QueryConfigurationError:
            raise
        except (OSError, ProfileConfigError, TypeError, ValueError) as error:
            raise_public(QueryConfigurationError, error)

        self._store = MemoryStore(root=store_root, create=create)
        self._store_root = self._store.store_dir.resolve()
        self._registry = registry
        self._profile = selected_profile
        self._query_config = config
        self._ordinary_provider_factory = ordinary_provider_factory or partial(
            connect_ordinary_provider,
            config,
        )
        self._query_route_provider_factory = query_route_provider_factory or partial(
            connect_route_provider,
            config,
        )
        self._semantic_provider_factory = (
            semantic_provider_factory or self._ordinary_provider_factory
        )
        self._runtime = ClientRuntime(
            store=self._store,
            store_root=self._store_root,
            registry=self._registry,
            profile=self._profile,
            query_config=self._query_config,
            ordinary_provider_factory=self._ordinary_provider_factory,
            query_route_provider_factory=self._query_route_provider_factory,
            semantic_provider_factory=self._semantic_provider_factory,
        )

    @property
    def store_root(self) -> Path:
        return self._store_root

    @property
    def profile_name(self) -> str | None:
        return self._profile.name if self._profile is not None else None

    @property
    def query_config(self) -> QueryProviderConfig:
        return self._query_config

    def start_meld(
        self,
        left_context: str,
        right_context: str,
        *,
        mode: str = "directional",
        target_context: str | None = None,
        create_target: bool = False,
        left_descendants: bool = False,
        right_descendants: bool = False,
    ) -> MeldSessionResult:
        """Create one durable reviewed Meld without opening a terminal UI."""

        from memcommit.api._operations.meld import start_meld

        return start_meld(
            self._runtime,
            left_context,
            right_context,
            mode=mode,
            target_context=target_context,
            create_target=create_target,
            left_descendants=left_descendants,
            right_descendants=right_descendants,
        )

    def restart_meld(
        self,
        left_context: str,
        right_context: str,
        target_context: str,
        *,
        expected_version: str,
        mode: str = "directional",
        left_descendants: bool = False,
        right_descendants: bool = False,
    ) -> MeldSessionResult:
        """Replace one exact saved Meld review without deleting its target."""

        from memcommit.api._operations.meld import restart_meld

        return restart_meld(
            self._runtime,
            left_context,
            right_context,
            target_context,
            expected_version=expected_version,
            mode=mode,
            left_descendants=left_descendants,
            right_descendants=right_descendants,
        )

    def open_meld(self, target_context: str) -> MeldSessionResult:
        """Open one exact saved review without provider or mutation."""

        from memcommit.api._operations.meld import open_meld

        return open_meld(self._runtime, target_context)

    def comment_meld(
        self,
        target_context: str,
        comment: str,
        *,
        issue_uid: str | None = None,
        revision: str = "EXTEND",
        revises_turn_uids: Sequence[str] = (),
    ) -> MeldSessionResult:
        """Submit one complete semantic follow-up against a saved version."""

        from memcommit.api._operations.meld import comment_meld

        return comment_meld(
            self._runtime,
            target_context,
            comment,
            issue_uid=issue_uid,
            revision=revision,
            revises_turn_uids=revises_turn_uids,
        )

    def preserve_meld(self, target_context: str) -> MeldSessionResult:
        """Preserve every remaining distinction under the saved-session CAS."""

        from memcommit.api._operations.meld import preserve_meld

        return preserve_meld(self._runtime, target_context)

    def defer_meld(self, target_context: str) -> MeldSessionResult:
        """Close one saved review without changing its target."""

        from memcommit.api._operations.meld import defer_meld

        return defer_meld(self._runtime, target_context)

    def apply_meld(self, target_context: str) -> PublicMeldApplyResult:
        """Apply exactly one ready saved proposal without another provider turn."""

        from memcommit.api._operations.meld import apply_meld

        return apply_meld(self._runtime, target_context)

    def add_memories(
        self,
        contents: Sequence[str],
        *,
        context_name: str | None = None,
    ) -> AddMemoriesResult:
        """Append one exact ordered batch and publish one Add checkpoint."""

        from memcommit.api._operations.add import add_memories

        return add_memories(
            self._runtime,
            contents,
            context_name=context_name,
        )

    def query_ordinary(
        self,
        question: str,
        *,
        context_names: Sequence[str] | None = None,
        include_descendants: bool = False,
        follow_embeds: bool = True,
        on_stage: StageObserver | None = None,
    ) -> OrdinaryQueryResult:
        """Answer from one exact readable Context set without publishing state."""

        from memcommit.api._operations.query import query_ordinary

        return query_ordinary(
            self._runtime,
            question,
            context_names=context_names,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
            on_stage=on_stage,
        )

    def query_granted(
        self,
        public_name: str,
        question: str | None = None,
        *,
        language: str = "en",
        session_name: str | None = None,
        memory_handle: str | None = None,
        federate_descendants: bool = True,
        on_stage: StageObserver | None = None,
    ) -> GrantedQueryResult:
        """Browse or answer one active-Profile QUERY grant.

        When ``session_name`` is supplied, returning successfully means the
        visible turn was also reauthorized and CAS-published.
        """

        from memcommit.api._operations.query import query_granted

        return query_granted(
            self._runtime,
            public_name,
            question,
            language=language,
            session_name=session_name,
            memory_handle=memory_handle,
            federate_descendants=federate_descendants,
            on_stage=on_stage,
        )

    def query_reference(
        self,
        reference: QueryContextRef,
        question: str,
        *,
        language: str = "en",
        on_stage: StageObserver | None = None,
    ) -> ReferenceQueryResult:
        """Answer through one exact legacy QueryContextRef without persistence."""

        from memcommit.api._operations.query import query_reference

        return query_reference(
            self._runtime,
            reference,
            question,
            language=language,
            on_stage=on_stage,
        )


__all__ = ["MemCommitClient"]
