"""Declared setup-time semantic prewarms for fixed Study fixtures."""

from memcommit.study_scenarios.legacy.prewarm.atomize import (
    AtomizePrewarmInstallResult,
    install_declared_atomize_prewarms,
    is_installed_atomize_prewarm,
)
from memcommit.study_scenarios.legacy.prewarm.compare import (
    ComparePrewarmInstallResult,
    install_declared_compare_prewarms,
    is_installed_compare_prewarm,
)
from memcommit.study_scenarios.legacy.prewarm.meld_directional import (
    DirectionalMeldPrewarmInstallResult,
    install_declared_directional_meld_prewarms,
)
from memcommit.study_scenarios.legacy.prewarm.meld_resolution import (
    MeldResolutionPrewarmInstallResult,
    build_meld_resolution_prewarm_artifact,
    find_installed_meld_resolution_branch,
    install_declared_meld_resolution_prewarms,
)

__all__ = [
    "AtomizePrewarmInstallResult",
    "ComparePrewarmInstallResult",
    "DirectionalMeldPrewarmInstallResult",
    "MeldResolutionPrewarmInstallResult",
    "build_meld_resolution_prewarm_artifact",
    "find_installed_meld_resolution_branch",
    "install_declared_atomize_prewarms",
    "install_declared_compare_prewarms",
    "install_declared_directional_meld_prewarms",
    "install_declared_meld_resolution_prewarms",
    "is_installed_atomize_prewarm",
    "is_installed_compare_prewarm",
]
