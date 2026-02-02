import requests
import json
import os
from datetime import datetime
import math
import time

def fetch_overpass_data(query):
    url = "http://overpass-api.de/api/interpreter"
    for attempt in range(3):  # 3 Versuche bei Timeout
        try:
            response = requests.post(url, data={'data': query}, timeout=120)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ Versuch {attempt+1} fehlgeschlagen: {e}")
            time.sleep(5)
    return None

def fetch_streets_multi_plz(plz_liste):
    print(f"🔍 Rufe Daten ab für PLZ: {', '.join(plz_liste)}...")
    area_filters = "".join([f'area["postal_code"="{p}"];' for p in plz_liste])
    
    # Query 1: Nur die Straßen
    q_streets = f'[out:json][timeout:90];({area_filters})->.a; way["highway"~"residential|tertiary|unclassified|living_street"]["name"](area.a); out center;'
    
    # Query 2: Nur die Hausnummern (getrennt, um Timeout zu vermeiden)
    q_houses = f'[out:json][timeout:90];({area_filters})->.a; node["addr:housenumber"](area.a); out body;'

    data_s = fetch_overpass_data(q_streets)
    data_h = fetch_overpass_data(q_houses)

    if not data_s or not data_h:
        print("❌ API-Abfrage endgültig fehlgeschlagen.")
        return {}, []

    streets_dict = {}
    coords_list = []

    # 1. Straßen verarbeiten
    for s in data_s.get('elements', []):
        name = s['tags']['name']
        lat, lon = s['center']['lat'], s['center']['lon']
        s_id = name.replace(" ", "_").lower()
        if s_id not in streets_dict:
            streets_dict[s_id] = {"name": name, "households": 0, "coords": [lat, lon], "status": "free", "user": "", "nodes": []}
            coords_list.append([lat, lon])
        streets_dict[s_id]["nodes"].append((lat, lon))

    # 2. Häuser zuordnen (Lokal)
    print(f"🧮 Ordne {len(data_h.get('elements', []))} Häuser zu...")
    THRESHOLD = 0.0004 
    for h in data_h.get('elements', []):
        h_lat, h_lon = h['lat'], h['lon']
        best_id, min_d = None, 999
        for s_id, s_data in streets_dict.items():
            for n_lat, n_lon in s_data["nodes"]:
                d = math.sqrt((h_lat - n_lat)**2 + (h_lon - n_lon)**2)
                if d < min_d: min_d, best_id = d, s_id
        if best_id and min_d < THRESHOLD:
            streets_dict[best_id]["households"] += 1

    for s_id in streets_dict:
        del streets_dict[s_id]["nodes"]
        if streets_dict[s_id]["households"] == 0: streets_dict[s_id]["households"] = 5
            
    return streets_dict, coords_list

def generate_multi_plan():
    plz_liste = []
    print("--- Admin-Tool: Gebietsplanung (Ohne Sektoren) ---")
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
            "city": label, "plz": ", ".join(plz_liste),
            "date": datetime.now().strftime("%d.%m.%Y"),
            "center": [avg_lat, avg_lon], "total_streets": len(streets_dict)
        },
        "streets": streets_dict
    }
    
    os.makedirs('data', exist_ok=True)
    with open('data/streets_status.json', 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, sort_keys=True, ensure_ascii=False)
    print(f"✅ Fertig! {len(streets_dict)} Straßen gespeichert.")

if __name__ == "__main__":
    generate_multi_plan()