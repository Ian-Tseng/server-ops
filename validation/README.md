# Validation Authority

This directory contains the current release-candidate evidence for Server Ops
0.3.0.

Status: `local_acceptance_complete`

- [`release-candidate-test-receipt.json`](release-candidate-test-receipt.json)
  records 112/112 passing post-acceptance tests, package digest
  `6c1c3c06b53a3899cf71475575370e491943c0c13f471799ad2ebd90008b5e62`,
  validator success, and `LOCAL_ACCEPTANCE_COMPLETE`.
- [`component-map/candidates/20260829T151655101597Z-e699a390-component-map-612853c2df78.json`](component-map/candidates/20260829T151655101597Z-e699a390-component-map-612853c2df78.json)
  is the exact immutable public-authority and provider-safety repair candidate
  accepted by the owner as `component-map-612853c2df78`. Its exact file
  SHA-256 is
  `b39ea9550ea20cad63802e0763e2efdc34e8b4a96e8697fe1ab8a31a9993f536`.
  All 55 source hashes and all 55 raw-versus-Git-clean identities match.
  Eighteen source hashes change, and the Windows start-provider element target
  now explicitly binds discarded child stdout/stderr, a fixed bounded provider
  marker, recovery-aware status/diagnosis, the repaired v0.3.0 security and
  provenance authorities, and their regressions.
- [`component-map/candidates/20260829T151507994427Z-74c1c749-component-map-d0a21cb16283.json`](component-map/candidates/20260829T151507994427Z-74c1c749-component-map-d0a21cb16283.json)
  is immutable superseded evidence with file SHA-256
  `b6b62e619c1352720515bb0cd23b6cefcf2f7d3214cd254920390e6b764b7c8a`;
  it predates the final mechanical validation-test cleanup and must not be
  accepted.
- [`component-map/candidates/20260829T150505210069Z-f1bf7614-component-map-a1d3e443e532.json`](component-map/candidates/20260829T150505210069Z-f1bf7614-component-map-a1d3e443e532.json)
  is immutable superseded public-authority-only evidence with file SHA-256
  `7ba9de270f6a03f3240535c8a40948b837c8653b648b86dd8a4b0b3d034ecb51`;
  it predates both provider-safety repairs and must not be accepted.
- [`component-map/candidates/20260829T150318953688Z-c4629f3e-component-map-ccae980f79a9.json`](component-map/candidates/20260829T150318953688Z-c4629f3e-component-map-ccae980f79a9.json)
  is immutable superseded evidence with file SHA-256
  `26cd98adc0d8e7bf01c555691bdfd15f22d287bf91ab05449924896171a0ae10`;
  it predates the truthful pending-acceptance test contract and must not be
  accepted.
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
  current accepted map `component-map-612853c2df78`, canonical-file SHA-256
  `8465ed19b3cfbfcaf4bf3f24d1c86ae5e081257f1dee293828006ec0ebff6445`.
  The immediately preceding accepted map is preserved at
  [`component-map/accepted-history/20260829T152552954964Z-78399ac0-component-map-1b71ca68d45f.json`](component-map/accepted-history/20260829T152552954964Z-78399ac0-component-map-1b71ca68d45f.json).
- [`component-map/accepted-history/20260828T071258344058Z-3fbc1e96-component-map-9f1011b674b7.json`](component-map/accepted-history/20260828T071258344058Z-3fbc1e96-component-map-9f1011b674b7.json)
  preserves an earlier accepted map; the later
  `component-map-e959500caf18` is preserved at
  [`component-map/accepted-history/20260828T085305102551Z-f7ae1757-component-map-e959500caf18.json`](component-map/accepted-history/20260828T085305102551Z-f7ae1757-component-map-e959500caf18.json).
  The earlier `component-map-03ef25335da3` is preserved at
  [`component-map/accepted-history/20260828T092908980290Z-c188467d-component-map-03ef25335da3.json`](component-map/accepted-history/20260828T092908980290Z-c188467d-component-map-03ef25335da3.json).
- [`history/20260828T122744159205Z-3ae711ec.json`](history/20260828T122744159205Z-3ae711ec.json)
  remains immutable semantic history. The current append-only semantic authority is
  [`history/20260829T152956210365Z-a1c9dfa4.json`](history/20260829T152956210365Z-a1c9dfa4.json),
  with deterministic
  [report](reports/20260829T152956210365Z-a1c9dfa4.md) and canonical payload
  digest
  `5a0f2e6cf092445c6f6e424e2cae9b81674a565f1bd78b9f1a1d33607696a024`.
  The accepted-map bridge audit
  `20260829T152756829910Z-cbde332c` remains immutable history.
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

Fresh pre-landing documentation review found that `SECURITY.md` and
`SOURCE.md` still described v0.2.1 while the candidate advertised v0.3.0,
and that citation dates predated publication. Specialist review then found an
unbounded inherited child-output log and status/diagnosis that could omit an
unresolved recovery interlock. The two provider regressions failed first and
now pass: the child uses `DEVNULL` with one fixed bounded provider marker,
and structured or raw recovery state overrides ordinary next-step advice.
The repaired pre-acceptance suite passes 111/111 in 36.67 seconds; the exact
112-test command reports only the expected stale accepted-map failure
(111 passed, one failed, 44.18 seconds).

The owner accepted exact candidate `component-map-612853c2df78` at SHA-256
`b39ea9550ea20cad63802e0763e2efdc34e8b4a96e8697fe1ab8a31a9993f536`.
Bridge audit `20260829T152756829910Z-cbde332c` verified the accepted structure;
the exact post-acceptance suite then passed 112/112 in 31.69 seconds, and final
audit `20260829T152956210365Z-a1c9dfa4` bound that receipt to the accepted map.

Next action: rerun the complete local release validation, commit and push the
accepted snapshot, open the approved version-prefixed PR, and require all six
matrix jobs to pass. Merge, publication, installation, and activation remain
separate later gates.

Final pre-landing audit status: `validated_for_pr_creation`. The independent
coverage audit counted 112 tests versus 75 on `origin/main` (+37), assessed 87%
coverage across 30 material paths, and found no P0/P1 gap. The independent plan
audit found no implementation or evidence contradiction, and the specialist
review found no race, shell-injection, recovery, identity, lifecycle, secret, or
release-claim blocker.

Pending non-blocking next implementation: add focused regressions for expired
plans, a matching process appearing between plan and apply, terminate-timeout
kill escalation, and tampered launch receipts in status/diagnose. Also link
`references/product-lifecycle.md` from a package entry point. Those mapped-source
changes are intentionally deferred because making them after exact acceptance
would invalidate `component-map-612853c2df78`; they require a later candidate,
validation run, and explicit acceptance. The immediate current gate remains the
approved PR plus all six matrix jobs.
