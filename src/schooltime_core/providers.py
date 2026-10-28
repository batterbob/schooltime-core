"""Caller-owned source descriptions for normalized snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ValidationError
from .schema import CAPABILITY_VALUES, MAX_TEXT, require_source_id, require_string


@dataclass(frozen=True)
class SourceSpec:
    """A provider-neutral source description supplied by the caller."""

    source_id: str
    display_label: str
    capabilities: frozenset[str] = frozenset()
    link_policy: object | None = None

    def __post_init__(self) -> None:
        require_source_id(self.source_id)
        require_string(self.display_label, field="display_label", limit=MAX_TEXT)
        if not isinstance(self.capabilities, frozenset) or not self.capabilities <= CAPABILITY_VALUES:
            raise ValidationError("capabilities must be a frozen set of supported capability names")
