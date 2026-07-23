from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import tempfile
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen


BASE_URL = "https://bangumi.org/"
USER_AGENT = "JWC24-HBNJ/0.1 (private compatibility project)"
KNOWN_SERVICE_NAMES = {
    # Bangumi truncates both names to the same "TOKYO　.." label in its grid.
    "0x5C38": "TOKYO MX1",
    "0x5C3A": "TOKYO MX2",
}

CHANNEL_PATTERN = re.compile(
    r'<li\b[^>]*class="[^"]*\bjs_channel\b[^"]*\btopmost\b[^"]*"[^>]*>\s*'
    r"<p>(?P<name>.*?)</p>",
    re.IGNORECASE | re.DOTALL,
)
LINE_PATTERN = re.compile(
    r'<ul\b[^>]*id="program_line_(?P<line>\d+)"[^>]*>(?P<body>.*?)</ul>',
    re.IGNORECASE | re.DOTALL,
)
ITEM_PATTERN = re.compile(
    r"<li\b(?P<attrs>[^>]*)>(?P<body>.*?)</li>",
    re.IGNORECASE | re.DOTALL,
)
ANCHOR_PATTERN = re.compile(
    r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
TITLE_PATTERN = re.compile(
    r'<p\b[^>]*class="[^"]*\bprogram_title\b[^"]*"[^>]*>(?P<title>.*?)</p>',
    re.IGNORECASE | re.DOTALL,
)
DETAIL_PATTERN = re.compile(
    r'<p\b[^>]*class="[^"]*\bprogram_detail\b[^"]*"[^>]*>(?P<detail>.*?)</p>',
    re.IGNORECASE | re.DOTALL,
)
GENRE_PATTERN = re.compile(r"\bgc-(?P<genre>[a-z0-9_-]+)\b", re.IGNORECASE)

# TV no Tomo stores up to three one-byte genre IDs in each program record.
# Its IDs follow the ARIB main-genre order plus one because zero means unset.
BANGUMI_GENRE_IDS = {
    "news": 1,
    "sports": 2,
    "information": 3,
    "info": 3,
    "drama": 4,
    "music": 5,
    "variety": 6,
    "movie": 7,
    "anime": 8,
    "documentary": 9,
    "theater": 10,
    "education": 11,
    "welfare": 12,
}


def attribute(attrs: str, name: str) -> str:
    match = re.search(
        rf"\b{re.escape(name)}\s*=\s*([\"'])(.*?)\1",
        attrs,
        re.IGNORECASE | re.DOTALL,
    )
    return html.unescape(match.group(2)) if match else ""


def compact_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def wii_safe_text(value: str) -> str:
    """Replace supplementary broadcast symbols unsupported by the Wii font."""
    result: list[str] = []
    for character in value:
        if ord(character) <= 0xFFFF:
            result.append(character)
            continue
        normalized = unicodedata.normalize("NFKC", character)
        if normalized != character and all(ord(item) <= 0xFFFF for item in normalized):
            result.append(f"[{normalized}]")
        # Other supplementary emoji have no reliable equivalent in HBNJ's
        # Wii-era font and are omitted instead of rendering as surrogate ??.
    return re.sub(r"\s+", " ", "".join(result)).strip()


def parse_timestamp(value: str) -> datetime:
    if not re.fullmatch(r"\d{12}", value):
        raise ValueError(f"invalid Bangumi timestamp: {value!r}")
    return datetime.strptime(value, "%Y%m%d%H%M")


def stable_u32(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:4], "big")


def fetch(group_id: int, broadcast_date: str) -> tuple[str, str]:
    url = (
        f"{BASE_URL}epg/td?"
        f"broad_cast_date={broadcast_date}&ggm_group_id={group_id}"
    )
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "identity",
        },
    )
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        source = response.read().decode(charset, errors="strict")
    return url, source


def unique_display_names(names: list[str], service_ids: list[str]) -> list[str]:
    names = [
        KNOWN_SERVICE_NAMES.get(service_id, name)
        for name, service_id in zip(names, service_ids)
    ]
    totals = Counter(names)
    seen: Counter[str] = Counter()
    result = []
    for name, service_id in zip(names, service_ids):
        seen[name] += 1
        if totals[name] == 1:
            result.append(name)
        else:
            result.append(f"{name} ({seen[name]})")
    if len(set(result)) != len(result):
        raise ValueError("could not disambiguate duplicate channel names")
    return result


