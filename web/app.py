import asyncio
import os
import re
import threading

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config import (
    APP_DIR,
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
            "bot_aktif": durum == "Aktif (Çalışıyor)",
            "durum_renk": durum_renk,
            "kod_icerigi": _uzanti_icerigi(),
            "uzanti_durumu": UZANTI_DURUMU["mesaj"],
            "uzanti_renk": (
                "#10b981" if UZANTI_DURUMU["yuklendi"] else "#f59e0b"
            ),
        },
    )


Gorsel_UZANTILAR = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def profil_resmini_bul():
    try:
        for dosya in sorted(APP_DIR.iterdir()):
            if dosya.is_file() and dosya.suffix.lower() in Gorsel_UZANTILAR:
                return dosya
    except Exception:
        logger.exception("Profil resmi aranamadi")
    return None


@app.get("/avatar")
def avatar():
    from fastapi.responses import FileResponse, Response

    dosya = profil_resmini_bul()
    if dosya is None:
        return Response(status_code=404)
    return FileResponse(str(dosya))


@app.get("/api/durum")
def api_durum():
    bot = bot_manager.bot
    return {
        "durum": bot_manager.status,
        "hazir": bool(
            bot
            and bot.is_ready()
            and not bot.is_closed()
            and bot.guilds
        ),
    }


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
    return RedirectResponse(url="/?tab=sayac", status_code=303)


