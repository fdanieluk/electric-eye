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


def load_ac(path: str | Path | None = None) -> dict:
    """Load [ac.<name>] tables from devices.toml. Returns {name: ACUnit}."""
    from electric_eye.ac import ACUnit  # local import: keeps msmart off the blinds path

    p = _resolve_path(path)
    data = tomllib.loads(p.read_text())
    units = {}
    for name, cfg in data.get("ac", {}).items():
        units[name] = ACUnit(
            name=cfg.get("name", name),
            ip=cfg["ip"],
            device_id=int(cfg["id"]),
            token=cfg["token"],
            key=cfg["key"],
            port=int(cfg.get("port", 6444)),
        )
    return units
