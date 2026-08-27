# Safety and Evidence

## Identity

Every future mutation cell requires PID, creation time, resolved executable, normalized
argv, and strategy-specific ownership evidence. Direct children require a matching launch
receipt. Watchdog children require anchored supervisor and child fingerprints plus their
proven relationship. Working directory and listeners are corroboration only.

A user assertion authorizes risk; it is not ownership evidence and cannot produce a
certified-safe result. If required fields are inaccessible, mutation is unavailable.

## States

Persist these separately:

- mutation: planned, refused, running, completed, failed;
- process: absent, observed, running, exited, ambiguous;
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
lock, a pre-launch transition, shell-free `Popen`, and exact child observation. A plan is
single-use even if the child later exits. If post-launch identity verification or receipt
persistence fails, the provider terminates only the exact child handle it just created,
records the rollback outcome, and returns mutation failure with
`side_effect_occurred=true`. This rollback is failure containment, not stop-provider
certification.

## Claim boundary

Package validation proves structure. Deterministic tests prove only their fixtures.
A validated local receipt records its product version, adapter digest, canonical workspace,
actual provider cell, platform, action, and verification scope. Its canonical digest detects
unexpected content drift; it is not an external attestation, and an actor who can rewrite
owner-local state can recompute it. Reusability requires independently certified matrix
cells and adapter-only adoption evidence; fixture counts alone are insufficient.
