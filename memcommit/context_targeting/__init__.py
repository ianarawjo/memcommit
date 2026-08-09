"""Shared Context targeting models, resolution, loading, and TUI controls.

The package intentionally keeps its layers in separate modules.  Import from
the narrow module that owns the needed contract so core Context loading never
acquires a prompt-toolkit dependency through a convenience re-export.
"""
