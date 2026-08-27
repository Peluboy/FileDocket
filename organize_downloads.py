#!/usr/bin/env python3
"""
FileDocket — safe file organizer

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

Every move is recorded in ~/.file-organizer/history.json so the GUI can offer a one-click
undo. Extra folders chosen in the menu-bar app (~/.file-organizer/settings.json) are always
sorted too, in addition to ~/Downloads.

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

# User data lives under ~/.file-organizer alongside the existing logs/state.
STATE_DIR = Path.home() / ".file-organizer"
SETTINGS_FILE = STATE_DIR / "settings.json"
HISTORY_FILE = STATE_DIR / "history.json"
HISTORY_LIMIT = 200
COOLDOWN_FILE = STATE_DIR / "undo_cooldown.json"
COOLDOWN_MINUTES = 5  # recently undone files are excluded from auto-organize for this long

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


# ---- User settings (extra folders + rules) ------------------------------

def load_settings() -> dict:
    """Full settings dict: {'extra_roots': [...], 'rules': [...]}."""
    try:
        data = json.loads(SETTINGS_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(data: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:  # noqa: BLE001
        print(f"! error saving settings: {e}", file=sys.stderr)


def load_extra_roots() -> List[Path]:
    """Folders (besides Downloads) the user asked to keep organized."""
    data = load_settings()
    out = []
    for raw in data.get("extra_roots", []) or []:
        try:
            p = Path(str(raw)).expanduser()
        except Exception:
            continue
        if p.is_dir() and p not in out:
            out.append(p)
    return out


def save_extra_roots(roots: List[Path]) -> None:
    data = load_settings()
    data["extra_roots"] = [str(p) for p in roots]
    save_settings(data)


def load_rules() -> List[dict]:
    """User-defined rules, e.g. {"match":"suffix","value":"iso","dest":"ISOs"}."""
    data = load_settings()
    return data.get("rules", []) or []


def save_rules(rules: List[dict]) -> None:
    data = load_settings()
    data["rules"] = rules
    save_settings(data)


# ---- Custom rules -------------------------------------------------------

def user_category_for(path: Path) -> Optional[str]:
    """Return a user-defined destination for a file, or None for the default."""
    for r in load_rules():
        dest = r.get("dest")
        if not dest:
            continue
        v = (r.get("value") or "").lower()
        try:
            if r.get("match") == "keyword" and v and v in path.stem.lower():
                return str(dest)
            if (r.get("match") == "suffix" and v and
                    path.suffix.lower().lstrip(".") == v):
                return str(dest)
        except Exception:
            continue
    return None


# ---- Shared: resolve roots ----------------------------------------------

def resolve_roots(args_roots: Optional[List[str]] = None) -> List[Path]:
    """All folders to act on: CLI path(s) (or Downloads) + extras from settings."""
    roots = [Path(p).expanduser() for p in args_roots] if args_roots else list(DEFAULT_ROOTS)
    for extra in load_extra_roots():
        if extra not in roots:
            roots.append(extra)
    return [r for r in roots if r.is_dir()]


# ---- Duplicates ----------------------------------------------------------

def _file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _prefix_hash(path: Path, n: int = 1 << 16) -> str:
    """Quick hash of the first n bytes — a cheap first-pass duplicate check."""
    import hashlib
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        h.update(f.read(n))
    return h.hexdigest()


# ---- Candidates (shallow vs deep) ---------------------------------------

def iter_candidates(root: Path, deep: bool = False):
    """Yield the files a scan should consider inside `root`.

    Shallow (default): only LOOSE files at the top level — category folders are
    never entered, exactly like organizing itself.

    Deep: every file below root (so already-grouped folders get checked too),
    EXCEPT hidden files, in-progress downloads, and FileDocket's own bookkeeping
    folders (_Duplicates, _Old_*) so already-handled copies aren't reported twice.
    """
    if not root.is_dir():
        return
    if not deep:
        for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if skip_reason(entry) is None:
                yield entry
        return
    for entry in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
        if entry.is_dir() or entry.name.startswith("."):
            continue
        if entry.suffix.lower() in IN_PROGRESS_SUFFIXES:
            continue
        parts = entry.relative_to(root).parts
        if len(parts) > 1 and any(p.startswith("_") for p in parts[:-1]):
            continue   # _Duplicates / _Old_* bookkeeping folders
        yield entry


def find_duplicates(roots: List[Path], deep: bool = False) -> List[dict]:
    """Return groups of content-identical files across the roots.

    Pipeline (fast, catches renamed copies too):
      bucket by size → prefix-hash → full sha256 to confirm.
    Each group: {'name','size','hash','files':[...]}. Nothing is changed here.
    Use deep=True to include files inside already-grouped category folders.
    """
    from collections import defaultdict
    size_buckets = defaultdict(list)
    for root in roots:
        for entry in iter_candidates(root, deep):
            try:
                size = entry.stat().st_size
            except Exception:
                continue
            size_buckets[size].append(entry)

    groups = []
    for size, paths in size_buckets.items():
        if len(paths) < 2:
            continue
        prefix_buckets = defaultdict(list)
        for p in paths:
            try:
                prefix_buckets[_prefix_hash(p)].append(p)
            except Exception:
                continue
        for _pre, same in prefix_buckets.items():
            if len(same) < 2:
                continue
            full_buckets = defaultdict(list)
            for p in same:
                try:
                    full_buckets[_file_sha256(p)].append(p)
                except Exception:
                    continue
            for h, match in full_buckets.items():
                if len(match) >= 2:
                    groups.append({"name": match[0].name, "size": size,
                                   "hash": h, "files": match})
    return groups


def move_duplicates(roots: List[Path], dry_run: bool, deep: bool = False) -> dict:
    """Move duplicate copies (all but the first) into <root>/_Duplicates.

    Uses unique_destination so nothing is ever overwritten, and records history
    so the moves can be undone like any other FileDocket move.
    Pass deep=True to include duplicates hiding inside grouped folders.
    """
    stats = {"moved": 0, "groups": 0, "bytes": 0}
    for root in roots:
        if not root.is_dir():
            continue
        groups = find_duplicates([root], deep=deep)
        if not groups:
            continue
        dup_dir = root / "_Duplicates"
        for g in groups:
            stats["groups"] += 1
            keep = g["files"][0]
            for p in g["files"][1:]:
                if p == keep:
                    continue
                if dry_run:
                    stats["moved"] += 1
                    stats["bytes"] += g["size"]
                    continue
                try:
                    dup_dir.mkdir(exist_ok=True)
                    dest = unique_destination(dup_dir, keep.name)
                    shutil.move(str(p), str(dest))
                    record_history(root, p, dest)
                    stats["moved"] += 1
                    stats["bytes"] += g["size"]
                except Exception as e:  # noqa: BLE001
                    print(f"  ! duplicate move failed for {p.name}: {e}",
                          file=sys.stderr)
    return stats


# ---- Space & "old/big" ---------------------------------------------------

def biggest_files(roots: List[Path], n: int = 20, deep: bool = False) -> List[dict]:
    """The n largest files across roots, with category + path.

    Shallow: loose top-level files only. Deep: everything below root
    (excluding FileDocket bookkeeping folders).
    """
    items = []
    for root in roots:
        for entry in iter_candidates(root, deep):
            try:
                size = entry.stat().st_size
            except Exception:
                continue
            items.append({"name": entry.name, "path": str(entry), "size": size,
                          "category": category_for(entry), "root": str(root)})
    items.sort(key=lambda x: x["size"], reverse=True)
    return items[:n]


ARCHIVE_MATCH_CATEGORIES = {"Installers", "Archives"}


def classify_by_category(roots: List[Path], deep: bool = False) -> dict:
    """Total size + count per category across roots.

    Shallow: loose top-level files only. Deep: everything below root.
    """
    totals = {}
    for root in roots:
        for entry in iter_candidates(root, deep):
            try:
                size = entry.stat().st_size
            except Exception:
                continue
            cat = category_for(entry)
            t = totals.setdefault(cat, {"count": 0, "bytes": 0})
            t["count"] += 1
            t["bytes"] += size
    return totals


def archive_old(roots: List[Path], days: int, dry_run: bool) -> dict:
    """Move old Installers/Archives into <root>/_Old_<Category>.

    'Old' = mtime older than 'days'. Never deletes; undoable.
    """
    cutoff = time.time() - days * 86400
    stats = {"moved": 0, "by_cat": {}, "bytes": 0}
    for root in roots:
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if skip_reason(entry) is not None:
                continue
            cat = category_for(entry)
            if cat not in ARCHIVE_MATCH_CATEGORIES:
                continue
            try:
                if entry.stat().st_mtime > cutoff:
                    continue
                size = entry.stat().st_size
            except Exception:
                continue
            stats["moved"] += 1
            stats["by_cat"][cat] = stats["by_cat"].get(cat, 0) + 1
            stats["bytes"] += size
            if dry_run:
                continue
            dest_dir = root / f"_Old_{cat}"
            try:
                dest_dir.mkdir(exist_ok=True)
                dest = unique_destination(dest_dir, entry.name)
                shutil.move(str(entry), str(dest))
                record_history(root, entry, dest)
            except Exception as e:  # noqa: BLE001
                print(f"  ! archive move failed for {entry.name}: {e}",
                      file=sys.stderr)
                stats["moved"] -= 1
                stats["bytes"] -= size
    return stats


# ---- History / undo -----------------------------------------------------

def load_history() -> List[dict]:
    try:
        data = json.loads(HISTORY_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def record_history(root: Path, src: Path, dest: Path) -> None:
    """Append one move to the history file so it can be undone later."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        entries = load_history()
        entries.append({
            "ts": time.time(),
            "root": str(root),
            "orig": src.name,
            "dest": str(dest),
        })
        if len(entries) > HISTORY_LIMIT:
            entries = entries[-HISTORY_LIMIT:]
        HISTORY_FILE.write_text(json.dumps(entries, indent=2))
    except Exception as e:  # noqa: BLE001
        print(f"  ! history not saved: {e}", file=sys.stderr)


