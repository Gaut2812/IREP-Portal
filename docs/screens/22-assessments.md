# Screen 22 · Assessments (trainer)

**Sprint:** S9. **Status:** feature-only.
**Routes:** `/trainer/assessments` (22), `/student/tests` (the 23 list). The IREP bank is a tab on `/admin/content` (46).

## Links

| Link | Direction | What moves | Status |
| --- | --- | --- | --- |
| L13 | 22 ↔ 24, 23 | Problems, tests and trainer notes down; results back | active |
| L37 | 46 → 22, 24, 44 | Question and problem bank (problems reach 24 through 22), notification templates (S6) | active |

## Publishing (L13)

- Coding problems and practice tests have `status` (`draft`, `published`), `batch_ids` (`null` means every batch in the college), `due_at` and `published_at`. Rows created before S9 are published to every batch, so 23 and 24 behave as before.
- Trainers create drafts (a problem needs at least one visible sample case; a test needs four options and a correct answer per question) and publish them to **their own batches** with an optional due date. Students in newly reached batches get an in-app notice linking to 24 or 23. Audited: `assessment.created`, `assessment.published`, `assessment.unpublished`.
- Unpublishing removes only the trainer's batches; other batches keep the item. When no batch is left, the item is a draft again.
- Students see, open, run, submit, ask hints on and start attempts for only what is published to their batch; anything else is 404. Practice tests are always looked up within the caller's college. The old fallbacks to "any test" are removed.
- Trainer notes on a problem are edited on 22 and shown on 24.
- **Results back:** for each of the trainer's students the item reaches: attempts, the best result (coding: status and tests passed; tests: best score and accuracy), plus totals.

## The IREP bank (L37)

- Bank items are coding problems and practice tests in the platform tenant (`irep_platform`), authored by IREP staff on 46. They are never shown to students directly.
- A trainer imports a bank item into their college as a **draft** (`source_id` points back to it; importing twice is refused). From there it follows the normal publishing rules. 46 shows how many colleges imported each item.

## Judge0 (untrusted code)

- Code runs through `services/judge0_service.py`. `JUDGE0_ADAPTER=fake` (default) grades locally without executing anything. `JUDGE0_ADAPTER=judge0` calls a Judge0 CE cluster over HTTP with `JUDGE0_AUTH_TOKEN`.
- Production refuses to start without `JUDGE0_ADAPTER=judge0`, a URL and a token (`main.py`).
- Operating rules (for the person who sets it up; `infra/` changes need review):
  - Judge0 runs on its own host or VM, never on the database or API host, with no route to the database, Valkey or internal services (egress denied except what Judge0 itself needs).
  - Enable Judge0 authentication and put the token only in the API's secret store. The Judge0 config file is never committed.
  - Keep the per-submission CPU, wall-time and memory limits (problem `time_limit_ms`, `memory_limit_mb`) and Judge0's own sandbox limits; cap concurrent submissions per college.
  - Monitor queue length; the coding screen shows a clear error when Judge0 is unavailable.

## Endpoints

| Method | Path | Role |
| --- | --- | --- |
| GET | `/trainer/assessments` | trainer |
| POST | `/trainer/assessments/problems`, `/trainer/assessments/tests` | trainer (drafts) |
| PUT | `/trainer/assessments/problem/{id}/notes` | trainer |
| POST | `/trainer/assessments/{problem\|test}/{id}/publish`, `.../unpublish` | trainer, own batches only |
| GET | `/trainer/assessments/{problem\|test}/{id}/results` | trainer |
| GET | `/trainer/bank`; POST `/trainer/bank/{problem\|test}/{id}/import` | trainer |
| GET | `/admin/content/bank`; POST `/admin/content/bank/problems`, `/admin/content/bank/tests` | irep_admin |
| GET | `/student/tests` | student |

## Acceptance tests

- **API:**
  - L13: drafts are invisible; publishing reaches the batch only (other batches 404, including submit); notes travel; results come back for coding and tests; unpublishing hides again.
  - Guards: another trainer's batch is 403; past due dates are 422; another college is 404; students are 403; at least one visible case; options A to D; a college-wide item keeps other batches when one trainer unpublishes; no fallback to another test.
  - L37: bank items import as drafts once; a published import reaches the student; staff add bank problems that never reach students directly.
- **E2E:** a trainer creates and publishes a test, a student sees it and submits, and the trainer sees the score (L13); a bank test imports (L37); staff see the bank; Tamil toggle; role guard.
