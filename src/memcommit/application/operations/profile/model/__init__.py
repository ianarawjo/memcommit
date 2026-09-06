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
    _inspection_with_grants as _inspection_with_grants,
    _prepare_profile_deletion_batch as _prepare_profile_deletion_batch,
    _publish_permanent_removal as _publish_permanent_removal,
    _query_sources as _query_sources,
    _read_granted_access_names as _read_granted_access_names,
    _read_json as _read_json,
    _registry_lock as _registry_lock,
    _reject_duplicate_keys as _reject_duplicate_keys,
    _rollback_profile_deletion_batch as _rollback_profile_deletion_batch,
    _source_digest as _source_digest,
    _source_store as _source_store,
    _translation_catalogs as _translation_catalogs,
    _write_registry as _write_registry,
    authority_grant_snapshot_lock as authority_grant_snapshot_lock,
    inspect_store as inspect_store,
)

from .grants import (
    ShareEndpoint as ShareEndpoint,
    _assert_access_name_available as _assert_access_name_available,
    _grant_scope as _grant_scope,
    _grant_selector as _grant_selector,
    create_authority_grant as create_authority_grant,
    delete_authority_grant as delete_authority_grant,
    grant_placement as grant_placement,
    list_authority_grants as list_authority_grants,
    resolve_share_endpoint as resolve_share_endpoint,
    update_authority_grant as update_authority_grant,
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
    "ShareEndpoint",
    "StoreInspection",
    "StudyImportResult",
    "StudyProviderPolicyMigrationResult",
    "StudyRemovalResult",
    "StudyRenameResult",
    "StudyRunProfilePair",
    "authority_grant_snapshot_lock",
    "baseline_store_digest",
    "create_authority_grant",
    "create_profile",
    "delete_authority_grant",
    "grant_placement",
    "import_baseline_profile",
    "import_profile",
    "inspect_store",
    "list_authority_grants",
    "list_profiles",
    "migrate_visible_study_provider_policy",
    "remove_profile",
    "remove_study",
    "rename_profile",
    "rename_study",
    "resolve_share_endpoint",
    "study_run_profile_pairs",
    "update_authority_grant",
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

_INIT_STUDY_PROFILE_COMPAT_EXPORTS = {
    "StudyImportResult": "model",
    "_StudyProfileSource": "model",
    "_StudyTaskPackage": "model",
    "_STUDY_BUNDLE_NAMESPACE": "model",
    "_study_run_authority_profile_name": "model",
    "_study_integer": "package",
    "_expected_study_grant_uid": "package",
    "_legacy_study_package": "package",
    "_study_package": "package",
    "_content_digest": "package",
    "_study_catalogs": "package",
    "_study_query_entries": "package",
    "_validate_study_manifest_content": "package",
    "_study_manifest_context": "package",
    "_study_packages": "package",
    "_validate_study_package_grants": "package",
    "_STUDY_PRACTICE_ROOT": "composition",
    "_STUDY_PRACTICE_DESCRIPTION": "composition",
    "_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT": "composition",
    "_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT": "composition",
    "_STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT": "composition",
    "_PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT": "composition",
    "_LEGACY_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT": "composition",
    "_LEGACY_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT": "composition",
    "_LEGACY_PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT": "composition",
    "_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_UID": "composition",
    "_STUDY_PRACTICE_DESCRIPTION_SITUATION_UID": "composition",
    "_STUDY_PRACTICE_DESCRIPTION_TASK_UID": "composition",
    "_LEGACY_STUDY_PRACTICE_PROVENANCE_UID": "composition",
    "_STUDY_PRACTICE_SOURCE": "composition",
    "_STUDY_PRACTICE_SOURCE_CONTENTS": "composition",
    "_LEGACY_SCENARIO_GRANTED_ROOT": "composition",
    "_legacy_scenario_branch": "composition",
    "_study_practice_contexts": "composition",
    "_is_study_practice_name": "composition",
    "_canonicalize_study_practice_description": "composition",
    "_remap_context_records": "composition",
    "_remap_translation_catalogs": "composition",
    "_materialize_study_context_parents": "composition",
    "_write_mapped_study_store": "composition",
    "_compose_legacy_scenario_store": "composition",
    "_STUDY_RUN_SOURCE_KIND": "publication",
    "_STUDY_RUN_GRANTED_SOURCE_KIND": "publication",
    "_materialize_study_grants": "publication",
    "_publish_study_profile_batch": "publication",
}


# Study transactions import this package's storage primitives. Keep their
# aggregate exports lazy so direct transaction imports cannot create a cycle.
_CURRENT_STUDY_EXPORTS = {
    "StudyRunProfilePair": "model",
    "StudyRenameResult": "model",
    "StudyRemovalResult": "model",
    "study_run_profile_pairs": "topology",
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
        from memcommit.application.operations.resource_import import profile

        value = getattr(profile, name)
    else:
        module_name = _INIT_STUDY_PROFILE_COMPAT_EXPORTS.get(name)
        if module_name is None:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        from importlib import import_module

        module = import_module(
            f"memcommit.application.operations.init_study.profile.{module_name}"
        )
        value = getattr(module, name)
    globals()[name] = value
    return value
