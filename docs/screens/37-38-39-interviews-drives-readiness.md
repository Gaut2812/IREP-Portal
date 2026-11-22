# Screens 37, 38 and 39 (S15): mock interviews, mock drives, placement readiness

Sources: the screen map's rows 37 to 39 ("Slots, live scoring, feedback"; "Company-pattern drives with test and interview rounds"; "Drill-down by branch, batch and student"), `docs/INTERCONNECT.md` §4 (L16, L17, L29, L34, L35), and §5.4 (who sees what).

## 37 Mock interviews (trainer) at `/trainer/interviews`

**Who:** trainers, for their own slots and interviews only. Other trainers' rows are `404`.

**What the trainer does:**
- **Slots.** Open slots for one of their batches: technical, HR or AI coding round, start time, and 15–120 minutes. They see who booked each slot (from 36). They can cancel a slot that has not started: a booked slot cancels the interview and notifies the student.
- **To score.** Booked interviews whose start time has passed and that are not submitted yet. The trainer scores every rubric criterion (`rubric_config`, 1 to max), adds timestamped notes and writes feedback in English and optionally Tamil, then submits. Submitting is final: the student is notified and sees the scores on 36.
- **Recording.** The trainer can attach the recording file. It is stored through `services/storage` under `recordings/interviews/<id>.<ext>`, counted against the MoU storage quota (L36), and played on 36 through a signed link.
- **Drive rounds.** Slots created by a mock drive (38) are marked with the drive's name (L17).

**Links:**
- **L16 (36 ↔ 37):** slots go down to 36; a booking comes up to 37; rubric scores, feedback, notes and the recording go down to 36 on submit.
- **L17 (38 → 37):** interview rounds of a published drive become slots for the round's trainer.

**Events (§5.3):**

| Event | Audit | Notify | Recipient |
| --- | --- | --- | --- |
| `interview.slot_cancelled` | yes | yes (if booked) | student |
| `interview.submit` | yes | yes | student |
| `interview.recording_added` | yes | no | — |

## 38 Mock drives (college) at `/college/drives`

**Who:** `college_admin` and `placement_officer`, for their own college only.

**L29 (42 → 38):** a mock drive is an event type. Creating an event of kind `drive` on 42 also creates its drive here, as a draft. Publishing the event on 42 announces it to students and parents, as for every event.

**On the drive the college:**
- **Sets the company pattern**, for example "Service company: aptitude + technical + HR" or "Product company: coding + 2 technical".
- **Adds rounds in order.** Each round is one of:
  - a **test** round: a published practice test from 22/46, with a cut-off percentage;
  - an **interview** round: a round type, a trainer of the drive's batch, a start time, a length, how many slots, and a cut-off score out of the rubric maximum.
- **Publishes the rounds (L17).** Each interview round creates its slots on the trainer's 37, marked with the drive. Students of the drive's batch book them on 36 as usual. The test round's test is assigned to the batch. Trainers and students are notified.
- **Sees results per student:**
  - test score, as a % of the latest submitted attempt
  - interview overall score
  - whether each cut-off was cleared, and whether all rounds were cleared (shortlisted)

  Scores only: trainer notes and feedback are never shown to the college (§5.4, L35).
- **Publishes the shortlist.** Shortlisted students are notified. Results are frozen.

**Events (§5.3):**

| Event | Audit | Notify | Recipient |
| --- | --- | --- | --- |
| `drive.created` | yes | no | — |
| `drive.round_added` / `drive.round_removed` | yes | no | — |
| `drive.published` | yes | yes | round trainers, the batch's students |
| `drive.shortlist_published` | yes | yes | shortlisted students |

## 39 Placement readiness (college) at `/college/readiness`

**Who:** `college_admin` and `placement_officer`, for their own college.

**L34 and L35 rules:** it shows the one readiness score and band from the readiness engine (L34), as aggregates and bands (L35, §5.4). It never shows trainer notes or chats.

**What it shows:**
- **College:** average score, band counts (Placement Ready, Nearly Ready, Needs Support), and the average monthly change.
- **By branch, then batch:** the same figures, plus the average of each readiness component (from the latest snapshots).
- **By student, within a batch:** score, band and monthly change. Filter by band. No component breakdown per student, notes or chats.

**Events:** reads only; no notifications. Aggregates are not audited, as for 19.

## Definition of done

- L16, L17 and L29 are `active`, with tagged pytest and Playwright tests.
- API tests cover: happy paths, the wrong role (403), another college (404), and Tamil labels.
- Playwright specs for 37, 38 and 39 cover the happy path, the Tamil toggle and the role guard.
