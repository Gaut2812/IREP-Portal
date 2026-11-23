# S16: Billing (screen 47, full) and DPDP consent for minors

Sources:
- screen map row 47 ("Quotas for lab hours, AI calls and storage; credits; invoices")
- flow "Usage, quotas and billing", step 4: "Metered, credited, invoiced"
- `docs/screens/48-audit-and-consent.md` open points: "DOB capture and the identity-bound flow in S16"
- `docs/PERMISSIONS.md`: billing is super-admin only

## Billing

**Who:**
- **The super admin** generates, issues, settles and voids invoices, and adds credits (`SUPER`).
- **College admins** see their own college's issued invoices and credit balance, and download the PDFs.
- **IREP staff and everyone else** get `403`.

**Monthly invoice per college** (`period` = `YYYY-MM`). Amounts are kept in paise (integers).

| Line | Quantity | Rate |
| --- | --- | --- |
| Seats | students enrolled when the invoice is generated | MoU `fee_per_student_inr` ÷ 12 (the fee is per academic year) |
| Lab hours over quota | the college's lab minutes this month over its quota (L36), in hours, rounded up | MoU `lab_overage_inr_per_hour` (0 = not charged) |
| Recording storage over quota | MB over the MoU storage quota, in GB, rounded up | MoU `storage_overage_inr_per_gb` (0 = not charged) |
| Usage this month (information) | lab minutes, AI calls and recording MB used against quota | no charge; shows the lab use on the invoice |
| Credit | unused credits of the college, up to the subtotal | negative |
| GST | `BILLING_GST_PCT` (18 %) of subtotal minus credits | |

**Life cycle:** `draft → issued → paid`, or `void`.
- **Draft:** generating a period creates or refreshes that period's draft for every active college with an active MoU. Issued invoices are never touched.
- **Issue:**
  - assigns the next number in the financial year (April–March), e.g. `IREP/2026-27/0001`
  - fixes the lines
  - stores the PDF
  - sets `due_on` to 30 days later
  - notifies the college admins (`invoice.issued`)
- **Paid:** needs a payment reference (UTR or cheque number).
- **Void:** needs a reason. Credits it used are released.

**Audit:** `invoice.generated`, `invoice.issued`, `invoice.paid`, `invoice.voided`, `billing.credit_added`. Every super-admin request is also audited as `super_admin.request`.

**Routes:**
- `/admin/billing` (super admin)
- `/college/billing` (college admin)

## DPDP: date of birth, minors and verifiable parental consent

The DPDP Act, section 9, requires verifiable consent of a parent before a child's (under 18) personal data is processed. The DPDP Rules, rule 10, add that the consent must come from an identifiable adult.

- **Date of birth:**
  - `students.date_of_birth` is captured in the student import (`dob` column, `YYYY-MM-DD`)
  - the college can set it on 03 (`PUT /college/students/{id}/dob`)
  - `is_minor` = under 18 today
- **Notices are versioned.** Each optional purpose has a notice in English and Tamil (`services/consent.NOTICES`). Every consent record stores the `notice_version` the person saw.
- **Identity-bound parental consent:**
  - For a **minor**, the optional purposes (`public_portfolio`, `ai_hints`, `recordings`, `sms_alerts`) count as granted only when a **linked parent** granted them.
  - The parent must do so in a session that began with the parent's mobile-number OTP, at most 15 minutes earlier. The record stores how the identity was verified: `method=otp_parent`, the parent's user id, and the OTP sign-in time.
  - A college upload of a signed paper form (`paper_form_upload`, with its reference) also counts.
- **A minor asking:** recording a consent for themselves creates a **request** (`status=requested`). The linked parents are notified, in English and Tamil, and approve or decline on the parent's consent page (`/parent/consent`). Adults decide for themselves as before.
- **Where the consent is enforced** for minors:
  - publishing a public portfolio (32) needs `public_portfolio`
  - asking the AI Study Buddy (25) needs `ai_hints`

  Without it the answer is `403` with `code=parental_consent_required` and an English/Tamil message.
- **Self-service requests:** a parent (for a linked child) or an adult student (for themselves) can ask for a copy of the data or its deletion. The request goes into the same queue as the college's requests (48). It has the 30-day target, and the college and IREP staff are notified.

**Events:** `consent.requested` (notify parents), `consent.recorded` (as before, now with `notice_version`), `data_request.created` (self-service).

## Definition of done

- API tests cover:
  - the happy path for each role
  - 403 for the wrong role
  - 404 across colleges
  - Tamil messages
  - the money arithmetic (paise, GST, credits, rounding)
  - invoice numbering across a financial year
  - the minor and adult consent paths
  - the 15-minute identity window
- A Playwright spec covers billing (super admin and college), the parent consent page, the Tamil toggle and the role guards.
- `docs/PERMISSIONS.md`, README and `openapi.json` are updated.
