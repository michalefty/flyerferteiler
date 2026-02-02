#!/bin/bash

# Pfad-Definitionen
APP_DIR="/home/micha/app"
DATA_FILE="$APP_DIR/data/streets_status.json"
BACKUP_DIR="$APP_DIR/data/backups"
LOG_FILE="$APP_DIR/sync.log"
MAX_LOG_SIZE=10485760 # 10 MB in Bytes

# Log-Funktion mit Zeitstempel
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# --- NEU: Log-Rotation ---
if [ -f "$LOG_FILE" ]; then
    FILE_SIZE=$(stat -c%s "$LOG_FILE")
    if [ "$FILE_SIZE" -gt "$MAX_LOG_SIZE" ]; then
        # Behalte die letzten 100 Zeilen und leere den Rest
        TMP_LOG=$(tail -n 100 "$LOG_FILE")
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] 🔄 Log-Rotation: Datei war zu groß ($FILE_SIZE Bytes). Geleert." > "$LOG_FILE"
        echo "$TMP_LOG" >> "$LOG_FILE"
    fi
fi

# In das Verzeichnis wechseln
cd "$APP_DIR" || { log "❌ Verzeichnis nicht gefunden"; exit 1; }

# 1. Updates von GitHub holen
git fetch origin main > /dev/null 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    log "🚀 Admin-Update erkannt!"
    
    # Backup des alten Stands (Häkchen der Helfer)
    if [ -f "$DATA_FILE" ]; then
        CITY=$(jq -r '.metadata.city // "Unbekannt"' "$DATA_FILE")
        TS=$(date +"%Y-%m-%d_%H-%M")
        BACKUP_NAME="Abschluss_${CITY}_${TS}.json"
        
        mkdir -p "$BACKUP_DIR"
        cp "$DATA_FILE" "$BACKUP_DIR/$BACKUP_NAME"
        
        log "📦 Backup erstellt: $BACKUP_NAME"
        git add "$BACKUP_DIR/$BACKUP_NAME"
        git commit -m "Archiv: $BACKUP_NAME" > /dev/null 2>&1
    fi

    # Code auf den Stand von GitHub bringen
    log "📥 Aktualisiere auf neuen Admin-Stand..."
    git reset --hard origin/main > /dev/null 2>&1
    
    # App neu starten
    sudo systemctl restart flyer
    log "✅ Update abgeschlossen und Service neu gestartet."

else
    # 2. Nur User-Änderungen (Häkchen) sichern
    git add "$DATA_FILE"
    if ! git diff --cached --quiet; then
        log "☁️ Synchronisiere Helfer-Daten mit GitHub..."
        git commit -m "User Update: Straßen übernommen" > /dev/null 2>&1
        git push origin main > /dev/null 2>&1
        log "✅ Synchronisation erfolgreich."
    fi
fi
