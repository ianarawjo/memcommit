"""Bounded JSON transport shared by completion and decision providers."""

import json
import urllib.error
import urllib.request
from collections.abc import Callable

from memcommit.providers.errors import QueryProviderError


_MAX_PROVIDER_ENVELOPE_BYTES = 16 * 1024 * 1024
JsonRequester = Callable[
    [str, str, dict[str, object] | None, dict[str, str], float, str],
    dict[str, object],
]


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def request_json(
    url: str,
    method: str,
    payload: dict[str, object] | None,
    headers: dict[str, str],
    timeout: float,
    operation: str,
) -> dict[str, object]:
    body = None
    request_headers = {"Accept": "application/json", **headers}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=body, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(_MAX_PROVIDER_ENVELOPE_BYTES + 1)
    except urllib.error.HTTPError as error:
        # Provider errors may reflect private input; expose only the status code.
        raise QueryProviderError(
            f"The {operation} provider returned HTTP {error.code}."
        ) from error
    except (OSError, urllib.error.URLError) as error:
        raise QueryProviderError(
            f"The {operation} provider could not be reached."
        ) from error
    if len(raw) > _MAX_PROVIDER_ENVELOPE_BYTES:
        raise QueryProviderError(
            f"The {operation} provider returned an oversized response."
        )
    try:
        value = json.loads(raw, object_pairs_hook=_strict_json_object)
    except (UnicodeDecodeError, ValueError) as error:
        raise QueryProviderError(
            f"The {operation} provider returned an invalid JSON envelope."
        ) from error
    if not isinstance(value, dict):
        raise QueryProviderError(
            f"The {operation} provider returned an invalid response envelope."
        )
    return value
