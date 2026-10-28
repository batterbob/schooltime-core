"""Provider-neutral, deterministic weekly projection."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from .errors import ValidationError

MAX_WEEK_ITEMS = 24


def build_week(overview: object, *, now: datetime) -> dict[str, object]:
    """Derive a capped weekly view from a validated overview and aware instant."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValidationError("now must be aware")
    if not isinstance(overview, dict) or overview.get("schema") != "schooltime_core_v1" or overview.get("version") != 1:
        raise ValidationError("overview must use schema version 1")
    timezone = overview.get("timezone")
    if not isinstance(timezone, str):
        raise ValidationError("overview timezone is invalid")
    today = now.astimezone(ZoneInfo(timezone)).date()
    calendar = cast(dict[str, Any], overview.get("calendar", {}))
    calendar_days = {item["date"]: item["kind"] for item in cast(list[dict[str, str]], calendar.get("days", []))}
    next_day = today
    for _ in range(14):
        key = next_day.isoformat()
        if next_day.weekday() < 5 and calendar_days.get(key, "school") == "school":
            break
        next_day += timedelta(days=1)
    else:
        raise ValidationError("calendar does not yield a next school day")
    items: list[dict[str, object]] = []
    for child in cast(list[dict[str, Any]], overview.get("children", [])):
        for assignment in cast(list[dict[str, Any]], child.get("assignments", [])):
            if assignment.get("status") in {"submitted", "completed"}:
                continue
            item = dict(assignment)
            item["child_id"] = child["id"]
            item["child_label"] = child["display_label"]
            due = item.get("due")
            if due == next_day.isoformat():
                item["week_bucket"] = "due_next"
            elif isinstance(due, str) and today <= datetime.fromisoformat(due).date() <= today + timedelta(days=6):
                item["week_bucket"] = "current_week"
            elif item.get("status") == "returned":
                item["week_bucket"] = "returned_work"
            else:
                item["week_bucket"] = "later"
            items.append(item)
    items.sort(key=lambda item: (item["week_bucket"], item.get("due", "9999-12-31"), item["child_label"], item["title"], item["detail_key"]))
    notices = [{"kind": "source_stale", "source_id": source_id} for child in cast(list[dict[str, Any]], overview.get("children", [])) for source_id, lane in cast(dict[str, dict[str, Any]], child.get("lanes", {})).items() if lane.get("health") in {"stale", "unavailable"}]
    return {"timezone": timezone, "today": today.isoformat(), "next_school_day": next_day.isoformat(), "items": items[:MAX_WEEK_ITEMS], "notices": notices}
