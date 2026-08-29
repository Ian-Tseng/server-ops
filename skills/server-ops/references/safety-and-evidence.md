# Safety and Evidence

## Identity

Every future mutation cell requires PID, creation time, resolved executable, normalized
argv, and strategy-specific ownership evidence. Direct children require a matching launch
receipt. Watchdog children require anchored supervisor and child fingerprints plus their
proven relationship. Working directory and listeners are corroboration for ownership.
The v0.3.0 start cell also uses exclusive configured listeners as a pre-launch guard, but
a free-listener snapshot is not generic process-absence evidence.

A user assertion authorizes risk; it is not ownership evidence and cannot produce a
certified-safe result. If required fields are inaccessible, mutation is unavailable.

## States

Persist these separately:

- mutation: planned, refused, running, completed, failed;
- process: absent, observed, running, exited, ambiguous;
- start guard: listener_free_before_launch, listener_occupied, evidence_unavailable;
- supervisor: not_applicable, unproven, anchored, running, exited;
- health: not_checked, healthy, unhealthy;
- verification: not_run, passed, failed.

Never turn `mutation=completed, verification=failed` into unqualified success.

## Side effects

Future providers must follow:

```text
write intended transition -> atomic commit -> revalidate identity
-> one side effect -> observe -> write resulting transition
```

One owner-scoped workspace lock serializes mutation in v1. If state cannot be persisted,
identity drifts, a provider is uncertified, or authorization does not match the plan,
stop mutation and continue only bounded read-only observation.

The v0.3.0 Windows direct-child start cell implements this sequence with one workspace
lock, complete listener checks at plan and locked apply, a pre-launch transition,
shell-free `Popen` bound to a bounded non-reparse local-drive executable and its SHA-256,
with content rechecked under a Windows handle that denies write/delete replacement through
process creation, and exact child
observation including configured listener ownership. A plan is
single-use even if the child later exits. If post-launch identity verification fails, the
provider attempts to terminate only the exact child handle it just created and persist the
rollback outcome. Proven cleanup plus a persisted failure record returns mutation failure
with `side_effect_occurred=true`; unproven cleanup or result persistence returns recovery
required with the spawned PID, the same truthful side-effect state, and surviving
transition/log locators. This rollback is failure containment, not stop-provider
certification. Recovery-required outcomes retain a digest-bound workspace interlock;
subsequent plans and applies refuse before launch. Read-only recovery inspection reports
the marker and surviving locators without changing them.
The child writes stdout/stderr to `DEVNULL`; the provider log is a fixed bounded policy
marker. This prevents long-lived service output from exhausting owner-local state or
silently persisting arbitrary application data.

Normal Ctrl+C during child observation is routed through the same exact-child rollback.
If any Python control-flow exception, including Ctrl+C or SystemExit, occurs after process creation is entered but before an exact child handle
is available, the provider fails closed as `launch_outcome_unproven`, reports a possible
side effect with no fabricated PID, and retains the recovery interlock.
The outer recovery handler first retains the raw mutation lock, before terminating a known
child or writing failure evidence. Python control-flow exceptions during termination,
result persistence, or marker persistence therefore cannot make the workspace appear
clear; a failed structured marker leaves the raw lock `active_or_unreconciled`.
The typed `PLAN_INPUT_DRIFT` fast refusal also requires launch-entry evidence to remain
false, preventing an exception-code collision from clearing an already-unproven launch.
Hard termination can still leave an applying transition, lock, or surviving child, and
descendant containment is not certified. Preserve that state for manual reconciliation;
the read-only recovery command does not prove cleanup or authorize lock deletion.
`status` and `diagnose` surface structured and unreconciled workspace interlocks and
make reconciliation the next action instead of presenting health verification as safe.

## Claim boundary

Package validation proves structure. Deterministic tests prove only their fixtures.
A validated local receipt records its product version, adapter digest, canonical workspace,
actual provider cell, platform, action, and verification scope. Its canonical digest detects
unexpected content drift; it is not an external attestation, and an actor who can rewrite
owner-local state can recompute it. Reusability requires independently certified matrix
cells and adapter-only adoption evidence; fixture counts alone are insufficient.
