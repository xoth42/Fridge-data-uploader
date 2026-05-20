class ServerUnavailableError(Exception):
    pass
import os
import re
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

from metric_metadata import get_description, get_group, get_metric_name_for_raw_key, get_display_name, get_subgroup

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
        RotatingFileHandler(LOG_FILE, encoding="utf-8", maxBytes=1048576, backupCount=5),
    ],
)
log = logging.getLogger(__name__)

# Global variable to track the last time:minute we pushed metrics
_last_pushed_time = None

# ---------------------------------------------------------------------------
# Bluefors default filename patterns  ({date} replaced with "YY-MM-DD")
# ---------------------------------------------------------------------------
_DEFAULT_FILE_NAMING = {
    "status":    "Status_{date}.log",
    "flowmeter": "Flowmeter {date}.log",
    "heaters":   "Heaters {date}.log",
    "channels":  "Channels {date}.log",
    "maxigauge": "maxigauge {date}.log",
}


def _resolve_filename(fridge_cfg: dict, key: str, date_str: str) -> str:
    """Return the resolved filename for a file type, applying any per-fridge override."""
    pattern = fridge_cfg.get("file_naming", {}).get(key, _DEFAULT_FILE_NAMING[key])
    return pattern.replace("{date}", date_str)


# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------

def _require_env(var: str) -> str:
    """Return an env var's value or raise with a clear message."""
    value = os.getenv(var)
    if not value:
        raise ValueError(f"{var} is missing or empty in .env")
    return value