def undo_entry(entry: dict) -> bool:
    """Move a filed file back to its original root. Returns True on success.

    Careful: only ever moves the single file that we previously moved — we never
    undo folders or anything we didn't put there.
    """
    try:
        root = Path(entry["root"])
        dest = Path(entry["dest"])
        if dest.is_dir() or not dest.exists():
            return False
        target = unique_destination(root, entry["orig"])
        shutil.move(str(dest), str(target))
    except Exception as e:  # noqa: BLE001
        print(f"  ! undo failed: {e}", file=sys.stderr)
        return False
    return True


def undo_last() -> Optional[dict]:
    """Undo the most recent recorded move; returns the undone entry or None."""
    entries = load_history()
    if not entries:
        return None
    entry = entries[-1]
    if undo_entry(entry):
        try:
            HISTORY_FILE.write_text(json.dumps(entries[:-1], indent=2))
        except Exception:
            pass
        # Add the undone file to cooldown so auto-organize doesn't re-move it
        _add_cooldown(entry.get("orig", ""))
        return entry
    return None


# ---- Cooldown: prevent auto-organize from re-moving recently undone files ----

def _add_cooldown(filename: str) -> None:
    """Record a filename in the cooldown list with current timestamp."""
    try:
        data = {}
        if COOLDOWN_FILE.exists():
            data = json.loads(COOLDOWN_FILE.read_text())
        data[filename] = time.time()
        COOLDOWN_FILE.write_text(json.dumps(data))
    except Exception:
        pass


