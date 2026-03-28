#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installation du capteur-backup depuis : $DIR"

# Créer le venv si absent
if [ ! -d "$DIR/venv" ]; then
    echo "Création du venv..."
    python3 -m venv "$DIR/venv"
    "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"
fi

# Générer le fichier service avec le bon chemin
sed "s|__WORKING_DIR__|$DIR|g" "$DIR/capteur-backup.service.template" \
    > /etc/systemd/system/capteur-backup.service

systemctl daemon-reload
systemctl enable --now capteur-backup

echo "Service capteur-backup installé et démarré."
echo "  → systemctl status capteur-backup"
echo "  → journalctl -u capteur-backup -f"
