"""Compose validated Study inputs into one participant/authority run pair."""

from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from memcommit.context import Context, Memory
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    canonical_grant_permissions,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    _LEGACY_SCENARIO_GRANTED_ROOT,
    _STUDY_PRACTICE_DESCRIPTION,
    _STUDY_PRACTICE_ROOT,
    _STUDY_PRACTICE_SOURCE,
    _STUDY_TASKS,
    _StudyProfileSource,
    _StudyTaskPackage,
    _canonicalize_study_practice_description,
    _context_records,
    _compose_legacy_scenario_store,
    _expected_study_grant_uid,
    _is_study_practice_name,
    _remap_context_records,
    _remap_translation_catalogs,
    _legacy_scenario_branch,
    _study_catalogs,
    _study_packages,
    _study_practice_contexts,
    _validate_study_package_grants,
    _write_mapped_study_store,
)
from memcommit.application.operations.translate.view import TranslationCatalog


def _query_view_count_for_baseline(
    contexts: dict[str, Context],
    templates: tuple[dict[str, object], ...],
) -> int:
    memories: set[str] = set()
    for template in templates:
        try:
            permissions = canonical_grant_permissions(template.get("permissions"))
        except (ProfileConfigError, ValueError) as error:
            raise ProfileError(
                "Study baseline grant permissions are invalid."
            ) from error
        if "QUERY" not in permissions:
            continue
        identity = template.get("authority_context")
        exclusions = template.get("excluded_contexts")
        recursive = template.get("recursive")
        if (
            not isinstance(identity, dict)
            or not isinstance(identity.get("name"), str)
            or not isinstance(exclusions, list)
            or not isinstance(recursive, bool)
        ):
            raise ProfileError("Study baseline query grant scope is invalid.")
        root = identity["name"]
        excluded_names = {
            item.get("name") for item in exclusions if isinstance(item, dict)
        }
        if len(excluded_names) != len(exclusions):
            raise ProfileError("Study baseline query exclusions are invalid.")
        selected = [
            context
            for name, context in contexts.items()
            if (name == root or (recursive and name.startswith(root + "/")))
            and not any(
                name == excluded or name.startswith(str(excluded) + "/")
                for excluded in excluded_names
            )
        ]
        if not selected or selected[0].name != root:
            raise ProfileError("Study baseline query grant root is missing.")
        memories.update(
            item.uid
            for context in selected
            for item in context.iter_items()
            if isinstance(item, Memory)
        )
    return len(memories)


def _snapshot_legacy_scenario(
    baseline_root: Path,
    task_records: dict[int, dict[str, object]],
    destination: Path,
) -> dict[int, _StudyTaskPackage]:
    root = Path(baseline_root)
    contexts, query_refs = _context_records(root)
    if query_refs:
        raise ProfileError(
            "Study baseline granted material must be editable ordinary Contexts."
        )
    structural = {
        *(f"task-{task}" for task in _STUDY_TASKS),
        _LEGACY_SCENARIO_GRANTED_ROOT,
        *(f"{_LEGACY_SCENARIO_GRANTED_ROOT}/task-{task}" for task in _STUDY_TASKS),
    }
    practice_names = {
        _STUDY_PRACTICE_ROOT,
        _STUDY_PRACTICE_DESCRIPTION,
        _STUDY_PRACTICE_SOURCE,
    }
    present_practice_names = practice_names.intersection(contexts)
    if present_practice_names and present_practice_names != practice_names:
        raise ProfileError("Study baseline practice topology is incomplete.")
    expected = set(structural)
    expected.update(present_practice_names)
    for task in _STUDY_TASKS:
        for authority in (False, True):
            branch = _legacy_scenario_branch(task, authority=authority)
            expected.update(name for name in contexts if name.startswith(branch + "/"))
    if set(contexts) != expected:
        extras = sorted(set(contexts) - expected)
        missing = sorted(expected - set(contexts))
        detail = extras or missing
        raise ProfileError(
            "Study baseline Context topology is invalid: " + ", ".join(detail)
        )
    catalogs = _study_catalogs(root)
    if any(name in structural for name, _language in catalogs):
        raise ProfileError(
            "Study baseline structural Contexts cannot own translations."
        )

    packages: dict[int, _StudyTaskPackage] = {}
    for task in _STUDY_TASKS:
        raw = task_records[task]
        sources: list[_StudyProfileSource] = []
        role_contexts: dict[str, dict[str, Context]] = {}
        for authority in (False, True):
            role = "AUTHORITY" if authority else "TASK"
            source_name = (
                raw["authority_profile_name"] if authority else raw["task_profile_name"]
            )
            assert isinstance(source_name, str)
            branch = _legacy_scenario_branch(task, authority=authority)
            selected = {
                name: context
                for name, context in contexts.items()
                if name.startswith(branch + "/")
            }
            if task == 1 and not authority:
                practice = (
                    {name: contexts[name] for name in sorted(present_practice_names)}
                    if present_practice_names
                    else {
                        context.name: context for context in _study_practice_contexts()
                    }
                )
                practice = _canonicalize_study_practice_description(practice)
                selected.update(practice)
            if not selected:
                raise ProfileError(f"Study baseline branch {branch!r} is empty.")
            mapping = {
                name: (
                    name if _is_study_practice_name(name) else name[len(branch) + 1 :]
                )
                for name in selected
            }
            remapped = _remap_context_records(selected, mapping)
            branch_catalogs = tuple(
                replace(catalog, context_name=mapping[name])
                for (name, _language), catalog in sorted(catalogs.items())
                if name in selected
            )
            current_field = (
                "authority_current_context" if authority else "task_current_context"
            )
            current = raw[current_field]
            assert isinstance(current, str)
            store_root = destination / source_name
            inspection = _write_mapped_study_store(
                store_root,
                contexts=remapped,
                catalogs=branch_catalogs,
                current_context=current,
            )
            role_contexts[role] = {context.name: context for context in remapped}
            sources.append(
                _StudyProfileSource(
                    task=task,
                    name=source_name,
                    role=role,
                    store=store_root,
                    entries=(),
                    inspection=inspection,
                )
            )
        templates = tuple(copy.deepcopy(raw["grant_templates"]))
        packages[task] = _StudyTaskPackage(
            task=task,
            schema_version=2,
            manifest={"canonical_language": raw["canonical_language"]},
            manifest_digest=str(raw["manifest_sha256"]),
            profiles=tuple(sources),
            grant_templates=templates,
            query_view_count=_query_view_count_for_baseline(
                role_contexts["AUTHORITY"],
                templates,
            ),
        )
    return packages


