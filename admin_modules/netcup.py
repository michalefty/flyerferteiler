import requests
import json

try:
    import config
except ImportError:
    config = None

API_URL = "https://ccp.netcup.net/run/webservice/servers/endpoint.php?JSON"

def update_dns_record(new_ip):
    if not config: return
    
    api_key = getattr(config, 'NETCUP_API_KEY', None)
    api_password = getattr(config, 'NETCUP_API_PASSWORD', None)
    customer_number = getattr(config, 'NETCUP_CUSTOMER_NUMBER', None)
    domain = getattr(config, 'NETCUP_DOMAIN', None)
    hostname = getattr(config, 'NETCUP_HOST', '@')
    
    if not (api_key and api_password and customer_number and domain):
        # Silent return if not configured, or maybe just a log if verbose?
        # Only warn if one is missing but others present implies configuration attempt
        if api_key or customer_number:
            print("⚠️ Netcup Konfiguration unvollständig (API Key, Password, Customer Nr, Domain).")
        return

    print(f"🌍 Starte Netcup DNS Update für {hostname}.{domain} -> {new_ip}...")
    
    session = requests.Session()
    
    # 1. Login
    payload_login = {
        "action": "login",
        "param": {
            "apikey": api_key,
            "apipassword": api_password,
            "customernumber": customer_number
        }
    }
    
    try:
        r = session.post(API_URL, json=payload_login)
        resp = r.json()
        if resp['status'] != 'success':
            print(f"❌ Netcup Login fehlgeschlagen: {resp.get('longmessage')}")
            return
        
        apisessionid = resp['responsedata']['apisessionid']
        
        # 2. Get Info to update (InfoDnsRecords)
        payload_info = {
            "action": "infoDnsRecords",
            "param": {
                "apikey": api_key,
                "apisessionid": apisessionid,
                "customernumber": customer_number,
                "domainname": domain
            }
        }
        
        r = session.post(API_URL, json=payload_info)
        resp = r.json()
        if resp['status'] != 'success':
             print(f"❌ Fehler beim Abrufen der DNS Records: {resp.get('longmessage')}")
        else:
            records = resp['responsedata']['dnsrecords']
            target_record = None
            for rec in records:
                if rec['hostname'] == hostname and rec['type'] == 'A':
                    target_record = rec
                    break
            
            if not target_record:
                print(f"⚠️ Record für {hostname} (Type A) nicht gefunden.")
            elif target_record['destination'] == new_ip:
                print("✅ DNS Eintrag ist bereits aktuell.")
            else:
                # 3. Update Record
                target_record['destination'] = new_ip
                payload_update = {
                    "action": "updateDnsRecords",
                    "param": {
                        "apikey": api_key,
                        "apisessionid": apisessionid,
                        "customernumber": customer_number,
                        "domainname": domain,
                        "dnsrecordset": {
                            "dnsrecords": [target_record]
                        }
                    }
                }
                r = session.post(API_URL, json=payload_update)
                resp = r.json()
                if resp['status'] == 'success':
                    print(f"✅ DNS Eintrag aktualisiert: {hostname}.{domain} -> {new_ip}")
                    print("ℹ️  Hinweis: Es kann bis zu 48h dauern, bis die Änderung überall sichtbar ist (TTL).")
                else:
                     print(f"❌ Fehler beim Update des DNS Records: {resp.get('longmessage')}")

        # 4. Logout
        payload_logout = {
            "action": "logout",
            "param": {
                "apikey": api_key,
                "apisessionid": apisessionid,
                "customernumber": customer_number
            }
        }
        session.post(API_URL, json=payload_logout)

    except Exception as e:
        print(f"❌ Netcup API Fehler: {e}")
