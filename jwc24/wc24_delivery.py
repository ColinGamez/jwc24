"""Resolve each WC24 payload's owning title without reading device secrets."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .manifest import ChannelManifest


def envelope_key_paths(
    manifests: Sequence[ChannelManifest], nand_root: Path | None,
) -> dict[str, Path]:
    """Validate private key-file presence/size; never return their contents.

    Payload filenames must be unique because the shared server also supports
    filename-based aliases. Key ownership follows the manifest, including for
    assets and regional payload variants, rather than the requested URL.
    """
    owners: dict[str, ChannelManifest] = {}
    for manifest in manifests:
        for item in (*manifest.tasks, *manifest.assets):
            if item.filename in owners:
                raise ValueError("manifests declare duplicate payload filenames")
            owners[item.filename] = manifest

    result: dict[str, Path] = {}
    checked: set[Path] = set()
    for manifest in manifests:
        for item in (*manifest.tasks, *manifest.assets):
            if item.envelope != "wc24-aes-ofb":
                continue
            if nand_root is None:
                raise ValueError("encrypted WC24 serving requires an explicit NAND root")
            path = (nand_root / "title" / f"{manifest.title_type:08x}" /
                    f"{manifest.title_code:08x}" / "data" / "wc24pubk.mod")
            if path not in checked:
                try:
                    valid = path.is_file() and path.stat().st_size == 544
                except OSError:
                    valid = False
                if not valid:
                    raise ValueError("encrypted WC24 payload owner needs a 544-byte key file")
                checked.add(path)
            result[item.filename] = path
    return result
