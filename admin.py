import requests
import json
import os
from datetime import datetime
import math
import time
import subprocess

try:
    import config
except ImportError:
    config = None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Radius of Earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def fetch_overpass_data(query):
    url = getattr(config, 'OVERPASS_URL', "http://overpass-api.de/api/interpreter")
    for attempt in range(3):
        try:
            response = requests.post(url, data={'data': query}, timeout=120)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ API-Versuch {attempt+1} fehlgeschlagen: {e}")
            time.sleep(5)
    return None

def fetch_streets_multi_plz(plz_liste, radius_threshold_m=45):
    # --- Cache Check ---
    cache_dir = "cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_key = "_".join(sorted(plz_liste))
    cache_file = os.path.join(cache_dir, f"streets_{cache_key}.json")
    
    if os.path.exists(cache_file):
        if input(f"💾 Cache für {', '.join(plz_liste)} gefunden. Verwenden? (j/n): ").strip().lower() == 'j':
            print("📂 Lade Daten aus Cache...")
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data['streets'], data['coords']

    print(f"🔍 Suche ALLES: Straßen, Adresspunkte und Hausumrisse für {', '.join(plz_liste)}...")
    area_filters = "".join([f'area["postal_code"="{p}"];' for p in plz_liste])
    
    # Query 1: Streets with geometry
    # Added primary/secondary to capture main roads (Bundes-/Landesstraßen)
    q_streets = f'[out:json][timeout:90];({area_filters})->.a; way["highway"~"primary|secondary|tertiary|unclassified|residential|living_street|pedestrian"]["name"](area.a); out geom;'
    
    # Query 2: Addresses (nodes, ways, relations)
    q_houses = f'[out:json][timeout:90];({area_filters})->.a; nwr["addr:housenumber"](area.a); out center;'

    data_s = fetch_overpass_data(q_streets)
    data_h = fetch_overpass_data(q_houses)

    if not data_s or not data_h:
        print("❌ Daten konnten nicht geladen werden.")
        return {}, []

    raw_streets = {} # Intermediate storage for aggregation
    coords_list = []

    # 1. Process Streets & Calculate Length
    for s in data_s.get('elements', []):
        name = s['tags']['name']
        s_id_base = name.replace(" ", "_").lower()
        
        # Calculate length and center
        geometry = s.get('geometry', [])
        length = 0
        center_lat, center_lon = 0, 0
        nodes = []
        
        if geometry:
            for i in range(len(geometry) - 1):
                p1 = geometry[i]
                p2 = geometry[i+1]
                length += haversine(p1['lat'], p1['lon'], p2['lat'], p2['lon'])
                nodes.append([p1['lat'], p1['lon']])
            # Add last point
            if geometry:
                 nodes.append([geometry[-1]['lat'], geometry[-1]['lon']])

            # Simple center approximation (average of all points)
            center_lat = sum(p['lat'] for p in geometry) / len(geometry)
            center_lon = sum(p['lon'] for p in geometry) / len(geometry)
            coords_list.append([center_lat, center_lon])
            
            # Aggregate if street has multiple ways (common in OSM)
            if s_id_base not in raw_streets:
                raw_streets[s_id_base] = {
                    "name": name,
                    "households": 0,
                    "length": 0,
                    "coords": [center_lat, center_lon], 
                    "status": "free", 
                    "user": "", 
                    "paths": [] # List of lists (MultiLineString)
                }
            
            raw_streets[s_id_base]["length"] += length
            raw_streets[s_id_base]["paths"].append(nodes)
            # Update center (weighted average would be better, but keep simple)
            # Just keep the first found center for now, or update?
            # Let's keep the first one as "anchor"

    # 2. Assign Households to Streets
    print(f"🏠 Verarbeite {len(data_h.get('elements', []))} gefundene Adress-Objekte...")
    # Convert meters to degrees (approx)
    THRESHOLD = radius_threshold_m / 111320.0
    GRID_SIZE = 0.001 # Approx 111m
    
    # --- Optimization: Spatial Grid ---
    street_grid = {}
    
    def get_grid_key(lat, lon):
        return (int(lat / GRID_SIZE), int(lon / GRID_SIZE))

    print("🧩 Erstelle Spatial Grid für Straßen...")
    for s_id, s_data in raw_streets.items():
        for path in s_data["paths"]:
            for n in path[::5]: # Downsample for grid population
                key = get_grid_key(n[0], n[1])
                if key not in street_grid: street_grid[key] = set()
                street_grid[key].add(s_id)
                
    # Loop Houses
    for h in data_h.get('elements', []):
        h_lat = h.get('lat') or h.get('center', {}).get('lat')
        h_lon = h.get('lon') or h.get('center', {}).get('lon')
        if not h_lat: continue

        min_d = 999
        best_id = None
        
        # Get Candidate Streets (Current cell + 8 neighbors)
        g_lat, g_lon = get_grid_key(h_lat, h_lon)
        candidates = set()
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                k = (g_lat + dx, g_lon + dy)
                if k in street_grid:
                    candidates.update(street_grid[k])
        
        # Only check candidates
        for s_id in candidates:
            s_data = raw_streets[s_id]
            # Check distance to ANY node in ANY path
            for path in s_data["paths"]:
                for n_lat, n_lon in path[::5]: # Check every 5th node
                    d = math.sqrt((h_lat - n_lat)**2 + (h_lon - n_lon)**2)
                    if d < min_d:
                        min_d = d
                        best_id = s_id
        
        if best_id and min_d < THRESHOLD:
            # --- Weighting Logic ---
            # --- Weighting Logic ---
            weight = 1
            tags = h.get('tags', {})
            
            # 1. Explicit flats count
            if 'addr:flats' in tags:
                try:
                    flats_val = tags['addr:flats']
                    if '-' in flats_val: # e.g. "1-10"
                        parts = flats_val.split('-')
                        weight = max(1, int(parts[1]) - int(parts[0]) + 1)
                    else:
                        weight = max(1, int(flats_val))
                except:
                    pass
            # 2. Building Type Heuristic
            elif tags.get('building') in ['apartments', 'dormitory', 'terrace']:
                weight = 6 # Estimate for apartment buildings without flat count
            
            raw_streets[best_id]["households"] += weight

    # 3. Post-Process: Cleanup, Min Households, Splitting
    final_streets = {}
    
    for s_id, data in raw_streets.items():
        # Fallback for empty household counts
        if data["households"] == 0:
            data["households"] = max(3, int(data["length"] / 20))

        # Split Logic
        should_split = data["length"] > 600 or data["households"] > 80
        
        if should_split and len(data["paths"]) > 1:
            # Distribute PATHS (segments) instead of slicing nodes to avoid jump lines
            num_segments = max(2, int(data["length"] / 400))
            num_segments = min(num_segments, len(data["paths"])) # Can't split more than we have segments

            households_per_seg = math.ceil(data["households"] / num_segments)
            
            # Divide paths into chunks
            chunk_size = math.ceil(len(data["paths"]) / num_segments)
            
            for i in range(num_segments):
                start = i * chunk_size
                end = start + chunk_size
                seg_paths = data["paths"][start:end]
                
                if not seg_paths: continue

                # Recalculate length for this part
                seg_len = 0
                all_seg_nodes = []
                for p in seg_paths:
                    all_seg_nodes.extend(p)
                    # Approx length calc (sum of segments)
                    for k in range(len(p)-1):
                        seg_len += haversine(p[k][0], p[k][1], p[k+1][0], p[k+1][1])

                # Recalculate center
                if all_seg_nodes:
                    seg_lat = sum(n[0] for n in all_seg_nodes) / len(all_seg_nodes)
                    seg_lon = sum(n[1] for n in all_seg_nodes) / len(all_seg_nodes)
                else:
                    seg_lat, seg_lon = data["coords"]

                seg_id = f"{s_id}_part{i+1}"
                final_streets[seg_id] = {
                    "name": f"{data['name']} ({i+1}/{num_segments})",
                    "households": households_per_seg,
                    "length": int(seg_len),
                    "coords": [seg_lat, seg_lon],
                    "path": seg_paths, # List of lists
                    "status": "free",
                    "user": ""
                }
        else:
            # No split
            data["path"] = data["paths"] # Pass list of lists directly
            del data["paths"]
            data["length"] = int(data["length"])
            final_streets[s_id] = data

    # --- Cache Save ---
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump({'streets': final_streets, 'coords': coords_list}, f)

    return final_streets, coords_list

