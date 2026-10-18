"""The preserved Task 1--3 Study scenario and its owned fixture inputs."""

LEGACY_SCENARIO_ID = "legacy"
# This is a virtual provenance identity, not a registered or editable Profile.
LEGACY_BASELINE_UID = "b803a4ca-d5de-5ea1-9339-e24df565fb9c"
# Grant labels change this manifest fingerprint while Context/Memory identities
# and bodies stay fixed; existing runs retain their recorded source digest.
LEGACY_DIGEST = "85c417fa6455e866c63a162534f49cd163350c824da18ffd6c4d66093483cb2d"


__all__ = (
    "LEGACY_BASELINE_UID",
    "LEGACY_DIGEST",
    "LEGACY_SCENARIO_ID",
)
