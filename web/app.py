import asyncio
import os
import re
import threading

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config import (
    BOT_AYARLARI,
    BUNDLE_DIR,
    EXTENSION_FILE,
    ayarlari_kaydet,
    logger,
)
from core.manager import bot_manager
from core.user_extension import DURUM as UZANTI_DURUMU
from utils import ayarli_sunucu, kanal_bul

app = FastAPI()
templates = Jinja2Templates(directory=str(BUNDLE_DIR / "web" / "templates"))


def sunucu_kanallarini_getir():
    kanallar = []
    try:
        guild = ayarli_sunucu(bot_manager.bot)
        if guild is not None:
            kanallar = [channel.name for channel in guild.text_channels]
    except Exception:
        logger.exception("Kanal çekme hatası")

    if not kanallar:
        kanallar = [
            BOT_AYARLARI["sayac_kanal"],
            BOT_AYARLARI["tavsiye_kanal"],
            BOT_AYARLARI["log_kanal"],
            BOT_AYARLARI["youtube_kanal"],
        ]
    return sorted(set(kanallar))


def sunucu_rollerini_getir():
    """Otomatik rol menusu icin botun verebilecegi rolleri listeler."""
    roller = []
    try:
        guild = ayarli_sunucu(bot_manager.bot)
        if guild is not None:
            bot_uyesi = guild.me
            for rol in reversed(guild.roles):
                if rol.is_default() or rol.managed:
                    continue
                if bot_uyesi is not None and rol >= bot_uyesi.top_role:
                    continue
                roller.append({"id": rol.id, "name": rol.name})
    except Exception:
        logger.exception("Rol çekme hatası")
    return roller


def _kanal_id_guncelle(anahtar, kanal_adi):
    """Kanal adi degistiyse ID'yi sifirlar, bot calisiyorsa yenisini bulur."""
    if not kanal_adi:
        BOT_AYARLARI[f"{anahtar}_id"] = 0
        return

    if BOT_AYARLARI.get(anahtar, "") != kanal_adi:
        BOT_AYARLARI[f"{anahtar}_id"] = 0

    guild = ayarli_sunucu(bot_manager.bot)
    if guild is None:
        return

    channel = kanal_bul(guild, 0, kanal_adi)
    if channel is not None:
        BOT_AYARLARI[f"{anahtar}_id"] = channel.id
        logger.info(
            "Kanal ID guncellendi: %s -> #%s (%s)",
            anahtar,
            channel.name,
            channel.id,
        )


def _uzanti_icerigi():
    if not os.path.exists(EXTENSION_FILE):
        with open(EXTENSION_FILE, "w", encoding="utf-8") as f:
            f.write(
                "# Buraya dilediğin ek Python kodlarını yazabilirsin.\n"
                "# Ornek:\n"
                "# async def setup(bot):\n"
                "#     ...\n"
            )
    with open(EXTENSION_FILE, "r", encoding="utf-8") as f:
        return f.read()


def _ayarlari_kaydet():
    try:
        ayarlari_kaydet(BOT_AYARLARI)
    except Exception:
        logger.exception("Ayarlar kaydedilemedi")


@app.get("/", response_class=HTMLResponse)
def panel_ana_sayfa(request: Request):
    durum = bot_manager.status
    durum_renk = "#10b981" if durum == "Aktif (Çalışıyor)" else "#ef4444"

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "kanallar": sunucu_kanallarini_getir(),
            "roller": sunucu_rollerini_getir(),
            "ayarlar": BOT_AYARLARI,
            "bot_durumu": durum,
            "durum_renk": durum_renk,
            "kod_icerigi": _uzanti_icerigi(),
            "uzanti_durumu": UZANTI_DURUMU["mesaj"],
            "uzanti_renk": (
                "#10b981" if UZANTI_DURUMU["yuklendi"] else "#f59e0b"
            ),
        },
    )


@app.get("/bot-ac", response_class=RedirectResponse)
def bot_ac():
    bot_manager.start()
    return RedirectResponse(url="/", status_code=303)


@app.get("/bot-reset", response_class=RedirectResponse)
def bot_reset():
    threading.Thread(target=bot_manager.restart, daemon=True).start()
    return RedirectResponse(url="/", status_code=303)


@app.get("/bot-kapat", response_class=RedirectResponse)
def bot_kapat():
    threading.Thread(target=bot_manager.stop, daemon=True).start()
    return RedirectResponse(url="/", status_code=303)


@app.post("/guncelle-sayac", response_class=RedirectResponse)
def guncelle_sayac(
    hedef: int = Form(...),
    kanal: str = Form(...),
    giris: str = Form(...),
    cikis: str = Form(...),
):
    BOT_AYARLARI["hedef_uye"] = hedef
    _kanal_id_guncelle("sayac_kanal", kanal)
    BOT_AYARLARI["sayac_kanal"] = kanal
    BOT_AYARLARI["giris_mesaji"] = giris
    BOT_AYARLARI["cikis_mesaji"] = cikis
    _ayarlari_kaydet()
    return RedirectResponse(url="/", status_code=303)


