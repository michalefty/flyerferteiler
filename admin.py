import requests
import json
import os
from datetime import datetime

def generate_plan(stadt, plz, anzahl_austeiler):
    # Overpass API Abfrage (wie gehabt)
    # ... (Query-Logik hier) ...
    
    # Beispiel-Daten nach Abfrage:
    alle_strassen = [
        {"name": "Hauptstr.", "households": 40, "coords": [50.1, 9.1]},
        {"name": "Kirchweg", "households": 20, "coords": [50.11, 9.12]},
        # ... viele mehr
    ]
    
    # Berechnung der Sektoren
    gesamt_haushalte = sum(s['households'] for s in alle_strassen)
    ziel_pro_person = gesamt_haushalte / anzahl_austeiler
    
    streets_dict = {}
    for i, s in enumerate(alle_strassen):
        # Jeder Straße eine ID und Sektor-Empfehlung geben
        streets_dict[f"s_{i}"] = {
            "name": s['name'],
            "households": s['households'],
            "coords": s['coords'],
            "status": "free",
            "user": "",
            "sector": (i % anzahl_austeiler) + 1  # Einfache Zuweisung
        }

    export_data = {
        "metadata": {
            "city": stadt,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_households": gesamt_haushalte,
            "target_per_person": round(ziel_pro_person, 1)
        },
        "streets": streets_dict
    }
    
    with open('data/streets_status.json', 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, sort_keys=True, ensure_ascii=False)

# Start
generate_plan("Sulzbach", "63834", 5)