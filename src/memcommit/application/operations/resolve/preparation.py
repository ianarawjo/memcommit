"""Acquire one Context's Audit through the common Resolve application entry."""

from memcommit.application.operations.audit.application import (
    get_or_run_quality_audit,
    run_quality_audit,
)


def audit_resolve_context(
    context,
    *,
    checks,
    provider_factory,
    repository=None,
):
    """Share initial Audit acquisition between live and detached Resolve inputs."""
    options = dict(
        checks=checks,
    )
    if repository is None:
        return run_quality_audit(context, provider_factory, **options)
    return get_or_run_quality_audit(context, provider_factory, repository, **options)
