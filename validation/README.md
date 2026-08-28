# Validation Authority

This directory contains the current release-candidate evidence for Server Ops
0.3.0.

Status: `validated_local_acceptance_pr_ci_pending`

- [`release-candidate-test-receipt.json`](release-candidate-test-receipt.json)
  records 110/110 passing post-acceptance tests, package digest
  `30ce2206f7c9e14264f439fb53a473095017091b03f7e3fc8288fbfe2d607c37`,
  validator success, and `LOCAL_ACCEPTANCE_COMPLETE`.
- [`component-map/candidates/20260828T121546878759Z-cf0bbbcb-component-map-1b71ca68d45f.json`](component-map/candidates/20260828T121546878759Z-cf0bbbcb-component-map-1b71ca68d45f.json)
  is the exact immutable repaired candidate accepted by the owner as
  `component-map-1b71ca68d45f`.
  Its exact file SHA-256 is
  `d9982232d458e09307d88875950d5e0470eaa6db108e62112aa9735315d72547`;
  all 55 source hashes and all 55 raw-versus-Git-clean identities match. It
  changes seven source hashes to make malformed JSON array/object port values
  return the stable `MATCH_PORTS` refusal instead of an internal CLI error.
- [`component-map/candidates/20260828T103649217547Z-54bea1f3-component-map-4064f503e9fb.json`](component-map/candidates/20260828T103649217547Z-54bea1f3-component-map-4064f503e9fb.json)
  was the exact immutable candidate accepted by the owner as
  `component-map-4064f503e9fb`.
  Its exact file SHA-256 is
  `1e36315b8b3668bf68361ddc3ab5c9f9b62dce24b8f767b6634c5f401e669cff`;
  all 55 source hashes and all 55 raw-versus-Git-clean identities match. The
  clean typed-plan-drift path additionally requires proof that process
  creation was never entered. Its source snapshot predates the adapter repair,
  so it does not authorize the current working tree.
- [`component-map/candidates/20260828T102514869209Z-ce4016c6-component-map-4a18be830ccf.json`](component-map/candidates/20260828T102514869209Z-ce4016c6-component-map-4a18be830ccf.json)
  is immutable superseded evidence, `component-map-4a18be830ccf`.
  Its exact file SHA-256 is
  `a2cdaf135e46caf18a0cd0ab9de2d177f79ba794e792d8240dc680ce62abe378`;
  all 55 source hashes match. It retains the raw workspace lock before
  rollback or journaling and catches control-flow exceptions through structured
  marker persistence, leaving either a verified marker or a fail-closed raw lock,
  but its typed drift reset did not yet bind launch-entry evidence.
- [`component-map/candidates/20260828T101141501350Z-2cb1af30-component-map-062b460761b8.json`](component-map/candidates/20260828T101141501350Z-2cb1af30-component-map-062b460761b8.json)
  is immutable superseded evidence, `component-map-062b460761b8`.
  Its exact file SHA-256 is
  `628d03c56b5310e9a90374e4c257392ccfaa3c6ab0600a55107087e53e0dca88`;
  all 55 source hashes match. It catches `BaseException` around the mutation
  containment path so `SystemExit`, Ctrl+C, and ordinary exceptions cannot
  release the interlock after an unproven process-creation outcome, but it did
  not yet retain the lock before rollback/journal failure and is not acceptable.
- [`component-map/candidates/20260828T095926018327Z-145c4baa-component-map-23f1ea29981e.json`](component-map/candidates/20260828T095926018327Z-145c4baa-component-map-23f1ea29981e.json)
  is immutable superseded evidence, `component-map-23f1ea29981e`.
  Its exact file SHA-256 is
  `7b97fe3a7494cc9de06052bb04553eaa7523d414d7f2eae5cb3fc3a345371b2b`;
  all 55 source hashes match. It extends the conservative process-creation
  boundary from Ctrl+C to every exception that exits `Popen` without an exact
  child handle, but it did not yet cover `SystemExit` and is not acceptable.
- [`component-map/candidates/20260828T092344612263Z-ba7fa18c-component-map-aabf8af8bb5c.json`](component-map/candidates/20260828T092344612263Z-ba7fa18c-component-map-aabf8af8bb5c.json)
  is the exact immutable candidate accepted by the owner as
  `component-map-aabf8af8bb5c`.
  Its exact file SHA-256 is
  `98b3360330905c2fc82e8ea17fd4d132236008df74e3113193d570176e83030c`.
  It retains the executable-content and LF repairs and adds conservative
  `launch_outcome_unproven` recovery when Ctrl+C prevents exact child-handle
  recovery at the process-creation boundary.
  Earlier candidates remain immutable superseded history and are not
  acceptable substitutes for this acceptance.
- [`component-map/accepted-map.json`](component-map/accepted-map.json) is the
  current accepted map `component-map-1b71ca68d45f`, canonical-file SHA-256
  `2781fb78ac9627fe445ebb0bb983bfa8c896667502f5c5b2f8e823ab7ad8f2ab`.
  The immediately preceding accepted map is preserved at
  [`component-map/accepted-history/20260828T122212944269Z-be924617-component-map-4064f503e9fb.json`](component-map/accepted-history/20260828T122212944269Z-be924617-component-map-4064f503e9fb.json).
