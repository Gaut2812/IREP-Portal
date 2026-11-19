# Screen 45 · Colleges and MoU terms

**Role:** IREP staff (`irep_admin`; web role `admin`). **Sprint:** S2. **Status:** new screen (gap fix).
**Routes:** `/admin/colleges` (list + create), `/admin/colleges/{id}` (detail).
**Purpose:** create colleges, their first college admin, MoU terms and feature switches. This is the start of the "New college onboarding" flow.

## Links (docs/INTERCONNECT.md)

| Link | Direction | What moves | Status after this screen |
| --- | --- | --- | --- |
| L01 | 01 → 45 | Sign-in sends IREP staff to `/admin/colleges` | active (covered with the other homes) |
| L25 | 45 → 03 | New college, first admin, structure import | planned until 03 is built (S2) |
| L38 | 45 → 48 | Every create, change and activation is audited | active |
| L39 | 45 → 44 | First admin is notified (invite) | through the outbox |

## Data

- `colleges`: adds `city`, `state`, `status` (`onboarding` → `active` → `suspended`) and `features` (JSON of known switches).
- `mou_terms` (new): one row per version.
  - Fields: `starts_on`, `ends_on`, `students_cap`, `lab_hours_per_student`, `ai_calls_per_day`, `storage_gb`, `fee_per_student_inr`, `status` (`draft`, `active`, `superseded`), `notes`.
  - At most one `active` row per college; activating one supersedes the previous.
- Feature switches (default in brackets):
  - `virtual_labs` (on)
  - `cyber_range` (off)
  - `ai_study_buddy` (off)
  - `parent_sms` (off)
  - `whatsapp` (off)
  - `teams_live_classes` (on)

## Endpoints (`/api/v1/admin/colleges`, `irep_admin` only; everyone else 403)

| Method | Path | Rule |
| --- | --- | --- |
| GET | `/admin/colleges` | All colleges with student count, active MoU, admin count, status |
| POST | `/admin/colleges` | `name`, `code` (unique, 2–16 letters/digits), `city`, `state` → 201; duplicate code 409 |
| GET | `/admin/colleges/{id}` | College, MoU versions (newest first), features, college admins |
| PUT | `/admin/colleges/{id}/features` | Only known keys (unknown → 422) |
| POST | `/admin/colleges/{id}/mou` | `ends_on` after `starts_on`, positive caps; `activate=true` supersedes the active one |
| POST | `/admin/colleges/{id}/admins` | Creates a `college_admin` in that college; email unique (409). Local sign-in: a one-time temporary password is returned once. Keycloak: provisioned through the outbox with "update password" and "verify email" required actions |

A college becomes `active` once it has an active MoU and at least one college admin.

## Audit and notification events (§5.3)

`college.created`, `college.features_changed`, `mou.created`, `mou.activated`, `college.admin_created` (audit, plus the outbox event `audit.<action>`). Keycloak mode also emits `identity.invite_user`.

## UI states

- **List:** empty state, then a table: name, code, city, status chip, students, MoU end date.
- **Create form:** inline field errors, and the server's error on a duplicate code.
- **Detail:**
  - MoU versions with an "Active" chip.
  - The new-MoU form.
  - Feature toggles that save immediately.
  - The college-admins list, with an invite form that shows the temporary password once, with a copy button.
- Tamil toggle; a role guard for everyone except IREP staff.

## Acceptance tests

- **API** (`tests/test_screen_45_colleges.py`):
  - Create and list a college.
  - Duplicate code returns 409.
  - Validation errors return 422.
  - A non-staff role gets 403.
  - Activating a MoU supersedes the previous one.
  - Unknown feature keys return 422.
  - A first admin can sign in, sees only their college (tenant isolation), and the college becomes active.
  - Audit rows are written for every action.
- **E2E** (`e2e/screen45-colleges.spec.ts`):
  - Staff create a college, add and activate a MoU, toggle a feature, and invite an admin.
  - Tamil toggle.
  - A college admin sees the role guard.
