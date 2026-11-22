# Deploying the IREP pilot on one Ubuntu server

This guide takes a fresh Ubuntu 24.04 server to a running portal at `https://portal.<your-domain>`, with sign-in at `https://id.<your-domain>`, nightly backups and Teams live classes. Follow it top to bottom. Each step ends with a check, so you know it worked before you move on.

**What runs on the server** (all in Docker, from `infra/prod/docker-compose.yml`):

| Service | What it does | Reachable from the internet? |
|---|---|---|
| `caddy` | HTTPS for both domains (Let's Encrypt, renewed automatically), routes traffic | Yes: ports 80 and 443 only |
| `web` | The Next.js portal | No, through Caddy |
| `api` | The FastAPI backend (`/api/v1`, signed `/media` links) | No, through Caddy |
| `worker` | Sends email, SMS and Teams calls from the outbox | No |
| `beat` | Timers: outbox poll, Teams follow-ups, nightly readiness at 01:30 IST | No |
| `keycloak` | Sign-in for students, trainers, college staff and IREP staff | No, through Caddy |
| `postgres` | Two databases: `irep` (the portal) and `keycloak` | No |
| `valkey` | Message broker for the worker | No |
| `migrate` | Runs `alembic upgrade head`, then exits | No |

**What the pilot leaves out on purpose.** The Coding Lab (Judge0), Virtual Labs and Cyber Range, and the AI Study Buddy keep their demo adapters (`ALLOW_DEMO_ADAPTERS=judge0,labs,study_buddy`). Those screens still open, but code is graded by the built-in demo grader, labs run in the browser only, and the Study Buddy answers from canned text. Turn them on later by deploying their servers and removing the name from `ALLOW_DEMO_ADAPTERS`. The API refuses to start if anything else is left on a demo setting.

---

## 0. What you need before you start

- **A server.** 2 vCPU, 4 GB RAM and 40 GB disk is enough for a 500-student pilot. Examples: an Oracle Cloud Always Free Ampere VM (4 OCPU, 24 GB) or an AWS, Azure or GCP free-tier VM. Add 2 GB of swap on anything with 4 GB RAM or less (step 2).
  - Use Ubuntu 24.04 LTS, with a public IPv4 address.
  - Cloud firewall or security list: allow inbound TCP 22, 80 and 443, and UDP 443. Nothing else.
- **A domain** you control, with two names:
  - `portal.example.in`: the portal
  - `id.example.in`: sign-in (Keycloak)
- **An SMTP account** for email: parent sign-in codes, notices and Keycloak invites.
  - Brevo's free tier sends 300 emails a day; Amazon SES, Zoho or Google Workspace SMTP also work.
  - Verify your sender domain with the provider (SPF and DKIM records), or the codes will land in spam.
- **A second place for backups**: another server reachable over SSH, or a bucket that `rclone` supports (Backblaze B2, Cloudflare R2, Google Drive...).
- **For Teams live classes**: your Microsoft 365 admin works through [TEAMS_SETUP.md](TEAMS_SETUP.md) and gives you three values. You can deploy first and add Teams later (step 9).

Throughout this guide, replace `portal.example.in`, `id.example.in` and `example.in` with your real names.

## 1. Point DNS at the server

At your DNS provider, create two **A** records pointing to the server's public IP:

```
portal.example.in   A   <server IP>
id.example.in       A   <server IP>
```

**Check** (from your laptop; it can take a few minutes): `nslookup portal.example.in` and `nslookup id.example.in` both return the server IP.

## 2. Prepare the server

SSH in as the default user (for example `ubuntu`), then:

```bash
sudo apt-get update && sudo apt-get -y upgrade
sudo apt-get install -y ca-certificates curl git ufw unattended-upgrades rsync
sudo dpkg-reconfigure -f noninteractive unattended-upgrades   # security updates install themselves

# firewall: SSH and web only
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw --force enable

# 2 GB swap (skip if the server has more than 4 GB RAM)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Docker publishes Caddy's ports itself. Only Caddy publishes any ports, so ufw and Docker do not conflict here.

**Check:** `sudo ufw status` lists 22, 80 and 443 as allowed.

## 3. Install Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

**Check:** `docker run --rm hello-world` prints "Hello from Docker!", and `docker compose version` prints v2.20 or later.

## 4. Get the code

```bash
sudo mkdir -p /opt/irep && sudo chown $USER:$USER /opt/irep
git clone https://github.com/Gaut2812/IREP-Portal.git /opt/irep
cd /opt/irep
git checkout master            # or the release tag you were given
```

If the repository is private, create a read-only deploy key on GitHub (repository settings, then "Deploy keys") and clone with the SSH URL.

## 5. Fill in the settings

```bash
cd /opt/irep/infra/prod
cp .env.example .env
chmod 600 .env
for i in 1 2 3 4 5 6; do openssl rand -hex 32; done     # six fresh secrets to paste below
nano .env
```

Set at least these values. Every line in `.env.example` has a comment.

| Setting | Value |
|---|---|
| `APP_DOMAIN`, `ID_DOMAIN` | `portal.example.in`, `id.example.in` |
| `ACME_EMAIL` | your email, for certificate expiry notices |
| `KC_ADMIN_ALLOW_IPS` | your own public IP followed by `/32` (find it at https://ifconfig.me). Only this address can open the Keycloak admin console. Separate several with spaces. |
| `POSTGRES_PASSWORD`, `KC_DB_PASSWORD`, `VALKEY_PASSWORD`, `JWT_SECRET_KEY`, `KEYCLOAK_ADMIN_PASSWORD`, `GITHUB_WEBHOOK_SECRET` | one `openssl rand -hex 32` value each. Use hex: these go into connection URLs. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | from your email provider |
| `GRAPH_*`, `TEAMS_DEFAULT_ORGANIZER` | from your Microsoft 365 admin. If Teams is not ready yet, set `LIVE_CLASS_ADAPTER=fake` and add `live_classes` to `ALLOW_DEMO_ADAPTERS` (step 9). |
| `BACKUP_REMOTE` | your second backup location (step 10) |

Keep a copy of `.env` in your password manager. Without it, the backups cannot be restored to a working server.

**Never commit `.env`.** It is ignored by git, and the Docker builds leave it out as well.

## 6. Build and start

```bash
cd /opt/irep/infra/prod
docker compose build                 # 5-10 minutes the first time
docker compose up -d
docker compose ps
```

On the first start, the services come up in this order:
1. Postgres creates the `irep` and `keycloak` databases.
2. `migrate` creates the portal tables, then exits with code 0.
3. Keycloak imports the `irep` realm. This takes about a minute.
4. Caddy fetches the two HTTPS certificates.

**Check:**
- `docker compose ps` shows `api`, `web`, `worker`, `beat`, `keycloak`, `postgres`, `valkey` and `caddy` as running, with `api` and `keycloak` marked healthy. `migrate` shows `exited (0)`.
- `curl -s https://portal.example.in/health` returns `{"status":"healthy",...}`.
- Open `https://portal.example.in`: the sign-in page loads with a valid padlock.

**If the API keeps restarting**, run `docker compose logs api | head -40`. It prints every unsafe setting in one list, for example `- SMTP_HOST and SMTP_FROM are required`. Fix `.env`, then run `docker compose up -d` again.

**If there is no certificate**, run `docker compose logs caddy`. Usually DNS does not point at this server yet (step 1), or port 80 is blocked by the cloud firewall.

## 7. Point Keycloak at your domain and email

The realm is imported from a development template that has `localhost` addresses and no mail server. This one command fixes both. It also:
- turns self-registration off (accounts are invited or imported only)
- requires two-factor sign-in (an authenticator app such as Google Authenticator or Microsoft Authenticator) for IREP staff and super admins

Run it again whenever you change the domain or the SMTP settings; a re-run changes nothing that is already right.

```bash
docker compose run --rm api python ops/configure_keycloak.py
```

**Check:** it prints `realm irep: redirects -> https://portal.example.in; SMTP set; self-registration off; two-factor required for irep_admin, super_admin`.

Then, from the IP you put in `KC_ADMIN_ALLOW_IPS`:
1. Open `https://id.example.in/admin` and sign in with `KEYCLOAK_ADMIN_USER` and `KEYCLOAK_ADMIN_PASSWORD`.
2. Go to realm **irep**, then **Realm settings → Email**, and press **Test connection**.

From any other address, `/admin` returns 404. That is intended.

## 8. Create the first super admin

```bash
docker compose run --rm api python ops/bootstrap_admin.py --email you@example.in --name "Your Name"
```

This creates a **super admin**: IREP staff plus the powers only it has (see [docs/PERMISSIONS.md](../PERMISSIONS.md)):
- staff accounts
- MoU terms and fees
- feature switches
- billing
- deletion approvals
- logged support sessions

Everything a super admin does is written to the audit log.

Keycloak emails you a link to set your password. On your first sign-in, Keycloak shows a QR code: scan it with an authenticator app and type the 6-digit code. After that, every sign-in asks for a code. Then sign in at `https://portal.example.in` and choose **IREP staff**.

Running the command again is safe: it never resets an existing password or authenticator. Use `--resend-invite` to email the link again.

From there, everyone else is invited, not created by hand. Nobody can sign up on their own:
- **Super admin page** (`/admin/super`): invite IREP staff (they also must use two-factor), and open a logged support session before working on a college's account.
- **Screen 45 (Colleges):** onboard the pilot college. The college representative gets an invite email (`KEYCLOAK_INVITE_EMAIL=true`).
- **The college admin** adds trainers and students on the college screens. Each person gets a Keycloak invite to set their password.
- **Parents** come from the student import file:
  - `parent_phone`, `parent_email`
  - `parent_consent=yes`
  - `parent_consent_ref`: the signed consent form's number

  One mobile number becomes one parent account, linked to all of that parent's children. A row with parent details but no recorded consent is refused, and nothing is saved for it. Parents do not get a Keycloak account: they sign in with their mobile number plus a one-time code (see "Parent sign-in" below), so record a parent email for every parent.

**Check:** you can sign in (password, then authenticator code) and see the Colleges screen and the **Super admin** menu item.

Do **not** run `seed/run_seed.py` or `seed/sync_keycloak.py --password` on this server. They create demo accounts with a shared password.

## 9. Teams live classes

Your Microsoft 365 admin follows [TEAMS_SETUP.md](TEAMS_SETUP.md) and sends you `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET` (and its expiry date) and the organizer account. Put them in `.env` with `LIVE_CLASS_ADAPTER=teams`, then:

```bash
docker compose up -d api worker beat                   # reload the settings
docker compose run --rm api python ops/teams_check.py   # proves token, calendar and meeting access
docker compose run --rm api python ops/set_teams_upn.py --trainer-email trainer@college.edu --upn trainer@college.onmicrosoft.com   # per trainer with their own Teams licence
```

**Check:** `teams_check.py` prints `ok` for `token`, `calendar` and `meetings`. Then run the end-to-end class test in TEAMS_SETUP.md step 8.

**Until Teams is ready**, set `LIVE_CLASS_ADAPTER=fake` and add `live_classes` to `ALLOW_DEMO_ADAPTERS`. Classes then run in the in-portal classroom (shared notebook, polls, Q&A), without video.

## 10. Nightly encrypted backups

### Backup key (do this once, on your own computer, not on the server)

Backups are encrypted with [age](https://age-encryption.org), which is open source. The server holds only the **public** key, so it can encrypt but never decrypt. Anyone who copies the backups, from the server or from the second location, gets unreadable files.

```bash
# on your laptop (Ubuntu/Debian: sudo apt-get install age; macOS: brew install age; Windows: winget install FiloSottile.age)
age-keygen -o irep-backup.key
#   Public key: age1...   <- copy this line's key
```

- **The private key (`irep-backup.key`) belongs in your password manager**, as a secure note or an attached file. Keep a second copy somewhere offline, such as an encrypted USB stick in the office safe.
- **Losing the private key means losing the backups.** Never commit it, email it or leave it on the server.
- **The public key** (`age1...`) goes in `infra/prod/.env` as `BACKUP_AGE_RECIPIENT`. `backup.sh` refuses to run without it.

### What runs every night

On the server, install age once: `sudo apt-get install -y age`.

`infra/prod/backup.sh` writes the following into a dated folder under `BACKUP_DIR` (default `/var/backups/irep`). Each file is encrypted while it is written, so the plain data never touches the disk:
- `irep.dump.age`: the portal database (`pg_dump`, custom format)
- `keycloak.dump.age`: the sign-in database
- `uploads.tar.gz.age`: everything in file storage, such as certificate proofs, recordings, exports, and report and card PDFs
- `SHA256SUMS`, plus `RECIPIENT` (the public key used)

It keeps 7 days (`BACKUP_KEEP_DAYS`), then mirrors the folder to `BACKUP_REMOTE`. Only encrypted files leave the server.

**Second location.** Choose one:
- **Another server over SSH:** set `BACKUP_REMOTE=backup@203.0.113.20:/srv/backups/irep`. Then, as root, create a key and authorise it on that server:
  ```bash
  sudo ssh-keygen -t ed25519 -N "" -f /root/.ssh/id_ed25519
  sudo ssh-copy-id -i /root/.ssh/id_ed25519.pub backup@203.0.113.20
  ```
- **A bucket (B2, R2, S3, Google Drive):**
  ```bash
  sudo apt-get install -y rclone
  sudo rclone config    # create a remote, e.g. "b2"
  ```
  Then set `BACKUP_REMOTE=b2:irep-backups`.

**Run it once by hand**, then schedule it:

```bash
sudo /opt/irep/infra/prod/backup.sh
ls -lh /var/backups/irep/*/          # only .age files, SHA256SUMS and RECIPIENT
echo '15 2 * * * root /opt/irep/infra/prod/backup.sh >> /var/log/irep-backup.log 2>&1' | sudo tee /etc/cron.d/irep-backup
```

The backup runs at 02:15 server time, after the 01:30 IST readiness job. Ubuntu cloud images use UTC, so 02:15 UTC is 07:45 IST. That is fine for a quiet hour. Change the time if you prefer.

**Check the next morning:** `tail /var/log/irep-backup.log` ends with `done:`, and today's folder is also in the second location.

### Restore from a backup (do this drill once before go-live, then every term)

The restore uses the **encrypted** copy and your private key.
1. Copy the key to the server for the restore only.
2. `restore.sh` does the rest:
   - checks the checksums
   - proves the key opens every file before stopping anything
   - restores both databases and the uploads
   - starts everything again
   - records the drill in `BACKUP_DIR/restore-drills.log`, which the go-live check reads

```bash
scp irep-backup.key you@server:/tmp/irep-backup.key        # from your laptop
cd /opt/irep/infra/prod
sudo ./restore.sh /var/backups/irep/2026-11-20_0215 /tmp/irep-backup.key
sudo shred -u /tmp/irep-backup.key                         # never leave the private key on the server
```

To restore from the second location instead:
1. Copy the dated folder back to the server, with `rsync` or `rclone copy b2:irep-backups/2026-11-20_0215 /var/backups/irep/2026-11-20_0215`.
2. Run the same command.

**Before go-live,** the drill replaces only demo data. Later, practise on a separate test server instead, by following steps 1–6 there with a copy of `.env`.

**On a new server:** follow steps 1–6 with the **same `.env`**, then run the restore. The JWT secret and database passwords must match.

**Check:** sign in, open a certificate proof and download a report PDF.

## 11. Updating to a new version

```bash
cd /opt/irep && git fetch && git checkout <new tag or master> && git pull
cd infra/prod
sudo ./backup.sh                                  # always back up first
sed -i "s/^IREP_VERSION=.*/IREP_VERSION=$(git rev-parse --short HEAD)/" .env
docker compose build && docker compose up -d      # migrate runs before the api starts
docker compose ps && curl -s https://portal.example.in/health
```

**Rolling back:**
1. Set `IREP_VERSION` back to the previous tag. The old images are still on the server.
2. Run `git checkout` on the previous commit, then `docker compose up -d`.
3. If the new version ran a migration, restore the backup you took first.

Clean up old images now and then: `docker image prune -a --filter "until=720h"`.

## Parent sign-in: email code (default) and the SMS switch

Parents sign in with their mobile number. The portal then sends a 6-digit code, valid for 5 minutes. This happens in the API in Keycloak mode as well: Keycloak 26 has no email or SMS one-time-code login, so the API issues the parent session (`routers/auth.py`). The code is sent directly, never stored in plain text or queued.

- **`PARENT_OTP_CHANNEL=email`** (default, free): the code goes to the parent's email on file, in English and Tamil. A parent without an email address gets the same "if this number is registered" answer, and the audit log records `skipped:no_email`. Make sure the college office records parent emails.
- **SMS through Fast2SMS** (paid, **off by default**; the provider IREP uses):
  1. In the Fast2SMS dashboard, open **Dev API** and copy the API key. Treat it like a password: it goes only in `infra/prod/.env`, never in chat, email or git. If it was ever shared, regenerate it there.
  2. Recharge the wallet. Quick SMS (`route=q`) needs no DLT template and costs more per SMS. The OTP route (`FAST2SMS_OTP_ROUTE=otp`) sends only the code, in Fast2SMS's fixed text.
  3. Set:
     ```
     SMS_PROVIDER=fast2sms
     FAST2SMS_API_KEY=...
     PARENT_OTP_CHANNEL=sms        # optional: codes by SMS; leave "email" to send only notices by SMS
     ```
  4. Run `docker compose up -d api worker beat`, then request a parent code with your own mobile number.

  The key travels only in the `authorization` header of a POST, never in a URL, so it stays out of logs.
- **SMS through MSG91** (paid, **off by default**):
  1. Register your sender ID and two templates on the DLT portal (TRAI rules): an OTP template with an `##otp##` variable, and a notice template with a `##message##` variable.
  2. Create the same templates in MSG91. Then set:
     ```
     SMS_PROVIDER=msg91
     MSG91_AUTH_KEY=...
     MSG91_OTP_TEMPLATE_ID=...
     MSG91_TEMPLATE_ID=...
     PARENT_OTP_CHANNEL=sms        # optional: codes by SMS; leave "email" to send only notices by SMS
     ```
  3. Run `docker compose up -d api worker beat`.

While `SMS_PROVIDER=off`, every notice meant for SMS (leave decisions, events, at-risk alerts) goes to the person's email instead. It is recorded as `delivered:email`.

## Files: local disk now, S3 later

All files go through `services/storage.py`, an interface with `put`, `get`, `exists`, `delete` and `size`. In the pilot, `STORAGE_ADAPTER=local` keeps them on the `uploads` Docker volume, and the nightly backup copies them.

To move to an S3-compatible bucket later:
1. Implement `S3Storage` (the docstring lists the steps).
2. Copy the files across.
3. Set `STORAGE_ADAPTER=s3`.

Callers do not change. Production refuses `s3` until it is implemented.

## Day-to-day commands

```bash
cd /opt/irep/infra/prod
docker compose ps                         # what is running
docker compose logs -f --tail=100 api     # API log (also: worker, keycloak, caddy)
docker compose restart worker             # after changing email/SMS settings
docker compose exec postgres psql -U irep -d irep    # database shell (careful)
df -h / && docker system df               # disk space
```

## Security notes

- Only Caddy is published. Postgres, Valkey and Keycloak's admin API are reachable only inside Docker.
- Keycloak's `/admin` and the `master` realm answer only to `KC_ADMIN_ALLOW_IPS`. `/docs` and `/openapi.json` are not served publicly.
- The Keycloak admin created from `KEYCLOAK_ADMIN_USER` is a bootstrap account. After the first sign-in:
  1. In the master realm, create a named admin user for yourself, with a strong password and OTP.
  2. Create a service account for the API's user sync.
  3. Replace `KEYCLOAK_ADMIN_USER` and `KEYCLOAK_ADMIN_PASSWORD` in `.env`.
  4. Delete the bootstrap user.
- Rotate `GRAPH_CLIENT_SECRET` before it expires (TEAMS_SETUP.md, "Secret rotation").
- Deactivating a user in the portal blocks new sign-ins. Tokens already issued stay valid until they expire (15 minutes for Keycloak access tokens).
