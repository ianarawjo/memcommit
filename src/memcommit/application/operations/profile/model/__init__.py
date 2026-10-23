"""Profile control-plane application services grouped by responsibility."""

from ._storage import (
    ContextInventory as ContextInventory,
    ProfileError as ProfileError,
    StoreInspection as StoreInspection,
    _assert_plain_tree as _assert_plain_tree,
    _context_record_at as _context_record_at,
    _context_records as _context_records,
    _copy_store as _copy_store,
    _destroy_profile_deletion_batch as _destroy_profile_deletion_batch,
    _ensure_control_dirs as _ensure_control_dirs,
    _fsync_directory as _fsync_directory,
    _prepare_profile_deletion_batch as _prepare_profile_deletion_batch,
    _publish_permanent_removal as _publish_permanent_removal,
    _read_json as _read_json,
    _registry_lock as _registry_lock,
    _reject_duplicate_keys as _reject_duplicate_keys,
    _rollback_profile_deletion_batch as _rollback_profile_deletion_batch,
    _source_digest as _source_digest,
    _source_store as _source_store,
    _translation_catalogs as _translation_catalogs,
    _write_registry as _write_registry,
    inspect_store as inspect_store,
)


from .lifecycle import (
    ProfileCreationResult as ProfileCreationResult,
    ProfileRemovalResult as ProfileRemovalResult,
    ProfileRenameResult as ProfileRenameResult,
    _profile_study_target as _profile_study_target,
    _write_empty_profile_store as _write_empty_profile_store,
    create_profile as create_profile,
    import_profile as import_profile,
    list_profiles as list_profiles,
    remove_profile as remove_profile,
    rename_profile as rename_profile,
    use_profile as use_profile,
)

__all__ = [
    "ContextInventory",
    "ProfileCreationResult",
    "ProfileError",
    "ProfileRemovalResult",
    "ProfileRenameResult",
    "StoreInspection",
    "StudyImportResult",
    "StudyProviderPolicyMigrationResult",
    "StudyRemovalResult",
    "StudyRenameResult",
    "StudyRunProfileGroup",
    "baseline_store_digest",
    "create_profile",
    "import_baseline_profile",
    "import_profile",
    "inspect_store",
    "list_profiles",
    "migrate_visible_study_provider_policy",
    "remove_profile",
    "remove_study",
    "rename_profile",
    "rename_study",
    "group_study_run_profiles",
    "use_profile",
]


_MEM_IMPORT_COMPAT_EXPORTS = {
    "_BASELINE_TOP_LEVEL_DIRECTORIES",
    "_baseline_import_provenance",
    "_baseline_store_files",
    "_copy_store_baseline",
    "_publish_baseline_profile_locked",
    "baseline_store_digest",
    "import_baseline_profile",
}


# Study transactions import this package's storage primitives. Keep their
# aggregate exports lazy so direct transaction imports cannot create a cycle.
_CURRENT_STUDY_EXPORTS = {
    "StudyRunProfileGroup": "model",
    "StudyRenameResult": "model",
    "StudyRemovalResult": "model",
    "group_study_run_profiles": "topology",
    "rename_study": "lifecycle",
    "remove_study": "lifecycle",
    "StudyProviderPolicyMigrationResult": "provider_policy_migration",
    "migrate_visible_study_provider_policy": "provider_policy_migration",
}


def __getattr__(name: str):
    """Lazily preserve names relocated from the aggregate Profile model."""

    if name in _CURRENT_STUDY_EXPORTS:
        from importlib import import_module

        module = import_module(
            f"memcommit.application.operations.profile.study.{_CURRENT_STUDY_EXPORTS[name]}"
        )
        value = getattr(module, name)
    elif name in _MEM_IMPORT_COMPAT_EXPORTS:
        from memcommit.application.operations.mem_import import profile

        value = getattr(profile, name)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value
