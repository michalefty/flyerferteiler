#!/bin/bash
APP_DIR="/home/micha/app"
DATA_FILE="$APP_DIR/data/streets_status.json"
BACKUP_DIR="$APP_DIR/data/backups"

cd $APP_DIR

# 1. Prüfen, ob der Admin auf GitHub etwas Neues hochgeladen hat
git fetch origin main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "🚀 Admin-Update erkannt!"

    # 2. BEVOR wir das neue Gebiet ziehen: Alten Helfer-Stand sichern
    if [ -f "$DATA_FILE" ]; then
        CITY=$(jq -r '.metadata.city' $DATA_FILE)
        DATE=$(jq -r '.metadata.date' $DATA_FILE)
        TS=$(date +"%H-%M")
        BACKUP_NAME="Abschluss_${CITY}_${DATE}_${TS}.json"
        
        echo "📦 Erstelle Abschluss-Backup: $BACKUP_NAME"
        cp $DATA_FILE "$BACKUP_DIR/$BACKUP_NAME"
        
        # Backup zu GitHub pushen zur Archivierung
        git add "$BACKUP_DIR/$BACKUP_NAME"
        git commit -m "Archiv: Stand vor Gebietswechsel ($CITY)"
        git push origin main
    fi

    # 3. Jetzt das neue Gebiet vom Admin laden
    echo "📥 Lade neues Zielgebiet..."
    git reset --hard origin/main
    
    # 4. App neu starten, um neue index.html oder Daten zu laden
    sudo systemctl restart flyer
else
    # Wenn der Admin nichts geändert hat, prüfen wir nur, 
    # ob die User-Eingaben (Server) zu GitHub gesichert werden sollen.
    # Hier machen wir KEIN Backup-File, sondern synchronisieren nur die Hauptdatei.
    git add $DATA_FILE
    if ! git diff --cached --quiet; then
        echo "☁️ Synchronisiere User-Eingaben mit GitHub..."
        git commit -m "User Update: Straßen übernommen"
        git push origin main
    fi
fi