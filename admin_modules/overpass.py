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

def sort_paths_spatially(paths):
    """Sorts a list of paths (segments) geographically to ensure continuity."""
    if not paths: return []
    
    # 1. Calculate centers of each segment
    centers = []
    all_lats, all_lons = [], []
    for p in paths:
        if not p: continue
        # Average lat/lon of the segment
        c_lat = sum(x[0] for x in p) / len(p)
        c_lon = sum(x[1] for x in p) / len(p)
        centers.append({'lat': c_lat, 'lon': c_lon, 'path': p})
        all_lats.append(c_lat)
        all_lons.append(c_lon)
    
    if not centers: return paths

    # 2. Determine principal axis (Lat or Lon)
    lat_span = max(all_lats) - min(all_lats)
    lon_span = max(all_lons) - min(all_lons)
    
    # 3. Sort
    # Ideally we would chain them by connectivity, but sorting by main axis 
    # is a robust 95% solution for splitting streets into "North/South" or "East/West" parts.
    if lat_span > lon_span:
        centers.sort(key=lambda x: x['lat'])
    else:
        centers.sort(key=lambda x: x['lon'])
        
    return [x['path'] for x in centers]

def dist_point_to_segments(lat, lon, paths):
    """Returns min distance from point to any segment in paths."""
    min_d = float('inf')
    for path in paths:
        # Check all points in path (simplified)
        for p in path[::2]: # Check every 2nd node for speed
            d = (lat - p[0])**2 + (lon - p[1])**2 # Squared Euclidean (approx)
            if d < min_d: min_d = d
    return math.sqrt(min_d)

