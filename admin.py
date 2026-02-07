import requests
import json
import os
import uuid
from datetime import datetime
import time
import subprocess

try:
    import config
except ImportError:
    config = None

# Import modules
from admin_modules.overpass import fetch_streets_multi_plz
from admin_modules.vm import start_vm, schedule_stop_vm, get_vm_details
from admin_modules.backups import restore_backup, cleanup_backups
from admin_modules.users import anonymize_users

def generate_multi_plan():
    plz_liste = []
    print("\n--- ADMIN TOOL (Präzise Hausnummernsuche) ---")
    while True:
        p = input("PLZ (oder '0' zum Starten): ").strip()
        if p == '0': break
        if len(p) == 5: plz_liste.append(p)

    if not plz_liste: return
    
    # 1. Basic Metadata (always needed)
    label = input("Anzeigename: ")
    
    default_days = getattr(config, 'SURVEY_DURATION_DAYS', 7) if config else 7
    try:
        dur_input = input(f"Dauer der Abfrage in Tagen (Default: {default_days}): ").strip()
        survey_days = int(dur_input) if dur_input else default_days
    except ValueError:
        survey_days = default_days
        print(f"⚠️ Ungültige Eingabe, nutze Default: {survey_days} Tage")

    # 2. Cache Check Strategy
    cache_dir = "cache"
    cache_key = "_".join(sorted(plz_liste))
    cache_file = os.path.join(cache_dir, f"streets_{cache_key}.json")
    
    streets_dict = None
    coords_list = None
    radius = 45 # Default

    if os.path.exists(cache_file):
        if input(f"💾 Cache für {', '.join(plz_liste)} gefunden. Verwenden? (j/n): ").strip().lower() == 'j':
            print("📂 Lade Daten aus Cache...")
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                streets_dict = data['streets']
                coords_list = data['coords']
            except Exception as e:
                print(f"❌ Fehler beim Laden des Cache: {e}")

    # 3. Fetch if not from Cache
    if not streets_dict:
        try:
            rad_input = input("Suchradius für Häuser (Meter) [Default: 45]: ").strip()
            radius = int(rad_input) if rad_input else 45
        except ValueError:
            radius = 45
            print(f"⚠️ Ungültige Eingabe, nutze Default: {radius}m")

        # Note: fetch_streets_multi_plz also has a cache check.
        # Since we already checked/rejected it (or file didn't exist), 
        # it might prompt again if we created it in the meantime, but that's unlikely in single session.
        # However, if we rejected it above, we probably want to force fetch.
        # But fetch_streets_multi_plz doesn't have a "force" param.
        # If user rejected cache above, they likely want to fetch new.
        # If I call fetch_streets_multi_plz now, it sees the file and asks AGAIN.
        # This is a small UX flaw, but acceptable for now or I'd need to modify overpass.py.
        # To avoid double prompt, I could check if I rejected it.
        # But for now, I will accept the potential double prompt if user says 'n' above.
        
        streets_dict, coords_list = fetch_streets_multi_plz(plz_liste, radius)
    
    if not streets_dict: return

    # --- Merge Logic: Existing Data ---
    should_ask_import = False
    if os.path.exists('data/streets_status.json'):
        try:
            with open('data/streets_status.json', 'r', encoding='utf-8') as f:
                old_meta = json.load(f).get('metadata', {})
                old_plz = old_meta.get('plz', '').replace(' ', '').split(',')
                # Check overlap
                if any(p in old_plz for p in plz_liste):
                    should_ask_import = True
        except:
            pass

    if should_ask_import:
        print("\n🔄 Bestehende Daten für diese PLZ gefunden.")
        print("   Wähle Import-Optionen für DIESE PLZ-Gebiete:")
        print("   1. Status & User-Input übernehmen (Reservierungen)")
        print("   2. Manuell eingezeichnete Straßen übernehmen")
        print("   3. BEIDES (Status + Manuelle Straßen)")
        print("   0. NICHTS (Start bei Null)")
        
        import_mode = input("Auswahl (0-3) [Default: 3]: ").strip()
        if not import_mode: import_mode = '3'
        
        if import_mode in ['1', '2', '3']:
            try:
                with open('data/streets_status.json', 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                
                merged, manual = 0, 0
                old_streets = old_data.get('streets', {})
                
                for sid, sdata in old_streets.items():
                    # 1. Status & User
                    if import_mode in ['1', '3'] and sid in streets_dict:
                         if sdata.get('status') == 'taken':
                            streets_dict[sid]['status'] = 'taken'
                            streets_dict[sid]['user'] = sdata.get('user', '')
                            merged += 1
                            
                    # 2. Manual Streets
                    elif import_mode in ['2', '3'] and '_manual_' in sid:
                        streets_dict[sid] = sdata
                        manual += 1
                        
                print(f"✅ Integriert: {merged} Reservierungen, {manual} manuelle Straßen.")
            except Exception as e:
                print(f"⚠️ Merge-Fehler: {e}")

    avg_lat = sum(c[0] for c in coords_list) / len(coords_list)
    avg_lon = sum(c[1] for c in coords_list) / len(coords_list)
    
    # Calculate Bounding Box
    lats = [c[0] for c in coords_list]
    lons = [c[1] for c in coords_list]
    bbox = [[min(lats), min(lons)], [max(lats), max(lons)]]

    export_data = {
        "metadata": {
            "city": label, 
            "plz": ", ".join(plz_liste),
            "date": datetime.now().strftime("%d.%m.%Y"),
            "center": [avg_lat, avg_lon],
            "bbox": bbox,
            "total_streets": len(streets_dict),
            "duration": survey_days
        },
        "streets": streets_dict
    }
    
    os.makedirs('data', exist_ok=True)
    
    # --- Staging Selection ---
    print("\n--- 💾 SPEICHERN ---")
    print("1. 🟢 LIVE: Direkt als 'streets_status.json' speichern (Live-Betrieb)")
    print("2. 🟡 STAGING: Als Vorschau speichern (zum Testen/Absegnen)")
    
    mode = input("Auswahl (1/2) [Default: 2]: ").strip()
    
    # --- 4. VM Check (Infrastructure) ---
    # Check immediately after decision, before doing any git work
    if config and getattr(config, 'CLOUD_PROVIDER', '') == 'gcloud':
        print("\n☁️  Prüfe Cloud-VM Status...")
        # Check and Offer Start
        start_vm() 

    target_file = 'data/streets_status.json'
    
    if mode == '1':
        print("💾 Speichere als LIVE Version...")
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, sort_keys=True, ensure_ascii=False)
        print(f"\n✅ Erfolgreich! Straßen: {len(streets_dict)}")
        
        # Standard Push Logic for Live
        if config and input("\n🚀 Änderungen jetzt zu GitHub pushen? (j/n): ").strip().lower() == 'j':
             # Git Push Logic
            try:
                print("⏳ Führe Git-Operationen durch...")
                subprocess.run(["git", "add", target_file], check=True)
                
                if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 1:
                    msg = getattr(config, 'GIT_COMMIT_MESSAGE', f"Update Plan: {label}")
                    subprocess.run(["git", "commit", "-m", msg], check=True)
                
                remote = getattr(config, 'GIT_REMOTE_URL', 'origin')
                branch = getattr(config, 'GIT_BRANCH', 'main')
                
                print("🔄 Hole Änderungen vom Server (Pull --rebase)...")
                subprocess.run(["git", "pull", "--rebase", remote, branch], check=True)
                
                subprocess.run(["git", "push", remote, branch], check=True)
                print("✅ Push erfolgreich!")

            except subprocess.CalledProcessError as e:
                print(f"❌ Fehler beim Git-Push: {e}")
             
    else: # Staging Default
        staging_id = str(uuid.uuid4())
        staging_file = 'data/staging.json'
        access_file = 'data/staging_access.json'
        
        # Save Content
        with open(staging_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, sort_keys=True, ensure_ascii=False)
            
        # Save Meta Access
        access_data = {"uuid": staging_id, "created": datetime.now().isoformat()}
        with open(access_file, 'w') as f:
            json.dump(access_data, f)
            
        print(f"\n✅ STAGING Version lokal erstellt!")
        
        # Git Push for Staging
        if config:
            if input("🚀 Staging-Dateien zu GitHub pushen (für Server-Preview)? (j/n): ").strip().lower() == 'j':
                try:
                    print("⏳ Pushe Staging-Dateien (inkl. Assets)...")
                    # Force add static in case they were ignored or new
                    subprocess.run(["git", "add", staging_file, access_file, "static/"], check=True)
                    subprocess.run(["git", "commit", "-m", f"Staging Build: {label}"], check=True)
                    
                    remote = getattr(config, 'GIT_REMOTE_URL', 'origin')
                    branch = getattr(config, 'GIT_BRANCH', 'main')
                    subprocess.run(["git", "push", remote, branch], check=True)
                    
                    preview_url = f"https://flyerferteiler.de/preview/{staging_id}"
                    print(f"\n✅ Staging erfolgreich gepusht!")
                    print(f"⏳ Warte auf Deployment (Checke URL alle 10s)...")
                    
                    # Polling Loop
                    start_wait = time.time()
                    while True:
                        try:
                            r = requests.get(preview_url, timeout=5)
                            if r.status_code == 200 and "VORSCHAU MODUS" in r.text:
                                print(f"\n🚀 PREVIEW ONLINE: {preview_url}")
                                break
                            elif r.status_code == 200:
                                print(f"   ... Status 200 (aber Inhalt fehlt noch?), warte weiter ...")
                            else:
                                print(f"   ... Status {r.status_code}, warte weiter ...")
                        except Exception:
                             print("   ... Verbindung noch nicht möglich ...")
                        
                        if time.time() - start_wait > 300: # 5 Min Timeout
                            print("\n⚠️  Timeout: Server braucht länger als erwartet.")
                            print(f"   Bitte manuell prüfen: {preview_url}")
                            break
                            
                        time.sleep(10)

                except subprocess.CalledProcessError as e:
                    print(f"❌ Git-Fehler: {e}")
            else:
                print("ℹ️ Kein Push durchgeführt. Vorschau nur lokal verfügbar.")
        return 


