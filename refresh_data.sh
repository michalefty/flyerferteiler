#!/bin/bash

# Pfade
APP_DIR="/home/micha/app"
DATA_FILE="$APP_DIR/data/streets_status.json"
BACKUP_DIR="$APP_DIR/data/backups"
LOG_FILE="$APP_DIR/sync.log"
MAX_LOG_SIZE=5242880 # 5 MB (etwas kleiner gewählt für schnellere Rotation)

# Log-Funktion mit Zeitstempel
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# --- 1. Log-Rotation (Sicherheits-Check) ---
if [ -f "$LOG_FILE" ]; then
    FILE_SIZE=$(stat -c%s "$LOG_FILE")
    if [ "$FILE_SIZE" -gt "$MAX_LOG_SIZE" ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        touch "$LOG_FILE"
        chmod 666 "$LOG_FILE"
        log "🔄 Log-Rotation durchgeführt (Alte Datei unter sync.log.old)"
    fi
fi

# --- 2. Heartbeat ---
log "⏱️ Cronjob-Lauf gestartet..."

# In das Verzeichnis wechseln
cd "$APP_DIR" || { echo "❌ Verzeichnis nicht gefunden" >> "$LOG_FILE"; exit 1; }

# --- 3. Updates von GitHub holen ---
# Wir nutzen --quiet, um das Log sauber zu halten
git fetch origin main > /dev/null 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    log "🚀 Admin-Update auf GitHub erkannt!"
    
    if [ -f "$DATA_FILE" ]; then
        CITY=$(jq -r '.metadata.city // "Unbekannt"' "$DATA_FILE")
        TS=$(date +"%Y-%m-%d_%H-%M")
        BACKUP_NAME="Abschluss_${CITY}_${TS}.json"
        
        mkdir -p "$BACKUP_DIR"
        cp "$DATA_FILE" "$BACKUP_DIR/$BACKUP_NAME"
        
        log "📦 Backup erstellt: $BACKUP_NAME"
        git add "$BACKUP_DIR/$BACKUP_NAME"
        git commit -m "Archiv: $BACKUP_NAME" > /dev/null 2>&1
        git push origin main > /dev/null 2>&1
    fi

    log "📥 Aktualisiere auf neuen Admin-Stand..."
    git reset --hard origin/main > /dev/null 2>&1
    
    # Neustart des Service
    if sudo systemctl restart flyer; then
        log "✅ Service erfolgreich neu gestartet."
    else
        log "❌ FEHLER: systemctl restart flyer fehlgeschlagen!"
    fi

else
    # --- 4. User-Änderungen sichern ---
    git add "$DATA_FILE"
    if ! git diff --cached --quiet; then
        log "☁️ Synchronisiere Helfer-Daten mit GitHub..."
        if git commit -m "User Update: Straßen übernommen" > /dev/null 2>&1; then
            git push origin main > /dev/null 2>&1
            log "✅ Synchronisation erfolgreich."
        else
            log "⚠️ Commit fehlgeschlagen (evtl. keine echten Änderungen)."
        fi
    else
        log "😴 Keine Änderungen vorhanden."
    fi
fi