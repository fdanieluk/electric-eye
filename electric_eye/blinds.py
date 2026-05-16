import json
import logging
import time
from dataclasses import dataclass

from mobilus_client.app import App
from mobilus_client.config import Config

log = logging.getLogger(__name__)


@dataclass
class BlindsClient:
    host: str
    login: str
    password: str

    def _call(self, commands: list[tuple[str, dict[str, str]]]) -> list[dict]:
        log.debug("Connecting to gateway at %s:%d", self.host, 8884)
        log.debug("Login: %s", self.login)
        log.debug("Commands: %s", commands)

        config = Config(
            gateway_host=self.host,
            user_login=self.login,
            user_password=self.password,
        )
        log.debug("Config: host=%s, port=%d, protocol=%s, timeout=%.1fs",
                   config.gateway_host, config.gateway_port,
                   config.gateway_protocol, config.timeout_period)

        app = App(config)
        t0 = time.monotonic()
        raw = app.call(commands)
        elapsed = time.monotonic() - t0

        log.debug("Raw response (%0.2fs): %s", elapsed, raw)
        return json.loads(raw) if raw else []

    def list_devices(self) -> list[dict]:
        return self._call([("devices_list", {})])

    def get_state(self) -> list[dict]:
        return self._call([("current_state", {})])

    def control(self, device_id: str, value: str) -> list[dict]:
        return self._call([("call_events", {"device_id": device_id, "value": value})])

    def control_many(self, device_ids: list[str], value: str) -> list[dict]:
        commands = [("call_events", {"device_id": did, "value": value}) for did in device_ids]
        log.debug("Batching %d commands in one connection", len(commands))
        return self._call(commands)

    def control_many_varied(self, commands: list[tuple[str, str]]) -> list[dict]:
        """Send different values to different devices in one connection.
        commands: [(device_id, value), ...]
        """
        calls = [("call_events", {"device_id": did, "value": val}) for did, val in commands]
        log.debug("Batching %d varied commands in one connection", len(calls))
        return self._call(calls)
