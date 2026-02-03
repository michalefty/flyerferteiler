# 🗺️ Flyer-Planer (GitOps Edition)

Ein robustes, Git-basiertes Tool zur Koordinierung von Flyer-Verteilaktionen. Es kombiniert ein lokales Python-Admin-Tool mit einer leichtgewichtigen Flask-Webanwendung in der Cloud.

## 🏗️ Architektur
Das System folgt einem "GitOps"-Ansatz:
1. **Single Source of Truth:** Der Zustand (Straßen, Bearbeiter) wird in `data/streets_status.json` gespeichert.
2. **Admin (Lokal):** Erstellt neue Gebiete und plant die VM-Laufzeit.
3. **Server (Cloud VM):** Synchronisiert sich automatisch via Git, hostet die Web-App und erstellt Backups.
4. **Datenfluss:** `Admin -> Push -> GitHub -> Pull -> VM -> Web-UI`.

## ✅ Voraussetzungen

### 💻 Lokal (Admin-Computer)
Damit du das Admin-Tool nutzen kannst, benötigst du:
* **Python 3.8+**
* **Git** (konfiguriert mit Zugriff auf das Repo)
* **Google Cloud CLI (`gcloud`)** (für das Starten/Stoppen der VM)
   * *Installation:* [Cloud SDK Doku](https://cloud.google.com/sdk/docs/install)
   * *Login:* `gcloud auth login`

### ☁️ Server (Cloud VM)
Die VM (z.B. Debian/Ubuntu) benötigt folgende System-Pakete:
* **Python 3 + pip** (für die App)
* **Git** (für den Sync)
* **jq** (für JSON-Parsing im Bash-Skript)

## 🛠️ Installation & Einrichtung

### 1. Lokale Einrichtung (Admin)
```bash
# 1. Repository klonen
git clone <dein-repo-url>
cd flyerferteiler

# 2. Virtuelle Umgebung erstellen
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Python-Abhängigkeiten installieren
pip install -r requirements.txt

# 4. Config erstellen (Optional, falls nicht im Env)
# Erstelle eine config.py mit deinen Cloud-Einstellungen (siehe unten)
```

### 2. Server Einrichtung (VM)
Verbinde dich per SSH auf deine VM und führe folgendes aus:

```bash
# 1. System-Pakete installieren
sudo apt update
sudo apt install -y python3-venv git jq

# 2. Repository klonen
git clone <dein-repo-url> ~/app
cd ~/app

# 4. App installieren
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Systemd Service einrichten (Beispiel)
# Erstelle /etc/systemd/system/flyer.service
# ... ExecStart=/home/micha/app/venv/bin/gunicorn -w 4 -b 0.0.0.0:80 app:app
```

## 🚀 Benutzung (Workflow)

### 1. Neues Gebiet erstellen
Starte das Admin-Skript lokal:
```bash
python admin.py
```
* Gib die PLZ(s) ein (z.B. `63834`).
* Das Tool lädt Daten von OpenStreetMap (Overpass API).
* Es berechnet Straßenlängen, schätzt Haushalte und teilt lange Straßen auf.

### 2. Deployment & Start
Am Ende des Admin-Skripts wirst du gefragt:
* **Git Push?** Lädt die neuen Daten zu GitHub hoch.
* **VM Starten?** Startet die Google Cloud Instanz via `gcloud`.
* **Timer setzen?** Plant den Shutdown der VM (z.B. nach 7 Tagen) mittels `shutdown` Befehl.

### 3. Während der Aktion
* Helfer rufen die Webseite auf.
* Klicken auf Straßen, um sie zu reservieren ("Ich mache das!").
* Der Server synchronisiert alle paar Minuten die Änderungen zurück ins Git (`refresh_data.sh` via Cronjob).

## ⚙️ Konfiguration (`config.py`)
Erstelle eine `config.py` im Stammverzeichnis, um `admin.py` anzupassen:

```python
# config.py
CLOUD_PROVIDER = 'gcloud'       # oder 'none'
VM_INSTANCE_NAME = 'flyer-server'
VM_ZONE = 'europe-west3-c'
SURVEY_DURATION_DAYS = 7        # Automatische Abschaltung nach X Tagen
ADMIN_PASSWORD = 'deinSicheresPasswort' # Für Admin-Funktionen im Web
```

## 🐛 Troubleshooting

* **VM fährt nicht herunter?**
  * Prüfe auf der VM, ob `at` installiert ist: `which at`
  * Prüfe die Queue: `sudo atq`
* **Keine neuen Daten im Web?**
  * Prüfe das Log auf der VM: `tail -f sync.log`
  * Läuft der Cronjob für `refresh_data.sh`?
