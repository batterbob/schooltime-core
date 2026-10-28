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
