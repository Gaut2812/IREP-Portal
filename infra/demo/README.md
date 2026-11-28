# IREP public demo server

A demo of the portal with the demo accounts and demo data, for showing colleges and testing on a phone.
It is **not** production: no Keycloak, every engine on its demo adapter (coding lab, labs, Study Buddy,
live classes), and no email or SMS is ever sent. Production is `infra/prod` (`docs/deploy/DEPLOY.md`).

**Never put real students' or parents' data on this server.** Everyone who passes the gate can sign in
as any demo account, including the super admin.

## What you need

- **A small Ubuntu server:** 2 vCPU, 4 GB RAM, 30 GB disk (add 2 GB swap). Postgres, the API, the website and
  Caddy only: no Keycloak, ClamAV, Valkey or Judge0.
- **One domain name**, for example `demo.yourdomain.in`, with a DNS A record pointing at the server.
- Ports 80 and 443 open (Caddy fetches the HTTPS certificate by itself).

## Steps

```bash
# 1. Docker (https://docs.docker.com/engine/install/ubuntu/), then the code
sudo git clone <repo> /opt/irep && cd /opt/irep/infra/demo

# 2. Settings
cp .env.example .env && chmod 600 .env
openssl rand -hex 32            # POSTGRES_PASSWORD
openssl rand -hex 32            # JWT_SECRET_KEY
openssl rand -hex 32            # DEMO_GATE_TOKEN
docker run --rm caddy:2 caddy hash-password --plaintext 'the-gate-password'   # DEMO_GATE_HASH, inside single quotes
nano .env                       # APP_DOMAIN, ACME_EMAIL and the values above

# 3. Build and start (first build: about 10 minutes)
docker compose build && docker compose up -d
docker compose ps               # seed: Exited (0); api, web, caddy, postgres: Up
```

Open `https://demo.yourdomain.in`. The browser asks for the gate user name (`DEMO_GATE_USER`, default `irep`)
and password, then shows the normal sign-in page.

## Demo sign-ins

| Role | Sign in |
|---|---|
| Student | `priya.r@demo.edu` / `password123` |
| Trainer | `arun.k@demo.edu` / `password123` |
| College admin | `admin@demo.edu` / `password123` |
| IREP staff | `staff@irep.demo` / `password123` |
| Super admin | `super@irep.demo` / `password123` |
| Parent | mobile `9876543210`; the code is shown on the screen |

## The gate

- `DEMO_GATE=gate` (default): one shared user name and password protect the whole site. After it, the browser
  holds a secret cookie (`DEMO_GATE_TOKEN`); API and file calls without that cookie get 401. This stops strangers
  from using the demo (for example to upload files). Search engines are asked not to index it.
- `DEMO_GATE=open`: anyone with the link can reach the sign-in page. Use it only for a short live demo.
- Change the gate password: make a new hash, update `.env`, then `docker compose up -d caddy`.

## Keeping it fresh

```bash
docker compose run --rm seed       # re-anchors the demo dates to today and restores the demo records
docker compose down -v && docker compose up -d   # full reset: deletes everything visitors added
```

A nightly refresh (as root, `crontab -e`):

```
30 2 * * * cd /opt/irep/infra/demo && docker compose run --rm seed >> /var/log/irep-demo-seed.log 2>&1
```

## Updating

```bash
cd /opt/irep && git pull && cd infra/demo && docker compose build && docker compose up -d
```

## Differences from production

| | Demo (`infra/demo`) | Production (`infra/prod`) |
|---|---|---|
| `ENVIRONMENT` | `demo`: sign-in required; parent codes shown on screen | `production`: refuses fakes and weak settings |
| Sign-in | local, `password123` demo accounts | Keycloak, invitations, staff two-factor |
| Email and SMS | never sent (`NOTIFY_ADAPTER=fake`) | sent (`NOTIFY_ADAPTER=live`) |
| Coding lab, labs, Study Buddy, live classes | demo adapters | real engines on their own servers |
| Uploads | not virus-scanned; behind the gate | scanned by ClamAV |
| Backups | none (demo data can be re-created) | nightly, encrypted |
