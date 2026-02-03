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
- [ ] Die Dauer der Abfrage bitte als input (standart aus config.py)
- [ ] admin.py Den restore vom letzten status und die geänderten straßen getrennt abfragen
- [ ] wäre es eine Möglichkeit den Bereich der Häuser die zu einer Straße gehören zu verkleiner oder vergrößern? Denn aktuell sind noch nicht annähernd alle Häuser erfasst.
- [ ] In der Doku und auch in der anzeige immer wieder drauf hinweisen das die Häuser pro Straße nur eine Schätzung sind.
- [ ] Der Admin sollte eine Übersicht erhalten - wieviele Leute ich eingetragen haben...
- [ ] die Farben der Staßen die von den Usern reserviert werden sollten nicht grün/ähnlich sein größerer Kontrast.
- [ ] wäre eine Legende mit den Farben == User möglich?
- [ ] checken ob Webseite antwortet bevor vorgeschlagen wird dass sie neu gestartet werden soll.
- [ ] lustige begründung warum flyerferteiler und nich flyerverteiler
- [ ] ein countdown wie lange die abfrage noch läuft
- [ ] beim dark-theme wird der pdf-export button nicht lesbar
- [ ] das passwort für den admin-zugang wird in der config.py gesetzt, bitte trotzdem bei admin.py nachfragen
