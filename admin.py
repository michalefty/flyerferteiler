import requests
import json
import os
from datetime import datetime
import math
import time

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Radius of Earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def fetch_overpass_data(query):
    url = "http://overpass-api.de/api/interpreter"
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
    print(f"🔍 Suche ALLES: Straßen, Adresspunkte und Hausumrisse für {', '.join(plz_liste)}...")
    area_filters = "".join([f'area["postal_code"="{p}"];' for p in plz_liste])
    
    # Query 1: Streets with geometry
    q_streets = f'[out:json][timeout:90];({area_filters})->.a; way["highway"~"residential|tertiary|unclassified|living_street"]["name"](area.a); out geom;'
    
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
                nodes.append((p1['lat'], p1['lon']))
            
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
                    "coords": [center_lat, center_lon], # Start with this segment's center
                    "status": "free", 
                    "user": "", 
                    "nodes": []
                }
            
            raw_streets[s_id_base]["length"] += length
            raw_streets[s_id_base]["nodes"].extend(nodes)
            # Update center (running average would be better, but this is okay for now)
            # We'll keep the first found center or update it? Let's just keep adding nodes and re-calc center later if needed.

    # 2. Assign Households to Streets
    print(f"🏠 Verarbeite {len(data_h.get('elements', []))} gefundene Adress-Objekte...")
    THRESHOLD = 0.0004 # Approx 40m
    
    for h in data_h.get('elements', []):
        h_lat = h.get('lat') or h.get('center', {}).get('lat')
        h_lon = h.get('lon') or h.get('center', {}).get('lon')
        if not h_lat: continue

        min_d = 999
        best_id = None
        
        # Determine nearest street
        # Optimization: This is O(N*M), could be slow for huge datasets. 
        # For a few hundred streets/houses it's fine.
        for s_id, s_data in raw_streets.items():
            # Check distance to ANY node of the street (simplified)
            # Optimization: Check distance to street "center" first? 
            # Let's stick to node check for accuracy, but maybe sample nodes?
            for n_lat, n_lon in s_data["nodes"][::5]: # Check every 5th node for speed
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
            data["households"] = max(3, int(data["length"] / 20)) # Estimate based on length (1 house every 20m)

        # Split Logic
        # Split if length > 600m OR households > 80
        should_split = data["length"] > 600 or data["households"] > 80
        
        if should_split:
            num_segments = max(2, int(data["length"] / 400))
            households_per_seg = math.ceil(data["households"] / num_segments)
            length_per_seg = int(data["length"] / num_segments)
            
            # Nodes aufteilen
            total_nodes = data["nodes"]
            chunk_size = math.ceil(len(total_nodes) / num_segments)
            
            for i in range(num_segments):
                # Slice nodes for this segment
                # Overlap by 1 node to ensure visual continuity
                start_idx = i * chunk_size
                end_idx = min((i + 1) * chunk_size + 1, len(total_nodes))
                seg_nodes = total_nodes[start_idx:end_idx]
                
                # Fallback if slice is empty (rare edge case with few nodes but long distance)
                if not seg_nodes: 
                    seg_nodes = [data["coords"]] 

                # Calculate new center for this segment
                seg_lat = sum(n[0] for n in seg_nodes) / len(seg_nodes)
                seg_lon = sum(n[1] for n in seg_nodes) / len(seg_nodes)

                seg_id = f"{s_id}_part{i+1}"
                final_streets[seg_id] = {
                    "name": f"{data['name']} ({i+1}/{num_segments})",
                    "households": households_per_seg,
                    "length": length_per_seg,
                    "coords": [seg_lat, seg_lon],
                    "path": seg_nodes, # Save geometry path
                    "status": "free",
                    "user": ""
                }
        else:
            # Save geometry for non-split streets too
            data["path"] = data["nodes"]
            del data["nodes"] # Remove old key
            data["length"] = int(data["length"])
            final_streets[s_id] = data

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

if __name__ == "__main__":
    generate_multi_plan()
