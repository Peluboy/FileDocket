#!/usr/bin/env python3
"""
Downloads organizer  (v3 — safe)

Sorts loose files into flat, type-based folders:
  Images, Documents, Videos, Audio, Archives, Installers, Code, Design, Fonts, Other

SAFETY RULES (the important part):
  * Only ever touches LOOSE FILES sitting directly in the top level of a root.
  * NEVER opens, descends into, moves, empties, or deletes any folder.
    Your extracted packs / project folders are always left completely alone.
  * Skips in-progress downloads (.crdownload, .part, ...) and hidden files.
  * Re-checks freshly-changed files a few times before moving (still writing?).
  * Never overwrites: name collisions get " (1)", " (2)", ...
  * --dry-run shows what WOULD happen without moving anything.

Usage:
  python3 organize_downloads.py --dry-run        # preview
  python3 organize_downloads.py                  # organize ~/Downloads
  python3 organize_downloads.py --path ~/Desktop # a different/extra root
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

# ---- Configuration -------------------------------------------------------

DEFAULT_ROOTS = [Path.home() / "Downloads"]

EXT_MAP = {}


def _reg(top, exts):
    for e in exts:
        EXT_MAP[e] = top


_reg("Images", ["png", "jpg", "jpeg", "gif", "webp", "heic", "heif", "bmp",
                "tiff", "tif", "svg", "ico", "avif"])
_reg("Design", ["psd", "ai", "eps", "indd", "sketch", "fig", "xd",
                "afdesign", "afphoto", "afpub"])
_reg("Documents", ["pdf", "doc", "docx", "txt", "rtf", "md", "odt", "pages",
                   "csv", "tsv", "xls", "xlsx", "ods", "numbers",
                   "ppt", "pptx", "odp", "key", "epub", "mobi"])
_reg("Videos", ["mp4", "mov", "avi", "mkv", "webm", "m4v", "flv", "wmv",
                "mpg", "mpeg"])
_reg("Audio", ["mp3", "wav", "aac", "flac", "m4a", "ogg", "opus", "aiff", "wma"])
_reg("Archives", ["zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz", "iso"])
_reg("Installers", ["dmg", "pkg", "app", "deb", "rpm", "exe", "msi"])
_reg("Code", ["html", "htm", "css", "js", "jsx", "ts", "tsx", "json", "xml",
              "yml", "yaml", "py", "rb", "go", "rs", "java", "c", "cpp", "h",
              "sh", "sql", "php", "swift"])
_reg("Fonts", ["ttf", "otf", "woff", "woff2", "eot"])

OTHER = "Other"
MANAGED = set(EXT_MAP.values()) | {OTHER}

IN_PROGRESS_SUFFIXES = {
    ".crdownload", ".part", ".partial", ".download", ".tmp", ".opdownload",
}

STABILITY_SECONDS = 4
RETRY_ROUNDS = 5
RETRY_WAIT = 2

# ---- Logic ---------------------------------------------------------------


def category_for(path: Path) -> str:
    return EXT_MAP.get(path.suffix.lower().lstrip("."), OTHER)


def skip_reason(path: Path) -> Optional[str]:
    """Permanent reasons to skip. Directories are ALWAYS skipped here."""
    if path.name.startswith("."):
        return "hidden"
    if path.is_dir():
        return "folder (never touched)"
    if path.suffix.lower() in IN_PROGRESS_SUFFIXES:
        return "download in progress"
    return None


def is_stable(path: Path, now: float) -> bool:
    try:
        return now - path.stat().st_mtime >= STABILITY_SECONDS
    except FileNotFoundError:
        return False


def unique_destination(dest_dir: Path, filename: str) -> Path:
    target = dest_dir / filename
    if not target.exists():
        return target
    stem, suffix = Path(filename).stem, Path(filename).suffix
    n = 1
    while True:
        cand = dest_dir / f"{stem} ({n}){suffix}"
        if not cand.exists():
            return cand
        n += 1


def plan_root(root: Path) -> Tuple[List[Tuple[Path, str]], List[Path]]:
    """Return (moves, deferred). moves = [(src, category)]. TOP LEVEL ONLY."""
    moves, deferred = [], []
    now = time.time()
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if skip_reason(entry) is not None:
            continue                      # folders and everything unsafe: left alone
        if not is_stable(entry, now):
            deferred.append(entry)
            continue
        moves.append((entry, category_for(entry)))
    return moves, deferred


def organize_root(root: Path, dry_run: bool, stats: dict):
    moves, deferred = plan_root(root)
    _apply(root, moves, dry_run, stats)

    rounds = 1 if dry_run else RETRY_ROUNDS
    for r in range(rounds):
        if not deferred:
            break
        if dry_run:
            stats["skipped"] += len(deferred)
            break
        time.sleep(RETRY_WAIT)
        moves, deferred = plan_root(root)
        _apply(root, moves, dry_run, stats)
    else:
        stats["skipped"] += len(deferred)


def _apply(root: Path, moves, dry_run: bool, stats: dict):
    for src, category in moves:
        if not src.exists() or src.is_dir():   # belt-and-suspenders: never a folder
            continue
        stats["by_cat"][category] = stats["by_cat"].get(category, 0) + 1
        stats["moved"] += 1
        if dry_run:
            continue
        dest_dir = root / category
        dest_dir.mkdir(exist_ok=True)
        dest = unique_destination(dest_dir, src.name)
        try:
            shutil.move(str(src), str(dest))
        except Exception as e:  # noqa: BLE001
            print(f"  ! failed to move {src.name}: {e}", file=sys.stderr)
            stats["moved"] -= 1
            stats["by_cat"][category] -= 1


def main(args_list: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Safely organize loose files by type.")
    ap.add_argument("--dry-run", action="store_true", help="Preview without moving.")
    ap.add_argument("--path", action="append", help="Root(s) to organize (repeatable).")
    args = ap.parse_args(args_list)

    roots = [Path(p).expanduser() for p in args.path] if args.path else DEFAULT_ROOTS
    roots = [r for r in roots if r.is_dir()]

    stats = {"moved": 0, "skipped": 0, "by_cat": {}}
    for root in roots:
        organize_root(root, args.dry_run, stats)

    head = "DRY RUN — nothing moved" if args.dry_run else "Organized"
    print(f"\n{head}: {', '.join(str(r) for r in roots)}")
    print("-" * 46)
    for cat in sorted(stats["by_cat"]):
        print(f"  {cat:14} {stats['by_cat'][cat]:>4}")
    print("-" * 46)
    verb = "would move" if args.dry_run else "moved"
    print(f"Total {verb}: {stats['moved']}   |   skipped: {stats['skipped']}")
    print(f"SUMMARY: {verb} {stats['moved']} file(s)")

    if not args.dry_run:
        try:
            state_dir = Path.home() / ".file-organizer"
            state_dir.mkdir(parents=True, exist_ok=True)
            with open(state_dir / "last_run.json", "w") as f:
                json.dump({
                    "timestamp": time.time(),
                    "moved": stats["moved"],
                    "skipped": stats["skipped"],
                    "by_cat": stats["by_cat"]
                }, f)
        except Exception as e:
            print(f"Error saving state: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
