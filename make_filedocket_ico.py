#!/usr/bin/env python3
"""Write filedocket.ico from the menu-bar PNG (PNG-inside-ICO)."""
from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "filedocket.ico"
SRC = ROOT / "status_iconTemplate@2x.png"
if not SRC.is_file():
    SRC = ROOT / "status_iconTemplate.png"


def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{SRC} is not a PNG")
    w, h = struct.unpack(">II", data[16:24])
    return w, h


def main() -> None:
    png = SRC.read_bytes()
    w, h = png_size(png)
    # ICONDIR
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack(
        "<BBBBHHII",
        w if w < 256 else 0,
        h if h < 256 else 0,
        0,
        0,
        1,
        32,
        len(png),
        6 + 16,
    )
    OUT.write_bytes(header + entry + png)
    print(f"wrote {OUT} ({w}x{h}, {len(png)} bytes PNG)")


if __name__ == "__main__":
    main()
