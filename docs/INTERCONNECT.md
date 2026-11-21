# IREP Portal — Interconnect

The source of truth for how the 49 screens link together. `scripts/link_gate.py` reads the link table in section 3 and fails CI when an **active** link has no passing test tagged with its ID.

Source: *IREP Portal — 26 + 9 Screen Map, Links and Visual Flows* (19 Nov 2026), which builds on the Final Screen Map and Link Table v1.0 (15 Nov 2026) and the mockup PDF. If this file and that document disagree, fix this file and note the change in the PR.

## 1. How to use this file

- **Building a screen:** wire every link listed for it in section 4, and write the notification and audit events from section 5.3.
- **Proving a link:** tag the test that exercises both ends.
  - pytest: `@pytest.mark.link("L07")`
  - Playwright: `test("…", { tag: "@L07" }, …)`
- **Turning a link on:** when both screens of a link exist, change its status from `planned` to `active` in the same PR that adds the test. From then on the gate requires a passing test for it.
- **Build sprint:** each link is built in the same sprint as the later of its two screens.

## 2. Status values

| Status | Meaning | Gate |
| --- | --- | --- |
| `active` | Both ends are built | Needs at least one passing tagged test and no failing one |
| `planned` | At least one end is not built yet | Reported only |

Screens built so far: 01, 07, 08, 12, 13, 15, 18 (parent messages at `/parent/messages`), 19, 23, 24, 29, 30, 31, 32, 33, 34, 35, 36, 02, 03, 04, 05, 06, 09, 10, 11, 14, 16, 17, 20 (MoU terms; usage figures with 47), 21, 42, 43 (leave and Cyber Range; certificate proofs in S11), 44, 45, 46 (curriculum and templates; banks in S9), 48, 49. Readiness v1 (S7) recomputes attendance from the register every night.

Screen specs live in `docs/screens/` (one file per screen, written before the screen is built).

## 3. Link table

### 3.1 Arrow links (drawn on the map)

| ID | From | To | Direction | What moves | Trigger | Basis | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L01 | 01 Sign-in | 12, 13, 15, 19, 45 | One way | Role, college and language decide the home screen and sidebar | After login | PDF | active |
| L02 | 12 Student dashboard | 13 Trainer dashboard | Both | Up: readiness, attendance, problems solved. Down: plan, notes, flags | Nightly and on events | PDF | active |
| L03 | 13 Trainer dashboard | 15 Parent overview | One way | Parent updates, monthly report, at-risk alert | Trainer quick actions | PDF | active |
| L04 | 08 Live sessions | 07 Live classroom | Both | Join request; recording and attendance back | Join session | PDF | active |
| L05 | 42 College events | 17 Parent events | Both | Invitations down; RSVPs and counts up | College publishes; parent taps RSVP | PDF, Gap fix | active |
| L06 | 07 Live classroom | 09 Trainer attendance | One way | Join and leave events; Present at 75% of the session | Meeting ends | PDF | active |
| L07 | 09 Trainer attendance | 10 Parent attendance | Both | Attendance record down; leave request up | Marking; parent request | Inferred | active |
| L08 | 29 Virtual labs | 43 Approvals | Both | Cyber Range access request; approve or deny | Student requests a lab | PDF, Gap fix | active |
| L09 | 10 Parent attendance | 43 Approvals | Both | Leave request; decision | Parent submits | Gap fix | active |
| L10 | 26 Student certificates | 43 Approvals | Both | External certificate proof; decision | Student uploads proof | Gap fix | planned |
| L11 | 05 Schedule | 06 Timetable | Both | Proposed sessions; approval or clash warning | Any schedule change | Inferred | active |
| L12 | 46 Content library | 11 My courses | One way | Curriculum, lessons, notes by semester and track | Content published | Gap fix | active |
| L13 | 22 Assessments | 24 Coding Lab, 23 Practice tests | Both | Problems, tests, trainer notes; results back to 22 | Trainer publishes | PDF | planned |
| L14 | 30 Sprint board | 31 Code reviews | Both | Pull-request queue; review result and change requests | Pull request opened | PDF | active |
| L15 | 32 Portfolio | 33 Parent projects | One way | Public projects, links and demo videos | Student sets visibility | Inferred | active |
| L16 | 36 Student interviews | 37 Trainer interviews | Both | Slots, rubric scores, feedback, recording | Booking, then scoring | PDF | planned |
| L17 | 38 Mock drives | 37 Trainer interviews | One way | Drive rounds reuse interview slots and tests | Drive created | Inferred | planned |
| L18 | 34 Discussions | 35 Messages | Both | Reports to the moderation queue; remove or keep back | One-tap report | PDF | active |
| L19 | 35 Messages | 18 Message trainer | Both | One-to-one chat, translation, 24-hour reply promise | Message sent | PDF | active |
| L20 | 35 Messages | 41 College messages | Both | Trainer and coordinator chat | Message sent | PDF, Gap fix | planned |
| L21 | 25 Study Buddy | 14 At-risk, 13 Trainer dashboard | One way | AI usage counts for each student | Every AI call | PDF | planned |
| L22 | 21 Reports | 16 Parent progress reports | One way | Approved monthly card and PDF | Trainer approves | PDF, plan | active |
| L23 | 47 Usage and billing | 20 MoU reports | One way | Usage figures included in reports | Monthly | Gap fix | planned |
| L24 | 04 Batches | 03 Branches and batches | Both | Structure and student lists down; roster changes up | Import, semester promotion | Inferred | active |
| L25 | 45 Colleges | 03 Branches and batches | One way | New college, first admin, structure import | Admin creates a college | Gap fix | active |
| L26 | 40 Survey | 02 Settings | Both | Survey sent; responses returned | College publishes a survey | Inferred | planned |
| L27 | 48 Audit | 02 Settings | Both | Data export and deletion requests; audit trail | College admin requests | Gap fix | active |
| L28 | 49 Support | 44 Notification centre | One way | Ticket replies as notifications | Support replies | Gap fix | active |

