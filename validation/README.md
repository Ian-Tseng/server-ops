# Validation authority

This directory contains the release-candidate evidence for Server Ops 0.1.1.

- [`release-candidate-test-receipt.json`](release-candidate-test-receipt.json) records
  52 passing local tests, package digest
  `d9bb1546b46010013305f15085fe435dc2e62dd97e76a00d5c87595710df2e77`,
  and explicit limits.
- [`component-map/accepted-map.json`](component-map/accepted-map.json) is the
  owner-accepted map `component-map-45ec384c16a2` with SHA-256
  `8555494effce518d12095015530d23907ac3be9b998ac437666750771a1dc213`.
- `history/` contains append-only evidence-bound JSON records.
- `reports/` contains deterministic Markdown views of those records.

The current local semantic authority is
[`history/20260820T095705280604Z-6cbdb220.json`](history/20260820T095705280604Z-6cbdb220.json)
with deterministic
[`report`](reports/20260820T095705280604Z-6cbdb220.md), canonical digest
`7119993df62e4776eaaabf83311059e235a0b0beb1cf51ad5ea73943c86a20ca`.
Its `PARTIAL` status is intentional: it does not establish pending PR CI, exact-main
CI, publication, public install, or live client activation.
