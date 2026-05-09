#!/usr/bin/env python3
"""
Capteur TTN — Subscribe aux uplinks bruts de The Things Network relayés
sur le broker MQTT local par ttn-bridge, normalise au format Vigie et
republie sur vigie/sensors/<nom>.
"""

import json
import socket
import sys
import time
import logging
import signal

import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("capteur-ttn")

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


def best_gateway(rx_metadata: list) -> dict:
    """Renvoie la passerelle au RSSI le plus élevé (signal le plus fort)."""
    if not rx_metadata:
        return {}
    return max(rx_metadata, key=lambda g: g.get("rssi", -9999))


def transform_uplink(raw: dict, devices_map: dict) -> dict:
    """Convertit un uplink TTN brut en message Vigie sensor_status.

    devices_map : {dev_eui_uppercase_no_dashes: {"name": str, "kind": Optional[str], "alarm": bool}}
    Fallback sur device_id si l'EUI n'est pas mappé. kind=None et alarm=False si non précisés.
    """
    end_device_ids = raw.get("end_device_ids", {})
    device_id = end_device_ids.get("device_id", "")
    dev_eui = (end_device_ids.get("dev_eui") or "").upper()

    entry = devices_map.get(dev_eui, {})
    name = entry.get("name") or device_id
    kind = entry.get("kind")
    alarm = bool(entry.get("alarm", False))

    uplink = raw.get("uplink_message", {})
    decoded = uplink.get("decoded_payload")
    f_cnt = uplink.get("f_cnt")
    gateway = best_gateway(uplink.get("rx_metadata", []))
    rssi = gateway.get("rssi")
    snr = gateway.get("snr")

    battery = uplink.get("last_battery_percentage") or {}
    battery_percent = battery.get("value")

    return {
        "type": "sensor_status",
        "emetteur": socket.gethostname(),
        "name": name,
        "kind": kind,
        "alarm": alarm,
        "device_id": device_id,
        "decoded": decoded,
        "rssi": rssi,
        "snr": snr,
        "f_cnt": f_cnt,
        "battery_percent": battery_percent,
        "received_at": raw.get("received_at"),
    }


def normalize_devices(raw_devices: dict) -> dict:
    """Normalise le mapping config.devices en {EUI: {name, kind, alarm}}.

    Accepte deux formes par device :
      - "EUI": "porte-entree"                                          (rétrocompatible)
      - "EUI": {"name": "porte-entree", "kind": "door", "alarm": true}

    `kind` est libre (utilisé côté consommateur pour choisir un rendu).
    `alarm` (bool, default False) est un drapeau : si True, le consommateur
    Vigie peut décider de notifier sur les transitions vers l'état "actif"
    de ce capteur (ex: porte ouverte, présence détectée).

    Les EUI sont mis en majuscules et débarrassés des tirets pour matcher
    indifféremment les variantes (`a8-40-...` ou `A84041...`).
    """
    out = {}
    for eui, value in (raw_devices or {}).items():
        key = eui.upper().replace("-", "")
        if isinstance(value, str):
            out[key] = {"name": value, "kind": None, "alarm": False}
        elif isinstance(value, dict):
            out[key] = {
                "name": value.get("name"),
                "kind": value.get("kind"),
                "alarm": bool(value.get("alarm", False)),
            }
        else:
            log.warning("devices.%s ignoré (type non supporté : %s)", eui, type(value).__name__)
    return out


def make_on_message(topic_prefix: str, devices_map: dict):
    """Factory pour le callback on_message. Le `client` est fourni par paho
    en premier argument du callback — pas besoin de closure dessus."""

    def on_message(client, _userdata, msg):
        try:
            raw = json.loads(msg.payload)
        except (ValueError, UnicodeDecodeError) as e:
            log.error("Payload TTN illisible sur %s : %s", msg.topic, e)
            return

        try:
            message = transform_uplink(raw, devices_map)
        except Exception as e:
            log.error("Échec transformation uplink (%s) : %s", msg.topic, e)
            return

        topic = f"{topic_prefix}/{message['name']}"
        client.publish(topic, json.dumps(message), qos=1, retain=True)
        log.info(
            "%s → %s (rssi=%s snr=%s f_cnt=%s bat=%s%%)",
            msg.topic, topic,
            message["rssi"], message["snr"], message["f_cnt"], message["battery_percent"],
        )

    return on_message


def make_on_connect(source_topic: str):
    def on_connect(client, _userdata, _flags, rc):
        if rc == 0:
            client.subscribe(source_topic, qos=1)
            log.info("Connecté au broker, abonné à %s", source_topic)
        else:
            log.error("Échec connexion MQTT (rc=%s)", rc)

    return on_connect


def connect_mqtt(cfg: dict, source_topic: str, topic_prefix: str, devices_map: dict) -> mqtt.Client:
    client = mqtt.Client(client_id=f"capteur-ttn-{socket.gethostname()}", clean_session=True)
    if cfg.get("username"):
        client.username_pw_set(cfg["username"], cfg.get("password", ""))

    client.on_message = make_on_message(topic_prefix, devices_map)
    client.on_connect = make_on_connect(source_topic)

    client.connect(cfg["broker"], cfg["port"], keepalive=60)
    client.loop_start()
    return client


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    config = load_config(config_path)

    mqtt_cfg = config["mqtt"]
    source_topic = config.get("source_topic", "ttn/devices/+/up")
    topic_prefix = mqtt_cfg.get("topic_prefix", "vigie/sensors")

    devices_map = normalize_devices(config.get("devices") or {})

    log.info(
        "Démarrage — broker=%s:%d, source=%s, prefix=%s, %d device(s) mappé(s)",
        mqtt_cfg["broker"], mqtt_cfg["port"], source_topic, topic_prefix, len(devices_map),
    )

    client = connect_mqtt(mqtt_cfg, source_topic, topic_prefix, devices_map)

    try:
        while running:
            time.sleep(1)
    finally:
        client.loop_stop()
        client.disconnect()
        log.info("Arrêté proprement.")


if __name__ == "__main__":
    main()
