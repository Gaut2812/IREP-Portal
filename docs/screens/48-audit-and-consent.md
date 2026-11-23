# Screen 48 · Audit and consent

**Role:** IREP staff (`irep_admin`). The college admin uses the request side from Screen 02 (link L27). **Sprint:** S2. **Status:** new screen (gap fix).
**Routes:** `/admin/audit` (trail), `/admin/audit/consent` (consent records), `/admin/audit/requests` (export and deletion requests).
**Purpose:** the audit trail, parent and student consent records, and data export and deletion requests. "Consent must be recorded before any parent data is stored" (build order, S2).

## Links (docs/INTERCONNECT.md)

| Link | Direction | What moves | Status after this screen |
| --- | --- | --- | --- |
| L38 | every sensitive action → 48 | Audit trail; consent records for 15 (parent overview) and 32 (public portfolio) | active (writer exists; this adds the reader) |
| L27 | 02 ↔ 48 | Export and deletion requests; audit trail back | planned until 02 is built (S2), then active |
| L39 | 48 → 44 | The requester is notified when a request completes | through the outbox |

## Data

- `audit_log` (exists, append-only). This screen only reads it: there are no edit or delete endpoints, ever.
- `consent_records` (new): one row per decision. A withdrawal is a new row, never an update.
  - `subject_user_id`: the student the consent is about.
  - `granted_by_user_id`: the parent, or the student if 18+.
  - `purpose`: one of `parent_data_processing`, `public_portfolio`, `ai_hints`, `recordings`, `sms_alerts`.
  - `status`: `granted` or `withdrawn`.
  - `method`: `otp_parent`, `paper_form_upload` or `in_app`.
  - Also: `evidence_ref`, `recorded_at`.
  - The current state is the latest row per (subject, purpose).
- `data_requests` (new):
  - `kind`: `export` or `deletion`.
  - Also: `subject_user_id`, `requested_by` (college admin), `reason`.
  - `status`: `received` → `in_progress` → `completed` or `rejected`.
  - `result_ref`: an export file key in object storage, or a deletion summary.
  - `due_on`: 30 days, the DPDP handling target. Confirm with legal.

## Endpoints (`/api/v1/admin/audit…`, `irep_admin`; college admins only where stated)

| Method | Path | Rule |
| --- | --- | --- |
| GET | `/admin/audit` | Filters: college, actor, action prefix, entity, date range. Paged, newest first. Read-only |
| GET | `/admin/audit/export.csv` | Same filters, as CSV. The export itself is audited (`audit.exported`) |
| GET | `/admin/consent` | Current consent per student and purpose; filters by college or batch; history per subject |
| POST | `/consent` | Parent (own child) or student 18+: grant or withdraw a purpose. Recorded, audited, outbox |
| POST | `/college/data-requests` | **College admin** (Screen 02 side): request an export or deletion for a student in their college |
| GET | `/admin/data-requests` | Staff queue with due dates; overdue first |
| POST | `/admin/data-requests/{id}/complete` | Staff: export → the outbox builds the file; deletion → anonymise (see rules); notify the requester |
| POST | `/admin/data-requests/{id}/reject` | A reason is required; the requester is notified |

## Rules

- Without a `granted` `parent_data_processing` consent, parent-facing data for that student (screens 15, 16, 18) is not shown. The default for existing demo data is seeded as granted.
- A public portfolio (32 → 33, link L15) requires `public_portfolio` consent.
- Deletion anonymises personal fields (name, email, phone, register number) and keeps aggregate rows and the audit trail, which records the anonymisation. Hard deletes are never used.
- Admins see the audit trail through a logged support view only (§5.4). Opening a college's records writes `support.access`.
- CERT-In: audit rows are kept 180 days minimum. There's no purge job before that.

## Audit and notification events (§5.3)

| Event | Audit | Notify |
| --- | --- | --- |
| `consent.recorded` | yes | no |
| `data_request.created` | yes | yes (IREP staff) |
| `data_request.completed` | yes | yes (requester) |
| `data_request.rejected` | yes | yes (requester) |
| `audit.exported` | yes | no |
| `support.access` | yes | no |

## UI states

- **Trail:** a table with filters, an expandable detail JSON, and a CSV button.
- **Consent:** per-student purpose chips (granted, withdrawn, missing) and a history drawer.
- **Requests:** a queue showing due-in-days or overdue in red, with complete and reject actions; reject requires a reason.
- Tamil toggle; role guard.

## Acceptance tests

- **API:**
  - The trail is filtered and paged.
  - No write endpoint exists for `audit_log`.
  - The CSV export is audited.
  - Withdrawal is a new row, and the current state flips.
  - A parent can record consent only for their own child (404 otherwise).
  - A college admin can request only for their own college's students (404 otherwise).
  - Deletion anonymises and keeps the aggregates.
  - The requester is notified through the outbox.
  - Without consent, the parent overview hides the child's data.
- **E2E:**
  - A college admin raises an export request; staff complete it; the requester sees the notification.
  - Staff filter the trail.
  - Tamil toggle and role guard.

## Open points to confirm

- The DPDP handling deadline (30 days assumed) and the verifiable parental consent method (Rule 10, from about 13 May 2027). The Master Plan puts DOB capture and the identity-bound flow in S16.
- Whether college admins see their own college's audit trail (the plan says "Export requests" only).
