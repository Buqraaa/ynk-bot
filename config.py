import json
import logging
import os
import sys
import threading
from pathlib import Path

import db

# PyInstaller ile derlendiginde ayarlar exe'nin yaninda, sablonlar ise gecici
# bundle klasorunde durur. Gelistirme sirasinda ikisi de proje klasorundedir.
# Sunucu ortamlarinda (Railway, Docker) veri dizini env var ile degistirilebilir.
# Boylece volume mount edilen klasore ayarlar/DB yazilir ve restart'ta kaybolmaz.
# BUNDLE_DIR: kodun/sablonlarin bulundugu dizin (her zaman kod dizini)
if getattr(sys, "frozen", False):
    _code_dir = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", _code_dir))
else:
    _code_dir = Path(__file__).resolve().parent
    BUNDLE_DIR = _code_dir

# APP_DIR: veri dosyalarinin (settings, DB) yazilacagi dizin
# Sunucu ortamlarinda (Railway, Docker) env var ile degistirilebilir
_data_dir_env = os.environ.get("DATA_DIR", "").strip()
if _data_dir_env:
    APP_DIR = Path(_data_dir_env).resolve()
    APP_DIR.mkdir(parents=True, exist_ok=True)
else:
    APP_DIR = _code_dir

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

# DAVE hata ayiklamasi kapali; normal seviyeye dondu

default_settings = {
    "hedef_uye": 1000,
    "guild_id": 0,
    "sayac_kanal": "genel",
    "sayac_kanal_id": 0,
    "giris_mesaji": "Sunucumuza hoş geldin {uye}! 🎉",
    "cikis_mesaji": "{uye} aramızdan ayrıldı.",
    "tavsiye_kanal": "genel",
    "tavsiye_kanal_id": 0,
    "tavsiye_baslik": "✨ Yeni Tavsiye",
    "log_kanal": "genel",
    "log_kanal_id": 0,
    "youtube_kanal": "duyuru",
    "youtube_kanal_id": 0,
    "youtube_channel_id": "",
    "youtube_mesaj": "@everyone Yeni video yayında arkadaşlar! Kaçırmayın 🔥\n{link}",
    "son_video_id": "",
    "hosgeldin_kanal": "",
    "hosgeldin_kanal_id": 0,
    "hosgeldin_baslik": "👋 Hoş geldin!",
    "hosgeldin_mesaj": "Sunucumuza hoş geldin {uye}! 🎉",
    "hosgeldin_renk": "#5865F2",
    "hosgeldin_rol_id": 0,
    "hosgeldin_botlari_dahil": False,
    "hosgeldin_gorsel": True,
    "hosgeldin_gorsel_baslik": "Hoş geldin!",
    "hosgeldin_gorsel_mesaj": "Sunucumuza katıldı",
    "veda_kanal": "",
    "veda_kanal_id": 0,
    "veda_mesaj": "{uye} aramızdan ayrıldı. Görüşürüz!",
    "xp_mesaj": 10,
    "xp_mesaj_cooldown": 60,
    "xp_voice_per_minute": 5,
    "xp_duyuru_kanal": "",
    "xp_duyuru_kanal_id": 0,
    "xp_level_roller": {},
    "cekilis_varsayilan_sure": "1h",
    "cekilis_varsayilan_kazanan": 1,
    "automod_spam": False,
    "automod_spam_limit": 5,
    "automod_link": False,
    "automod_block_invites": True,
    "automod_block_all_links": False,
    "automod_blocked_domains": [],
    "automod_word_filter": False,
    "automod_banned_words": [],
    "automod_caps": False,
    "automod_caps_threshold": 0.7,
    "automod_mention_spam": False,
    "automod_mention_limit": 5,
    "automod_raid": False,
    "automod_raid_limit": 10,
    "automod_aksiyon": "uyari",
    "muzik_varsayilan_ses": 50,
    "muzik_max_kuyruk": 50,
    "ticket_kategori": "Tickets",
    "ticket_panel_kanal": "",
    "ticket_panel_kanal_id": 0,
    "ticket_mesaj": "Destek talebi oluşturmak için aşağıdaki butona tıkla.",
    "ticket_destek_rol_id": 0,
    "ticket_log_kanal": "",
    "ticket_log_kanal_id": 0,
    "sil_max_limit": 100,
    "mod_timeout_varsayilan": 10,
    "mod_uyari_limit": 0,
}

_settings_lock = threading.RLock()


def ayarlari_yukle():
    with _settings_lock:
        try:
            data = db.ayar_yukle()
        except Exception:
            logger.exception("DB ayarlar okunamadi, varsayilanlar kullanilacak")
            data = {}
        if not data:
            data = default_settings.copy()
        else:
            for anahtar, deger in default_settings.items():
                if anahtar not in data:
                    data[anahtar] = deger
        # Geriye donuk uyumluluk: settings.json'a da yedek yaz.
        try:
            gecici = CONFIG_FILE.parent / (CONFIG_FILE.name + ".tmp")
            with open(gecici, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            os.replace(gecici, CONFIG_FILE)
        except Exception:
            pass
        return data


def ayarlari_kaydet(yeni_ayarlar):
    with _settings_lock:
        try:
            db.ayar_kaydet(yeni_ayarlar)
        except Exception:
            logger.exception("DB ayarlar kaydedilemedi")
        # Geriye donuk uyumluluk: JSON yedegi de tut.
        try:
            gecici = CONFIG_FILE.parent / (CONFIG_FILE.name + ".tmp")
            with open(gecici, "w", encoding="utf-8") as f:
                json.dump(yeni_ayarlar, f, ensure_ascii=False, indent=4)
            os.replace(gecici, CONFIG_FILE)
        except Exception:
            logger.exception("Ayarlar JSON'a kaydedilemedi")


BOT_AYARLARI = ayarlari_yukle()
