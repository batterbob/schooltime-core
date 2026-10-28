"""Strict validation and deterministic public snapshot projections."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import date
from hashlib import sha256
from typing import Any, Final, cast
from zoneinfo import ZoneInfo

from .errors import ValidationError
from .links import LinkPolicy, safe_link
from .schema import (
    ASSIGNMENT_STATUS_VALUES,
    HEALTH_VALUES,
    MAX_ASSIGNMENTS_PER_CHILD,
    MAX_ASSIGNMENTS_PER_COURSE,
    MAX_CALENDAR_DAYS,
    MAX_CHILDREN,
    MAX_COURSES_PER_LANE,
    MAX_SOURCES,
    MAX_TITLE,
    MAX_URL,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    require_aware_timestamp,
    require_identifier,
    require_local_date,
    require_number,
    require_source_id,
    require_string,
    require_timezone,
)

_TOP_KEYS: Final = frozenset({"schema", "version", "generated_at", "timezone", "sources", "children", "calendar"})
_SOURCE_KEYS: Final = frozenset({"display_label", "capabilities", "link_policy"})
_LANE_KEYS: Final = frozenset({"health", "courses"})
_COURSE_KEYS: Final = frozenset({"id", "title", "assignments"})
_ASSIGNMENT_KEYS: Final = frozenset({"id", "title", "due", "status", "grade", "score", "link", "note"})
_CHILD_KEYS: Final = frozenset({"id", "display_label", "lanes"})
_CALENDAR_KEYS: Final = frozenset({"days"})
_CALENDAR_DAY_KEYS: Final = frozenset({"date", "kind", "label"})


def _mapping(value: object, *, field: str, keys: frozenset[str], required: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - keys or required - set(value):
        raise ValidationError(f"{field} has an unsupported shape")
    return value


def _list(value: object, *, field: str, limit: int) -> list[Any]:
    if not isinstance(value, list) or len(value) > limit:
        raise ValidationError(f"{field} must be a list of at most {limit} values")
    return value


def _due(value: object, *, timezone: str) -> str | dict[str, str]:
    if isinstance(value, str):
        return require_local_date(value, field="due")
    due = _mapping(value, field="due", keys=frozenset({"local_date", "at"}), required=frozenset({"local_date", "at"}))
    local_date = require_local_date(due["local_date"], field="due.local_date")
    instant = require_aware_timestamp(due["at"], field="due.at")
    if instant.astimezone(ZoneInfo(timezone)).date().isoformat() != local_date:
        raise ValidationError("due timestamp and local_date disagree")
    return {"local_date": local_date, "at": due["at"]}


def _source_policy(source_id: str, descriptor: dict[str, Any]) -> LinkPolicy | None:
    value = descriptor.get("link_policy")
    if value is None:
        return None
    policy = _mapping(
        value,
        field="link_policy",
        keys=frozenset({"approved_origin", "allowed_path_patterns"}),
        required=frozenset({"approved_origin", "allowed_path_patterns"}),
    )
    patterns = _list(policy["allowed_path_patterns"], field="allowed_path_patterns", limit=16)
    if not patterns:
        raise ValidationError("allowed_path_patterns must not be empty")
    compiled: list[re.Pattern[str]] = []
    for item in patterns:
        text = require_string(item, field="allowed_path_pattern", limit=MAX_TITLE)
        try:
            compiled.append(re.compile(text))
        except re.error as exc:
            raise ValidationError("allowed_path_pattern is invalid") from exc
    return LinkPolicy(source_id, descriptor["display_label"], policy["approved_origin"], tuple(compiled))


def _due_date(value: str | dict[str, str] | None) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else value["local_date"]


def _detail_key(child_id: str, source_id: str, course_id: str, assignment_id: str) -> str:
    payload = json.dumps([child_id, source_id, course_id, assignment_id], separators=(",", ":"), ensure_ascii=True)
    return "detail-" + sha256(payload.encode("ascii")).hexdigest()


def validate_snapshot(raw: object) -> dict[str, object]:
    """Validate and deep-copy a version-1 normalized snapshot."""
    top = _mapping(raw, field="snapshot", keys=_TOP_KEYS, required=_TOP_KEYS - {"calendar"})
    if top["schema"] != SCHEMA_NAME or top["version"] != SCHEMA_VERSION:
        raise ValidationError("only schooltime_core_v1 version 1 is supported")
    timezone = require_timezone(top["timezone"])
    require_aware_timestamp(top["generated_at"], field="generated_at")
    source_input = _mapping(top["sources"], field="sources", keys=frozenset(str(key) for key in top["sources"]) if isinstance(top["sources"], dict) else frozenset(), required=frozenset())
    if not source_input or len(source_input) > MAX_SOURCES:
        raise ValidationError("sources must contain between one and sixteen entries")
    sources: dict[str, dict[str, object]] = {}
    policies: dict[str, LinkPolicy] = {}
    for source_id, raw_descriptor in source_input.items():
        require_source_id(source_id)
        descriptor = _mapping(raw_descriptor, field="source", keys=_SOURCE_KEYS, required=frozenset({"display_label"}))
        capabilities = _list(descriptor.get("capabilities", []), field="capabilities", limit=8)
        if not all(isinstance(item, str) and item in {"grades", "scores", "calendar", "links"} for item in capabilities):
            raise ValidationError("capabilities contain an unsupported value")
        if len(set(capabilities)) != len(capabilities):
            raise ValidationError("capabilities must not contain duplicates")
        normalized: dict[str, object] = {"display_label": require_string(descriptor["display_label"], field="display_label"), "capabilities": sorted(capabilities)}
        policy = _source_policy(source_id, descriptor)
        if policy is not None:
            policies[source_id] = policy
            normalized["link_policy"] = {"approved_origin": policy.approved_origin, "allowed_path_patterns": [pattern.pattern for pattern in policy.allowed_path_patterns]}
        sources[source_id] = normalized
    children_input = _list(top["children"], field="children", limit=MAX_CHILDREN)
    children: list[dict[str, object]] = []
    child_ids: set[str] = set()
    for raw_child in children_input:
        child = _mapping(raw_child, field="child", keys=_CHILD_KEYS, required=_CHILD_KEYS)
        child_id = require_identifier(child["id"], field="child.id")
        if child_id in child_ids:
            raise ValidationError("child IDs must be unique")
        child_ids.add(child_id)
        lanes_input = _mapping(child["lanes"], field="lanes", keys=frozenset(str(key) for key in child["lanes"]) if isinstance(child["lanes"], dict) else frozenset(), required=frozenset())
        if set(lanes_input) - set(sources):
            raise ValidationError("lanes must use declared source IDs")
        lanes: dict[str, object] = {}
        assignment_total = 0
        for source_id, raw_lane in lanes_input.items():
            lane = _mapping(raw_lane, field="lane", keys=_LANE_KEYS, required=_LANE_KEYS)
            if lane["health"] not in HEALTH_VALUES:
                raise ValidationError("lane.health is unsupported")
            courses_input = _list(lane["courses"], field="courses", limit=MAX_COURSES_PER_LANE)
            courses: list[dict[str, object]] = []
            course_ids: set[str] = set()
            for raw_course in courses_input:
                course = _mapping(raw_course, field="course", keys=_COURSE_KEYS, required=_COURSE_KEYS)
                course_id = require_identifier(course["id"], field="course.id")
                if course_id in course_ids:
                    raise ValidationError("course IDs must be unique within a lane")
                course_ids.add(course_id)
                assignments_input = _list(course["assignments"], field="assignments", limit=MAX_ASSIGNMENTS_PER_COURSE)
                assignment_total += len(assignments_input)
                if assignment_total > MAX_ASSIGNMENTS_PER_CHILD:
                    raise ValidationError("child assignment count exceeds the aggregate bound")
                assignments: list[dict[str, object]] = []
                assignment_ids: set[str] = set()
                for raw_assignment in assignments_input:
                    assignment = _mapping(raw_assignment, field="assignment", keys=_ASSIGNMENT_KEYS, required=frozenset({"id", "title"}))
                    assignment_id = require_identifier(assignment["id"], field="assignment.id")
                    if assignment_id in assignment_ids:
                        raise ValidationError("assignment IDs must be unique within a course")
                    assignment_ids.add(assignment_id)
                    normalized_assignment: dict[str, object] = {"id": assignment_id, "title": require_string(assignment["title"], field="assignment.title", limit=MAX_TITLE)}
                    if "due" in assignment:
                        normalized_assignment["due"] = _due(assignment["due"], timezone=timezone)
                    if "status" in assignment:
                        if assignment["status"] not in ASSIGNMENT_STATUS_VALUES:
                            raise ValidationError("assignment.status is unsupported")
                        normalized_assignment["status"] = assignment["status"]
                    for field in ("grade", "score"):
                        if field in assignment:
                            normalized_assignment[field] = require_number(assignment[field], field=field)
                    if "link" in assignment:
                        normalized_assignment["link"] = require_string(assignment["link"], field="link", limit=MAX_URL)
                    if "note" in assignment:
                        normalized_assignment["note"] = require_string(assignment["note"], field="note")
                    assignments.append(normalized_assignment)
                courses.append({"id": course_id, "title": require_string(course["title"], field="course.title", limit=MAX_TITLE), "assignments": assignments})
            lanes[source_id] = {"health": lane["health"], "courses": courses}
        children.append({"id": child_id, "display_label": require_string(child["display_label"], field="child.display_label"), "lanes": lanes})
    calendar: dict[str, object] | None = None
    if "calendar" in top:
        raw_calendar = _mapping(top["calendar"], field="calendar", keys=_CALENDAR_KEYS, required=_CALENDAR_KEYS)
        days: list[dict[str, str]] = []
        dates: set[str] = set()
        for raw_day in _list(raw_calendar["days"], field="calendar.days", limit=MAX_CALENDAR_DAYS):
            day = _mapping(raw_day, field="calendar day", keys=_CALENDAR_DAY_KEYS, required=frozenset({"date", "kind"}))
            day_date = require_local_date(day["date"], field="calendar.date")
            if day_date in dates or day["kind"] not in {"school", "closure"}:
                raise ValidationError("calendar days must be unique and use a supported kind")
            dates.add(day_date)
            normalized_day = {"date": day_date, "kind": day["kind"]}
            if "label" in day:
                normalized_day["label"] = require_string(day["label"], field="calendar.label")
            days.append(normalized_day)
        calendar = {"days": days}
    result: dict[str, object] = {"schema": SCHEMA_NAME, "version": SCHEMA_VERSION, "generated_at": top["generated_at"], "timezone": timezone, "sources": sources, "children": children}
    if calendar is not None:
        result["calendar"] = calendar
    return deepcopy(result)


def build_overview(raw: object) -> dict[str, object]:
    """Produce a deterministic, protected-field-free overview."""
    snapshot = validate_snapshot(raw)
    source_descriptors = cast(dict[str, dict[str, Any]], snapshot["sources"])
    policies = {
        source_id: _source_policy(source_id, descriptor)
        for source_id, descriptor in source_descriptors.items()
    }
    link_policies = {source_id: policy for source_id, policy in policies.items() if policy is not None}
    generated_day = require_aware_timestamp(snapshot["generated_at"], field="generated_at").astimezone(ZoneInfo(str(snapshot["timezone"]))).date()
    children: list[dict[str, object]] = []
    seen_keys: set[str] = set()
    for child in cast(list[dict[str, Any]], snapshot["children"]):
        public_assignments: list[dict[str, object]] = []
        for source_id, lane in child["lanes"].items():
            for course in lane["courses"]:
                for assignment in course["assignments"]:
                    key = _detail_key(child["id"], source_id, course["id"], assignment["id"])
                    if key in seen_keys:
                        raise ValidationError("duplicate detail key")
                    seen_keys.add(key)
                    due = _due_date(assignment.get("due"))
                    output: dict[str, object] = {"detail_key": key, "source_id": source_id, "course_id": course["id"], "course_title": course["title"], "id": assignment["id"], "title": assignment["title"], "status": assignment.get("status", "open")}
                    if due is not None:
                        output["due"] = due
                        output["due_bucket"] = "overdue" if date.fromisoformat(due) < generated_day else "today" if date.fromisoformat(due) == generated_day else "upcoming"
                    else:
                        output["due_bucket"] = "undated"
                    for field in ("grade", "score"):
                        if field in assignment:
                            output[field] = assignment[field]
                    if "link" in assignment:
                        link = safe_link(source_id, assignment["link"], link_policies)
                        if link is not None:
                            output["link"] = link
                    public_assignments.append(output)
        public_assignments.sort(key=lambda item: (item["due_bucket"] == "undated", item.get("due", "9999-12-31"), item["source_id"], item["course_title"], item["title"], item["id"]))
        children.append({"id": child["id"], "display_label": child["display_label"], "assignments": public_assignments})
    children.sort(key=lambda item: (item["display_label"], item["id"]))
    result: dict[str, object] = {"schema": SCHEMA_NAME, "version": SCHEMA_VERSION, "generated_at": snapshot["generated_at"], "timezone": snapshot["timezone"], "children": children}
    if "calendar" in snapshot:
        result["calendar"] = deepcopy(snapshot["calendar"])
    return result


def build_detail(raw: object, detail_key: object) -> dict[str, object]:
    """Return one protected detail record, or fail closed when it is absent."""
    if not isinstance(detail_key, str):
        raise ValidationError("detail_key must be a string")
    snapshot = validate_snapshot(raw)
    overview = build_overview(snapshot)
    for child in cast(list[dict[str, Any]], overview["children"]):
        for item in child["assignments"]:
            if item["detail_key"] == detail_key:
                detail = deepcopy(item)
                for source_child in cast(list[dict[str, Any]], snapshot["children"]):
                    if source_child["id"] != child["id"]:
                        continue
                    lane = source_child["lanes"][item["source_id"]]
                    for course in lane["courses"]:
                        if course["id"] == item["course_id"]:
                            for assignment in course["assignments"]:
                                if assignment["id"] == item["id"] and "note" in assignment:
                                    detail["note"] = assignment["note"]
                return cast(dict[str, object], detail)
    raise ValidationError("detail_key does not exist")
