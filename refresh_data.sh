#!/bin/bash
APP_DIR="/home/micha/app"
DATA_FILE="$APP_DIR/data/streets_status.json"
BACKUP_DIR="$APP_DIR/data/backups"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

cd $APP_DIR || exit 1

git fetch origin main > /dev/null 2>&1
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    log "🚀 Admin-Update erkannt!"
    if [ -f "$DATA_FILE" ]; then
        CITY=$(jq -r '.metadata.city' "$DATA_FILE")
        BACKUP_NAME="Abschluss_${CITY}_$(date +'%H-%M').json"
        log "📦 Backup vor Update: $BACKUP_NAME"
        cp "$DATA_FILE" "$BACKUP_DIR/$BACKUP_NAME"
        git add "$BACKUP_DIR/$BACKUP_NAME"
        git commit -m "Archivierung vor Update" > /dev/null 2>&1
        git push origin main > /dev/null 2>&1
    fi
    git reset --hard origin/main > /dev/null 2>&1
    sudo systemctl restart flyer
    log "✅ Update durchgeführt und Service neu gestartet."
else
    git add "$DATA_FILE"
    if ! git diff --cached --quiet; then
        log "☁️ Synchronisiere User-Daten..."
        git commit -m "User Update" > /dev/null 2>&1
        git push origin main > /dev/null 2>&1
        log "✅ Synchronisiert."
    fi
fi