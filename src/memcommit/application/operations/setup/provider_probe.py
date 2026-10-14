"""One synthetic provider response check before first Profile creation."""

import json

from memcommit.providers.errors import QueryProviderError

PROBE_SCHEMA = {
    "type": "object",
    "properties": {"provider_probe": {"type": "string", "enum": ["ok"]}},
    "required": ["provider_probe"],
    "additionalProperties": False,
}
PROBE_PROMPT = 'Return only the JSON object {"provider_probe":"ok"}. This is a synthetic connection test.'


def verify_provider_response(provider) -> None:
    try:
        response = json.loads(
            provider.complete(
                PROBE_PROMPT, operation="provider probe", output_schema=PROBE_SCHEMA
            )
        )
    except (TypeError, ValueError) as error:
        raise QueryProviderError(
            "The provider connection test did not return valid JSON."
        ) from error
    if response != {"provider_probe": "ok"}:
        raise QueryProviderError(
            "The provider connection test returned an unexpected answer."
        )
