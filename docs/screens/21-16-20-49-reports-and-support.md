# Screens 21 · Reports (trainer), 16 · Progress reports (parent), 20 · MoU reports (college), 49 · Support desk (IREP staff)

**Sprint:** S8. **Status:** 21, 16 and 20 are feature-only; 49 is new (gap fix).
**Routes:** `/trainer/reports` (21), `/parent/reports` (16), `/college/reports` (20), `/support` (any signed-in user) and `/admin/support` (49).
**Also in S8 (not screens):** an API load-test script (`apps/api/loadtest/`). The production deploy needs the hosting account, domain and secrets; it is tracked separately and its `infra/` changes go to a person for review.

## Links

| Link | Direction | What moves | Status |
| --- | --- | --- | --- |
| L22 | 21 → 16 | The approved monthly card and its PDF | active |
| L23 | 47 → 20 | Usage figures in the MoU report | planned (47 is S12/S16). 20 shows MoU terms and enrolment against the cap now |
| L35 | all data → 20 | Aggregates only | active (existing) |
| L28 | 49 → 44 | Ticket replies as notifications | active |
| L39 | every screen → 44, 49 | Alerts in; report-a-problem out | active: "Report a problem" is in the shell on every screen |

## Screen 21 · Reports (trainer)

- One card per student per month (`monthly_cards`), for the trainer's batches only (else 404).
- **Generate drafts** for a month: students without a card get a draft built from current data (problems solved, readiness, attendance, communication skill), with "last month" taken from the previous card. Re-running never overwrites a card.
- **Edit** a draft: trainer remark and "how to help at home", in English and Tamil.
- **Approve** (release rule §5.1.1): needs the remark and the help text in both languages. Approval sets `approved`, renders the PDF, notifies each linked parent (in-app and SMS, link `/parent/reports`), and audits `monthly_card.released`. Approved cards are read-only. Several cards can be approved at once; cards that fail the checks are listed back and left as drafts.

## Screen 16 · Progress reports (parent)

- Needs the granted `parent_data_processing` consent, like 15.
- Lists the child's released cards (`approved` or `sent`), newest first; a card shows its rows, the remark and the help text in the chosen language, and the PDF. Drafts and other children's cards are 404.

## Screen 20 · MoU reports (college)

- `college_admin` and `placement_officer`. Generate, list and download report PDFs (existing API). The report adds the active MoU (period and students against the cap). Content is aggregates only (L35): no names, notes or chats.

## Screen 49 · Support desk

- Anyone signed in can **report a problem** from any screen. The ticket keeps the page it came from, a category (`bug`, `question`, `access`, `data`) and the requester's college and role. IREP staff are notified in-app.
- Requesters see and reply to their own tickets only (others are 404). IREP staff (`irep_admin`) see every ticket, reply and close.
- **L28:** a staff reply notifies the requester in-app (`support.ticket_replied`, no audit per §5.3) with a link to the ticket. Requester replies reopen an answered ticket.
- Status: `open` → `answered` (staff replied) → `closed`. A closed ticket takes no more messages.

## Endpoints

| Method | Path | Role |
| --- | --- | --- |
| GET | `/trainer/reports?month=YYYY-MM&lang=` | trainer |
| POST | `/trainer/reports/generate` | trainer |
| GET/PUT | `/trainer/reports/{card_id}` | trainer; PUT for drafts only |
| POST | `/trainer/reports/{card_id}/approve`, `/trainer/reports/approve` (bulk) | trainer |
| GET | `/parent/reports?child_id=&lang=`, `/parent/reports/{card_id}?lang=`, `/parent/reports/{card_id}/pdf` | parent |
| GET/POST | `/college/reports`, `/college/reports/generate`, `/college/reports/{id}/download` | college (existing) |
| GET/POST | `/support/tickets`, `/support/tickets/{id}`, `/support/tickets/{id}/messages`, `/support/tickets/{id}/close` | any signed-in user (own tickets); irep_admin (all) |

## Acceptance tests

- **API:**
  - L22: drafts are hidden from the parent; approval needs Tamil, releases the card to 16 and 15, notifies the parent and audits; the PDF downloads.
  - Approved cards cannot be edited; other batches' cards are 404 for a trainer; another parent's child is 404; no consent means no cards.
  - 20: the report includes the MoU terms and aggregates only.
  - L39 and L28: a user reports a problem; staff see it and reply; the requester is notified and sees the reply; other users get 404; closed tickets refuse messages.
- **E2E:** trainer approves a card and the parent opens it in 16; a user reports a problem and staff reply (L28, L39); Tamil toggle and role guards.
