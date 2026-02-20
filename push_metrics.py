import os
import re
import sys
import logging
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

from metric_metadata import get_description, get_group, get_metric_name_for_raw_key

# ---------------------------------------------------------------------------
# Logging -- write log to script's own directory, never to the data directory
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

    pushgateway_url = _require_env("PUSHGATEWAY_URL")
    machine_name    = _require_env("MACHINE_NAME")
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
# File discovery & parsing -- STRICTLY READ-ONLY against the logs directory
# ---------------------------------------------------------------------------

def find_status_file(logs_dir: Path, target_date: date) -> Path:
    """
    Locate today's status file inside its date-stamped subdirectory.

    Expected layout (read-only):
        {logs_dir}/{YY-MM-DD}/Status_{YY-MM-DD}.log

    Raises FileNotFoundError with a clear message if the date folder or the
    status file inside it does not exist.
    """
    date_str = target_date.strftime("%y-%m-%d")
    date_dir = logs_dir / date_str
    if not date_dir.exists() or not date_dir.is_dir():
        raise FileNotFoundError(
            f"Today's date folder not found: {date_dir}"
        )
    status_path = date_dir / f"Status_{date_str}.log"
    if not status_path.exists():
        raise FileNotFoundError(
            f"Status file not found inside date folder: {status_path}"
        )
    return status_path


