import requests
import json
import os
from datetime import datetime

def fetch_streets_multi_plz(plz_liste):
    print(f"🔍 Starte Suche für folgende PLZ: {', '.join(plz_liste)}...")
    
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    # Wir bauen die PLZ-Filter dynamisch zusammen: (area["postal_code"="12345"]; area["postal_code"="67890"];)
    area_filters = "".join([f'area["postal_code"="{p}"];' for p in plz_liste])
    
    # Die Query sucht nun in der Vereinigung (Union) aller angegebenen PLZ-Flächen
    overpass_query = f"""
    [out:json][timeout:90];
    ({area_filters})->.searchAreas;
    (
      way["highway"~"residential|tertiary|unclassified|living_street"]["name"](area.searchAreas);
    );
    out center;
    """
    
    response = requests.post(overpass_url, data={'data': overpass_query})
    
    if response.status_code != 200:
        print("❌ Fehler bei der Overpass-Abfrage. Eventuell zu viele Daten oder Server-Timeout.")
        return {}, []

    data = response.json()
    streets_dict = {}
    coords_list = []

    for element in data.get('elements', []):
        tags = element.get('tags', {})
        name = tags.get('name')
        lat = element.get('center', {}).get('lat')
        lon = element.get('center', {}).get('lon')
        
        if name and lat and lon:
            # ID basierend auf Name (kleingeschrieben, ohne Leerzeichen)
            s_id = name.replace(" ", "_").lower()
            
            if s_id not in streets_dict:
                streets_dict[s_id] = {
                    "name": name,
                    "households": 20, 
                    "coords": [lat, lon],
                    "status": "free",
                    "user": "",
                    "sector": 0
                }
                coords_list.append([lat, lon])
    
    return streets_dict, coords_list

def generate_multi_plan():
    # 1. PLZ-Eingabeschleife
    plz_liste = []
    print("--- Gebiets-Planung ---")
    while True:
        p = input("PLZ eingeben (oder '0' zum Beenden): ").strip()
        if p == '0':
            break
        if len(p) == 5 and p.isdigit():
            plz_liste.append(p)
        else:
            print("⚠️ Ungültige PLZ. Bitte 5 Ziffern eingeben.")

    if not plz_liste:
        print("❌ Keine PLZ angegeben. Abbruch.")
        return

    stadt_label = input("Anzeigename für dieses Gesamtgebiet: ")
    anzahl_austeiler = int(input("Anzahl Austeiler für das gesamte Gebiet: "))

    # 2. Daten abrufen
    streets_dict, coords_list = fetch_streets_multi_plz(plz_liste)
    
    if not streets_dict:
        print("❌ Keine Straßen in diesen Gebieten gefunden.")
        return

    # 3. Sektoren zuweisen
    keys = sorted(streets_dict.keys())
    for i, key in enumerate(keys):
        streets_dict[key]['sector'] = (i % anzahl_austeiler) + 1

    # 4. Geografisches Zentrum berechnen
    avg_lat = sum(c[0] for c in coords_list) / len(coords_list)
    avg_lon = sum(c[1] for c in coords_list) / len(coords_list)

    # 5. Exportieren
    export_data = {
        "metadata": {
            "city": stadt_label,
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
    
    print(f"\n✅ Planung fertiggestellt!")
    print(f"📍 Gebiet: {stadt_label}")
    print(f"🛣️ Straßen gefunden: {len(streets_dict)}")
    print(f"📂 Datei 'data/streets_status.json' wurde aktualisiert.")

if __name__ == "__main__":
    generate_multi_plan()