# Fridge Data Uploader

Reads fridge sensor data from status log files and pushes metrics to a Prometheus Pushgateway.

## Prerequisites

- Windows machine with Python installed (Microsoft Store version is fine)
- Network access to the EC2 Pushgateway

## Quick Start

1. **Clone the repo** to a folder on the Windows machine, e.g.:
   ```
   C:\Users\<you>\Fridge-data-uploader
   ```

2. **Copy `.env.example` to `.env`** and fill in real values (especially `FRIGE_LOGS_DIR`):
   ```
   copy .env.example .env
   ```
   Then open `.env` in a text editor and set the correct paths and URLs.

3. **Run `setup.ps1`** — right-click → *Run with PowerShell*, or from a terminal:
   ```powershell
   powershell -ExecutionPolicy Bypass -File setup.ps1
   ```

4. **That's it.** The setup script installs dependencies, does a test run, and creates a Windows Task Scheduler job that runs every minute.

## Verifying It Works

- Check `push_metrics.log` in the script directory for per-run output.
- Visit `http://<PUSHGATEWAY_URL>/metrics` in a browser to see the pushed metrics.

## Notes

The script is **strictly read-only** against the fridge logs directory — it never writes, locks, or modifies anything there.

`FRIGE_LOGS_DIR` should point to the **top-level Bluefors Logs folder** (e.g. `C:\Lab\Bluefors Logs`). The script automatically navigates the date-based subdirectory structure that Bluefors creates:

```
Bluefors Logs/
├── 26-02-19/
│   └── Status_26-02-19
├── 26-02-18/
│   └── Status_26-02-18
└── ...
```

On each run the script looks for today's date folder (`YY-MM-DD/`) inside `FRIGE_LOGS_DIR`, then reads `Status_YY-MM-DD` from that folder.

## File Overview

| File | Purpose |
|---|---|
| `push_metrics.py` | Main script — reads status file and pushes metrics |
| `setup.ps1` | One-time setup: installs deps and creates scheduled task |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for the `.env` config file |
| `.env` | Your local config (gitignored — never committed) |
| `push_metrics.log` | Runtime log (gitignored — written locally) |

## Uninstall

To remove the scheduled task:
```powershell
Unregister-ScheduledTask -TaskName PushFridgeMetrics
```
