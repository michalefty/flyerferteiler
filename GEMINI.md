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
- [x] **Stundenanzeige:** Die Stundenanzeige zeigt nun die gesamte verbleibende Laufzeit (Tage + Stunden) an.
- [x] **Scroll-Verhalten:** Overlay ("Map Lock") hinzugefügt, um versehentliches Scrollen auf Mobilgeräten zu verhindern.

### 🛠️ Admin-CLI (`admin.py`) & Backend
- [x] **Anonymisierung:** Admin-Funktion zum Kürzen von Namen in der Datenbank (DSGVO).
- [x] **Backup Cleanup:** Funktion zum Löschen alter Backups implementieren.
- [x] **Abfragedauer:** Input-Prompt für die Dauer der Abfrage hinzufügen.
- [x] **Restore-Logik:** Restore vom letzten Status und Abfrage geänderter Straßen trennen.
- [x] **Server-Check:** Vor Neustart-Vorschlag prüfen, ob die Webseite tatsächlich nicht antwortet.
- [x] **Passwort-Prompt:** Admin-Passwort interaktiv abfragen, auch wenn es in `config.py` steht.
- [x] **VM-Start-Check:** `admin.py` prüft vor Aktionen, ob der Server läuft, und startet ihn bei Bedarf.
- [x] **Shutdown/Index-Off:** `index_off.html` wird bei Ablauf der Zeit angezeigt; Server-Shutdown deaktiviert.

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
- [x] **Git-Workflow:** Nach Force-Push sicherstellen, dass Clients synchronisieren.
- [x] **Lizenz:** Projekt auf EUPL v1.2 umgestellt.

- [x] **API & Netcup:** API gegen netcup zur änderung wenn sich die öffentliche IP der VM ändert. ipadresse im DNS ändern hinweis das es länger dauert bis die DNS-änderung repliziert ist.
- [x] **PDF Zoom:** Die Karte beim PDF braucht mehr ein-zoom auf den bbox von den gewählten Straßen sonst erkennt man auf dem Ausdruck nix
- [x] **Map Width:** Die Karte nicht über die volle breite der Seite um ein besseres Scollen zu ermöglichen.
- [x] **PDF Workflow:** check: Suggested Workflow For a quick, front-end solution, integrate leaflet-easyPrint... -> *Evaluated: Improved existing jsPDF solution.*
- [x] **Admin Safety:** wir brauchen einen check im admin-py ob noch eine flyer-aktion aktuell läuft und wie lange mit rückmeldung zum user bevor wir updates einspielen.

- [ ] nur vorerst eine idee: wie könnte man mehrere flyeraktion laufen lassen?
