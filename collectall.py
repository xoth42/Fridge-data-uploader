"""
collectall.py -- Read first and last line of ALL files in today's Bluefors
date folder and POST them to dpaste.org for review.

STRICTLY READ-ONLY against the Bluefors logs directory.
No files are created, modified, or locked in the data directory.
All output goes to the script's own directory only.

Run via:  python collectall.py
    or:   powershell -ExecutionPolicy Bypass -File collectall.ps1
"""

import os
import sys
from datetime import date
from pathlib import Path
import urllib.request
import urllib.parse

from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Max file size we will attempt to read (skip anything larger)
# ---------------------------------------------------------------------------
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


def require_env(var: str) -> str:
    """Return an env var value or raise with a clear message."""
    value = os.getenv(var)
    if not value:
        raise ValueError(f"{var} is missing or empty in .env")
    return value


def get_today_folder(logs_dir: Path) -> Path:
    """Find today's YY-MM-DD subfolder inside logs_dir."""
    date_str = date.today().strftime("%y-%m-%d")
    date_dir = logs_dir / date_str
    if not date_dir.exists():
        raise FileNotFoundError(
            f"Today's date folder not found: {date_dir}"
        )
    if not date_dir.is_dir():
        raise NotADirectoryError(
            f"Expected a folder but found a file: {date_dir}"
        )
    return date_dir


def is_likely_binary(filepath: Path) -> bool:
    """
    Quick check: read a small chunk and look for null bytes.
    If found, it is probably a binary file and we should skip it.
    Read-only, minimal handle time.
    """
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(512)
        return b"\x00" in chunk
    except Exception:
        return True  # if we cannot even peek, treat as binary and skip


def read_first_and_last_line(filepath: Path) -> tuple[str, str]:
    """
    Read the first and last non-empty lines of a text file.
    - Opens read-only
    - Replaces bad characters instead of crashing
    - Minimizes time with the file handle open
    - Returns a clear error message if anything goes wrong
    """
    first_line = ""
    last_line = ""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                if not first_line:
                    first_line = stripped
                last_line = stripped
    except PermissionError:
        return ("[PERMISSION DENIED -- skipped]", "")
    except OSError as exc:
        return (f"[OS ERROR: {exc}]", "")
    except Exception as exc:
        return (f"[ERROR reading file: {exc}]", "")

    if not first_line:
        return ("[EMPTY FILE]", "")

    return (first_line, last_line)


def collect_all_files(date_dir: Path) -> str:
    """Build a verbose report of every file in the date folder. Read-only."""
    try:
        files = sorted(os.listdir(date_dir))
    except PermissionError:
        raise PermissionError(
            f"Cannot list directory (permission denied): {date_dir}"
        )

    lines: list[str] = []

    lines.append("=" * 72)
    lines.append("  BLUEFORS DATA COLLECTION REPORT")
    lines.append(f"  Date folder: {date_dir}")
    lines.append(f"  Date: {date.today().isoformat()}")
    lines.append(f"  Total files found: {len(files)}")
    lines.append("=" * 72)
    lines.append("")

    for i, filename in enumerate(files, 1):
        filepath = date_dir / filename

        # Skip subdirectories
        if not filepath.is_file():
            lines.append(f"[{i:03d}] SKIP (not a file): {filename}")
            lines.append("")
            continue

        # Get file size safely
        try:
            size = filepath.stat().st_size
        except OSError as exc:
            lines.append(f"[{i:03d}] File: {filename}")
            lines.append(f"      ERROR: Cannot stat file: {exc}")
            lines.append("")
            continue

        # Skip files that are too large
        if size > MAX_FILE_SIZE_BYTES:
            lines.append(f"[{i:03d}] File: {filename}")
            lines.append(f"      Size: {size} bytes")
            lines.append(f"      SKIPPED: File exceeds {MAX_FILE_SIZE_BYTES} byte limit")
            lines.append("")
            continue

        # Skip empty files
        if size == 0:
            lines.append(f"[{i:03d}] File: {filename}")
            lines.append(f"      Size: 0 bytes")
            lines.append(f"      SKIPPED: Empty file")
            lines.append("")
            continue

        # Skip binary files
        if is_likely_binary(filepath):
            lines.append(f"[{i:03d}] File: {filename}")
            lines.append(f"      Size: {size} bytes")
            lines.append(f"      SKIPPED: Appears to be a binary file")
            lines.append("")
            continue

        # Read first and last lines
        first, last = read_first_and_last_line(filepath)

        lines.append(f"[{i:03d}] File: {filename}")
        lines.append(f"      Size: {size} bytes")
        lines.append(f"      FIRST LINE: {first}")
        if last and last != first:
            lines.append(f"      LAST  LINE: {last}")
        elif last == first:
            lines.append(f"      LAST  LINE: (same as first -- single line file)")
        else:
            lines.append(f"      LAST  LINE: (empty)")
        lines.append("")

    lines.append("=" * 72)
    lines.append("  END OF REPORT")
    lines.append("=" * 72)

    return "\n".join(lines)


def post_to_dpaste(content: str) -> str:
    """
    POST the report to dpaste.org and return the URL.
    dpaste.org is a simple, free paste service -- no account needed.
    """
    data = urllib.parse.urlencode({
        "content": content,
        "syntax": "text",
        "expiry_days": 7,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://dpaste.org/api/",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        url = resp.read().decode("utf-8").strip().strip('"')
    return url


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    env_file = script_dir / ".env"

    # ---- Phase 1: Load config ----
    try:
        if not env_file.exists():
            raise FileNotFoundError(f".env not found at {env_file}")
        load_dotenv(dotenv_path=env_file)
        logs_dir = Path(require_env("FRIGE_LOGS_DIR")).expanduser().resolve()
    except Exception as exc:
        print(f"CONFIG ERROR: {exc}")
        return 1

    # ---- Phase 2: Find today's folder ----
    try:
        date_dir = get_today_folder(logs_dir)
    except Exception as exc:
        print(f"FOLDER ERROR: {exc}")
        return 1

    print(f"Found date folder: {date_dir}")
    print("")

    # ---- Phase 3: Collect all file data (READ-ONLY) ----
    try:
        report = collect_all_files(date_dir)
    except PermissionError as exc:
        print(f"PERMISSION ERROR: {exc}")
        return 1
    except Exception as exc:
        print(f"COLLECTION ERROR: {exc}")
        return 1

    # ---- Phase 4: Print to console ----
    print(report)
    print("")

    # ---- Phase 5: Save a local copy (in script dir, NOT data dir) ----
    report_file = script_dir / "collectall_report.txt"
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report saved locally: {report_file}")
    except Exception as exc:
        print(f"WARNING: Could not save local copy: {exc}")
        print("(This is non-fatal -- the console output above is the same data)")

    # ---- Phase 6: Post to dpaste for easy sharing ----
    print("")
    print("Attempting to post to dpaste.org for easy sharing...")
    try:
        url = post_to_dpaste(report)
        print(f"Report posted to: {url}")
        print("(Link expires in 7 days)")
    except urllib.error.URLError as exc:
        print(f"WARNING: Could not reach dpaste.org: {exc}")
        print("(No internet access? Use the local file instead.)")
    except Exception as exc:
        print(f"WARNING: dpaste upload failed: {exc}")
        print("(Use the local file or console output above instead.)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())