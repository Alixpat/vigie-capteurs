# Capteur TTN

Capteur passerelle pour **Vigie**. Subscribe aux uplinks bruts de The Things Network relayés par `ttn-bridge` sur le broker MQTT local, normalise au format Vigie et republie sur `vigie/sensors/<nom>`.

Sert de couche d'adaptation entre le format TTN (JSON nested ~1.5 KB) et le format compact attendu par les consommateurs Vigie.

## Pré-requis

Un service en amont qui republie les uplinks TTN sur le broker local au topic `ttn/devices/<dev-eui>/up` (par défaut, `ttn-bridge` dans le dépôt `pidesk`). Sans ça, le capteur attend dans le vide.

## Installation

```bash
cd capteur-ttn
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Éditer `config.json` :

- **mqtt** : adresse du broker, port, identifiants optionnels, préfixe de topic de sortie
- **source_topic** : pattern d'abonnement aux uplinks bruts (défaut `ttn/devices/+/up`)
- **devices** : mapping `dev_eui → infos device`. Les EUI sont normalisés en majuscules sans tirets, donc `"A84041FFB184F8F4"` ou `"a8-40-41-ff-b1-84-f8-f4"` sont équivalents. Deux formats acceptés par device :
  - Forme courte : `"EUI": "porte-entree"` (kind=null, alarm=false)
  - Forme complète : `"EUI": {"name": "porte-entree", "kind": "door", "alarm": true}`

  Champs optionnels :
  - `kind` (string) : utilisé par le consommateur Vigie pour choisir un rendu adapté (ex. `door`, `temperature`, `motion`).
  - `alarm` (bool, default `false`) : si `true`, l'app Android Vigie déclenche une notification système quand ce capteur passe à l'état "actif" (porte ouverte pour `kind=door`, présence pour `kind=motion`), à condition que le toggle alarme soit activé dans l'app.

  Si un device n'est pas mappé du tout, le `device_id` TTN est utilisé comme nom (ex. `eui-a84041ffb184f8f4`), `kind` reste `null` et `alarm` reste `false`.

## Lancement

```bash
source venv/bin/activate
python3 capteur_ttn.py
# ou avec un fichier de config custom
python3 capteur_ttn.py /chemin/vers/config.json
```

## Messages publiés

Topic : `vigie/sensors/<nom>` (par défaut)

Les champs `decoded`, `rssi`, `snr`, `f_cnt`, `battery_percent`, `received_at` peuvent être `null` si absents de l'uplink. Le `decoded` est forwardé tel quel — sa structure dépend du décodeur configuré côté TTN pour chaque type de capteur.

Exemple pour un Dragino LDS02 (capteur de porte) :

```json
{
  "type": "sensor_status",
  "emetteur": "pidesk",
  "name": "porte-entree",
  "kind": "door",
  "alarm": true,
  "device_id": "eui-a84041ffb184f8f4",
  "decoded": {
    "ALARM": 0,
    "BAT_V": 2.958,
    "DOOR_OPEN_STATUS": 1,
    "DOOR_OPEN_TIMES": 29,
    "LAST_DOOR_OPEN_DURATION": 0,
    "MOD": 1
  },
  "rssi": -75,
  "snr": 10,
  "f_cnt": 39,
  "battery_percent": 39.13,
  "received_at": "2026-05-09T10:40:47.319Z"
}
```

Le `rssi` et `snr` proviennent de la passerelle au signal le plus fort lorsque plusieurs gateways ont reçu l'uplink.

Tous les messages sont publiés avec le flag **retain** : le broker conserve le dernier état de chaque capteur.

## Déploiement en service systemd

```bash
sudo ./install.sh
```

```bash
sudo systemctl status capteur-ttn
sudo journalctl -u capteur-ttn -f
```

Le service est lié à `mosquitto.service` (`Requires=`) puisqu'il consomme et publie sur le broker local.

## Arrêt

`Ctrl+C` en mode manuel, ou `sudo systemctl stop capteur-ttn` pour le service.
