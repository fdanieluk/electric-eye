import json
import logging
import os
import sys

import click
from dotenv import load_dotenv

from electric_eye.blinds import BlindsClient

load_dotenv()


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        stream=sys.stderr,
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def get_blinds_client() -> BlindsClient:
    host = os.environ.get("MOBILUS_HOST")
    login = os.environ.get("MOBILUS_LOGIN")
    password = os.environ.get("MOBILUS_PASSWORD")

    missing = []
    if not host:
        missing.append("MOBILUS_HOST")
    if not login:
        missing.append("MOBILUS_LOGIN")
    if not password:
        missing.append("MOBILUS_PASSWORD")

    if missing:
        click.echo(f"Missing env vars: {', '.join(missing)}", err=True)
        click.echo("Set them in .env or export them.", err=True)
        sys.exit(1)

    return BlindsClient(host=host, login=login, password=password)


def get_all_devices(client: BlindsClient) -> list[dict]:
    """Fetch flat list of all devices."""
    data = client.list_devices()
    devices = []
    for resp in data:
        devices.extend(resp.get("devices", []))
    return devices


def resolve_device_id(client: BlindsClient, name_or_id: str) -> str:
    """Resolve a device name to its ID, or return the ID if already numeric."""
    if name_or_id.isdigit():
        return name_or_id

    for device in get_all_devices(client):
        if device.get("name", "").lower() == name_or_id.lower():
            return str(device["id"])

    click.echo(f"Device '{name_or_id}' not found.", err=True)
    sys.exit(1)


def parse_room(device_name: str) -> str:
    """Extract room name from device name (e.g. 'Salon - Kominek lewo (10)' -> 'salon')."""
    return device_name.split(" - ")[0].strip().lower()


def resolve_room_device_ids(client: BlindsClient, room: str) -> list[str]:
    """Find all device IDs belonging to a room (matched by name prefix)."""
    devices = get_all_devices(client)
    room_lower = room.lower()
    ids = [str(d["id"]) for d in devices if parse_room(d["name"]) == room_lower]
    if not ids:
        available = sorted(set(parse_room(d["name"]) for d in devices))
        click.echo(f"Room '{room}' not found. Available rooms:", err=True)
        for r in available:
            click.echo(f"  - {r}", err=True)
        sys.exit(1)
    return ids


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging (shows all MQTT messages, encryption, etc.)")
def cli(verbose):
    """electric-eye: control your Mobilus blinds."""
    setup_logging(verbose)


@cli.group()
def blinds():
    """Manage Mobilus blinds."""
    pass


@blinds.command("list")
def blinds_list():
    """List all paired devices."""
    client = get_blinds_client()
    devices = get_all_devices(client)
    for d in devices:
        click.echo(f"  [{d['id']:>2}] {d['name']}  (type={d['type']})")


@blinds.command("rooms")
def blinds_rooms():
    """List all rooms and their devices."""
    client = get_blinds_client()
    devices = get_all_devices(client)
    rooms: dict[str, list[dict]] = {}
    for d in devices:
        room = parse_room(d["name"])
        rooms.setdefault(room, []).append(d)
    for room, devs in sorted(rooms.items()):
        click.echo(f"{room}:")
        for d in devs:
            click.echo(f"  [{d['id']:>2}] {d['name']}")
        click.echo()


@blinds.command("status")
def blinds_status():
    """Get current state of all devices."""
    client = get_blinds_client()
    data = client.get_state()
    click.echo(json.dumps(data, indent=2))


@blinds.command()
@click.argument("device")
def up(device):
    """Open a blind. DEVICE can be a name or numeric ID."""
    client = get_blinds_client()
    device_id = resolve_device_id(client, device)
    data = client.control(device_id, "UP")
    click.echo(json.dumps(data, indent=2))


@blinds.command()
@click.argument("device")
def down(device):
    """Close a blind. DEVICE can be a name or numeric ID."""
    client = get_blinds_client()
    device_id = resolve_device_id(client, device)
    data = client.control(device_id, "DOWN")
    click.echo(json.dumps(data, indent=2))


@blinds.command()
@click.argument("device")
def stop(device):
    """Stop a blind. DEVICE can be a name or numeric ID."""
    client = get_blinds_client()
    device_id = resolve_device_id(client, device)
    data = client.control(device_id, "STOP")
    click.echo(json.dumps(data, indent=2))