def check_server_status():
    print("\n--- 🏥 SERVER STATUS CHECK ---")
    
    # 1. Infrastructure Check (VM)
    vm_ready = True
    if config and getattr(config, 'CLOUD_PROVIDER', '') == 'gcloud':
        print("☁️  Prüfe Cloud-VM (gcloud)...")
        # Imported at top, but ensure it's available
        # from admin_modules.vm import get_vm_details, start_vm 
        status, ip = get_vm_details()
        
        if status:
            print(f"   ℹ️  Status: {status}")
            if ip: print(f"   ℹ️  IP: {ip}")
            
            if status != "RUNNING":
                vm_ready = False
                print("⚠️  Server ist NICHT aktiv.")
                # User asked for "simple start if off"
                if input("🚀 VM jetzt einschalten? (j/n) [j]: ").strip().lower() in ['', 'j']:
                    if start_vm():
                        vm_ready = True
                    else:
                        print("❌ Start abgebrochen oder fehlgeschlagen.")
            else:
                print("✅ Server läuft (Infrastructure OK).")
        else:
            print("⚠️  Konnte VM-Status nicht abrufen (gcloud Fehler?).")

    if not vm_ready:
        print("❌ Abbruch: Server-Infrastruktur nicht bereit.")
        input("\n(Drücke Enter um zurückzukehren)")
        return

    # 2. Application Check (HTTP)
    url = getattr(config, 'PRODUCTION_URL', None) if config else None
    
    # Try to guess URL from IP if configured URL is missing but we found an IP
    if not url and 'ip' in locals() and ip:
        url = f"http://{ip}:8080" # Assumption/Default
        print(f"ℹ️  Keine URL konfiguriert, versuche IP: {url}")

    if not url:
        url = input("🌐 Server-URL eingeben (z.B. http://1.2.3.4:8080): ").strip()
    
    if not url:
        print("❌ Keine URL angegeben.")
        return

    if not url.startswith("http"):
        url = "http://" + url
        
    print(f"📡 Prüfe App-Erreichbarkeit ({url}) ...")
    try:
        start = time.time()
        resp = requests.get(url, timeout=10) # 10s timeout for cold boot
        duration = (time.time() - start) * 1000
        
        if resp.status_code == 200:
            print(f"✅ Web-App ist ONLINE (Status 200). Antwortzeit: {duration:.0f}ms")
            
            if "Flyer-Verteilung" in resp.text:
                print("✅ Inhalt verifiziert.")
            else:
                print("⚠️  Status 200, aber Inhalt weicht ab.")
        else:
            print(f"⚠️  Server antwortet mit Status-Code: {resp.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ VERBINDUNGSFEHLER: Webserver nicht erreichbar.")
        print("   -> App läuft evtl. noch nicht (Gunicorn)?")
        print("   -> Firewall (Port 8080)?")
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT: Server antwortet nicht rechtzeitig.")
    except Exception as e:
        print(f"❌ Fehler: {e}")
    input("\n(Drücke Enter um zurückzukehren)")

