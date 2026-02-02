#!/bin/bash
APP_DIR="/home/micha/app"
DATA_FILE="$APP_DIR/data/streets_status.json"
BACKUP_DIR="$APP_DIR/data/backups"

cd $APP_DIR

# 1. Backup der aktuellen Helfer-Daten (wie gehabt)
if [ -f "$DATA_FILE" ]; then
    CITY=$(jq -r '.metadata.city' $DATA_FILE)
    TS=$(date +"%Y-%m-%d_%H-%M")
    BACKUP_NAME="${CITY}_${TS}.json"
    cp $DATA_FILE "$BACKUP_DIR/$BACKUP_NAME"
    
    git add "$BACKUP_DIR/$BACKUP_NAME"
    git add $DATA_FILE
    if ! git diff --cached --quiet; then
        git commit -m "Automatisches Backup: $BACKUP_NAME"
        git push origin main
    fi
fi

# 2. Prüfen, ob es Updates auf GitHub gibt
git fetch origin main

# Wir vergleichen den lokalen Stand mit dem Stand auf GitHub
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "🔄 Änderungen erkannt. Aktualisiere Code und starte Service neu..."
    
    # Änderungen ziehen
    git reset --hard origin/main
    
    # 3. Den Service neu starten
    # Da wir den Code geändert haben (z.B. index.html), muss Flask neu laden
    sudo systemctl restart flyer
    
    echo "✅ Update erfolgreich durchgeführt."
else
    echo "| Keine Code-Änderungen auf GitHub gefunden."
fi