@blinds.command("set")
@click.argument("device")
@click.argument("percent", type=int)
def set_position(device, percent):
    """Set blind to a specific position (0-100%). DEVICE can be a name or numeric ID."""
    if not 0 <= percent <= 100:
        click.echo("Percent must be 0-100.", err=True)
        sys.exit(1)

    client = get_blinds_client()
    device_id = resolve_device_id(client, device)
    data = client.control(device_id, f"{percent}%")
    click.echo(json.dumps(data, indent=2))


@blinds.command("room-up")
@click.argument("room")
def room_up(room):
    """Open all blinds in a room (single connection)."""
    client = get_blinds_client()
    ids = resolve_room_device_ids(client, room)
    click.echo(f"Opening {len(ids)} device(s) in '{room}'...")
    data = client.control_many(ids, "UP")
    click.echo(json.dumps(data, indent=2))


@blinds.command("room-down")
@click.argument("room")
def room_down(room):
    """Close all blinds in a room (single connection)."""
    client = get_blinds_client()
    ids = resolve_room_device_ids(client, room)
    click.echo(f"Closing {len(ids)} device(s) in '{room}'...")
    data = client.control_many(ids, "DOWN")
    click.echo(json.dumps(data, indent=2))


@blinds.command("room-stop")
@click.argument("room")
def room_stop(room):
    """Stop all blinds in a room."""
    client = get_blinds_client()
    ids = resolve_room_device_ids(client, room)
    click.echo(f"Stopping {len(ids)} device(s) in '{room}'...")
    data = client.control_many(ids, "STOP")
    click.echo(json.dumps(data, indent=2))


@blinds.command("room-set")
@click.argument("room")
@click.argument("percent", type=int)
def room_set(room, percent):
    """Set all blinds in a room to a position (0-100%)."""
    if not 0 <= percent <= 100:
        click.echo("Percent must be 0-100.", err=True)
        sys.exit(1)

    client = get_blinds_client()
    ids = resolve_room_device_ids(client, room)
    click.echo(f"Setting {len(ids)} device(s) in '{room}' to {percent}%...")
    data = client.control_many(ids, f"{percent}%")
    click.echo(json.dumps(data, indent=2))


@blinds.command("all-up")
def all_up():
    """Open all blinds in the house (single connection)."""
    client = get_blinds_client()
    devices = get_all_devices(client)
    ids = [str(d["id"]) for d in devices]
    click.echo(f"Opening all {len(ids)} device(s)...")
    data = client.control_many(ids, "UP")
    click.echo(json.dumps(data, indent=2))


@blinds.command("all-down")
def all_down():
    """Close all blinds in the house (single connection)."""
    client = get_blinds_client()
    devices = get_all_devices(client)
    ids = [str(d["id"]) for d in devices]
    click.echo(f"Closing all {len(ids)} device(s)...")
    data = client.control_many(ids, "DOWN")
    click.echo(json.dumps(data, indent=2))


@cli.command()
@click.option("--host", default="127.0.0.1", help="Address to bind")
@click.option("--port", default=8000, type=int, help="Port to bind")
@click.option("--reload", is_flag=True, help="Auto-reload on code changes (dev)")
def web(host, port, reload):
    """Run the localhost webapp to control blinds."""
    import uvicorn
    click.echo(f"electric-eye web on http://{host}:{port}")
    uvicorn.run("electric_eye.web:app", host=host, port=port, reload=reload)


@cli.command()
@click.option("--listen-host", default="0.0.0.0", help="Address to listen on")
@click.option("--listen-port", default=8884, type=int, help="Port to listen on")
@click.option("--gateway-host", default=None, help="Gateway IP (default: MOBILUS_HOST from .env)")
@click.option("--gateway-port", default=8884, type=int, help="Gateway port")
def proxy(listen_host, listen_port, gateway_host, gateway_port):
    """MITM proxy — intercept and decode Mobilus Dom app traffic.

    Decrypts all MQTT messages between the mobile app and the gateway.
    Point the mobile app at this machine's IP to capture traffic.
    """
    import asyncio
    from electric_eye.proxy import run_proxy

    setup_logging(verbose=True)

    if gateway_host is None:
        gateway_host = os.environ.get("MOBILUS_HOST")
    password = os.environ.get("MOBILUS_PASSWORD")

    if not gateway_host or not password:
        click.echo("Need MOBILUS_HOST and MOBILUS_PASSWORD (from .env or --gateway-host)", err=True)
        sys.exit(1)

    click.echo(f"Proxy: {listen_host}:{listen_port} -> {gateway_host}:{gateway_port}")
    click.echo("Point the Mobilus Dom app at this machine's IP to intercept traffic.")
    click.echo("Press Ctrl+C to stop.\n")

    asyncio.run(run_proxy(listen_host, listen_port, gateway_host, gateway_port, password))
