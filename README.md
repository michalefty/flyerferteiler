# 📍 Flyer-Verteiler Webtool

Dieses Tool hilft dabei, die Flyerverteilung in einer Ortschaft zu koordinieren. Nutzer können sich Straßen zuweisen, die dann für andere gesperrt werden.

## Sicherheit & Passwort
Aus Sicherheitsgründen wird das Passwort nicht mit hochgeladen. 

1. Erstelle lokal eine Datei `config.py`.
2. Schreibe hinein: `SECRET_KEY = "dein_passwort"`.
3. Auf dem Server (z.B. Render.com): Erstelle die Datei dort manuell oder nutze die "Environment Variables", um `SECRET_KEY` zu setzen (siehe oben).

## 1. Lokale Vorbereitung
Bevor du das Tool hochlädst, musst du die Straßendaten für deinen Ort generieren.

1. Installiere die Voraussetzungen: `pip install requests`
2. Nutze das Admin-Skript (Python), um die `data/streets_status.json` zu erstellen.
3. Starte das Tool lokal mit `python app.py`, um das Design zu prüfen.

## 2. Deployment (Hosting)
Wir nutzen **Render.com**, um das Tool kostenlos online zu stellen.

### Einstellungen bei Render:
- **Runtime:** Python
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn -k eventlet -w 1 app:app`
- **Region:** Frankfurt (eu-central-1) für beste Geschwindigkeit in DE.

### Wichtig: Speicherung aktivieren
Da wir keine Datenbank nutzen, musst du bei Render unter dem Reiter **"Disk"** eine Festplatte hinzufügen:
- **Name:** data-storage
- **Mount Path:** `/data`
- **Size:** 1GB (reicht völlig aus)

Dadurch bleibt der Status der Straßen erhalten, auch wenn der Server neu startet.

## 3. Nutzung
1. Nach dem Deployment erhältst du von Render einen Link (z.B. `https://flyer-tool.onrender.com`).
2. **Link verschicken:** Diesen Link kannst du einfach per WhatsApp oder E-Mail an die Helfer senden.
3. **Bedienung:** Helfer geben ihren Namen ein, klicken auf "Nehmen" und können sich am Ende ihre Liste exportieren.