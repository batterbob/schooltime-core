"""Bounded, provider-neutral schema primitives."""

from __future__ import annotations

import re
from datetime import date, datetime
from math import isfinite
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ValidationError

SCHEMA_NAME: Final = "schooltime_core_v1"
SCHEMA_VERSION: Final = 1
MAX_CHILDREN: Final = 16
MAX_SOURCES: Final = 16
MAX_COURSES_PER_LANE: Final = 64
MAX_ASSIGNMENTS_PER_COURSE: Final = 256
MAX_ASSIGNMENTS_PER_CHILD: Final = 1024
MAX_CALENDAR_DAYS: Final = 730
MAX_TEXT: Final = 500
MAX_TITLE: Final = 160
MAX_IDENTIFIER: Final = 80
MAX_URL: Final = 2048
SOURCE_ID_RE: Final = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
HEALTH_VALUES: Final = frozenset({"current", "partial", "stale", "unavailable"})
ASSIGNMENT_STATUS_VALUES: Final = frozenset({"open", "submitted", "completed", "returned"})
CAPABILITY_VALUES: Final = frozenset({"grades", "scores", "calendar", "links"})


def require_string(value: object, *, field: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ValidationError(f"{field} must be a nonempty string of at most {limit} characters")
    if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValidationError(f"{field} contains an unsafe character")
    return value


def require_identifier(value: object, *, field: str) -> str:
    return require_string(value, field=field, limit=MAX_IDENTIFIER)


def require_source_id(value: object) -> str:
    if not isinstance(value, str) or not SOURCE_ID_RE.fullmatch(value):
        raise ValidationError("source_id must be a short lowercase identifier")
    return value


def require_number(value: object, *, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be a finite number")
    if not isfinite(value) or abs(value) > 1_000_000:
        raise ValidationError(f"{field} is outside the supported range")
    return value


def require_timezone(value: object) -> str:
    name = require_string(value, field="timezone", limit=64)
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError("timezone must be an IANA time-zone name") from exc
    return name


def require_local_date(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be an ISO local date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO local date") from exc
    return value


def require_aware_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be an aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} must be an aware ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationError(f"{field} must be an aware ISO timestamp")
    return parsed