def fetch_streets_multi_plz(plz_liste, radius_threshold_m=45):
    # --- Cache Check ---
    cache_dir = "cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_key = "_".join(sorted(plz_liste))
    cache_file = os.path.join(cache_dir, f"streets_{cache_key}_v2.json")
    
    if os.path.exists(cache_file):
        if input(f"💾 Cache für {', '.join(plz_liste)} gefunden. Verwenden? (j/n): ").strip().lower() == 'j':
            print("📂 Lade Daten aus Cache...")
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data['streets'], data['coords']

    print(f"🔍 Suche ALLES: Straßen, Adresspunkte und Hausumrisse für {', '.join(plz_liste)}...")
    area_filters = "".join([f'area["postal_code"="{p}"];' for p in plz_liste])
    
    # Query 1: Streets with geometry
    q_streets = f'[out:json][timeout:90];({area_filters})->.a; way["highway"~"primary|secondary|tertiary|unclassified|residential|living_street|pedestrian"]["name"](area.a); out geom;'
    
    # Query 2: Addresses
    q_houses = f'[out:json][timeout:90];({area_filters})->.a; nwr["addr:housenumber"](area.a); out center;'

    data_s = fetch_overpass_data(q_streets)
    data_h = fetch_overpass_data(q_houses)

    if not data_s or not data_h:
        print("❌ Daten konnten nicht geladen werden.")
        return {}, []

    raw_streets = {} 
    coords_list = []

    # 1. Process Streets
    for s in data_s.get('elements', []):
        name = s['tags']['name']
        s_id_base = name.replace(" ", "_").lower()
        
        geometry = s.get('geometry', [])
        length = 0
        nodes = []
        
        if geometry:
            for i in range(len(geometry) - 1):
                p1 = geometry[i]
                p2 = geometry[i+1]
                length += haversine(p1['lat'], p1['lon'], p2['lat'], p2['lon'])
                nodes.append([p1['lat'], p1['lon']])
            if geometry:
                 nodes.append([geometry[-1]['lat'], geometry[-1]['lon']])

            center_lat = sum(p['lat'] for p in geometry) / len(geometry)
            center_lon = sum(p['lon'] for p in geometry) / len(geometry)
            coords_list.append([center_lat, center_lon])
            
            if s_id_base not in raw_streets:
                raw_streets[s_id_base] = {
                    "name": name,
                    "households": 0,
                    "length": 0,
                    "coords": [center_lat, center_lon], 
                    "status": "free", 
                    "user": "", 
                    "paths": [],
                    "house_coords": [] # List of {lat, lon, w}
                }
            
            raw_streets[s_id_base]["length"] += length
            raw_streets[s_id_base]["paths"].append(nodes)

    # 2. Assign Households to Streets
    print(f"🏠 Verarbeite {len(data_h.get('elements', []))} gefundene Adress-Objekte...")
    THRESHOLD = radius_threshold_m / 111320.0
    GRID_SIZE = 0.001 
    
    street_grid = {}
    def get_grid_key(lat, lon): return (int(lat / GRID_SIZE), int(lon / GRID_SIZE))

    for s_id, s_data in raw_streets.items():
        for path in s_data["paths"]:
            for n in path[::5]: 
                key = get_grid_key(n[0], n[1])
                if key not in street_grid: street_grid[key] = set()
                street_grid[key].add(s_id)
                
    for h in data_h.get('elements', []):
        h_lat = h.get('lat') or h.get('center', {}).get('lat')
        h_lon = h.get('lon') or h.get('center', {}).get('lon')
        if not h_lat: continue

        min_d = 999
        best_id = None
        
        g_lat, g_lon = get_grid_key(h_lat, h_lon)
        candidates = set()
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                k = (g_lat + dx, g_lon + dy)
                if k in street_grid: candidates.update(street_grid[k])
        
        for s_id in candidates:
            s_data = raw_streets[s_id]
            # Use improved check
            d = dist_point_to_segments(h_lat, h_lon, s_data["paths"])
            if d < min_d:
                min_d = d
                best_id = s_id
        
        if best_id and min_d < THRESHOLD:
            weight = 1
            tags = h.get('tags', {})
            if 'addr:flats' in tags:
                try:
                    flats_val = tags['addr:flats']
                    if '-' in flats_val:
                        parts = flats_val.split('-')
                        weight = max(1, int(parts[1]) - int(parts[0]) + 1)
                    else:
                        weight = max(1, int(flats_val))
                except: pass
            elif tags.get('building') in ['apartments', 'dormitory', 'terrace']:
                weight = 6 
            
            raw_streets[best_id]["households"] += weight
            raw_streets[best_id]["house_coords"].append({'lat': h_lat, 'lon': h_lon, 'w': weight})

    # 3. Post-Process: Sorting and Splitting
    final_streets = {}
    
    for s_id, data in raw_streets.items():
        # Sort paths to reduce gaps when splitting
        sorted_paths = sort_paths_spatially(data["paths"])
        
        should_split = data["length"] > 600 or data["households"] > 80
        
        if should_split and len(sorted_paths) > 1:
            num_segments = max(2, int(data["length"] / 400))
            num_segments = min(num_segments, len(sorted_paths))
            
            chunk_size = math.ceil(len(sorted_paths) / num_segments)
            
            split_parts = []
            
            # Create parts
            for i in range(num_segments):
                start = i * chunk_size
                end = start + chunk_size
                seg_paths = sorted_paths[start:end]
                if not seg_paths: continue
                
                # Calc geometry
                seg_len = 0
                all_seg_nodes = []
                for p in seg_paths:
                    all_seg_nodes.extend(p)
                    for k in range(len(p)-1):
                        seg_len += haversine(p[k][0], p[k][1], p[k+1][0], p[k+1][1])
                
                if all_seg_nodes:
                    seg_lat = sum(n[0] for n in all_seg_nodes) / len(all_seg_nodes)
                    seg_lon = sum(n[1] for n in all_seg_nodes) / len(all_seg_nodes)
                else:
                    seg_lat, seg_lon = data["coords"]
                    
                split_parts.append({
                    "id": f"{s_id}_part{i+1}",
                    "name": f"{data['name']} ({i+1}/{len(sorted_paths)//chunk_size + 1 if chunk_size else num_segments})",
                    "paths": seg_paths,
                    "length": int(seg_len),
                    "coords": [seg_lat, seg_lon],
                    "houses": [],
                    "households": 0
                })

            # Distribute houses to closest part
            for h in data["house_coords"]:
                best_part = None
                min_part_d = float('inf')
                
                for part in split_parts:
                    d = dist_point_to_segments(h['lat'], h['lon'], part['paths'])
                    if d < min_part_d:
                        min_part_d = d
                        best_part = part
                
                if best_part:
                    best_part["houses"].append(h)
                    best_part["households"] += h['w']

            # Finalize parts
            for part in split_parts:
                # Fix name index
                # Ensure min households
                if part["households"] == 0:
                     part["households"] = max(2, int(part["length"] / 25))
                
                final_streets[part["id"]] = {
                    "name": part["name"],
                    "households": part["households"],
                    "length": part["length"],
                    "coords": part["coords"],
                    "path": part["paths"],
                    "houses": part["houses"], # Include coords!
                    "status": "free",
                    "user": ""
                }

        else:
            # No split
            if data["households"] == 0:
                data["households"] = max(3, int(data["length"] / 20))
            
            data["path"] = sorted_paths # Use sorted paths
            del data["paths"]
            data["length"] = int(data["length"])
            data["houses"] = data["house_coords"]
            del data["house_coords"]
            final_streets[s_id] = data

    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump({'streets': final_streets, 'coords': coords_list}, f)

    return final_streets, coords_list
