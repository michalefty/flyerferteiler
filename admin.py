import requests
import json
import os
from datetime import datetime

def fetch_streets_from_overpass(stadt, plz):
    print(f"🔍 Suche Straßen in {stadt} ({plz})...")
    
    # Overpass Query: Sucht nach allen befahrbaren Straßen (highways) in der PLZ
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json][timeout:25];
    area["postal_code"="{plz}"]["name"="{stadt}"]->.searchArea;
    (
      way["highway"]["name"](area.searchArea);
    );
    out center;
    """
    
    response = requests.post(overpass_url, data={'data': overpass_query})
    data = response.json()
    
    streets_dict = {}
    coords_list = []

    for element in data.get('elements', []):
        if 'name' in element['tags']:
            name = element['tags']['name']
            lat = element['center']['lat']
            lon = element['center']['lon']
            
            # ID generieren (Name ohne Leerzeichen)
            s_id = name.replace(" ", "_").replace("ß", "ss")
            
            # Falls Straße mehrfach vorkommt (Segmente), fassen wir sie zusammen
            if s_id not in streets_dict:
                streets_dict[s_id] = {
                    "name": name,
                    "households": 20, # Dummy-Wert, da OSM keine Briefkastenzahlen hat
                    "coords": [lat, lon],
                    "status": "free",
                    "user": "",
                    "sector": 0
                }
                coords_list.append([lat, lon])
    
    return streets_dict, coords_list

def generate_plan(stadt, plz, anzahl_austeiler):
    streets_dict, coords_list = fetch_streets_from_overpass(stadt, plz)
    
    if not streets_dict:
        print("❌ Keine Straßen gefunden!")
        return

    # Sektoren zuweisen (einfache Verteilung)
    sorted_keys = sorted(streets_dict.keys())
    for i, key in enumerate(sorted_keys):
        streets_dict[key]['sector'] = (i % anzahl_austeiler) + 1

    # Zentrum berechnen für Leaflet fitBounds
    avg_lat = sum(c[0] for c in coords_list) / len(coords_list)
    avg_lon = sum(c[1] for c in coords_list) / len(coords_list)

    export_data = {
        "metadata": {
            "city": stadt,
            "plz": plz,
            "date": datetime.now().strftime("%d.%m.%Y"),
            "center": [avg_lat, avg_lon],
            "total_streets": len(streets_dict)
        },
        "streets": streets_dict
    }
    
    os.makedirs('data', exist_ok=True)
    with open('data/streets_status.json', 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, sort_keys=True, ensure_ascii=False)
    
    print(f"✅ Datei mit {len(streets_dict)} Straßen erstellt.")

if __name__ == "__main__":
    s = input("Stadt (z.B. Sulzbach am Main): ")
    p = input("PLZ: ")
    a = int(input("Anzahl Austeiler: "))
    generate_plan(s, p, a)