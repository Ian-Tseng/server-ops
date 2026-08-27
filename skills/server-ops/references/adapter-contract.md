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

For the certified Windows start cell, set `mutation_enabled` to true, use strategy
`direct_child`, configure `launch.argv` and `launch.cwd`, and keep a match predicate that
the launched process will satisfy. Use an absolute `.exe`/`.com` path when reproducibility
matters. The adapter enables planning only; it does not approve a plan or prove ownership.
An exact launch receipt must match PID, creation time, executable, argv digest, cwd, and
adapter digest before status reports `identity=owned`.
