# Contributing

Open an issue before changing a trust boundary, adapter schema, provider capability, or
release contract. Keep project-specific facts in `.server-ops.json`; do not add them to
the reusable core.

Run:

    py -3 -X utf8 -m pytest -q
    py -3 -X utf8 skills\server-ops\scripts\build_manifest.py
    py -3 -X utf8 skills\server-ops\scripts\verify_package.py

Do not commit credentials, machine-private paths, runtime receipts, generated caches, or
unverified mutation providers.
