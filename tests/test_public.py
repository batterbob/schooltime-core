from copy import deepcopy

import pytest

from schooltime_core.errors import ValidationError
from schooltime_core.public import build_detail, build_overview, validate_snapshot


def snapshot() -> dict[str, object]:
    return {
        "schema": "schooltime_core_v1",
        "version": 1,
        "generated_at": "2026-03-09T09:00:00-04:00",
        "timezone": "America/New_York",
        "sources": {
            "ledger": {
                "display_label": "Ledger",
                "capabilities": ["links", "scores"],
                "link_policy": {"approved_origin": "https://portal.example.com", "allowed_path_patterns": [r"/item/[0-9]+"]},
            }
        },
        "children": [{"id": "aster", "display_label": "Aster", "lanes": {"ledger": {"health": "current", "courses": [{"id": "math", "title": "Invented Math", "assignments": [{"id": "practice", "title": "Practice set", "due": "2026-03-09", "score": 9, "note": "Ask about the last question.", "link": "https://portal.example.com/item/42?temporary=yes"}]}]}}}],
        "calendar": {"days": [{"date": "2026-03-09", "kind": "school"}]},
    }


def test_overview_is_deterministic_and_strips_protected_notes() -> None:
    raw = snapshot()
    validated = validate_snapshot(raw)
    overview = build_overview(raw)
    assert "note" not in overview["children"][0]["assignments"][0]
    assert overview["children"][0]["assignments"][0]["link"]["url"] == "https://portal.example.com/item/42"
    overview["children"][0]["assignments"][0]["title"] = "mutated"
    assert validated["children"][0]["lanes"]["ledger"]["courses"][0]["assignments"][0]["title"] == "Practice set"


def test_detail_recovers_protected_note_only_for_a_valid_key() -> None:
    overview = build_overview(snapshot())
    key = overview["children"][0]["assignments"][0]["detail_key"]
    assert build_detail(snapshot(), key)["note"] == "Ask about the last question."
    with pytest.raises(ValidationError):
        build_detail(snapshot(), "unknown")


def test_unknown_data_and_inconsistent_timestamp_fail_closed() -> None:
    unknown = snapshot()
    unknown["unexpected"] = True
    with pytest.raises(ValidationError):
        validate_snapshot(unknown)
    inconsistent = deepcopy(snapshot())
    inconsistent["children"][0]["lanes"]["ledger"]["courses"][0]["assignments"][0]["due"] = {"local_date": "2026-03-09", "at": "2026-03-10T01:00:00-04:00"}
    with pytest.raises(ValidationError):
        validate_snapshot(inconsistent)
