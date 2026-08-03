from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class Task:
    slot: int
    filename: str
    route: str
    payload: Path
    refresh_minutes: int
    retry_minutes: int
    unsigned: bool
    mode: str
    compression: str
    envelope: str


@dataclass(frozen=True)
class Asset:
    filename: str
    payload: Path
    compression: str
    envelope: str


@dataclass(frozen=True)
class ChannelManifest:
    path: Path
    schema_version: int
    channel_id: str
    name: str
    title_id: int
    system_menu_region: str
    base_url: str
    prune_duplicate_tasks: bool
    tasks: tuple[Task, ...]
    assets: tuple[Asset, ...]

    @property
    def title_type(self) -> int:
        return self.title_id >> 32

    @property
    def title_code(self) -> int:
        return self.title_id & 0xFFFFFFFF


def _required(data: dict[str, Any], key: str, expected: type) -> Any:
    value = data.get(key)
    if not isinstance(value, expected):
        raise ValueError(f"{key!r} must be {expected.__name__}")
    return value


def load_manifest(path: Path) -> ChannelManifest:
    path = path.resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("only manifest schema_version 1 is supported")

    channel_id = _required(data, "channel_id", str)
    if not channel_id or channel_id.upper() != channel_id:
        raise ValueError("channel_id must be a non-empty uppercase ID")
    title_id_text = _required(data, "title_id", str)
    if len(title_id_text) != 16:
        raise ValueError("title_id must contain exactly 16 hexadecimal digits")
    try:
        title_id = int(title_id_text, 16)
    except ValueError as exc:
        raise ValueError("title_id must be hexadecimal") from exc

    region = _required(data, "system_menu_region", str)
    if region != "JPN":
        raise ValueError("this workspace currently accepts JPN manifests only")
    base_url = _required(data, "base_url", str).rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute HTTP(S) URL")
    prune_duplicates = data.get("prune_duplicate_tasks", False)
    if not isinstance(prune_duplicates, bool):
        raise ValueError("prune_duplicate_tasks must be boolean")

    raw_tasks = _required(data, "tasks", list)
    tasks: list[Task] = []
    seen_slots: set[int] = set()
    seen_names: set[str] = set()
    for index, raw in enumerate(raw_tasks):
        if not isinstance(raw, dict):
            raise ValueError(f"tasks[{index}] must be an object")
        slot = _required(raw, "slot", int)
        filename = _required(raw, "filename", str)
        route = _required(raw, "route", str)
        payload_text = _required(raw, "payload", str)
        refresh = _required(raw, "refresh_minutes", int)
        retry = _required(raw, "retry_minutes", int)
        unsigned = raw.get("unsigned", True)
        if not isinstance(unsigned, bool):
            raise ValueError(f"tasks[{index}].unsigned must be boolean")
        mode = raw.get("mode", "create")
        if mode not in {"create", "adopt"}:
            raise ValueError(f"tasks[{index}].mode must be 'create' or 'adopt'")
        compression = raw.get("compression", "none")
        if compression not in {"none", "nintendo-lz10"}:
            raise ValueError(f"tasks[{index}].compression is unsupported")
        envelope = raw.get("envelope", "raw")
        if envelope not in {"raw", "wc24-aes-ofb"}:
            raise ValueError(f"tasks[{index}].envelope is unsupported")
        if envelope == "wc24-aes-ofb" and unsigned:
            raise ValueError(f"tasks[{index}] encrypted WC24 envelope cannot be unsigned")
        if not 0 <= slot < 120 or slot in seen_slots:
            raise ValueError(f"tasks[{index}].slot is duplicate or outside 0..119")
        if not filename or len(filename.encode("ascii")) >= 64 or "/" in filename:
            raise ValueError(f"tasks[{index}].filename is invalid")
        if filename in seen_names:
            raise ValueError(f"duplicate task filename: {filename}")
        if not route.startswith("/") or "?" in route:
            raise ValueError(f"tasks[{index}].route must be an absolute path without a query")
        if refresh <= 0 or retry <= 0:
            raise ValueError(f"tasks[{index}] refresh/retry values must be positive")
        payload = (path.parent / payload_text).resolve()
        tasks.append(
            Task(
                slot,
                filename,
                route,
                payload,
                refresh,
                retry,
                unsigned,
                mode,
                compression,
                envelope,
            )
        )
        seen_slots.add(slot)
        seen_names.add(filename)

    assets: list[Asset] = []
    raw_assets = data.get("assets", [])
    if not isinstance(raw_assets, list):
        raise ValueError("'assets' must be a list")
    for index, raw in enumerate(raw_assets):
        if not isinstance(raw, dict):
            raise ValueError(f"assets[{index}] must be an object")
        filename = _required(raw, "filename", str)
        payload_text = _required(raw, "payload", str)
        compression = raw.get("compression", "none")
        envelope = raw.get("envelope", "raw")
        if not filename or len(filename.encode("ascii")) >= 64 or "/" in filename:
            raise ValueError(f"assets[{index}].filename is invalid")
        if filename in seen_names:
            raise ValueError(f"duplicate task/asset filename: {filename}")
        if compression not in {"none", "nintendo-lz10"}:
            raise ValueError(f"assets[{index}].compression is unsupported")
        if envelope not in {"raw", "wc24-aes-ofb"}:
            raise ValueError(f"assets[{index}].envelope is unsupported")
        assets.append(
            Asset(
                filename,
                (path.parent / payload_text).resolve(),
                compression,
                envelope,
            )
        )
        seen_names.add(filename)

    return ChannelManifest(
        path=path,
        schema_version=1,
        channel_id=channel_id,
        name=_required(data, "name", str),
        title_id=title_id,
        system_menu_region=region,
        base_url=base_url,
        prune_duplicate_tasks=prune_duplicates,
        tasks=tuple(tasks),
        assets=tuple(assets),
    )
