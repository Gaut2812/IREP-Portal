# Feedback review and implementation plan (27 Nov 2026)

Source: the owner's walkthrough of all five portals plus four screenshots. Each item below was checked in the code, and a cause is given where one was found. Paths are relative to the repo root.

Contents:
- Part A: bugs with confirmed causes
- Part B: how the screens you asked about work today
- Part C: the build plan, in phases
- Part D: decisions needed before Phase 2

---

## Part A. Bugs with confirmed causes

| # | What you saw | Cause in the code | Fix |
|---|---|---|---|
| A1 | Score history shows only "68 … 74", with no bars (screenshot 3) | `apps/web/src/app/student/page.tsx:358-362`: each bar's height is a `%`, but its parent is a flex column with no fixed height, so every bar is 0 px tall. Only the number labels show. | Give each column a fixed height (`h-full` and `justify-end`) or draw a small SVG line chart with dates on the x-axis. Show it with 1 snapshot too ("first snapshot"). |
| A2 | Sidebar says "Projects" (screenshot 1) | `locales/en.json` key `nav.sprint_board` = "Projects". | Change it to "Sprint Board" in `en` and `ta`. |
| A3 | Two "All 20 Problems" buttons (screenshot 4) | Coding lab `[problemId]/page.tsx:450` ("Problem 18 of 20" switcher) and `:526-534` (footer button) both open the same drawer. | Remove the footer button and keep the top switcher. |
| A4 | Coding lab doesn't run real code | `JUDGE0_ADAPTER=fake` (the default) never runs code. `MockJudge0Adapter` (`services/judge0_service.py:282`) passes any code that contains `countComponents`, so every other problem and language looks broken. | Run real Judge0 in dev (see C2.3). Keep the fake adapter for CI only. |
| A5 | Coding lab text is fixed English and fake | Hard-coded "Trainer Arun Kumar", "All 18 hidden test cases passed", "Problem {n \|\| 18}", "Curriculum Trainer: Arun Kumar", "Asked:" and "Input:". This breaks i18n rule 9 and shows wrong numbers. | Take these from the API (`tests_total` and the problem's author) and move the strings into `en`/`ta`. |
| A6 | Practice test opens on question 12 | `tests/[id]/page.tsx:151`: "If Question 12 exists, default to 12 as per PDF 4 mockup". This was copied from a mock-up. | Start on the first unanswered question. |
| A7 | Week sessions show the wrong state | `sessions.status` is a stored string ("Upcoming", "Missed", "Attended") set by the seed. In the demo DB, Thursday's past class is still "Upcoming" and Friday 09:00 is "Scheduled". | Work out the state at read time from the clock, the meeting and attendance: upcoming, live, ended, attended or missed. Keep the stored status only for cancelled sessions. |
| A8 | Trainer can't reopen the live classroom after ending a class | The sidebar link is hard-coded: `AppShell.tsx:104` → `/live/sess_thu_rag`. After that class ends, the link always lands on "Class ended". | Add a `/trainer/live` hub: today's and the next classes with Start or Join, and past classes with recordings and attendance. |
| A9 | "Schedule mock" quick action goes to Messages | `services/trainer_dashboard.py:164`: `href: "/trainer/messages"`. | Send it to `/trainer/interviews?new=slot`. Check every action (C3.1). |
| A10 | Weekly DSA widget's "Open" sends the trainer to the student solve screen | `app/trainer/page.tsx:284` links to `/student/coding/{id}`. | Open a trainer problem view: submissions, solve rate, common errors and edit notes. |
| A11 | "Assign mentor" does nothing | The API only writes a `FlagAction(action_type="mentor")` log row (`routers/trainer.py:112`). There is no mentor field and no picker, and nobody is notified. | See C3.6. |
| A12 | "Parent call" does nothing visible | It is a notification (in-app and SMS/email to the parent, plus a thread message), not a phone call. It returns `already` once `parent_notified` is set (the seed sets it), and `held` during quiet hours. | See C3.6. |
| A13 | Mock interview booking "not working" | The backend books correctly (dry-run on the demo DB succeeded). The UI has no calendar, only a list of 3 seeded slots. A second booking of the same round type is refused with 409 "You already have an upcoming round of this type", and that message is easy to miss. | Calendar UI (C2.6). Seed slots across the next 2 weeks. |
| A14 | Delete options missing almost everywhere | Only 10 `DELETE` routes exist in the whole API. None exist for tests, problems, bank items, recordings, certificates, events, MoU reports, colleges, courses or messages. | Phase 1 (shared delete pattern). |
| A15 | College can't reactivate a user | There is a `POST /college/users/{id}/deactivate` and no reactivate route. | Add `reactivate` with an audit event, and clear the `core/active_users` cache. |
| A16 | Draft events can't be edited | The API has `PUT /college/events/{id}` for drafts, but the web page never calls it (0 PUT calls). | Add Edit and Delete for drafts, and Cancel for published events (C4.4). |
| A17 | College certifications show no student names | This is intentional: `GET /college/certifications` returns counts only (rule 8, §5.4). | A decision for you (D1). |

---

## Part B. How these screens work today

### Student

- **Readiness score.** The nightly job (`services/readiness.run_nightly`, 01:30) computes a weighted score:
  - DSA 25%, Track 20%, Aptitude 15%, Communication 15%, Cloud 10%, Future skills 10%, Attendance 5%.
  - Bands: 75 and above is Placement Ready, 60 to 74 is Nearly Ready, below 60 is Needs Support. A college can change the weights and bands.
  - One snapshot is saved each day. "+n this month" compares it with the snapshot a month earlier. "Why this score" shows each component's value × weight.
  - The other dashboard tiles: **Skill progress** comes from lessons completed and problems solved per skill. **Problems solved** counts accepted submissions. **Streak** counts consecutive days with practice. **Badges** are awarded on milestones. **Upcoming** lists published events and tests.
- **My Data & Consent (`/student/privacy`).** DPDP (India's data protection law) screen.
  - It lists each purpose your data is used for, for example sharing your progress with your parent. Required purposes can't be switched off. Optional ones you can grant or withdraw.
  - A student without a date of birth is treated as a minor. A minor's optional purposes need a parent grant, made after an OTP sign-in in the last 15 minutes or on a paper form.
  - You can also ask to download your data or delete it. IREP super admins approve deletions.
- **Class check-in.** The trainer shows a 6-character code in the live class, and the student types it in. It marks attendance for students who joined outside LiveKit or Teams.

### Trainer

- **Attendance.** For each session the trainer sees the roster with Present, Absent, Late or Excused. It is pre-filled from LiveKit or Teams join records and check-in codes, and the trainer confirms. Excused is left out of the attendance %. The nightly job feeds attendance into readiness and the at-risk rules.
- **Mock interviews: "To score".** Booked interviews whose start time has passed and that are not yet submitted.
  - The trainer scores each rubric criterion (1 to max, from the college's `rubric_config`) and adds timestamped notes and feedback.
  - Submitting is final. The student is notified and sees the scores and feedback, and the overall score feeds the Communication and Track parts of readiness.
  - A recording file can be attached and is played back through a signed link.
- **Code reviews.**
  - Student teams push to GitHub. The `/webhooks/github` webhook records each pull request and links it to a sprint-board card.
  - The trainer opens a PR, sees the diff and the AI reviewer's notes (patterns and complexity; it uses Gemini if a key is set, otherwise rules only), leaves inline comments, and chooses Approve or Request changes.
  - Approve moves the card from Code Review to Done. Request changes moves it back to In Progress and notifies the author.
- **At-risk students.**
  - Each night the rules flag a student for low attendance, a falling score, missed tests and similar.
  - The trainer opens a flag and takes an action: Notify parent, Extra Saturday class, Mentor, Note, or Resolve (Resolve needs a note).
- **Message moderation.** Every chat message passes `services/moderation.py` before it is saved:
  - **Block** (never posted): built-in abusive terms; phone numbers and emails (no private contact between students); invite links to WhatsApp or Telegram; and the college's own block terms.
  - **Flag** (posted, but a report goes to the group's moderators, link L18): the college's own flag terms.
  - Any student can also report a message. College admins manage terms in `/college/moderation`.
  - Who may message whom is fixed in `services/chat_policy.can_message`. There is no student-to-student private chat.

### College

- **Branch and batch.** A branch is a department, for example "CSE" or "AI & DS". It has a code, a track and an optional HoD. A batch is a class group inside a branch for one semester and academic year (for example "AI&DS Sem 5 A").
  - Students are imported into a batch, and trainers are mapped to batches.
  - "Promote" moves a batch to the next semester. Readiness and reports can be drilled down by branch, then batch, then student.
- **Placement readiness.** It shows the same score as the student dashboard, as aggregates: band counts and average per branch and batch, the month's trend, and the weakest skill per batch. It drills down to a student's score and band. It never shows trainer notes or chats.
- **Mock drives.** A drive simulates a company's hiring process.
  - The college creates a `drive` event (on Events), sets the company pattern and adds rounds: a test round (a published test with a cut-off %) or an interview round (trainer, time, slots, cut-off score).
  - Publishing turns interview rounds into slots on the trainer's Mock interviews screen, and students book them as usual.
  - Results show each student's round scores and whether they cleared each cut-off. Students who clear every round are shortlisted, and publishing the shortlist notifies them and freezes the results.
- **Timetable: who edits it?** Trainers don't edit the timetable directly. They propose a new session, a reschedule, a cancellation or a substitute from `/trainer/schedule`. `college_admin` approves or rejects on `/college/timetable` (clashes are warned about) and books rooms. The trainer and students are then notified. `placement_officer` can view but not edit.

### Parent

- **RSVP** ("répondez s'il vous plaît") means "please reply". For an event you answer Attending, Maybe or Not attending, plus how many guests. The college sees the counts so it can plan seats.

### Login and invitations

- No one registers themselves. Accounts are created by:
  - IREP staff: a college's first admin, from `/admin/colleges`;
  - the college admin: trainers and staff, from `/college/settings`;
  - student import: students, and parents when consent is given;
  - the super admin: IREP staff.
- In local dev mode the creator sees a temporary password once. In Keycloak mode (production) Keycloak emails a "set your password" link, and the user sets it on Keycloak's page, not a portal page. That's why you didn't find one.
- **Plan:** C6.1.

---

## Part C. Build plan

Every item follows the Definition of done in `CLAUDE.md`: links, outbox and audit events, API tests (happy path, 403 for the wrong role, 404 across colleges, Tamil), Playwright, both locales, `alembic check`, `api-client` regenerated. Changes to auth, Judge0, labs, Graph and `infra/` need a person's review.

### Phase 0: quick fixes (about 2 days, no schema changes)

1. A1 score-history chart.
2. A2 rename to Sprint Board.
3. A3 remove the duplicate button.
4. A5 coding-lab strings.
5. A6 first question.
6. A9 all quick actions (see C3.1).
7. A10 trainer problem link.
8. Trainer reports: remove the "Tamil remark" boxes.
   - Generate `trainer_remark_ta` and `how_to_help_ta` with `services/translation.py` when the report is saved, so parents still get Tamil (rule 9).
9. Trainer messages: remove the "Who can message whom" card.
   - The rule itself stays in `chat_policy.can_message`.
10. Remove "Class check-in" from the student sidebar.
    - Show the code box inside the live session page while the class is live.
    - Keep `/student/checkin` as a deep link for SMS reminders.
11. Dashboard: "Resume practice" goes to the student's last opened problem, not a fixed one. "Upcoming" rows become links.

**Status (27 Nov 2026):** done. Playwright: 172 passed and 3 skipped (opt-in LiveKit), run against a freshly seeded copy of the DB. Also fixed: the dashboard project card now counts only the student's team sprint, not every task in the college. Still on the dashboard for Phase 2: `problems_delta` and `streak_best` are hard-coded for Priya in `services/dashboard.py`.

### Phase 1: delete for every screen (about 4 days)

1. **One shared component:** `components/ui/ConfirmDelete.tsx`.
   - A card that names the item and says "This will be deleted permanently and cannot be undone".
   - Delete is a red button. Cancel has the focus. For colleges and MoUs, you must type the name to confirm.
   - It opens only when the Delete button is pressed.
2. **One API pattern.**
   - Drafts and your own content are deleted for good.
   - Anything other records depend on gets `deleted_at` (a soft delete) so reports and audit stay correct. It is hidden from every list.
   - Each delete calls `record_audit()` and emits an outbox event, and returns 404 across colleges.
   - New FK constraints are named (rule 11).
3. **Where delete goes:**

| Screen | Delete what | Rule |
|---|---|---|
| Trainer · Assessments | IREP bank item (own imports), test, coding problem | Blocked (409) while a test has active attempts. A published item with submissions is soft-deleted. |
| Trainer · Mock interviews | Recording | Deletes the file through `storage` and gives back the MoU storage quota. |
| Student · Certificates | An external certificate in `pending_proof` or `rejected` | Earned and IREP-issued certificates can't be deleted. Download is added (C2.8). |
| College · Events | Draft: delete. Published: cancel. | Cancelling notifies everyone who replied. |
| College · MoU reports | A generated report | Deletes the file. The audit row stays. |
| IREP · Colleges & MoU | A college or an MoU | Super admin only, through the existing deletion-approval flow, and only with no active students. Otherwise "Deactivate college". |
| IREP · Content library | A course or lesson | Unpublish first. Lesson progress is kept for reports. |
| Discussions, Messages | Own message | See C2.10. |

**Status (27 Nov 2026):** done.
- The shared `components/ui/ConfirmDelete.tsx` is used on: trainer assessments (problem or test), interview recordings, student external certificates, college draft events (edit too) and MoU reports, IREP courses and lessons, and colleges and MoUs (super admin; you type the college code to confirm).
- Stored files are removed after commit through the outbox (`storage.delete`, `services/file_cleanup.py`).
- Not in this phase:
  - Message edit and delete move to Phase 2 (C2.10), together with seen ticks.
  - Trainers delete their imported copies of IREP bank items; the IREP master items are not theirs to delete.

### Phase 2: student portal (about 3 weeks)

1. **Dashboard (C2.1).** A1 fix, plus each tile opens its own detail:
   - Problems solved: list by topic.
   - Streak: a calendar heat map.
   - Badges: all badges, including locked ones with how to earn them.
   - Skill progress: what moves each bar.
2. **My courses (C2.2).** Add two features:
   - a thumbnail and intro video on each course (from C6.3);
   - "Continue where you left off": the last opened lesson, plus a next-lesson button inside a lesson.
   - Lessons can hold a video.
3. **Coding lab (C2.3).**
   - **Real execution.** A Judge0 CE `docker compose` for dev (`infra/judge0`, reviewed, never on the DB host) with `JUDGE0_ADAPTER=judge0`. The language list is Python 3, Java, C++ and Node.js, with the right Judge0 language IDs for the installed version.
   - **Starter code** for each language comes from the problem.
   - **Terminal panel.** A **Custom input** (stdin) box and a "Run with my input" button that shows stdout, stderr, compile errors, time and memory, as in VS Code's output panel. It is not a shell (see D3).
   - **Full screen.** A button that hides the problem and AI panels and calls `requestFullscreen()` on the editor area. Esc exits.
   - **Monaco.** Turn on the minimap toggle, bracket colours and format-on-type, add a font-size control, and save the draft per problem and language in `localStorage`.
4. **Practice test (C2.4).**
   - **Network loss:**
     - Answers are saved to `localStorage` on every change.
     - An offline banner shows, and the timer pauses on screen.
     - A heartbeat every 15 s.
     - The server keeps `ends_at` and adds `paused_seconds`. When the heartbeat comes back, `POST /attempts/{id}/resume` moves `ends_at` forward by the measured gap.
     - The extension is capped (for example 10 minutes a test) so it can't be abused, and each pause is logged as a proctor event the trainer can see.
     - Queued answers are sent on reconnect.
   - **Tab switch:**
     - Save immediately when the page is hidden.
     - When the student comes back, a modal says: "You left the test window. Do not open other tabs or apps while writing the test. Switch {n} of {max}".
     - After the college's maximum (default 3), auto-submit with a warning.
     - Copy and paste stay blocked.
5. **Sprint Board (C2.5).**
   - **How it works today.** It is a team Kanban (To do, In progress, Code review, Done) for a capstone project.
     - Cards move by drag or the "Move to" menu, and moves sync live to teammates (WebSocket).
     - A PR on a card shows its review state.
     - Daily stand-ups and change requests belong to the sprint.
     - **But only the seed can create projects and tasks today.**
   - **Add:**
     - Trainer `/trainer/projects`: create a project with title, client, description, goals, repo URL and sprint count; form teams; set sprint goals.
     - Students get a "Project details" panel at the top of the board (description, goals, repo link, sprint dates).
     - Students can add, edit and delete their own tasks: title, tag, points, assignee from the team.
6. **Mock interview (C2.6).**
   - A month and week calendar of open slots. Click a day to see times, then book.
   - "My bookings" with cancel, up to 24 h before.
   - Clear messages for 409 replies.
   - Seed slots for the next 14 days.
7. **AI Study Buddy (C2.7).** Today it has one chat, a topic field, a daily usage cap and a fake adapter.
   - **Finish:**
     - Several saved conversations (list, rename, delete).
     - Pick a course or lesson as context.
     - Answers stream in, with code blocks and a copy button.
     - "Explain my last failed submission" from the coding lab.
     - Practice-question mode.
     - Thumbs up and down.
   - Production uses `STUDY_BUDDY_ADAPTER=anthropic`, and `anthropic` is added to `requirements.txt`. Redaction stays.
8. **Certificates (C2.8).**
   - Download for earned certificates: a PDF with name, course, date and a verification code, generated server-side and stored through `storage`.
   - Download for uploaded proofs.
   - Delete per Phase 1.
9. **Live session (C2.9).** Fix A7, then add the features in C3.9 on the student side: raise hand, chat, reactions, captions toggle and the check-in box. The week view links to each class's own page.
10. **Discussions (C2.10).**
    - Edit your own message within 15 minutes. It shows "edited", and the original is kept for moderation.
    - Delete your own message. It shows "This message was deleted", and moderators can still see it.
    - Seen ticks: ✓ sent, ✓✓ seen by at least one member, with a "Seen by" list for groups. This needs a new `message_reads` table and a WebSocket event.
    - An emoji picker (a small set: 👍 ❤️ 😂 😮 🙏 👏) for both reactions and composing. Today "react" is a single like toggle.
    - The same features go to College messages and Parent messages (C4.7).

**Phase 2 status (27 Nov 2026): the coding lab (C2.3) is done. The rest of Phase 2 is next.**
- **Terminal:** "Run with my input" runs Python, Java (class `Main`), C++ or Node.js on Judge0 and shows stdout, stderr and compiler output. With the fake runner it says "not set up" rather than inventing output.
- **Judging:** LeetCode-style problems are judged through a Python driver (`services/code_harness.py`, `io_mode=function`, migration 0027). Every seeded expected output is proven by `tests/test_code_harness.py`.
- **Editor:** full screen, text size, minimap, reset, and drafts per problem and language.
- **Fixed:**
  - Starter code had been the full answer (all 21 problems, plus a connected-components answer in Java, C++ and JS for every problem). Students now get stubs; the seed repairs existing databases.
  - A failed run used to hide which cases failed.
- **Open:**
  - Judge0 has not been run live: Docker Desktop was not running. See `docs/deploy/JUDGE0.md`.
  - Java, C++ and JS judging for function problems needs per-language drivers.
  - `infra/judge0` needs a person's review.

**Practice test (C2.4), done 28 Nov 2026:**
- A heartbeat every 15 s. When the connection comes back, the server measures the gap from its own last heartbeat and adds it back (at most 10 min per attempt, logged as `connection_paused`). Migration 0028.
- Answers are kept on the device while offline. Reopening after the old end time resumes the same attempt; it used to start a new one and drop the answers.
- Leaving the page saves at once and shows a warning on return. The fourth time, the test is submitted. Switches are counted on the server.
- Trainers see "Left page" and "Paused (min)" per student in test results.

**Sprint Board (C2.5), done 28 Nov 2026:**
- A project details panel (description, goals, members, repo, sprint goal). Students add, edit and delete cards: their own open cards; a card with a pull request stays.
- New Trainer › Projects (`/trainer/projects`): create a team from my batches, edit it, start the next sprint (unfinished cards move along), and delete a project with no work on record. Migration 0029.

**Also done 28 Nov 2026:**
- **Mock interviews (C2.6):** a booking calendar (5-week window; the old first-8-then-drop-booked list hid free slots). A slot you can't book says why. Two weeks of demo slots are seeded.
- **Study Buddy (C2.7):** saved chats (rename, delete), a course to stay on, practice-question mode, thumbs, code blocks with Copy, and "Ask Study Buddy why it failed" from the coding lab. Per-turn context goes in a mid-conversation system message on models that support it, so the cached system prompt is unchanged. Migration 0030. Streaming not done.
- **Certificates (C2.8):** download an earned certificate as a PDF, for the student and the parent.
- **Live (C2.9, part):** a class the trainer ended early is over (no Join); Excused is shown; the dashboard uses the computed status. New Trainer › Live classroom hub (`/trainer/live`) replaces the fixed link. The Teams-style controls are C3.9.
- **Discussions (C2.10):** edit (15 min, moderated, original kept) and delete your own message; seen ticks with a "seen by" list; emoji reactions (one per person) and an emoji picker. Migration 0031.
- **Dashboard (C2.1):** each tile opens what is behind it: problems by topic, a 12-week practice heat map with current and best streak, all badges (locked ones say how to earn them), and how each skill bar grows. `problems_delta` and `streak_best` are now computed; they were hard-coded for Priya.
- **Courses (C2.2, also C6.3):** IREP staff add a course description, thumbnail and intro video, and a video per lesson (scanned, signed links, with delete). Students get cards with thumbnails, "Continue where you left off", videos and "Next lesson". Migration 0032.
- **Phase 2 is complete.**

### Phase 3: trainer portal (about 2 weeks)

1. **Dashboard (C3.1).** Fix every quick action:
   - Mark attendance: today's session.
   - Create test: the assessments page with the form open.
   - Review PRs: the reviews page.
   - Send parent update: the parent tab of messages.
   - Schedule mock: the interviews page with a new slot.
   - Monthly report: the reports page.
   - Add a Playwright test that clicks each one.
   - DSA "Open" fix (A10).
2. **Batches (C3.2).**
   - Show the college name and branch on each batch.
   - Roster: register number, name, attendance %, readiness band, and a link to the student profile.
   - Check the counts against the DB with a test.
3. **Attendance (C3.3).** Show a short "How attendance is recorded" note on the page (Part B), and show each record's source: LiveKit, Teams, check-in or manual.
4. **Assessments (C3.4).** Deletes from Phase 1.
5. **Mock interviews (C3.5).**
   - An in-page "How scoring works" note.
   - Rubric criteria shown with their descriptions.
   - Delete recording (Phase 1).
6. **At-risk (C3.6).**
   - Rename "Parent call" to **"Notify parent"**. Show its outcome: sent, held until 08:00 (quiet hours), already notified on a date, or no parent linked.
   - Add **"Log phone call"**: outcome and notes, so a real call can be recorded.
   - **Assign mentor:**
     - Add `at_risk_flags.mentor_user_id` (migration).
     - A picker of the college's trainers and staff.
     - The mentor and the student are notified, and the mentor sees the student under "My mentees".
     - Change or remove it later.
7. **Reports (C3.7).** Phase 0 item 8.
8. **Messages (C3.8).** Remove the card (Phase 0). Add the WhatsApp-style features (C2.10).
9. **Live classroom (C3.9).** LiveKit adapter in the portal.
   - `/trainer/live` hub (A8): end a class, then start the next one or open "Ended" classes with attendance and the recording.
   - **Stop sharing** a lab: the `DELETE /trainer/sessions/{id}/spectate` API and `SpectateBar` already exist. Add the button to the live page's toolbar.
   - **Teams-like controls:**
     - participant list with mute, remove and lower hand;
     - raise hand queue;
     - chat with pinned messages;
     - reactions;
     - screen share;
     - spotlight;
     - lobby and admit;
     - mute all;
     - polls and Q&A (both exist);
     - breakout rooms (LiveKit rooms per group);
     - recording start and stop (needs LiveKit Egress: not done, needs review);
     - live attendance count;
     - end for all, or leave and let the class continue.

**Phase 3 status (28 Nov 2026): done, except the three live-class items listed at the end.**

- **Judge0 (review prep).** `docs/deploy/JUDGE0_REVIEW.md` is the checklist for the person who reviews `infra/judge0`. Container limits (2 GB, 2 CPUs, 512 processes, log rotation) are set. The HTTP timeout follows the wall-time limit. The coding terminal allows one run every 2 s and 60 per hour per student (`code_runs` in the usage ledger). Not run against a live Judge0 yet: Docker was not running here.
- **Dashboard and batches (C3.1, C3.2).** Quick actions were fixed in Phase 0. Batches and the roster show the college and branch, and the roster count is checked against the DB.
- **How-it-works notes (C3.3, C3.5).** Attendance, mock-interview scoring, code review, at-risk and moderation pages each have a "How it works" panel (`components/ui/HowItWorks.tsx`, `howto.*` keys). Attendance shows each mark's source. The interview scoring form shows what each rubric line looks for, the 1–5 scale and the readiness bars.
- **At-risk (C3.6).**
  - "Notify parent" shows when the parent was told. It can be sent again after 3 days; it used to be once per flag, ever. A held quiet-hours notice is skipped if one went out after it was requested.
  - "Log phone call" needs an outcome: reached, no answer, or asked to call back.
  - Mentor: migration 0034 adds `mentor_user_id`. The picker lists the college's trainers. The mentor and the student are told; the change goes in the flag history and the audit log. The mentor sees the student under "My mentees" and can open the flag even when it is not their batch. A mentor can be changed or removed.
  - Tests: `tests/test_at_risk_mentor.py` and the screen 14 Playwright spec.
- **Live classroom (C3.9).** Migration 0033 adds the controls:
  - in-class chat with pins;
  - a raise-hand queue (the trainer can lower hands);
  - reactions and spotlight;
  - mute all;
  - a head count;
  - "End for all" behind a confirmation, plus "Leave (class continues)";
  - the lab link opens in a new tab.

  Participant mute and remove, screen share, polls, Q&A and stop sharing were already there. Tests: `tests/test_live_controls.py` and the screen 07 Playwright spec.
- **Not done:**
  - lobby admit (a waiting room the trainer admits from);
  - breakout rooms;
  - recording start and stop, which needs LiveKit Egress and a person's review.

### Phase 4: college, parent, IREP (about 1.5 weeks)

1. **College.**
   - In-page explainers for Branch, Readiness, Drives and Timetable (Part B).
   - Certifications per D1.
   - Events: edit, delete and cancel (A16).
   - MoU report delete.
   - Settings: reactivate (A15).
   - Messages: WhatsApp-style history, edit and delete (C2.10).
2. **Parent RSVP.**
   - After choosing, show a confirmation card: "You replied: Attending · 2 guests". It has a **Change reply** button, allowed until the event starts or until an RSVP deadline set by the college.
   - Changing to "Not attending" asks for confirmation and an optional reason.
   - The college's counts update.
3. **IREP staff.**
   - College & MoU delete (Phase 1).
   - Content library: upload a course thumbnail (image) and an intro video, plus a video per lesson. Through `storage`, with the antivirus scan, counted against quota.
   - Course delete.
   - Content library glitches: you mentioned glitches but didn't describe them. Please list the steps or send a screenshot so they can be reproduced.

**Phase 4 status (28 Nov 2026): done, except the content library glitches (not described yet).**

- **College explainers.** Branches and batches, placement readiness, mock drives and the timetable each have a "How it works" panel.
- **Certifications (D1).**
  - New route: `GET /college/certifications/holders`, with search, batch and issuer filters, 50 rows per page.
  - It lists name, register number, batch, certificate, issuer and date. It never lists proof files or decision notes.
  - Each read is audited (`college.certificate_holders_read`).
  - `docs/INTERCONNECT.md` §5.4 and `docs/PERMISSIONS.md` are updated.
- **Events.**
  - Draft edit and delete were done in Phase 1; cancel already existed.
  - The college can set a reply deadline (migration 0035, `events.rsvp_deadline`).
  - The event detail lists why parents can't come, without names.
- **Settings: reactivate (A15).** This was already in place. `POST /college/users/{id}/reactivate` is audited, and the user cache clears itself on commit (`core/active_users`).
- **Messages (trainer, parent, college threads).**
  - Migration 0036 adds `edited_at`, `deleted_at` and `first_text`.
  - The sender can edit within 15 minutes, or delete for everyone after a confirmation. Both sides then see "This message was deleted".
  - The first text is kept for audit, and edits and deletes are audited.
  - Sent and seen ticks show in all three message screens (`components/messages/ThreadMessageBody.tsx`).
- **Parent RSVP.**
  - After replying, the card shows "You replied: Attending · 2 people" with **Change reply**.
  - A reply can be changed until the deadline, or until the event starts if there is none; after that the API returns 409.
  - "Can't come" asks for confirmation and takes an optional reason. The college counts update.
- **IREP staff.** College and MoU delete and course delete were done in Phase 1; course thumbnails, intro videos and lesson videos in Phase 2.
- **Tests.** `tests/test_phase4_college_parent.py`, `tests/test_thread_edit_delete.py`, `e2e/phase4-college-parent.spec.ts`, and the extended events spec.

### Phase 5: login and invitations (about 3 days, needs a person's review)

1. **Invitations.**
   - Local mode: add an invite link with a one-time token (48 h), plus a portal page `/auth/set-password` that sets the password and signs the user in. This replaces showing a temporary password.
   - Keycloak mode: Keycloak's own email link stays.
   - Both modes get an "Invitations" list on `/college/settings` and `/admin/colleges` showing who was invited, whether they accepted, a Resend button and a Revoke button.

**Phase 5 status (28 Nov 2026): built; needs a person's review (auth).**

- **No more temporary passwords.** Every account someone creates for someone else gets an invitation (migration 0037, `invitations`, `services/invitations.py`):
  - a college's first admin (45);
  - college admins and placement officers (02);
  - IREP staff (super admin).
- **Local mode, development (`NOTIFY_ADAPTER=fake`).**
  - The creator sees a one-time link once: `/auth/set-password#token=…`. It works for 48 hours.
  - The token sits in the fragment, so it never reaches server logs, and the page removes it from the address bar.
  - Only its SHA-256 is stored.
- **Local mode, live email.** The outbox handler `invite.send` mints the token when it sends the email. So the token is never in an outbox payload or a notification row, and the creator's response has no link.
- **Keycloak mode.**
  - Keycloak's own email link stays, and Resend asks Keycloak to send it again.
  - `/auth/invitations/*` return 410.
  - The portal cannot see when someone accepts in Keycloak, so those rows stay "Waiting".
- **Set-password page.**
  - Rules: at least 10 characters, a letter and a number, and not the email name.
  - Setting the password signs the person in. The link works once; an expired link says so.
  - Failed lookups count toward the per-IP sign-in limit.
- **Invitations list.** On `/college/settings` and `/admin/colleges/[id]`: status (Waiting, Accepted, Expired, Revoked), who invited them, Resend (a new link; the old one stops working) and Revoke (asks first; the unused account is switched off). Each step is audited (`invitation.*`).
- **Tests.** `tests/test_invitations.py`, plus the screen 02, 03 and 45 Playwright specs, which now go through the set-password page.
- **For the reviewer.**
  - Password policy and the 48-hour validity (`INVITE_HOURS`).
  - In live email mode, if the commit fails after the email was sent, the next retry sends a new link and the first one will not work.
  - Keycloak acceptance tracking is not done.

---

## Part D. Decisions needed

**Answers (27 Nov 2026):** D1 yes, show student names on College › Certifications. D2 (later the same day) yes: drafts and a person's own items are truly deleted; anything students or records used is hidden but kept. D3 yes: a stdin box with output, no shell. D4 and D5 not answered yet.

- **D1. Student names on College › Certifications.** Today the college sees counts only, by design (rule 8, §5.4: aggregates only). Showing names (not notes or files) is reasonable for placement, but it changes the visibility rule and `docs/PERMISSIONS.md`.
- **D2. "Delete permanently".** The proposal is a hard delete for drafts and your own content, and a soft delete (hidden everywhere, kept for audit and reports) for anything other records depend on. A true hard delete of a college or of students needs the DPDP deletion-approval flow.
- **D3. Coding-lab terminal.** The proposal is a stdin box with output, the same thing VS Code's Run button shows. A real interactive shell (a PTY over WebSocket into a sandbox) is a lab-grade feature: it needs the labs infrastructure and a security review.
- **D4. Live classes: LiveKit or Teams?** Features like breakout rooms, hand raise and stop-sharing can only be built in the portal's LiveKit room. With the Teams adapter the class runs inside Microsoft Teams, which already has those features, and the portal only creates the meeting and imports attendance. The proposal is to build them on LiveKit and keep Teams as the college's option.
- **D5. The AI code reviewer uses Gemini** (`services/ai_reviewer_service.py`), while Study Buddy uses Claude. Should both use the same provider?

## Suggested order

Phase 0, then 1, 2, 3, 4 and 5. Phase 0 and Phase 1 can ship this week on their own. D1 to D4 block parts of Phases 2 to 4 only.
