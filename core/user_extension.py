import importlib.util
import inspect
import sys

from config import EXTENSION_FILE, logger

MODUL_ADI = "_ynk_user_extension"

# Panel bu sozlugu okuyup uzantinin durumunu gosterir.
DURUM = {"yuklendi": False, "mesaj": "Henüz yüklenmedi"}


async def uzantiyi_yukle(bot):
    """user_extension.py dosyasini yukler ve varsa setup(bot) cagirir.

    Hatalar botu durdurmaz; panelde ve bot.log'da gosterilir.
    """
    DURUM["yuklendi"] = False
    DURUM["mesaj"] = "Yükleniyor..."

    if not EXTENSION_FILE.exists():
        DURUM["mesaj"] = "Uzantı dosyası bulunamadı"
        return False

    try:
        spec = importlib.util.spec_from_file_location(
            MODUL_ADI, EXTENSION_FILE
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Uzantı dosyası okunamadı")

        modul = importlib.util.module_from_spec(spec)
        sys.modules[MODUL_ADI] = modul
        spec.loader.exec_module(modul)

        setup = getattr(modul, "setup", None)
        if setup is not None:
            sonuc = setup(bot)
            if inspect.isawaitable(sonuc):
                await sonuc

        DURUM["yuklendi"] = True
        DURUM["mesaj"] = (
            "Yüklendi (setup bulundu)"
            if setup is not None
            else "Yüklendi (setup fonksiyonu yok)"
        )
        logger.info("Kod uzantısı yüklendi")
        return True
    except Exception as hata:
        logger.exception("Kod uzantısı yüklenemedi")
        DURUM["mesaj"] = f"Hata: {type(hata).__name__}: {hata}"
        return False
