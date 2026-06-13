import tomllib
from pathlib import Path


def _resolve_path(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else Path("devices.toml")


VALID_GROUP_ROLES = ("room", "floor", "tag")
_DEFAULT_ROLE = "room"


def _group_devices(entry) -> list[str]:
    """Device IDs from a [groups] entry: inline-table {devices=[...]} or a bare list."""
    ids = entry["devices"] if isinstance(entry, dict) else entry
    return [str(i) for i in ids]


def load_groups(path: str | Path | None = None) -> dict[str, list[str]]:
    """Load [groups] membership. Returns {group_name: [device_id_str, ...]}.

    Role lives on each group too (see load_group_roles); this returns membership
    only, so the shape is stable for callers that just resolve a group's devices.
    """
    p = _resolve_path(path)
    data = tomllib.loads(p.read_text())
    return {name: _group_devices(entry) for name, entry in data.get("groups", {}).items()}


def load_group_roles(path: str | Path | None = None) -> dict[str, str]:
    """Load each group's declared role from [groups]. Returns {group_name: role}.

    Inline-table entries declare `role` explicitly; a bare list (legacy form) or a
    missing role defaults to "room". Raises ValueError on an unknown role.
    """
    p = _resolve_path(path)
    data = tomllib.loads(p.read_text())
    roles = {}
    for name, entry in data.get("groups", {}).items():
        role = entry.get("role", _DEFAULT_ROLE) if isinstance(entry, dict) else _DEFAULT_ROLE
        if role not in VALID_GROUP_ROLES:
            raise ValueError(
                f"Group '{name}' has invalid role '{role}'; "
                f"expected one of {', '.join(VALID_GROUP_ROLES)}."
            )
        roles[name] = role
    return roles


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
