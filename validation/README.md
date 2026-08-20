# Validation Authority

This directory contains the release-candidate evidence for Server Ops 0.1.2.

- [`release-candidate-test-receipt.json`](release-candidate-test-receipt.json)
  records 58 passing local tests, package digest
  `f4bec48344a670d30b6dc93902022b9b1ce398a56f9397e22050ca58149e04b1`,
  and explicit limits.
- [`component-map/accepted-map.json`](component-map/accepted-map.json) is the
  owner-accepted map `component-map-9338aa4e9535` with SHA-256
  `94e0afe6ce4b556d7b4ddaa6e8928aa0a26defe8e3b62e3e5d3babc330c652a6`.
- [`release-scan-v012-input.json`](release-scan-v012-input.json) is the
  reviewed v2 input.
- [`history/20260820T181728563514Z-5879212e.json`](history/20260820T181728563514Z-5879212e.json)
  is the current append-only semantic authority, with deterministic
  [report](reports/20260820T181728563514Z-5879212e.md) and canonical digest
  `a7f4c394a19081e2cbc77de33ba669af49bd8a35509205029e5185d406be098d`.

Earlier records and maps remain immutable historical states. The current
`PARTIAL` record does not establish protected managed-repair environments,
hosted canary, agent execution, draft publication, PR/main CI, publication,
public install/update, or live client activation.