@app.post("/guncelle-karsilama", response_class=RedirectResponse)
def guncelle_karsilama(
    hosgeldin_kanal: str = Form(""),
    hosgeldin_baslik: str = Form(""),
    hosgeldin_mesaj: str = Form(""),
    hosgeldin_renk: str = Form("#5865F2"),
    hosgeldin_rol_id: int = Form(0),
    hosgeldin_botlari_dahil: int = Form(0),
    hosgeldin_gorsel: int = Form(0),
    hosgeldin_gorsel_baslik: str = Form(""),
    hosgeldin_gorsel_mesaj: str = Form(""),
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
    BOT_AYARLARI["hosgeldin_botlari_dahil"] = bool(
        hosgeldin_botlari_dahil
    )

    BOT_AYARLARI["hosgeldin_gorsel"] = bool(hosgeldin_gorsel)
    BOT_AYARLARI["hosgeldin_gorsel_baslik"] = (
        hosgeldin_gorsel_baslik.strip() or "Hoş geldin!"
    )
    BOT_AYARLARI["hosgeldin_gorsel_mesaj"] = (
        hosgeldin_gorsel_mesaj.strip() or "Sunucumuza katıldı"
    )

    _kanal_id_guncelle("veda_kanal", veda_kanal)
    BOT_AYARLARI["veda_kanal"] = veda_kanal
    BOT_AYARLARI["veda_mesaj"] = (
        veda_mesaj.strip() or "{uye} aramızdan ayrıldı. Görüşürüz!"
    )

    _ayarlari_kaydet()
    return RedirectResponse(url="/?tab=karsilama", status_code=303)


@app.post("/karsilama-test", response_class=RedirectResponse)
def karsilama_test():
    bot = bot_manager.bot
    loop = bot_manager.loop

    if not (bot and loop and not bot.is_closed() and bot.guilds):
        logger.warning("Karşılama testi: bot çalışmıyor")
        return RedirectResponse(url="/?tab=karsilama", status_code=303)

    guild = ayarli_sunucu(bot)

    async def gonder():
        from cogs.karsilama import test_mesaji_gonder

        await test_mesaji_gonder(bot, guild)

    try:
        future = asyncio.run_coroutine_threadsafe(gonder(), loop)
        future.result(10)
    except Exception:
        logger.exception("Karşılama test mesajı gönderilemedi")

    return RedirectResponse(url="/?tab=karsilama", status_code=303)


@app.post("/guncelle-tavsiye", response_class=RedirectResponse)
def guncelle_tavsiye(kanal: str = Form(...), baslik: str = Form(...)):
    _kanal_id_guncelle("tavsiye_kanal", kanal)
    BOT_AYARLARI["tavsiye_kanal"] = kanal
    BOT_AYARLARI["tavsiye_baslik"] = baslik
    _ayarlari_kaydet()
    return RedirectResponse(url="/?tab=tavsiye", status_code=303)


@app.post("/guncelle-log", response_class=RedirectResponse)
def guncelle_log(log_kanal: str = Form(...)):
    _kanal_id_guncelle("log_kanal", log_kanal)
    BOT_AYARLARI["log_kanal"] = log_kanal
    _ayarlari_kaydet()
    return RedirectResponse(url="/?tab=log", status_code=303)


@app.post("/ticket-panel-gonder", response_class=RedirectResponse)
def ticket_panel_gonder_route(
    ticket_panel_kanal: str = Form(""),
    ticket_kategori: str = Form("Tickets"),
    ticket_mesaj: str = Form(""),
    ticket_destek_rol_id: int = Form(0),
    ticket_log_kanal: str = Form(""),
):
    _kanal_id_guncelle("ticket_panel_kanal", ticket_panel_kanal)
    BOT_AYARLARI["ticket_panel_kanal"] = ticket_panel_kanal
    BOT_AYARLARI["ticket_kategori"] = ticket_kategori.strip() or "Tickets"
    BOT_AYARLARI["ticket_mesaj"] = ticket_mesaj.strip() or "Destek talebi oluşturmak için aşağıdaki butona tıkla."
    BOT_AYARLARI["ticket_destek_rol_id"] = int(ticket_destek_rol_id or 0)
    _kanal_id_guncelle("ticket_log_kanal", ticket_log_kanal)
    BOT_AYARLARI["ticket_log_kanal"] = ticket_log_kanal
    _ayarlari_kaydet()

    bot = bot_manager.bot
    loop = bot_manager.loop
    if not (bot and loop and not bot.is_closed() and bot.guilds):
        logger.warning("Ticket paneli gönderilemedi: bot çalışmıyor")
        return RedirectResponse(url="/?tab=ticket", status_code=303)

    guild = ayarli_sunucu(bot)

    async def gonder():
        from cogs.tickets import ticket_panel_gonder
        await ticket_panel_gonder(bot, guild)

    try:
        future = asyncio.run_coroutine_threadsafe(gonder(), loop)
        future.result(15)
    except Exception:
        logger.exception("Ticket paneli gönderilemedi")

    return RedirectResponse(url="/?tab=ticket", status_code=303)


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
    return RedirectResponse(url="/?tab=youtube", status_code=303)


@app.post("/guncelle-muzik", response_class=RedirectResponse)
def guncelle_muzik(
    muzik_varsayilan_ses: int = Form(50),
    muzik_max_kuyruk: int = Form(50),
):
    BOT_AYARLARI["muzik_varsayilan_ses"] = max(0, min(100, int(muzik_varsayilan_ses)))
    BOT_AYARLARI["muzik_max_kuyruk"] = max(1, min(200, int(muzik_max_kuyruk)))
    _ayarlari_kaydet()
    return RedirectResponse(url="/?tab=muzik", status_code=303)


@app.post("/guncelle-xp", response_class=RedirectResponse)
def guncelle_xp(
    xp_mesaj: int = Form(10),
    xp_mesaj_cooldown: int = Form(60),
    xp_voice_per_minute: int = Form(5),
    xp_duyuru_kanal: str = Form(""),
):
    BOT_AYARLARI["xp_mesaj"] = max(1, min(100, int(xp_mesaj)))
    BOT_AYARLARI["xp_mesaj_cooldown"] = max(10, min(3600, int(xp_mesaj_cooldown)))
    BOT_AYARLARI["xp_voice_per_minute"] = max(1, min(50, int(xp_voice_per_minute)))
    _kanal_id_guncelle("xp_duyuru_kanal", xp_duyuru_kanal)
    BOT_AYARLARI["xp_duyuru_kanal"] = xp_duyuru_kanal
    _ayarlari_kaydet()
    return RedirectResponse(url="/?tab=xp", status_code=303)


@app.post("/guncelle-automod", response_class=RedirectResponse)
def guncelle_automod(
    automod_spam: int = Form(0),
    automod_spam_limit: int = Form(5),
    automod_link: int = Form(0),
    automod_block_invites: int = Form(0),
    automod_block_all_links: int = Form(0),
    automod_blocked_domains: str = Form(""),
    automod_word_filter: int = Form(0),
    automod_banned_words: str = Form(""),
    automod_caps: int = Form(0),
    automod_caps_threshold: float = Form(0.7),
    automod_mention_spam: int = Form(0),
    automod_mention_limit: int = Form(5),
    automod_raid: int = Form(0),
    automod_raid_limit: int = Form(10),
    automod_aksiyon: str = Form("uyari"),
):
    BOT_AYARLARI["automod_spam"] = bool(automod_spam)
    BOT_AYARLARI["automod_spam_limit"] = max(2, min(20, int(automod_spam_limit)))
    BOT_AYARLARI["automod_link"] = bool(automod_link)
    BOT_AYARLARI["automod_block_invites"] = bool(automod_block_invites)
    BOT_AYARLARI["automod_block_all_links"] = bool(automod_block_all_links)
    BOT_AYARLARI["automod_blocked_domains"] = [d.strip() for d in automod_blocked_domains.split(",") if d.strip()]
    BOT_AYARLARI["automod_word_filter"] = bool(automod_word_filter)
    BOT_AYARLARI["automod_banned_words"] = [w.strip() for w in automod_banned_words.split(",") if w.strip()]
    BOT_AYARLARI["automod_caps"] = bool(automod_caps)
    BOT_AYARLARI["automod_caps_threshold"] = max(0.5, min(1.0, float(automod_caps_threshold)))
    BOT_AYARLARI["automod_mention_spam"] = bool(automod_mention_spam)
    BOT_AYARLARI["automod_mention_limit"] = max(2, min(20, int(automod_mention_limit)))
    BOT_AYARLARI["automod_raid"] = bool(automod_raid)
    BOT_AYARLARI["automod_raid_limit"] = max(3, min(50, int(automod_raid_limit)))
    if automod_aksiyon in ("uyari", "sustur", "ban"):
        BOT_AYARLARI["automod_aksiyon"] = automod_aksiyon
    _ayarlari_kaydet()
    return RedirectResponse(url="/?tab=automod", status_code=303)


@app.post("/guncelle-komutlar", response_class=RedirectResponse)
def guncelle_komutlar(sil_max_limit: int = Form(...)):
    BOT_AYARLARI["sil_max_limit"] = max(1, min(100, sil_max_limit))
    _ayarlari_kaydet()
    return RedirectResponse(url="/?tab=komutlar", status_code=303)


@app.post("/guncelle-moderasyon", response_class=RedirectResponse)
def guncelle_moderasyon(
    mod_timeout_varsayilan: int = Form(10),
    mod_uyari_limit: int = Form(0),
):
    BOT_AYARLARI["mod_timeout_varsayilan"] = max(1, min(40320, int(mod_timeout_varsayilan)))
    BOT_AYARLARI["mod_uyari_limit"] = max(0, min(100, int(mod_uyari_limit)))
    _ayarlari_kaydet()
    return RedirectResponse(url="/?tab=komutlar", status_code=303)


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

    return RedirectResponse(url="/?tab=duyuru", status_code=303)


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


def fastapi_baslat(host="127.0.0.1", port=8000):
    uvicorn.run(app, host=host, port=port, log_level="warning")
