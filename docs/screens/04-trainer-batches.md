# Screen 04 · Trainer batches

**Role:** trainer. **Sprint:** S3. **Status:** feature-only (no mockup).
**Routes:** `/trainer/batches` (my batches and roster), `/trainer/students/{id}` (student profile and notes).
**Purpose:** the roster of the batches a trainer is mapped to, student profiles, and private trainer notes. Roster changes go to the college as requests.

## Links (docs/INTERCONNECT.md)

| Link | Direction | What moves | Status after this screen |
| --- | --- | --- | --- |
| L24 | 03 ↔ 04 | Down: batches and student lists from the college structure (mapping on 03). Up: roster change requests, which the college approves on 03 | active (test: mapped on 03 → visible on 04; requested on 04 → approved on 03 → roster updated) |
| L02 | 12 ↔ 13 | Unchanged | |
| L38 | 04 → 48 | Notes and roster requests are audited (note text is never copied into the audit log) | active |

## Rules

- A trainer sees only batches they are mapped to (primary or substitute). Any other batch or student returns 404.
- **Private notes** (§5.4): visible to the trainers mapped to that student's batch, never to the student, parent, college or admin. Only the author can delete a note. Notes are not included in college aggregates (L35).
- **Roster change requests:**
  - `move` to another batch (same college and semester) or `remove` from the batch, with a reason.
  - The college admin approves or rejects them on Screen 03.
  - Approving applies the change; rejecting needs a reason.
  - The trainer is notified either way.
  - At most one open request per student.

## Endpoints

| Method | Path | Role |
| --- | --- | --- |
| GET | `/trainer/batches` | trainer: mapped batches with student count, average readiness and attendance |
| GET | `/trainer/batches/{id}/roster` | trainer: students with readiness, band, attendance and open flags |
| GET | `/trainer/students/{id}` | trainer: profile, parents (names only), notes, open roster request |
| POST | `/trainer/students/{id}/notes` | trainer: 1–2000 characters |
| DELETE | `/trainer/notes/{note_id}` | trainer: author only |
| POST | `/trainer/roster-requests` | trainer: `student_id`, `kind`, `to_batch_id` (for a move), `reason` |
| GET | `/college/roster-requests` | college admin: open requests first |
| POST | `/college/roster-requests/{id}/approve` and `/reject` | college admin |

## Acceptance tests

- **API:**
  - The roster shows only mapped batches.
  - Another trainer's batch or student returns 404.
  - Notes are hidden from the student, parent and college, and only the author can delete.
  - L24 round trip:
    - Map a trainer on 03, and the batch appears on 04.
    - A move requested on 04 and approved on 03 updates the student's batch.
    - A rejected request needs a reason.
  - A move to another semester's batch returns 422.
- **E2E:**
  - The trainer opens a batch, opens a student, adds a note and requests a move.
  - The college approves it on 03.
  - Tamil toggle; role guard.