### 3.2 Core links (through the portal core, no arrow)

| ID | From | To | Direction | What moves | Trigger | Basis | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L29 | 42 College events | 12, 34, 38 | One way | Upcoming list, placement-update posts; a mock drive is an event type (12 and 34 built and tested; 38 in S15) | Event published | Gap fix | planned |
| L30 | 41 College messages | 34, 15 | One way | Announcement-only posts to students and parents | Announcement posted | PDF, Gap fix | planned |
| L31 | 14 At-risk | 18, 15 | One way | A flag creates a parent call and alert; the parent sees it in messages and the overview | Flag action | PDF | active |
| L32 | 26 Student certificates | 27 Parent certificates | One way | Read-only copy of earned certificates | Certificate verified | Inferred | planned |
| L33 | 11 My courses | 12 Dashboard | One way | Course progress feeds the skill bars | Lesson progress | Inferred | active |
| L34 | 24, 23, 30, 36 and attendance (09) | 12, 13, 14, 15, 19, 39 | One way | One readiness score and band shown everywhere | Nightly and on events | PDF | active |
| L35 | All data | 19, 39, 28, 20 | One way | Aggregates only; no private trainer notes or chats | On read | PDF | active |
| L36 | 47 Usage and billing | 29, 25, 08 | One way | Quotas for lab hours, AI calls and recording storage | Every metered use | Gap fix | planned |
| L37 | 46 Content library | 22, 24, 44 | One way | Question bank, problem bank, notification templates | Content published | Gap fix | planned |
| L38 | Every sensitive action | 48 Audit; consent records for 15 and 32 | One way | Audit trail and consent | Every sensitive action | Gap fix | active |
| L39 | Every screen | 44 Notification centre, 49 Support | One way | Alerts in; report-a-problem out | Any alert or report | Gap fix | active |

L38 is `active` for the audit writer that already records sensitive actions. Screen 48 and the consent records stay to be built in S2.

### 3.3 Labs links (proposed)

The Master Plan adds L40–L43 for the labs track "once confirmed". This is an open decision, so they are not listed in the gate yet.

## 4. Per-screen links

Arrows: → sends to, ← receives from, ↔ both ways. Every screen also has L39 (bell → 44; report-a-problem → 49) and L38 (sensitive actions → 48), which are not repeated below.

### Student

