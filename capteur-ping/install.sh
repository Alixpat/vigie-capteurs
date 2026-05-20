#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
CONF_DIR="/etc/vigie/capteur-ping"

echo "Installation du capteur-ping depuis : $DIR"

# Créer le venv si absent
if [ ! -d "$DIR/venv" ]; then
    echo "Création du venv..."
    python3 -m venv "$DIR/venv"
    "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"
fi

# Copier la config si elle n'existe pas
if [ ! -f "$CONF_DIR/config.json" ]; then
    echo "Copie de la configuration vers $CONF_DIR"
    mkdir -p "$CONF_DIR"
    cp "$DIR/config.example.json" "$CONF_DIR/config.json"
    echo "  → Pensez à éditer $CONF_DIR/config.json avec vos paramètres"
fi

# Générer le fichier service avec le bon chemin
sed "s|__WORKING_DIR__|$DIR|g" "$DIR/capteur-ping.service.template" \
    > /etc/systemd/system/capteur-ping.service

systemctl daemon-reload
systemctl enable --now capteur-ping

echo "Service capteur-ping installé et démarré."
echo "  → Configuration : $CONF_DIR/config.json"
echo "  → systemctl status capteur-ping"
echo "  → journalctl -u capteur-ping -f"
