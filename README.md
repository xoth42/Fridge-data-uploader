# Fridge Data Uploader

Windows-side uploader for Bluefors fridge log files. It reads the latest values
from the current day's Bluefors log folder and pushes them to the lab
Prometheus Pushgateway once per minute.

This repo is the client half of the fridge monitoring system. The server stack
scrapes Pushgateway and displays the data in Grafana.

## Current Shape

The live code is small:

| Path | Purpose |
| --- | --- |
| `push_metrics.py` | Main one-shot collector and Pushgateway uploader |
| `metric_metadata.py` | Metric names, descriptions, Grafana units, groups, and default channel labels |
| `fridge_configs/*.config` | Per-fridge YAML for channel labels, file naming, and file-type enable/disable |
| `.env.example` | Template for local machine config |
| `server.env` | Shared Pushgateway target |
| `START_LOGGING.bat` | Double-click entrypoint that requests admin and runs setup |
| `setup.ps1` | Installs dependencies, test-runs the uploader, and registers the scheduled task |
| `run_with_git_update.ps1` | Silent scheduled-task runner; updates repo/deps, runs diagnostics, then pushes metrics |
| `run_silent.vbs` | Hides the PowerShell scheduled-task window |
| `diagnose.py` | One-shot Bluefors log structure scanner and diagnostic URL publisher |

Ignore old notes or comments that talk about EC2-specific setup or `.env`
owning every setting. The live code reads Pushgateway configuration from
`server.env` and machine-specific settings from `.env`.

## Requirements

- Windows data machine with access to the Bluefors log directory
- Python 3.9 or newer
- Git, if you want the scheduled task's automatic `git pull` to work
- Network access from the fridge machine to the Pushgateway host and port

Python dependencies are installed from `requirements.txt` by `setup.ps1`.

## Quick Start

On the fridge computer:

```bat
copy .env.example .env
notepad .env
notepad server.env
```

Set `.env` for this machine:

```dotenv
FRIGE_LOGS_DIR=C:\Users\WangLab\Bluefors logs
MACHINE_NAME=fridge-manny
# PUSH_JOB_NAME=sensor_data
# HASTEBIN_TOKEN=
# PYTHON_EXE_OVERRIDE=C:\Path\To\python.exe
```

Set `server.env` to the monitoring server's Pushgateway:

```dotenv
PUSHGATEWAY_URL=zickers-fridge.duckdns.org:9091
```

Then double-click:

```text
START_LOGGING.bat
```

It requests Administrator privileges because `setup.ps1` registers a Windows
Scheduled Task named `PushFridgeMetrics`.

## How It Runs

`setup.ps1` does a one-time setup:

- verifies `.env` exists
- finds Python 3.9 or newer, respecting `PYTHON_EXE_OVERRIDE` when set
- installs `requirements.txt`
- runs `push_metrics.py` once with visible output
- removes any old `PushFridgeMetrics` task
- finds `pythonw.exe`
- registers a silent scheduled task that runs every minute
- attempts a final `git pull`

The scheduled task runs:

```text
wscript.exe -> run_silent.vbs -> run_with_git_update.ps1 -> push_metrics.py
```

On each scheduled run, `run_with_git_update.ps1` silently:

- runs `git pull`
- syncs Python dependencies from `requirements.txt`
- refreshes the scheduled task wrapper if needed
- runs `diagnose.py`
- runs `push_metrics.py`

`diagnose.py` is version-gated by `.diagnose_done`; it only scans again when
`DIAGNOSE_VERSION` changes or the flag is deleted.

## Configuration

### `.env`

Required:

- `FRIGE_LOGS_DIR`: top-level Bluefors logs directory. The misspelling is
  intentional because the code reads this exact variable.
- `MACHINE_NAME`: Prometheus instance label and fridge config selector, for
  example `fridge-manny` or `fridge-dodo`.

Optional:

- `PUSH_JOB_NAME`: Prometheus Pushgateway job label, default `sensor_data`.
- `HASTEBIN_TOKEN`: lets `diagnose.py` upload a diagnostic report.
- `PYTHON_EXE_OVERRIDE`: full path to a Python 3.9+ executable.

### `server.env`

Required:

- `PUSHGATEWAY_URL`: Pushgateway host and port. Do not include `/metrics`.

Example:

```dotenv
PUSHGATEWAY_URL=zickers-fridge.duckdns.org:9091
```

### `fridge_configs/`

