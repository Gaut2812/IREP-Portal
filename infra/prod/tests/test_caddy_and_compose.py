"""Caddy per-IP limits on sign-in and OTP, upload size limits, and the Compose wiring.

Static checks always run. CADDY_IT=1 (CI builds irep-caddy:test from caddy.Dockerfile) also starts the
real Caddy with SIGNIN_RATE_PER_MIN=5 and proves the 6th sign-in POST from one IP gets 429.
"""
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

PROD = Path(__file__).resolve().parents[1]
CADDYFILE = (PROD / "Caddyfile").read_text(encoding="utf-8")


def _zone(name: str) -> str:
    m = re.search(r"zone " + name + r" \{(.*?)\n\t\t\}", CADDYFILE, re.S)
    assert m, f"zone {name} missing"
    return m.group(1)


def test_signin_and_otp_are_rate_limited_per_ip_on_both_domains():
    assert "order rate_limit before basicauth" in CADDYFILE
    app = _zone("signin_per_ip")
    for path in ("/api/v1/auth/login", "/api/v1/auth/parent/otp/request", "/api/v1/auth/parent/otp/verify"):
        assert path in app
    kc = _zone("kc_signin_per_ip")
    assert "/realms/*/login-actions/*" in kc
    for z in (app, kc):
        assert "method POST" in z and "key {remote_host}" in z and "events {$SIGNIN_RATE_PER_MIN:120}" in z and "window 1m" in z


def test_recordings_may_be_large_everything_else_25_mb():
    assert re.search(r"request_body @recording \{\s*max_size 600MB", CADDYFILE)
    assert re.search(r"request_body @not_recording \{\s*max_size 25MB", CADDYFILE)


def test_compose_builds_caddy_with_the_module_and_only_caddy_is_published():
    yaml = pytest.importorskip("yaml")
    compose = yaml.safe_load((PROD / "docker-compose.yml").read_text(encoding="utf-8"))
    caddy = compose["services"]["caddy"]
    assert caddy["build"]["dockerfile"] == "caddy.Dockerfile"
    assert "caddy-ratelimit" in (PROD / "caddy.Dockerfile").read_text(encoding="utf-8")
    assert {n for n, s in compose["services"].items() if s.get("ports")} == {"caddy"}
    assert caddy["environment"]["SIGNIN_RATE_PER_MIN"] == "${SIGNIN_RATE_PER_MIN:-120}"


@pytest.mark.skipif(os.getenv("CADDY_IT") != "1", reason="set CADDY_IT=1 after: docker build -f caddy.Dockerfile -t irep-caddy:test .")
def test_real_caddy_answers_429_after_the_limit():
    name = f"irep-caddy-it-{os.getpid()}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-p", "127.0.0.1:18099:8080",
                    "-v", f"{PROD / 'Caddyfile'}:/etc/caddy/Caddyfile:ro",
                    "-e", "APP_DOMAIN=http://app.localhost:8080", "-e", "ID_DOMAIN=http://id.localhost:8080",
                    "-e", "ACME_EMAIL=ops@example.in", "-e", "KC_ADMIN_ALLOW_IPS=203.0.113.10/32",
                    "-e", "SIGNIN_RATE_PER_MIN=5", "irep-caddy:test"], check=True, capture_output=True)
    try:
        def post(host, path, method="POST"):
            req = urllib.request.Request(f"http://127.0.0.1:18099{path}", method=method, headers={"Host": host}, data=b"" if method == "POST" else None)
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    return r.status, r.headers
            except urllib.error.HTTPError as e:
                return e.code, e.headers
        for _ in range(30):
            try:
                post("app.localhost", "/health", "GET")
                break
            except OSError:
                time.sleep(0.5)
        for host, path in (("app.localhost", "/api/v1/auth/parent/otp/request"), ("id.localhost", "/realms/irep/login-actions/authenticate")):
            codes = [post(host, path)[0] for _ in range(7)]
            assert codes[:5] == [502] * 5 and codes[5:] == [429, 429], (host, codes)     # 502: no upstream in this test
            status, headers = post(host, path)
            assert status == 429 and int(headers["Retry-After"]) > 0
            assert post(host, path, "GET")[0] == 502                                    # reading is not limited
    finally:
        subprocess.run(["docker", "stop", name], capture_output=True)
