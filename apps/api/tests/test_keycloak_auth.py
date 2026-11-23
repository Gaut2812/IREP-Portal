"""AUTH_PROVIDER=keycloak: RS256 tokens verified against the realm key set.

No Keycloak server here: tokens are signed with a local RSA key and the
verifier is given that key set. infra/keycloak covers the live server.
"""
import sys
import time
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwk, jwt

from core import keycloak
from core.config import settings
from core.security import create_access_token
from main import app

client = TestClient(app)
ISSUER = "http://kc.test/realms/irep"


def _keypair(kid):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    public_jwk = jwk.construct(pub, "RS256").to_dict()
    public_jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    public_jwk = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in public_jwk.items()}
    return pem, public_jwk


PEM_A, JWK_A = _keypair("key-a")
PEM_B, JWK_B = _keypair("key-b")


def _token(pem=PEM_A, kid="key-a", **over):
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": ["irep-api", "account"], "sub": "kc-uuid-1", "exp": now + 300, "iat": now,
              "irep_user_id": "usr_priya_01", "college_id": "col_demo_001", "email": "priya.r@demo.edu",
              "name": "Priya R", "realm_access": {"roles": ["student", "offline_access", "default-roles-irep"]}}
    claims.update(over)
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


@pytest.fixture
def kc(monkeypatch):
    jwks = {"keys": [JWK_A]}
    fetches = []

    def fetch(url):
        fetches.append(url)
        return {"keys": list(jwks["keys"])}   # a fresh copy, like a real HTTP fetch

    monkeypatch.setattr(settings, "AUTH_PROVIDER", "keycloak")
    keycloak.set_verifier(keycloak.KeycloakVerifier(ISSUER, "irep-api", fetch=fetch))
    yield {"jwks": jwks, "fetches": fetches}
    keycloak.set_verifier(None)


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_valid_keycloak_token_maps_to_the_portal_user(kc):
    me = client.get("/api/v1/auth/me", headers=_h(_token())).json()
    assert (me["sub"], me["id"], me["role"], me["college_id"]) == ("usr_priya_01", "usr_priya_01", "student", "col_demo_001")
    assert me["avatar"] == "PR" and me["language_pref"] in ("en", "ta")
    assert client.get("/api/v1/student/dashboard", headers=_h(_token())).json()["student"]["id"] == "std_priya_01"


@pytest.mark.parametrize("bad", [
    {"iss": "http://evil.test/realms/irep"},
    {"aud": "some-other-api"},
    {"exp": int(time.time()) - 10},
])
def test_wrong_issuer_audience_or_expiry_is_401(kc, bad):
    assert client.get("/api/v1/auth/me", headers=_h(_token(**bad))).status_code == 401


def test_token_signed_by_an_unknown_key_is_401(kc):
    assert client.get("/api/v1/auth/me", headers=_h(_token(pem=PEM_B, kid="key-a"))).status_code == 401


def test_key_rotation_refetches_the_key_set_once(kc):
    client.get("/api/v1/auth/me", headers=_h(_token()))
    kc["jwks"]["keys"] = [JWK_A, JWK_B]                      # Keycloak rotated
    n = len(kc["fetches"])
    assert client.get("/api/v1/auth/me", headers=_h(_token(pem=PEM_B, kid="key-b"))).status_code == 200
    assert len(kc["fetches"]) == n + 1


def test_role_and_tenant_come_from_keycloak_claims(kc):
    trainer = _token(irep_user_id="usr_arun_01", realm_access={"roles": ["trainer"]})
    assert client.get("/api/v1/trainer/dashboard", headers=_h(trainer)).status_code == 200
    assert client.get("/api/v1/college/overview", headers=_h(trainer)).status_code == 403
    two_roles = _token(realm_access={"roles": ["student", "trainer"]})
    assert client.get("/api/v1/auth/me", headers=_h(two_roles)).status_code == 403
    unlinked = _token(irep_user_id=None)
    assert client.get("/api/v1/auth/me", headers=_h(unlinked)).status_code == 403
    other_college = _token(college_id="col_other_999")
    assert client.get("/api/v1/student/dashboard", headers=_h(other_college)).status_code == 404


def test_local_tokens_only_for_parents_and_password_login_is_closed(kc):
    student_local = create_access_token({"sub": "usr_priya_01", "role": "student", "college_id": "col_demo_001"})
    parent_local = create_access_token({"sub": "usr_ramesh_01", "role": "parent", "college_id": "col_demo_001"})
    assert client.get("/api/v1/auth/me", headers=_h(student_local)).status_code == 401
    assert client.get("/api/v1/parent/overview", headers=_h(parent_local)).status_code == 200
    r = client.post("/api/v1/auth/login", json={"role": "student", "identifier": "priya.r@demo.edu", "password": "password123"})
    assert r.status_code == 410
    cfg = client.get("/api/v1/auth/config").json()
    assert cfg == {"provider": "keycloak", "issuer": settings.KEYCLOAK_ISSUER, "client_id": "irep-web", "parent_sign_in": "otp"}


def test_local_mode_is_unchanged():
    assert settings.AUTH_PROVIDER == "local"
    assert client.get("/api/v1/auth/config").json() == {"provider": "local"}
    r = client.post("/api/v1/auth/login", json={"role": "student", "identifier": "priya.r@demo.edu", "password": "password123"})
    assert r.status_code == 200
