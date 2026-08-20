from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from server_ops import discovery
from server_ops.models import MatchSpec


class FakeProcess:
    def __init__(self, info, ports=()):
        self.info = info
        self.ports = ports

    def net_connections(self, kind):
        assert kind == "inet"
        return [SimpleNamespace(status="LISTEN", laddr=SimpleNamespace(port=port)) for port in self.ports]

    def cwd(self):
        return self.info["cwd"]

    def as_dict(self, attrs, ad_value=None):
        return {attribute: self.info.get(attribute, ad_value) for attribute in attrs}


class FakePsutil:
    class AccessDenied(Exception):
        pass

    CONN_LISTEN = "LISTEN"

    class NoSuchProcess(Exception):
        pass

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.processes = {
            10: FakeProcess({"pid": 10, "ppid": 1, "create_time": 123.0, "exe": "C:/Python/python.exe", "cmdline": ["python", "server.py"], "cwd": str(self.workspace)}, (8090,)),
            11: FakeProcess({"pid": 11, "ppid": 1, "create_time": 124.0, "exe": "C:/Python/python.exe", "cmdline": ["python", "other.py"], "cwd": str(self.workspace.parent)}),
        }

    def process_iter(self, attrs, ad_value=None):
        assert "create_time" in attrs
        return list(self.processes.values())

    def Process(self, pid):
        return self.processes[pid]

    def net_connections(self, kind):
        assert kind == "inet"
        return [SimpleNamespace(pid=10, status="LISTEN", laddr=SimpleNamespace(port=8090))]


def test_discovery_is_workspace_bounded_and_matching_is_explicit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(discovery, "psutil", FakePsutil(tmp_path))
    candidates = discovery.discover_workspace(tmp_path)
    assert [candidate.pid for candidate in candidates] == [10]
    assert candidates[0].listening_ports == (8090,)
    assert discovery.match_candidates(candidates, MatchSpec()) == []
    matched = discovery.match_candidates(candidates, MatchSpec(("server.py",), None, (8090,)))
    assert [candidate.pid for candidate in matched] == [10]
