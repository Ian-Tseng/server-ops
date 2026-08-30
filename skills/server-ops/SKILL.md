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
py <skill-root>/scripts/server_ops.py --workspace <workspace> verify <service>
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

Version 0.3.0 certifies only the Windows + psutil + direct-child + start cell. It
requires a mutation-enabled `direct_child` adapter, an absolute or trusted-PATH
executable that resolves to a non-reparse local-drive file no larger than 512 MiB, a
plan-bound executable SHA-256, a bounded launch argv/cwd,
at least one unique configured listener port treated by the owner as exclusive for the
service lifetime, a complete global listener snapshot showing that guard free, an
unexpired immutable plan, and the exact plan digest at apply. Apply checks the same guard
again under the workspace lock, rechecks executable content while a Windows handle denies
write/delete replacement through process creation. It journals intent before one child start and verifies
PID, creation time, executable, effective argv, cwd, configured listener ownership, and
the adapter match before persisting launch and result receipts. The listener snapshot is
not generic process-absence proof. Child stdout/stderr is discarded by default; the
provider log is a fixed bounded policy marker and never an unbounded service-output sink.
If post-spawn cleanup or result persistence is not
proved, the operation returns recovery-required with the spawned PID, transition and log
locators, `side_effect_occurred=true`, and a retained workspace interlock that refuses
later mutation plans and applies. If any Python control-flow exception, including Ctrl+C or SystemExit, exits process creation before the exact
child handle becomes available, report `launch_outcome_unproven`, a null PID, and a
conservative possible side effect under the same retained interlock. `recover inspect`
exposes that state without clearing it.
Recovery retains the raw workspace lock before rollback or failure journaling; a
control-flow exception during rollback, result persistence, or structured marker writing
therefore leaves either a verified recovery marker or an unreconciled raw lock.
A `PLAN_INPUT_DRIFT` exception clears the lock only when launch entry is proven false;
an identical error code after launch entry remains recovery-required.
`status` and `diagnose` always expose the workspace recovery state and prioritize
reconciliation when the interlock is structured, raw, invalid, or unreadable.
Stop, restart, watchdog, non-Windows, missing-psutil,
ambiguous, drifted, replayed, or unverifiable operations remain typed refusals. Do not
bypass those refusals with raw process, shell, task-manager, port-kill, or supervisor
commands. Read
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
- An external start can race after a free-listener snapshot. Hard termination can leave an
  applying transition, workspace lock, or surviving child; descendants are not contained.
  Preserve the state and reconcile identity manually. Do not remove the lock or claim
  recovery merely because the original CLI process exited.
- Keep fast status to one bounded probe. When the user asks to wait for readiness or
  verify stability, run `verify SERVICE`: it requires consecutive healthy observations
  within a bounded deadline and changes nothing.
- Diagnose from observed evidence: record the symptom, inspect relevant recent changes,
  test one explicit hypothesis at a time, and rerun focused verification. Health,
  stability, ownership, and schema compatibility are separate states.

The external design sources and exact adoption decisions are recorded in
[references/source-ledger.md](references/source-ledger.md). No telemetry,
problem report, feedback, attachment, or diagnostic bundle is transmitted by default.

## Finish with managed maintenance and one quality receipt

After completing the substantive operation and immediately before the final
response, run:

```text
<python-3> <skill-root>/scripts/update_policy.py --format json maintain
```

Maintenance is consent-gated, leased, and restricted to one clean, unpinned,
user-scope GitHub CLI installation from `Ian-Tseng/server-ops`. It must not
replace or shorten the operational result. Append its `message` and `action`
only when `emit` is true; a verified replacement activates on the next
invocation. An unconfigured or disabled policy transmits nothing.

Then emit exactly one content-free outcome receipt:

```text
<python-3> <skill-root>/scripts/skill_outcome.py --format json emit \
  --outcome <completed|completed_with_limitations|failed> \
  --quality-signal <claim_evidence_gap|lifecycle_inconsistency|documentation_mismatch|internal_failure|no_issue>
```

Append only the returned `SKILL_OUTCOME_RECEIPT_V1:` marker as the final line.
Use `no_issue` when no reusable skill-quality follow-up is warranted. The
marker contains no process arguments, workspace content, path, prompt, log, or
patch. It permits an installed `analyze-project-claims` adapter to create one
local proposal; it never authorizes an issue, edit, update, merge, release, or
operation. Any public issue remains a separate, twice-confirmed action
restricted to the `Ian-Tseng` owner boundary.

Repository-side repair is separate from this invocation. An owner-reviewed
`managed-repair-ready` issue may enter the full-SHA-pinned central workflow,
but the label is eligibility only: protected environments separately approve
credential-free candidate work and draft publication. The workflow cannot
accept evidence, merge, release, publish, update this installation, or prove
fresh activation. Never bypass the native updater or send project content as
feedback.
