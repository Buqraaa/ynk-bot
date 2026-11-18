#!/bin/bash
# Oracle Cloud (Ubuntu 22.04/24.04) icin YNK Bot kurulum scripti
# Kullanim: bash setup_oracle.sh

set -e

echo "=== YNK Bot - Oracle Cloud Kurulum ==="

# 1. Sistem guncelle
sudo apt update && sudo apt upgrade -y

# 2. Python ve bagimliliklar
sudo apt install -y python3 python3-pip python3-venv ffmpeg git

# 3. Proje klasoru
mkdir -p /home/ubuntu/ynk-bot
cd /home/ubuntu/ynk-bot

# 4. Python virtual env
python3 -m venv venv
source venv/bin/activate

# 5. Bagimliliklari kur
pip install --upgrade pip
pip install -r requirements.txt

# 6. .env dosyasi (token'i buraya yaz)
if [ ! -f .env ]; then
    cp .env.example .env
    echo "!!! .env dosyasini duzenle: nano .env !!!"
fi

echo ""
echo "=== Kurulum tamamlandi ==="
echo "Sonraki adimlar:"
echo "1. nano .env  (DISCORD_TOKEN yaz)"
echo "2. scp ile settings.json ve ynk.db dosyalarini yukle"
echo "3. sudo cp ynk-bot.service /etc/systemd/system/"
echo "4. sudo systemctl daemon-reload"
echo "5. sudo systemctl enable ynk-bot"
echo "6. sudo systemctl start ynk-bot"
echo "7. sudo systemctl status ynk-bot"
echo ""
echo "Panel: http://SUNUCU_IP:8000"
echo "Oracle Cloud'da port 8000'i acmayi unutma (Security List / Ingress Rules)!"
