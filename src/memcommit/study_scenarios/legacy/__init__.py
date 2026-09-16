"""The preserved Task 1--3 Study scenario and its owned fixture inputs."""

LEGACY_SCENARIO_ID = "legacy"
# This is a virtual provenance identity, not a registered or editable Profile.
LEGACY_BASELINE_UID = "b803a4ca-d5de-5ea1-9339-e24df565fb9c"
# Native source paths change the package fingerprint while preserving every
# prior Context/Memory identity and body; existing runs retain their old digest.
LEGACY_DIGEST = "7c6a595a5bd5dadb5729dd6c0751afaf7b2924b5b9a839375e10af8d94a91ba7"


__all__ = (
    "LEGACY_BASELINE_UID",
    "LEGACY_DIGEST",
    "LEGACY_SCENARIO_ID",
)
