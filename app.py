import os
import json
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

try:
    import config
    secret_key = config.SECRET_KEY
except ImportError:
    secret_key = "fallback-schluessel-bitte-config-erstellen"

app = Flask(__name__)
app.config['SECRET_KEY'] = secret_key
socketio = SocketIO(app, cors_allowed_origins="*")
app = Flask(__name__)
# WICHTIG: Ein geheimer Schlüssel für die Sitzungen
app.config['SECRET_KEY'] = 'flyer-geheimnis-123'
socketio = SocketIO(app, cors_allowed_origins="*")

# Pfad zur Datendatei (im gemounteten Volume auf Render)
DATA_FILE = 'data/streets_status.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# Daten beim Start laden
streets_db = load_data()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    # Schickt dem User sofort den aktuellen Stand, wenn er die Seite öffnet
    emit('update_ui', {"streets": streets_db})

@socketio.on('unselect_street')
def handle_unselection(data):
    town_key = data.get('town_key')
    s_id = data.get('street_id')
    user_name = data.get('user_name')
    
    if town_key in streets_db and s_id in streets_db[town_key]:
        # Sicherheitsscheck: Nur der eingetragene User darf freigeben
        if streets_db[town_key][s_id]['user'] == user_name:
            streets_db[town_key][s_id]['status'] = 'free'
            streets_db[town_key][s_id]['user'] = ""
            
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(streets_db, f, indent=2, ensure_ascii=False)
                
            emit('update_ui', {"streets": streets_db}, broadcast=True)

@socketio.on('select_street')
def handle_selection(data):
    town_key = data.get('town_key')
    s_id = data.get('street_id')
    user_name = data.get('user_name')
    
    # Prüfen, ob Ort und Straße existieren und frei sind
    if town_key in streets_db and s_id in streets_db[town_key]:
        if streets_db[town_key][s_id]['status'] == 'free':
            streets_db[town_key][s_id]['status'] = 'taken'
            streets_db[town_key][s_id]['user'] = user_name
            
            # Speichern
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(streets_db, f, indent=2, ensure_ascii=False)
                
            # Update an alle
            emit('update_ui', {"streets": streets_db}, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port)