def generate_multi_plan():
    plz_liste = []
    print("\n--- ADMIN TOOL (Präzise Hausnummernsuche) ---")
    while True:
        p = input("PLZ (oder '0' zum Starten): ").strip()
        if p == '0': break
        if len(p) == 5: plz_liste.append(p)

    if not plz_liste: return
    label = input("Anzeigename: ")
    
    # New: Ask for duration
    default_days = getattr(config, 'SURVEY_DURATION_DAYS', 7) if config else 7
    try:
        dur_input = input(f"Dauer der Abfrage in Tagen (Default: {default_days}): ").strip()
        survey_days = int(dur_input) if dur_input else default_days
    except ValueError:
        survey_days = default_days
        print(f"⚠️ Ungültige Eingabe, nutze Default: {survey_days} Tage")

    # New: Ask for Radius
    try:
        rad_input = input("Suchradius für Häuser (Meter) [Default: 45]: ").strip()
        radius = int(rad_input) if rad_input else 45
    except ValueError:
        radius = 45
        print(f"⚠️ Ungültige Eingabe, nutze Default: {radius}m")

    streets_dict, coords_list = fetch_streets_multi_plz(plz_liste, radius)
    if not streets_dict: return

    # --- Merge Logic: Existing Data ---
    if os.path.exists('data/streets_status.json'):
        if input("🔄 Bestehende Daten (Status & manuelle Straßen) integrieren? (j/n): ").strip().lower() == 'j':
            try:
                with open('data/streets_status.json', 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                
                merged, manual = 0, 0
                for sid, sdata in old_data.get('streets', {}).items():
                    # Status übernehmen
                    if sid in streets_dict:
                        if sdata.get('status') == 'taken':
                            streets_dict[sid]['status'] = 'taken'
                            streets_dict[sid]['user'] = sdata.get('user', '')
                            merged += 1
                    # Manuelle Straßen übernehmen
                    elif '_manual_' in sid:
                        streets_dict[sid] = sdata
                        manual += 1
                print(f"✅ Integriert: {merged} Status-Updates, {manual} manuelle Straßen.")
            except Exception as e:
                print(f"⚠️ Merge-Fehler: {e}")

    avg_lat = sum(c[0] for c in coords_list) / len(coords_list)
    avg_lon = sum(c[1] for c in coords_list) / len(coords_list)

    export_data = {
        "metadata": {
            "city": label, 
            "plz": ", ".join(plz_liste),
            "date": datetime.now().strftime("%d.%m.%Y"),
            "center": [avg_lat, avg_lon],
            "total_streets": len(streets_dict),
            "duration": survey_days
        },
        "streets": streets_dict
    }
    
    os.makedirs('data', exist_ok=True)
    with open('data/streets_status.json', 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, sort_keys=True, ensure_ascii=False)
    
    print(f"\n✅ Erfolgreich! Straßen: {len(streets_dict)}, Häuser: {sum(s['households'] for s in streets_dict.values())}")

    # Git Push Logic
    if config:
        ask = input("\n🚀 Änderungen jetzt zu GitHub pushen? (j/n): ").strip().lower()
        if ask == 'j':
            try:
                print("⏳ Führe Git-Operationen durch...")
                subprocess.run(["git", "add", "data/streets_status.json"], check=True)
                
                # Check if there are changes to commit
                # git diff --cached --quiet returns 0 if no changes, 1 if changes exist
                if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 1:
                    msg = getattr(config, 'GIT_COMMIT_MESSAGE', f"Update Plan: {label}")
                    subprocess.run(["git", "commit", "-m", msg], check=True)
                else:
                    print("ℹ️ Keine Änderungen zum Committen.")
                
                remote = getattr(config, 'GIT_REMOTE_URL', 'origin')
                branch = getattr(config, 'GIT_BRANCH', 'main')
                
                print("🔄 Hole Änderungen vom Server (Pull --rebase)...")
                subprocess.run(["git", "pull", "--rebase", remote, branch], check=True)
                
                subprocess.run(["git", "push", remote, branch], check=True)
                print("✅ Push erfolgreich!")

                # VM Management
                manage_vm = input("\n☁️  Soll die Cloud-VM jetzt gestartet und der Timer gesetzt werden? (j/n): ").strip().lower()
                if manage_vm == 'j':
                    start_vm()
                    schedule_stop_vm(survey_days)

            except subprocess.CalledProcessError as e:
                print(f"❌ Fehler beim Git-Push: {e}")
        else:
            print("ℹ️ Kein Push durchgeführt.")
    else:
        print("⚠️ config.py fehlt. Git-Push übersprungen.")

def start_vm():
    provider = getattr(config, 'CLOUD_PROVIDER', 'none')
    if provider == 'gcloud':
        name = getattr(config, 'VM_INSTANCE_NAME', 'flyer-server')
        zone = getattr(config, 'VM_ZONE', 'europe-west3-c')
        project = getattr(config, 'VM_PROJECT', '')
        
        cmd = ["gcloud", "compute", "instances", "start", name, "--zone", zone]
        if project:
            cmd.extend(["--project", project])
            
        print(f"🚀 Starte VM '{name}' in Zone '{zone}'...")
        try:
            subprocess.run(cmd, check=True)
            print("✅ VM gestartet. Warte auf Boot (30s)...")
            time.sleep(30) # Wait for SSH to be ready
        except subprocess.CalledProcessError as e:
            print(f"❌ Fehler beim Starten der VM: {e}")
            return False
    return True

def schedule_stop_vm(days=None):
    # Calculate minutes
    if days is None:
        days = getattr(config, 'SURVEY_DURATION_DAYS', 7) if config else 7
    minutes = days * 24 * 60
    
    print(f"⏲️  Setze Shutdown-Timer auf {days} Tage ({minutes} Minuten)...")
    
    # We use SSH to schedule 'shutdown'. Assumes 'gcloud compute ssh' works or standard ssh.
    # Using gcloud ssh for convenience if provider is gcloud
    provider = getattr(config, 'CLOUD_PROVIDER', 'none')
    name = getattr(config, 'VM_INSTANCE_NAME', 'flyer-server')
    zone = getattr(config, 'VM_ZONE', 'europe-west3-c')
    
    if provider == 'gcloud':
        # Use 'shutdown' to schedule poweroff (standard tool, no 'at' required)
        # Note: Unlike 'at', this might not survive a reboot, but is sufficient for single-run sessions.
        cmd_str = f"sudo shutdown -h +{minutes}"
        
        print(f"⏲️  Plane Shutdown via 'shutdown' in {minutes} Minuten ({days} Tagen)...")
        cmd = ["gcloud", "compute", "ssh", name, "--zone", zone, "--command", cmd_str]
        
        try:
            subprocess.run(cmd, check=True)
            print(f"✅ Shutdown erfolgreich geplant.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Fehler beim Planen des Shutdowns: {e}")

def anonymize_users():
    print("\n--- 🛡️ User-Namen Anonymisieren (DSGVO) ---")
    data_file = 'data/streets_status.json'
    
    if not os.path.exists(data_file):
        print(f"❌ Datei '{data_file}' nicht gefunden.")
        return

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for s in data.get('streets', {}).values():
        user = s.get('user', '').strip()
        if user:
            # Simple heuristic: Split by space
            parts = user.split()
            if len(parts) >= 2:
                # Firstname + Lastname -> Firstname + L.
                new_name = f"{parts[0]} {parts[-1][0]}."
                if new_name != user:
                    s['user'] = new_name
                    count += 1
            # Special case: Single name stays single name (nickname assumption)

    if count > 0:
        print(f"✅ {count} Namen wurden gekürzt (z.B. 'Max Mustermann' -> 'Max M.').")
        if input("💾 Änderungen speichern? (j/n): ").strip().lower() == 'j':
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
            print("💾 Gespeichert!")
    else:
        print("ℹ️ Keine Namen gefunden, die gekürzt werden mussten.")

import shutil
import getpass

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

def check_server_status():
    print("\n--- 🏥 SERVER STATUS CHECK ---")
    url = getattr(config, 'PRODUCTION_URL', None) if config else None
    
    if not url:
        url = input("🌐 Server-URL eingeben (z.B. http://1.2.3.4:8080): ").strip()
    
    if not url:
        print("❌ Keine URL angegeben.")
        return

    if not url.startswith("http"):
        url = "http://" + url
        
    print(f"📡 Prüfe Erreichbarkeit von {url} ...")
    try:
        start = time.time()
        resp = requests.get(url, timeout=5)
        duration = (time.time() - start) * 1000
        
        if resp.status_code == 200:
            print(f"✅ Server ist ONLINE (Status 200). Antwortzeit: {duration:.0f}ms")
            
            # Optional: Check content
            if "Flyer-Verteilung" in resp.text:
                print("✅ App-Inhalt verifiziert.")
            else:
                print("⚠️  Status 200, aber erwarteter Inhalt fehlt (Wartungsseite?).")
        else:
            print(f"⚠️  Server antwortet mit Status-Code: {resp.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ VERBINDUNGSFEHLER: Server nicht erreichbar.")
        print("   -> Ist die VM gestartet?")
        print("   -> Ist die Firewall offen (Port 80/443/8080)?")
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT: Server antwortet nicht rechtzeitig (5s).")
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
    # Security Check
    required_pwd = None
    if config:
        required_pwd = getattr(config, 'ADMIN_PASSWORD', None) or os.environ.get('ADMIN_PASSWORD')
    
    if required_pwd:
        try:
            pwd = getpass.getpass("🔒 Admin-Passwort eingeben: ")
            if pwd != required_pwd:
                print("❌ Falsches Passwort.")
                exit(1)
        except KeyboardInterrupt:
            print("\nAbbruch.")
            exit(0)
            
    main_menu()
