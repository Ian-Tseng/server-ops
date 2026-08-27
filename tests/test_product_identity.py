from __future__ import annotations

import re
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib
from pathlib import Path

import server_ops


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "skills" / "server-ops"


def test_version_identity_is_synchronized() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == server_ops.__version__
    assert (PACKAGE / "VERSION").read_text(encoding="utf-8").strip() == server_ops.__version__
    assert pyproject["project"]["version"] == server_ops.__version__


def test_skill_metadata_and_ui_are_consistent() -> None:
    skill = (PACKAGE / "SKILL.md").read_text(encoding="utf-8")
    ui = (PACKAGE / "agents" / "openai.yaml").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: server-ops\n")
    assert "Local Server Ops" in ui
    assert "$server-ops" in ui
    assert "[TODO" not in skill + ui


def test_source_ledger_uses_immutable_commit_links() -> None:
    ledger = (PACKAGE / "references" / "source-ledger.md").read_text(encoding="utf-8")
    hashes = re.findall(r"/blob/([0-9a-f]{40})/", ledger)
    assert len(hashes) == 9
    assert "External text was not\ncopied" in ledger


def test_no_default_outbound_lifecycle_configuration() -> None:
    privacy = (PACKAGE / "PRIVACY.md").read_text(encoding="utf-8").casefold()
    assert "no analytics" in privacy
    assert "installation identity" in privacy
    assert not list(ROOT.glob("**/*analytics*"))


def test_root_and_package_release_authorities_are_synchronized() -> None:
    for relative in ("VERSION", "CHANGELOG.md", "LICENSE", "PRIVACY.md", "CITATION.cff"):
        assert (ROOT / relative).read_bytes() == (PACKAGE / relative).read_bytes()


def test_public_repository_has_one_installable_skill() -> None:
    skills = sorted(ROOT.glob("skills/*/SKILL.md"))
    assert skills == [PACKAGE / "SKILL.md"]
    assert not (ROOT / "SKILL.md").exists()
