import asyncio
import json
import logging
import os
import sys

import click
from dotenv import load_dotenv

from electric_eye.blinds import BlindsClient
from electric_eye.config import load_ac, load_devices, load_group_roles, load_groups

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


def resolve_group(name: str) -> list[str]:
    """Look up a group name in devices.toml, exit with available groups if not found."""
    groups = load_groups()
    if name in groups:
        return groups[name]
    click.echo(f"Group '{name}' not found. Available groups:", err=True)
    for g in groups:
        click.echo(f"  - {g}", err=True)
    sys.exit(1)


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
    """List all groups from devices.toml."""
    groups = load_groups()
    roles = load_group_roles()
    device_names = load_devices()
    for group, ids in groups.items():
        click.echo(f"{group} ({roles.get(group, 'room')}):")
        for did in ids:
            name = device_names.get(did, "?")
            click.echo(f"  [{int(did):>2}] {name}")
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
    """Open all blinds in a group (single connection)."""
    ids = resolve_group(room)
    client = get_blinds_client()
    click.echo(f"Opening {len(ids)} device(s) in '{room}'...")
    data = client.control_many(ids, "UP")
    click.echo(json.dumps(data, indent=2))


@blinds.command("room-down")
@click.argument("room")
def room_down(room):
    """Close all blinds in a group (single connection)."""
    ids = resolve_group(room)
    client = get_blinds_client()
    click.echo(f"Closing {len(ids)} device(s) in '{room}'...")
    data = client.control_many(ids, "DOWN")
    click.echo(json.dumps(data, indent=2))


@blinds.command("room-stop")
@click.argument("room")
def room_stop(room):
    """Stop all blinds in a group."""
    ids = resolve_group(room)
    client = get_blinds_client()
    click.echo(f"Stopping {len(ids)} device(s) in '{room}'...")
    data = client.control_many(ids, "STOP")
    click.echo(json.dumps(data, indent=2))


@blinds.command("room-set")
@click.argument("room")
@click.argument("percent", type=int)
def room_set(room, percent):
    """Set all blinds in a group to a position (0-100%)."""
    if not 0 <= percent <= 100:
        click.echo("Percent must be 0-100.", err=True)
        sys.exit(1)

    ids = resolve_group(room)
    client = get_blinds_client()
    click.echo(f"Setting {len(ids)} device(s) in '{room}' to {percent}%...")
    data = client.control_many(ids, f"{percent}%")
    click.echo(json.dumps(data, indent=2))


@blinds.command("all-up")
def all_up():
    """Open all blinds in the house (single connection)."""
    ids = list(load_devices().keys())
    client = get_blinds_client()
    click.echo(f"Opening all {len(ids)} device(s)...")
    data = client.control_many(ids, "UP")
    click.echo(json.dumps(data, indent=2))


@blinds.command("all-down")
def all_down():
    """Close all blinds in the house (single connection)."""
    ids = list(load_devices().keys())
    client = get_blinds_client()
    click.echo(f"Closing all {len(ids)} device(s)...")
    data = client.control_many(ids, "DOWN")
    click.echo(json.dumps(data, indent=2))


# --- AC (Vivax / Midea LAN) ---


def get_ac_client():
    from electric_eye.ac import ACClient

    units = load_ac()
    if not units:
        click.echo("No AC units configured. Add an [ac.<name>] table to devices.toml.", err=True)
        sys.exit(1)
    return ACClient(units)


def resolve_ac_unit(client, unit: str) -> None:
    if unit in client.units:
        return
    click.echo(f"AC unit '{unit}' not found. Available units:", err=True)
    for name in client.units:
        click.echo(f"  - {name}", err=True)
    sys.exit(1)


def _ac_run(coro):
    """Run an AC coroutine, printing the resulting state as JSON."""
    try:
        result = asyncio.run(coro)
    except Exception as e:
        click.echo(f"AC command failed: {e}", err=True)
        sys.exit(1)
    click.echo(json.dumps(result, indent=2))


@cli.group()
def ac():
    """Manage air conditioners (Vivax / Midea LAN)."""
    pass


@ac.command("list")
def ac_list():
    """List configured AC units."""
    for name, unit in get_ac_client().units.items():
        click.echo(f"  {name:<12} {unit.name:<14} {unit.ip}")


@ac.command("status")
@click.argument("unit")
def ac_status(unit):
    """Show all current state of a unit."""
    client = get_ac_client()
    resolve_ac_unit(client, unit)
    _ac_run(client.status(unit))


@ac.command("capabilities")
@click.argument("unit")
def ac_capabilities(unit):
    """List everything the unit supports (modes, fan speeds, swing, features)."""
    client = get_ac_client()
    resolve_ac_unit(client, unit)
    _ac_run(client.capabilities(unit))


@ac.command("on")
@click.argument("unit")
def ac_on(unit):
    """Turn a unit on."""
    client = get_ac_client()
    resolve_ac_unit(client, unit)
    _ac_run(client.set_power(unit, True))


@ac.command("off")
@click.argument("unit")
def ac_off(unit):
    """Turn a unit off."""
    client = get_ac_client()
    resolve_ac_unit(client, unit)
    _ac_run(client.set_power(unit, False))


@ac.command("set")
@click.argument("unit")
@click.argument("temperature", type=float)
def ac_set(unit, temperature):
    """Set target temperature (°C)."""
    client = get_ac_client()
    resolve_ac_unit(client, unit)
    _ac_run(client.set_temperature(unit, temperature))


@ac.command("fan")
@click.argument("unit")
@click.argument("speed")
def ac_fan(unit, speed):
    """Set fan speed: silent/low/medium/high/auto/max, or a number 1-100."""
    from electric_eye.ac import parse_fan

    client = get_ac_client()
    resolve_ac_unit(client, unit)
    try:
        value = parse_fan(speed)
    except KeyError:
        click.echo("Speed must be silent/low/medium/high/auto/max or a number 1-100.", err=True)
        sys.exit(1)
    _ac_run(client.set_fan_speed(unit, value))


@ac.command("mode")
@click.argument("unit")
@click.argument("mode")
def ac_mode(unit, mode):
    """Set mode: auto/cool/dry/heat/fan_only."""
    from electric_eye.ac import parse_mode

    client = get_ac_client()
    resolve_ac_unit(client, unit)
    try:
        value = parse_mode(mode)
    except KeyError:
        click.echo("Mode must be auto/cool/dry/heat/fan_only.", err=True)
        sys.exit(1)
    _ac_run(client.set_mode(unit, value))


@ac.command("swing")
@click.argument("unit")
@click.argument("mode")
def ac_swing(unit, mode):
    """Set swing: off/vertical/horizontal/both."""
    from electric_eye.ac import parse_swing

    client = get_ac_client()
    resolve_ac_unit(client, unit)
    try:
        value = parse_swing(mode)
    except KeyError:
        click.echo("Swing must be off/vertical/horizontal/both.", err=True)
        sys.exit(1)
    _ac_run(client.set_swing(unit, value))


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
