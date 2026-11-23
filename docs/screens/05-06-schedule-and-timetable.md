# Screens 05 · Schedule (trainer) and 06 · Timetable (college)

**Sprint:** S4. **Status:** feature-only (no mockups).
**Routes:** `/trainer/schedule` (05), `/college/timetable` (06).
**Purpose:**
- On 05, trainers see their week and propose changes: a new session, a reschedule, a cancellation or a substitute.
- On 06, the college sees the whole timetable, approves or rejects proposals with clash warnings, and books rooms.

This is the "Schedule change" flow.

## Links (docs/INTERCONNECT.md)

| Link | Direction | What moves | Status after these screens |
| --- | --- | --- | --- |
| L11 | 05 ↔ 06 | Proposed sessions up; approval or clash warning back | active |
| — | 06 → 08 | An approved change shows in the students' live-sessions week (flow step 4, inferred) | covered by the same test |
| L39 | → 44 | The trainer and the batch's students are notified of approved changes | through notify_user |

## Data

- `sessions` gains:
  - `room`: a free-text room or lab name; room bookings are sessions with a room.
  - `substitute_trainer_id`
  - `status = "Cancelled"` for cancelled sessions.
- `schedule_change_requests` (new):
  - `kind`: `new`, `reschedule`, `cancel` or `substitute`.
  - `batch_id` and, except for `new`, `session_id`.
  - The proposed title, start, end, room and substitute.
  - `reason` and `requested_by_trainer_id`.
  - `status`: `pending`, `approved` or `rejected`.
  - `clashes`: computed when proposed and again on approval.
  - `decision_note`.

## Clash rules (`services/scheduling.find_clashes`)

A proposed time overlaps an existing, non-cancelled session:

- **batch** — the same batch.
- **trainer** — a batch the trainer or substitute is mapped to, or where they already substitute.
- **room** — the same room (case-insensitive).

The session being moved doesn't count against itself. Clashes are a **warning**: the college may approve with `override=true`, which is audited along with the clash list.

## Endpoints

| Method | Path | Role / rule |
| --- | --- | --- |
| GET | `/trainer/schedule?week=YYYY-MM-DD` | trainer: sessions of mapped batches (and substitutions) for the Monday-based week, plus their requests |
| POST | `/trainer/schedule/requests` | trainer, own batches only. Validation: end after start, 15–240 minutes, not in the past. Returns the clashes |
| GET | `/college/timetable?week=YYYY-MM-DD` | college admin: every session in the week, pending requests with live clashes, known rooms |
| POST | `/college/schedule-requests/{id}/approve` | college admin. With current clashes, returns 409 and the list unless `override=true`. Applies the change and notifies |
| POST | `/college/schedule-requests/{id}/reject` | college admin; a reason is required; the trainer is notified |

With Teams, an approved reschedule or cancellation of a session that already has a Teams meeting emits `teams.update_event` or `teams.cancel_event`. Graph is only ever called from the outbox.

## Acceptance tests

- **API:**
  - The trainer's week shows only mapped batches.
  - Proposals are validated.
  - Each clash kind is detected.
  - Approving a new session creates it, and it appears in the student's live week (08).
  - Approving a reschedule moves the session.
  - With clashes, approval returns 409 unless overridden, and the override is audited.
  - Rejecting requires a reason.
  - Another college's request returns 404.
  - With Teams, a reschedule emits an outbox event.
- **E2E:**
  - A trainer proposes a session, which the college approves on 06.
  - Tamil toggle; role guard.
