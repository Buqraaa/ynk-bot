import threading

import webview

from web.app import fastapi_baslat


def main():
    server_thread = threading.Thread(
        target=fastapi_baslat, daemon=True, name="ynk-web"
    )
    server_thread.start()

    webview.create_window(
        "YNK Studio - MEE6 Dashboard",
        "http://127.0.0.1:8000",
        width=1280,
        height=800,
    )
    webview.start()


if __name__ == "__main__":
    main()
