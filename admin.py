import requests
import json
import os
from datetime import datetime
import math

def fetch_streets_multi_plz(plz_liste):
    """
    Lädt Straßen und Hausnummern getrennt und ordnet sie lokal zu.
    Verhindert 504 Timeouts durch Reduzierung der Serverlast.
    """
    print(f"🔍 Optimiere Abfrage für: {', '.join(plz_liste)}...")
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    area_filters = "".join([f'area["postal_code"="{p}"];' for p in plz_liste])
    
    # Neue, flache Query: Lädt alle Straßen UND alle Hausnummer-Knoten separat
    overpass_query = f"""
    [out:json][timeout:90];
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

    # Daten sortieren: Was ist Straße, was ist Hausnummer?
    for el in data.get('elements', []):
        if el['type'] == 'way':
            streets_raw.append(el)
        elif el['type'] == 'node' and 'tags' in el and 'addr:housenumber' in el['tags']:
            house_nodes.append((el['lat'], el['lon']))

    print(f"🗺️  {len(streets_raw)} Straßenabschnitte und {len(house_nodes)} Hausnummern geladen.")
    print("🧮 Ordne Häuser den Straßen lokal zu (Distanz-Check)...")

    streets_dict = {}
    coords_list = []

    # Funktion für grobe Distanzberechnung (Pythagoras reicht hier völlig aus)
    def get_dist(lat1, lon1, lat2, lon2):
        return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

    # 1. Straßen initialisieren
    for s in streets_raw:
        name = s['tags']['name']
        lat = s['center']['lat']
        lon = s['center']['lon']
        s_id = name.replace(" ", "_").lower()
        
        if s_id not in streets_dict:
            streets_dict[s_id] = {
                "name": name, "households": 0, "coords": [lat, lon],
                "status": "free", "user": "", "sector": 0, "segments": []
            }
            coords_list.append([lat, lon])
        
        # Wir speichern die Segmente (Center-Punkte), um Häuser später zuzuordnen
        streets_dict[s_id]["segments"].append((lat, lon))

    # 2. Häuser den Straßen zuordnen (Radius ca. 30m / 0.0003 Grad)
    # Wissenschaftlicher Hinweis: 0.0001 Grad entsprechen ca. 11 Metern
    THRESHOLD = 0.0003 
    
    for h_lat, h_lon in house_nodes:
        min_dist = 999
        best_street = None
        
        # Finde die nächste Straße für dieses Haus
        for s_id, s_data in streets_dict.items():
            for seg_lat, seg_lon in s_data["segments"]:
                d = get_dist(h_lat, h_lon, seg_lat, seg_lon)
                if d < min_dist:
                    min_dist = d
                    best_street = s_id
        
        if best_street and min_dist < THRESHOLD:
            streets_dict[best_street]["households"] += 1

    # Cleanup: Segmente entfernen und Minimum setzen
    for s_id in streets_dict:
        del streets_dict[s_id]["segments"]
        if streets_dict[s_id]["households"] == 0:
            streets_dict[s_id]["households"] = 5
            
    return streets_dict, coords_list

def generate_multi_plan():
    plz_liste = []
    print("--- Admin-Tool: Gebietsplanung (Optimiert) ---")
    while True:
        p = input("PLZ eingeben (oder '0' zum Starten): ").strip()
        if p == '0': break
        if len(p) == 5: plz_liste.append(p)

    if not plz_liste: return
    stadt_label = input("Anzeigename für das Gebiet: ")
    anzahl_austeiler = int(input("Anzahl Sektoren: "))

    streets_dict, coords_list = fetch_streets_multi_plz(plz_liste)
    if not streets_dict: return

    # Sektoren und Export (wie gehabt)
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
    
    print(f"\n✅ Fertig! {len(streets_dict)} Straßen und {sum(s['households'] for s in streets_dict.values())} Häuser erfasst.")

if __name__ == "__main__":
    generate_multi_plan()