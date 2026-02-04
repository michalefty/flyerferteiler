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

## 🔜 Roadmap & Offene Punkte

### 🖥️ Frontend & UX
- [x] **Datenschutz-Hinweis:** Expliziter Hinweis im UI, nur Kürzel/Vornamen zu verwenden (DSGVO).
- [x] **Daten: Überregionale Straßen (Backend):** Filter erweitert für Bundes-/Landesstraßen (primary/secondary).
- [x] **Farbkontrast:** Reservierte Straßen kontrastreicher gestalten (nicht grün/ähnlich zu "frei").
- [x] **Legende:** Farblegende für User/Status auf der Karte hinzufügen.
- [x] **Dark Mode Fix:** Lesbarkeit des PDF-Export-Buttons im Dark Theme korrigieren.
- [x] **Countdown:** Anzeige der verbleibenden Zeit für die aktuelle Abfrage/Session.
- [x] **Admin-Übersicht:** Dashboard für Admins: Anzahl eingetragener Helfer/User anzeigen.
- [x] **Sortierung nach Bereichen:** Straßenliste nach Nähe sortieren (Nachbarn zeigen), wenn eine Straße ausgewählt wird.

### 🛠️ Admin-CLI (`admin.py`) & Backend
- [x] **Anonymisierung:** Admin-Funktion zum Kürzen von Namen in der Datenbank (DSGVO).
- [x] **Backup Cleanup:** Funktion zum Löschen alter Backups implementieren.
- [x] **Abfragedauer:** Input-Prompt für die Dauer der Abfrage hinzufügen.
- [x] **Restore-Logik:** Restore vom letzten Status und Abfrage geänderter Straßen trennen.
- [x] **Server-Check:** Vor Neustart-Vorschlag prüfen, ob die Webseite tatsächlich nicht antwortet.
- [x] **Passwort-Prompt:** Admin-Passwort interaktiv abfragen, auch wenn es in `config.py` steht.

### 🗺️ Datenqualität & Algorithmus (Overpass/OSM)
- [x] **Overpass-Optimierung:** GPS-Koordinaten-Abfrage in `admin.py` optimieren.
- [x] **Hausnummern-Import:** Direkte Abfrage von `node["addr:housenumber"]` und `way` via Overpass API.
- [x] **Gewichtung:** Gebäude-Typ-Faktor einführen (z.B. `building=apartments` → höhere Flyer-Anzahl).
- [x] **Radius-Justierung:** Option prüfen, den Erfassungsradius für Häuser pro Straße konfigurierbar zu machen.

### 💤 Backlog / Später
- [ ] **Gebietssuche (Polygon):** Umstellung von reiner Straßensuche auf Polygon-Suche (besser für überregionale Straßen).

### 📄 PDF & Export
- [x] **Rendering-Check:** Prüfen, ob Karten im PDF durch HTTPS-Umstellung korrekt dargestellt werden (kein Spiegeln mehr).
- [x] **Asset-Pfade:** Sicherstellen, dass PDF-Library absolute Pfade oder lokale URLs (`http://127.0.0.1...`) nutzt.

### 📚 Dokumentation & Sonstiges
- [x] **Disclaimer:** In Doku und UI deutlich hinweisen: "Häuserzahlen sind Schätzungen".
- [x] **Easter Egg:** "Warum Flyerferteiler?" – Lustige Begründung/Story hinzufügen.
- [x] **Git-Workflow:** Nach Force-Push sicherstellen, dass Clients synchronisieren.