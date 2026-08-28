"""Operation-neutral coordination values for terminal review surfaces."""

RESPONSE_LABEL = "REFINE, COMMENT, OR ENTER A DIFFERENT READING"
ATOMIZE_RESPONSE_LABEL = RESPONSE_LABEL


class ReviewCancelled(Exception):
    """An interactive review closed normally without applying Memories."""
