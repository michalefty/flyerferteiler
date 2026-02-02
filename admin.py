import requests
import json
import os
from datetime import datetime
import math

def fetch_streets_multi_plz(plz_liste):
    print(f"🔍 Optimiere Abfrage für PLZ: {', '.join(plz_liste)}...")
    overpass_url = "http://overpass-api.de/api/interpreter"
    area_filters = "".join([f'area["postal_code"="{p}"];' for p in plz_liste])
    
    overpass_query = f"""
    [out:json][timeout:120];
    ({area_filters})->.searchAreas;
    (
      way["highway"~"residential|tertiary|unclassified|living_street"]["name"](area.searchAreas);
      node["addr:housenumber"](area.searchAreas);
    );
    out center;
    """
    
    try:
        response = requests.post(overpass_url, data={'data': overpass_query})
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ API-Fehler: {e}")
        return {}, []

    streets_raw = []
    house_nodes = []
    for el in data.get('elements', []):
        if el['type'] == 'way': 
            streets_raw.append(el)
        elif el['type'] == 'node' and 'tags' in el and 'addr:housenumber' in el['tags']: 
            house_nodes.append((el['lat'], el['lon']))

    streets_dict = {}
    coords_list = []

    def get_dist(lat1, lon1, lat2, lon2):
        return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

    # Alle Straßenabschnitte sammeln und nach Name gruppieren
    for s in streets_raw:
        name = s['tags']['name']
        lat, lon = s['center']['lat'], s['center']['lon']
        s_id = name.replace(" ", "_").lower()
        
        if s_id not in streets_dict:
            streets_dict[s_id] = {
                "name": name, "households": 0, "coords": [lat, lon],
                "status": "free", "user": "", "sector": 0, "nodes": []
            }
            coords_list.append([lat, lon])
        
        streets_dict[s_id]["nodes"].append((lat, lon))

    # Häuser den gruppierten Straßen zuordnen (Radius ca. 35m)
    THRESHOLD = 0.00035 
    for h_lat, h_lon in house_nodes:
        best_dist = 999
        best_id = None
        for s_id, s_data in streets_dict.items():
            for n_lat, n_lon in s_data["nodes"]:
                d = get_dist(h_lat, h_lon, n_lat, n_lon)
                if d < best_dist:
                    best_dist = d
                    best_id = s_id
        if best_id and best_dist < THRESHOLD:
            streets_dict[best_id]["households"] += 1

    # Cleanup und Minimum-Schutz
    for s_id in streets_dict:
        del streets_dict[s_id]["nodes"]
        if streets_dict[s_id]["households"] == 0:
            streets_dict[s_id]["households"] = 5
            
    return streets_dict, coords_list

def generate_multi_plan():
    plz_liste = []
    print("--- Admin-Tool: Gebietsplanung (Vollständig) ---")
    while True:
        p = input("PLZ eingeben (oder '0' zum Starten): ").strip()
        if p == '0': break
        if len(p) == 5: plz_liste.append(p)

    if not plz_liste: return
    stadt_label = input("Anzeigename für das Gebiet: ")
    anzahl_austeiler = int(input("Anzahl Sektoren: "))

    streets_dict, coords_list = fetch_streets_multi_plz(plz_liste)
    if not streets_dict: return

    sorted_keys = sorted(streets_dict.keys())
    for i, key in enumerate(sorted_keys):
        streets_dict[key]['sector'] = (i % anzahl_austeiler) + 1

    avg_lat = sum(c[0] for c in coords_list) / len(coords_list)
    avg_lon = sum(c[1] for c in coords_list) / len(coords_list)

    export_data = {
        "metadata": {
            "city": stadt_label, "plz": ", ".join(plz_liste),
            "date": datetime.now().strftime("%d.%m.%Y"),
            "center": [avg_lat, avg_lon], "total_streets": len(streets_dict)
        },
        "streets": streets_dict
    }
    
    os.makedirs('data', exist_ok=True)
    with open('data/streets_status.json', 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, sort_keys=True, ensure_ascii=False)
    
    print(f"\n✅ Erfolgreich! {len(streets_dict)} Straßen und {sum(s['households'] for s in streets_dict.values())} Häuser erfasst.")

if __name__ == "__main__":
    generate_multi_plan()