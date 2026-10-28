from datetime import datetime

import pytest
from test_public import snapshot

from schooltime_core.errors import ValidationError
from schooltime_core.public import build_overview
from schooltime_core.week import build_week


def test_week_handles_weekend_and_is_deterministic() -> None:
    overview = build_overview(snapshot())
    now = datetime.fromisoformat("2026-03-07T12:00:00-05:00")
    result = build_week(overview, now=now)
    assert result["next_school_day"] == "2026-03-09"
    assert result == build_week(overview, now=now)


def test_week_rejects_naive_clock() -> None:
    with pytest.raises(ValidationError):
        build_week(build_overview(snapshot()), now=datetime(2026, 3, 7))
