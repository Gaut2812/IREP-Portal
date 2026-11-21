# Screens 46 · Content library (IREP staff) and 11 · My courses (student)

**Sprint:** S6. **Status:** 46 is new (gap fix); 11 is feature-only.
**Routes:** `/admin/content` (46), `/student/courses` and `/student/courses/{id}` (11).
**Flow:** "Content publishing" (steps 1, 2, 6, 7). The question and problem banks for 22 and 24 (L37's other half) come with Assessments in S9.

## Links

| Link | Direction | What moves | Status |
| --- | --- | --- | --- |
| L12 | 46 → 11 | Curriculum, lessons and notes by semester and track, when published | active |
| L33 | 11 → 12 | Course progress feeds the dashboard skill bars | active |
| L37 | 46 → 44 | Tamil and English notification templates | active for templates. 46 → 22/24 banks are planned (S9), so the link row stays `planned` until then |

## Ownership and tenancy

- Library content is IREP's. Courses, lessons and templates live in the **platform tenant** (`irep_platform`), and only `irep_admin` writes them.
- Students in every college read **published** courses for their semester and track. This is the one place a query reads outside the caller's college, and it's read-only for published content.
- Progress (`lesson_progress`) belongs to the student's own college, like any student data.

## Data

- `courses`: `title_en`/`title_ta`, `track` (or `All`), `semester`, `skill_key` (one of the dashboard skills: `dsa`, `aptitude`, `cloud`, `track`, `future_skills`, `communication`), `status` (`draft` or `published`), `published_at`.
- `lessons`: `course_id`, `position`, `title_en`/`title_ta`, `body_en`/`body_ta` (Markdown), `duration_min`.
- `lesson_progress`: `student_id`, `lesson_id` and `completed_at`; unique per student and lesson.
- `notification_templates`: `key`, `title_en`/`title_ta`, `body_en`/`body_ta` with `{placeholders}`. `services/templates.render(key, **vars)` falls back to the caller's text when no template exists.

## Rules

- Publishing needs at least one lesson with a title and body in English and Tamil, and notifies the matching students. Unpublishing hides the course but keeps progress.
- **L33:** after a lesson is completed, the student's skill bar for the course's `skill_key` becomes `max(current, round(100 × completed ÷ published lessons))` across that skill's courses. It never goes down, so the existing scores aren't disturbed.
- Every create, publish and template change is audited.

## Endpoints

| Method | Path | Role |
| --- | --- | --- |
| GET/POST | `/admin/content/courses` | irep_admin |
| GET/PUT | `/admin/content/courses/{id}` | irep_admin: course and its lessons |
| POST | `/admin/content/courses/{id}/lessons` | irep_admin |
| PUT/DELETE | `/admin/content/lessons/{id}` | irep_admin |
| POST | `/admin/content/courses/{id}/publish` and `/unpublish` | irep_admin |
| GET/PUT | `/admin/content/templates`, `/admin/content/templates/{key}` | irep_admin |
| GET | `/student/courses?lang=` | student: published courses for their semester and track, with progress |
| GET | `/student/courses/{id}?lang=` | student: lessons with completion state; Tamil text when `lang=ta` |
| POST | `/student/lessons/{id}/complete` | student; idempotent |

## Acceptance tests

- **API:**
  - Staff create a course and lessons, then publish it; publishing is refused while a Tamil body is missing.
  - L12: the course appears on 11 for matching students only, not before publishing.
  - L33: completing lessons raises the skill bar and never lowers it.
  - Templates render with variables and fall back when missing.
  - Roles are guarded; students only see published courses for their own semester and track.
- **E2E:**
  - Staff publish a course; a student opens it and completes a lesson.
  - Tamil toggle; role guard.
