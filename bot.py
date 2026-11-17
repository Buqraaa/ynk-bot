import threading
import time
import urllib.request

import webview

from web.app import fastapi_baslat

PANEL_URL = "http://127.0.0.1:8000"


def _sunucu_hazir_mi(url, timeout=10):
    bitis = time.time() + timeout
    while time.time() < bitis:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except Exception:
            time.sleep(0.2)
    return False


def main():
    server_thread = threading.Thread(
        target=fastapi_baslat, daemon=True, name="ynk-web"
    )
    server_thread.start()
    _sunucu_hazir_mi(PANEL_URL)

    webview.create_window(
        "YNK Studio - MEE6 Dashboard",
        PANEL_URL,
        width=1280,
        height=800,
    )
    webview.start()


if __name__ == "__main__":
    main()
