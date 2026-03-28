# Capteur Backup

Capteur de suivi des sauvegardes pour **Vigie**. Il surveille les logs syslog (journald) pour détecter l'exécution des sauvegardes et publie leur statut sur un broker MQTT.

## Installation

```bash
cd capteur-backup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Éditer `config.json` :

- **mqtt** : adresse du broker, port, identifiants optionnels, préfixe de topic
- **check_interval_seconds** : intervalle entre les vérifications (secondes)
- **jobs** : liste des sauvegardes à surveiller
  - `name` : nom du job
  - `syslog_tag` : tag utilisé dans syslog/journald
  - `success_pattern` : texte présent dans le log en cas de succès
  - `failure_pattern` : texte présent dans le log en cas d'échec
  - `expected_every_hours` : délai max attendu entre deux sauvegardes (heures)

## Lancement

```bash
source venv/bin/activate
python3 capteur_backup.py
# ou avec un fichier de config custom
python3 capteur_backup.py /chemin/vers/config.json
```

## Messages publiés

Topic : `vigie/backup/<job_name>` (par défaut)

Sauvegarde réussie :
```json
{"type": "backup_status", "job": "rsync-pidrive", "status": "success", "detail": "Sauvegarde réussie", "last_run": "2026-03-23T02:00:12+00:00"}
```

Sauvegarde en échec :
```json
{"type": "backup_status", "job": "rsync-pidrive", "status": "failed", "detail": "Sauvegarde en échec", "last_run": "2026-03-23T02:00:12+00:00"}
```

Sauvegarde manquante :
```json
{"type": "backup_status", "job": "rsync-pidrive", "status": "missing", "detail": "Dernière sauvegarde il y a 200h (seuil : 192h)", "last_run": "2026-03-16T02:00:12+00:00"}
```

## Déploiement en service systemd

```bash
sudo ./install.sh
```

```bash
# Vérifier le statut
sudo systemctl status capteur-backup

# Voir les logs
sudo journalctl -u capteur-backup -f
```

## Arrêt

`Ctrl+C` en mode manuel, ou `sudo systemctl stop capteur-backup` pour le service.
