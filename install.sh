#!/data/data/com.termux/files/usr/bin/bash
set -e
pkg install -y python >/dev/null 2>&1 || true
mkdir -p "$HOME/website-deployer"
cd "$HOME/website-deployer"
python -m pip install -r requirements.txt
python -m py_compile app.py
echo
echo "Website Deployer terpasang."
echo "Jalankan: cd ~/website-deployer && python app.py"
echo "Buka: http://127.0.0.1:5000"
