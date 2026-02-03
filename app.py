from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime

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
    return render_template('index.html', metadata=data['metadata'], streets=data['streets'])

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
    # Simple hardcoded password or from env
    pwd = request.json.get('password')
    correct = os.environ.get('ADMIN_PASSWORD', 'geheim123') 
    if pwd == correct:
        return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route('/admin/add_street', methods=['POST'])
def add_street():
    req = request.json
    # Validation: Check if admin (client-side usually, but here simple)
    # Ideally use a session or token, but for this scale, we trust the "hidden" UI if pwd matched
    
    data = load_data()
    
    s_id = req['name'].replace(" ", "_").lower() + "_manual_" + str(int(datetime.now().timestamp()))
    
    new_street = {
        "name": req['name'],
        "households": int(req['households']),
        "length": int(req['length']),
        "coords": req['coords'], # Center [lat, lon]
        "path": [req['path']],   # Geometry [[lat, lon], ...]
        "status": "free",
        "user": ""
    }
    
    data['streets'][s_id] = new_street
    save_data(data)
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(port=8080)