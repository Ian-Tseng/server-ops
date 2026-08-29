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
- `recover inspect OPERATION_ID`: read one owner-scoped receipt, the workspace recovery
  interlock, and surviving result/transition locators; it changes and clears nothing.

Human output is concise. `--json` emits a versioned envelope and stable typed error codes.
Exit codes are: 0 success, 2 invalid input, 3 unsupported/refused, 4 mutation failure,
5 verification failure, 6 recovery required, and 7 internal error.

Process arguments may be inspected locally for bounded matching, but public JSON exposes
only their count and canonical digest, never raw argument values. Human command names and
errors are stripped of terminal control characters.
Both status forms expose the current workspace recovery interlock. Any non-clear state
overrides ordinary health or ownership next-step advice with manual reconciliation.

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
bounded local non-reparse resolved executable and content SHA-256, effective argv digest, unique exclusive configured
listener ports, complete free-listener observation, provider cell, verification scope, and
operation digest. `apply` requires the exact stored operation ID and digest, rejects input
drift or replay, rechecks the listener guard under the workspace lock, rechecks the executable
digest while a Windows read handle denies write/delete replacement through process creation,
journals before launch, starts one direct child without a shell, verifies the exact child owns a configured
listener, and records identity and result receipts. `listener_free_before_launch` is a
snapshot, not generic process absence. Stop, restart, watchdog, and non-Windows cells still
refuse with `CAPABILITY_NOT_CERTIFIED`.
The child inherits `DEVNULL` for stdout and stderr. The reported log contains one fixed
bounded provider-policy line; it does not retain arbitrary or unbounded service output.

An external start can race after the locked snapshot. Normal Ctrl+C during post-launch
observation is contained by terminating the exact child. If any Python control-flow
exception, including Ctrl+C or SystemExit, exits process
creation before the exact handle becomes available, the provider records
`launch_outcome_unproven`, conservatively reports a possible side effect with a null PID,
and retains the recovery interlock. A hard kill can still leave an
`applying` transition, workspace lock, or surviving child, and descendants are not
contained. `recover inspect` is read-only and does not clear this state; preserve it for
manual identity reconciliation. A rollback or failure-journal error returns exit 6 with
`rollback=termination_unproven` or `result_persistence=failed` and the surviving safe
transition/log locators. When `Popen` returned, it also reports
`side_effect_occurred=true` and the spawned PID. A failure before process creation is
entered reports false and a null PID; an unproven creation boundary reports
true and a null PID.
Before rollback or failure journaling begins, the handler retains the raw mutation lock.
A Python control-flow exception during termination or result persistence is recorded as
unproven recovery; if structured marker persistence is interrupted, the raw operation-ID
lock remains and is reported as `active_or_unreconciled`.
A `PLAN_INPUT_DRIFT` refusal uses the clean pre-launch path only when the launch state also
proves process creation was never entered; error-code identity alone cannot clear the lock.
The provider then retains a digest-bound `recovery_required` workspace interlock. Both a
new plan and any previously created plan fail closed while it remains. `recover inspect`
reports the interlock and surviving receipt locators but never clears them; owner-led
identity reconciliation is required before any out-of-band state repair.
