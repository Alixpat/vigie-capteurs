#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installation du capteur-ping depuis : $DIR"

# Créer le venv si absent
if [ ! -d "$DIR/venv" ]; then
    echo "Création du venv..."
    python3 -m venv "$DIR/venv"
    "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"
fi

# Générer le fichier service avec le bon chemin
sed "s|__WORKING_DIR__|$DIR|g" "$DIR/capteur-ping.service.template" \
    > /etc/systemd/system/capteur-ping.service

systemctl daemon-reload
systemctl enable --now capteur-ping

echo "Service capteur-ping installé et démarré."
echo "  → systemctl status capteur-ping"
echo "  → journalctl -u capteur-ping -f"
