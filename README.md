# Local Server Ops

Local Server Ops is an evidence-bound agent skill and Python CLI for inspecting local
workspace HTTP services. Version 0.3.0 preserves deterministic read-only inspection and
adds one narrowly certified mutation cell: Windows `psutil/direct_child/start`. Every
other lifecycle cell remains refused.

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

Version 0.3.0 can plan and apply only Windows direct-child start after adapter opt-in and
exact-plan approval. It journals before launch, verifies the spawned child's complete
identity, and records local launch/result receipts. Stop, restart, watchdog, non-Windows,
and unverifiable operations return typed refusals; do not bypass them with raw commands.

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
and Windows direct-child start contracts. It does not establish production reliability,
stop/restart safety, complete cross-platform support, or ownership without an exact
matching launch receipt.
