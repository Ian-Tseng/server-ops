# Local Server Ops

Local Server Ops is an agent skill and Python CLI for evidence-bound inspection of local
workspace services. Version 0.2.1 is deliberately read-only: it discovers processes,
strictly validates project adapters, runs bounded literal-loopback health predicates,
reports exact capability cells, and records mutation refusals without changing processes.

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
`$CODEX_HOME/backups/server-ops`, outside the active skill registry. Version 0.2.1 also
migrates verified legacy `skills/server-ops.backup-*` directories to that location and
refuses unverified legacy backups.

If installation returns `INSTALL_RECOVERY_REQUIRED`, do not retry. Preserve and inspect
the reported destination, backup, and staging paths; the filesystem outcome is explicitly
unknown until manually reconciled.

## Evidence boundary

Passing tests establishes only the tested adapter, discovery, health, output, and refusal
contracts. Version 0.2.1 does not claim a certified start, stop, or restart provider, live
production reliability, or complete cross-platform support.
