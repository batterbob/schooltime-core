# schooltime-core

`schooltime-core` is a small, provider-neutral Python building block for
validating normalized schooltime snapshots and creating deterministic public
and weekly projections. It is not a school portal, connector, service, or
deployment product.

The v0.x API is unstable. It performs all work in memory and has no runtime
dependencies, network access, persistence, authentication, scheduler, or UI.
Callers own adapters, credentials, consent, storage, retention, and delivery.

See `docs/schema.md` for the normalized input contract and `PRIVACY.md` for
data-handling boundaries.

## Five-minute example

```python
from datetime import datetime
from schooltime_core.project import build_snapshot
from schooltime_core.providers import SourceSpec
from schooltime_core.public import build_overview

snapshot = build_snapshot(
    children=[], sources={"ledger": SourceSpec("ledger", "Ledger")},
    generated_at=datetime.fromisoformat("2026-01-05T09:00:00+00:00"),
    timezone="UTC", calendar={"days": []},
)
overview = build_overview(snapshot)
```

The library has no connectors. v0.x APIs may change without compatibility
guarantees; adapters and any external storage remain caller-owned.
