# Adapter contract

Adapters are caller-owned code that normalize external responses into this
package's bounded, provider-neutral schema. They must reject or transform
unreadable records before passing only documented fields and bounded values to
this package. An adapter may choose arbitrary opaque source IDs, but it must
declare each source's display label and capabilities through `SourceSpec`.

This package does not fetch, authenticate, store, schedule, or discover
external data. Adapters must never pass credentials, raw responses, unbounded
metadata, or source-specific fields to the normalized snapshot.
