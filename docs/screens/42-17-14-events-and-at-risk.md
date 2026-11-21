# Screens 42 · Events (college), 17 · Events (parent), 14 · At-risk students (trainer), and readiness v1

**Sprint:** S7. **Status:** 42 is new (gap fix); 17 and 14 are feature-only.
**Routes:** `/college/events` (42), `/parent/events` (17), `/trainer/at-risk` (14).
**Flows:** "Events and RSVPs" and "At-risk support" (steps 1 to 6). Readiness v1 closes the L34 gap: attendance is recomputed from the session register every night.

## Links

| Link | Direction | What moves | Status |
| --- | --- | --- | --- |
| L05 | 42 ↔ 17 | Invitations down; RSVPs and counts up | active |
| L29 | 42 → 12, 34, 38 | Upcoming list on 12; placement-update posts in the placement group on 34; mock drives on 38 | 12 and 34 are built and tested. 38 comes in S15, so the row stays `planned` until then |
| L31 | 14 → 18, 15 | A parent call on a flag sends the parent an alert, opens a message in the trainer thread (18) and shows a support alert on the overview (15) | active |
| L34 | inputs → 12, 13, 14, 15, 19, 39 | Nightly readiness: attendance from the register, then the score, band and monthly delta | active (v1) |
| L21 | 25 → 14 | AI usage counts | planned (25 is S10) |

## Screen 42 · Events (college)

- Roles: `college_admin` and `placement_officer`. Events belong to the caller's college.
- An event has an English and Tamil title (Tamil is required to publish), a kind (`event`, `guest`, `demo_day`, `meeting`, `drive`, `placement_update`), start and end, location, audience (`students`, `parents`, `all`), an optional batch, and whether it takes RSVPs.
- Status is `draft`, `published` or `cancelled`. Only drafts are edited. Rows made before S7 count as `published`.
- **Publish** (start in the future): the audience is notified (students in-app; parents in-app and SMS through the outbox). `event.published` is audited.
  - **L29:** a `drive` or `placement_update` also posts an announcement in each placement-announcement group (`kind = announcements`), visible on 34.
- **Cancel:** parents who said yes or maybe are told; it is audited (`event.cancelled`).
- **Counts up (L05):** each event shows yes, maybe and no counts and the expected guests. The college sees counts only, never which parent answered (§5.4 aggregates).

## Screen 17 · Events (parent)

- Published events for parents or everyone, college-wide or for the child's batch: upcoming, then the last 30 days.
- RSVP (yes, maybe or no, with 0 to 10 guests) only for upcoming published events that take RSVPs; otherwise 404. Saving is audited as `event.rsvp`; nobody is notified (§5.3).

## Screen 14 · At-risk students (trainer)

- Flags for the trainer's batches only (a flag in another batch or college is 404). It shows a summary (open, high severity, parent alerts sent), each flag's student, score, band and attendance, and the flag's history of actions.
- Actions: parent call, extra Saturday, mentor, note; resolving needs a note (existing endpoints, now audited as `at_risk.parent_call` for calls).
- **L31:** a parent call alerts each linked parent once per flag and posts a message in the trainer–parent thread (created if missing), in English and Tamil. During the college's quiet hours (default 21:00 to 08:00) the call is held: it is queued in the outbox until quiet hours end, and the handler is idempotent (`parent_notified`).
- 15 shows open flags whose parent has been alerted as a support alert, with the trainer's suggested next step. 13's existing counts are unchanged.

## Readiness v1 (nightly)

`services/readiness.run_nightly(db, college_id)`, scheduled by Celery beat at 01:30 IST for every college, and runnable from `POST /admin/jobs/readiness`:

1. **Attendance:** `Present ÷ (Present + Absent + Partial)` over the student's register rows, so Excused (approved leave) and trainer overrides count as they were finally marked. A student with no marked rows keeps the stored value.
2. **Score:** one snapshot per student per day; a re-run the same day replaces it.
3. **Delta:** today's score minus the score from about a month ago (the latest snapshot on or before 30 days ago, else the oldest one), matching "this month" on 12 and 15.
4. **At-risk rules** run on the new numbers; each new flag notifies the batch's trainers in-app (`at_risk.flagged`, audited).

## Endpoints

| Method | Path | Role |
| --- | --- | --- |
| GET/POST | `/college/events` | college_admin, placement_officer |
| GET/PUT | `/college/events/{id}` | same; PUT for drafts only |
| POST | `/college/events/{id}/publish`, `/college/events/{id}/cancel` | same |
| GET | `/parent/events?lang=&child_id=` | parent |
| POST | `/parent/events/{id}/rsvp` | parent (existing; now upcoming published events only) |
| GET | `/trainer/at-risk?status=&lang=` | trainer (existing; adds summary, band and attendance) |
| GET | `/trainer/flags/{id}` | trainer: flag with its action history |

## Acceptance tests

- **API:**
  - L05: a published event reaches the parent list; RSVP updates the college's counts; RSVP to drafts, cancelled or past events is refused.
  - L29: publishing a drive lists it on the student dashboard and posts in the placement group.
  - L31: a parent call alerts the parent once, adds a thread message and shows on 15; in quiet hours the alert is held in the outbox and delivered once.
  - L34: the nightly job recomputes attendance from the register (Excused left out), keeps one snapshot per day, uses a monthly delta, and opens and notifies new flags.
  - Role guards (403) and cross-college or other-batch checks (404); Tamil output on 17 and 14.
- **E2E:** the college publishes an event and a parent RSVPs, then the counts update; a trainer makes a parent call and the parent sees the alert on the overview; Tamil toggle and role guards.
