import os
import json

def anonymize_users():
    print("\n--- 🛡️ User-Namen Anonymisieren (DSGVO) ---")
    data_file = 'data/streets_status.json'
    
    if not os.path.exists(data_file):
        print(f"❌ Datei '{data_file}' nicht gefunden.")
        return

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for s in data.get('streets', {}).values():
        user = s.get('user', '').strip()
        if user:
            # Simple heuristic: Split by space
            parts = user.split()
            if len(parts) >= 2:
                # Firstname + Lastname -> Firstname + L.
                new_name = f"{parts[0]} {parts[-1][0]}."
                if new_name != user:
                    s['user'] = new_name
                    count += 1
            # Special case: Single name stays single name (nickname assumption)

    if count > 0:
        print(f"✅ {count} Namen wurden gekürzt (z.B. 'Max Mustermann' -> 'Max M.').")
        if input("💾 Änderungen speichern? (j/n): ").strip().lower() == 'j':
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
            print("💾 Gespeichert!")
    else:
        print("ℹ️ Keine Namen gefunden, die gekürzt werden mussten.")