- [`component-map/accepted-history/20260828T071258344058Z-3fbc1e96-component-map-9f1011b674b7.json`](component-map/accepted-history/20260828T071258344058Z-3fbc1e96-component-map-9f1011b674b7.json)
  preserves an earlier accepted map; the later
  `component-map-e959500caf18` is preserved at
  [`component-map/accepted-history/20260828T085305102551Z-f7ae1757-component-map-e959500caf18.json`](component-map/accepted-history/20260828T085305102551Z-f7ae1757-component-map-e959500caf18.json).
  The earlier `component-map-03ef25335da3` is preserved at
  [`component-map/accepted-history/20260828T092908980290Z-c188467d-component-map-03ef25335da3.json`](component-map/accepted-history/20260828T092908980290Z-c188467d-component-map-03ef25335da3.json).
- [`history/20260828T093239804671Z-765723d4.json`](history/20260828T093239804671Z-765723d4.json)
  remains immutable semantic history. The current append-only semantic authority is
  [`history/20260828T122744159205Z-3ae711ec.json`](history/20260828T122744159205Z-3ae711ec.json),
  with deterministic
  [report](reports/20260828T122744159205Z-3ae711ec.md) and canonical payload
  digest
  `765a7ff1f8a5256db64962f030f950d035788914de356c122a565cfd45e67b29`.
  The accepted-map bridge audit
  `20260828T122519806610Z-c3210eb5` remains immutable history.
- [`managed-workflow-pin-v083-receipt.json`](managed-workflow-pin-v083-receipt.json)
  and [`managed-workflow-pin-v083-input.json`](managed-workflow-pin-v083-input.json)
  remain the reviewed managed-repair pin evidence.

Earlier release records, inputs, and maps remain immutable historical states.
The previously accepted repaired candidate established package verification and
the 100-test local Windows gate. Final adversarial review found that Ctrl+C
could arrive after Windows created a process but before the outer child variable
received its handle, allowing false `not_started` evidence and lock release. The
new regression failed first and now passes; the provider recovers an exact handle
when available and otherwise records `launch_outcome_unproven`, a possible side
effect, null PID, and a retained interlock. A subsequent ordinary-`OSError`
probe exposed the same gap outside Ctrl+C: its new red regression first returned
exit 4 with `side_effect_occurred=false`, then passed after the provider marked
entry into `Popen` unproven until it durably published an exact handle. The full
Windows provider file passed 24/24 and the pre-acceptance suite passed 100/100.
A further create-child-then-`SystemExit(73)` red test then escaped the provider
and left the recovery state clear. Catching `BaseException` across both launch
and mutation containment paths fixed that class: the Windows provider file now
passed 25/25, the pre-acceptance suite passed 101/101, and the exact 102-test
gate failed only on the stale accepted-map hash. Two further red probes raised
`SystemExit` during exact-child termination and failure-result journaling; both
escaped and cleared recovery state. The recovery handler now retains the raw
lock before either step and catches `BaseException` in rollback, journaling, and
structured marker writing. The two red tests pass, a third marker-write test
proves `active_or_unreconciled` fallback, the provider file passes 28/28, the
pre-acceptance suite passed 104/104, and the exact 105-test gate failed only on
the stale accepted-map hash. A final exception-code-collision probe then had
`Popen` create a child before raising `OpsError("PLAN_INPUT_DRIFT")`; the clean
fast path incorrectly returned exit 3 and cleared recovery. Requiring
`not launch_outcome_unproven` in that reset closes the collision. The red test
now passes, the provider file passes 29/29, and the pre-acceptance suite passes
105/105. The owner accepted exact candidate `component-map-4064f503e9fb`;
after the accepted-map bridge audit, the full post-acceptance suite passed
106/106 in 32.14 seconds and the final semantic audit verified. This state does
not cover the later adapter repair. Final pre-landing review then found that
runtime duplicate detection called `set()` before validating port types, so
otherwise valid JSON containing `match.ports: [[]]` or `[{}]` escaped as an
internal error. Four loader/CLI regressions failed first and now pass 4/4; the
complete adapter and CLI files pass 40/40. The rebuilt package verifies, the
pre-acceptance suite passes 109/109 in 32.11 seconds, and the exact 110-test
command reports only the expected stale accepted-map failure (109 passed, one
failed, 32.31 seconds). The owner then accepted exact candidate
`component-map-1b71ca68d45f`; bridge audit
`20260828T122519806610Z-c3210eb5` verified, the full post-acceptance suite passed
110/110 in 37.13 seconds, and final audit
`20260828T122744159205Z-3ae711ec` verified. This repaired state does
not establish PR matrix CI, exact
merged-main CI, tag protection, publication, public installation or
update, fresh activation, protected managed-repair environments, hosted
canary, agent execution, or draft publication.

Next action: complete fresh pre-landing audits, commit/push the accepted v0.3.0
source, open the version-prefixed PR, and require all six matrix jobs to pass. Merge,
publication, installation, and activation remain separate later gates.
