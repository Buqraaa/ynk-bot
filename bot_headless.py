"""
Headless baslatici: GUI (pywebview) olmadan bot + panel calistirir.
Oracle Cloud / VPS / Docker gibi sunucu ortamlari icin kullanilir.
Kullanim: python bot_headless.py
"""
import os
import sys
import threading
import time
import urllib.request

from web.app import fastapi_baslat
from core.manager import bot_manager

PORT = int(os.environ.get("PORT", 8000))
PANEL_URL = f"http://0.0.0.0:{PORT}"


def _sunucu_hazir_mi(url, timeout=15):
    bitis = time.time() + timeout
    while time.time() < bitis:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    server_thread = threading.Thread(
        target=fastapi_baslat, args=("0.0.0.0", PORT), daemon=True, name="ynk-web"
    )
    server_thread.start()

    if _sunucu_hazir_mi(f"http://127.0.0.1:{PORT}"):
        print(f"[YNK] Panel hazir: http://0.0.0.0:{PORT}")
    else:
        print("[YNK] Panel baslatilamadi!")

    # Botu otomatik baslat
    bot_manager.start()
    time.sleep(2)
    print(f"[YNK] Bot durumu: {bot_manager.status}")

    # Ana thread'i canli tut
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[YNK] Kapatiliyor...")
        bot_manager.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
