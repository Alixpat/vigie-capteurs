#!/usr/bin/env python3
"""
Capteur Ping — Vérifie la disponibilité des machines sur le LAN
et publie leur statut sur un broker MQTT au format Vigie.
"""

import json
import subprocess
import sys
import platform
import time
import logging
import signal

import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("capteur-ping")

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


def ping(host: str, count: int = 3, timeout: int = 2) -> bool:
    """Ping une machine et renvoie True si elle répond."""
    param_count = "-n" if platform.system().lower() == "windows" else "-c"
    param_timeout = "-w" if platform.system().lower() == "windows" else "-W"
    try:
        result = subprocess.run(
            ["ping", param_count, str(count), param_timeout, str(timeout), host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except FileNotFoundError:
        log.error("Commande ping introuvable")
        return False


def build_message(hostname: str, ip: str, is_up: bool) -> dict:
    """Construit un message au format Vigie."""
    return {
        "type": "lan_status",
        "hostname": hostname,
        "ip": ip,
        "status": "up" if is_up else "down",
    }


def connect_mqtt(cfg: dict) -> mqtt.Client:
    """Crée et connecte un client MQTT."""
    client = mqtt.Client(client_id="capteur-ping", clean_session=True)
    if cfg.get("username"):
        client.username_pw_set(cfg["username"], cfg.get("password", ""))
    client.connect(cfg["broker"], cfg["port"], keepalive=60)
    client.loop_start()
    return client


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    config = load_config(config_path)

    mqtt_cfg = config["mqtt"]
    ping_cfg = config["ping"]
    machines = config["machines"]

    log.info(
        "Démarrage — broker=%s:%d, %d machine(s), intervalle=%ds",
        mqtt_cfg["broker"],
        mqtt_cfg["port"],
        len(machines),
        ping_cfg["interval_seconds"],
    )

    client = connect_mqtt(mqtt_cfg)
    topic_prefix = mqtt_cfg.get("topic_prefix", "vigie/lan")

    try:
        while running:
            for machine in machines:
                hostname = machine["hostname"]
                ip = machine["ip"]

                is_up = ping(
                    ip,
                    count=ping_cfg.get("count", 3),
                    timeout=ping_cfg.get("timeout_seconds", 2),
                )
                log.info("%s (%s) : %s", hostname, ip, "up" if is_up else "down")

                message = build_message(hostname, ip, is_up)
                topic = f"{topic_prefix}/{hostname}"
                client.publish(topic, json.dumps(message), qos=1, retain=True)

            # Attente interruptible
            for _ in range(ping_cfg["interval_seconds"]):
                if not running:
                    break
                time.sleep(1)
    finally:
        client.loop_stop()
        client.disconnect()
        log.info("Arrêté proprement.")


if __name__ == "__main__":
    main()
