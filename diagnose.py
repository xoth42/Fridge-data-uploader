"""
diagnose.py -- One-shot fridge data structure scanner.

Runs automatically via run_with_git_update.ps1 when the script is present
and .diagnose_done flag does not exist. Creates the flag on completion so
it never runs more than once.

What it does:
  1. Scans the full Bluefors logs directory (all date folders, file listing)
  2. For the most recent date folder: reads first + last line of every file
  3. Posts the full report to dpaste.org
  4. Pushes the dpaste URL back to the Pushgateway as a metric label
     so it can be read from Prometheus/Grafana without remote access:
       fridge_diagnostic_url{instance="fridge-dodo", url="https://dpaste.org/xxx"} 1
  5. Creates .diagnose_done flag — will not run again until flag is deleted

To re-run: delete .diagnose_done from the script directory.

STRICTLY READ-ONLY against the Bluefors logs directory.
"""

import os
import sys
import urllib.request
import urllib.parse
from datetime import date, datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
import logging

from dotenv import load_dotenv
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

SCRIPT_DIR    = Path(__file__).resolve().parent
LOG_FILE      = SCRIPT_DIR / "diagnose.log"
DONE_FLAG     = SCRIPT_DIR / ".diagnose_done"
REPORT_FILE   = SCRIPT_DIR / "diagnose_report.txt"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# Increment this to force a re-run on all machines even if .diagnose_done exists.
DIAGNOSE_VERSION = "3"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(LOG_FILE, encoding="utf-8", maxBytes=1048576, backupCount=2),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    env_file = SCRIPT_DIR / ".env"
    server_env = SCRIPT_DIR / "server.env"
    if not env_file.exists():
        raise FileNotFoundError(f".env not found at {env_file}")
    load_dotenv(dotenv_path=env_file)
    if server_env.exists():
        load_dotenv(dotenv_path=server_env, override=True)
    logs_dir_raw = os.getenv("FRIGE_LOGS_DIR")
    if not logs_dir_raw:
        raise ValueError("FRIGE_LOGS_DIR missing in .env")
    machine_name = os.getenv("MACHINE_NAME", "unknown")
    pushgateway_url = os.getenv("PUSHGATEWAY_URL", "")
    job_name = os.getenv("PUSH_JOB_NAME", "sensor_data")
    return {
        "logs_dir": Path(logs_dir_raw).expanduser().resolve(),
        "machine_name": machine_name,
        "pushgateway_url": pushgateway_url,
        "job_name": job_name,
    }


# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------

def is_likely_binary(filepath: Path) -> bool:
    try:
        with open(filepath, "rb") as f:
            return b"\x00" in f.read(512)
    except Exception:
        return True


def read_first_and_last(filepath: Path) -> tuple[str, str]:
    first, last = "", ""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                if not first:
                    first = s
                last = s
    except PermissionError:
        return "[PERMISSION DENIED]", ""
    except Exception as exc:
        return f"[ERROR: {exc}]", ""
    return (first or "[EMPTY]"), last


