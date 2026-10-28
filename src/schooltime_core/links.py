"""Fail-closed, caller-injected link authorization."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from re import Pattern
from urllib.parse import SplitResult, urlsplit, urlunsplit

from .errors import ValidationError
from .schema import MAX_URL, require_source_id, require_string

_FORBIDDEN_URL_CHARS = re.compile(r"[\x00-\x20\x7f\\]")
_ENCODED_SEPARATOR = re.compile(r"%(?:2f|5c)", re.IGNORECASE)


@dataclass(frozen=True)
class LinkPolicy:
    """A source's exact origin and allowed URL path grammar."""

    source_id: str
    display_label: str
    approved_origin: str
    allowed_path_patterns: tuple[Pattern[str], ...]
    _host: str = field(init=False, repr=False)
    _port: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        require_source_id(self.source_id)
        require_string(self.display_label, field="display_label")
        if not isinstance(self.approved_origin, str) or len(self.approved_origin) > MAX_URL:
            raise ValidationError("approved_origin must be a bounded HTTPS origin")
        parts = _safe_split(self.approved_origin)
        if parts is None or parts.scheme != "https" or parts.path or parts.query or parts.fragment:
            raise ValidationError("approved_origin must be a canonical HTTPS origin")
        if parts.username is not None or parts.password is not None or parts.hostname is None:
            raise ValidationError("approved_origin must not contain credentials")
        host = parts.hostname.lower()
        if ":" in host or host != parts.hostname or host.endswith("."):
            raise ValidationError("approved_origin must use a canonical DNS hostname")
        try:
            port = parts.port or 443
        except ValueError as exc:
            raise ValidationError("approved_origin has an invalid port") from exc
        canonical = f"https://{host}" + (f":{port}" if port != 443 else "")
        if self.approved_origin != canonical:
            raise ValidationError("approved_origin is not canonical")
        if not self.allowed_path_patterns or not all(hasattr(pattern, "fullmatch") for pattern in self.allowed_path_patterns):
            raise ValidationError("allowed_path_patterns must contain compiled patterns")
        object.__setattr__(self, "_host", host)
        object.__setattr__(self, "_port", port)


def _safe_split(value: object) -> SplitResult | None:
    if not isinstance(value, str) or not value or len(value) > MAX_URL or _FORBIDDEN_URL_CHARS.search(value):
        return None
    try:
        return urlsplit(value)
    except ValueError:
        return None


def safe_link(
    source_id: object,
    candidate_url: object,
    policies: Mapping[str, LinkPolicy],
) -> dict[str, str] | None:
    """Return an approved, query-free link or ``None`` for unsafe optional input."""
    if not isinstance(source_id, str) or not isinstance(policies, Mapping):
        return None
    policy = policies.get(source_id)
    if not isinstance(policy, LinkPolicy) or policy.source_id != source_id:
        return None
    parts = _safe_split(candidate_url)
    if parts is None or parts.scheme != "https" or parts.fragment or parts.username is not None:
        return None
    if parts.password is not None or parts.hostname is None or ":" in parts.hostname:
        return None
    try:
        port = parts.port or 443
    except ValueError:
        return None
    host = parts.hostname.lower()
    path = parts.path or "/"
    if host != policy._host or port != policy._port or host.endswith("."):
        return None
    if ".." in path or _ENCODED_SEPARATOR.search(path):
        return None
    if not any(pattern.fullmatch(path) for pattern in policy.allowed_path_patterns):
        return None
    netloc = host + (f":{port}" if port != 443 else "")
    return {"label": policy.display_label, "url": urlunsplit(("https", netloc, path, "", ""))}
