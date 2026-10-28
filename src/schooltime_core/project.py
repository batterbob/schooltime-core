"""Construction of bounded snapshots from already-normalized caller inputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import TypeAlias

from .errors import ValidationError
from .links import LinkPolicy
from .providers import SourceSpec
from .public import validate_snapshot
from .schema import SCHEMA_NAME, SCHEMA_VERSION, require_timezone

ChildInput: TypeAlias = Mapping[str, object]
CalendarInput: TypeAlias = Mapping[str, object]


def build_snapshot(
    *,
    children: Sequence[ChildInput],
    sources: Mapping[str, SourceSpec],
    generated_at: datetime,
    timezone: str,
    calendar: CalendarInput | None = None,
    prior_snapshot: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a schema-v1 snapshot without fetching or interpreting raw provider data."""
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValidationError("generated_at must be aware")
    require_timezone(timezone)
    if calendar is None:
        raise ValidationError("calendar input is required to build a snapshot")
    if prior_snapshot is not None and not isinstance(prior_snapshot, Mapping):
        raise ValidationError("prior_snapshot must be a mapping when supplied")
    descriptors: dict[str, object] = {}
    for source_id, spec in sources.items():
        if source_id != spec.source_id:
            raise ValidationError("source mapping keys must match SourceSpec IDs")
        descriptor: dict[str, object] = {"display_label": spec.display_label, "capabilities": sorted(spec.capabilities)}
        if isinstance(spec.link_policy, LinkPolicy):
            descriptor["link_policy"] = {"approved_origin": spec.link_policy.approved_origin, "allowed_path_patterns": [pattern.pattern for pattern in spec.link_policy.allowed_path_patterns]}
        elif spec.link_policy is not None:
            raise ValidationError("link_policy must be a LinkPolicy or None")
        descriptors[source_id] = descriptor
    raw = {"schema": SCHEMA_NAME, "version": SCHEMA_VERSION, "generated_at": generated_at.isoformat(), "timezone": timezone, "sources": descriptors, "children": [dict(child) for child in children], "calendar": dict(calendar)}
    return validate_snapshot(raw)
