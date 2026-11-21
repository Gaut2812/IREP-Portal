# JupyterHub for IREP server labs (labs track). NEEDS A PERSON'S REVIEW before any deployment.
#
# Model: students never log in to JupyterHub. The portal's labs service (apps/api,
# LAB_ADAPTER=jupyterhub) creates a pseudonymous hub user per student, starts one named
# server per lab session with a profile, and hands the student a short-lived token
# scoped to that one server. Entitlement, quotas, approvals and metering stay in the portal.
#
# Runs on a lab node, never on the database or API host (Master Plan: "Labs and Judge0:
# default-deny outbound traffic, block cloud metadata and the portal subnet, CPU and
# process limits, mining-port blocks, maximum session age").
import os

c = get_config()  # noqa: F821  (provided by JupyterHub)

# --- the portal is the only client -------------------------------------------------------
c.JupyterHub.authenticator_class = "null"            # no login page; access is by scoped token only
c.JupyterHub.allow_named_servers = True
c.JupyterHub.named_server_limit_per_user = 1         # one lab per student at a time (the portal enforces it too)
c.JupyterHub.redirect_to_server = False
c.JupyterHub.db_url = "sqlite:////srv/jupyterhub/data/jupyterhub.sqlite"
c.JupyterHub.cookie_secret_file = "/srv/jupyterhub/data/jupyterhub_cookie_secret"

c.JupyterHub.services = [
    {"name": "irep-labs", "api_token": os.environ["IREP_LABS_SERVICE_TOKEN"]},       # the portal's labs service
    {"name": "idle-culler", "command": ["python3", "-m", "jupyterhub_idle_culler",
                                        "--timeout=1800",          # 30 min idle, same as the portal
                                        "--max-age=10800",         # hard cap 3 h whatever the portal says
                                        "--remove-named-servers"]},
]
c.JupyterHub.load_roles = [
    {"name": "irep-labs", "services": ["irep-labs"],
     "scopes": ["admin:users", "admin:servers", "tokens", "read:users"]},
    {"name": "idle-culler", "services": ["idle-culler"],
     "scopes": ["list:users", "read:users:activity", "read:servers", "delete:servers"]},
]

# --- spawning: one container per session, image and limits from the profile ------------------
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.hub_connect_ip = "jupyterhub"
c.DockerSpawner.network_name = os.environ.get("LAB_NETWORK", "irep-labs-users")   # internal network: no egress at all
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.remove = True                       # nothing survives a session (students copy out what they keep)
c.DockerSpawner.name_template = "irep-lab-{username}-{servername}"
c.DockerSpawner.extra_host_config = {
    "pids_limit": 256,
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges"],
    "init": True,
    "memswap_limit": None,                          # set per profile below (same as mem_limit: no swap)
}
c.DockerSpawner.extra_create_kwargs = {"user": "1000"}
c.Spawner.default_url = "/lab"
c.Spawner.http_timeout = 120
c.Spawner.start_timeout = 300
c.Spawner.environment = {"JUPYTERHUB_ALLOW_TOKEN_IN_URL": "1"}   # the portal opens the server with ?token=

REGISTRY = os.environ.get("LAB_IMAGE_REGISTRY", "irep")
PROFILES = {
    "linux":     {"image": f"{REGISTRY}/lab-linux:1",     "mem": "1G", "cpu": 1.0},
    "ai-cpu":    {"image": f"{REGISTRY}/lab-ai-cpu:1",    "mem": "4G", "cpu": 2.0},
    "fullstack": {"image": f"{REGISTRY}/lab-fullstack:1", "mem": "2G", "cpu": 1.5},
    # "cyber-range" never runs here: it has its own isolated node (infra/cyber-range, S12).
}
if os.environ.get("LAB_SYSBOX") == "1":
    # Docker & Kubernetes (S11): only on nodes with the Sysbox runtime installed. Container root is
    # an unprivileged host uid under Sysbox, so dockerd and kind run without --privileged.
    PROFILES["docker-k8s"] = {"image": f"{REGISTRY}/lab-docker-k8s:1", "mem": "6G", "cpu": 2.0, "sysbox": True}


def pre_spawn(spawner):
    profile = (spawner.user_options or {}).get("profile", "linux")
    p = PROFILES.get(profile)
    if p is None:
        raise ValueError(f"Unknown or disabled lab profile: {profile}")
    spawner.image = p["image"]
    spawner.mem_limit = p["mem"]
    spawner.cpu_limit = p["cpu"]
    host = {**spawner.extra_host_config, "memswap_limit": p["mem"]}
    if p.get("sysbox"):
        host = {**host, "runtime": "sysbox-runc", "pids_limit": 2048}
        host.pop("cap_drop", None)              # capabilities are namespaced by Sysbox; dockerd needs them inside
        spawner.extra_create_kwargs = {"user": "0"}   # start.sh runs the dockerd hook as root, then drops to jovyan
    else:
        spawner.extra_create_kwargs = {"user": "1000"}
    spawner.extra_host_config = host
    spawner.environment = {**spawner.environment, "IREP_LAB_PROFILE": profile,
                           "IREP_LAB_SESSION": str((spawner.user_options or {}).get("session", ""))}


c.Spawner.pre_spawn_hook = pre_spawn
