# Validation Authority

This directory contains the release-candidate evidence for Server Ops 0.1.2.

- [`release-candidate-test-receipt.json`](release-candidate-test-receipt.json)
  records 58 passing local tests, package digest
  `f4bec48344a670d30b6dc93902022b9b1ce398a56f9397e22050ca58149e04b1`,
  and explicit limits.
- [`component-map/accepted-map.json`](component-map/accepted-map.json) is the
  owner-accepted map `component-map-cdc677b9e2a7` with SHA-256
  `e9ca67cc89713c5ac5cc370d5bb244a6120094bb951e26c8695df696d8d16abe`.
- [`managed-workflow-pin-v083-receipt.json`](managed-workflow-pin-v083-receipt.json)
  records the focused and substantive local pin checks and their limits.
- [`managed-workflow-pin-v083-input.json`](managed-workflow-pin-v083-input.json)
  is the reviewed v2 pin input.
- [`history/20260825T044823321045Z-980e266b.json`](history/20260825T044823321045Z-980e266b.json)
  is the current append-only semantic authority, with deterministic
  [report](reports/20260825T044823321045Z-980e266b.md) and canonical digest
  `b2ef5e643dd1989fa943c7bc02c380c8d94a7d622cdb30a7b9e0f5abb2607439`.

Earlier release records, inputs, and maps remain immutable historical states.
The current `PARTIAL` pin record does not establish protected managed-repair
environments, hosted canary, agent execution, draft publication, producer
PR/main CI, merge, publication, public install/update, or live client
activation.
