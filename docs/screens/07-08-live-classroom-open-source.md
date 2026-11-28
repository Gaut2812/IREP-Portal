# 07 + 08 Live classroom on open-source video (LiveKit), Teams later

Status: **P1-P3 built** (backend, web stage, moderation; dev infra; tested end to end against a real LiveKit server). P4 production deploy, P5 recording and P6 per-college switch are open. Needs a person's review before merge (new `infra/`, external engine, migration).

Decisions taken: LiveKit; students' camera and mic start off; recording later (P5); media on its own VM.

## 1. Goal

Today screen 07 has three providers behind `services/live_class.get_live_adapter()`:

| Adapter | What the user gets | Gap |
|---|---|---|
| `fake` (default) | In-portal stage: shared code, flow panel, polls, Q&A, presence | No audio or video |
| `bbb` | Signed BigBlueButton URL in an iframe | `create` is never actually called; BBB needs its own heavy Ubuntu host; its UI is not ours (no Tamil, no portal panels) |
| `teams` | "Join in Teams" in a new tab, Graph attendance report | Waits on the college's M365 consent (`docs/deploy/TEAMS_SETUP.md`) |

We add a fourth, **`livekit`**: real audio, video and screen share **inside** `/live/[sessionId]`, next to the existing poll, Q&A and attendance panels, on free self-hosted software. Teams stays as the target for colleges that have M365; the switch is a config (and later per-college) choice, with no change to screens 08, 09, 10 or the attendance maths.

## 2. Engine choice

| | LiveKit (recommended) | Jitsi Meet | BigBlueButton |
|---|---|---|---|
| Licence | Apache-2.0 | Apache-2.0 | LGPL-3.0 |
| Embeds as our UI | Yes: React SDK, we draw tiles and controls | Iframe of Jitsi UI | Iframe of BBB UI |
| Per-user auth | JWT minted by our API (room, identity, publish rights) | JWT via Prosody plugin | Checksum URLs |
| Join/leave webhooks for attendance (L06) | Built in, signed | Needs a Prosody event-sync module | Needs bbb-webhooks |
| Recording | Egress (separate container) | Jibri (one Chrome per recording) | Built in, slow processing |
| Footprint | One Go binary (+ Valkey for multi-node, which we already run) | 4 services | Dedicated Ubuntu 22.04 box |
| Low bandwidth | Simulcast, dynacast, adaptive stream | Simulcast | Fixed |

LiveKit wins on the two things this portal cares about: attendance comes back as signed webhooks into the tables we already have, and the room is our own React UI, so i18n (rule 9), the UI kit and the side panels all keep working. `bbb` stays in the code as is.

## 3. How it fits the existing flow

```
08 Live sessions ──Join──▶ POST /sessions/{id}/join
                              │ ensure_meeting(): provider="livekit", room="irep-{college_id}-{session_id}"
                              │ returns {provider, ws_url, token}   (token minted locally, no network call)
                              ▼
07 /live/[sessionId]  ── LiveKit JS ──▶ livekit-server (own node)
                              │                    │ webhook (signed JWT, sha256 of body)
                              │                    ▼
                              │          POST /webhooks/livekit
                              │            participant_joined/left → JoinEvent(source="livekit")
                              │            room_finished           → finalize_session() → 09 (L06)
                              │            egress_ended            → Recording row → 08 (L04)
                              ▼
          polls, Q&A, presence: unchanged (our tables + /ws/live/{id})
```

## 4. Backend work (`apps/api`)

