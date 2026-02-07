import requests
import json
import os
import math
import time
from .geo import haversine

try:
    import config
except ImportError:
    config = None

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
