import os
import tomllib
from pathlib import Path


def _resolve_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get("DEVICES_TOML")
    if env:
        return Path(env)
    return Path("devices.toml")


def load_groups(path: str | Path | None = None) -> dict[str, list[str]]:
    """Load [groups] from devices.toml. Returns {group_name: [device_id_str, ...]}."""
    p = _resolve_path(path)
    data = tomllib.loads(p.read_text())
    return {name: [str(i) for i in ids] for name, ids in data.get("groups", {}).items()}


def load_devices(path: str | Path | None = None) -> dict[str, str]:
    """Load [devices] from devices.toml. Returns {device_id_str: device_name}."""
    p = _resolve_path(path)
    data = tomllib.loads(p.read_text())
    return {str(k): v for k, v in data.get("devices", {}).items()}
