# Fridge Data Uploader

Reads all available Bluefors fridge sensor data and pushes metrics to a Prometheus Pushgateway every minute.

## Prerequisites

- Windows machine with Python installed (Microsoft Store version is fine)
- Network access to the EC2 Pushgateway

## Quick Start

1. **Clone the repo** to a folder on the Windows machine, e.g.:
   ```
   C:\Users\<you>\Fridge-data-uploader
   ```

2. **Copy `.env.example` to `.env`** and fill in real values:
   ```
   copy .env.example .env
   ```
   Then open `.env` in a text editor and set the correct path and URL.

3. **Run `setup.ps1` from an elevated (Administrator) PowerShell** -- right-click -> *Run as Administrator*, or from an admin terminal:
   ```powershell
   powershell -ExecutionPolicy Bypass -File setup.ps1
   ```
   Admin rights are required to register a Windows Task Scheduler job.

4. **That's it.** The setup script installs dependencies, does a test run, and registers a Windows Task Scheduler job that runs silently every minute (no CMD popup).

## What Gets Collected

The script reads the following files from today's Bluefors date folder (`YY-MM-DD/`) and pushes them as Prometheus Gauges:

| Source file | Metrics | Notes |
|---|---|---|
| `Status_YY-MM-DD.log` | Compressor pressures/temps, turbo pump speed/power, scroll pump, control pressure | Key-value CSV |
| `CH1 T / CH1 R` | `ch1_t_kelvin`, `ch1_r_ohms` | 50K flange |
| `CH2 T / CH2 R` | `ch2_t_kelvin`, `ch2_r_ohms` | 4K flange |
| `CH5 T / CH5 R` | `ch5_t_kelvin`, `ch5_r_ohms` | Still |
| `CH6 T / CH6 R` | `ch6_t_kelvin`, `ch6_r_ohms` | MXC (mK-range, stored in K) |
| `CH9 T / CH9 R` | `ch9_t_kelvin`, `ch9_r_ohms` | FSE (mK-range, stored in K) |
| `Flowmeter YY-MM-DD.log` | `flowmeter_mmol_per_s` | Mixture flow rate |
| `Heaters YY-MM-DD.log` | `heater_0_watts`, `heater_1_watts`, ... | Per-channel heater power |
| `Channels YY-MM-DD.log` | `valve_v1`, `valve_v2`, ..., `valve_compressor`, ... | Valve/device on-off states (0 or 1) |
| `maxigauge YY-MM-DD.log` | `maxigauge_ch1_pressure_mbar` ... `maxigauge_ch6_pressure_mbar` | 6-channel pressure gauge |

New CH* files added by Bluefors are picked up automatically.

> **Note:** The channel-to-sensor label assignments (50K flange, 4K flange, Still, MXC, FSE) and unit assumptions are preliminary guesses based on available documentation. They will be reviewed by experienced technicians and may change as the data is validated.

## Metric Naming Convention

All metric names follow the pattern `<key>_<unit>`, for example:
- `cpahpa_mbar` -- compressor high pressure actual
- `ch6_t_kelvin` -- MXC temperature (raw K value)
- `tc400actualspd_hz` -- turbo pump speed
- `flowmeter_mmol_per_s` -- mixture flow rate

Each metric includes a human-readable HELP string (visible in Pushgateway) that shows the source file and raw key name for easy verification.

## Verifying It Works

- Check `push_metrics.log` in the script directory for per-run output.
- Visit `http://<PUSHGATEWAY_URL>/metrics` in a browser to see pushed metrics.

## Notes

- The script is **strictly read-only** against the fridge logs directory.
- `FRIGE_LOGS_DIR` should point to the **top-level Bluefors Logs folder** (e.g. `C:\Users\WangLab\Bluefors logs`). The script automatically navigates the date-based subdirectory structure.
- The scheduled task uses `pythonw.exe` so there is no visible CMD window.
- Each file parser fails independently -- one missing or malformed file does not prevent other files from being collected.

```
Bluefors logs/
+-- 26-02-19/
|   +-- Status_26-02-19.log
|   +-- CH1 T 26-02-19.log
|   +-- CH1 R 26-02-19.log
|   +-- ...
|   +-- Flowmeter 26-02-19.log
|   +-- Heaters 26-02-19.log
|   +-- Channels 26-02-19.log
|   +-- maxigauge 26-02-19.log
+-- 26-02-18/
|   +-- ...
```

## File Overview

| File | Purpose |
|---|---|
| `push_metrics.py` | Main script -- collects all data sources and pushes metrics |
| `metric_metadata.py` | Metadata dict: descriptions, unit suffixes, Grafana units, groups |
| `setup.ps1` | One-shot setup: installs deps, test run, registers silent scheduled task |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for the `.env` config file |
| `.env` | Your local config (gitignored -- never committed) |
| `push_metrics.log` | Runtime log (gitignored -- written locally) |

## Uninstall

To remove the scheduled task (run from an elevated/Administrator PowerShell):
```powershell
Unregister-ScheduledTask -TaskName PushFridgeMetrics
```
