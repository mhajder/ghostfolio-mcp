from urllib.parse import quote

TRUTHY_VALUES = ("1", "true", "yes", "on")


def parse_bool(val, default=True):
    """
    Convert a value to boolean.

    A blank or whitespace-only value counts as unset and yields the default,
    so an env var declared without a value (``GHOSTFOLIO_VERIFY_SSL=``) cannot
    silently flip a setting off.

    Args:
        val: The value to convert.
        default (bool, optional): The default value to return if val is None or blank. Defaults to True.

    Returns:
        bool: True if val represents a truthy value ("1", "true", "yes", "on"), case-insensitive; otherwise False.
    """
    if val is None:
        return default
    normalized = str(val).strip().casefold()
    if not normalized:
        return default
    return normalized in TRUTHY_VALUES


def quote_path_segment(value: str) -> str:
    """
    Percent-encode a value for use as a single URL path segment.

    Ghostfolio path parameters are caller-supplied (symbols on a MANUAL data
    source are named by the user), so they can contain characters that carry
    meaning in a URL. Interpolating them raw silently sends the request
    somewhere else: ``#`` starts a fragment and truncates the path, ``?``
    starts the query string, and ``/`` adds a path segment. On a write or a
    delete that means acting on a *different* symbol - and getting a success
    response for it.

    Nothing is treated as safe, so ``/`` becomes ``%2F`` and stays inside the
    segment. Values made up of unreserved characters (the common case, e.g.
    ``AAPL``, ``2026-04-30`` or a UUID) come back unchanged, and httpx2 does not
    re-encode the escapes this produces.

    Two cases percent-encoding alone does not cover, because ``.`` is an
    unreserved character:

    - A dot-only segment (``.``, ``..``) is removed by RFC 3986 dot-segment
      normalisation, which walks the request up to a different endpoint. The
      dots are escaped so the value stays a value.
    - An empty segment collapses into the trailing slash, turning an
      item request into a collection one - ``delete_activity("")`` would issue
      ``DELETE /api/v1/activities``, which deletes *every* activity. There is
      no correct request to make for an empty identifier, so this raises.

    Args:
        value: The path segment value to encode.

    Returns:
        str: The percent-encoded segment.

    Raises:
        ValueError: If the value is empty or whitespace-only.
    """
    segment = str(value)
    if not segment.strip():
        raise ValueError(
            "URL path segment must not be empty - a symbol, date or ID is required"
        )
    encoded = quote(segment, safe="")
    if set(encoded) == {"."}:
        encoded = encoded.replace(".", "%2E")
    return encoded
