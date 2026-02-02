# 🤖 Gemini AI Context: Flyer-Planer Project

## 🎯 Projekt-Status
- **Architektur:** Flask-Webapp mit JSON-Backend (keine SQL-DB).
- **Deployment:** Google Cloud VM (Debian/Ubuntu) mit Git-basiertem Sync-Mechanismus.
- **Speichermodell:** Atomic Replacement (Admin-Push überschreibt VM-Stand nach automatischem Backup).

## 🛠️ Technische Details
- **Backend:** Python 3.11+, Flask, Gunicorn.
- **Frontend:** HTML5, Leaflet.js (Karten), JavaScript (Fetch-API).
- **Automatisierung:** Bash-Skripting mit `jq` zur JSON-Verarbeitung auf der VM.
- **Daten:** `data/streets_status.json` mit `metadata` und `streets` Keys.

## 📜 Getroffene Entscheidungen
- **GitOps:** GitHub dient als Zwischenspeicher und Historie.
- **Backups:** VM erstellt vor jedem Pull ein Backup in `data/backups/`.
- **Sektorisierung:** Admin-Skript berechnet Sektoren basierend auf Helferanzahl.

## 🔜 Nächste Schritte / Offene Punkte
- [ ] Overpass-Query im `admin.py` für GPS-Koordinaten optimieren.
- [ ] User-Interface-Feinschliff (Filter für Sektoren).
- [ ] Cleanup-Funktion für alte Backups im `admin.py`.