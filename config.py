import json
import logging
import os
import sys
import threading
from pathlib import Path

# PyInstaller ile derlendiginde ayarlar exe'nin yaninda, sablonlar ise gecici
# bundle klasorunde durur. Gelistirme sirasinda ikisi de proje klasorundedir.
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = APP_DIR

CONFIG_FILE = APP_DIR / "settings.json"
EXTENSION_FILE = APP_DIR / "user_extension.py"
LOG_FILE = APP_DIR / "bot.log"


def _load_env_file(path, override=False):
    """Harici bagimlilik olmadan basit .env okuyucu."""
    try:
        with open(path, "r", encoding="utf-8-sig") as env_file:
            for satir in env_file:
                satir = satir.strip()
                if not satir or satir.startswith("#") or "=" not in satir:
                    continue
                anahtar, deger = satir.split("=", 1)
                anahtar = anahtar.strip()
                deger = deger.strip().strip('"').strip("'")
                if override or anahtar not in os.environ:
                    os.environ[anahtar] = deger
    except FileNotFoundError:
        pass


def token_oku():
    """Her bot baslatmasinda .env'yi yeniden okur."""
    _load_env_file(APP_DIR / ".env", override=True)
    return os.getenv("DISCORD_TOKEN", "").strip()


BOT_TOKEN = token_oku()

_handlers = [logging.StreamHandler()]
try:
    _handlers.insert(0, logging.FileHandler(LOG_FILE, encoding="utf-8"))
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_handlers,
)
logger = logging.getLogger("ynk")

default_settings = {
    "hedef_uye": 1000,
    "sayac_kanal": "genel",
    "giris_mesaji": "Sunucumuza hoş geldin {uye}! 🎉",
    "cikis_mesaji": "{uye} aramızdan ayrıldı.",
    "tavsiye_kanal": "genel",
    "tavsiye_baslik": "✨ Yeni Tavsiye",
    "log_kanal": "genel",
    "youtube_kanal": "duyuru",
    "youtube_channel_id": "",
    "youtube_mesaj": "@everyone Yeni video yayında arkadaşlar! Kaçırmayın 🔥\n{link}",
    "son_video_id": "",
    "sil_max_limit": 100,
}

_settings_lock = threading.RLock()


def ayarlari_yukle():
    with _settings_lock:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                for anahtar, deger in default_settings.items():
                    if anahtar not in data:
                        data[anahtar] = deger
                return data
            except Exception:
                logger.exception("Ayarlar okunamadi, varsayilanlar kullanilacak")
        return default_settings.copy()


def ayarlari_kaydet(yeni_ayarlar):
    with _settings_lock:
        gecici = CONFIG_FILE.parent / (CONFIG_FILE.name + ".tmp")
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(yeni_ayarlar, f, ensure_ascii=False, indent=4)
        os.replace(gecici, CONFIG_FILE)


BOT_AYARLARI = ayarlari_yukle()
