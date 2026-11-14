"""Download and checksum-verify the large public NASA/NAIF runtime assets.

Used by the Render build so source control stays compact while the deployed
science API still has the official LOLA tiles and DE440 lunar orientation PCK.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_PATH = ROOT / "data" / "terrain" / "lola" / "provenance.json"
KERNEL_ASSETS = (
    (
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_de440_250416.tf",
        ROOT / "kernels" / "moon_de440_250416.tf",
        "a47c71e9c9f33796bdafb2c9d69a7ee447b6016ecad80f71cd6f3e479f9cf768",
        19_478,
    ),
    (
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de440_200625.bpc",
        ROOT / "kernels" / "moon_pa_de440_200625.bpc",
        "60cd55aa401ea2ea97360636f567554bfe4e37bb829f901b4460a455dfaf783f",
        12_863_488,
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path, expected_sha256: str, expected_bytes: int | None = None) -> None:
    if destination.is_file() and _sha256(destination) == expected_sha256:
        print(f"Verified existing asset: {destination.relative_to(ROOT)}")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".download")
    request = urllib.request.Request(url, headers={"User-Agent": "Lunar-Horizon-build/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            digest = hashlib.sha256()
            byte_count = 0
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
                byte_count += len(chunk)
        if digest.hexdigest() != expected_sha256:
            raise RuntimeError(f"Checksum mismatch for {url}")
        if expected_bytes is not None and byte_count != expected_bytes:
            raise RuntimeError(f"Unexpected file size for {url}: {byte_count} bytes")
        os.replace(temporary, destination)
        print(f"Downloaded and verified: {destination.relative_to(ROOT)} ({byte_count:,} bytes)")
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def fetch() -> None:
    manifest = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    for asset in manifest["tiles"]:
        _download(
            asset["url"],
            ROOT / asset["file"],
            asset["sha256"],
            int(asset["bytes"]),
        )
    for url, path, checksum, byte_count in KERNEL_ASSETS:
        _download(url, path, checksum, byte_count)


if __name__ == "__main__":
    fetch()