def _legacy_study_packages(
    destination: Path,
) -> tuple[dict[int, _StudyTaskPackage], str]:
    """Materialize the packaged Legacy fixture through the former baseline path.

    The intermediate store is deliberately process-local. It preserves the
    exact Practice normalization and Task/authority remapping that the removed
    editable baseline used to provide without publishing an installation
    prerequisite in the Profile registry.
    """

    from memcommit.study_scenarios.legacy import LEGACY_DIGEST
    from memcommit.study_scenarios.legacy.bundle import build_all_study_bundles

    bundle_root = destination / "bundles"
    build_all_study_bundles(bundle_root)
    source_packages = _study_packages(bundle_root)
    _validate_study_package_grants(source_packages)

    baseline_root = destination / "baseline"
    _compose_legacy_scenario_store(source_packages, baseline_root)

    task_records: dict[int, dict[str, object]] = {}
    for task, package in source_packages.items():
        task_source = next(
            source for source in package.profiles if source.role == "TASK"
        )
        authority_source = next(
            source for source in package.profiles if source.role == "AUTHORITY"
        )
        task_records[task] = {
            "manifest_sha256": package.manifest_digest,
            "canonical_language": package.manifest.get("canonical_language"),
            "task_profile_name": task_source.name,
            "authority_profile_name": authority_source.name,
            "task_current_context": task_source.inspection.current_context,
            "authority_current_context": authority_source.inspection.current_context,
            "grant_templates": list(package.grant_templates),
        }

    packages = _snapshot_legacy_scenario(
        baseline_root,
        task_records,
        destination / "snapshots",
    )
    # Translation-catalog audit timestamps are intentionally created at build
    # time, so a raw staging-tree digest would make identical scenario inputs
    # look different. Manifest digests cover the reviewed task and authority
    # data; the canonical Practice records cover the only added scenario data.
    scenario_material = json.dumps(
        {
            "schema_version": 1,
            "task_manifests": [
                packages[task].manifest_digest for task in sorted(packages)
            ],
            "practice_contexts": [
                context.to_dict() for context in _study_practice_contexts()
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    scenario_digest = hashlib.sha256(scenario_material).hexdigest()
    if scenario_digest != LEGACY_DIGEST:
        raise ProfileError(
            "Legacy scenario content changed without updating its reviewed digest."
        )
    return packages, scenario_digest


def _coffee_study_packages(destination: Path) -> dict[int, _StudyTaskPackage]:
    """Materialize fresh package sources for the built-in Coffee scenario.

    These sources are transient inputs to the same two-Profile publication
    boundary used by the legacy baseline.  Their Context names are already the
    public runtime names, so composing them must not add a second ``task-N``
    prefix.
    """

    from memcommit.study_scenarios.coffee import build_coffee_scenario

    scenario = build_coffee_scenario()
    packages: dict[int, _StudyTaskPackage] = {}
    for task_spec in scenario.tasks:
        task = task_spec.task
        participant_name = f"coffee-task-{task}-participant"
        authority_name = f"coffee-task-{task}-authority"
        sources: list[_StudyProfileSource] = []
        contexts_by_role: dict[str, dict[str, Context]] = {}
        for role, name, contexts, catalogs, current in (
            (
                "TASK",
                participant_name,
                task_spec.participant_contexts,
                task_spec.participant_catalogs,
                task_spec.participant_current,
            ),
            (
                "AUTHORITY",
                authority_name,
                task_spec.authority_contexts,
                task_spec.authority_catalogs,
                task_spec.authority_current,
            ),
        ):
            store_root = destination / name
            inspection = _write_mapped_study_store(
                store_root,
                contexts=contexts,
                catalogs=catalogs,
                current_context=current,
            )
            materialized, query_refs = _context_records(store_root)
            if query_refs:
                raise ProfileError(
                    "Built-in Study scenarios cannot contain query pointers."
                )
            contexts_by_role[role] = materialized
            sources.append(
                _StudyProfileSource(
                    task=task,
                    name=name,
                    role=role,
                    store=store_root,
                    entries=(),
                    inspection=inspection,
                )
            )

        templates: list[dict[str, object]] = []
        for grant in task_spec.grants:
            authority_context = contexts_by_role["AUTHORITY"][grant.authority_context]
            attachment_context = contexts_by_role["TASK"][grant.attachment_context]
            templates.append(
                {
                    "schema_version": 1,
                    "key": grant.key,
                    "grant_uid": _expected_study_grant_uid(task, grant.key),
                    "authority_profile": authority_name,
                    "grantee_profile": participant_name,
                    "authority_context": {
                        "uid": authority_context.uid,
                        "name": authority_context.name,
                    },
                    "attachment": {
                        "kind": "GRANTEE_CONTEXT",
                        "context": {
                            "uid": attachment_context.uid,
                            "name": attachment_context.name,
                        },
                    },
                    "public_name": grant.public_name,
                    "permissions": list(grant.permissions),
                    "recursive": grant.recursive,
                    "excluded_contexts": [],
                }
            )
        template_tuple = tuple(templates)
        packages[task] = _StudyTaskPackage(
            task=task,
            schema_version=2,
            manifest={
                "canonical_language": "en",
                # Legacy bundle Contexts are task-relative and need prefixing;
                # this scenario declares the final public hierarchy directly.
                "runtime_names_pre_namespaced": True,
                "scenario_id": scenario.scenario_id,
            },
            manifest_digest=scenario.digest,
            profiles=tuple(sources),
            grant_templates=template_tuple,
            query_view_count=_query_view_count_for_baseline(
                contexts_by_role["AUTHORITY"],
                template_tuple,
            ),
        )
    return packages


def _prefix_study_grant_template(
    raw: dict[str, object],
    *,
    task: int,
) -> dict[str, object]:
    """Map one package grant into the two-Profile run namespace."""

    result = copy.deepcopy(raw)
    prefix = f"task-{task}"

    key = result.get("key")
    if task == 1 and key == "task-1-campus-wiki-view":
        permissions = result.get("permissions")
        if isinstance(permissions, list):
            # Older editable baselines predate explicit whole-wiki query and
            # delete permissions. Keep them initializable while preserving the
            # current Task 1 operation contract in every newly created run.
            if "DELETE" not in permissions:
                permissions.append("DELETE")
            if "QUERY" not in permissions:
                permissions.append("QUERY")
            for permission in (
                "EMBED",
                "DERIVE",
                "COMBINE",
                "EXPORT",
                "ACCEPT_DERIVED",
                "SAVE_BOUND_ANALYSIS",
                "SAVE_ANALYSIS",
            ):
                if permission not in permissions:
                    permissions.append(permission)
        result.setdefault("provider", "codex_chatgpt")
    elif key in {
        "task-2-advisor1-view",
        "task-2-advisor2-view",
    }:
        permissions = result.get("permissions")
        if isinstance(permissions, list):
            # Existing baselines remain importable, but each new Study run
            # receives the current source-side derivation contract.
            for permission in (
                "EMBED",
                "DERIVE",
                "COMBINE",
                "EXPORT",
                "SAVE_BOUND_ANALYSIS",
                "SAVE_ANALYSIS",
            ):
                if permission not in permissions:
                    permissions.append(permission)

    if key == "task-3-healthcare-transmission-guidance-view":
        permissions = result.get("permissions")
        if isinstance(permissions, list) and "EMBED" not in permissions:
            # Editable baselines created before revocable links remain usable,
            # while new Study runs expose the current Task 3 source contract.
            permissions.append("EMBED")

    authority_context = result.get("authority_context")
    if isinstance(authority_context, dict) and isinstance(
        authority_context.get("name"), str
    ):
        authority_context["name"] = f"{prefix}/{authority_context['name']}"
    exclusions = result.get("excluded_contexts")
    if isinstance(exclusions, list):
        for exclusion in exclusions:
            if isinstance(exclusion, dict) and isinstance(exclusion.get("name"), str):
                exclusion["name"] = f"{prefix}/{exclusion['name']}"

    attachment = result.get("attachment")
    if isinstance(attachment, dict) and attachment.get("kind") == "GRANTEE_CONTEXT":
        context = attachment.get("context")
        if isinstance(context, dict) and isinstance(context.get("name"), str):
            context["name"] = f"{prefix}/{context['name']}"
        public_name = result.get("public_name")
        if isinstance(public_name, str):
            # The public path is deliberately task-local while the attachment
            # stays the exact participant Context required by the grant model.
            result["public_name"] = f"{prefix}/{public_name}"
    return result


def _compose_study_run_pair(
    packages: dict[int, _StudyTaskPackage],
    *,
    participant_root: Path,
    authority_root: Path,
) -> dict[int, _StudyTaskPackage]:
    """Write two run-private stores and return grant-ready package views."""

    participant_contexts: list[Context] = []
    authority_contexts: list[Context] = []
    participant_catalogs: list[TranslationCatalog] = []
    authority_catalogs: list[TranslationCatalog] = []

    for task in _STUDY_TASKS:
        package = packages[task]
        pre_namespaced = package.manifest.get("runtime_names_pre_namespaced") is True
        for authority in (False, True):
            role = "AUTHORITY" if authority else "TASK"
            source = next(item for item in package.profiles if item.role == role)
            source_contexts, query_refs = _context_records(source.store)
            if query_refs:
                raise ProfileError("Study run sources cannot contain query pointers.")
            mapping = {
                name: (
                    name
                    if pre_namespaced
                    or (task == 1 and not authority and _is_study_practice_name(name))
                    else f"task-{task}/{name}"
                )
                for name in source_contexts
            }
            remapped = _remap_context_records(source_contexts, mapping)
            catalogs = _remap_translation_catalogs(source.store, mapping)
            if authority:
                authority_contexts.extend(remapped)
                authority_catalogs.extend(catalogs)
            else:
                participant_contexts.extend(remapped)
                participant_catalogs.extend(catalogs)

    first_package = packages[1]
    first_pre_namespaced = (
        first_package.manifest.get("runtime_names_pre_namespaced") is True
    )
    first_participant_source = next(
        source for source in first_package.profiles if source.role == "TASK"
    )
    participant_inspection = _write_mapped_study_store(
        participant_root,
        contexts=tuple(participant_contexts),
        catalogs=tuple(participant_catalogs),
        # Start at the Practice parent so the participant deliberately opens
        # its description before proceeding. Task-specific Contexts stay
        # intact for later explicit navigation.
        current_context=(
            first_participant_source.inspection.current_context
            if first_pre_namespaced
            else _STUDY_PRACTICE_ROOT
        ),
    )
    authority_source = next(
        source for source in packages[1].profiles if source.role == "AUTHORITY"
    )
    authority_inspection = _write_mapped_study_store(
        authority_root,
        contexts=tuple(authority_contexts),
        catalogs=tuple(authority_catalogs),
        current_context=(
            authority_source.inspection.current_context
            if first_pre_namespaced
            else f"task-1/{authority_source.inspection.current_context}"
        ),
    )

    # _materialize_study_grants validates each original package independently.
    # Its source names remain the manifest identities, but every task now reads
    # from one of the two merged run stores.
    merged: dict[int, _StudyTaskPackage] = {}
    merged_authority_contexts = {
        context.name: context for context in authority_contexts
    }
    for task in _STUDY_TASKS:
        package = packages[task]
        sources: list[_StudyProfileSource] = []
        for source in package.profiles:
            inspection = (
                authority_inspection
                if source.role == "AUTHORITY"
                else participant_inspection
            )
            sources.append(
                replace(
                    source,
                    store=(
                        authority_root
                        if source.role == "AUTHORITY"
                        else participant_root
                    ),
                    inspection=inspection,
                )
            )
        templates = (
            tuple(copy.deepcopy(raw) for raw in package.grant_templates)
            if package.manifest.get("runtime_names_pre_namespaced") is True
            else tuple(
                _prefix_study_grant_template(raw, task=task)
                for raw in package.grant_templates
            )
        )
        merged[task] = replace(
            package,
            profiles=tuple(sources),
            grant_templates=templates,
            query_view_count=_query_view_count_for_baseline(
                merged_authority_contexts,
                templates,
            ),
        )
    return merged
