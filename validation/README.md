# Validation Authority

This directory contains the release-candidate evidence for Server Ops 0.1.2.

- [`release-candidate-test-receipt.json`](release-candidate-test-receipt.json)
  records 58 passing local tests, package digest
  `f4bec48344a670d30b6dc93902022b9b1ce398a56f9397e22050ca58149e04b1`,
  and explicit limits.
- [`component-map/accepted-map.json`](component-map/accepted-map.json) is the
  owner-accepted map `component-map-9d2207994405` with SHA-256
  `d4893ecd8ef7ec44885dbaabe67034ccc3c05701fd0b33f97bef1814a16bf4c1`.
- [`release-scan-v012-input.json`](release-scan-v012-input.json) is the
  reviewed v2 input.
- [`history/20260820T161835496304Z-b294247f.json`](history/20260820T161835496304Z-b294247f.json)
  is the current append-only semantic authority, with deterministic
  [report](reports/20260820T161835496304Z-b294247f.md) and canonical digest
  `8df3f657733e1baacd2d13263b1ab98dd8d13d20505912034b11b773866ca5d8`.

Earlier records and maps remain immutable historical states. The current
`PARTIAL` record does not establish protected managed-repair environments,
hosted canary, agent execution, draft publication, PR/main CI, publication,
public install/update, or live client activation.
