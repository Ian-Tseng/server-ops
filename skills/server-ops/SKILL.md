---
name: server-ops
description: Inspect, diagnose, validate, and safely plan operations for local workspace HTTP services. Use when a developer asks whether a local server is running, healthy, bound to the intended checkout, or should be started, stopped, or restarted. Excludes production, remote hosts, containers/orchestrators, databases, and operating-system services.
license: MIT
metadata:
  short-description: Evidence-bound local server operations
---

# Local Server Ops

Use deterministic inspection before reasoning about a local service. Read-only commands
may run autonomously. Never infer mutation authority from this skill being selected.

## Start read-only

Run from the exact workspace root; do not search parent directories:

```powershell
py <skill-root>/scripts/server_ops.py --workspace <workspace> doctor
py <skill-root>/scripts/server_ops.py --workspace <workspace> status
```

Report what is observed, what is only corroboration, whether ownership is proven, what
health predicate ran, what changed, and one safe next action. A healthy response, PID,
port, process name, command substring, or working directory alone never proves ownership.

For command semantics and output contracts, read [references/operations.md](references/operations.md).
For adapter authoring or validation, read [references/adapter-contract.md](references/adapter-contract.md).

## Configure without enabling mutation

Preview the intended adapter path and explain that the draft is read-only before running:

```powershell
py <skill-root>/scripts/server_ops.py --workspace <workspace> init --draft --service <id>
py <skill-root>/scripts/server_ops.py --workspace <workspace> validate
```

Never overwrite an adapter, invent secret values, add shell strings, or convert discovery
evidence into ownership. Keep project-specific facts in `.server-ops.json`; do not patch
the reusable core for an ordinary adapter.

## Mutation gate

Before any start, stop, restart, force, or recovery side effect:

1. Require explicit user intent for the exact service and action.
2. Generate an immutable plan through the helper.
3. Show the target identity, ownership proof, provider cell, action, force policy,
   verification, expiry, and digest.
4. Obtain approval for that exact plan.
5. Apply only the unchanged stored operation and summarize its receipt.

Version 0.1.1 intentionally has no certified mutation provider. Its plan/apply commands
produce typed refusals and local receipts. Do not bypass that refusal with raw process,
shell, task-manager, port-kill, or supervisor commands. Read
[references/safety-and-evidence.md](references/safety-and-evidence.md) when mutation,
ownership, interruption, or recovery is involved.

## Boundaries and handoff

- Production, remote hosts, containers, Kubernetes, systemd, launchd, Windows Service
  Manager, and databases belong to their native operational workflows.
- Compose or another supervisor remains the lifecycle owner when it launched the service.
- `developer-friendly-monitor` owns progress, heartbeat, staleness, and long-running job
  presentation; this skill owns local service identity and operation evidence.
- Missing `psutil`, hidden process fields, ambiguous matches, changed adapters, or failed
  receipt persistence downgrade capability and never trigger installation or fallback.
- Run focused verification after health; health and compatibility are separate states.

The external design sources and exact adoption decisions are recorded in
[references/source-ledger.md](references/source-ledger.md). No telemetry, update check,
problem report, feedback, attachment, or diagnostic bundle is transmitted by default.
