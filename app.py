from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime
import requests
import math
try:
    import config
except ImportError:
    config = None

app = Flask(__name__)
DATA_FILE = 'data/streets_status.json'

def load_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)

@app.route('/')
def index():
    data = load_data()
    days = getattr(config, 'SURVEY_DURATION_DAYS', 7) if config else 7
    return render_template('index.html', metadata=data['metadata'], streets=data['streets'], survey_days=days)

@app.route('/update', methods=['POST'])
def update():
    req = request.json
    data = load_data()
    # Support für einzelne ID oder Liste von IDs (Bulk)
    ids = req['id'] if isinstance(req['id'], list) else [req['id']]
    
    for s_id in ids:
        if s_id in data['streets']:
            # 1. Reservieren (nur wenn vorher frei)
            if req['status'] == 'taken' and data['streets'][s_id]['status'] == 'free':
                data['streets'][s_id]['status'] = 'taken'
                data['streets'][s_id]['user'] = req['user']
            # 2. Freigeben (Deselect)
            elif req['status'] == 'free':
                data['streets'][s_id]['status'] = 'free'
                data['streets'][s_id]['user'] = ""
    
    save_data(data)
    return jsonify({"success": True})

@app.route('/admin/login', methods=['POST'])
def admin_login():
    pwd = request.json.get('password')
    correct = os.environ.get('ADMIN_PASSWORD')
    if not correct and config:
        correct = getattr(config, 'ADMIN_PASSWORD', None)
    if not correct:
        correct = 'geheim123'
        
    if pwd == correct:
        return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route('/admin/add_street', methods=['POST'])
def add_street():
    req = request.json
    data = load_data()
    
    new_name_clean = req['name'].strip().lower()
    force = req.get('force', False)
    
    # Check for duplicates
    if not force:
        for s in data['streets'].values():
            if s['name'].strip().lower() == new_name_clean:
                return jsonify({"success": False, "error": "duplicate", "msg": f"Straße '{s['name']}' existiert bereits!"})

    s_id = new_name_clean.replace(" ", "_") + "_manual_" + str(int(datetime.now().timestamp()))
    
    new_street = {
        "name": req['name'],
        "households": int(req['households']),
        "length": int(req['length']),
        "coords": req['coords'],
        "path": [req['path']], 
        "status": "free",
        "user": ""
    }
    
    data['streets'][s_id] = new_street
    save_data(data)
    return jsonify({"success": True})

@app.route('/admin/edit_street', methods=['POST'])
def edit_street():
    req = request.json
    s_id = req['id']
    data = load_data()
    
    if s_id not in data['streets']:
        return jsonify({"success": False, "msg": "ID nicht gefunden"}), 404
        
    street = data['streets'][s_id]
    
    if 'name' in req: street['name'] = req['name']
    if 'households' in req: street['households'] = int(req['households'])
    if 'status' in req: 
        street['status'] = req['status']
        if req['status'] == 'free': street['user'] = ""
    
    save_data(data)
    return jsonify({"success": True})

@app.route('/admin/delete_street', methods=['POST'])
def delete_street():
    req = request.json
    s_id = req['id']
    data = load_data()
    
    if s_id in data['streets']:
        del data['streets'][s_id]
        save_data(data)
        return jsonify({"success": True})
    
    return jsonify({"success": False, "msg": "Nicht gefunden"}), 404

@app.route('/admin/count_houses', methods=['POST'])
def count_houses():
    path = request.json.get('path', [])
    if not path or len(path) < 2:
        return jsonify({"count": 0})

    # Build Poly string for Overpass "poly" filter
    # Format: "lat1 lon1 lat2 lon2 ..."
    poly_str = " ".join([f"{p[0]} {p[1]}" for p in path])
    
    # Query: Houses inside or near the polygon? 
    # Poly filter selects elements strictly INSIDE or ON the line. 
    # For a street line, we want houses AROUND it. 
    # Standard Overpass around works on IDs or coordinates. 
    # We can simulate "around" by checking around the points.
    
    # Let's try recursive around for points.
    # OR better: use (poly:...) to get the line (if it was an OSM way). But we have raw coords.
    # Efficient approach: Query houses in the bounding box, then filter in Python?
    # Or just query around each point of the path (approximate).
    
    # Simplified approach: Query around the *center* of the line? No, too inaccurate.
    # Query around *each point* with radius 30m.
    
    query_parts = []
    for p in path[::3]: # Optimization: Check every 3rd point (approx every 10-20m usually)
        query_parts.append(f'nwr["addr:housenumber"](around:35,{p[0]},{p[1]});')
    
    combined_query = ''.join(query_parts)
    query = f'[out:json][timeout:25];({combined_query}); out count;'
    
    try:
        r = requests.post("http://overpass-api.de/api/interpreter", data={'data': query}, timeout=30)
        if r.status_code == 200:
            # Output contains count element
            # structure: { elements: [ { tags: { total: "123" } } ] } or similar for "out count"
            # Actually "out count" returns stats in the head or a specific element.
            # Let's verify Overpass "out count" response format:
            # It returns an element with "type": "count", "tags": {"nodes": "...", ... "total": "..."}
            
            res = r.json()
            if 'elements' in res and len(res['elements']) > 0:
                total = int(res['elements'][0]['tags'].get('total', 0))
                return jsonify({"count": total})
    except Exception as e:
        print(f"Overpass Error: {e}")
        
    return jsonify({"count": 0, "error": "API failed"})

@app.route('/admin/export_geojson', methods=['GET'])
def export_geojson():
    data = load_data()
    features = []
    
    for s_id, s in data['streets'].items():
        # Handle LineString or Point
        geometry = {
            "type": "LineString",
            "coordinates": [[p[1], p[0]] for p in s.get('path', [])] # GeoJSON uses [lon, lat]
        } if s.get('path') and len(s['path']) > 1 else {
            "type": "Point",
            "coordinates": [s['coords'][1], s['coords'][0]]
        }
        
        feature = {
            "type": "Feature",
            "properties": {
                "name": s['name'],
                "households": s['households'],
                "length": s.get('length', 0),
                "status": s['status']
            },
            "geometry": geometry
        }
        features.append(feature)
        
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    return jsonify(geojson)

if __name__ == '__main__':
    app.run(port=8080)