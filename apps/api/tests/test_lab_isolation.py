"""Lab isolation guardrails (labs track S11/S12). Nothing in infra/labs or infra/cyber-range can
run in CI, so this checks the configuration itself: the hub's spawner limits, the lab
networks, the Sysbox-only Docker & Kubernetes profile, and the Cyber Range's isolated network.
A change that weakens any of them fails here and goes to a person for review."""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

INFRA = Path(__file__).resolve().parents[3] / "infra"


class _Cfg(SimpleNamespace):
    """Enough of traitlets' Config for jupyterhub_config.py: attributes appear on first use."""

    def __getattr__(self, name):
        child = _Cfg()
        setattr(self, name, child)
        return child


def _load_hub(monkeypatch, sysbox="0"):
    monkeypatch.setenv("IREP_LABS_SERVICE_TOKEN", "t" * 64)
    monkeypatch.setenv("LAB_SYSBOX", sysbox)
    c = _Cfg()
    scope = {"get_config": lambda: c, "__file__": str(INFRA / "labs/hub/jupyterhub_config.py")}
    exec(compile((INFRA / "labs/hub/jupyterhub_config.py").read_text(encoding="utf-8"), "jupyterhub_config.py", "exec"), scope)
    return c, scope


def _spawn(scope, c, profile):
    sp = SimpleNamespace(user_options={"profile": profile, "session": "ls_x"}, extra_host_config=dict(c.DockerSpawner.extra_host_config),
                         environment=dict(c.Spawner.environment), extra_create_kwargs={})
    scope["pre_spawn"](sp)
    return sp


def test_hub_is_locked_down(monkeypatch):
    c, scope = _load_hub(monkeypatch)
    assert c.JupyterHub.authenticator_class == "null"                       # no login page; scoped tokens only
    assert c.JupyterHub.named_server_limit_per_user == 1 and c.DockerSpawner.remove is True
    host = c.DockerSpawner.extra_host_config
    assert host["cap_drop"] == ["ALL"] and "no-new-privileges" in host["security_opt"] and host["pids_limit"] <= 512
    assert "privileged" not in str(host).lower()
    roles = {r["name"]: r["scopes"] for r in c.JupyterHub.load_roles}
    assert set(roles["irep-labs"]) == {"admin:users", "admin:servers", "tokens", "read:users"}
    culler = next(s for s in c.JupyterHub.services if s["name"] == "idle-culler")["command"]
    assert "--timeout=1800" in culler and any(a.startswith("--max-age=") for a in culler)


def test_profiles_get_limits_and_unknown_ones_are_refused(monkeypatch):
    c, scope = _load_hub(monkeypatch)
    for profile in ("linux", "ai-cpu", "fullstack"):
        sp = _spawn(scope, c, profile)
        assert sp.mem_limit and sp.cpu_limit and sp.extra_create_kwargs["user"] == "1000"
        assert sp.extra_create_kwargs["labels"] == {"irep.session": "ls_x"}             # cAdvisor metering (S13)
        assert sp.extra_host_config["memswap_limit"] == sp.mem_limit and "runtime" not in sp.extra_host_config
    for refused in ("docker-k8s", "cyber-range", "root"):
        with pytest.raises(ValueError):
            _spawn(scope, c, refused)                                            # Sysbox off: no Docker profile


def test_docker_profile_only_with_sysbox(monkeypatch):
    c, scope = _load_hub(monkeypatch, sysbox="1")
    sp = _spawn(scope, c, "docker-k8s")
    assert sp.extra_host_config["runtime"] == "sysbox-runc" and "privileged" not in str(sp.extra_host_config).lower()
    with pytest.raises(ValueError):
        _spawn(scope, c, "cyber-range")


def test_lab_networks_have_no_way_out_except_the_registry_cache():
    compose = yaml.safe_load((INFRA / "labs/docker-compose.yml").read_text(encoding="utf-8"))
    assert compose["networks"]["irep-labs-users"]["internal"] is True
    on_egress = [n for n, svc in compose["services"].items() if "irep-labs-egress" in (svc.get("networks") or {})]
    assert on_egress == ["registry-cache"]
    assert all(not svc.get("privileged") for svc in compose["services"].values())
    assert compose["services"]["cadvisor"]["networks"] == ["irep-labs-hub"]                # metering: never on the lab network
    assert all(v.endswith(":ro") for v in compose["services"]["cadvisor"]["volumes"])


def test_cyber_range_is_isolated(monkeypatch):
    compose = yaml.safe_load((INFRA / "cyber-range/docker-compose.yml").read_text(encoding="utf-8"))
    nets, services = compose["networks"], compose["services"]
    assert nets["range-net"]["internal"] is True                                    # targets and workstations: no way out
    non_internal = [n for n, cfg in nets.items() if not cfg.get("internal")]
    assert non_internal == ["range-front"]
    for name, svc in services.items():
        assert not svc.get("privileged"), name
        if name != "gateway":
            assert "range-front" not in (svc.get("networks") or {}) and "ports" not in svc, name
    assert all(p.startswith("${RANGE_BIND") or p.startswith("127.0.0.1:") for p in services["gateway"]["ports"])

    monkeypatch.setenv("RANGE_SERVICE_TOKEN", "r" * 64)
    c = _Cfg()
    scope = {"get_config": lambda: c}
    exec(compile((INFRA / "cyber-range/hub/jupyterhub_config.py").read_text(encoding="utf-8"), "range_config.py", "exec"), scope)
    assert c.DockerSpawner.network_name == nets["range-net"]["name"]
    host = c.DockerSpawner.extra_host_config
    assert host["cap_drop"] == ["ALL"] and host["cap_add"] == ["NET_RAW"] and "no-new-privileges" in host["security_opt"]
    with pytest.raises(ValueError):
        scope["pre_spawn"](SimpleNamespace(user_options={"profile": "linux"}))     # this hub runs the range only


def test_cyber_range_never_runs_on_the_shared_lab_hub(monkeypatch):
    from core.config import settings
    from services import lab_orchestrator as lo
    monkeypatch.setattr(settings, "LAB_ADAPTER", "jupyterhub")
    monkeypatch.setattr(settings, "JUPYTERHUB_API_TOKEN", "lab-token")
    monkeypatch.setattr(settings, "CYBER_RANGE_HUB_URL", "")
    with pytest.raises(lo.LabLaunchError) as e:
        lo.get_lab_adapter(isolated=True)
    assert e.value.reason == "range_unavailable"
    monkeypatch.setattr(settings, "CYBER_RANGE_HUB_URL", "http://range:8000")
    monkeypatch.setattr(settings, "CYBER_RANGE_API_TOKEN", "range-token")
    adapter = lo.get_lab_adapter(isolated=True)
    assert adapter.base == "http://range:8000" and adapter.token == "range-token"
    assert lo.get_lab_adapter().base != "http://range:8000"