def _load_fridge_config(machine_name: str) -> dict:
    """Load the YAML fridge config for this machine.

    Looks up fridge_configs/{name}.config by stripping the 'fridge-' prefix
    from MACHINE_NAME (e.g. 'fridge-dodo' -> 'fridge_configs/dodo.config').
    Returns an empty dict (all defaults) if the config file is not found.
    """
    config_name = machine_name.removeprefix("fridge-")
    config_path = SCRIPT_DIR / "fridge_configs" / f"{config_name}.config"
    if not config_path.exists():
        log.warning(
            "No fridge config found at %s — using defaults (all file types enabled, "
            "standard Bluefors filenames, no channel label overrides)",
            config_path,
        )
        return {}
    with open(config_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    log.info("Loaded fridge config: %s", config_path.name)
    return cfg


def load_config(env_file: Path) -> dict:
    """Load and validate every setting we need from the .env file."""
    if not env_file.exists():
        raise FileNotFoundError(f".env file not found at: {env_file}")
    load_dotenv(dotenv_path=env_file)


    # Only load PUSHGATEWAY_URL from server.env
    server_env_file = env_file.parent / "server.env"
    if not server_env_file.exists():
        raise FileNotFoundError(f"server.env file not found at: {server_env_file}")
    load_dotenv(dotenv_path=server_env_file, override=True)
    pushgateway_url = os.getenv("PUSHGATEWAY_URL")
    if not pushgateway_url:
        raise ValueError("PUSHGATEWAY_URL is missing in server.env")

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

def read_last_line(file_path: Path) -> str:
    """
    Read the last line of a file.

    Opened read-only; we read sequentially to be safe on files that are
    actively appended to on Windows.  The returned line is stripped.
    """
    last_line = ""
    with open(file_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last_line = line
    if not last_line:
        raise ValueError(f"File is empty: {file_path}")
    return last_line.strip()


def extract_time_minute(line: str) -> str:
    """Extract HH:MM from a CSV line with format: date,time,...
    
    Returns the time field truncated to HH:MM (e.g., "15:14" from "15:14:27").
    """
    parts = [p.strip() for p in line.split(",", 2)]
    if len(parts) < 2:
        raise ValueError(f"Line too short to extract time: {line!r}")
    time_str = parts[1]  # "HH:MM:SS" format
    # Extract just HH:MM
    return ":".join(time_str.split(":")[:2])


def is_new_data(line: str) -> bool:
    """Check if the line's timestamp (HH:MM) differs from the last push.
    
    Returns True if this is new data (different HH:MM), False if stale (same HH:MM).
    """
    global _last_pushed_time
    try:
        current_time = extract_time_minute(line)
        if _last_pushed_time is None or _last_pushed_time != current_time:
            _last_pushed_time = current_time
            return True # data is new
        return False # data is stale
    except Exception as exc:
        log.error("Error checking for stale data: %s", exc)
        return True  # If we can't determine, push anyway


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


# Regex to detect CH* T / CH* R / CH* P filenames: e.g. "CH1 T 26-02-19.log"
_CH_FILE_RE = re.compile(
    r"^CH(\d+)\s+(T|R|P)\s+\d{2}-\d{2}-\d{2}\.log$",
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
        raw_key = f"maxigauge_{ch_label}"              # e.g. "maxigauge_ch1"
        metric_name = get_metric_name_for_raw_key(raw_key)
        if metric_name == raw_key:
            metric_name = f"{raw_key}_pressure_mbar"  # fallback for unlisted channels
        result[metric_name] = float(pressure_text)
        block_start += 6
    if not result:
        raise ValueError(f"No maxigauge channels parsed from line: {last!r}")
    return result


def collect_all_metrics(
    logs_dir: Path,
    target_date: date,
    fridge_cfg: dict,
) -> tuple[dict[str, float], dict[str, str]]:
    """Collect metrics from all Bluefors log files for the given date.

    Uses the fridge config to:
      - skip file types disabled in collect:
      - resolve filenames via file_naming: (per-fridge overrides)
      - supply channel subgroup labels from temperature/resistance/pressure_channels

    Each parser is wrapped in an independent try/except so a missing or
    malformed file never blocks the others.

    Returns:
      all_metrics     : flat dict of metric name -> float value
      subgroup_labels : metric name -> subgroup string (config channel label overrides)
    """
    date_str = target_date.strftime("%y-%m-%d")
    date_dir = logs_dir / date_str

    if not date_dir.exists() or not date_dir.is_dir():
        raise FileNotFoundError(f"Today's date folder not found: {date_dir}")

    collect = fridge_cfg.get("collect", {})

    # Build channel label lookups from config (YAML keys may be ints).
    def _ch_labels(section: str) -> dict[str, str]:
        return {str(k): v for k, v in fridge_cfg.get(section, {}).items()}

    temp_labels  = _ch_labels("temperature_channels")
    res_labels   = _ch_labels("resistance_channels")
    pres_labels  = _ch_labels("pressure_channels")

    all_metrics: dict[str, float] = {}
    subgroup_labels: dict[str, str] = {}

    # ---- Status file ------------------------------------------------
    if collect.get("status", True):
        status_filename = _resolve_filename(fridge_cfg, "status", date_str)
        status_path = date_dir / status_filename
        try:
            raw_status = parse_status_line(read_last_line(status_path))
            for raw_key, value in raw_status.items():
                metric_name = get_metric_name_for_raw_key(raw_key)
                all_metrics[metric_name] = value
            log.info("Status file: parsed %d metric(s)", len(raw_status))
        except Exception as exc:
            log.error("Status file error (%s): %s", status_filename, exc)

    # ---- CH* T, CH* R, CH* P files (dynamic discovery) -------------
    try:
        all_filenames = os.listdir(date_dir)
    except Exception as exc:
        log.error("Cannot list date folder %s: %s", date_dir, exc)
        all_filenames = []

    for filename in sorted(all_filenames):
        m = _CH_FILE_RE.match(filename)
        if not m:
            continue
        ch_num  = m.group(1)
        ch_type = m.group(2).lower()  # "t", "r", or "p"

        raw_key = f"ch{ch_num}_{ch_type}"
        metric_name = get_metric_name_for_raw_key(raw_key)
        if metric_name == raw_key:
            unit = {"t": "kelvin", "r": "ohms", "p": "mbar"}[ch_type]
            metric_name = f"{raw_key}_{unit}"

        filepath = date_dir / filename
        try:
            all_metrics[metric_name] = parse_channel_file(filepath)
            log.info("Channel file %s -> %s", filename, metric_name)
            if ch_type == "t" and ch_num in ("6", "9"):
                log.info(
                    "  Note: %s is mK-range (value=%.3e K) -- raw K stored",
                    metric_name,
                    all_metrics[metric_name],
                )
        except Exception as exc:
            log.error("Channel file error (%s): %s", filename, exc)
            continue

        # Apply subgroup label from config, overriding hardcoded metadata.
        label_map = {"t": temp_labels, "r": res_labels, "p": pres_labels}[ch_type]
        label = label_map.get(ch_num)
        if label:
            subgroup_labels[metric_name] = label

    # ---- Flowmeter --------------------------------------------------
    if collect.get("flowmeter", True):
        flowmeter_filename = _resolve_filename(fridge_cfg, "flowmeter", date_str)
        flowmeter_path = date_dir / flowmeter_filename
        try:
            metric_name = get_metric_name_for_raw_key("flowmeter")
            all_metrics[metric_name] = parse_flowmeter_file(flowmeter_path)
            log.info("Flowmeter file: parsed %s", metric_name)
        except Exception as exc:
            log.error("Flowmeter file error (%s): %s", flowmeter_filename, exc)

    # ---- Heaters ----------------------------------------------------
    if collect.get("heaters", True):
        heaters_filename = _resolve_filename(fridge_cfg, "heaters", date_str)
        heaters_path = date_dir / heaters_filename
        try:
            heater_metrics = parse_heaters_file(heaters_path)
            all_metrics.update(heater_metrics)
            log.info("Heaters file: parsed %d heater metric(s)", len(heater_metrics))
        except Exception as exc:
            log.error("Heaters file error (%s): %s", heaters_filename, exc)

    # ---- Channels (valves) ------------------------------------------
    if collect.get("channels", True):
        channels_filename = _resolve_filename(fridge_cfg, "channels", date_str)
        channels_path = date_dir / channels_filename
        try:
            valve_metrics = parse_channels_file(channels_path)
            all_metrics.update(valve_metrics)
            log.info("Channels file: parsed %d valve metric(s)", len(valve_metrics))
        except Exception as exc:
            log.error("Channels file error (%s): %s", channels_filename, exc)

    # ---- Maxigauge --------------------------------------------------
    if collect.get("maxigauge", True):
        maxigauge_filename = _resolve_filename(fridge_cfg, "maxigauge", date_str)
        maxigauge_path = date_dir / maxigauge_filename
        try:
            gauge_metrics = parse_maxigauge_file(maxigauge_path)
            all_metrics.update(gauge_metrics)
            log.info("Maxigauge file: parsed %d pressure metric(s)", len(gauge_metrics))
        except Exception as exc:
            log.error("Maxigauge file error (%s): %s", maxigauge_filename, exc)

    return all_metrics, subgroup_labels


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
    subgroup_labels: dict[str, str] | None = None,
) -> None:
    """Push every key/value pair as a Gauge to the Pushgateway.

    subgroup_labels provides per-metric subgroup overrides sourced from the
    fridge config's channel label maps; falls back to hardcoded metadata.
    """
    if subgroup_labels is None:
        subgroup_labels = {}

    registry = CollectorRegistry()

    for metric_key, value in all_metrics.items():
        safe_name = _safe_metric_name(metric_key)
        description = get_description(metric_key)
        group = get_group(metric_key)
        display_name = get_display_name(metric_key)
        subgroup = subgroup_labels.get(metric_key) or get_subgroup(metric_key)
        gauge = Gauge(
            safe_name,
            description,
            ["subsystem", "display_name", "subgroup"],
            registry=registry,
        )
        gauge.labels(subsystem=group, display_name=display_name, subgroup=subgroup).set(value)

    heartbeat = Gauge(
        "last_push_timestamp_seconds",
        "Unix epoch of the most recent successful push",
        registry=registry,
    )
    heartbeat.set_to_current_time()

    try:
        push_to_gateway(
            pushgateway_url,
            job=job_name,
            grouping_key={"instance": machine_name},
            registry=registry,
        )
    except Exception as exc:
        raise ServerUnavailableError(f"Pushgateway server unavailable: {exc}")


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

    fridge_cfg = _load_fridge_config(cfg["machine_name"])

    # ---- Phase 1b: guard against pushing incomplete data -------------------
    # push_to_gateway does a full PUT/replace of all metrics for the
    # job+instance group.  If the Status file is absent or empty (e.g. during
    # the midnight date-rollover — on slow fridges like Dodo the new-day file
    # may not appear for ~15 min), a push without Status metrics would DELETE
    # them from Pushgateway and trigger false "no data" alerts on the server.
    # Skipping the push leaves all previously-published values intact until
    # the file arrives.
    target_date = date.today()
    date_str = target_date.strftime("%y-%m-%d")
    date_dir = cfg["logs_dir"] / date_str
    status_filename = _resolve_filename(fridge_cfg, "status", date_str)
    status_path = date_dir / status_filename

    if fridge_cfg.get("collect", {}).get("status", True):
        if not status_path.exists():
            log.info(
                "Status file not yet available (%s) — skipping push to preserve "
                "Pushgateway data.",
                status_filename,
            )
            return 0

        try:
            status_line = read_last_line(status_path)
        except ValueError:
            # File exists but is empty — same situation as absent.
            log.info(
                "Status file exists but is empty (%s) — skipping push to preserve "
                "Pushgateway data.",
                status_filename,
            )
            return 0
        except Exception as exc:
            log.warning(
                "Could not read Status file (%s): %s. Proceeding anyway.",
                status_filename, exc,
            )
            status_line = None

        if status_line is not None:
            try:
                if not is_new_data(status_line):
                    log.info("Data is stale (timestamp unchanged). Skipping push.")
                    return 0
            except Exception as exc:
                log.warning("Could not check for stale data: %s. Proceeding anyway.", exc)

    # ---- Phase 2: collect metrics from all log files (READ-ONLY) -------
    try:
        all_metrics, subgroup_labels = collect_all_metrics(
            cfg["logs_dir"], target_date, fridge_cfg
        )
    except Exception as exc:
        log.error("Data collection error: %s", exc)
        return 1

    log.info("FRIGE_LOGS_DIR resolved to: %s", cfg["logs_dir"])
    log.info("Collected %d metric(s) total: %s", len(all_metrics), list(all_metrics.keys()))

    if not all_metrics:
        log.error("No metrics collected -- nothing to push")
        return 1

    # ---- Phase 2b: machine-specific corrections ----------------------------
    # Dodo's cooling water sensor physically reports °F but the file labels the
    # column as Celsius.  Convert to true °C here so the pushed metric is
    # consistent with Manny and no dashboard-side workaround is needed.
    if cfg["machine_name"] == "fridge-dodo": # only on dodo...
        for key in ("cpatempwi_celsius", "cpatempwo_celsius"): # for the two water temps that we care about, which are reported in F, but labled as C, 
            if key in all_metrics: # if we are reporting them..
                tmp = all_metrics[key]
                all_metrics[key] = (all_metrics[key] - 32.0) * 5.0 / 9.0 # convert to C
                log.info(f"{key} F→°C correction applied: {tmp}°F → {all_metrics[key]}°C")

    # ---- Phase 3: push to Prometheus Pushgateway -----------------------
    try:
        push_metrics(
            all_metrics,
            pushgateway_url=cfg["pushgateway_url"],
            machine_name=cfg["machine_name"],
            job_name=cfg["job_name"],
            subgroup_labels=subgroup_labels,
        )
    except ServerUnavailableError as exc:
        log.error("Push failed: server down or unreachable at %s: %s", cfg["pushgateway_url"], exc)
        return 2
    except Exception as exc:
        log.error("Push failed (target: %s): %s", cfg["pushgateway_url"], exc)
        return 1

    log.info(
        "Successfully pushed %d metric(s) to %s",
        len(all_metrics),
        cfg["pushgateway_url"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
