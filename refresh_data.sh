#!/bin/bash
# crontab: */2 * * * * /home/ubuntu/app/refresh_data.sh >> /home/ubuntu/app/sync.log 2>&1
# Pfad zu deiner App auf der VM
APP_DIR="/home/ubuntu/app"
DATA_FILE="$APP_DIR/data/streets_status.json"
BACKUP_DIR="$APP_DIR/data/backups"

cd $APP_DIR

# 1. Sicherstellen, dass Verzeichnisse existieren
mkdir -p $BACKUP_DIR

# 2. Backup des aktuellen Helfer-Standes erstellen
if [ -f "$DATA_FILE" ]; then
    # Stadtname und Datum für den Dateinamen extrahieren
    CITY=$(jq -r '.metadata.city' $DATA_FILE)
    # Sonderzeichen entfernen
    CITY_CLEAN=$(echo $CITY | tr -dc '[:alnum:]\n\r' | tr ' ' '_')
    TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")
    BACKUP_NAME="${CITY_CLEAN}_${TIMESTAMP}.json"

    # Datei physisch kopieren
    cp $DATA_FILE "$BACKUP_DIR/$BACKUP_NAME"

    # In Git sichern
    git add "$BACKUP_DIR/$BACKUP_NAME"
    git add $DATA_FILE
    
    # Nur committen, wenn es Änderungen gab (z.B. neue Häkchen)
    if ! git diff --cached --quiet; then
        git commit -m "Automatisches Backup: $BACKUP_NAME"
        git push origin main
    fi
fi

# 3. Neue Daten vom Admin (GitHub) erzwingen
echo "Lade neue Admin-Daten von GitHub..."
git fetch origin main
git reset --hard origin/main

# 4. Berechtigungen sicherstellen und App neu starten
sudo systemctl restart flyer
echo "Refresh abgeschlossen: $(date)"