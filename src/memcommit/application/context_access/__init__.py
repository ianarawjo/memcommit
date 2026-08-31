"""Resolve Context identity and attachment independently from authorization."""

from .model import GrantedContextBinding, granted_context_binding_digest

__all__ = ["GrantedContextBinding", "granted_context_binding_digest"]
