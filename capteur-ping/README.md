# Capteur Ping

Capteur de disponibilité réseau pour **Vigie**. Il ping une liste de machines à intervalle régulier et publie leur statut sur un broker MQTT.

## Installation

```bash
cd capteur-ping
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Éditer `config.json` :

- **mqtt** : adresse du broker, port, identifiants optionnels, préfixe de topic
- **ping** : intervalle entre les cycles (secondes), timeout et nombre de pings
- **machines** : liste des machines à surveiller (`hostname` + `ip`)

## Lancement

```bash
source venv/bin/activate
python3 capteur_ping.py
# ou avec un fichier de config custom
python3 capteur_ping.py /chemin/vers/config.json
```

Le capteur tourne en boucle et publie un message MQTT par machine à chaque cycle.

## Messages publiés

Topic : `vigie/lan/<hostname>` (par défaut)

Machine en ligne :
```json
{"type": "lan_status", "hostname": "serveur-web", "ip": "192.168.1.10", "status": "up"}
```

Machine hors ligne :
```json
{"type": "lan_status", "hostname": "serveur-web", "ip": "192.168.1.10", "status": "down"}
```

## Déploiement en service systemd

```bash
# Copier les fichiers
sudo mkdir -p /opt/vigie/capteur-ping
sudo cp -r . /opt/vigie/capteur-ping/

# Créer le venv sur place
cd /opt/vigie/capteur-ping
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt

# Installer et démarrer le service
sudo cp capteur-ping.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now capteur-ping
```

```bash
# Vérifier le statut
sudo systemctl status capteur-ping

# Voir les logs
sudo journalctl -u capteur-ping -f
```

## Arrêt

`Ctrl+C` en mode manuel, ou `sudo systemctl stop capteur-ping` pour le service.
