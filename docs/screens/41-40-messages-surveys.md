# Screens 41 · College messages, 40 · Feedback survey (parent) and the surveys part of 02

**Sprint:** S14. **Status:** 41 and 40 are feature-only.
**Routes:** `/college/messages` (41), `/college/surveys` (02 settings, surveys), `/parent/surveys` (40).

## Links

| Link | Direction | What moves | Status |
| --- | --- | --- | --- |
| L20 | 35 ↔ 41 | Trainer and coordinator chat | active |
| L30 | 41 → 34, 15 | Announcement-only posts to students and parents | active |
| L26 | 02 ↔ 40 | Survey sent; responses returned | active |

## 41 · Chat with trainers (L20)

- A college admin starts a thread with any trainer of the college (the pair is allowed in `chat_policy.can_message`; no policy change). Messages use the existing thread endpoints, including Tamil translation and the WebSocket. The trainer sees the thread under "College" in 35.

## 41 · Announcements at scale (L30)

- One-way posts to students, parents or both, for the whole college or one batch, in English and Tamil. Audited as `announcement.posted`.
- **Students:** a post in the announcement-only group (34) and an in-app notice.
- **Parents:** an in-app notice and SMS (through the outbox), and the announcement on the overview (15).
- **Fan-out:** the request writes the announcement and one outbox event per 500 recipients. The dispatcher delivers chunks independently (several Celery workers in production).
  - A chunk is idempotent: recipients who already have the notice are skipped.
  - The page shows delivered out of recipients while it runs.
- **Benchmark** (`loadtest/broadcast_fanout.py`): on this machine (SQLite) one worker delivered 614 notices in about 0.4 to 0.7 s, roughly 900 to 1,500 a second, which projects to under a minute for 50,000 against the Master Plan's 15. Re-run it on PostgreSQL before the pilot.

## 02 / 40 · Surveys (L26)

- The college writes rating (1–5), pick-one and comment questions in English and Tamil. Publishing needs the Tamil text, notifies every linked parent (in-app and SMS) and is audited as `survey.published`. Drafts can be edited; published surveys can be closed.
- Parents answer once, in either language (a Tamil option is stored as its English option). Required questions are checked, and closed or past-date surveys refuse answers.
- **Results:** averages and the spread for ratings, counts for choices, and comments in sorted order without names. Nothing is shown below 3 responses, so a single parent's answers cannot be picked out.

## Labs track S14

- **Cloud Sandbox:** each college sets its own AWS Academy Learner Lab course link (https on awsacademy.instructure.com or awsacademy.com only). The external lab opens it and its credits are metered as before.
- **Lab hours in the college view:** the college overview (19) adds this month's lab hours against quota and how many students used labs (aggregates).

## Endpoints

| Method | Path | Role |
| --- | --- | --- |
| GET/POST | `/college/threads`; GET `/college/message-contacts` | college_admin |
| GET/POST | `/college/announcements`; GET `/college/announcements/{id}` | college_admin |
| GET/PUT | `/college/labs/cloud-sandbox` | college_admin |
| GET/POST | `/college/surveys`; PUT `/college/surveys/{id}`; POST `.../publish`, `.../close`; GET `.../results` | college_admin |
| GET | `/parent/surveys?lang=`; POST `/parent/surveys/{id}/responses` | parent |

## Acceptance tests

- **API:**
  - L20: start a chat and both sides see the messages; the policy forbids non-trainers; tenant 404; role 403.
  - L30: recipients match the batch, chunks are delivered, an idempotent retry sends nothing, the group post appears, and the parent overview shows it in Tamil; large audiences split into chunks.
  - L26: Tamil is required to publish; answers are validated; answer once; results stay hidden below the threshold; aggregates without names; closed surveys refuse answers; guards.
  - AWS Academy link and lab hours on the overview.
- **E2E:** the college chats; an announcement reaches the parent's overview; a survey is published and answered; Tamil; role guard.
