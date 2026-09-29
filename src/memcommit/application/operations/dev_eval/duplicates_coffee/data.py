"""Authored coffee inputs and expected groups; positions bind to real List UIDs."""

NAME = "duplicates_coffee"
CONTENTS = (
    "The user likes coffee.",
    "The user likes coffee.",
    "Coffee is a drink the user likes.",
    "The user prefers window seats at cafés.",
    "At cafés, the user prefers sitting by a window.",
    "The user does not drink coffee in the evening.",
)
# Repeated text is not an identity key. These positions refer to insertion order.
EXACT_GROUPS = ((0, 1),)
REDUNDANCY_GROUPS = ((0, 1, 2), (3, 4))
