#!/usr/bin/env python3
"""
Capteur Internet — Vérifie la connectivité internet en pingant
des cibles externes et publie le statut sur un broker MQTT au format Vigie.
"""

import json
import re
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
log = logging.getLogger("capteur-internet")

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
    client = mqtt.Client(client_id="capteur-internet", clean_session=True)
    if cfg.get("username"):
        client.username_pw_set(cfg["username"], cfg.get("password", ""))
    client.connect(cfg["broker"], cfg["port"], keepalive=60)
    client.loop_start()
    return client


def ping_host(host: str, count: int = 3, timeout: int = 5) -> dict:
    """Ping une cible et renvoie le statut + la latence moyenne."""
    param_count = "-n" if platform.system().lower() == "windows" else "-c"
    param_timeout = "-w" if platform.system().lower() == "windows" else "-W"
    try:
        result = subprocess.run(
            ["ping", param_count, str(count), param_timeout, str(timeout), host],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return {"reachable": False, "latency_ms": None}

        # Extraire la latence moyenne depuis la sortie de ping
        # Linux : "rtt min/avg/max/mdev = 10.0/12.5/15.0/2.5 ms"
        match = re.search(r"=\s*[\d.]+/([\d.]+)/", result.stdout)
        latency = float(match.group(1)) if match else None

        return {"reachable": True, "latency_ms": latency}
    except FileNotFoundError:
        log.error("Commande ping introuvable")
        return {"reachable": False, "latency_ms": None}


def build_message(name: str, host: str, ping_result: dict) -> dict:
    return {
        "type": "internet_status",
        "name": name,
        "host": host,
        "status": "up" if ping_result["reachable"] else "down",
        "latency_ms": ping_result["latency_ms"],
    }


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    config = load_config(config_path)

    mqtt_cfg = config["mqtt"]
    targets = config["targets"]
    ping_cfg = config["ping"]
    interval = config["check_interval_seconds"]

    log.info(
        "Démarrage — broker=%s:%d, %d cible(s), intervalle=%ds",
        mqtt_cfg["broker"], mqtt_cfg["port"], len(targets), interval,
    )

    client = connect_mqtt(mqtt_cfg)
    topic_prefix = mqtt_cfg.get("topic_prefix", "vigie/internet")

    try:
        while running:
            for target in targets:
                name = target["name"]
                host = target["host"]

                result = ping_host(
                    host,
                    count=ping_cfg.get("count", 3),
                    timeout=ping_cfg.get("timeout_seconds", 5),
                )

                latency_str = f"{result['latency_ms']:.1f}ms" if result["latency_ms"] else "N/A"
                status_str = "up" if result["reachable"] else "down"
                log.info("%s (%s) : %s — %s", name, host, status_str, latency_str)

                message = build_message(name, host, result)
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
