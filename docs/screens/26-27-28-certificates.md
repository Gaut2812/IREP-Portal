# Screens 26 · Certificates (student), 27 · Certificates (parent), 28 · Certifications (college), and the 43 proof decision

**Sprint:** S11. **Status:** all feature-only.
**Routes:** `/student/certificates` (26), `/parent/certificates` (27), `/college/certifications` (28), certificate items on `/trainer/approvals` (43).

## Links

| Link | Direction | What moves | Status |
| --- | --- | --- | --- |
| L10 | 26 ↔ 43 | External certificate proof up; the trainer's decision down | active |
| L32 | 26 → 27 | Read-only copy of verified certificates | active |
| L35 | all data → 28 | Counts, proof status and vouchers as aggregates | active (existing link, tested here too) |

**Release rule 5.1.4:** an external certificate shows as verified only after the trainer approves the proof.

## Flow

1. The student adds an external certificate (name, issuer, date, optional credential id) with its proof, or uploads the result for a scheduled exam (an exam can carry an IREP-funded voucher).
   - Files must be a real PDF, PNG or JPEG (checked by their first bytes, not the name or type the browser sends) and at most 5 MB.
   - Files are stored through `services/storage.py` under the student's college and are never public.
   - Audited as `certificate_proof.submitted`; the student's batch trainers are notified.
2. The certificate is `pending_proof` and appears on 43 for the student's batch trainers (another batch's trainer gets 404). Opening the proof is a sensitive read and is audited (`certificate_proof.viewed`).
3. The trainer approves or rejects; a rejection needs a note.
   - Audited as `certificate_proof.decided`.
   - On approval the certificate becomes `earned` with a verify code. The student and the linked parents are notified (L32).
   - On rejection the student sees the note and can upload a new proof.
4. **27** shows only `earned` certificates and scheduled exams, without proof files, behind the parent-data consent (like 15 and 16).
5. **28** shows totals, earned by month, top issuers, earned by batch, the proof queue's status, the share of students with a certificate, and vouchers used out of issued. It has no names, files, credential ids or notes.

## Endpoints

| Method | Path | Role |
| --- | --- | --- |
| GET, POST | `/student/certificates` (POST is multipart: title, issuer, issued_on, credential_id, file) | student |
| POST | `/student/certificates/{id}/proof`; GET the same path (own file) | student |
| GET | `/trainer/certificates/{id}/proof` | trainer, own batches (audited) |
| POST | `/trainer/approvals/certificates/{id}` `{decision, note}` | trainer, own batches |
| GET | `/trainer/approvals` (now includes `certificate` items) | trainer |
| GET | `/parent/certificates?child_id=&lang=` | parent |
| GET | `/college/certifications?months=` | college_admin, placement_officer |

## Acceptance tests

- **API:**
  - L10 and L32: pending is invisible to the parent; the queue shows the proof; the trainer views it (audited); approval makes the certificate verified for the parent (Tamil label, no proof); notifications and audits are written.
  - A rejection needs a note and the student can resubmit; scheduled-exam proof with a voucher.
  - Guards: file type checked by its bytes, size limit, no future dates, roles, other batch and other college, parent consent.
  - L35: the college sees counts only.
- **E2E:** the student uploads, the trainer approves on 43, and the parent sees the certificate; the college tiles show no names; Tamil; role guard.
