# Adapter Contract

The authority is `schemas/adapter.schema.json` plus the strict runtime validator. The
schema supplies editor help; runtime validation remains authoritative and parity-tested.

Discovery accepts only an explicit adapter or the exact workspace-root
`.server-ops.json`. Paths are canonicalized and must remain under the adapter workspace.
Unknown fields are rejected.

```json
{
  "schema_version": 1,
  "services": [
    {
      "id": "example-server",
      "label": "Example Server",
      "workspace": ".",
      "mutation_enabled": false,
      "strategy": "read_only",
      "match": {
        "argv_contains": ["example_server.py"],
        "ports": [8090]
      },
      "health": {
        "url": "http://127.0.0.1:8090/health",
        "expected_status": 200,
        "expected_body": "OK",
        "timeout_ms": 1500
      }
    }
  ]
}
```

Argument arrays are executable intent even without a shell. Do not store credentials,
tokens, passwords, arbitrary environment values, or commands copied from untrusted output.
Working directory, argv substrings, ports, and health remain corroboration only.