1. **Config** (`core/config.py`): `LIVEKIT_URL` (server API, e.g. `http://livekit:7880`), `LIVEKIT_WS_URL` (public `wss://`), `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_RECORDING` (off by default).
2. **Adapter** `LiveKitAdapter` in `services/live_class.py`:
   - `create_meeting` returns `irep-{college_id}-{session_id}` (tenant in the room name, so a token can never name another college's room).
   - `join_token(meeting_id, user, role, session)`: HS256 JWT with `python-jose` (already a dependency): `video.room`, `roomJoin`, `canSubscribe`; trainer gets `roomAdmin`, `canPublish` all sources; students get mic and camera, no screen share until the trainer grants it. TTL ends 30 minutes after the session's scheduled end. Identity is `users.id`, display name from the DB, never from the client.
3. **Join route** (`routers/live.py`): for `livekit`, return `{provider, ws_url, token}`; record a `click` JoinEvent only (as Teams does). Existing role, tenant and join-window checks stay first.
4. **Webhook** `POST /webhooks/livekit`:
   - Verify the `Authorization` JWT with the API secret and the body's sha256; reject otherwise (401).
   - Resolve the session from the room name and check its `college_id` matches; ignore unknown rooms.
   - Idempotent: LiveKit retries, so store the webhook `id` (new nullable unique `join_events.external_id`) and skip duplicates.
   - `room_finished` sets `ended_at` and calls `finalize_session()`; record `audit live.end` if not already ended by the trainer.
5. **Presence** (`user_presence`): for `provider == "livekit"` count only `source="livekit"` events, exactly like the Teams branch. 75% rule unchanged.
6. **Moderation** (trainer only, audited): mute a participant, remove a participant, allow or revoke a student's screen share, end the room for everyone. Each writes state plus an outbox event (`live.moderate`, `live.room_end`); the handler calls LiveKit's RoomService (Twirp over HTTP). Rule 3 forbids calling it inside the request; in development the API dispatcher runs it after commit, so latency is a second at most. *Review point: if worker latency in production is too slow for "mute", consider a narrow after-commit exception like the parent OTP.*
7. **Recording (phase 2)**: `livekit.egress_start` outbox event on trainer "Record" → Egress room-composite MP4 → upload through `services/storage.get_storage()` → `Recording(status="processing")` then `ready` on `egress_ended`; `size_mb` counts against MoU storage (L36, `services/quotas.py`). Consent: show "This class is recorded" banner to everyone in the room.
8. **Production guard** (`core/production.py`): accept `livekit` as a real adapter; require non-default key/secret and a `wss://` public URL; `ALLOW_DEMO_ADAPTERS` unchanged.
9. **Migration**: `join_events.external_id` (String(64), nullable, unique, named constraint) + `live_meetings.provider` comment update. `alembic check` on SQLite and PostgreSQL.

## 5. Web work (`apps/web`)

- Add `livekit-client` (Apache-2.0). Built without `@livekit/components-react` so the room uses our UI kit and locales. Read `apps/web/AGENTS.md` first; the room is a client component loaded with `dynamic(..., { ssr: false })`.
- `src/components/live/LiveKitStage.tsx` replaces the dark stage area when `provider === "livekit"`:
  - Main tile: active screen share, else trainer camera; filmstrip of up to 8 others, then "+N".
  - Control bar (UI kit buttons): mic, camera, screen share (trainer, or student when granted), raise hand (data message, shown in the participant list), "Audio only" for weak networks, leave.
  - Trainer menu on a participant: mute, allow share, remove. "End for everyone" calls the existing `POST /sessions/{id}/end`.
  - Reconnecting / network-poor banner; adaptive stream and dynacast on by default.
- Right-hand panels (poll, Q&A, attendance meter, spectate link) unchanged.
- All strings under `live_class.*` in `en.json` and `ta.json`. No hex classes, nothing under 12px (`scripts/ui_codemod.py --check`).
- Camera and mic permission denied: clear message and audio-only fallback, never a blank page.

## 6. Infra (needs review)

- `infra/livekit/docker-compose.yml` + `livekit.dev.yaml`: on 7880 (HTTP/WS), 7881 (TCP), 52000-52100/udp (clear of Windows reserved ranges); webhook to `http://host.docker.internal:8000/api/v1/webhooks/livekit`.
- `infra/livekit/livekit.yaml` for production: own VM (rule 10 spirit: not on the DB host), Valkey from the main stack for room state, built-in TURN on 443/TLS so campus firewalls that block UDP still work, Caddy terminates `wss://live.<domain>`.
- Egress (phase 2) as a separate container on the same node; it needs ~2 vCPU per concurrent recording.
- Sizing note for the pilot: a 4 vCPU / 8 GB node comfortably carries a few concurrent classes of 60-100 students with students' video mostly off. Load test with `lk load-test` before go-live; add `loadtest/livekit_room.md`.
- `ops/golive_check.py`: add a LiveKit check (token mint, `ListRooms` reachability, webhook secret set).

## 7. Tests

pytest (`tests/test_screen_07_livekit.py`), tagged `@pytest.mark.link("L04")` / `("L06")`:
- Token claims: room carries the caller's college, identity is `users.id`, student cannot screen share, TTL bounded.
- Join: happy path, wrong role 403, other college's session 404, ended session 409, before window 409.
- Webhook: bad signature 401, room of another tenant ignored, duplicate event id ignored, join/leave → presence, `room_finished` → attendance Present at 75%, Excused on approved leave.
- Moderation: trainer only, audit row + outbox event written, handler idempotent (RoomService mocked).
- Tamil: room state strings carry `_ta` where server text is shown.
- Production guard: `livekit` with demo secret is refused.

Playwright (`e2e/screen07-livekit.spec.ts`): runs only when `LIVEKIT_E2E=1` with the dev container up; Chromium with fake media flags (`--use-fake-device-for-media-stream`). Trainer starts, student joins, both tiles render, Tamil toggle, parent role guarded. The default suite keeps the `fake` adapter so CI needs no media server.

## 8. Teams later

- Nothing in this plan removes or forks the Teams path; `TeamsAdapter`, `services/teams.py` and the attendance import stay.
- Add `College.live_provider` (nullable, overrides `LIVE_CLASS_ADAPTER`) so pilot colleges can move to Teams one at a time once their admin consents; `ensure_meeting()` reads it. Existing meetings keep the provider they were created with.
- Behaviour that differs and the UI must state: Teams opens in a new tab, recordings stay in Teams, attendance arrives after the meeting (not live).

## 9. Phases

| Phase | Scope | Size |
|---|---|---|
| P1 | Config, adapter, token, join route, webhook, presence, migration, dev compose, pytest | ~2 days |
| P2 | Web stage: tiles, controls, permissions fallback, i18n, Playwright behind flag | ~3 days |
| P3 | Trainer moderation through the outbox, raise hand, audio-only | ~1.5 days |
| P4 | Production config, TURN, golive check, load test, docs/deploy/LIVEKIT.md | ~1.5 days |
| P5 | Recording via Egress → screen 08, quotas, consent banner | ~2 days |
| P6 | Per-college provider switch for Teams | ~1 day |

## 10. Decisions needed

1. Engine: LiveKit (recommended) vs Jitsi.
2. Recording in the pilot (P5) or later?
3. Students' cameras: off by default (recommended for bandwidth) or on?
4. Largest expected class size and number of concurrent classes (sizes the node).
5. Hosting: a separate VM for media (recommended) or the pilot VM for the first month.
