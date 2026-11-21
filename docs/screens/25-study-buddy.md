# Screen 25 · AI Study Buddy (student), and screen 34 moderation (S10)

**Sprint:** S10. **Status:** 25 is feature-only; the moderation words extend screen 34.
**Routes:** `/student/buddy` (25), `/college/moderation` (34 words for the college).

## Links

| Link | Direction | What moves | Status |
| --- | --- | --- | --- |
| L21 | 25 → 14, 13 | AI usage counts per student (never the chat) | active: the trainer dashboard's `ai_usage` and `ai_calls_7d` on each at-risk row |
| L36 | 47 → 25 | AI-call quota and daily cap | planned (47 is S12 and S16). The cap is read from the college's active MoU (`ai_calls_per_day`, default 30) |
| L18 | 34 ↔ 35 | Flagged posts reach the moderation queue | active (existing); college "flag" words add system reports |

## Study Buddy rules

- A hint-first tutor: it leads with hints and questions, explains the idea, uses a different small example, and never writes the full solution. It answers in the student's language (Tamil in, Tamil out). Studies only; it points to the trainer or counsellor for anything else.
- **Paused** while the student has a practice-test attempt in progress (409).
- **Minors' data:** the model sees the question, the student's last 6 turns and the topic. Emails and phone numbers are redacted before anything is stored or sent. No names, ids or other records are sent.
- **Cap:** the MoU's `ai_calls_per_day` per student per day (429 `quota`); one question at a time (429 `too_fast`).
- **Metering:** each answered question writes one `ai_calls` row to `usage_ledger` (L21 and the 47 credits meter). Students can delete their chat; the counts stay.
- **Rule 3:** the read transaction ends before the model is called. The turn and its usage are written afterwards.
- **Adapters:**
  - `STUDY_BUDDY_ADAPTER=fake` (default) gives fixed hints.
  - `=anthropic` uses Claude through the official SDK (`STUDY_BUDDY_MODEL`, default `claude-opus-5-5`): low effort for short tutoring turns, the system prompt cached, server-side refusal fallback (`fallbacks: "default"`), and a polite message if the request is still refused.
  - Production refuses `fake`. The `anthropic` package is not in `requirements.txt` yet: install it on the server that runs this adapter (SDK 1.x uses `httpx2`; check it next to the test stack before pinning it in CI).
- **Privacy notice:** the page says the trainer sees how often the student uses it, never what they ask.

## Moderation (34, S10)

- Always refused in groups: the platform's insult and test-leak words, phone numbers and emails (no private contact between students), and invite links to other chat apps.
- Each college keeps its own words (`college_admin`, audited): `block` refuses the post; `flag` lets it through and files a system report in the group moderators' queue (L18).
- Flood control: the same text three times in two minutes is refused.

## Endpoints

| Method | Path | Role |
| --- | --- | --- |
| GET, DELETE | `/student/buddy` | student (own chat) |
| POST | `/student/buddy/ask` | student |
| GET/POST | `/college/moderation/terms`; DELETE `/college/moderation/terms/{id}` | college_admin |

## Acceptance tests

- **API:**
  - Answers, Tamil reply, history, delete.
  - Redaction before the model and in storage.
  - Daily cap, too-fast and test lock.
  - Roles.
  - L21 counts without content.
  - The Claude adapter's request shape (stub client: model, cached system prompt, fallbacks, refusal handling).
  - Moderation: contact and invite links refused; block and flag words, with flags in the queue; flood control; tenant 404.
- **E2E:** ask and get a hint while the daily count goes down; clear the chat; Tamil; role guards; the college adds and removes a word.
