from __future__ import annotations

import json
import sys

from install_skill import ROOT, InstallRefusal, load_manifest, verify_tree


def main() -> int:
    try:
        manifest = load_manifest()
        problems = verify_tree(ROOT, manifest)
        if problems:
            raise InstallRefusal(", ".join(problems[:8]))
        print(json.dumps({"status": "PACKAGE_VERIFIED", "digest_sha256": manifest["manifest_digest"]}, sort_keys=True))
        return 0
    except (InstallRefusal, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "PACKAGE_INVALID", "message": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
