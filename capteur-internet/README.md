# Capteur Internet

Capteur de connectivité internet pour **Vigie**. Il ping des cibles externes à intervalle régulier et publie le statut + latence sur un broker MQTT.

## Installation

```bash
cd capteur-internet
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Éditer `config.json` :

- **mqtt** : adresse du broker, port, identifiants optionnels, préfixe de topic
- **check_interval_seconds** : intervalle entre les vérifications (secondes)
- **targets** : liste des cibles à pinger (`name` + `host`)
- **ping** : nombre de pings et timeout

## Lancement

```bash
source venv/bin/activate
python3 capteur_internet.py
# ou avec un fichier de config custom
python3 capteur_internet.py /chemin/vers/config.json
```

## Messages publiés

Topic : `vigie/internet/<name>` (par défaut)

Cible joignable :
```json
{"type": "internet_status", "name": "google-dns", "host": "8.8.8.8", "status": "up", "latency_ms": 12.5}
```

Cible injoignable :
```json
{"type": "internet_status", "name": "google-dns", "host": "8.8.8.8", "status": "down", "latency_ms": null}
```

Résumé global (topic `vigie/internet/global`) :
```json
{"type": "internet_status", "name": "global", "status": "up"}
```

Tous les messages sont publiés avec le flag **retain** : le broker conserve le dernier état, ce qui permet de le récupérer même après une reconnexion.

## Déploiement en service systemd

```bash
sudo ./install.sh
```

```bash
sudo systemctl status capteur-internet
sudo journalctl -u capteur-internet -f
```

## Arrêt

`Ctrl+C` en mode manuel, ou `sudo systemctl stop capteur-internet` pour le service.
