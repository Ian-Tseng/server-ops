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
- `verify [SERVICE] [--deadline-ms N] [--interval-ms N] [--stable-successes N]`:
  repeatedly evaluate only the configured loopback health predicate until the requested
  consecutive-success condition is met or the bounded deadline expires.
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

Focused verification accepts a 100..60000 ms deadline, a 10..5000 ms interval no longer
than the deadline, and 1..20 consecutive successes. It uses monotonic elapsed time,
resets the consecutive count after any unhealthy observation, performs no mutation, and
returns exit 5 when the condition is not established. It proves only the configured
health predicate remained true for the observed sequence; it does not prove ownership,
compatibility, production reliability, or future availability.

## Diagnosis sequence

Do not jump from a symptom to a repair. Capture the failing predicate and timestamp,
inspect the smallest relevant recent-change surface, state one falsifiable hypothesis,
run one read-only observation that can distinguish it, then update or reject the
hypothesis. After an authorized repair, rerun the same focused verification contract.
Do not hide a timeout by increasing the deadline unless the service's documented startup
condition justifies the change.

## Plans and receipts

`plan start|stop|restart SERVICE` either emits an exact plan or a typed refusal. Refusals
are persisted because they are useful evidence that no side effect occurred. `apply`
requires an exact operation ID and digest and fails closed if either changed.

Version 0.3.0 certifies only Windows `psutil/direct_child/start`. A successful plan is
stored for ten minutes, contains no raw argv, and binds the adapter, canonical workspaces,
resolved executable, argv digest, provider cell, verification scope, and operation digest.
`apply` requires the exact stored operation ID and digest, rejects input drift or replay,
journals before launch, starts one direct child without a shell, and records identity and
result receipts. Stop, restart, watchdog, and non-Windows cells still refuse with
`CAPABILITY_NOT_CERTIFIED`.
