# Screens 10 · Attendance (parent) and 43 · Approvals (trainer)

**Sprint:** S5. **Status:** 10 is feature-only; 43 is new (gap fix). Screen 43 is built here for leave and Cyber Range access; certificate proofs join it in S11.
**Routes:** `/parent/attendance` (10), `/trainer/approvals` (43).
**Flow:** "Parent leave request" (steps 1–7). **Release rule:** a leave request changes attendance only after the trainer approves it.

## Links

| Link | Direction | What moves | Status |
| --- | --- | --- | --- |
| L09 | 10 ↔ 43 | Leave request up; decision down | active |
| L07 | 09 ↔ 10 | The attendance record down to the parent (Excused after approval); the leave request up | active |
| L08 | 29 ↔ 43 | Cyber Range access request; approve or deny | active (the existing 29 approval flow, now in the one queue) |
| L38, L39 | → 48, 44 | Every request and decision is audited; the parent is notified of the decision, trainers of the request | through the outbox |

## Data

`leave_requests` (new):

- `student_id` and `requested_by` (the parent).
- `start_date` and `end_date`, which are inclusive, and `reason`.
- `status`: `pending`, `approved` or `denied`.
- `decided_by` (the trainer), `decision_note` and `decided_at`.

## Rules

- **Parents:**
  - Only for their own child; any other child returns 404.
  - At most 30 days per request, starting no more than 7 days in the past (to cover a recent absence) and no more than 60 days ahead.
  - No overlap with another pending or approved request.
  - Consent: the parent-data consent from Screen 48 is required to see attendance; without it the response is a consent prompt, as on Screen 15.
- **Approval (trainers of the student's batch):**
  - Approving marks the student's sessions in the range **Excused** (source `leave`), both those already marked Absent and those not yet marked.
  - `Present` and `manual` rows are never changed.
  - Sessions that end later are finalized as Excused instead of Absent while approved leave covers them.
- **Denial** needs a note. Nothing about attendance changes before a decision.
- **Excused** counts neither as present nor as absent in the parent's summary.

## Endpoints

| Method | Path | Role |
| --- | --- | --- |
| GET | `/parent/attendance?child_id&month=YYYY-MM` | parent: sessions in the month with status (`Present`, `Absent`, `Excused` or upcoming), a summary and leave requests |
| POST | `/parent/leave-requests` | parent: `child_id` (optional), `start_date`, `end_date`, `reason` |
| GET | `/trainer/approvals?status=pending` | trainer: one queue of leave and Cyber Range requests for mapped batches |
| POST | `/trainer/approvals/leave/{id}` | trainer: `decision` (`approve` or `deny`), `note` (required for deny) |
| POST | `/trainer/approvals/labs/{id}` | existing (Screen 29) |

## Acceptance tests

- **API:**
  - L09: a parent requests leave, which reaches the trainer's queue and the trainer approves it.
  - L07: the parent's month shows Excused for the approved days, and the trainer's Screen 09 roster shows Excused.
  - Before approval nothing changes.
  - A denial needs a note and changes nothing.
  - Overlap, range and child checks.
  - A later class during the leave is finalized as Excused.
  - Cyber Range requests appear in the same queue.
  - Other roles and trainers are refused.
- **E2E:**
  - A parent requests leave and the trainer approves it on 43; the parent sees it approved.
  - Tamil toggle; role guard.
