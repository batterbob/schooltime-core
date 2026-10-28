from datetime import datetime

import pytest

from schooltime_core.errors import ValidationError
from schooltime_core.project import build_snapshot
from schooltime_core.providers import SourceSpec


def test_builder_accepts_three_arbitrary_sources() -> None:
    sources = {key: SourceSpec(key, key.title()) for key in ("ledger", "notebook", "planner")}
    built = build_snapshot(children=[{"id": "cedar", "display_label": "Cedar", "lanes": {key: {"health": "current", "courses": []} for key in sources}}], sources=sources, generated_at=datetime.fromisoformat("2026-03-09T09:00:00-04:00"), timezone="America/New_York", calendar={"days": []})
    assert set(built["sources"]) == set(sources)


def test_builder_requires_calendar_and_aware_time() -> None:
    with pytest.raises(ValidationError):
        build_snapshot(children=[], sources={}, generated_at=datetime(2026, 1, 1), timezone="UTC", calendar=None)