def parse_region(
    source: str,
    *,
    group_id: int,
    area_id: int,
    area_name: str,
    prefecture_raw: int,
    source_url: str,
) -> dict[str, object]:
    names = [
        re.sub(r"^\d+\s*", "", compact_text(match.group("name"))).strip()
        for match in CHANNEL_PATTERN.finditer(source)
    ]
    lines = {int(match.group("line")): match.group("body") for match in LINE_PATTERN.finditer(source)}
    if not names or len(lines) != len(names):
        raise ValueError(f"channel/line mismatch: names={len(names)} lines={len(lines)}")

    parsed_lines: list[tuple[str, list[dict[str, object]]]] = []
    for line_number, name in enumerate(names, start=1):
        programs: list[dict[str, object]] = []
        service_ids: set[str] = set()
        for item in ITEM_PATTERN.finditer(lines[line_number]):
            attrs = item.group("attrs")
            start_raw = attribute(attrs, "s")
            end_raw = attribute(attrs, "e")
            source_event_id = attribute(attrs, "se-id")
            if not start_raw or not end_raw or not source_event_id:
                continue
            service_id = source_event_id.split("-", 1)[0]
            start = parse_timestamp(start_raw)
            end = parse_timestamp(end_raw)
            if end <= start:
                raise ValueError(
                    f"non-positive window on line {line_number}: {start_raw}..{end_raw}"
                )
            service_ids.add(service_id)

            anchor = ANCHOR_PATTERN.search(item.group("body"))
            anchor_attrs = anchor.group("attrs") if anchor else ""
            anchor_body = anchor.group("body") if anchor else item.group("body")
            metadata_text = attribute(anchor_attrs, "data-content")
            metadata: dict[str, object] = {}
            if metadata_text:
                metadata = json.loads(metadata_text)
            title_match = TITLE_PATTERN.search(anchor_body)
            title = str(metadata.get("title") or "")
            if not title and title_match:
                title = compact_text(title_match.group("title"))
            if not title:
                raise ValueError(f"missing program title on line {line_number}")
            title = wii_safe_text(title)
            if not title:
                # Bangumi occasionally publishes placeholder events whose
                # title contains only full-width spaces.
                title = "番組情報なし"
            detail_match = DETAIL_PATTERN.search(anchor_body)
            description = (
                compact_text(detail_match.group("detail")) if detail_match else ""
            )
            description = wii_safe_text(description)
            genre_match = GENRE_PATTERN.search(item.group("body"))
            source_genre = genre_match.group("genre").lower() if genre_match else ""
            genre_id = BANGUMI_GENRE_IDS.get(source_genre, 0)
            href = attribute(anchor_attrs, "href")
            content_id = str(metadata.get("contentsId") or "")
            program_id = str(metadata.get("programId") or attribute(attrs, "pid"))
            identity = content_id or f"{service_id}:{start_raw}:{program_id}:{title}"
            programs.append(
                {
                    "id": stable_u32(f"{group_id}:{service_id}:{identity}"),
                    "source_content_id": content_id,
                    "source_program_id": program_id,
                    "source_event_id": source_event_id,
                    "title": title,
                    "description": description,
                    "genre_id": genre_id,
                    "source_genre": source_genre or "none",
                    "start": start.isoformat(timespec="minutes"),
                    "end": end.isoformat(timespec="minutes"),
                    "source_url": urljoin(BASE_URL, href),
                }
            )
        if not programs:
            raise ValueError(f"line {line_number} ({name}) has no programs")
        if len(service_ids) != 1:
            raise ValueError(
                f"line {line_number} ({name}) has mixed service IDs: {sorted(service_ids)}"
            )
        parsed_lines.append((next(iter(service_ids)), programs))

    service_ids = [service_id for service_id, _ in parsed_lines]
    if len(set(service_ids)) != len(service_ids):
        raise ValueError("the page repeats a service identity on multiple lines")
    display_names = unique_display_names(names, service_ids)

    channels: list[dict[str, object]] = []
    output_programs: list[dict[str, object]] = []
    for index, ((service_id, programs), display_name) in enumerate(
        zip(parsed_lines, display_names),
        start=1,
    ):
        channel_id = area_id * 100 + index
        channels.append(
            {
                "id": channel_id,
                "service_id": service_id,
                "name": display_name,
                "network": display_name,
            }
        )
        previous_end: datetime | None = None
        for program in sorted(programs, key=lambda item: str(item["start"])):
            start = datetime.fromisoformat(str(program["start"]))
            end = datetime.fromisoformat(str(program["end"]))
            if previous_end is not None and start < previous_end:
                raise ValueError(
                    f"overlap for {service_id}: {start.isoformat()} < {previous_end.isoformat()}"
                )
            previous_end = end
            output_programs.append({**program, "channel_id": channel_id})

    return {
        "status": "ok",
        "format": "jwc24_hbnj_guide_v1",
        "source": "bangumi.org",
        "source_url": source_url,
        "bangumi_group_id": group_id,
        "area": {
            "id": area_id,
            "name": area_name,
            "prefecture_raw": prefecture_raw,
            "channel_ids": [int(channel["id"]) for channel in channels],
        },
        "channels": channels,
        "programs": output_programs,
    }


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        delete=False,
    ) as temporary:
        temporary.write(text)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect one strict HBNJ guide region.")
    parser.add_argument("--group-id", type=int, required=True)
    parser.add_argument("--date", required=True, help="Broadcast date in YYYYMMDD form")
    parser.add_argument("--area-id", type=int, required=True)
    parser.add_argument("--area-name", required=True)
    parser.add_argument("--prefecture-raw", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not re.fullmatch(r"\d{8}", args.date):
        raise SystemExit("--date must use YYYYMMDD")
    source_url, source = fetch(args.group_id, args.date)
    payload = parse_region(
        source,
        group_id=args.group_id,
        area_id=args.area_id,
        area_name=args.area_name,
        prefecture_raw=args.prefecture_raw,
        source_url=source_url,
    )
    atomic_json(args.out, payload)
    print(
        f"wrote {args.out}: channels={len(payload['channels'])} "
        f"programs={len(payload['programs'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
