# Validation Authority

This directory contains the release-candidate evidence for Server Ops 0.2.1.

- [`release-candidate-test-receipt.json`](release-candidate-test-receipt.json)
  records 75 passing local tests, package digest
  `446d450279503dd2eb176fa1434a250d2344106e449f47b514c8cf01f4c6e79e`,
  and explicit limits.
- [`component-map/accepted-map.json`](component-map/accepted-map.json) is the
  owner-accepted map `component-map-09678f4a5fc5` with SHA-256
  `0d44a002c1763c3dac8252e6e6287e277d184dd0e4138f7d157f507c1afb81bb`.
- [`managed-workflow-pin-v083-receipt.json`](managed-workflow-pin-v083-receipt.json)
  records the focused and substantive local pin checks and their limits.
- [`managed-workflow-pin-v083-input.json`](managed-workflow-pin-v083-input.json)
  is the reviewed v2 pin input.
- [`history/20260827T070210659923Z-bc0977f0.json`](history/20260827T070210659923Z-bc0977f0.json)
  is the current append-only semantic authority, with deterministic
  [report](reports/20260827T070210659923Z-bc0977f0.md) and canonical digest
  `8b891506dbe1de76ce47c3841c7df1f0451f0d9e337304c84da85a50ccbfbeb9`.

Earlier release records, inputs, and maps remain immutable historical states.
The current `PARTIAL` release-candidate record does not establish protected managed-repair
environments, hosted canary, agent execution, draft publication, producer
PR/main CI, merge, publication, public install/update, or live client
activation.
