# Validation Authority

This directory contains the release-candidate evidence for Server Ops 0.2.0.

- [`release-candidate-test-receipt.json`](release-candidate-test-receipt.json)
  records 74 passing local tests, package digest
  `c6f9dacdebbaa31e0603a99f3521243bb0db738f16144548245fc9cd68fd905a`,
  and explicit limits.
- [`component-map/accepted-map.json`](component-map/accepted-map.json) is the
  owner-accepted map `component-map-90e4a2a3c26d` with SHA-256
  `760d461d12c467d7b52f0adf5e87f03f4f3d4c3880a0965406220e59dcd1e7c0`.
- [`managed-workflow-pin-v083-receipt.json`](managed-workflow-pin-v083-receipt.json)
  records the focused and substantive local pin checks and their limits.
- [`managed-workflow-pin-v083-input.json`](managed-workflow-pin-v083-input.json)
  is the reviewed v2 pin input.
- [`history/20260827T052430872937Z-d8530034.json`](history/20260827T052430872937Z-d8530034.json)
  is the current append-only semantic authority, with deterministic
  [report](reports/20260827T052430872937Z-d8530034.md) and canonical digest
  `c398f91b0bb1a22329728ff8e9b473b852341868c410b90ea6cc77ba13f615f1`.

Earlier release records, inputs, and maps remain immutable historical states.
The current `PARTIAL` pin record does not establish protected managed-repair
environments, hosted canary, agent execution, draft publication, producer
PR/main CI, merge, publication, public install/update, or live client
activation.