`push_metrics.py` maps `MACHINE_NAME` to a fridge config by removing the
`fridge-` prefix:

```text
fridge-manny -> fridge_configs/manny.config
fridge-dodo  -> fridge_configs/dodo.config
fridge-sid   -> fridge_configs/sid.config
```

These YAML files can:

- label temperature, resistance, and pressure channels
- disable file types that a fridge does not produce
- override Bluefors filename patterns

Current notes:

- Manny has CH1, CH2, CH5, CH6, and CH9 labels configured.
- Dodo disables `Channels` collection and uses `heaters_{date}.log`.
- Sid is present but incomplete; channel layout is not confirmed.

## What Gets Collected

For today's Bluefors date folder (`YY-MM-DD`), the uploader reads the latest
line from each available source:

| Source | Metrics |
| --- | --- |
| `Status_{date}.log` | Compressor pressures, temperatures, current, hours, turbo pump, scroll pump, control pressure |
| `CH* T {date}.log` | Channel temperatures, pushed as `ch*_t_kelvin` |
| `CH* R {date}.log` | Channel resistances, pushed as `ch*_r_ohms` |
| `CH* P {date}.log` | Channel pressures, pushed as `ch*_p_mbar` |
| `Flowmeter {date}.log` | `flowmeter_mmol_per_s` |
| `Heaters {date}.log` | `heater_<id>_watts` |
| `Channels {date}.log` | `valve_<name>` states as `0` or `1` |
| `maxigauge {date}.log` | `maxigauge_ch*_pressure_mbar` |

CH files are discovered dynamically, so new `CH* T`, `CH* R`, and `CH* P`
files are picked up without editing the code.

Each metric is pushed with labels:

- `instance`: from `MACHINE_NAME`, via Pushgateway grouping key
- `subsystem`: from `metric_metadata.py`
- `display_name`: from `metric_metadata.py`
- `subgroup`: from fridge config when available, otherwise metadata default

The uploader also pushes `last_push_timestamp_seconds` on every successful
upload. The server uses this for stale-data alerts.

## Guardrails

The uploader is read-only against the Bluefors log directory.

Each parser fails independently. A missing optional file logs an error but does
not stop other files from being collected.

The uploader skips a push when the current day's Status file is missing, empty,
or has not advanced to a new minute. This matters because `push_to_gateway`
replaces the whole `job` plus `instance` group; pushing an incomplete set during
midnight rollover would erase still-valid values from Pushgateway.

Dodo-specific correction: `push_metrics.py` converts `cpatempwi_celsius` and
`cpatempwo_celsius` from Fahrenheit to Celsius because Dodo's cooling-water
sensor is mislabeled in the source log.

## Manual Commands

Run one visible push:

```powershell
python .\push_metrics.py
```

Run setup from an elevated PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Inspect the scheduled task:

```powershell
Get-ScheduledTask -TaskName PushFridgeMetrics
```

Remove the scheduled task:

```powershell
Unregister-ScheduledTask -TaskName PushFridgeMetrics -Confirm:$false
```

Force diagnostics to run again:

```powershell
Remove-Item .\.diagnose_done
python .\diagnose.py
```

## Logs And Verification

Local files written by the uploader:

- `push_metrics.log`: rotating runtime log for `push_metrics.py`
- `diagnose.log`: rotating log for `diagnose.py`
- `diagnose_report.txt`: latest local diagnostic report
- `.diagnose_done`: diagnostic completion/version marker
- `.last_task_update_check`: scheduled-task wrapper refresh marker

Verification points:

```powershell
Get-Content .\push_metrics.log -Tail 80
```

From a machine that can reach the monitoring server:

```text
http://<PUSHGATEWAY_URL>/metrics
```

Useful Prometheus queries on the server:

```promql
last_push_timestamp_seconds{job="sensor_data",instance="fridge-manny"}
fridge_diagnostic_url{instance="fridge-dodo"}
```

## Bluefors Folder Shape

`FRIGE_LOGS_DIR` should point to the top-level folder that contains date
subdirectories:

```text
Bluefors logs/
  26-02-19/
    Status_26-02-19.log
    CH1 T 26-02-19.log
    CH1 R 26-02-19.log
    Flowmeter 26-02-19.log
    Heaters 26-02-19.log
    Channels 26-02-19.log
    maxigauge 26-02-19.log
  26-02-18/
    ...
```

Per-fridge config can override filename patterns when a fridge differs from the
Bluefors defaults.
