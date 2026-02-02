import requests
import json
import os
from datetime import datetime

def fetch_streets_multi_plz(plz_liste):
    """
    Fragt die Overpass API nach Straßen und der Anzahl der Hausnummern im Umkreis ab.
    Aggregiert Daten für Straßen, die aus mehreren Segmenten bestehen.
    """
    print(f"🔍 Suche Straßen und Hausnummern für PLZ: {', '.join(plz_liste)}...")
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    # Gebietsfilter für alle angegebenen PLZs erstellen
    area_filters = "".join([f'area["postal_code"="{p}"];' for p in plz_liste])
    
    # Die Query sucht Straßen und zählt Hausnummern im 25m Radius um jedes Segment
    overpass_query = f"""
    [out:json][timeout:180];
    ({area_filters})->.searchAreas;
    (
      way["highway"~"residential|tertiary|unclassified|living_street"]["name"](area.searchAreas);
    )->.allStreets;
    
    foreach .allStreets -> .thisStreet {{
      .thisStreet out center;
      node["addr:housenumber"](around.thisStreet:25);
      out count;
    }}
    """
    
    try:
        response = requests.post(overpass_url, data={'data': overpass_query})
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ Fehler bei der API-Abfrage: {e}")
        return {}, []

    streets_dict = {}
    coords_list = []
    current_street_id = None

    # Verarbeitung der Overpass-Antwort
    # Overpass liefert abwechselnd 'way' (die Straße) und 'count' (die Häuser dazu)
    for element in data.get('elements', []):
        if element['type'] == 'way':
            tags = element.get('tags', {})
            name = tags.get('name')
            lat = element.get('center', {}).get('lat')
            lon = element.get('center', {}).get('lon')
            
            # Eindeutige ID basierend auf dem Namen (kleingeschrieben)
            s_id = name.replace(" ", "_").lower()
            current_street_id = s_id
            
            if s_id not in streets_dict:
                streets_dict[s_id] = {
                    "name": name,
                    "households": 0, 
                    "coords": [lat, lon],
                    "status": "free",
                    "user": "",
                    "sector": 0
                }
                coords_list.append([lat, lon])
                
        elif element['type'] == 'count' and current_street_id:
            # Hausnummern zum bestehenden Straßeneintrag addieren
            count = int(element.get('tags', {}).get('total', 0))
            streets_dict[current_street_id]["households"] += count

    # Mindestanzahl an Häusern setzen, falls OSM keine Daten hat (Vermeidung von 0)
    for s_id in streets_dict:
        if streets_dict[s_id]["households"] == 0:
            streets_dict[s_id]["households"] = 5
            
    return streets_dict, coords_list

def generate_multi_plan():
    """
    Hauptfunktion zur Erstellung der Planungsdatei.
    Fragt PLZs ab, bis '0' eingegeben wird.
    """
    plz_liste = []
    print("--- Admin-Tool: Gebietsplanung erstellen ---")
    while True:
        p = input("PLZ eingeben (oder '0' zum Beenden/Starten): ").strip()
        if p == '0':
            break
        if len(p) == 5 and p.isdigit():
            plz_liste.append(p)
        else:
            print("⚠️ Bitte eine gültige 5-stellige PLZ eingeben.")

    if not plz_liste:
        print("❌ Keine PLZ angegeben. Abbruch.")
        return

    stadt_label = input("Anzeigename für das Gebiet (z.B. Sulzbach & Soden): ")
    anzahl_austeiler = int(input("In wie viele Sektoren soll aufgeteilt werden? "))

    # Daten von OpenStreetMap holen
    streets_dict, coords_list = fetch_streets_multi_plz(plz_liste)
    
    if not streets_dict:
        print("❌ Keine Daten gefunden. Prüfe die PLZ oder die Internetverbindung.")
        return

    # Sektoren gleichmäßig zuweisen
    sorted_keys = sorted(streets_dict.keys())
    for i, key in enumerate(sorted_keys):
        streets_dict[key]['sector'] = (i % anzahl_austeiler) + 1

    # Geografisches Zentrum für die Karten-Initialisierung berechnen
    avg_lat = sum(c[0] for c in coords_list) / len(coords_list)
    avg_lon = sum(c[1] for c in coords_list) / len(coords_list)

    # Finale Datenstruktur erstellen
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
    
    # Ordner erstellen und Datei speichern
    os.makedirs('data', exist_ok=True)
    with open('data/streets_status.json', 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, sort_keys=True, ensure_ascii=False)
    
    print(f"\n✅ Erfolg!")
    print(f"📍 Gebiet: {stadt_label} ({', '.join(plz_liste)})")
    print(f"🛣️  Gefundene Straßen: {len(streets_dict)}")
    print(f"🏠 Erfasste Häuser gesamt: {sum(s['households'] for s in streets_dict.values())}")
    print(f"📂 Datei gespeichert unter: data/streets_status.json")

if __name__ == "__main__":
    generate_multi_plan()