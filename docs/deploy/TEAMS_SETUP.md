# Microsoft Teams setup for IREP live classes

**For:** the Microsoft 365 / Entra ID administrator of the college (or of IREP, if classes are organised from IREP's tenant).
**Time needed:** about 1 hour, plus up to 30 minutes for policies to take effect.
**What you hand back:** the four values in step 7.

## What the portal does in your tenant

The IREP portal schedules live classes as **Outlook calendar events with a Teams meeting** on an organizer's calendar. After each class it reads that meeting's **attendance report**. It uses an app registration with application permissions (no signed-in user), from a background worker.

| The portal... | Graph call | Permission (Application) |
|---|---|---|
| creates, moves and cancels the class event on the organizer's calendar | `POST/PATCH /users/{organizer}/events`, `POST .../events/{id}/cancel` | `Calendars.ReadWrite` |
| finds the Teams meeting behind the event | `GET /users/{organizer}/onlineMeetings?$filter=JoinWebUrl eq '...'` | `OnlineMeetings.Read.All` |
| imports who attended and for how long | `GET /users/{organizer}/onlineMeetings/{id}/attendanceReports/...` | `OnlineMeetingArtifact.Read.All` |

The portal does **not**:
- read mail or chats
- create users
- send messages as anyone
- download recordings

It only touches the calendars of the organizer accounts you allow (step 5).

---

## 1. Register the app

1. Go to **Microsoft Entra admin center → Identity → Applications → App registrations → New registration**.
2. Fill in:
   - **Name:** `IREP Portal – Live classes`
   - **Supported account types:** *Accounts in this organizational directory only* (single tenant)
   - **Redirect URI:** leave empty
3. Select **Register**.
4. On the overview page, copy:
   - **Application (client) ID**: this is `GRAPH_CLIENT_ID`
   - **Directory (tenant) ID**: this is `GRAPH_TENANT_ID`

## 2. Create a client secret

1. In the app, open **Certificates & secrets → Client secrets → New client secret**.
2. Set the **Description** to `IREP portal` and the **Expires** to 12 months.
3. Copy the secret's **Value** now: it is shown only once. This is `GRAPH_CLIENT_SECRET`. Do not copy the "Secret ID".
4. Note the expiry date. See "Secret rotation" at the end.

## 3. Add the three permissions and grant admin consent

1. In the app, open **API permissions → Add a permission → Microsoft Graph → Application permissions**.
2. Add:
   - `Calendars.ReadWrite`
   - `OnlineMeetings.Read.All`
   - `OnlineMeetingArtifact.Read.All`
3. Select **Grant admin consent for <your organisation>** and confirm.
4. All three rows should show a green tick, "Granted for ...".
5. Remove the default delegated `User.Read` permission if you like. The portal does not use it.

> **If you will scope calendar access with RBAC for Applications (step 5, option A):** do **not** grant `Calendars.ReadWrite` here. Grant only the two meeting permissions, and give calendar access through Exchange in step 5. An Entra-consented `Calendars.ReadWrite` covers every mailbox in the tenant, and Exchange scoping cannot narrow it.

## 4. Allow the app to read the organizers' meetings (Teams application access policy)

App-only access to online meetings and attendance reports needs a Teams **application access policy**. Without it, every meeting call returns 403. In PowerShell:

```powershell
Install-Module MicrosoftTeams -Scope CurrentUser      # once
Connect-MicrosoftTeams

New-CsApplicationAccessPolicy -Identity "IREP-Portal-Meetings" `
  -AppIds "<GRAPH_CLIENT_ID>" `
  -Description "IREP portal: read class meetings and attendance reports"

# grant it to each organizer account (step 6); repeat per trainer who organises with their own account
Grant-CsApplicationAccessPolicy -PolicyName "IREP-Portal-Meetings" -Identity "irep-classes@college.edu"
Grant-CsApplicationAccessPolicy -PolicyName "IREP-Portal-Meetings" -Identity "trainer.one@college.edu"
```

- You can grant it to the whole tenant with `Grant-CsApplicationAccessPolicy -PolicyName "IREP-Portal-Meetings" -Global`. Per-organizer grants are tighter and recommended.
- The policy can take **up to 30 minutes** to take effect.

## 5. Limit calendar access to the organizer accounts (Exchange Online)

Without this step, `Calendars.ReadWrite` lets the app read and write **every** mailbox calendar in the tenant. Create a mail-enabled security group, for example `irep-organizers@college.edu`, containing only the organizer accounts from step 6. Then choose **one** option.

**Option A: RBAC for Applications (Microsoft's current recommendation).** Requires that `Calendars.ReadWrite` was **not** consented in step 3.

```powershell
Install-Module ExchangeOnlineManagement -Scope CurrentUser   # once
Connect-ExchangeOnline

# The service principal's Object ID: Entra admin center → Enterprise applications → "IREP Portal – Live classes" → Object ID
New-ServicePrincipal -AppId "<GRAPH_CLIENT_ID>" -ObjectId "<enterprise app Object ID>" -DisplayName "IREP Portal – Live classes"

$dn = (Get-Recipient "irep-organizers@college.edu").DistinguishedName
New-ManagementScope -Name "IREP organizers" -RecipientRestrictionFilter "MemberOfGroup -eq '$dn'"
New-ManagementRoleAssignment -App "<GRAPH_CLIENT_ID>" -Role "Application Calendars.ReadWrite" -CustomResourceScope "IREP organizers"

# check: True for an organizer, False for anyone else
Test-ServicePrincipalAuthorization -Identity "<GRAPH_CLIENT_ID>" -Resource "irep-classes@college.edu"
Test-ServicePrincipalAuthorization -Identity "<GRAPH_CLIENT_ID>" -Resource "principal@college.edu"
```

**Option B: Application access policy (older, still supported).** Keep `Calendars.ReadWrite` consented in step 3.

```powershell
Connect-ExchangeOnline
New-ApplicationAccessPolicy -AppId "<GRAPH_CLIENT_ID>" -PolicyScopeGroupId "irep-organizers@college.edu" `
  -AccessRight RestrictAccess -Description "IREP portal: organizer calendars only"
Test-ApplicationAccessPolicy -Identity "irep-classes@college.edu" -AppId "<GRAPH_CLIENT_ID>"   # AccessCheckResult: Granted
Test-ApplicationAccessPolicy -Identity "principal@college.edu"     -AppId "<GRAPH_CLIENT_ID>"   # AccessCheckResult: Denied
```

Changes can take up to 30 minutes (option A: up to 2 hours) to apply.

## 6. Organizer accounts, licences and meeting settings

**Organizer accounts.** Classes are created on an organizer's calendar, and that account becomes the meeting organizer.
- **Default organizer:** one shared account, for example `irep-classes@college.edu`. This is `TEAMS_DEFAULT_ORGANIZER`. The portal uses it for every trainer who has no account of their own.
- **Optional, per trainer:** a trainer with their own licensed account can organise their own classes. They then see the classes in their own Outlook and Teams calendar. IREP links each one with `ops/set_teams_upn.py`. Send IREP the list of trainer email → Teams sign-in name.
- **Each organizer account needs:**
  - a licence that includes **Teams and an Exchange Online mailbox**. For education tenants, Microsoft 365 A1 for faculty (free) is enough for scheduling and attendance reports.
  - to be in the access policy (step 4) and the organizer group (step 5).

**Meeting policy.** Go to **Teams admin center → Meetings → Meeting policies**, open the policy assigned to the organizers (or Global), and set:

| Setting | Value | Why |
|---|---|---|
| Attendance and engagement report | **On** | The portal imports attendance from it. Without it, attendance must be entered by hand. |
| Attendee information (in the report) | Show everything | Names and emails let the portal match students |
| Meeting recording | **On** | So trainers can record classes |
| Recordings automatically expire | Your choice, e.g. 120 days | Storage use in OneDrive |
| Who can bypass the lobby | People in my org and guests (or Everyone, if students join anonymously) | Students are not held in the lobby |
| Anonymous users can join a meeting | **On** if students do not have accounts in your tenant | Students join from the "Join in Teams" button |

**How the portal matches students in the attendance report:**
1. **By email**, for students who sign in to Teams with the email registered in the portal.
2. **By display name**, for students who join anonymously. They must type their name as **`IREP-<register number> <Name>`**, for example `IREP-21AD045 Priya R`. The portal shows students this rule next to the Join button.
3. Anyone else is listed for the trainer to confirm by hand.

## 7. Values to send to IREP

Send these through a password manager or another secure channel, **never by plain email or chat**:

| Value | Where it goes |
|---|---|
| Directory (tenant) ID | `GRAPH_TENANT_ID` |
| Application (client) ID | `GRAPH_CLIENT_ID` |
| Client secret **value** + expiry date | `GRAPH_CLIENT_SECRET` |
| Default organizer account, e.g. `irep-classes@college.edu` | `TEAMS_DEFAULT_ORGANIZER` |
| (optional) trainer email → Teams sign-in name list | `ops/set_teams_upn.py` |

IREP then runs `ops/teams_check.py`, which proves the token, calendar access and meeting access without creating anything (DEPLOY.md step 9).

## 8. End-to-end test (do this together, before the first real class)

You need:
- one trainer
- one student who signs in to Teams with their portal email
- one student who joins anonymously as `IREP-<register no> <Name>`

| # | Step | Expected result |
|---|---|---|
| 1 | IREP runs `docker compose run --rm api python ops/teams_check.py` | `ok token`, `ok calendar`, `ok meetings` |
| 2 | In the portal, schedule a 15-minute test class for the trainer's batch starting in about 20 minutes | Within a minute or two, the event appears in the organizer's Outlook and Teams calendar, titled with the class name, with a Teams link |
| 3 | Reschedule it by 5 minutes in the portal | The calendar event moves |
| 4 | Students open the class in the portal | A **Join in Teams** button opens the same meeting |
| 5 | Everyone joins; the trainer starts **recording**; stay at least 12 of the 15 minutes; the trainer ends the meeting for everyone | The recording appears in the meeting chat and the organizer's OneDrive, and the students in the meeting can open it |
| 6 | Wait `TEAMS_REPORT_DELAY_SECONDS` (default 15 minutes) after the scheduled end, plus up to 15 minutes for the next background run. A college admin can trigger it earlier with `POST /api/v1/admin/jobs/teams`. | The class attendance shows both students **Present** (75% rule): one matched by email, one by display name. Anyone unmatched waits for the trainer to confirm. |
| 7 | Schedule another class and cancel it in the portal | The calendar event is cancelled and attendees get the cancellation |

**If a step fails:**
- **Step 1, `token` fails:** wrong tenant or client ID, the secret ID was copied instead of the value, or the secret has expired.
- **Step 1 or 2, `calendar` fails (403 / ErrorAccessDenied):** consent is missing (step 3), the organizer is outside the scope (step 5), or the account has no Exchange mailbox.
- **Step 1, `meetings` fails, or step 6 shows nothing:** the Teams access policy is not granted to this organizer, or it is less than 30 minutes old (step 4). Also check that `OnlineMeetingArtifact.Read.All` is consented and the attendance report is on in the meeting policy (step 6).
- **The IREP log shows the exact Graph error:** `docker compose logs worker | grep Graph`. The portal retries failed calls automatically with back-off.

**Recordings:** in this pilot, Teams recordings stay in Teams and OneDrive and are shared through the meeting. The portal does not copy them (no `Files.Read.All` or `OnlineMeetingRecording.Read.All` permission is requested). Importing them into the portal's recordings list is a later addition, and it would need one more permission and your consent then.

## Secret rotation

Client secrets expire, and when the secret expires, classes stop being created. **One month before** the expiry date:
1. Create a new secret (step 2) and send its value to IREP.
2. IREP updates `GRAPH_CLIENT_SECRET` and restarts the worker. Then IREP runs `ops/teams_check.py`.
3. Delete the old secret once the check passes.

## Removing access

To stop the portal touching your tenant:
1. Delete the app registration, or remove its admin consent.
2. Remove the policies:
   - `Remove-CsApplicationAccessPolicy -Identity "IREP-Portal-Meetings"`
   - in Exchange, `Remove-ManagementRoleAssignment` or `Remove-ApplicationAccessPolicy`

Events that were already created stay on the organizers' calendars.
