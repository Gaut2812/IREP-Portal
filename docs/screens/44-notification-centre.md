# Screen 44 · Notification centre

**Role:** every role (opened from the bell). **Sprint:** S3. **Status:** new screen (gap fix).
**Route:** `/notifications`.
**Purpose:** a list of the user's notifications with filters and read state, plus their delivery preferences (channels, quiet hours, language).

## Links

| Link | What moves | Status |
| --- | --- | --- |
| L39 | Alerts from every screen arrive here; report-a-problem goes to 49 | planned until 49 (support) is built; the alerts half works today |
| L28 | 49 → 44: ticket replies as notifications | planned (S8) |
| L37 | 46 → 44: Tamil and English templates | planned (S6) |

## Endpoints (`/api/v1/notifications…`, any signed-in user, own rows only)

| Method | Path | Rule |
| --- | --- | --- |
| GET | `/notifications` | Newest first. Query: `kind`, `unread_only`, `before` (cursor), `limit` ≤ 100. Returns `kinds` and `next_before` |
| GET | `/notifications/unread-count` | |
| POST | `/notifications/{id}/read` | Another user's id returns 404 |
| POST | `/notifications/read-all` | |
| GET/PUT | `/notifications/preferences` | `email_enabled`, `sms_enabled`, `push_enabled`, `quiet_start_hour` and `quiet_end_hour` (both set or both empty, 0–23), `language` (stored on the user) |

## Delivery rules (`services/notifications.notify_user`)

- In-app notifications are always delivered immediately.
- A channel the user switched off is recorded as `suppressed`: not sent, and visible in delivery reports.
- During quiet hours, SMS and email are queued in the outbox with a delay until the hours end, so nothing is lost. The window may wrap midnight, for example 21 → 7.
- SMS and email use the user's language when a Tamil version exists.
- Push needs web-push keys and a service worker (planned). The preference is stored now.

## Acceptance tests

- **API** (`tests/test_screen_44_notifications.py`):
  - Filters and the cursor return no overlapping pages.
  - Another user's notification returns 404.
  - Preference validation.
  - A suppressed channel creates no outbox event.
  - Quiet hours delay SMS until they end.
  - Tamil text is used for a Tamil-preferring user.
  - Quiet-window maths.
- **E2E** (`e2e/screen44-notifications.spec.ts`):
  - Bell → "See all" → mark all read → unread filter.
  - Preferences saved.
  - Tamil toggle.
  - A signed-out visitor is redirected to sign in.
