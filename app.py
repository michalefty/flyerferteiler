from flask import Flask, render_template, request, jsonify
import json

app = Flask(__name__)

@app.route('/')
def index():
    with open('data/streets_status.json', 'r') as f:
        data = json.load(f)
    return render_template('index.html', metadata=data['metadata'], streets=data['streets'])

@app.route('/update', methods=['POST'])
def update():
    req = request.json
    with open('data/streets_status.json', 'r') as f:
        data = json.load(f)
    
    s_id = req['id']
    data['streets'][s_id]['status'] = req['status']
    data['streets'][s_id]['user'] = req['user']
    
    with open('data/streets_status.json', 'w') as f:
        json.dump(data, f, indent=2)
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(port=10000)