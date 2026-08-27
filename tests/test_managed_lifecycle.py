from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "skills" / "server-ops"
UPDATE_POLICY = PACKAGE / "scripts" / "update_policy.py"
OUTCOME = PACKAGE / "scripts" / "skill_outcome.py"


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class ManagedLifecycleTests(unittest.TestCase):
    def test_managed_repair_is_thin_sha_pinned_and_policy_bound(self):
        policy = json.loads((ROOT / ".github" / "managed-skill-policy.json").read_text(encoding="utf-8"))
        caller = (ROOT / ".github" / "workflows" / "managed-skill-repair.yml").read_text(encoding="utf-8")
        self.assertEqual(policy["repository"], {"default_branch": "main", "full_name": "Ian-Tseng/server-ops", "id": 1340553935})
        self.assertEqual(policy["workflow"]["sha"], "0fb28f50d9ed84ba47fdbdf2b7d0001f8b4e05b4")
        self.assertFalse(policy["enabled"])
        self.assertIn("@0fb28f50d9ed84ba47fdbdf2b7d0001f8b4e05b4", caller)
        self.assertIn("workflow-sha: 0fb28f50d9ed84ba47fdbdf2b7d0001f8b4e05b4", caller)
        self.assertNotIn("secrets: inherit", caller)
        self.assertNotIn("gh pr create", caller)

    def test_release_contains_managed_update_and_receipt_surfaces(self):
        self.assertTrue(UPDATE_POLICY.is_file())
        self.assertTrue(OUTCOME.is_file())
        self.assertTrue((PACKAGE / "scripts" / "_internal" / "safe_process.py").is_file())
        self.assertTrue((PACKAGE / "references" / "skill-outcome-receipt.schema.json").is_file())

    def test_skill_runs_maintenance_then_emits_one_trailing_receipt(self):
        skill = (PACKAGE / "SKILL.md").read_text(encoding="utf-8")
        maintenance = skill.index("scripts/update_policy.py --format json maintain")
        outcome = skill.index("scripts/skill_outcome.py --format json emit")
        self.assertLess(maintenance, outcome)
        self.assertIn("SKILL_OUTCOME_RECEIPT_V1:", skill)
        self.assertIn("final line", skill)
        self.assertIn("Ian-Tseng", skill)

    def test_emitter_binds_verified_package_without_project_content(self):
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(OUTCOME),
                "--format",
                "json",
                "emit",
                "--outcome",
                "completed_with_limitations",
                "--quality-signal",
                "claim_evidence_gap",
            ],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "RECEIPT_READY")
        marker = payload["marker"]
        self.assertTrue(marker.startswith("SKILL_OUTCOME_RECEIPT_V1:"))
        token = marker.split(":", 1)[1]
        decoded = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        receipt = json.loads(decoded.decode("utf-8"))
        self.assertEqual(canonical_bytes(receipt), decoded)
        self.assertEqual(
            receipt["producer"],
            {
                "owner": "Ian-Tseng",
                "repository": "server-ops",
                "skill": "server-ops",
                "version": "0.3.0",
                "package_digest_sha256": payload["package_digest_sha256"],
                "identity_authority": "producer_declared_untrusted",
            },
        )
        unsigned = dict(receipt)
        digest = unsigned.pop("receipt_digest_sha256")
        self.assertEqual(digest, hashlib.sha256(canonical_bytes(unsigned)).hexdigest())
        self.assertEqual(receipt["requested_action"], "analyze_quality")
        serialized = canonical_bytes(receipt).decode("ascii")
        for forbidden in ("prompt", "transcript", "project_path", "log", "patch", "token"):
            self.assertNotIn(forbidden, serialized)

    def test_no_issue_receipt_requests_no_followup(self):
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(OUTCOME),
                "--format",
                "json",
                "emit",
                "--outcome",
                "completed",
                "--quality-signal",
                "no_issue",
            ],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["receipt"]["requested_action"], "none")

    def test_update_policy_exposes_consent_gated_commands(self):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(UPDATE_POLICY), "--help"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("maintain", "enable", "disable", "status", "doctor", "check-now"):
            self.assertIn(command, result.stdout)


if __name__ == "__main__":
    unittest.main()
