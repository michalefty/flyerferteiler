# 🗺️ Flyer-Planer-Tool (GitOps Edition)

Ein interaktives Tool zur Planung von Flyer-Verteilaktionen. Admin-gesteuerte Gebietsauswahl via OpenStreetMap (OSM) und koordinierte Auswahl durch Helfer via Web-Interface.

## 🚀 Workflow
1. **Lokal:** Der Admin generiert mit `admin.py` ein Zielgebiet. Die Daten werden zu GitHub gepusht.
2. **VM:** Die Google Cloud VM erkennt Änderungen, sichert den aktuellen Helfer-Stand in den Backup-Ordner und lädt das neue Gebiet.
3. **User:** Helfer wählen über eine Karte (`Leaflet.js`) oder Liste ihre Straßen aus.

## 🛠️ Installation (Lokal)
1. Repository klonen: `git clone <repo-url>`
2. Venv erstellen: `python3 -m venv venv && source venv/bin/activate`
3. Abhängigkeiten installieren: `pip install -r requirements.txt`

## 🌍 Deployment (Server)
* **Plattform:** Google Cloud (e2-micro, Always Free)
* **Sync:** Das Skript `refresh_data.sh` läuft alle 2 Minuten via Cronjob.
* **Backup:** Alle abgeschlossenen Aktionen liegen unter `data/backups/`.

## 📂 Struktur
- `app.py`: Flask-Server (läuft auf der VM).
- `admin.py`: Lokales Tool zur Gebietsgenerierung.
- `data/streets_status.json`: Aktueller Status (Single Source of Truth).
- `refresh_data.sh`: Automatisierungsskript für die VM.