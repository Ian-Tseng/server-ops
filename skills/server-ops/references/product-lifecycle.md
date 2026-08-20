# Product Lifecycle

Canonical source:
`https://github.com/Ian-Tseng/server-ops` at `skills/server-ops`.

Installed target:
`$CODEX_HOME/skills/server-ops` or `~/.codex/skills/server-ops` when `CODEX_HOME` is unset.

The public repository, tagged release, package version, manifest digest, installed path,
and active invocation version are distinct identities. Update checks, replacement,
analytics, problem reports, feedback, attachments, and diagnostic upload are all
unconfigured/off. No installation identity is generated.

An installer must verify the source manifest, refuse an ambiguous or modified target,
stage outside the active skill registry, preserve rollback copies under
`$CODEX_HOME/backups/server-ops`, and verify the installed manifest. Managed updates
migrate only verified legacy `skills/server-ops.backup-*` directories and refuse an
unverified legacy copy or a backup root inside the active registry. A newly installed
skill becomes active in a fresh client session. GitHub-managed updates are explicit
through `gh skill update server-ops`; the bundled hash-verified installer is an
offline/local-source alternative, not an automatic updater.