def read_last_line(file_path: Path) -> str:
    """
    Read the last non-empty line of a file.

    Opened read-only; we read sequentially to be safe on files that are
    actively appended to on Windows.  Only the returned line is stripped.
    """
    last_line = ""
    with open(file_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last_line = line
    if not last_line:
        raise ValueError(f"File is empty: {file_path}")
    return last_line.strip()


def parse_status_line(line: str) -> dict[str, float]:
    """Parse one CSV line from the Status file.

    Format: date,time,key,value,key,value,...
    Returns a dict of raw key -> float value.
    """
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


# Regex to detect CH* T / CH* R filenames: e.g. "CH1 T 26-02-19.log"
_CH_FILE_RE = re.compile(
    r"^CH(\d+)\s+(T|R)\s+\d{2}-\d{2}-\d{2}\.log$",
    re.IGNORECASE,
)


def parse_channel_file(filepath: Path) -> float:
    """Parse a CH* T or CH* R file and return the latest value.

    Format: date,time,value
    """
    last = read_last_line(filepath)
    parts = last.split(",")
    if len(parts) < 3:
        raise ValueError(f"CH file line too short: {last!r}")
    return float(parts[2].strip())


def parse_flowmeter_file(filepath: Path) -> float:
    """Parse the Flowmeter file and return the latest flow value in mmol/s.

    Format: date,time,value
    """
    last = read_last_line(filepath)
    parts = last.split(",")
    if len(parts) < 3:
        raise ValueError(f"Flowmeter line too short: {last!r}")
    return float(parts[2].strip())


def parse_heaters_file(filepath: Path) -> dict[str, float]:
    """Parse the Heaters file and return power per heater channel.

    Format: date,time,id,power,id,power,...
    Returns: {"heater_0_watts": 0.0, "heater_1_watts": 0.008, ...}
    """
    last = read_last_line(filepath)
    parts = [p.strip() for p in last.split(",")]
    # parts[0]=date, parts[1]=time, then id/power pairs from index 2
    result: dict[str, float] = {}
    i = 2
    while i + 1 < len(parts):
        heater_id = parts[i]
        power_text = parts[i + 1]
        metric_name = f"heater_{heater_id}_watts"
        result[metric_name] = float(power_text)
        i += 2
    if not result:
        raise ValueError(f"No heater pairs found in line: {last!r}")
    return result


def parse_channels_file(filepath: Path) -> dict[str, float]:
    """Parse the Channels file and return valve/device on-off states.

    Format: date,time,0,name,state,name,state,...
    Returns: {"valve_v1": 1.0, "valve_v2": 0.0, ...}

    Hyphens in valve names are replaced with underscores so that the
    resulting metric names are Prometheus-compliant.
    """
    last = read_last_line(filepath)
    parts = [p.strip() for p in last.split(",")]
    # parts[0]=date, parts[1]=time, parts[2]=leading zero, name/state from 3
    result: dict[str, float] = {}
    i = 3
    while i + 1 < len(parts):
        raw_name = parts[i]
        state_text = parts[i + 1]
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", raw_name)
        metric_name = f"valve_{safe_name}"
        result[metric_name] = float(state_text)
        i += 2
    if not result:
        raise ValueError(f"No valve pairs found in line: {last!r}")
    return result


def parse_maxigauge_file(filepath: Path) -> dict[str, float]:
    """Parse the maxigauge file and return pressures for each channel.

    Format: date,time,CH1,name,status,pressure,unk1,unk2,CH2,...
    Each channel block is 6 fields: label, name, status, pressure, unk1, unk2.
    Returns: {"maxigauge_ch1_pressure_mbar": 2.27e-06, ...}
    """
    last = read_last_line(filepath)
    parts = [p.strip() for p in last.split(",")]
    # Channel blocks start at index 2; each block is 6 fields wide.
    result: dict[str, float] = {}
    block_start = 2
    while block_start + 5 < len(parts):
        ch_label = parts[block_start].lower()          # "ch1", "ch2", ...
        pressure_text = parts[block_start + 3]
        metric_name = f"maxigauge_{ch_label}_pressure_mbar"
        result[metric_name] = float(pressure_text)
        block_start += 6
    if not result:
        raise ValueError(f"No maxigauge channels parsed from line: {last!r}")
    return result


def collect_all_metrics(logs_dir: Path, target_date: date) -> dict[str, float]:
    """Collect metrics from ALL Bluefors log files for the given date.

    Each file parser is wrapped in an independent try/except so that a
    missing or malformed file never prevents the other files from being read.

    Returns a flat dict of fully-qualified metric name -> float value where
    each key already contains the appropriate unit suffix.
    """
    date_str = target_date.strftime("%y-%m-%d")
    date_dir = logs_dir / date_str

    if not date_dir.exists() or not date_dir.is_dir():
        raise FileNotFoundError(f"Today's date folder not found: {date_dir}")

    all_metrics: dict[str, float] = {}

    # ---- Status file ------------------------------------------------
    status_path = date_dir / f"Status_{date_str}.log"
    try:
        raw_status = parse_status_line(read_last_line(status_path))
        for raw_key, value in raw_status.items():
            metric_name = get_metric_name_for_raw_key(raw_key)
            all_metrics[metric_name] = value
        log.info("Status file: parsed %d metric(s)", len(raw_status))
    except Exception as exc:
        log.error("Status file error (%s): %s", status_path.name, exc)

    # ---- CH* T and CH* R files (dynamic discovery) ------------------
    try:
        all_filenames = os.listdir(date_dir)
    except Exception as exc:
        log.error("Cannot list date folder %s: %s", date_dir, exc)
        all_filenames = []

    for filename in sorted(all_filenames):
        m = _CH_FILE_RE.match(filename)
        if not m:
            continue
        ch_num = m.group(1)
        ch_type = m.group(2).upper()
        if ch_type == "T":
            metric_name = f"ch{ch_num}_t_kelvin"
        else:
            metric_name = f"ch{ch_num}_r_ohms"
        filepath = date_dir / filename
        try:
            all_metrics[metric_name] = parse_channel_file(filepath)
            log.info("Channel file %s -> %s", filename, metric_name)
            # CH6 T and CH9 T store sub-1K (mK-range) values as raw K.
            # The description in metric_metadata notes this; no conversion applied.
            if ch_type == "T" and ch_num in ("6", "9"):
                log.info(
                    "  Note: %s is mK-range (value=%.3e K) -- raw K stored, see metric description",
                    metric_name,
                    all_metrics[metric_name],
                )
        except Exception as exc:
            log.error("Channel file error (%s): %s", filename, exc)

    # ---- Flowmeter --------------------------------------------------
    flowmeter_path = date_dir / f"Flowmeter {date_str}.log"
    try:
        all_metrics["flowmeter_mmol_per_s"] = parse_flowmeter_file(flowmeter_path)
        log.info("Flowmeter file: parsed flowmeter_mmol_per_s")
    except Exception as exc:
        log.error("Flowmeter file error (%s): %s", flowmeter_path.name, exc)

    # ---- Heaters ----------------------------------------------------
    heaters_path = date_dir / f"Heaters {date_str}.log"
    try:
        heater_metrics = parse_heaters_file(heaters_path)
        all_metrics.update(heater_metrics)
        log.info("Heaters file: parsed %d heater metric(s)", len(heater_metrics))
    except Exception as exc:
        log.error("Heaters file error (%s): %s", heaters_path.name, exc)

    # ---- Channels (valves) ------------------------------------------
    channels_path = date_dir / f"Channels {date_str}.log"
    try:
        valve_metrics = parse_channels_file(channels_path)
        all_metrics.update(valve_metrics)
        log.info("Channels file: parsed %d valve metric(s)", len(valve_metrics))
    except Exception as exc:
        log.error("Channels file error (%s): %s", channels_path.name, exc)

    # ---- Maxigauge --------------------------------------------------
    maxigauge_path = date_dir / f"maxigauge {date_str}.log"
    try:
        gauge_metrics = parse_maxigauge_file(maxigauge_path)
        all_metrics.update(gauge_metrics)
        log.info("Maxigauge file: parsed %d pressure metric(s)", len(gauge_metrics))
    except Exception as exc:
        log.error("Maxigauge file error (%s): %s", maxigauge_path.name, exc)

    return all_metrics


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
    all_metrics: dict[str, float],
    pushgateway_url: str,
    job_name: str,
    machine_name: str,
) -> None:
    """Push every key/value pair as a Gauge to the Pushgateway.

    Uses get_description() for the HELP text and get_group() for the
    subsystem label so each metric can be filtered in Grafana.
    """
    registry = CollectorRegistry()

    for metric_key, value in all_metrics.items():
        safe_name = _safe_metric_name(metric_key)
        description = get_description(metric_key)
        group = get_group(metric_key)
        gauge = Gauge(
            safe_name,
            description,
            ["subsystem"],
            registry=registry,
        )
        gauge.labels(subsystem=group).set(value)

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

    # ---- Phase 2: collect metrics from all log files (READ-ONLY) -------
    try:
        all_metrics = collect_all_metrics(cfg["logs_dir"], date.today())
    except Exception as exc:
        log.error("Data collection error: %s", exc)
        return 1

    log.info("FRIGE_LOGS_DIR resolved to: %s", cfg["logs_dir"])
    log.info("Collected %d metric(s) total: %s", len(all_metrics), list(all_metrics.keys()))

    if not all_metrics:
        log.error("No metrics collected -- nothing to push")
        return 1

    # ---- Phase 3: push to Prometheus Pushgateway -----------------------
    try:
        push_metrics(
            all_metrics,
            pushgateway_url=cfg["pushgateway_url"],
            machine_name=cfg["machine_name"],
            job_name=cfg["job_name"],
        )
    except Exception as exc:
        log.error("Push failed: %s", exc)
        return 1

    log.info(
        "Successfully pushed %d metric(s) to %s",
        len(all_metrics),
        cfg["pushgateway_url"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