- **11 My courses** (S6): ← 46 · L12 curriculum by semester and track · → 12 · L33 progress feeds skill bars
- **12 Student dashboard** (built): ← 01 · L01 · ↔ 13 · L02 · ← L34 readiness · ← 42 · L29 upcoming · ← 11 · L33
- **23 Practice tests** (built): ← 22 · L13 tests down, results back · → L34 readiness input
- **24 Coding Lab** (built): ← 22 · L13 problems and trainer notes · ← 46 · L37 problem bank · → L34 readiness input
- **25 AI Study Buddy** (after pilot): → 14, 13 · L21 AI usage counts · ← 47 · L36 AI-call quota and daily cap
- **26 Certificates** (S11): ↔ 43 · L10 proof up, decision down · → 27 · L32 · → 28 · L35 counts and proof status only. *Release rule: verified only after trainer approval.*
- **29 Virtual labs** (built): ↔ 43 · L08 Cyber Range access · ← 47 · L36 lab-hour quota
- **30 Sprint board** (built): ↔ 31 · L14 · → L34 readiness input
- **32 Portfolio** (built): → 33 · L15 public projects · → 48 · L38 consent for a public portfolio
- **34 Discussions** (built): ↔ 35 · L18 moderation · ← 41 · L30 announcements · ← 42 · L29 placement posts
- **36 Mock interviews** (built): ↔ 37 · L16 · → L34 readiness input

### Trainer

- **04 Batches** (S3): ↔ 03 · L24 structure down, roster changes up
- **05 Schedule** (S4): ↔ 06 · L11 proposals up, approval or clash back
- **07 Live classroom** (built): ↔ 08 · L04 · → 09 · L06 Present at 75%
- **09 Attendance** (S4): ← 07 · L06 · ↔ 10 · L07 · → L34 readiness input. *Release rule: leave changes attendance only after approval.*
- **13 Trainer dashboard** (built): ↔ 12 · L02 · → 15 · L03 · ← 25 · L21 · ← L34
- **14 At-risk students** (built): ← 25 · L21 · ← L34 · → 18, 15 · L31 parent call and alert
- **21 Reports** (built): → 16 · L22 approved monthly card. *Release rule: card released only after trainer approval.*
- **22 Assessments** (S9): ↔ 24, 23 · L13 · ← 46 · L37 question and problem banks
- **31 Code reviews** (built): ↔ 30 · L14 PR queue in, review result out
- **35 Message Hub** (built): ↔ 18 · L19 · ↔ 34 · L18 · ↔ 41 · L20
- **37 Mock interviews** (S15): ↔ 36 · L16 · ← 38 · L17
- **43 Approvals** (S5 leave, S11 proofs, S12 labs): ↔ 29 · L08 · ↔ 10 · L09 · ↔ 26 · L10. Every decision → 44 and 48.

### Parent

- **10 Attendance** (S5): ↔ 09 · L07 · ↔ 43 · L09
- **15 Parent overview** (built): ← 01 · L01 · ← 13 · L03 · ← 14 · L31 · ← 41 · L30 · ← L34
- **16 Progress reports** (built): ← 21 · L22
- **17 Events** (built): ↔ 42 · L05 invitations down, RSVP up
- **18 Message trainer** (built): ↔ 35 · L19 · ← 14 · L31
- **27 Certificates** (S11): ← 26 · L32 read-only
- **33 Projects and portfolio** (built): ← 32 · L15
- **40 Feedback survey** (S14): ↔ 02 · L26

### College

- **02 Settings** (S2): ↔ 40 · L26 · ↔ 48 · L27 export and deletion
- **03 Branches and batches** (S2): ← 45 · L25 · ↔ 04 · L24
- **06 Timetable** (S4): ↔ 05 · L11
- **19 College overview** (built): ← 01 · L01 · ← L34 · ← L35 aggregates only
- **20 MoU reports** (built; L23 usage figures with 47): ← 47 · L23 · ← L35 aggregates only
- **28 Certifications** (S11): ← L35 counts, proofs and vouchers as aggregates
- **38 Mock drives** (S15): → 37 · L17 · ← 42 · L29
- **39 Placement readiness** (S15): ← L34 · ← L35
- **41 Messages** (S14): ↔ 35 · L20 · → 34, 15 · L30 announcement-only posts
- **42 Events** (built): ↔ 17 · L05 · → 12, 34, 38 · L29

### Admin (IREP staff)

