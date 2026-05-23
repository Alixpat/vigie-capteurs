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

Le repo versionne uniquement `config.example.json` (template). La config réelle vit dans `/etc/vigie/capteur-internet/config.json` sur la machine et n'est pas committée — `install.sh` la crée à partir du template au premier déploiement, à éditer ensuite avec les vrais paramètres.

Champs :

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

Le payload inclut le statut courant ainsi que les informations sur la dernière coupure détectée (depuis le démarrage du capteur). Les champs `last_downtime_*` sont `null` tant qu'aucune coupure n'a été observée.

Cible joignable, aucune coupure depuis le démarrage :
```json
{
  "type": "internet_status",
  "name": "google",
  "host": "8.8.8.8",
  "status": "up",
  "latency_ms": 12.5,
  "last_downtime_start": null,
  "last_downtime_end": null,
  "last_downtime_duration_minutes": null
}
```

Cible injoignable :
```json
{
  "type": "internet_status",
  "name": "google",
  "host": "8.8.8.8",
  "status": "down",
  "latency_ms": null,
  "last_downtime_start": null,
  "last_downtime_end": null,
  "last_downtime_duration_minutes": null
}
```

Cible rétablie après une coupure :
```json
{
  "type": "internet_status",
  "name": "google",
  "host": "8.8.8.8",
  "status": "up",
  "latency_ms": 12.5,
  "last_downtime_start": "2026-05-08T09:12:03+00:00",
  "last_downtime_end": "2026-05-08T09:18:45+00:00",
  "last_downtime_duration_minutes": 6.7
}
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
