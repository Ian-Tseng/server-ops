# Operations

## Read-only commands

Global options precede the command:

```text
server-ops [--workspace PATH] [--adapter FILE] [--json] [--no-color] COMMAND
```

- `doctor`: interpreter, platform, adapter, optional `psutil`, state root, network policy,
  and exact mutation availability.
- `status [SERVICE]`: configured service card/table or adapter-free workspace candidates.
- `diagnose [SERVICE]`: status plus matched and missing ownership evidence.
- `validate`: strict adapter validation and digest.
- `capabilities`: exact OS/provider/strategy/action cells. Never infer an OS-wide promise.
- `migrate --check`: read-only schema compatibility.
- `recover inspect OPERATION_ID`: read one owner-scoped local receipt.

Human output is concise. `--json` emits a versioned envelope and stable typed error codes.
Exit codes are: 0 success, 2 invalid input, 3 unsupported/refused, 4 mutation failure,
5 verification failure, 6 recovery required, and 7 internal error.

Process arguments may be inspected locally for bounded matching, but public JSON exposes
only their count and canonical digest, never raw argument values. Human command names and
errors are stripped of terminal control characters.

## Health

Only credential-free `http://127.0.0.1:<port>` and `http://[::1]:<port>` URLs are
accepted. DNS, proxy configuration, redirects, remote hosts, credentials, regex,
streaming, and command-health predicates are not accepted.

Fast status uses one bounded attempt. A status match establishes only the configured
predicate. Focused verification is a separate executable-intent surface and never runs
automatically during read-only status.

## Plans and receipts

`plan start|stop|restart SERVICE` either emits an exact plan or a typed refusal. Refusals
are persisted because they are useful evidence that no side effect occurred. `apply`
requires an exact operation ID and digest and fails closed if either changed.

Version 0.1.2 has no certified mutation provider, so every lifecycle plan refuses with
`MUTATION_DISABLED` or `CAPABILITY_NOT_CERTIFIED`. This is deliberate product behavior.
