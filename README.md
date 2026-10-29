# schooltime-core

`schooltime-core` is a provider-neutral Python library for turning normalized
school data into bounded, deterministic views. It validates a closed snapshot
schema, removes protected detail from overview responses, authorizes outbound
links against caller-supplied policies, and derives a compact weekly view.

It is a building block, not a school portal. The package has no connectors,
network access, persistence, authentication, scheduler, telemetry, or UI.
Callers own those boundaries, including consent, credentials, retention,
access control, logging, and delivery.

The v0.x API is intentionally small and may change without compatibility
guarantees.

## Why use it?

School systems expose very different APIs, but applications usually need the
same small set of operations after ingestion:

- reject malformed or unexpectedly large records;
- keep records from independent sources in distinct lanes;
- produce stable overview and detail representations;
- prevent protected notes from leaking into list views;
- allow source links only when their origin and path match explicit policy;
- group open work into a deterministic weekly view;
- do all of that without giving the projection layer network or storage access.

`schooltime-core` starts after provider-specific acquisition. An adapter
normalizes external data, then the package owns validation and projection:

```text
provider API or export
        │
        ▼
caller-owned adapter
        │ normalized dictionaries
        ▼
build_snapshot / validate_snapshot
        │
        ├──────────► build_overview ─────► build_week
        │                    │
        └────────────────────┴──────────► build_detail
```

## What it does not do

The package deliberately does not:

- fetch data or manage credentials;
- implement a provider connector;
- infer joins between sources;
- store snapshots or maintain a database;
- authenticate users or decide who may see a student;
- render HTML or provide an HTTP API;
- send notifications;
- make legal or policy decisions for applications processing student data.

## Installation

The project is not currently published on PyPI. Download the wheel from the
immutable `v0.1.0` GitHub release, verify its published SHA-256 value, and
install it locally:

```bash
python -m pip install ./schooltime_core-0.1.0-py3-none-any.whl
```

Pin an immutable release tag or commit rather than tracking `main`.

For development:

```bash
git clone <repository-url>
cd schooltime-core
python -m pip install -e ".[dev]"
python -m pytest
```

Python 3.11 or newer is required. The runtime package uses only the Python
standard library.

## End-to-end example

This example constructs one synthetic source and assignment. The approved link
policy keeps only links on the configured HTTPS origin whose paths match the
compiled expression. Query strings are removed from emitted links.

```python
from datetime import datetime
import re

from schooltime_core.links import LinkPolicy
from schooltime_core.project import build_snapshot
from schooltime_core.providers import SourceSpec
from schooltime_core.public import build_detail, build_overview
from schooltime_core.week import build_week

policy = LinkPolicy(
    "planner",
    "Open planner",
    "https://portal.example.com",
    (re.compile(r"/items/[0-9]+"),),
)

snapshot = build_snapshot(
    children=[{
        "id": "aster",
        "display_label": "Aster",
        "lanes": {
            "planner": {
                "health": "current",
                "courses": [{
                    "id": "math",
                    "title": "Invented Math",
                    "assignments": [{
                        "id": "practice-7",
                        "title": "Practice set 7",
                        "due": "2026-03-09",
                        "status": "open",
                        "score": 9,
                        "note": "Review question 4.",
                        "link": (
                            "https://portal.example.com/items/42"
                            "?session=discard"
                        ),
                    }],
                }],
            },
        },
    }],
    sources={
        "planner": SourceSpec(
            "planner",
            "Planner",
            frozenset({"links", "scores"}),
            policy,
        ),
    },
    generated_at=datetime.fromisoformat("2026-03-07T12:00:00-05:00"),
    timezone="America/New_York",
    calendar={
        "days": [{"date": "2026-03-09", "kind": "school"}],
    },
)

overview = build_overview(snapshot)
item = overview["children"][0]["assignments"][0]
detail = build_detail(snapshot, item["detail_key"])
week = build_week(
    overview,
    now=datetime.fromisoformat("2026-03-07T12:00:00-05:00"),
)

print(item["link"])
# {'label': 'Planner', 'url': 'https://portal.example.com/items/42'}

print("note" in item, detail["note"])
# False Review question 4.

print(week["next_school_day"], week["items"][0]["week_bucket"])
# 2026-03-09 due_next
```

