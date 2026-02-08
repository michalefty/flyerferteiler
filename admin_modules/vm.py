import subprocess
import time
try:
    import config
except ImportError:
    config = None

from admin_modules.netcup import update_dns_record

def get_vm_details():
    """Returns (status, ip) or (None, None)"""
    provider = getattr(config, 'CLOUD_PROVIDER', 'none')
    if provider != 'gcloud':
        return None, None

    name = getattr(config, 'VM_INSTANCE_NAME', 'flyer-server')
    zone = getattr(config, 'VM_ZONE', 'europe-west3-c')
    project = getattr(config, 'VM_PROJECT', '')
    
    # Get Status and IP in one go
    # format: csv(status,networkInterfaces[0].accessConfigs[0].natIP)
    cmd = [
        "gcloud", "compute", "instances", "describe", name, 
        "--zone", zone, 
        "--format=csv[no-heading](status,networkInterfaces[0].accessConfigs[0].natIP)"
    ]
    if project: cmd.extend(["--project", project])

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        parts = res.stdout.strip().split(',')
        if len(parts) >= 1:
            status = parts[0]
            ip = parts[1] if len(parts) > 1 else None
            return status, ip
    except FileNotFoundError:
        print("⚠️ 'gcloud' Command nicht gefunden.")
    except subprocess.CalledProcessError:
        pass # Instance might not exist or auth fail
    return None, None

def start_vm():
    provider = getattr(config, 'CLOUD_PROVIDER', 'none')
    if provider != 'gcloud':
        return True

    name = getattr(config, 'VM_INSTANCE_NAME', 'flyer-server')
    zone = getattr(config, 'VM_ZONE', 'europe-west3-c')
    project = getattr(config, 'VM_PROJECT', '')
    
    status, _ = get_vm_details()
    print(f"🔍 VM Status: {status}")

    if status == "RUNNING":
        if input("🔄 VM läuft. Neustart (Reset) erzwingen? (j/n): ").strip().lower() == 'j':
            cmd = ["gcloud", "compute", "instances", "reset", name, "--zone", zone]
            if project: cmd.extend(["--project", project])
            try:
                subprocess.run(cmd, check=True)
                print("✅ Reset ausgelöst. Warte 30s...")
                time.sleep(30)
            except subprocess.CalledProcessError as e:
                print(f"❌ Fehler beim Reset: {e}")
        return True

    # Start
    if input(f"🚀 VM '{name}' jetzt starten? (j/n): ").strip().lower() != 'j':
        return False

    cmd = ["gcloud", "compute", "instances", "start", name, "--zone", zone]
    if project: cmd.extend(["--project", project])

    try:
        subprocess.run(cmd, check=True)
        print("✅ Startbefehl gesendet. Warte auf Boot (45s)...")
        time.sleep(45)
        
        # Check IP and update DNS
        _, ip = get_vm_details()
        if ip:
            update_dns_record(ip)
            
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Start fehlgeschlagen: {e}")
        return False

def trigger_server_update():
    """Triggers the refresh_data.sh script on the server via SSH."""
    provider = getattr(config, 'CLOUD_PROVIDER', 'none')
    if provider != 'gcloud':
        return

    name = getattr(config, 'VM_INSTANCE_NAME', 'flyer-server')
    zone = getattr(config, 'VM_ZONE', 'europe-west3-c')
    project = getattr(config, 'VM_PROJECT', '')
    
    print("🔄 Trigger Server-Update (git pull & restart)...")
    
    # Assuming script is at ~/app/refresh_data.sh based on APP_DIR in script
    # We use 'sudo' because the script restarts systemd services
    ssh_cmd = f"sudo /home/micha/app/refresh_data.sh"
    
    cmd = ["gcloud", "compute", "ssh", name, "--zone", zone, "--command", ssh_cmd]
    if project: cmd.extend(["--project", project])

    try:
        subprocess.run(cmd, check=True)
        print("✅ Update-Trigger erfolgreich.")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Update-Trigger fehlgeschlagen: {e}")
        print("   (Der Server holt die Daten aber auch automatisch per Cronjob)")

def schedule_stop_vm(days=None):
    print(f"ℹ️  Shutdown-Timer deaktiviert (Server läuft dauerhaft).")
