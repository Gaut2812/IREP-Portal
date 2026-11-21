# Cyber Range hub (S12). NEEDS A PERSON'S REVIEW. Same model as infra/labs: the portal's labs service
# is the only client; one workstation per approved session, on the internal range network only.
import os

c = get_config()  # noqa: F821

c.JupyterHub.authenticator_class = "null"
c.JupyterHub.allow_named_servers = True
c.JupyterHub.named_server_limit_per_user = 1
c.JupyterHub.db_url = "sqlite:////srv/jupyterhub/data/jupyterhub.sqlite"
c.JupyterHub.cookie_secret_file = "/srv/jupyterhub/data/jupyterhub_cookie_secret"
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.hub_connect_ip = "gateway"
c.JupyterHub.services = [
    {"name": "irep-labs", "api_token": os.environ["RANGE_SERVICE_TOKEN"]},
    {"name": "idle-culler", "command": ["python3", "-m", "jupyterhub_idle_culler", "--timeout=1800", "--max-age=5400",
                                        "--remove-named-servers"]},     # 90 min hard cap, like the portal's session
]
c.JupyterHub.load_roles = [
    {"name": "irep-labs", "services": ["irep-labs"], "scopes": ["admin:users", "admin:servers", "tokens", "read:users"]},
    {"name": "idle-culler", "services": ["idle-culler"], "scopes": ["list:users", "read:users:activity", "read:servers", "delete:servers"]},
]
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"
c.DockerSpawner.image = os.environ.get("RANGE_WORKSTATION_IMAGE", "irep/range-workstation:1")
c.DockerSpawner.network_name = "irep-cyber-range"          # internal: targets only, nothing outside
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.remove = True
c.DockerSpawner.extra_create_kwargs = {"user": "1000"}
c.DockerSpawner.extra_host_config = {"pids_limit": 256, "cap_drop": ["ALL"], "cap_add": ["NET_RAW"],   # NET_RAW for ping/nmap only
                                     "security_opt": ["no-new-privileges"], "init": True, "memswap_limit": "2G"}
c.Spawner.mem_limit = "2G"
c.Spawner.cpu_limit = 1.0
c.Spawner.default_url = "/lab"
c.Spawner.environment = {"JUPYTERHUB_ALLOW_TOKEN_IN_URL": "1", "RANGE_TARGETS": "http://juice-shop:3000 http://dvwa"}


def pre_spawn(spawner):
    profile = (spawner.user_options or {}).get("profile", "cyber-range")
    if profile != "cyber-range":
        raise ValueError("This hub only runs the Cyber Range workstation")


c.Spawner.pre_spawn_hook = pre_spawn
