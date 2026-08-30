# Local Server Ops

Local Server Ops is an agent skill and Python CLI for evidence-bound inspection of local
workspace services. Version 0.3.0 preserves strict read-only inspection and adds one
narrowly certified mutation cell: listener-guarded Windows
`psutil/direct_child/start`.

Install from GitHub:

```powershell
gh skill install Ian-Tseng/server-ops skills/server-ops/SKILL.md --agent codex --scope user
gh skill install Ian-Tseng/server-ops skills/server-ops/SKILL.md --agent claude-code --scope user
```

Start a fresh client session. Use `$server-ops` in Codex or `/server-ops` in
Claude Code. Managed updates remain consent-gated and are delegated to
`gh skill update server-ops` after package and installation identity checks.

```powershell
py scripts/server_ops.py --workspace C:\path\to\project doctor
py scripts/server_ops.py --workspace C:\path\to\project status
py scripts/server_ops.py --workspace C:\path\to\project verify my-server --deadline-ms 5000 --stable-successes 3
py scripts/server_ops.py --workspace C:\path\to\project init --draft --service my-server
py scripts/server_ops.py --workspace C:\path\to\project validate
```

Install the optional process-inspection dependency explicitly:

```powershell
py -m pip install "psutil>=5.9,<7"
```

No command installs dependencies automatically. No analytics, reporting, or
diagnostic-upload behavior is enabled. Update checks remain off until separately
enabled and never include workspace content. See `PRIVACY.md` and the references
linked from `SKILL.md`.

Build the deterministic install manifest and preview a Codex installation:

```powershell
py scripts/build_manifest.py
py scripts/verify_package.py
py scripts/install_skill.py --dry-run --json
```

Run the installer without `--dry-run` only after reviewing its destination. Updates require
`--update`, refuse modified installed files, and preserve verified rollback copies under
`$CODEX_HOME/backups/server-ops`, outside the active skill registry. Version 0.3.0 also
migrates verified legacy `skills/server-ops.backup-*` directories to that location and
refuses unverified legacy backups.

If installation returns `INSTALL_RECOVERY_REQUIRED`, do not retry. Preserve and inspect
the reported destination, backup, and staging paths; the filesystem outcome is explicitly
unknown until manually reconciled.

## Evidence boundary

Passing tests establishes only the tested adapter, discovery, health, output, refusal,
and listener-guarded Windows direct-child start contracts. The start cell requires at
least one unique configured listener port, a complete global listener snapshot that is
free at plan and locked apply, and a bounded local non-reparse executable whose SHA-256 is
plan-bound and rechecked under a Windows replacement-denying handle through process creation.
It verifies the exact spawned PID, effective argv, cwd, listener ownership, adapter match, and launch receipt.
Child stdout/stderr is discarded by default, and the provider log is a fixed bounded
policy marker rather than retained service output.
Any Python control-flow exception, including Ctrl+C or SystemExit, inside process creation is recovery-required when an exact child handle cannot be
recovered; the provider records `launch_outcome_unproven` and keeps the workspace interlock.
Recovery retains the raw workspace lock before termination and failure journaling, so a
control-flow exception in either step leaves later mutations fail-closed.
Typed plan drift clears the raw lock only when process creation is proven not entered.
`status` and `diagnose` expose any structured or unreconciled recovery interlock and
make reconciliation the next action.
Version 0.3.0 does not claim generic process absence, certified stop/restart/watchdog,
non-Windows mutation, production reliability, external-start race exclusion, hard-crash
recovery, descendant containment, or ownership when the exact evidence does not match.