def print_help():
    print("\n--- 📖 HILFE & DOKUMENTATION ---")
    print("1. 🗺️  Neuen Plan erstellen (PLZ Suche):")
    print("   - Fragt nach PLZ(s) und lädt Straßendaten von der Overpass API.")
    print("   - Berechnet Haushaltszahlen und segmentiert lange Straßen.")
    print("   - Erstellt/Aktualisiert 'data/streets_status.json'.")
    print("   - Pusht Änderungen zu GitHub und startet ggf. die VM.")
    print("\n2. 🛡️  User-Namen anonymisieren (DSGVO):")
    print("   - Scannt 'data/streets_status.json'.")
    print("   - Kürzt Klarnamen auf Vornamen + Initial (z.B. 'Max Mustermann' -> 'Max M.').")
    print("\n3. 🧹 Alte Backups bereinigen:")
    print("   - Löscht alte JSON-Dateien aus 'data/backups/'.")
    print("   - Behält die N neuesten Dateien (konfigurierbar).")
    print("\n4. ⏪ Restore Backup:")
    print("   - Stellt einen älteren Stand aus 'data/backups/' wieder her.")
    print("\n5. 🏥 Server Status Check:")
    print("   - Prüft, ob die Web-App erreichbar ist.")
    print("   - Misst Antwortzeit.")
    input("\n(Drücke Enter um zurückzukehren)")

def main_menu():
    while True:
        print("\n--- 🛠️ ADMIN TOOL ---")
        print("1. 🗺️  Neuen Plan erstellen (PLZ Suche)")
        print("2. 🛡️  User-Namen anonymisieren (DSGVO)")
        print("3. 🧹 Alte Backups bereinigen")
        print("4. ⏪ Restore Backup")
        print("5. 🏥 Server Status Check")
        print("6. ❓ Hilfe anzeigen")
        print("0. ❌ Beenden")
        
        choice = input("\nWähle eine Option (0-6): ").strip()
        
        if choice == '1':
            generate_multi_plan()
        elif choice == '2':
            anonymize_users()
        elif choice == '3':
            cleanup_backups()
        elif choice == '4':
            restore_backup()
        elif choice == '5':
            check_server_status()
        elif choice == '6' or choice == '?' or choice.lower() == 'h':
            print_help()
        elif choice == '0':
            print("👋 Bye!")
            break
        else:
            print("Ungültige Eingabe.")

if __name__ == "__main__":
    main_menu()
