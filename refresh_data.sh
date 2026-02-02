#!/bin/bash
APP_DIR="/home/micha/app"
DATA_FILE="$APP_DIR/data/streets_status.json"
BACKUP_DIR="$APP_DIR/data/backups"

# Funktion für Zeitstempel-Logs
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

cd $APP_DIR || { log "❌ Fehler: Verzeichnis $APP_DIR nicht gefunden"; exit 1; }

# 1. Remote-Stand abrufen
git fetch origin main > /dev/null 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    log "🚀 Admin-Update auf GitHub erkannt!"

    # 2. Backup des alten Helfer-Standes
    if [ -f "$DATA_FILE" ]; then
        CITY=$(jq -r '.metadata.city' "$DATA_FILE")
        DATE=$(jq -r '.metadata.date' "$DATA_FILE")
        TS=$(date +"%H-%M")
        BACKUP_NAME="Abschluss_${CITY}_${DATE}_${TS}.json"
        
        log "📦 Erstelle Abschluss-Backup: $BACKUP_NAME"
        cp "$DATA_FILE" "$BACKUP_DIR/$BACKUP_NAME"
        
        git add "$BACKUP_DIR/$BACKUP_NAME"
        git commit -m "Archiv: Stand vor Gebietswechsel ($CITY)" > /dev/null 2>&1
        git push origin main > /dev/null 2>&1
    fi

    # 3. Code aktualisieren
    log "📥 Lade neues Zielgebiet und Code-Updates..."
    git reset --hard origin/main > /dev/null 2>&1
    
    # 4. Service neu starten
    sudo systemctl restart flyer
    log "✅ Service neu gestartet und auf aktuellem Stand."

else
    # Prüfen auf User-Eingaben (Server-seitig)
    git add "$DATA_FILE"
    if ! git diff --cached --quiet; then
        log "☁️ Synchronisiere User-Eingaben (neue Straßen belegt)..."
        git commit -m "User Update: Straßen übernommen" > /dev/null 2>&1
        git push origin main > /dev/null 2>&1
        log "✅ Synchronisation abgeschlossen."
    fi
    # Optional: Ein "Still Alive" Log alle x Durchläufe
    # log "Keine Änderungen vorhanden."
fi