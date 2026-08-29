# Local Server Ops

Local Server Ops is an evidence-bound agent skill and Python CLI for inspecting local
workspace HTTP services. Version 0.3.0 preserves deterministic read-only inspection and
adds one narrowly certified mutation cell: listener-guarded Windows
`psutil/direct_child/start`. Every other lifecycle cell remains refused.

## Install

For Codex:

    gh skill install Ian-Tseng/server-ops skills/server-ops/SKILL.md --agent codex --scope user

For Claude Code:

    gh skill install Ian-Tseng/server-ops skills/server-ops/SKILL.md --agent claude-code --scope user

Start a fresh client session. Invoke `$server-ops` in Codex or `/server-ops` in
Claude Code. Installation establishes distribution, not client discovery or a successful
live invocation.

Updates remain user-controlled. The installed skill asks once before enabling
notification or automatic replacement, verifies one clean GitHub-managed user
installation, and checks through a 24-hour lease after substantive use:

    gh skill update server-ops --dry-run
    gh skill update server-ops

Pin the release when reproducibility matters:

    gh skill install Ian-Tseng/server-ops skills/server-ops/SKILL.md --agent codex --scope user --pin v0.3.0

## Read-only quickstart

From the exact workspace root:

Replace `<skill-root>` with the installed `server-ops` directory. Keep the substituted
path quoted so installations under a directory containing spaces remain runnable:

    py "<skill-root>\scripts\server_ops.py" --workspace . doctor
    py "<skill-root>\scripts\server_ops.py" --workspace . status
    py "<skill-root>\scripts\server_ops.py" --workspace . verify <service> --deadline-ms 5000 --stable-successes 3

Verify the installed package:

    py "<skill-root>\scripts\verify_package.py"

Version 0.3.0 can plan and apply only Windows direct-child start after adapter opt-in,
an exclusive configured listener port, a complete listener snapshot that shows the guard
free at plan time, and exact-plan approval. Apply checks the listener again under the
workspace lock, launches the resolved non-reparse executable from a local drive without a
shell, and binds its bounded content SHA-256 while a Windows file handle denies replacement
through process creation. It verifies the spawned PID's executable, effective argv, cwd, configured listener,
and adapter match, and records local launch/result receipts. Child stdout/stderr is
discarded by default; the reported provider log is a fixed bounded policy marker, not
service output. Stop, restart, watchdog,
non-Windows, and unverifiable operations return typed refusals; do not bypass them with
raw commands.
If a Python control-flow exception, including Ctrl+C or SystemExit, exits the process-creation boundary before an exact child handle is
available, the provider conservatively records `launch_outcome_unproven`, reports a
possible side effect, and retains the recovery interlock instead of claiming no launch.
The recovery handler retains the raw workspace lock before rollback or journal work; if
either step is interrupted, the structured marker or raw lock still blocks later mutation.
A typed plan-drift refusal clears that lock only when process creation was never entered.
Read-only `status` and `diagnose` always expose the workspace interlock and prioritize
manual reconciliation whenever recovery is not clear.

The listener snapshot is not generic proof that no related process exists. An unrelated
external start can race after the snapshot, hard process termination can leave an
`applying` transition, lock, or surviving child for manual reconciliation, and descendant
containment is not certified. This cell is for bounded local development, not production
supervision.

## GitHub-managed repair boundary

This repository carries one closed policy and one thin caller pinned to analyzer
workflow commit `0fb28f50d9ed84ba47fdbdf2b7d0001f8b4e05b4`. It copies no central repair implementation. A
label is triage eligibility only; protected environments gate the agent and
draft publication separately. Repair remains disabled until both method and
venue hosted canaries pass.

See the immutable [managed fleet quickstart](https://github.com/Ian-Tseng/analyze-project-claims/blob/0fb28f50d9ed84ba47fdbdf2b7d0001f8b4e05b4/docs/MANAGED_FLEET_QUICKSTART.md)
and [operations runbook](https://github.com/Ian-Tseng/analyze-project-claims/blob/0fb28f50d9ed84ba47fdbdf2b7d0001f8b4e05b4/docs/MANAGED_FLEET_OPERATIONS.md).

## Development

    py -3 -X utf8 -m pytest -q
    py -3 -X utf8 skills\server-ops\scripts\build_manifest.py
    py -3 -X utf8 skills\server-ops\scripts\verify_package.py

Release and evidence: [changelog](CHANGELOG.md), [publishing guide](PUBLISHING.md),
[validation authority](validation/README.md), and [source ledger](SOURCE.md).

Project policy: [contributing](CONTRIBUTING.md), [security](SECURITY.md),
[privacy](PRIVACY.md), [license](LICENSE), and [citation metadata](CITATION.cff).
The standalone package carries synchronized release authorities, including its
[privacy contract](skills/server-ops/PRIVACY.md).

Passing tests establishes only the tested adapter, discovery, health, output, refusal,
and listener-guarded Windows direct-child start contracts. It does not establish production reliability,
stop/restart safety, complete cross-platform support, or ownership without an exact
matching launch receipt.
