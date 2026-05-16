import asyncio
import logging
import os
from importlib import resources

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from electric_eye.blinds import BlindsClient
from electric_eye.config import load_groups

log = logging.getLogger(__name__)

app = FastAPI(title="electric-eye")


def get_client() -> BlindsClient:
    host = os.environ.get("MOBILUS_HOST")
    login = os.environ.get("MOBILUS_LOGIN")
    password = os.environ.get("MOBILUS_PASSWORD")
    if not (host and login and password):
        raise HTTPException(status_code=500, detail="Missing MOBILUS_HOST/LOGIN/PASSWORD env vars")
    return BlindsClient(host=host, login=login, password=password)


class SetPositionBody(BaseModel):
    percent: int = Field(ge=0, le=100)


@app.get("/")
async def index():
    path = resources.files("electric_eye") / "static" / "index.html"
    return FileResponse(str(path))


@app.get("/api/devices")
async def list_devices():
    client = get_client()
    data = await asyncio.to_thread(client.list_devices)
    devices = []
    for resp in data:
        devices.extend(resp.get("devices", []))
    return devices


@app.get("/api/state")
async def get_state():
    client = get_client()
    data = await asyncio.to_thread(client.get_state)
    state = {}
    for resp in data:
        for evt in resp.get("events", []):
            did = str(evt.get("deviceId", ""))
            if did:
                state[did] = {"value": evt.get("value", "")}
    return state


async def _control(device_id: str, value: str):
    client = get_client()
    try:
        data = await asyncio.to_thread(client.control, device_id, value)
        return {"ok": True, "response": data}
    except Exception as e:
        log.exception("control failed")
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/devices/{device_id}/up")
async def device_up(device_id: str):
    return await _control(device_id, "UP")


@app.post("/api/devices/{device_id}/down")
async def device_down(device_id: str):
    return await _control(device_id, "DOWN")


@app.post("/api/devices/{device_id}/stop")
async def device_stop(device_id: str):
    return await _control(device_id, "STOP")


@app.post("/api/devices/{device_id}/set")
async def device_set(device_id: str, body: SetPositionBody):
    return await _control(device_id, f"{body.percent}%")


# --- Group (room) endpoints ---


def _resolve_group(group_name: str) -> list[str]:
    groups = load_groups()
    if group_name not in groups:
        raise HTTPException(status_code=404, detail=f"Group '{group_name}' not found")
    return groups[group_name]


_device_types_cache: dict[str, int] = {}


async def _get_device_types() -> dict[str, int]:
    """Fetch device types from gateway, cached after first call."""
    global _device_types_cache
    if not _device_types_cache:
        client = get_client()
        data = await asyncio.to_thread(client.list_devices)
        for resp in data:
            for d in resp.get("devices", []):
                _device_types_cache[str(d["id"])] = d.get("type", 1)
    return _device_types_cache


def _map_percent_for_type(percent: int, device_type: int) -> str:
    """Map user-facing percentage to API value based on device type.

    For type 7 (tilt blind), percentage mapping may differ from roller shutters.
    Currently passthrough — adjust after physical experiments with type-7 devices.
    """
    # TODO: After experimenting with type-7 devices, adjust mapping here.
    # For now, all types use the same percentage directly.
    return f"{percent}%"


async def _control_many(device_ids: list[str], value: str):
    client = get_client()
    try:
        # If this is a percentage command and we have mixed types, send per-type values
        if value.endswith("%") and value[:-1].isdigit():
            types = await _get_device_types()
            percent = int(value[:-1])
            has_mixed = len({types.get(did, 1) for did in device_ids}) > 1
            if has_mixed:
                commands = []
                for did in device_ids:
                    dtype = types.get(did, 1)
                    mapped = _map_percent_for_type(percent, dtype)
                    commands.append((did, mapped))
                data = await asyncio.to_thread(
                    client.control_many_varied, commands
                )
                return {"ok": True, "response": data}
        data = await asyncio.to_thread(client.control_many, device_ids, value)
        return {"ok": True, "response": data}
    except Exception as e:
        log.exception("control_many failed")
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/groups")
async def list_groups():
    return load_groups()


@app.post("/api/groups/{group_name}/up")
async def group_up(group_name: str):
    return await _control_many(_resolve_group(group_name), "UP")


@app.post("/api/groups/{group_name}/down")
async def group_down(group_name: str):
    return await _control_many(_resolve_group(group_name), "DOWN")


@app.post("/api/groups/{group_name}/stop")
async def group_stop(group_name: str):
    return await _control_many(_resolve_group(group_name), "STOP")


@app.post("/api/groups/{group_name}/set")
async def group_set(group_name: str, body: SetPositionBody):
    return await _control_many(_resolve_group(group_name), f"{body.percent}%")
