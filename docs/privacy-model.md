# Privacy model

The package is an in-memory transformation library. It neither contacts an
external service nor writes records, and it emits no telemetry. The caller is
responsible for obtaining consent, limiting adapter input, authenticating users,
storing data, defining retention, securing logs, and responding to requests to
access or delete records. Real student data must never appear in this project.
