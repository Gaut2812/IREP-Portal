"""IREP staff and super admins: the API accepts only Keycloak tokens from a two-factor sign-in
(amr contains "otp"). Verified against Keycloak 26.0.7 (docs/PERMISSIONS.md); here with signed test tokens."""
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from fastapi.testclient import TestClient

from core.security import PLATFORM_TENANT
from main import app
from tests.test_keycloak_auth import _h, _token, kc  # noqa: F401  (kc is a fixture)

client = TestClient(app)


def _staff(role="irep_admin", sub="usr_irep_staff_01", **over):
    return _token(irep_user_id=sub, college_id=PLATFORM_TENANT, realm_access={"roles": [role, "irep_2fa"]}, **over)


def test_staff_token_without_otp_is_refused_with_a_reason(kc):
    for amr in (None, ["pwd"], []):
        tok = _staff(amr=amr) if amr is not None else _staff()
        r = client.get("/api/v1/admin/colleges", headers=_h(tok))
        assert r.status_code == 401 and r.headers["X-IREP-Reason"] == "two_factor_required"
        assert "authenticator" in r.json()["detail"]


def test_staff_and_super_admin_with_otp_are_accepted(kc):
    assert client.get("/api/v1/admin/colleges", headers=_h(_staff(amr=["pwd", "otp"]))).status_code == 200
    sup = _staff(role="super_admin", sub="usr_irep_super_01", amr=["otp"])
    assert client.get("/api/v1/admin/staff", headers=_h(sup)).status_code == 200
    assert client.get("/api/v1/admin/staff", headers=_h(_staff(role="super_admin", sub="usr_irep_super_01", amr=["pwd"]))).status_code == 401


def test_other_roles_do_not_need_otp(kc):
    student = _token(amr=["pwd"])
    assert client.get("/api/v1/auth/me", headers=_h(student)).status_code == 200


def test_websocket_refuses_a_staff_token_without_otp(kc):
    from core.security import websocket_user
    assert websocket_user(_staff(amr=["pwd"])) is None
    assert websocket_user(_staff(amr=["otp"])).role == "irep_admin"


def test_the_reason_header_is_readable_cross_origin():
    r = client.get("/api/v1/auth/config", headers={"Origin": "http://localhost:3000"})
    assert "X-IREP-Reason" in r.headers.get("access-control-expose-headers", "")


def test_keycloak_setup_tags_password_and_otp_steps():
    from ops.configure_keycloak import AMR_MAX_AGE, AMR_REFS
    assert AMR_REFS == {"auth-username-password-form": "pwd", "auth-otp-form": "otp"} and AMR_MAX_AGE == "28800"
