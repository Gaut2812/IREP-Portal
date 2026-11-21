# Screen 03 · Branches and batches

**Role:** college admin (`college_admin`, web role `college`). **Sprint:** S2. **Status:** feature-only (no mockup).
**Route:** `/college/structure`.
**Purpose:** set up the college structure (branches, batches by semester), import students, map trainers to batches, and promote batches to the next semester. Step 3 of "New college onboarding".

## Links (docs/INTERCONNECT.md)

| Link | Direction | What moves | Status after this screen |
| --- | --- | --- | --- |
| L25 | 45 → 03 | New college, first admin, structure import | active (test: a college created on 45 is set up here by its first admin) |
| L24 | 04 ↔ 03 | Structure and student lists down; roster changes up | planned until 04 (S3) |
| L38 | 03 → 48 | Every structure change, import and promotion is audited | active |

## Endpoints (`/api/v1/college/…`, `college_admin` only; tenant from the token)

| Method | Path | Rule |
| --- | --- | --- |
| GET | `/college/structure` | Branches → batches with student count and mapped trainers |
| POST | `/college/branches` | `name`, `code` (unique in the college), `track`, optional `hod_name` |
| POST | `/college/batches` | `branch_id` (own college), `short_name` (unique per branch, semester and year), `semester` 2–7, `academic_year`, `track` |
| GET | `/college/trainers` | Trainers of the college (for mapping) |
| POST | `/college/batches/{id}/trainers` | Map a trainer (`primary` or `substitute`); at most one primary per batch |
| DELETE | `/college/batches/{id}/trainers/{trainer_id}` | Unmap |
| POST | `/college/students/import?dry_run=true\|false` | CSV upload (see below). Dry run reports row errors and counts without writing |
| POST | `/college/batches/{id}/promote` | Semester + 1 for the batch and its students (up to 7). Audited |

### Student CSV

Header: `register_no,name,email,phone,branch_code,batch,semester,parent_name,parent_phone`. The parent columns are optional.

- `branch_code` and `batch` (the short name) must exist in the college, and `semester` must match the batch.
- `register_no` is the key: re-importing updates name, phone and batch instead of creating duplicates.
- Duplicate register numbers or emails inside the file are row errors.
- An email that belongs to another account is a row error.
- A parent phone creates or links a parent account (role `parent`) and a parent-student link. The parent then sees the consent card from Screen 48 before any data.
- Students get no usable portal password from the import. With Keycloak, each new student is invited through the outbox. With local sign-in, a support step sets the password; this is a known limitation.
- The limit is 5,000 rows per file.

## Audit and notification events

`structure.branch_created`, `structure.batch_created`, `structure.trainer_mapped`, `structure.trainer_unmapped`, `students.imported` (counts only, no personal data in the detail), `batch.promoted`.

## UI states

- **Empty college:** a "Start by adding a branch" prompt, which is where a college created on Screen 45 lands.
- **Tree:** branches → batches (semester, year, students, trainers), with add-branch, add-batch and map-trainer forms.
- **Import panel:**
  - Choose a file, then a dry run shows counts (new, updated, parents linked) and the first 50 row errors.
  - "Import" stays disabled while there are errors; after import, the counts.
- **Promote:** asks for confirmation, then updates the semester.
- Tamil toggle; role guard (trainers and staff blocked).

## Acceptance tests

- **API:**
  - Create a branch and batch; duplicate codes return 409.
  - Another college's branch returns 404.
  - Trainer mapping allows only one primary.
  - The dry run writes nothing.
  - The import creates students, users and parents, and a re-import updates instead of duplicating.
  - Row errors are reported with row numbers.
  - Promote moves the batch and students and is capped at 7.
  - Non-college roles get 403.
  - L25 end to end: a college created on 45 is set up by its first admin.
- **E2E:**
  - The first admin of a new college adds a branch and batch, imports a CSV (dry run, then import) and maps a trainer.
  - Tamil toggle; role guard.
