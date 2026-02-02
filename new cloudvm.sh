#new cloudvm
# System-Updates und Tools
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git nginx jq

# Projekt klonen (Nutze deine GitHub-URL)
git clone https://github.com/DEIN_USER/DEIN_REPO.git ~/app
cd ~/app

# Virtual Environment und Python-Pakete
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt


