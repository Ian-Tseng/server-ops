# Validation Authority

This directory contains the release-candidate evidence for Server Ops 0.1.2.

- [`release-candidate-test-receipt.json`](release-candidate-test-receipt.json)
  records 58 passing local tests, package digest
  `f4bec48344a670d30b6dc93902022b9b1ce398a56f9397e22050ca58149e04b1`,
  and explicit limits.
- [`component-map/accepted-map.json`](component-map/accepted-map.json) is the
  owner-accepted map `component-map-ff2371924e59` with SHA-256
  `3cbe90f8994ad09cf919ef1b0e9d32c382b2b2bdaffeff397fe03b28d6f070a3`.
- [`release-scan-v012-input.json`](release-scan-v012-input.json) is the
  reviewed v2 input.
- [`history/20260820T172647921263Z-d5c3fa25.json`](history/20260820T172647921263Z-d5c3fa25.json)
  is the current append-only semantic authority, with deterministic
  [report](reports/20260820T172647921263Z-d5c3fa25.md) and canonical digest
  `69f923b3f47722c7684fc1e08e572dd0daf57911ecef39725e8f941e373661d0`.

Earlier records and maps remain immutable historical states. The current
`PARTIAL` record does not establish protected managed-repair environments,
hosted canary, agent execution, draft publication, PR/main CI, publication,
public install/update, or live client activation.
