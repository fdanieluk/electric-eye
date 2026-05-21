# electric-eye

A CLI and local web dashboard for controlling Mobilus blinds/shutters at home.

## What it does


- Provides a `ee` CLI for quick terminal control
- Serves a local web UI (`ee web`) with a clean dashboard for per-device and per-room control

## Stack

- FastAPI (web API + serving static UI)
- Click (CLI)
- [`mobilus-client`](https://github.com/zpieslak/mobilus-client) by [Zbigniew Pieślak](https://github.com/zpieslak) — reverse-engineered Python client for the Mobilus Cosmo GTW gateway (AES-CFB encrypted protobuf over MQTT/WebSocket)

## Usage

Copy `.env.example` to `.env` and fill in your gateway credentials:

```
MOBILUS_HOST=192.168.x.x
MOBILUS_LOGIN=admin
MOBILUS_PASSWORD=yourpassword
```

### CLI

```bash
uv run ee --help
uv run ee blinds list
uv run ee blinds status
uv run ee blinds up <id>
uv run ee blinds room-down <room>
uv run ee blinds all-stop

# Show full MQTT/encryption debug output
uv run ee -v blinds status
```

### Web UI

```bash
uv run ee web --host 0.0.0.0
# Open http://localhost:8000
```

### Docker

```bash
docker compose up -d
```

## Project structure

```
electric_eye/
  cli.py        # Click CLI entry point
  web.py        # FastAPI app + JSON API
  blinds.py     # BlindsClient wrapper around mobilus-client
  config.py     # Env config
  static/       # Single-page HTML/JS UI (no build step)
```

