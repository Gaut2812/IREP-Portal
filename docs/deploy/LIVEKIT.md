# Live classes on LiveKit (open source)

`LIVE_CLASS_ADAPTER=livekit` puts audio, video and screen share inside the portal's live classroom
(screen 07). LiveKit (Apache-2.0) is self-hosted; there is no licence fee. Teams stays available
(`LIVE_CLASS_ADAPTER=teams`, `TEAMS_SETUP.md`); a meeting keeps the provider it was created with.

Status: works end to end in development (Playwright against a real server). **Production is not
deployed yet**: the media node, TURN and the firewall rules below need a person's review.

## How it works

1. Join (`POST /sessions/{id}/join`) returns a token minted by the API: room
   `irep-{college_id}-{session_id}`, identity `users.id`. Trainers can moderate and share their
   screen; students get camera and mic, and screen share only when the trainer allows it.
2. LiveKit calls `POST /api/v1/webhooks/livekit` (JWT signed with the API secret, carrying the
   body's sha256). `participant_joined/left` become join events; `room_finished` finalizes
   attendance (75% rule). Retries are deduplicated by the webhook id.
3. Ending the class, mute, remove and screen-share permission go through the outbox
   (`livekit.end_room`, `livekit.moderate`) to LiveKit's RoomService. All are audited.

## Development

```bash
docker compose -f infra/livekit/docker-compose.yml up -d      # LiveKit on :7880, UDP 52000-52100
cd apps/api
LIVE_CLASS_ADAPTER=livekit venv/Scripts/python -m uvicorn main:app --port 8000
```

The defaults in `core/config.py` match `infra/livekit/livekit.dev.yaml` (dev-only key). Webhooks go
to `host.docker.internal:8000`. A class whose meeting already exists keeps its old provider:
re-seed, or delete its `live_meetings` row, to try LiveKit on a seeded session.

End-to-end test with real media (fake camera in Chromium):

```bash
cd apps/web
LIVEKIT_E2E=1 pnpm exec playwright test e2e/screen07-livekit.spec.ts --project=chromium
```

## Production (one media VM)

- **Separate VM** from the database and the API (4 vCPU / 8 GB carries a few concurrent classes
  of 60-100 students with students' cameras mostly off). Load test with `lk load-test` first.
- Copy `infra/livekit/livekit.prod.yaml`, fill every `CHANGE_ME`, run
  `livekit/livekit-server:v1.9 --config /etc/livekit.yaml` with host networking.
- Firewall: 443/tcp (Caddy: `wss://live.<domain>` → 7880, and TURN/TLS), 7881/tcp,
  50000-60000/udp, 3478/udp. Keep 7880 closed to the internet except through Caddy.
- API `.env`: `LIVE_CLASS_ADAPTER=livekit`, `LIVEKIT_URL` (private address),
  `LIVEKIT_WS_URL=wss://...`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (32+ random characters).
  `core/production.py` refuses dev keys and a non-`wss://` URL.

## Not done yet

- Recording (LiveKit Egress → `services/storage` → screen 08, MoU storage quota).
- Per-college provider switch (`College.live_provider`) for moving colleges to Teams one by one.
- `ops/golive_check.py` LiveKit check and a load-test note in `loadtest/`.