The overview intentionally omits `note`; a caller must present the opaque
`detail_key` to `build_detail` to recover that field. This is a projection
boundary, not authorization: an application must still authenticate the caller
and decide whether that caller may access the requested student record.

## Core concepts

### Sources and adapters

A source is an opaque caller-chosen identifier plus a display label and optional
capabilities. `SourceSpec` does not know which external product supplied the
data. Provider-specific adapters live outside this package and must convert raw
responses into the documented normalized schema.

See the [adapter contract](docs/adapter-contract.md) before writing an adapter.

### Snapshots

A snapshot contains:

- an aware generation timestamp and IANA timezone;
- declared source descriptors;
- children with source-keyed lanes;
- courses and bounded assignments;
- a required calendar object, which may contain an empty `days` list.

Unknown keys, duplicate identifiers, unsupported enums, inconsistent due
timestamps, and values outside the documented bounds fail closed with
`ValidationError`. See the complete [schema and limits](docs/schema.md).

### Public projections

`build_overview` validates the whole snapshot, emits deterministic ordering,
removes protected notes, calculates due buckets, and omits unsafe optional
links. `build_detail` returns one validated item selected by its derived detail
key and may include the protected note.

### Weekly projection

`build_week` takes an overview plus an explicit aware clock. It derives the
local date, locates the next school day, ignores submitted or completed work,
assigns weekly buckets, sorts deterministically, and caps output.

### Link policies

`LinkPolicy` binds a source to one canonical HTTPS origin and one or more
full-match path expressions. `safe_link` rejects credentials, fragments,
authority mismatches, malformed ports, encoded path separators, traversal
segments, controls, oversized input, and paths outside policy. Accepted links
are returned without query strings.

## Module map

| Module | Responsibility |
| --- | --- |
| `schooltime_core.schema` | Shared bounds and primitive validators |
| `schooltime_core.providers` | Provider-neutral `SourceSpec` descriptors |
| `schooltime_core.links` | Injected HTTPS origin and path authorization |
| `schooltime_core.project` | Construct snapshots from normalized input |
| `schooltime_core.public` | Validate snapshots and build overview/detail views |
| `schooltime_core.week` | Derive a bounded weekly view |
| `schooltime_core.errors` | Stable `ValidationError` refusal type |

## Privacy and security boundaries

The core is intentionally offline and in-memory. It emits no telemetry and
ships no real student records. Those properties reduce its authority, but they
do not make an application using it automatically private or secure.

Callers remain responsible for:

- obtaining any required consent;
- authenticating users and authorizing each student record;
- protecting credentials and raw provider responses;
- choosing storage, encryption, retention, deletion, and backup policies;
- preventing sensitive values from entering logs, traces, issues, and tests;
- applying network and SSRF controls in adapters;
- keeping provider-specific failures from being misrepresented as empty data.

Read [PRIVACY.md](PRIVACY.md), the longer
[privacy model](docs/privacy-model.md), and [SECURITY.md](SECURITY.md) before
using the package with real records. Report vulnerabilities through GitHub's
private **Report a vulnerability** form, not a public issue.

## Development

The repository uses synthetic identities, schools, courses, assignments, and
reserved domains. Real student data is prohibited in code, fixtures,
documentation, commits, issues, and test output.

Run the local checks with:

```bash
python -m pytest
python -m ruff check .
python -m mypy
python -m build
python tools/check_release_tree.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution boundary. The CI
workflow tests Python 3.11 and 3.12, performs static checks, builds distributions,
and runs release-hygiene checks.

## Project status

`0.1.x` is pre-alpha. The normalized schema and public function signatures may
change while adapter experience accumulates. Planned work should prioritize:

- richer adapter examples using synthetic input;
- machine-readable schema documentation;
- clearer compatibility and deprecation rules;
- more edge-case fixtures around calendars and source health;
- explicit compatibility and deprecation rules before the API is declared
  stable.
