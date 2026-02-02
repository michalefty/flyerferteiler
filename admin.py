import requests
import json
import os
from datetime import datetime

def fetch_streets_multi_plz(plz_liste):
    print(f"🔍 Suche Straßen und Hausnummern für: {', '.join(plz_liste)}...")
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    area_filters = "".join([f'area["postal_code"="{p}"];' for p in plz_liste])
    
    # Query: Findet Straßen UND Hausnummern im Umkreis von 20m um diese Straßen
overpass_query = f"""
[out:json][timeout:180];
({area_filters})->.searchAreas;
way["highway"~"residential|tertiary|unclassified|living_street"]["name"](area.searchAreas)->.allStreets;

foreach .allStreets -> .thisStreet {{
  .thisStreet out center;
  node["addr:housenumber"](around.thisStreet:25); // Erhöht auf 25m für breite Straßen
  out count;
}}
"""
    
    response = requests.post(overpass_url, data={'data': overpass_query})
    if response.status_code != 200:
        print("❌ Fehler bei der Overpass-Abfrage.")
        return {}, []

    data = response.json()
    streets_dict = {}
    coords_list = []
    
    current_street = None

    # Overpass gibt abwechselnd die Straße (center) und die Anzahl (count) aus
    for element in data.get('elements', []):
        if element['type'] == 'way':
            tags = element.get('tags', {})
            name = tags.get('name')
            lat = element.get('center', {}).get('lat')
            lon = element.get('center', {}).get('lon')
            s_id = name.replace(" ", "_").lower()
            
            current_street = s_id
            if s_id not in streets_dict:
                streets_dict[s_id] = {
                    "name": name,
                    "households": 0, # Wird im nächsten Schritt (count) gefüllt
                    "coords": [lat, lon],
                    "status": "free",
                    "user": "",
                    "sector": 0
                }
                coords_list.append([lat, lon])
        
        elif element['type'] == 'count' and current_street:
            # Wir nehmen die Anzahl der gefundenen Hausnummer-Objekte
            count = int(element.get('tags', {}).get('total', 0))
            # Fallback: Wenn 0 Häuser gefunden wurden (OSM Lücke), setzen wir 5 als Minimum
            streets_dict[current_street]["households"] += max(count, 5)

    return streets_dict, coords_list

def generate_multi_plan():
    plz_liste = []
    while True:
        p = input("PLZ eingeben (oder '0' zum Beenden): ").strip()
        if p == '0': break
        if len(p) == 5: plz_liste.append(p)

    if not plz_liste: return
    stadt_label = input("Anzeigename: ")
    anzahl_austeiler = int(input("Anzahl Austeiler: "))

    streets_dict, coords_list = fetch_streets_multi_plz(plz_liste)
    keys = sorted(streets_dict.keys())
    for i, key in enumerate(keys):
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
    print(f"✅ Planung fertiggestellt! {len(streets_dict)} Straßen.")

if __name__ == "__main__":
    generate_multi_plan()