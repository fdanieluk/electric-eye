import asyncio
import logging
import os
from importlib import resources

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from electric_eye.blinds import BlindsClient

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
