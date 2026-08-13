"""Shared-component setup flow for interactive resource import."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.commands.context_picker import (
    ContextMemoryRow,
    ContextMemorySelection,
    choose_context,
    context_memory_rows,
)
from memcommit.commands.context_reach_dialog import choose_context_reach
from memcommit.commands.exact_command_review import ExactCommandReview
from memcommit.commands.exact_command_review_shell import approve_exact_command
from memcommit.commands.exact_name_dialog import choose_exact_name
from memcommit.commands.flat_selection_dialog import choose_flat_option
from memcommit.commands.tui_primitives import ExactNameFieldView
from memcommit.context import Memory, MemoryRef
from memcommit.context_targeting.tui.name_editor import (
    ContextNameView,
    choose_context_name,
)
from memcommit.profile_config import (
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
    validate_profile_name,
)
from memcommit.profiles import ProfileError
from memcommit.resource_import import (
    ContextImportPlan,
    MemoryImportPlan,
    plan_context_import,
    plan_memory_import,
)
from memcommit.selection import SelectionOption
from memcommit.store import MemoryStore, validate_context_name


ImportKind = Literal["PROFILE", "CONTEXT", "MEMORY"]


@dataclass(frozen=True)
class ImportSourceProfile:
    """Name-only source entry; no Profile content is opened for this catalog."""

    uid: str
    name: str
    kind: str


@dataclass(frozen=True)
class ImportSourceCatalog:
    """Frozen source list whose active Profile is deliberately absent."""

    active_profile_uid: str
    sources: tuple[ImportSourceProfile, ...]


@dataclass(frozen=True)
class ImportSetupReceipt:
    """Approved process-local import setup and its revalidation boundary."""

    kind: ImportKind
    source_profile_name: str
    source_profile_uid: str
    review: ExactCommandReview
    target_name: str | None = None
    source_context: str | None = None
    memory_selector: str | None = None
    target_context: str | None = None
    recursive: bool = False
    context_plan: ContextImportPlan | None = None
    memory_plan: MemoryImportPlan | None = None


def freeze_import_source_catalog(
    registry: ProfileRegistry | None = None,
) -> ImportSourceCatalog:
    """Freeze registered non-active Profile names without inspecting stores."""

    frozen_registry = registry or load_profile_registry()
    sources = tuple(
        ImportSourceProfile(profile.uid, profile.name, profile.kind)
        for profile in frozen_registry.visible_profiles
        if profile.uid != frozen_registry.active_uid
    )
    if not sources:
        raise ProfileError(
            "No non-active registered Profile is available as an import source."
        )
    return ImportSourceCatalog(
        active_profile_uid=frozen_registry.active_uid,
        sources=sources,
    )


def _frozen_source_profile(
    catalog: ImportSourceCatalog,
    source: ImportSourceProfile,
) -> ProfileEntry:
    registry = load_profile_registry()
    if registry.active_uid != catalog.active_profile_uid:
        raise ProfileError("Active Profile changed during import setup; reopen it.")
    current = registry.by_name(source.name)
    if (
        current is None
        or registry.is_removed(current)
        or current.uid != source.uid
        or current.uid == registry.active_uid
    ):
        raise ProfileError("Source Profile identity changed during import setup.")
    return current


def _choose_source_profile(
    catalog: ImportSourceCatalog,
    *,
    app_input: Input | None,
    app_output: Output | None,
    require_tty: bool,
) -> ImportSourceProfile | None:
    by_uid = {source.uid: source for source in catalog.sources}
    selected = choose_flat_option(
        tuple(
            SelectionOption(
                source.uid,
                source.name,
                f"{source.kind} · REGISTERED SOURCE",
            )
            for source in catalog.sources
        ),
        title="MEM IMPORT · SOURCE PROFILE",
        detail="Choose one registered source. Profile contents open only after selection.",
        footer_note="CURRENT PROFILE HIDDEN FROM SOURCE LIST",
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    return by_uid[selected.uid] if selected is not None else None


def _import_memory_rows(
    store: MemoryStore, context_name: str
) -> tuple[ContextMemoryRow, ...]:
    context = store.load(context_name)
    projected = context_memory_rows(context)
    display_items = tuple(
        item for item in context.iter_items() if isinstance(item, (Memory, MemoryRef))
    )
    if len(projected) != len(display_items):
        raise ProfileError("Source Memory preview changed during import setup.")
    return tuple(
        replace(row, selector=item.uid if isinstance(item, Memory) else None)
        for row, item in zip(projected, display_items, strict=True)
    )


def _fresh_profile_name(source_name: str, registry: ProfileRegistry) -> str:
    occupied = {profile.name.casefold() for profile in registry.profiles}
    stem = f"{source_name}-import"
    candidate = stem
    suffix = 2
    while candidate.casefold() in occupied:
        candidate = f"{stem}-{suffix}"
        suffix += 1
    return validate_profile_name(candidate)


def _profile_target_validator(registry: ProfileRegistry):
    occupied = {profile.name.casefold() for profile in registry.profiles}

    def validate(value: str) -> None:
        canonical = validate_profile_name(value)
        if canonical.casefold() in occupied:
            raise ProfileError(f"Profile {canonical!r} already exists.")

    return validate


def _context_source_names(
    store: MemoryStore,
    source_name: str,
    *,
    recursive: bool,
) -> tuple[str, ...]:
    names = tuple(store.list_context_names())
    return tuple(
        name
        for name in names
        if name == source_name or (recursive and name.startswith(source_name + "/"))
    )


def _mapped_context_names(
    source_names: tuple[str, ...],
    *,
    source_root: str,
    target_root: str,
) -> tuple[str, ...]:
    return tuple(target_root + name[len(source_root) :] for name in source_names)


def _fresh_context_root(
    source_names: tuple[str, ...],
    *,
    source_root: str,
    destination_names: tuple[str, ...],
) -> str:
    occupied = set(destination_names)
    stem = source_root
    candidate = stem
    suffix = 1
    while any(
        name in occupied
        for name in _mapped_context_names(
            source_names,
            source_root=source_root,
            target_root=candidate,
        )
    ):
        suffix += 1
        candidate = f"{stem}-import" if suffix == 2 else f"{stem}-import-{suffix}"
    return validate_context_name(candidate)


def _context_target_validator(
    source_names: tuple[str, ...],
    *,
    source_root: str,
    destination_names: tuple[str, ...],
):
    occupied = set(destination_names)

    def validate(value: str) -> None:
        target_root = validate_context_name(value)
        collisions = tuple(
            name
            for name in _mapped_context_names(
                source_names,
                source_root=source_root,
                target_root=target_root,
            )
            if name in occupied
        )
        if collisions:
            raise ProfileError(
                "Import destination already exists: " + ", ".join(collisions)
            )

    return validate


def _profile_review(
    source: ImportSourceProfile, target_name: str
) -> ExactCommandReview:
    return ExactCommandReview(
        argv=(
            "mem",
            "import",
            "profile",
            target_name,
            "--from-profile",
            source.name,
        ),
        effects=(
            f"Create new clean-baseline Profile {target_name!r} from {source.name!r}.",
            "Preserve Context and Memory identities; omit operational history.",
            "Do not expose or switch the current Profile.",
        ),
    )


def _context_review(plan: ContextImportPlan, target_name: str) -> ExactCommandReview:
    argv = [
        "mem",
        "import",
        "context",
        plan.source_context,
        "--from-profile",
        plan.source_profile,
        "--as",
        target_name,
    ]
    if plan.recursive:
        argv.append("--recursive")
    return ExactCommandReview(
        argv=tuple(argv),
        effects=(
            f"Create {plan.context_count} new Context(s) in Profile {plan.target_profile!r}.",
            f"Copy {plan.memory_count} directly owned Memory item(s) with stable identities.",
            "Keep source, active Profile selection, and current Context unchanged.",
        ),
    )


def _memory_review(plan: MemoryImportPlan) -> ExactCommandReview:
    return ExactCommandReview(
        argv=(
            "mem",
            "import",
            "memory",
            plan.source_memory_uid,
            "--from-profile",
            plan.source_profile,
            "--context",
            plan.source_context,
            "--into",
            plan.target_context,
        ),
        effects=(
            f"Append Memory [{plan.source_memory_uid[:8]}] to Context {plan.target_context!r}.",
            f"Write only to Profile {plan.target_profile!r} and preserve the Memory UID/content.",
            "Keep source, active Profile selection, and current Context unchanged.",
        ),
    )


def choose_import_setup(
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ImportSetupReceipt | None:
    """Compose shared pickers into one approved import setup."""

    kind_option = choose_flat_option(
        (
            SelectionOption("PROFILE", "PROFILE", "Create one clean baseline Profile."),
            SelectionOption(
                "CONTEXT", "CONTEXT", "Copy one Context or lexical subtree."
            ),
            SelectionOption("MEMORY", "MEMORY", "Copy one directly owned Memory."),
        ),
        title="MEM IMPORT · RESOURCE",
        detail="Choose the identity-preserving resource boundary to import.",
        footer_note="EXTERNAL PATH IMPORT REMAINS AVAILABLE WITH --from PATH",
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if kind_option is None:
        return None
    kind: ImportKind = kind_option.uid  # type: ignore[assignment]

    catalog = freeze_import_source_catalog()
    source = _choose_source_profile(
        catalog,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if source is None:
        return None
    source_profile = _frozen_source_profile(catalog, source)

    if kind == "PROFILE":
        registry = load_profile_registry()
        target_name = choose_exact_name(
            ExactNameFieldView(
                value=_fresh_profile_name(source.name, registry),
                label="NEW PROFILE NAME",
                state="NOT CREATED",
                detail="Edit the exact destination Profile name",
                validate=_profile_target_validator(registry),
                value_label="Profile name",
                strip_candidate=False,
            ),
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
        )
        if target_name is None:
            return None
        _frozen_source_profile(catalog, source)
        review = _profile_review(source, target_name)
        if not approve_exact_command(
            review,
            title="MEM IMPORT · PROFILE · FINAL APPROVAL",
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
        ):
            return None
        return ImportSetupReceipt(
            kind=kind,
            source_profile_name=source.name,
            source_profile_uid=source.uid,
            target_name=target_name,
            review=review,
        )

    source_store = MemoryStore(
        root=profile_store_dir(source_profile),
        create=False,
    )
    source_names = tuple(source_store.list_context_names())
    if not source_names:
        raise ProfileError(f"Source Profile {source.name!r} has no ordinary Contexts.")
    source_current = source_store.current_context_name()

    def memory_loader(name: str) -> tuple[ContextMemoryRow, ...]:
        return _import_memory_rows(source_store, name)

    if kind == "CONTEXT":
        selected_context = choose_context(
            source_names,
            current=(
                source_current if source_current in source_names else source_names[0]
            ),
            title=f"MEM IMPORT · SOURCE CONTEXT · {source.name}",
            accept_label="choose source",
            memory_loader=memory_loader,
            initially_expand_selected=True,
            initially_show_memories=True,
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
        )
        if not isinstance(selected_context, str):
            return None
        recursive = choose_context_reach(
            title="MEM IMPORT · CONTEXT RANGE",
            detail="Choose whether the reviewed source includes lexical descendants.",
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
        )
        if recursive is None:
            return None
        frozen_source_names = _context_source_names(
            source_store,
            selected_context,
            recursive=recursive,
        )
        destination = MemoryStore()
        destination_names = tuple(destination.list_context_names())
        target_name = choose_context_name(
            ContextNameView(
                value=_fresh_context_root(
                    frozen_source_names,
                    source_root=selected_context,
                    destination_names=destination_names,
                ),
                label="IMPORT DESTINATION",
                state="NOT CREATED",
                detail="Edit directly or choose an existing parent; no Context is created yet.",
                validate=_context_target_validator(
                    frozen_source_names,
                    source_root=selected_context,
                    destination_names=destination_names,
                ),
                context_names=destination_names,
                current_context=destination.current_context_name(),
            ),
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
        )
        if target_name is None:
            return None
        plan = plan_context_import(
            source.name,
            selected_context,
            target_name=target_name,
            recursive=recursive,
        )
        if (
            plan.source_profile_uid != source.uid
            or plan.target_profile_uid != catalog.active_profile_uid
        ):
            raise ProfileError(
                "Profile identity changed during import setup; reopen it."
            )
        review = _context_review(plan, target_name)
        if not approve_exact_command(
            review,
            title="MEM IMPORT · CONTEXT · FINAL APPROVAL",
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
        ):
            return None
        return ImportSetupReceipt(
            kind=kind,
            source_profile_name=source.name,
            source_profile_uid=source.uid,
            source_context=selected_context,
            target_name=target_name,
            recursive=recursive,
            context_plan=plan,
            review=review,
        )

    selected_memory = choose_context(
        source_names,
        current=source_current if source_current in source_names else source_names[0],
        title=f"MEM IMPORT · SOURCE MEMORY · {source.name}",
        accept_label="choose Memory",
        memory_loader=memory_loader,
        browse_only=True,
        selectable_memories=True,
        initially_expand_all=True,
        initially_show_memories=True,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if not isinstance(selected_memory, ContextMemorySelection):
        return None
    destination = MemoryStore()
    destination_names = tuple(destination.list_context_names())
    if not destination_names:
        raise ProfileError("The active Profile has no destination Context.")
    target_context = choose_context(
        destination_names,
        current=destination.current_context_name(),
        title="MEM IMPORT · DESTINATION CONTEXT",
        accept_label="choose destination",
        memory_loader=lambda name: context_memory_rows(destination.load(name)),
        initially_expand_selected=True,
        initially_show_memories=True,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if not isinstance(target_context, str):
        return None
    plan = plan_memory_import(
        source.name,
        selected_memory.context_name,
        selected_memory.selector,
        target_context_locator=target_context,
    )
    if (
        plan.source_profile_uid != source.uid
        or plan.target_profile_uid != catalog.active_profile_uid
    ):
        raise ProfileError("Profile identity changed during import setup; reopen it.")
    review = _memory_review(plan)
    if not approve_exact_command(
        review,
        title="MEM IMPORT · MEMORY · FINAL APPROVAL",
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    ):
        return None
    return ImportSetupReceipt(
        kind=kind,
        source_profile_name=source.name,
        source_profile_uid=source.uid,
        source_context=selected_memory.context_name,
        memory_selector=selected_memory.selector,
        target_context=target_context,
        memory_plan=plan,
        review=review,
    )
