from flask import Flask, render_template, request, jsonify
import json
import os

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

if __name__ == '__main__':
    app.run(port=8080)