import os
import datetime
from datetime import datetime
import shutil
import subprocess
import json

try:
    import config
except ImportError:
    config = None

def restore_backup():
    print("\n--- ⏪ RESTORE BACKUP ---")
    backup_dir = 'data/backups'
    target_file = 'data/streets_status.json'
    
    if not os.path.exists(backup_dir):
        print(f"❌ Verzeichnis '{backup_dir}' nicht gefunden.")
        return

    # List all JSON files
    files = [f for f in os.listdir(backup_dir) if f.endswith('.json')]
    if not files:
        print("ℹ️ Keine Backups gefunden.")
        return

    # Sort by modification time (newest first)
    files.sort(key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)), reverse=True)
    
    print(f"Verfügbare Backups:")
    for i, f in enumerate(files[:10]):
        dt = datetime.fromtimestamp(os.path.getmtime(os.path.join(backup_dir, f))).strftime('%d.%m.%Y %H:%M')
        print(f"{i+1}. {f} ({dt})")
        
    choice = input("\nBackup wählen (Nummer) oder '0' für Abbruch: ").strip()
    if not choice.isdigit() or choice == '0': return
    
    idx = int(choice) - 1
    if idx < 0 or idx >= len(files):
        print("❌ Ungültige Auswahl.")
        return
        
    selected_file = os.path.join(backup_dir, files[idx])
    
    print(f"\n⚠️  Achtung: Überschreibe '{target_file}' mit '{files[idx]}'!")
    if input("Wirklich wiederherstellen? (j/n): ").strip().lower() == 'j':
        try:
            shutil.copy2(selected_file, target_file)
            print("✅ Wiederherstellung erfolgreich.")
            
            # Git Push Option (since we changed data)
            if input("🚀 Änderungen zu GitHub pushen? (j/n): ").strip().lower() == 'j':
                 subprocess.run(["git", "add", target_file], check=True)
                 msg = f"Restore Backup: {files[idx]}"
                 subprocess.run(["git", "commit", "-m", msg], check=True)
                 remote = getattr(config, 'GIT_REMOTE_URL', 'origin') if config else 'origin'
                 branch = getattr(config, 'GIT_BRANCH', 'main') if config else 'main'
                 subprocess.run(["git", "push", remote, branch], check=True)
                 print("✅ Push erfolgreich!")
                 
        except Exception as e:
            print(f"❌ Fehler: {e}")

def cleanup_backups():
    print("\n--- 🧹 Backups Bereinigen ---")
    backup_dir = 'data/backups'
    if not os.path.exists(backup_dir):
        print(f"❌ Verzeichnis '{backup_dir}' nicht gefunden.")
        return

    # List all JSON files
    files = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith('.json')]
    if not files:
        print("ℹ️ Keine Backups gefunden.")
        return

    # Sort by modification time (newest first)
    files.sort(key=os.path.getmtime, reverse=True)

    print(f"📦 Gesamtanzahl Backups: {len(files)}")
    print(f"🆕 Neuestes: {os.path.basename(files[0])} ({datetime.fromtimestamp(os.path.getmtime(files[0])).strftime('%d.%m.%Y %H:%M')})")
    print(f"🏚️ Ältestes: {os.path.basename(files[-1])} ({datetime.fromtimestamp(os.path.getmtime(files[-1])).strftime('%d.%m.%Y %H:%M')})")

    try:
        keep_input = input("\nWie viele (neueste) Backups behalten? (Default: 10): ").strip()
        keep = int(keep_input) if keep_input else 10
    except ValueError:
        print("❌ Ungültige Eingabe.")
        return

    if keep < 1: keep = 1
    to_delete = files[keep:]

    if not to_delete:
        print("✅ Keine Dateien zu löschen (Anzahl <= Limit).")
        return

    print(f"\n⚠️ Es werden {len(to_delete)} alte Dateien gelöscht!")
    if input("Wirklich löschen? (j/n): ").strip().lower() == 'j':
        deleted_count = 0
        for f in to_delete:
            try:
                os.remove(f)
                deleted_count += 1
            except Exception as e:
                print(f"❌ Fehler bei {os.path.basename(f)}: {e}")
        print(f"✅ {deleted_count} Backups erfolgreich gelöscht.")
    else:
        print("❌ Abbruch.")
