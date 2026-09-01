"""Operation-neutral authorization policies for resolved application inputs."""

from importlib import import_module


_EXPORT_MODULES = {
    "ContextUse": "context_use",
    "ContextUseAuthorization": "context_use",
    "authorize_context_use": "context_use",
    "authorized_context_operation": "context_operation",
    "authorized_context_mutation": "context_operation",
}


def __getattr__(name: str):
    """Load narrow authorization owners without coupling sibling policies."""

    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{module_name}"), name)
    globals()[name] = value
    return value


__all__ = list(_EXPORT_MODULES)