- **45 Colleges and MoU terms** (S2): ← 01 · L01 · → 03 · L25
- **46 Content library** (S6): → 11 · L12 · → 22, 24, 44 · L37
- **47 Usage and billing** (quotas S12, full S16): → 20 · L23 · → 29, 25, 08 · L36
- **48 Audit and consent** (S2): ↔ 02 · L27 · ← every sensitive action · L38
- **49 Support desk** (built): ← every screen · L39 · → 44 · L28

### Shared

- **01 Sign-in** (built): → 12, 13, 15, 19, 45 · L01
- **44 Notification centre** (S3): ← every screen · L39 · ← 49 · L28 · ← 46 · L37 templates

## 5. Rules the links must obey

### 5.1 Release rules

All four run through the trainer (screens 21 and 43):

1. A parent's monthly card is released only after the trainer approves it (21).
2. A Cyber Range session starts only after the trainer approves access (43).
3. A leave request changes attendance only after the trainer approves it (43).
4. An external certificate shows as verified only after the trainer approves the proof (43).

### 5.2 Who can message whom

Enforced in one function, `can_message` (see `apps/api/services/chat_policy.py`).

| Pair | Allowed | Where |
| --- | --- | --- |
| Student ↔ student, one to one | No | — |
| Student groups | Yes, moderated by trainers | 34 |
| Trainer ↔ parent, one to one | Yes, with Tamil–English translation | 35, 18 |
| Trainer ↔ college coordinator | Yes | 35, 41 |
| Announcements | Trainer → batches and parents; college → placement groups and parents | 35, 41 |
| Trainer ↔ student, one to one | No (recommended; decision needed): use groups and review comments | — |
| Parent ↔ college, direct | No (recommended; decision needed): route through the trainer | — |
| Parent ↔ student | No (decision needed) | — |
| Admin → anyone | System notices only, through 44 | 44 |

### 5.3 Notification and audit events

Every approval, release and removal writes an audit entry (48, via `services/audit.record_audit`) and sends a notification (44). Under the Master Plan both are written through the outbox in the same transaction as the change.

| Event | Audit | Notify | Recipient | Screen |
| --- | --- | --- | --- | --- |
| `leave.requested` | yes | yes | trainer | 10 → 43 |
| `leave.decided` | yes | yes | parent | 43 |
| `lab_access.requested` | yes | yes | trainer | 29 → 43 |
| `lab_access.decided` | yes | yes | student | 43 |
| `certificate_proof.submitted` | yes | yes | trainer | 26 → 43 |
| `certificate_proof.decided` | yes | yes | student | 43 |
| `monthly_card.released` | yes | yes | parent | 21 |
| `at_risk.flagged` | yes | yes | trainer | 14 |
| `at_risk.parent_call` | yes | yes | parent | 14 → 18, 15 |
| `message.reported` | yes | yes | moderators | 34 → 35 |
| `message.removed` / `member.muted` | yes | yes | sender | 35 |
| `announcement.posted` | yes | yes | audience | 35, 41 |
| `schedule.change_decided` | yes | yes | trainer, students | 06 → 05, 08 |
| `event.published` | yes | yes | audience | 42 |
| `event.rsvp` | yes | no | — | 17 |
| `survey.published` | yes | yes | parents | 02 → 40 |
| `data_request.created` / `data_request.completed` | yes | yes | college admin | 02 ↔ 48 |
| `support.ticket_replied` | no | yes | requester | 49 → 44 |
| `consent.recorded` | yes | no | — | 48 |
| `college.created` | yes | yes | first college admin | 45 |

Event names are derived from the flows in the source document. Confirm any new ones in the PR that adds them.

### 5.4 Who sees what

| Data | Student | Parent | Trainer | College | Admin |
| --- | --- | --- | --- | --- | --- |
| Readiness and scores | Own | Own child | Assigned batches | Aggregates and bands | Support access, logged |
| Attendance | Own | Own child | Assigned batches | Averages | Support access, logged |
| Code and test details | Own | Summary only | Assigned batches | No | No |
| Trainer private notes | No | No | Yes | No | No |
| Chats | Own groups | Own threads | Own threads and groups | Own threads | No |
| Certificates | Own | Own child | Assigned batches | Counts and proof status | No |
| Consent and audit | Own consent | Own consent | No | Export requests | Full audit trail |
