# Changelog

## 0.3.0 - 2026-08-28

- Certify only the listener-guarded Windows `psutil/direct_child/start` cell with explicit adapter opt-in,
  ten-minute immutable plans, exact-digest consent, and single-use replay protection.
- Require a unique exclusive configured port and complete free-listener evidence at plan
  and locked apply; never describe that snapshot as generic process absence.
- Reject malformed non-integer `match.ports` values through the stable `MATCH_PORTS`
  contract, including JSON arrays and objects that cannot be hashed, without falling
  through to an internal CLI error.
- Bind one shell-free launch to a bounded local non-reparse executable's SHA-256 and
  effective argv; recheck the digest while a Windows file handle denies replacement
  through process creation, then verify PID, creation time, executable, argv, listener ownership,
  cwd, and adapter match; persist launch/result evidence and prove ownership in status.
- Normalize CFF metadata under an explicit LF Git policy so accepted raw-byte evidence
  survives clean Windows, macOS, and Linux checkouts.
- Roll back only the exact spawned child when post-launch identity evidence fails; return
  recovery-required with the spawned PID and transition/log locators if cleanup or result
  persistence is unproven, and retain a workspace interlock that blocks later plans and
  applies until owner-led reconciliation.
- Treat any Python control-flow exception, including Ctrl+C or SystemExit, inside the process-creation boundary as
  `launch_outcome_unproven` when no
  exact child handle is available, conservatively retain the recovery interlock, and never
  claim that no side effect occurred in that window.
- Retain the raw workspace lock before rollback and failure journaling, catch Python
  control-flow exceptions in both steps, and preserve a fail-closed raw lock if structured
  recovery-marker persistence is itself interrupted; clear typed plan drift only when the
  process-creation boundary is proven not entered.
- Keep stop, restart, watchdog, non-Windows, drifted, ambiguous, and unverifiable cells
  fail-closed.
- Record external-start races, hard-crash recovery, and descendant containment as explicit
  non-production limitations.

## 0.2.1 - 2026-08-27

- Accept and integrity-bind GitHub CLI's installer-added `github-pinned` metadata so
  pinned public installs verify without weakening repository or ref checks.

## 0.2.0 - 2026-08-27

- Add an explicit read-only `verify` command with bounded deadlines and
  consecutive-success stability conditions.
- Document one-hypothesis-at-a-time diagnosis, recent-change evidence, and the
  separate meanings of health, stability, ownership, and compatibility.
- Expand the reviewed source ledger with popular condition-waiting,
  systematic-debugging, and service-health skill patterns.

## 0.1.2 - 2026-08-20

- Add a consent-gated GitHub-managed updater with a 24-hour lease and verified
  source, package, path, scope, pin, and tree postconditions.
- Emit one bounded, content-free `SkillOutcomeReceipt` after substantive use
  for optional local review by `analyze-project-claims`.
- Keep all service operations read-only and keep public issue creation behind
  separate exact confirmation within the `Ian-Tseng` owner boundary.

## 0.1.1 - 2026-08-20

- Moved update rollback copies outside the active Codex skill registry.
- Added verified migration of legacy sibling backups and refusal of unverified copies.
- Staged installations outside the registry and added rollback-safe migration tests.
- Rejected manifest path traversal and linked destination, backup, and staging boundaries.
- Restricted health to exact 127.0.0.1/::1 URLs without queries or redirect success.
- Added truthful recovery-required output when installer rollback cannot be completed.
- Added schema-checked, digest-verified refusal receipts bound to request and service workspaces.
- Redacted process arguments and sanitized terminal-facing error text.
- Pinned the complete Python 3.10/3.12 CI test dependency set.

## 0.1.0 - 2026-08-20

- Added strict versioned adapters and JSON Schema.
- Added adapter-free workspace discovery, doctor, status, diagnosis, and bounded loopback health.
- Added exact capability reporting and persistent refusal receipts.
- Added safe adapter draft generation and stable JSON/exit contracts.
- Added hash-verified installation, modified-target refusal, and rollback backups.
- Kept all mutation providers uncertified and unavailable.
