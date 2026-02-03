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

def fetch_streets_multi_plz(plz_liste):
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
    q_streets = f'[out:json][timeout:90];({area_filters})->.a; way["highway"~"residential|tertiary|unclassified|living_street|pedestrian"]["name"](area.a); out geom;'
    
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
    THRESHOLD = 0.0004 # Approx 40m
    
    for h in data_h.get('elements', []):
        h_lat = h.get('lat') or h.get('center', {}).get('lat')
        h_lon = h.get('lon') or h.get('center', {}).get('lon')
        if not h_lat: continue

        min_d = 999
        best_id = None
        
        for s_id, s_data in raw_streets.items():
            # Check distance to ANY node in ANY path
            for path in s_data["paths"]:
                for n_lat, n_lon in path[::5]: # Check every 5th node
                    d = math.sqrt((h_lat - n_lat)**2 + (h_lon - n_lon)**2)
                    if d < min_d:
                        min_d = d
                        best_id = s_id
        
        if best_id and min_d < THRESHOLD:
            raw_streets[best_id]["households"] += 1

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
    streets_dict, coords_list = fetch_streets_multi_plz(plz_liste)
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
            "total_streets": len(streets_dict)
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
                
                msg = getattr(config, 'GIT_COMMIT_MESSAGE', f"Update Plan: {label}")
                subprocess.run(["git", "commit", "-m", msg], check=True)
                
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
                    schedule_stop_vm()

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

def schedule_stop_vm():
    # Calculate minutes
    days = getattr(config, 'SURVEY_DURATION_DAYS', 7)
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

if __name__ == "__main__":
    generate_multi_plan()
