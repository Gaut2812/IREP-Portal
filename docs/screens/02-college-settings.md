# Screen 02 · College settings

**Role:** college admin (`college_admin`). **Sprint:** S2. **Status:** feature-only (no mockup).
**Route:** `/college/settings`.
**Purpose:** the college's own users and roles, branding and chat policy, and data export and deletion requests. Surveys (link L26) arrive with Screen 40 in S14.

## Links (docs/INTERCONNECT.md)

| Link | Direction | What moves | Status after this screen |
| --- | --- | --- | --- |
| L27 | 02 ↔ 48 | Export and deletion requests up; status, export file and audit trail back | active (test: a request raised here is completed on 48 and downloaded here) |
| L26 | 40 ↔ 02 | Survey sent; responses returned | planned until 40 (S14) |
| L38 | 02 → 48 | Every user, branding and request change is audited | active |

## Endpoints (`/api/v1/college/…`, `college_admin` only; tenant from the token)

| Method | Path | Rule |
| --- | --- | --- |
| GET | `/college/settings` | College profile (name and code are set by IREP staff on 45, read-only here), logo, chat retention, college users (`college_admin`, `placement_officer`) |
| PUT | `/college/settings/branding` | `logo_url` (https, or a path under the portal) and `chat_retention_days` (30–3650) |
| POST | `/college/users` | Add a `college_admin` or `placement_officer`; email unique (409). Local sign-in: a one-time temporary password, shown once. Keycloak: invited through the outbox |
| POST | `/college/users/{id}/deactivate` | Not yourself, and not the last active college admin (409) |
| POST | `/college/users/{id}/reactivate` | |
| GET | `/college/students?search=` | Register number or name, up to 20 results (to pick the student for a data request) |
| POST/GET | `/college/data-requests`, `/college/data-requests/{id}/export` | From Screen 48 (L27) |

Deactivated accounts cannot sign in, by password or OTP. The check runs after the password, so an account cannot be probed. **Known gap:** tokens already issued stay valid until they expire (7 days, local mode); revocation needs a per-request account check, which is planned with session management.

## Audit events

`college.settings_changed`, `college.user_created`, `college.user_deactivated`, `college.user_reactivated`, plus the data-request events from Screen 48.

## UI states

- **Users:** a table with role and status chips, an add-user form, a one-time password panel, and deactivate/reactivate buttons (disabled on your own row).
- **Branding and policy:** a logo URL with preview, and chat retention in days.
- **Data requests:** a student search, the kind (export or deletion) with a reason, then a list showing status, due date, download (when ready) and the staff decision note.
- Tamil toggle; role guard.

## Acceptance tests

- **API:**
  - A user is added and can sign in.
  - A duplicate email returns 409.
  - You can't deactivate yourself or the last admin.
  - A deactivated user can't sign in.
  - Branding is validated.
  - Student search is tenant-scoped.
  - L27 round trip: a request is raised here, completed on 48 and downloaded here.
  - Other roles get 403.
- **E2E:**
  - Add a placement officer, who then signs in.
  - Raise an export request, which staff complete on 48, and download it here.
  - Tamil toggle; role guard.
