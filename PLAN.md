# electric-eye — Master Plan

---

## Blinds (Mobilus Cosmo GTW)

### Bugs
- [ ] Room/group slider doesn't update individual device sliders after a command — stays stale until page reload
- [ ] Device types not visible on room/group cards — only on individual device rows

### Todo
- [ ] Health check: test each device individually, report which respond and which don't
- [ ] Type-7 tilt blind percentage mapping — physically test Salon devices (IDs 9, 10, 11) to determine how % commands behave vs roller shutters; infrastructure already in place (`_map_percent_for_type` + `control_many_varied`)
- [ ] README: setup instructions (docker compose, env vars, devices.toml)

### Later
- [ ] Scheduling — open/close at sunrise/sunset or specific times
- [ ] Scene support — e.g. "movie mode" = salon 80%, antresola 100%
- [ ] Wind rule — auto-close shutters (rolety) only, leave tilt blinds; needs wind data source + scheduler
- [ ] iOS app (SwiftUI, direct MQTT/WebSocket to gateway)

### Protocol research
- [ ] Document full MQTT message flow (connect, subscribe, publish, login handshake, command/response)
- [ ] Understand what the Mobilus Dom mobile app does differently (same commands? polling frequency? reconnect behaviour?)

---

## AC (Vivax / Midea LAN)

### How we connected
- Protocol confirmed via **Wireshark ARP MITM** — Wireshark identified traffic as `GDMideaAirCo` (Midea LAN)
- Library: `msmart-ng` (already in pyproject.toml)
- Discovery: `uv run msmart-ng discover -d <ip>` — auth via built-in cloud credentials, no account needed
- Key is stable; token fetched fresh each session

### Known devices
| Room | IP | Device ID |
|---|---|---|
| ? | 192.168.68.61 | 152832117775694 |

Run `uv run msmart-ng discover -d <ip>` on each new unit to get its ID and key.

> More IPs needed from TP-Link app.

### Implementation plan

**1. Config — `devices.toml`**
Add `[ac]` section:
```toml
[ac.living_room]
ip   = "192.168.68.61"
id   = 152832117775694
key  = "0fd27a5..."
name = "Living Room"
```

**2. `electric_eye/ac.py`**
Async wrapper around msmart-ng: `connect()`, `refresh()`, `set_power()`, `set_temperature()`, `set_mode()`

**3. CLI — `ee ac`**
- `ee ac list` — all units + state
- `ee ac on/off <unit>`
- `ee ac set <unit> <temp>`

**4. Web API — `/api/ac`**
- `GET /api/ac`
- `POST /api/ac/{unit}/on|off`
- `POST /api/ac/{unit}/set` `{"temperature": 22}`

**5. UI**
Climate tab is already stubbed in the web UI — wire it up once backend is ready.

---

## Cameras (Dahua — bypass NVR)

### Later
- [ ] Discover cameras on local network (may be on a separate PoE subnet behind the NVR)
- [ ] Talk to cameras directly via Dahua HTTP API (digest auth, CGI endpoints)
- [ ] Live RTSP stream viewing
- [ ] Motion detection events
- [ ] Own recording/storage

---

## DevOps / Infrastructure

### Decisions made
- **Branch strategy:** trunk-based — short-lived feature branches → PR → main; releases via git tags
- **Registry:** GHCR (`ghcr.io/fdanieluk/electric-eye`)
- **Image tags:** `<git-sha>` on every merge to main; `1.2.3` (semver, no `v` prefix) on tag push; no `latest`
- **Deployment:** manual `docker compose pull && docker compose up -d` on server for now

### Done
- [x] Branch protection on `main`
- [x] Dockerfile (Python 3.13, uv, two-stage sync for layer caching)
- [x] GH Actions workflow (`build-push.yml`) — builds on PR, pushes to GHCR on merge/tag, `workflow_dispatch` for manual runs

### Todo
- [ ] Merge `devops/ci-cd` PR and push `v1.0.0` tag to publish first image
- [ ] Add `ruff` to dev dependencies and add lint step to the workflow
- [ ] Decide on deployment automation (Watchtower vs webhook vs manual)
- [ ] Choose home server to run the container on
