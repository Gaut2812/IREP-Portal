# Permission matrix

This is the source of truth for who may do what. The API enforces it, and the web app only hides what the API would refuse anyway.

Legend:
- ✅ allowed
- 👁 read only
- ❌ refused (`403`)
- "own" means the caller's own rows only
- a row from another college, or a child not linked to the caller, is `404`, not `403` (architecture rule 1)

## Roles

| Role (API) | Web sign-in card | Tenant | Sign-in |
|---|---|---|---|
| `student` | Student | own college | Keycloak (pilot) |
| `parent` | Parent | own college | mobile number + one-time code (email by default, SMS when switched on) |
| `trainer` | Trainer | own college | Keycloak |
| `college_admin`, `placement_officer` | College | own college | Keycloak |
| `irep_admin` (IREP staff) | IREP staff | `irep_platform` | Keycloak **with two-factor (authenticator app), enforced at every sign-in** |
| `super_admin` | IREP staff | `irep_platform` | Keycloak **with two-factor, enforced at every sign-in** |

`super_admin` sits above IREP staff: it passes every `irep_admin` check (`core/security.require_role`), and only it passes `SUPER`.

## Creating accounts: invite or import only

There is no public sign-up for any role:
- the API has no sign-up route
- the Keycloak realm has `registrationAllowed=false`, and `ops/configure_keycloak.py` keeps it false
- the web client cannot use the password grant (`directAccessGrantsEnabled=false`), so the OTP step cannot be skipped

| New account | Created by | How |
|---|---|---|
| First super admin | the operator, on the server | `ops/bootstrap_admin.py` (Keycloak invite email; the first sign-in sets up the authenticator) |
| IREP staff, other super admins | super admin | Super admin page → invite (`POST /admin/staff`) |
| College admin | IREP staff or super admin | Screen 45 → college admins (`POST /admin/colleges/{id}/admins`) |
| Trainer | college admin | college screens (invite) |
| Student | college admin | student import (CSV, dry run first) |
| Parent | college admin, through the student import | from the `parent_phone` / `parent_email` columns. See below. |