@app.post("/guncelle-karsilama", response_class=RedirectResponse)
def guncelle_karsilama(
    hosgeldin_kanal: str = Form(""),
    hosgeldin_baslik: str = Form(""),
    hosgeldin_mesaj: str = Form(""),
    hosgeldin_renk: str = Form("#5865F2"),
    hosgeldin_rol_id: int = Form(0),
    veda_kanal: str = Form(""),
    veda_mesaj: str = Form(""),
):
    _kanal_id_guncelle("hosgeldin_kanal", hosgeldin_kanal)
    BOT_AYARLARI["hosgeldin_kanal"] = hosgeldin_kanal

    baslik = hosgeldin_baslik.strip() or "👋 Hoş geldin!"
    mesaj = hosgeldin_mesaj.strip() or "Sunucumuza hoş geldin {uye}! 🎉"
    BOT_AYARLARI["hosgeldin_baslik"] = baslik
    BOT_AYARLARI["hosgeldin_mesaj"] = mesaj

    renk = (hosgeldin_renk or "").strip()
    if not re.fullmatch(r"#?[0-9a-fA-F]{6}", renk):
        renk = "#5865F2"
    elif not renk.startswith("#"):
        renk = "#" + renk
    BOT_AYARLARI["hosgeldin_renk"] = renk.upper()

    BOT_AYARLARI["hosgeldin_rol_id"] = max(0, int(hosgeldin_rol_id))

    _kanal_id_guncelle("veda_kanal", veda_kanal)
    BOT_AYARLARI["veda_kanal"] = veda_kanal
    BOT_AYARLARI["veda_mesaj"] = (
        veda_mesaj.strip() or "{uye} aramızdan ayrıldı. Görüşürüz!"
    )

    _ayarlari_kaydet()
    return RedirectResponse(url="/", status_code=303)


@app.post("/guncelle-tavsiye", response_class=RedirectResponse)
def guncelle_tavsiye(kanal: str = Form(...), baslik: str = Form(...)):
    _kanal_id_guncelle("tavsiye_kanal", kanal)
    BOT_AYARLARI["tavsiye_kanal"] = kanal
    BOT_AYARLARI["tavsiye_baslik"] = baslik
    _ayarlari_kaydet()
    return RedirectResponse(url="/", status_code=303)


@app.post("/guncelle-log", response_class=RedirectResponse)
def guncelle_log(log_kanal: str = Form(...)):
    _kanal_id_guncelle("log_kanal", log_kanal)
    BOT_AYARLARI["log_kanal"] = log_kanal
    _ayarlari_kaydet()
    return RedirectResponse(url="/", status_code=303)


@app.post("/guncelle-youtube", response_class=RedirectResponse)
def guncelle_youtube(
    youtube_channel_id: str = Form(""),
    youtube_kanal: str = Form(...),
    youtube_mesaj: str = Form(...),
):
    eski_giris = BOT_AYARLARI.get("youtube_channel_id", "")
    yeni_giris = youtube_channel_id.strip()
    if eski_giris != yeni_giris:
        BOT_AYARLARI["son_video_id"] = ""

    BOT_AYARLARI["youtube_channel_id"] = yeni_giris
    _kanal_id_guncelle("youtube_kanal", youtube_kanal)
    BOT_AYARLARI["youtube_kanal"] = youtube_kanal
    BOT_AYARLARI["youtube_mesaj"] = youtube_mesaj
    _ayarlari_kaydet()
    return RedirectResponse(url="/", status_code=303)


@app.post("/guncelle-komutlar", response_class=RedirectResponse)
def guncelle_komutlar(sil_max_limit: int = Form(...)):
    BOT_AYARLARI["sil_max_limit"] = max(1, min(100, sil_max_limit))
    _ayarlari_kaydet()
    return RedirectResponse(url="/", status_code=303)


@app.post("/duyuru-gonder", response_class=RedirectResponse)
def duyuru_gonder(
    hedef_kanal: str = Form(...), duyuru_mesaji: str = Form(...)
):
    bot = bot_manager.bot
    loop = bot_manager.loop

    if bot and loop and not bot.is_closed() and bot.guilds:
        guild = ayarli_sunucu(bot)

        async def mesaj_at():
            channel = kanal_bul(guild, 0, hedef_kanal)
            if channel:
                await channel.send(duyuru_mesaji)
            else:
                logger.warning("Duyuru kanalı bulunamadı: #%s", hedef_kanal)

        try:
            asyncio.run_coroutine_threadsafe(mesaj_at(), loop)
        except Exception:
            logger.exception("Canlı duyuru hatası")
    else:
        logger.warning("Duyuru gönderilemedi: bot çalışmıyor")

    return RedirectResponse(url="/", status_code=303)


@app.post("/guncelle-kod", response_class=RedirectResponse)
def guncelle_kod(yeni_kod: str = Form(...)):
    try:
        with open(EXTENSION_FILE, "w", encoding="utf-8") as f:
            f.write(yeni_kod)
        UZANTI_DURUMU["yuklendi"] = False
        UZANTI_DURUMU["mesaj"] = "Kaydedildi; bot yeniden başlatılıyor..."
    except Exception:
        logger.exception("Kod kaydetme hatası")
        UZANTI_DURUMU["mesaj"] = "Kod kaydedilemedi (bot.log'a bak)"
    return RedirectResponse(url="/bot-reset", status_code=303)


def fastapi_baslat():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
