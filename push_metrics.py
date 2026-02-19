import os
import re
import sys
import logging
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

# ---------------------------------------------------------------------------
# Logging — write log to script's own directory, never to the data directory
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
LOG_FILE = SCRIPT_DIR / "push_metrics.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------

def _require_env(var: str) -> str:
    """Return an env var's value or raise with a clear message."""
    value = os.getenv(var)
    if not value:
        raise ValueError(f"{var} is missing or empty in .env")
    return value


def load_config(env_file: Path) -> dict:
    """Load and validate every setting we need from the .env file."""
    if not env_file.exists():
        raise FileNotFoundError(f".env file not found at: {env_file}")
    load_dotenv(dotenv_path=env_file)

    pushgateway_url = _require_env("PUSHGATEWAY_URL")       # e.g. 54.123.45.67:9091
    machine_name    = _require_env("MACHINE_NAME")           # e.g. fridge-alpha
    job_name        = os.getenv("PUSH_JOB_NAME", "sensor_data")
    logs_dir_raw    = _require_env("FRIGE_LOGS_DIR")

    logs_dir = Path(logs_dir_raw).expanduser().resolve()

    return {
        "pushgateway_url": pushgateway_url,
        "machine_name":    machine_name,
        "job_name":        job_name,
        "logs_dir":        logs_dir,
    }


# ---------------------------------------------------------------------------
# File discovery & parsing — STRICTLY READ-ONLY against the logs directory
# ---------------------------------------------------------------------------

def list_files_in_dir(directory: Path) -> list[str]:
    """List filenames in directory. Read-only — no writes, no temp files."""
    if not directory.exists():
        raise FileNotFoundError(f"Directory does not exist: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")
    # os.listdir is a pure read syscall — no locks, no handles held open
    return os.listdir(directory)


def find_status_file(files: list[str], logs_dir: Path, target_date: date) -> Path | None:
    status_name = f"Status_{target_date:%y-%m-%d}.txt"
    if status_name in files:
        return logs_dir / status_name
    return None


def read_last_line(file_path: Path) -> str:
    """
    Read the last line of a status file.

    Opened read-only with share-friendly flags so the process that writes
    the file is never blocked. We read the entire file sequentially rather
    than seeking — safer on files that are actively appended to on Windows.
    """
    last_line = ""
    with open(file_path, "r", encoding="utf-8") as handle:
        for line in handle:
            last_line = line
    if not last_line:
        raise ValueError(f"Status file is empty: {file_path}")
    return last_line.strip()


def parse_status_line(line: str) -> dict[str, float]:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 4 or (len(parts) - 2) % 2 != 0:
        raise ValueError(f"Status line has invalid format: {line}")

    values: dict[str, float] = {}
    for index in range(2, len(parts), 2):
        key = parts[index]
        value_text = parts[index + 1]
        if not key:
            raise ValueError(f"Missing idname in status line: {line}")
        try:
            values[key] = float(value_text)
        except ValueError as exc:
            raise ValueError(
                f"Invalid numeric value '{value_text}' in status line"
            ) from exc
    return values


# ---------------------------------------------------------------------------
# Prometheus push
# ---------------------------------------------------------------------------

_METRIC_NAME_RE = re.compile(r"[^a-zA-Z0-9_:]")


def _safe_metric_name(raw: str) -> str:
    """Sanitise an arbitrary key into a legal Prometheus metric name."""
    name = _METRIC_NAME_RE.sub("_", raw)
    if name and name[0].isdigit():
        name = f"m_{name}"
    return name


def push_metrics(
    status_values: dict[str, float],
    pushgateway_url: str,
    job_name: str,
    machine_name: str,
) -> None:
    """Push every key/value pair as a Gauge to the Pushgateway."""
    registry = CollectorRegistry()

    for raw_key, value in status_values.items():
        safe_name = _safe_metric_name(raw_key)
        gauge = Gauge(
            safe_name,
            f"Sensor reading: {raw_key}",
            registry=registry,
        )
        gauge.set(value)

    heartbeat = Gauge(
        "last_push_timestamp_seconds",
        "Unix epoch of the most recent successful push",
        registry=registry,
    )
    heartbeat.set_to_current_time()

    push_to_gateway(
        pushgateway_url,
        job=job_name,
        grouping_key={"instance": machine_name},
        registry=registry,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    env_file = SCRIPT_DIR / ".env"

    # ---- Phase 1: load config from .env --------------------------------
    try:
        cfg = load_config(env_file)
    except Exception as exc:
        log.error("Configuration error: %s", exc)
        return 1

    # ---- Phase 2: read the latest status values (READ-ONLY) ------------
    try:
        files = list_files_in_dir(cfg["logs_dir"])
        status_path = find_status_file(files, cfg["logs_dir"], date.today())
        if not status_path:
            raise FileNotFoundError("Today's status file was not found")
        last_line = read_last_line(status_path)
        status_values = parse_status_line(last_line)
    except Exception as exc:
        log.error("Data collection error: %s", exc)
        return 1

    log.info("FRIGE_LOGS_DIR resolved to: %s", cfg["logs_dir"])
    log.info("Status file: %s", status_path.name)
    log.info("Parsed %d metric(s): %s", len(status_values), list(status_values.keys()))

    # ---- Phase 3: push to Prometheus Pushgateway -----------------------
    try:
        push_metrics(
            status_values,
            pushgateway_url=cfg["pushgateway_url"],
            machine_name=cfg["machine_name"],
            job_name=cfg["job_name"],
        )
    except Exception as exc:
        log.error("Push failed: %s", exc)
        return 1

    log.info(
        "Successfully pushed %d metric(s) to %s",
        len(status_values),
        cfg["pushgateway_url"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())