# Publishing

Only Ian-Tseng may accept the release evidence map, merge the release PR, or publish a
version.

1. Keep root/package `VERSION`, `CHANGELOG.md`, `LICENSE`, `PRIVACY.md`, and
   `CITATION.cff` synchronized.
2. Rebuild and verify the package manifest:

       py -3 -X utf8 skills\server-ops\scripts\build_manifest.py
       py -3 -X utf8 skills\server-ops\scripts\verify_package.py

3. Run `py -3 -X utf8 -m pytest -q`. Replace `<skill-creator-root>` with the
   installed OpenAI `skill-creator` directory, then run the exact official validator:

       py -3 -X utf8 "<skill-creator-root>\scripts\quick_validate.py" skills\server-ops

4. Verify the accepted evidence map and the exact append-only record/report named in
   [validation/README.md](validation/README.md).
5. Land through a version-prefixed PR and wait for every PR matrix job.
6. Wait separately for the exact merged-main workflow.
7. Verify private vulnerability reporting, immutable releases, and an active no-bypass
   `refs/tags/v*` update/deletion ruleset.
8. Run `gh skill publish .\skills --dry-run`, then publish exactly once:

       gh skill publish .\skills --tag v0.1.1
9. Run `gh release verify v0.1.1` and verify the release/tag resolve to exact green main.
10. Use fresh disposable repositories to test Codex and Claude Code install, list,
    update dry-run, package verification, and available-client activation.

Do not call installation, discovery, invocation, mutation safety, or cross-platform
behavior verified until its exact gate has completed.
