# Screen 09 · Attendance (trainer)

**Role:** trainer (students use the check-in page). **Sprint:** S4. **Status:** feature-only (no mockup).
**Routes:** `/trainer/attendance` (sessions → roster), `/student/checkin` (enter the class code).
**Purpose:** review automatic attendance (75% rule), override with a reason, and check-in for in-lab or hybrid classes.

## Links

| Link | Direction | What moves | Status |
| --- | --- | --- | --- |
| L06 | 07 → 09 | Join and leave events → Present at 75% of the session, when the meeting ends | active (test: class ended on 07 → roster on 09) |
| L07 | 09 ↔ 10 | Attendance down to parents; leave requests up | planned until 10 (S5) |
| L34 | 09 → readiness | Attendance is a readiness input | core. **Gap:** readiness reads the stored `students.attendance_pct`; a nightly recompute from attendance rows (including overrides) is still to be built |

## Rules

- Sources: `auto` (75% rule), `teams` (Teams report), `qr` (check-in code), `manual` (trainer override). A manual row always wins, including over later automatic recomputes.
- Overrides need a reason of at least 5 characters, and record the overriding trainer. They're audited.
- **Check-in code:**
  - Six characters, derived by HMAC from the session and the current minute. It rotates every minute; the previous minute's code is still accepted.
  - Valid from 15 minutes before the start until the end.
  - A student can only check in to a session of their own batch. Checking in again is harmless.
  - Check-in never overrides a manual Absent.
- A trainer only sees sessions of mapped batches (or ones where they substitute); anything else returns 404.

## Endpoints

| Method | Path | Role |
| --- | --- | --- |
| GET | `/trainer/attendance/sessions?days=14` | trainer: recent sessions with present, absent and unmarked counts |
| GET | `/trainer/attendance/{session_id}` | trainer: roster with status, minutes, source and override reason |
| POST | `/trainer/attendance/{session_id}/override` | trainer: `student_id`, `status` (`Present` or `Absent`), `reason` |
| GET | `/trainer/attendance/{session_id}/checkin-code` | trainer, only during the window |
| POST | `/student/attendance/checkin` | student: `code` |

## Acceptance tests

- **API:**
  - L06: a class ended on 07 shows Present and Absent by the 75% rule on 09.
  - An override needs a reason, is audited, and survives re-finalising.
  - Check-in works only in the window and only for one's own batch; a wrong code is refused.
  - Check-in doesn't override a manual Absent.
  - Other trainers and roles are refused.
- **E2E:**
  - The trainer opens a past session and overrides one student.
  - The trainer shows the code, and a student checks in with it.
  - Tamil toggle; role guard.
