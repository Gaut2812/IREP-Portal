# Virtual labs: the labs track

Master Plan: "one launcher (JupyterHub) behind one FastAPI labs service". Every lab, browser or server, goes through the same portal checks: entitlement by semester and track, quota, trainer approval where needed (Cyber Range, with the AUP), and one lab at a time. Usage goes to `usage_ledger`, so the credits meter (47) works for every kind.

## What is built

| Lab | Runtime | How it runs | Plan sprint | State |
| --- | --- | --- | --- | --- |
| SQL Playground | browser | PostgreSQL in the browser (PGlite 0.2.12 from jsDelivr) | S4 | built, E2E-tested |
| Python Playground | browser | Python 3 in the browser (Pyodide 0.26.4 from jsDelivr) | S4 | built |
| Linux Sandbox | server | JupyterHub profile `linux` (JupyterLab terminal) | S9 | built; image and hub config in `infra/labs`, **not deployed** |
| Full-Stack Workspace | server | JupyterHub profile `fullstack` (code-server with Open VSX, Node.js, psql) | S10 | built; **not deployed** |
| AI Notebook | server | JupyterHub profile `ai-cpu` (scipy stack, 2 CPU, 4 GB) | S11 | built; **not deployed**. GPU stays on Kaggle and Colab |
| Cloud Sandbox | external | The college's AWS Academy Learner Lab link; credits metered by session time | S14 | built |
| Docker & Kubernetes | server | Docker + kind inside a Sysbox container (no `--privileged`); images only via the pull-through registry cache | S11 | built in `infra/labs/images/docker-k8s`; enabled only with `LAB_SYSBOX=1` on a Sysbox node; **not deployed** |
| Cyber Range | server | Juice Shop + DVWA on a **separate isolated node** (`infra/cyber-range`), its own hub, no outbound network, trainer approval + signed AUP, access expires after 30 days | S12 | built; portal routes only to `CYBER_RANGE_HUB_URL`; **not deployed** |

## Labs service (apps/api)

- `services/lab_orchestrator.py`: checks, sessions, culling (idle 30 min, hard expiry, starting more than 10 min means failed), metering and adapters.
- **Server labs** (`LAB_ADAPTER`):
  - `jupyterhub` (pilot, production): a pseudonymous hub user per student (`s` + 16 hex characters; no names or ids) and one named server per session with the lab's profile. "Open workspace" mints a token scoped to that one server that lasts until the session expires.
  - Starting and stopping are outbox events (`lab.start`, `lab.stop`), never calls inside a request (rule 3). Both handlers are idempotent.
  - `docker` (development only): a hardened `docker run`:
    - no network (the Cyber Range uses its isolated network)
    - all capabilities dropped, `no-new-privileges`, uid 1000
    - read-only root with tmpfs home
    - 1 CPU, 1 GB without swap, 256 processes
  - `fake` (default): records a workspace and shows a demo terminal.
  - Production refuses anything but `jupyterhub` (`main.py`).
- **Browser labs:** nothing runs on IREP servers. The page sends a beacon every minute and on tab close (`navigator.sendBeacon`).
  - Beacons are signed with a key derived from the API secret and scoped to one session. A beacon token is never valid as a sign-in token, and the reverse is also true.
- **External labs:** the portal records the session and its credits; "Open cloud sandbox" opens the college's link.
- **Trainer lab board** (`/trainer/labs`): live sessions in the trainer's batches (who, which lab, running and idle minutes, time left). The trainer can stop one with a note to the student (notified, audited as `lab.stop_by_trainer`). It shows no workspace contents.

## Endpoints added

| Method | Path | Role |
| --- | --- | --- |
| GET | `/student/lab-sessions/{id}/connect` | student, own session: a short-lived URL (server or external) |
| POST | `/labs/beacon` | none; the body carries the session-scoped token |
| GET | `/trainer/labs`; POST `/trainer/lab-sessions/{id}/stop` | trainer, own batches |

## Before anyone deploys `infra/labs` (person's review)

1. Use a dedicated lab node: never the database or API host. DockerSpawner mounts the Docker socket, which is root on that machine.
2. Keep the `irep-labs-users` network `internal: true`, so there is no route to the internet, cloud metadata or the portal subnet. If students need `pip install`, add a package mirror on that network instead of opening egress.
3. Put TLS in front of the hub, and allow only the portal's egress IP to reach `/hub/api`.
4. Generate `IREP_LABS_SERVICE_TOKEN` with `openssl rand -hex 32`. Store it only in `.env` on the node and as `JUPYTERHUB_API_TOKEN` in the portal's secrets. Never commit either.
5. Build the images, run one launch from the portal, confirm "Open workspace", then run the idle culler test (close the tab and wait 30 min).
6. JupyterHub 5 still accepts `?token=` with `JUPYTERHUB_ALLOW_TOKEN_IN_URL=1`. If a later version removes it, switch to an OAuth hand-off.
7. Browser labs load PGlite and Pyodide from jsDelivr at pinned versions. To remove the third-party dependency, self-host those files under the portal's domain.

## Still to do on the labs track

- **Done in S11/S12:** Docker & Kubernetes profile, launch storm (`loadtest/lab_storm.py`), Cyber Range node, isolation test (`tests/test_lab_isolation.py`), MoU quotas (L36).
- **Done in S13:**
  - **Server-lab metering:** cAdvisor in `infra/labs`. `services/lab_metering.py` runs every 5 min (Celery `irep.labs.meter`, or `POST /admin/jobs/labs/meter`) when `LAB_METER_URL` is set. It records CPU seconds and peak memory per session, and CPU use counts as activity for the idle culler.
  - **Exercise checkers:** `lab_exercises` (3 SQL, 2 Python seeded). The page sends its latest result; the expected answer stays on the server. These are practice checks, not marks: results run in the browser, so they feed readiness only once server-side checks exist (S15). Trainers see passed and tried counts on the lab board.
  - **Spectate links:** a trainer posts a read-only link (https, on the lab hub or `SPECTATE_ALLOWED_HOSTS`) on a class, and students see it on the live class page until the class ends.
- **Next on the hardware:** run the storm against the real hub; a Sysbox node for Docker & K8s; the range node.
- **S13:** cAdvisor metering for server labs, grading checkers, and spectate links on the class page.
- **S16:** k3s readiness.
- Labs links L40–L43 are still a Master Plan question ("Add the labs links L40–L43 to the interconnect table?").