def scan_logs_dir(logs_dir: Path) -> str:
    """Scan all date folders and produce a full report."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("  FRIDGE DIAGNOSTIC REPORT")
    lines.append(f"  Generated: {datetime.now().isoformat()}")
    lines.append(f"  Logs root: {logs_dir}")
    lines.append("=" * 72)
    lines.append("")

    if not logs_dir.exists():
        lines.append(f"ERROR: logs_dir does not exist: {logs_dir}")
        return "\n".join(lines)

    # List all date folders
    try:
        all_entries = sorted(logs_dir.iterdir())
    except Exception as exc:
        lines.append(f"ERROR listing logs_dir: {exc}")
        return "\n".join(lines)

    date_folders = [e for e in all_entries if e.is_dir()]
    lines.append(f"Date folders found ({len(date_folders)} total):")
    for folder in date_folders:
        try:
            n_files = sum(1 for _ in folder.iterdir() if _.is_file())
        except Exception:
            n_files = -1
        lines.append(f"  {folder.name}  ({n_files} files)")
    lines.append("")

    if not date_folders:
        lines.append("No date folders found — check FRIGE_LOGS_DIR path.")
        return "\n".join(lines)

    # Full file scan of the most recent folder
    recent = date_folders[-1]
    lines.append("=" * 72)
    lines.append(f"  DETAILED SCAN: {recent.name}  (most recent)")
    lines.append("=" * 72)
    lines.append("")

    try:
        files = sorted(f for f in recent.iterdir() if f.is_file())
    except Exception as exc:
        lines.append(f"ERROR listing folder: {exc}")
        return "\n".join(lines)

    for i, filepath in enumerate(files, 1):
        lines.append(f"[{i:03d}] {filepath.name}")
        try:
            size = filepath.stat().st_size
        except Exception as exc:
            lines.append(f"      ERROR stat: {exc}")
            lines.append("")
            continue

        lines.append(f"      Size: {size:,} bytes")

        if size == 0:
            lines.append("      SKIPPED: empty")
            lines.append("")
            continue
        if size > MAX_FILE_SIZE:
            lines.append("      SKIPPED: too large")
            lines.append("")
            continue
        if is_likely_binary(filepath):
            lines.append("      SKIPPED: binary")
            lines.append("")
            continue

        first, last = read_first_and_last(filepath)
        lines.append(f"      FIRST: {first}")
        if last and last != first:
            lines.append(f"      LAST:  {last}")
        elif last == first:
            lines.append(f"      LAST:  (same as first)")
        lines.append("")

    lines.append("=" * 72)
    lines.append("  END OF REPORT")
    lines.append("=" * 72)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# dpaste upload
# ---------------------------------------------------------------------------

def post_to_dpaste(content: str) -> str:
    data = urllib.parse.urlencode({
        "content": content,
        "syntax":  "text",
        "expiry_days": 7,
    }).encode("utf-8")
    req = urllib.request.Request("https://dpaste.org/api/", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8").strip().strip('"')


# ---------------------------------------------------------------------------
# Push URL back as a Prometheus metric so it's readable without remote access
# ---------------------------------------------------------------------------

def push_url_metric(pushgateway_url: str, job_name: str, machine_name: str, dpaste_url: str) -> None:
    registry = CollectorRegistry()
    g = Gauge(
        "fridge_diagnostic_url",
        "dpaste URL of the one-shot diagnostic report for this fridge",
        ["url"],
        registry=registry,
    )
    g.labels(url=dpaste_url).set(1)
    push_to_gateway(
        pushgateway_url,
        job="diagnostics",
        grouping_key={"instance": machine_name},
        registry=registry,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if DONE_FLAG.exists():
        stored = DONE_FLAG.read_text(encoding="utf-8")
        if f"version={DIAGNOSE_VERSION}" in stored:
            log.info("Diagnostic v%s already run. Increment DIAGNOSE_VERSION to re-run.", DIAGNOSE_VERSION)
            return 0
        log.info("Diagnose version changed — re-running diagnostic.")

    log.info("Starting one-shot diagnostic...")

    try:
        cfg = load_config()
    except Exception as exc:
        log.error("Config error: %s", exc)
        return 1

    log.info("Machine: %s", cfg["machine_name"])
    log.info("Logs dir: %s", cfg["logs_dir"])

    # Scan
    try:
        report = scan_logs_dir(cfg["logs_dir"])
    except Exception as exc:
        log.error("Scan failed: %s", exc)
        return 1

    # Save locally
    try:
        REPORT_FILE.write_text(report, encoding="utf-8")
        log.info("Report saved: %s", REPORT_FILE)
    except Exception as exc:
        log.warning("Could not save local report: %s", exc)

    # Upload to dpaste
    dpaste_url = ""
    try:
        dpaste_url = post_to_dpaste(report)
        log.info("Report posted to dpaste: %s", dpaste_url)
    except Exception as exc:
        log.warning("dpaste upload failed: %s", exc)

    # Push URL back to Prometheus so it's visible without remote access.
    # Always push — even on dpaste failure — so Prometheus shows the diagnostic
    # ran rather than giving no signal at all.
    if cfg["pushgateway_url"]:
        url_to_push = dpaste_url if dpaste_url else "DPASTE_FAILED"
        if not dpaste_url:
            log.warning(
                "dpaste upload failed; pushing sentinel url='DPASTE_FAILED' "
                "so the diagnostic run is visible in Prometheus."
            )
        try:
            push_url_metric(
                cfg["pushgateway_url"],
                cfg["job_name"],
                cfg["machine_name"],
                url_to_push,
            )
            log.info(
                "Diagnostic status pushed to Prometheus (url=%s). Query: "
                "fridge_diagnostic_url{instance=\"%s\"}",
                url_to_push,
                cfg["machine_name"],
            )
        except Exception as exc:
            log.warning("Could not push URL metric: %s", exc)

    # Mark done
    try:
        DONE_FLAG.write_text(
            f"Ran at {datetime.now().isoformat()}. version={DIAGNOSE_VERSION}. dpaste: {dpaste_url}\n",
            encoding="utf-8",
        )
        log.info("Flag created: %s", DONE_FLAG)
    except Exception as exc:
        log.warning("Could not create done flag: %s", exc)

    log.info("Diagnostic complete.")
    if dpaste_url:
        log.info(">>> REPORT URL: %s <<<", dpaste_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
