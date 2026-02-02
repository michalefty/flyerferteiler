import requests
import json
import os
from datetime import datetime
import math
import time

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
    
    # Query 1: Alle Straßen
    q_streets = f'[out:json][timeout:90];({area_filters})->.a; way["highway"~"residential|tertiary|unclassified|living_street"]["name"](area.a); out center;'
    
    # Query 2: ALLES mit einer Hausnummer (Knoten, Wege und Relationen)
    q_houses = f'[out:json][timeout:90];({area_filters})->.a; nwr["addr:housenumber"](area.a); out center;'

    data_s = fetch_overpass_data(q_streets)
    data_h = fetch_overpass_data(q_houses)

    if not data_s or not data_h:
        print("❌ Daten konnten nicht geladen werden.")
        return {}, []

    streets_dict = {}
    coords_list = []

    # 1. Straßen gruppieren
    for s in data_s.get('elements', []):
        name = s['tags']['name']
        lat, lon = s['center']['lat'], s['center']['lon']
        s_id = name.replace(" ", "_").lower()
        if s_id not in streets_dict:
            streets_dict[s_id] = {"name": name, "households": 0, "coords": [lat, lon], "status": "free", "user": "", "nodes": []}
            coords_list.append([lat, lon])
        streets_dict[s_id]["nodes"].append((lat, lon))

    # 2. Hausnummern (aus Punkten UND Flächen) zuordnen
    # 'nwr' in der Query steht für node, way, relation -> deckt alle OSM-Objekttypen ab
    print(f"🏠 Verarbeite {len(data_h.get('elements', []))} gefundene Adress-Objekte...")
    
    THRESHOLD = 0.0004 # Ca. 40 Meter Suchradius
    
    for h in data_h.get('elements', []):
        # Overpass 'out center' liefert lat/lon für alle Typen im 'center' oder direkt
        h_lat = h.get('lat') or h.get('center', {}).get('lat')
        h_lon = h.get('lon') or h.get('center', {}).get('lon')
        
        if not h_lat: continue

        min_d = 999
        best_id = None
        
        for s_id, s_data in streets_dict.items():
            for n_lat, n_lon in s_data["nodes"]:
                d = math.sqrt((h_lat - n_lat)**2 + (h_lon - n_lon)**2)
                if d < min_d:
                    min_d = d
                    best_id = s_id
        
        if best_id and min_d < THRESHOLD:
            streets_dict[best_id]["households"] += 1

    # Cleanup & Minimum (3 Häuser als Fallback für leere OSM-Straßen)
    for s_id in streets_dict:
        del streets_dict[s_id]["nodes"]
        if streets_dict[s_id]["households"] == 0:
            streets_dict[s_id]["households"] = 3

    return streets_dict, coords_list

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
            "city": label, "plz": ", ".join(plz_liste),
            "date": datetime.now().strftime("%d.%m.%Y"),
            "center": [avg_lat, avg_lon], "total_streets": len(streets_dict)
        },
        "streets": streets_dict
    }
    
    os.makedirs('data', exist_ok=True)
    with open('data/streets_status.json', 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, sort_keys=True, ensure_ascii=False)
    
    print(f"\n✅ Erfolgreich! Straßen: {len(streets_dict)}, Häuser: {sum(s['households'] for s in streets_dict.values())}")

if __name__ == "__main__":
    generate_multi_plan()