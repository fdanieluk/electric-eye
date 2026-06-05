import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from msmart.device import AirConditioner
from msmart.lan import AuthenticationError

log = logging.getLogger(__name__)

# The AC accepts only one TCP client at a time and is slow to free the slot,
# so we always disconnect after an operation and retry transient timeouts.
_CONNECT_RETRIES = 3
_RETRY_DELAY_S = 1.5

# Re-exported enums so callers (CLI/web) don't import msmart directly.
Mode = AirConditioner.OperationalMode
Fan = AirConditioner.FanSpeed
Swing = AirConditioner.SwingMode

# Keys from msmart's to_dict() that are secrets/noise — never return them.
_HIDDEN_STATE_KEYS = {"token", "key"}


@dataclass
class ACUnit:
    name: str
    ip: str
    device_id: int
    token: str  # hex string from `msmart-ng discover`
    key: str  # hex string from `msmart-ng discover`
    port: int = 6444


def parse_mode(value: str) -> "Mode":
    return Mode[value.upper()]


def parse_fan(value: str) -> "Fan | int":
    """Named speed (silent/low/medium/high/auto/max) or a custom int 1-100."""
    if value.isdigit():
        return int(value)
    return Fan[value.upper()]


def parse_swing(value: str) -> "Swing":
    return Swing[value.upper()]


def _jsonable(value):
    """msmart enums/flags -> readable names so the result is JSON-friendly."""
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _clean(d: dict) -> dict:
    return {k: _jsonable(v) for k, v in d.items() if k not in _HIDDEN_STATE_KEYS}


class ACClient:
    """Stateless async wrapper around msmart-ng for a set of AC units.

    Mirrors BlindsClient: every call opens a fresh authenticated connection.
    Midea control commands carry the *full* device state, so every write does
    refresh() -> mutate -> apply() — skipping the refresh would clobber any
    setting we don't explicitly send back to its default.
    """

    def __init__(self, units: dict[str, ACUnit]) -> None:
        self.units = units

    def unit(self, name: str) -> ACUnit:
        if name not in self.units:
            raise KeyError(f"AC unit '{name}' not found")
        return self.units[name]

    @asynccontextmanager
    async def _device(self, name: str):
        """Authenticated connection that is always closed afterwards.

        Leaving the socket open starves the next connection, so disconnect in
        a finally. Transient auth timeouts are retried with a short backoff.
        """
        u = self.unit(name)
        dev = AirConditioner(ip=u.ip, device_id=u.device_id, port=u.port)
        token, key = bytes.fromhex(u.token), bytes.fromhex(u.key)
        for attempt in range(1, _CONNECT_RETRIES + 1):
            try:
                log.debug("Authenticating with AC '%s' at %s:%d (attempt %d)",
                          name, u.ip, u.port, attempt)
                await dev.authenticate(token, key)
                break
            # A busy unit surfaces a timeout wrapped as AuthenticationError
            # ("No response from host"); genuine bad creds also land here and
            # will simply retry 3x before failing.
            except (AuthenticationError, TimeoutError, OSError) as e:
                if attempt == _CONNECT_RETRIES:
                    raise
                log.debug("AC '%s' connect failed (%s); retrying in %.1fs",
                          name, e, _RETRY_DELAY_S)
                await asyncio.sleep(_RETRY_DELAY_S)
        try:
            yield dev
        finally:
            dev._lan._disconnect()

    async def status(self, name: str) -> dict:
        """All current state of the unit."""
        async with self._device(name) as dev:
            await dev.refresh()
            return _clean(dev.to_dict())

    async def capabilities(self, name: str) -> dict:
        """Everything this unit supports (modes, fan speeds, swing, features)."""
        async with self._device(name) as dev:
            await dev.get_capabilities()
            return _clean(dev.capabilities_dict())

    async def apply(self, name: str, **props) -> dict:
        """Refresh current state, apply property changes, return new state.

        refresh() is mandatory — see class docstring. Pass several props at
        once so one user action is one connection, not one per setting.
        """
        async with self._device(name) as dev:
            await dev.refresh()
            for key, value in props.items():
                setattr(dev, key, value)
            log.debug("Applying to AC '%s': %s", name, props)
            await dev.apply()
            return _clean(dev.to_dict())

    # --- convenience wrappers over apply() ---

    async def set_power(self, name: str, on: bool) -> dict:
        return await self.apply(name, power_state=on)

    async def set_temperature(self, name: str, celsius: float) -> dict:
        return await self.apply(name, target_temperature=celsius)

    async def set_fan_speed(self, name: str, speed) -> dict:
        return await self.apply(name, fan_speed=speed)

    async def set_mode(self, name: str, mode: "Mode") -> dict:
        return await self.apply(name, operational_mode=mode)

    async def set_swing(self, name: str, mode: "Swing") -> dict:
        return await self.apply(name, swing_mode=mode)