**Student import and parents** (`POST /college/students/import`):
- One mobile number is one parent account within the college. That account is linked to each of their children, so one parent can have several children.
- A parent row needs `parent_phone`; `parent_email` is optional but needed for the email sign-in code.
- A row with any parent detail is refused unless it carries `parent_consent=yes` and `parent_consent_ref` (the signed form's number or file name).
- The `parent_data_processing` consent is recorded (`paper_form_upload`, with that reference) in the same transaction as the parent data. No parent data is saved without it.
- Parents are matched inside the importing college only.
- A `parent_email` that belongs to another account is refused.

## What each role can do

| Area | Student | Parent | Trainer | College admin | IREP staff | **Super admin** |
|---|---|---|---|---|---|---|
| Own dashboard, courses, labs, tests | ✅ own | 👁 linked child, after consent | ✅ own batches | 👁 aggregates | ❌ | ❌ |
| Trainer notes, chats | ❌ | ❌ | ✅ own | ❌ (rule 8) | ❌ | ❌ |
| Earned certificates by student (name, register no, title, issuer, date; no proof files), each read audited (D1) | ✅ own | 👁 linked child | 👁 own batches | 👁 own college | ❌ | ❌ |
| College structure, student import, trainers | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Invitations: list, resend, revoke (Phase 5) | ❌ | ❌ | ❌ | ✅ own college | ✅ any college (45) | ✅ |
| Colleges: list, create, detail (45) | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| College admins: create / invite (45) | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **MoU terms (incl. fees, quotas): create, activate** | ❌ | ❌ | ❌ | ❌ | 👁 | ✅ |
| **Feature switches per college** | ❌ | ❌ | ❌ | ❌ | 👁 | ✅ |
| Usage and quotas (47) | ❌ | ❌ | ❌ | 👁 own college | 👁 | 👁 |
| **Billing: generate, issue, settle, void invoices; add credits** (S16) | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Billing: own college's issued invoices, PDFs, credit balance | ❌ | ❌ | ❌ | 👁 own college | ❌ | 👁 all |
| Content library, templates (44) | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Question bank (staff side) | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Audit trail (48); student and parent names only inside a support session | ❌ | ❌ | ❌ | ❌ | 👁 | 👁 |
| **Student or parent records**: consent list and history (48), a data-export file | ❌ | ❌ | ❌ | ❌ | 👁 **only inside an active support session** | 👁 **only inside an active support session** |
| Data requests: raise | ✅ for themselves, 18+ only (S16) | ✅ for a linked child (S16) | ❌ | ✅ own college | ❌ | ❌ |
| **Optional consents for a minor** (AI Study Buddy, public portfolio, recordings, SMS): grant (S16) | asks only | ✅ linked child, OTP sign-in within 15 min | ❌ | ❌ (paper form via import) | ❌ | ❌ |
| Optional consents for an adult student (S16) | ✅ own | ❌ (the student decides) | ❌ | ❌ | ❌ | ❌ |
| Record a student's date of birth (S16) | ❌ | ❌ | ❌ | ✅ own college | ❌ | ❌ |
| Data **export** requests: build or reject (names hidden without a session) | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Data deletion requests: approve or reject** | ❌ | ❌ | ❌ | ❌ | ❌ (👁 in the queue) | ✅ |
| Support desk tickets (49) | ✅ own | ✅ own | ✅ own | ✅ own | ✅ all | ✅ all |
| **Logged support sessions: open, end, list** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **IREP staff accounts: invite, change role, deactivate, reactivate** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Background jobs (`/admin/jobs/*`) | ❌ | ❌ | some (trainer) | ✅ own college | ✅ | ✅ |

The rows in **bold** are super-admin only. The guards:
- `SUPER` in `routers/super_admin.py` and `routers/admin_colleges.py`
- `_may_decide` in `routers/audit_consent.py`

The staff-account endpoints also refuse to let a super admin deactivate themselves or demote or deactivate the last active super admin.

## Support sessions: how staff see student data

IREP staff, and the super admin too, read student or parent records only inside an active support session (`services/support_access.py`):
- The super admin opens a session for one staff member, one college, a reason, and 15–240 minutes.
- While it is open, that person may read that college's records. Every read is audited as `support.read`, with the session id. A refused attempt is audited as `support.read_denied`.
- Without a session the answer is `403`. Ending the session, or reaching its time limit, closes access at once.
- In staff-wide lists, student and parent names are hidden for colleges without a session. This covers the data-request queue and the actor names in the audit trail. Ids and the workflow stay usable.
- Support desk tickets (49) are readable without a session, because the student or parent sent them to IREP.

## Audit

- **Every request a super admin makes, reads included**, is written to the audit log as `super_admin.request`, with method, path and status code (`main.py`, `audit_every_super_admin_request`). The token is verified first: a forged `super_admin` claim gets `401` and no row.
- Specific events are written as well:
  - `staff.invited`, `staff.role_changed`, `staff.deactivated`, `staff.reactivated`
  - `support_session.opened`, `support_session.ended` (in the college's own trail)
  - `mou.created`, `mou.activated`, `college.features_changed`
  - `data_request.completed`, `data_request.rejected`
- Each audit row also emits an `audit.<action>` outbox event (architecture rule 4).

## Two-factor sign-in (Keycloak)

`ops/configure_keycloak.py` (idempotent) sets this up:
1. The realm roles `irep_admin` and `super_admin` include the marker role `irep_2fa`.
2. It binds the **`irep browser`** flow as the realm's browser flow.
3. In that flow, a user with `irep_2fa` must enter an authenticator code at **every** sign-in.
4. A staff user without an authenticator is made to set one up before getting in.
5. The stock "OTP if configured" step skips staff, so they are never asked twice.
6. Other roles are unchanged.
7. Invites for staff roles also carry the `CONFIGURE_TOTP` required action (`services/keycloak_admin.invite`).

This was verified against Keycloak 26.0.7 in a browser:
- a student signs in without OTP
- a staff user is forced to set up an authenticator
- every later staff sign-in needs a code, and a wrong code is refused

**The API checks it too.** `ops/configure_keycloak.py` adds an AMR mapper and tags the password step `pwd` and the OTP steps `otp`. Each reference is valid for 8 hours, the SSO idle time.
- `core/keycloak.py` refuses an `irep_admin` or `super_admin` token whose `amr` lacks `otp`. It answers `401` with `X-IREP-Reason: two_factor_required`; this applies to requests and WebSockets.
- On that answer, the web app sends the user back through Keycloak with `prompt=login` and shows "sign in again with your authenticator code". This happens once, after the very first sign-in, when the authenticator was only being set up (that token has `amr=["pwd"]`).
- Verified against Keycloak 26.0.7:
  - first sign-in: refused
  - a later sign-in with a code: accepted
  - a refreshed token: accepted

`AUTH_PROVIDER=local` (development only) has no second factor. Production refuses local auth (`core/production.py`).
