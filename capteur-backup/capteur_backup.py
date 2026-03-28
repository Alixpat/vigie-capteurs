#!/usr/bin/env python3
"""
Capteur Backup — Surveille les logs syslog des sauvegardes
et publie leur statut sur un broker MQTT au format Vigie.
"""

import json
import subprocess
import sys
import time
import logging
import signal
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("capteur-backup")

running = True


def handle_signal(signum, _frame):
    global running
    log.info("Signal %s reçu, arrêt en cours…", signum)
    running = False


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def connect_mqtt(cfg: dict) -> mqtt.Client:
    client = mqtt.Client(client_id="capteur-backup", clean_session=True)
    if cfg.get("username"):
        client.username_pw_set(cfg["username"], cfg.get("password", ""))
    client.connect(cfg["broker"], cfg["port"], keepalive=60)
    client.loop_start()
    return client


def get_syslog_entries(tag: str) -> list[dict]:
    """Récupère les entrées journald pour un tag donné, les plus récentes en dernier."""
    try:
        result = subprocess.run(
            [
                "journalctl", "-t", tag,
                "--no-pager", "-o", "json",
                "--since", "30 days ago",
            ],
            capture_output=True, text=True, timeout=30,
        )
        entries = []
        for line in result.stdout.strip().splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log.error("Impossible de lire journald : %s", e)
        return []


def analyse_job(job: dict) -> dict:
    """Analyse les logs syslog pour un job de sauvegarde.

    Retourne un dict avec le statut et les détails.
    """
    tag = job["syslog_tag"]
    success_pattern = job["success_pattern"]
    failure_pattern = job["failure_pattern"]
    expected_hours = job["expected_every_hours"]

    entries = get_syslog_entries(tag)

    if not entries:
        return {
            "status": "missing",
            "detail": "Aucune entrée trouvée dans les logs",
            "last_run": None,
        }

    # Chercher la dernière entrée de succès ou d'échec (parcours inversé)
    last_success = None
    last_failure = None

    for entry in reversed(entries):
        message = entry.get("MESSAGE", "")
        timestamp_us = entry.get("__REALTIME_TIMESTAMP")
        if timestamp_us:
            ts = datetime.fromtimestamp(
                int(timestamp_us) / 1_000_000, tz=timezone.utc
            )
        else:
            ts = None

        if last_success is None and success_pattern in message:
            last_success = ts
        if last_failure is None and failure_pattern in message:
            last_failure = ts

        if last_success and last_failure:
            break

    # Déterminer le statut
    now = datetime.now(timezone.utc)

    if last_success and last_failure:
        if last_success > last_failure:
            status = "success"
            last_run = last_success
        else:
            status = "failed"
            last_run = last_failure
    elif last_success:
        status = "success"
        last_run = last_success
    elif last_failure:
        status = "failed"
        last_run = last_failure
    else:
        return {
            "status": "missing",
            "detail": "Aucun message de succès ou d'échec trouvé",
            "last_run": None,
        }

    # Vérifier si la sauvegarde est en retard
    age_hours = (now - last_run).total_seconds() / 3600
    if age_hours > expected_hours:
        status = "missing"
        days, hours = divmod(int(age_hours), 24)
        seuil_days, seuil_hours = divmod(expected_hours, 24)
        age_str = f"{days}j {hours}h" if days else f"{hours}h"
        seuil_str = f"{seuil_days}j {seuil_hours}h" if seuil_days else f"{seuil_hours}h"
        detail = f"Dernière sauvegarde il y a {age_str} (seuil : {seuil_str})"
    elif status == "success":
        detail = "Sauvegarde réussie"
    else:
        detail = "Sauvegarde en échec"

    return {
        "status": status,
        "detail": detail,
        "last_run": last_run.isoformat() if last_run else None,
    }


def build_message(job_name: str, analysis: dict) -> dict:
    return {
        "type": "backup_status",
        "job": job_name,
        "status": analysis["status"],
        "detail": analysis["detail"],
        "last_run": analysis["last_run"],
    }


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    config = load_config(config_path)

    mqtt_cfg = config["mqtt"]
    jobs = config["jobs"]
    interval = config["check_interval_seconds"]

    log.info(
        "Démarrage — broker=%s:%d, %d job(s), intervalle=%ds",
        mqtt_cfg["broker"], mqtt_cfg["port"], len(jobs), interval,
    )

    client = connect_mqtt(mqtt_cfg)
    topic_prefix = mqtt_cfg.get("topic_prefix", "vigie/backup")

    try:
        while running:
            for job in jobs:
                name = job["name"]
                analysis = analyse_job(job)

                log.info("%s : %s — %s", name, analysis["status"], analysis["detail"])

                message = build_message(name, analysis)
                topic = f"{topic_prefix}/{name}"
                client.publish(topic, json.dumps(message), qos=1, retain=True)

            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)
    finally:
        client.loop_stop()
        client.disconnect()
        log.info("Arrêté proprement.")


if __name__ == "__main__":
    main()