def _is_on_cooldown(filename: str) -> bool:
    """Return True if this file was recently undone (within COOLDOWN_MINUTES)."""
    try:
        if not COOLDOWN_FILE.exists():
            return False
        data = json.loads(COOLDOWN_FILE.read_text())
        ts = data.get(filename)
        if ts and (time.time() - ts) < COOLDOWN_MINUTES * 60:
            return True
        # Clean up expired entries
        if ts:
            del data[filename]
            COOLDOWN_FILE.write_text(json.dumps(data))
    except Exception:
        pass
    return False


def plan_root(root: Path) -> Tuple[List[Tuple[Path, str]], List[Path]]:
    """Return (moves, deferred). moves = [(src, category)]. TOP LEVEL ONLY."""
    moves, deferred = [], []
    now = time.time()
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if skip_reason(entry) is not None:
            continue                      # folders and everything unsafe: left alone
        if _is_on_cooldown(entry.name):
            continue                      # recently undone: don't re-move
        if not is_stable(entry, now):
            deferred.append(entry)
            continue
        # User rules (keyword/suffix) can override the default category.
        moves.append((entry, user_category_for(entry) or category_for(entry)))
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
            record_history(root, src, dest)
        except Exception as e:  # noqa: BLE001
            print(f"  ! failed to move {src.name}: {e}", file=sys.stderr)
            stats["moved"] -= 1
            stats["by_cat"][category] -= 1


