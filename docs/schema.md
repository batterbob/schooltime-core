# Schema

`schooltime_core_v1` version `1` is a provider-neutral, in-memory snapshot.
Unknown keys fail validation. Inputs are ordinary JSON-compatible mappings and
lists; all identifiers are opaque strings.

Top-level fields are `schema`, `version`, `generated_at` (aware ISO timestamp),
`timezone` (IANA name), `sources`, `children`, and optional `calendar`.
`sources` maps a short lowercase source ID (1–32 characters, `[a-z][a-z0-9_-]*`)
to a source descriptor with `display_label` and optional capability names from
`grades`, `scores`, `calendar`, and `links`. A child has `id`, `display_label`,
and `lanes`; `lanes` maps only declared source IDs to lane objects.

Each lane has `health` (`current`, `partial`, `stale`, or `unavailable`) and
`courses`. A course has `id`, `title`, and `assignments`. An assignment has
`id`, `title`, optional `due`, optional `status`, optional generic `grade` and
`score`, optional `link`, and optional protected `note`. A due value is either
an ISO local date or `{ "local_date": "YYYY-MM-DD", "at": "aware ISO time" }`;
the two local dates must agree in the snapshot timezone. Optional calendar
entries have `date`, `kind` (`school` or `closure`), and optional `label`.

Bounds: at most 16 children and sources, 64 courses per lane, 256 assignments
per course, 1,024 assignments per child, and 730 calendar days. IDs are at most
80 characters; titles at most 160; other text at most 500; URLs at most 2,048;
numbers are finite with absolute value at most 1,000,000. Invalid structural
data raises `ValidationError`. Unsafe optional links are omitted during
projection rather than causing a snapshot failure.

Example identifiers and domains are synthetic: a source `ledger`, a child
`Aster`, a course `invented-math`, and `https://portal.example.com/item/42`.
