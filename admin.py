import requests
import json
import os

def fetch_and_append_town(city_name, postal_code, all_data):
    overpass_url = "http://overpass-api.de/api/interpreter"
    # Suche spezifisch nach Ort + PLZ
    query = f"""
    [out:json];
    area["name"="{city_name}"]["postal_code"="{postal_code}"]->.searchArea;
    (
      way(area.searchArea)["highway"]["name"];
      node(area.searchArea)["addr:street"]["addr:housenumber"];
    );
    out body;
    """
    response = requests.get(overpass_url, params={'data': query})
    elements = response.json().get('elements', [])

    streets = {}
    for el in elements:
        if el['type'] == 'node' and 'addr:street' in el['tags']:
            s_name = el['tags']['addr:street']
            streets[s_name] = streets.get(s_name, 0) + 1

    town_key = f"{postal_code}_{city_name}"
    all_data[town_key] = {}
    
    counter = 1
    for name, count in streets.items():
        all_data[town_key][f"{town_key}_{counter}"] = {
            "name": name,
            "households": count,
            "status": "free",
            "user": ""
        }
        counter += 1

# Hauptablauf
all_towns = {}
orte = [
    ("Sulzbach am Main", "63834"),
    ("Dornau", "63834"),
    ("Soden", "63834")
]

for stadt, plz in orte:
    print(f"Lade {stadt}...")
    fetch_and_append_town(stadt, plz, all_towns)

with open('data/streets_status.json', 'w', encoding='utf-8') as f:
    json.dump(all_towns, f, indent=2, ensure_ascii=False)