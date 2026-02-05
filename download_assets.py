import os
import requests

ASSETS = {
    "leaflet.css": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
    "leaflet.js": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    "leaflet.js.map": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js.map",
    # Images need to be handled if not embedded, Leaflet usually expects images relative to css
    # We will grab standard images
    "images/layers.png": "https://unpkg.com/leaflet@1.9.4/dist/images/layers.png",
    "images/layers-2x.png": "https://unpkg.com/leaflet@1.9.4/dist/images/layers-2x.png",
    "images/marker-icon.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    "images/marker-icon-2x.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    "images/marker-shadow.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    
    "jspdf.umd.min.js": "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js",
    "html2canvas.min.js": "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"
}

DEST_MAP = {
    "leaflet.css": "static/lib/leaflet/leaflet.css",
    "leaflet.js": "static/lib/leaflet/leaflet.js",
    "leaflet.js.map": "static/lib/leaflet/leaflet.js.map",
    "images/layers.png": "static/lib/leaflet/images/layers.png",
    "images/layers-2x.png": "static/lib/leaflet/images/layers-2x.png",
    "images/marker-icon.png": "static/lib/leaflet/images/marker-icon.png",
    "images/marker-icon-2x.png": "static/lib/leaflet/images/marker-icon-2x.png",
    "images/marker-shadow.png": "static/lib/leaflet/images/marker-shadow.png",
    "jspdf.umd.min.js": "static/lib/jspdf/jspdf.umd.min.js",
    "html2canvas.min.js": "static/lib/html2canvas/html2canvas.min.js"
}

def download_assets():
    print("⬇️  Downloading Assets...")
    for name, url in ASSETS.items():
        dest = DEST_MAP[name]
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            print(f"   Fetching {name}...")
            r = requests.get(url)
            r.raise_for_status()
            with open(dest, 'wb') as f:
                f.write(r.content)
        except Exception as e:
            print(f"❌ Error downloading {name}: {e}")

if __name__ == "__main__":
    download_assets()