def main(args_list: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="FileDocket — safely organize loose files by type.")
    ap.add_argument("--dry-run", action="store_true", help="Preview without moving.")
    ap.add_argument("--path", action="append", help="Root(s) to act on (repeatable).")
    ap.add_argument("--duplicates", action="store_true",
                    help="Scan for duplicate files and print a report.")
    ap.add_argument("--move-duplicates", action="store_true",
                    help="Move duplicate copies into <root>/_Duplicates.")
    ap.add_argument("--biggest", type=int, metavar="N",
                    help="Print the N largest files.")
    ap.add_argument("--space", action="store_true",
                    help="Print total size + count per category.")
    ap.add_argument("--archive", type=int, metavar="DAYS",
                    help="Move Installers/Archives older than DAYS days into _Old_*.")
    ap.add_argument("--deep", action="store_true",
                    help="Include files inside grouped folders (duplicates, "
                         "biggest, space). Skips FileDocket bookkeeping folders.")
    args = ap.parse_args(args_list)

    roots = resolve_roots(args.path)

    # --- Report-only subcommands -------------------------------------------
    if args.duplicates:
        groups = find_duplicates(roots, deep=args.deep)
        if not groups:
            print("No duplicate files found.")
            return 0
        total = sum((len(g["files"]) - 1) * g["size"] for g in groups)
        print(f"Found {len(groups)} duplicate group(s), "
              f"{sum(len(g['files']) - 1 for g in groups)} duplicate copy/copies "
              f"(~{_human_size(total)}).")
        for g in groups[:20]:
            names = ", ".join(str(f) for f in g["files"])
            print(f"  • {g['name']} ({_human_size(g['size'])})")
            print(f"      {names}")
        return 0

    if args.move_duplicates:
        stats = move_duplicates(roots, args.dry_run, deep=args.deep)
        verb = "Would move" if args.dry_run else "Moved"
        print(f"{verb} {stats['moved']} duplicate copy/copies from "
              f"{stats['groups']} group(s), freeing ~{_human_size(stats['bytes'])}.")
        return 0

    if args.biggest is not None:
        items = biggest_files(roots, max(1, args.biggest), deep=args.deep)
        if not items:
            print("No loose files found.")
            return 0
        print(f"Top {len(items)} largest files:")
        for it in items:
            print(f"  {_human_size(it['size']):>9}  {it['category']:12} {it['name']}")
        return 0

    if args.space:
        totals = classify_by_category(roots, deep=args.deep)
        total_bytes = sum(t["bytes"] for t in totals.values())
        if not totals:
            print("No loose files found.")
            return 0
        print(f"{'Category':12} {'Files':>7} {'Size':>10}")
        for cat in sorted(totals, key=lambda c: -totals[c]["bytes"]):
            t = totals[cat]
            print(f"  {cat:12} {t['count']:>5} {_human_size(t['bytes']):>10}")
        print(f"\nTotal ~{_human_size(total_bytes)}")
        return 0

    if args.archive is not None:
        days = max(1, args.archive)
        stats = archive_old(roots, days, args.dry_run)
        verb = "Would" if args.dry_run else "Moved"
        print(f"{verb} {stats['moved']} old Installer/Archive file(s), "
              f"freeing ~{_human_size(stats['bytes'])}.")
        return 0

    # --- Default: organize --------------------------------------------------
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


def _human_size(n: float) -> str:
    """Format bytes as a friendly size string."""
    try:
        n = float(n)
    except Exception:
        n = 0.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


if __name__ == "__main__":
    raise SystemExit(main())
