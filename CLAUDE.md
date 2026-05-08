# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Collection of independent Python "capteurs" (sensors) that publish status to an MQTT broker for the **Vigie** monitoring system. Each capteur is a standalone service in its own directory, with the same layout (Python script + `config.json` + `requirements.txt` + `install.sh` + `*.service.template`).

Current capteurs:
- `capteur-ping/` — pings LAN machines, publishes `vigie/lan/<hostname>`
- `capteur-internet/` — pings external targets, tracks downtime windows, publishes `vigie/internet/<name>`
- `capteur-backup/` — reads `journalctl` for backup script tags, publishes `vigie/backup/<job>`

Backend consumer (the Vigie dashboard) lives in a separate repo. This repo only contains the producers.

## Architecture conventions

All capteurs follow the same skeleton — keep new capteurs aligned with it:

1. **Single-file Python script** at `capteur-<name>/capteur_<name>.py` (note: directory uses `-`, file uses `_`).
2. **Config loaded from `sys.argv[1]`**, defaults to `./config.json`. The systemd unit always passes `/etc/vigie/capteur-<name>/config.json`.
3. **MQTT client**: `paho.mqtt.client` with `client_id="capteur-<name>"`, `clean_session=True`, `loop_start()`, optional username/password from config.
4. **Publishing**: every message is `qos=1, retain=True` so the broker keeps the last state for late subscribers and reconnections. Topic = `<topic_prefix>/<entity>` where `topic_prefix` is read from config (defaults differ per capteur).
5. **Message payload**: JSON with a `type` field that identifies the capteur (`lan_status`, `internet_status`, `backup_status`). Downstream Vigie discriminates on `type`.
6. **Main loop**: `while running:` polls each entity sequentially, then sleeps in 1-second increments so SIGTERM/SIGINT shut down within ~1s. The `running` flag is flipped by a shared `handle_signal` handler registered for SIGINT and SIGTERM. Always wrap the loop in `try/finally` that calls `client.loop_stop()` + `client.disconnect()`.
7. **Logging**: `logging.basicConfig` with `%(asctime)s [%(levelname)s] %(message)s`, logger named `capteur-<name>`. Don't print — journald captures the logger output via the systemd unit.

The `capteur-internet` capteur additionally tracks downtime transitions (start, end, duration) in an in-memory `state` dict keyed by target name, and includes the last downtime in every published message. Use the same pattern if a new capteur needs transition tracking; do not introduce a database — state is intentionally lost on restart since the broker holds the retained current value.

## Install / deploy pattern

Each capteur ships an `install.sh` that:
- Resolves its own directory via `$(cd "$(dirname "$0")" && pwd)` — the venv lives next to the script, not in `/opt`.
- Creates `venv/` if absent and `pip install -r requirements.txt`.
- Copies `config.json` to `/etc/vigie/capteur-<name>/config.json` only if it doesn't already exist (never overwrites a deployed config).
- Renders `capteur-<name>.service.template` by substituting `__WORKING_DIR__` with the resolved directory, writes to `/etc/systemd/system/`.
- Runs `systemctl daemon-reload && systemctl enable --now capteur-<name>`.

The service template's `ExecStart` is `__WORKING_DIR__/venv/bin/python3 capteur_<name>.py /etc/vigie/capteur-<name>/config.json`. New capteurs must follow the same `__WORKING_DIR__` placeholder convention so `install.sh` works unchanged.

`install.sh` must be run with `sudo` (writes to `/etc/` and `/etc/systemd/system/`).

## Backup capteur — syslog convention

`capteur-backup` works only if backup scripts log to syslog with `logger -t backup-<name>` and the success/failure substrings match the patterns in `config.json` (defaults: `"terminée avec succès"` and `"ERREUR"`). The capteur shells out to `journalctl -t <tag> --since "30 days ago" -o json` and walks entries newest-first to find the most recent success and failure. A run is `missing` if its age exceeds `expected_every_hours`. When adding a new monitored job, also document the syslog tag in `capteur-backup/README.md` so the convention stays discoverable.

## Common dev workflow

Per-capteur (run from the capteur's own directory):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 capteur_<name>.py            # uses ./config.json
python3 capteur_<name>.py /path/to/config.json
```

Service management once installed:

```bash
sudo systemctl status capteur-<name>
sudo journalctl -u capteur-<name> -f
sudo systemctl restart capteur-<name>
```

There are no automated tests, no linter config, and no CI in this repo. Manual testing = run the script against a local MQTT broker (e.g. `mosquitto`) and inspect with `mosquitto_sub -t 'vigie/#' -v`.

## Language

User-facing strings (logs, README, error messages, comments) are written in French. Keep that convention — don't translate existing French strings to English when editing.
