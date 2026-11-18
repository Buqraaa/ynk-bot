import asyncio
import os
import shutil
from collections import deque

import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_AYARLARI, logger

def _ffmpeg_yolu_bul():
    yol = shutil.which("ffmpeg")
    if yol:
        return yol
    # Yaygin kurulum konumlari (winget, choco, manuel)
    adaylar = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
    ]
    # winget alias konumu
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        adaylar.append(os.path.join(local, "Microsoft", "WinGet", "Links", "ffmpeg.exe"))
        # winget paket klasorunde ara
        pkg_root = os.path.join(local, "Microsoft", "WinGet", "Packages")
        if os.path.isdir(pkg_root):
            for root, dirs, files in os.walk(pkg_root):
                if "ffmpeg.exe" in files:
                    adaylar.append(os.path.join(root, "ffmpeg.exe"))
    for aday in adaylar:
        if os.path.isfile(aday):
            return aday
    return "ffmpeg"


FFMPEG_PATH = _ffmpeg_yolu_bul()

FFMPEG_OPTIONS = {
    "before_options": '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -headers "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)"',
    "options": "-vn",
}

YTDLP_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "remote_components": ["ejs:github"],
}

import base64
import tempfile

# Cookies dosyasi (Railway'de /app/data/cookies.txt olarak mount edilebilir)
_COOKIES_CACHE = None


def _cookies_dosyasi():
    global _COOKIES_CACHE
    if _COOKIES_CACHE is not None:
        return _COOKIES_CACHE

    # 1. Dosya olarak ara
    from config import APP_DIR, BUNDLE_DIR

    for base in (APP_DIR, BUNDLE_DIR):
        for ad in ("cookies.txt", "youtube_cookies.txt"):
            yol = base / ad
            if yol.exists():
                _COOKIES_CACHE = str(yol)
                return _COOKIES_CACHE

    # 2. Environment variable'dan (base64) olustur
    b64 = os.environ.get("YOUTUBE_COOKIES_B64", "").strip()
    if b64:
        try:
            icerik = base64.b64decode(b64)
            if len(icerik) < 200:
                logger.warning("YouTube cookies cok kucuk (%d byte), kullanilmiyor", len(icerik))
                return None
            # Netscape header eksikse ekle (yt-dlp format kontrolu)
            text = icerik.decode("utf-8", errors="replace")
            if "Netscape HTTP Cookie File" not in text:
                text = "# Netscape HTTP Cookie File\\n# https://curl.haxx.se/rfc/cookie_spec.html\\n# This is a generated file! Do not edit.\\n" + text
                icerik = text.encode("utf-8")
            fd, yol = tempfile.mkstemp(suffix=".txt", prefix="yt_cookies_")
            with os.fdopen(fd, "wb") as f:
                f.write(icerik)
            _COOKIES_CACHE = yol
            logger.info("YouTube cookies env var'dan yuklendi (%d byte)", len(icerik))
            return _COOKIES_CACHE
        except Exception as e:
            logger.warning("YouTube cookies decode hatasi: %s", e)

    _COOKIES_CACHE = None
    return None




class Track:
    def __init__(self, title, url, webpage_url, duration):
        self.title = title
        self.url = url
        self.webpage_url = webpage_url
        self.duration = duration


def _extract(query):
    import yt_dlp

    # 1. Arama: web client (search destekler)
    import time as _time
    info = None
    for _deneme in range(3):
        try:
            opts_search = dict(YTDLP_OPTIONS)
            cookies = _cookies_dosyasi()
            if cookies:
                opts_search["cookiefile"] = cookies
            opts_search.pop("format", None)
            opts_search["extract_flat"] = "in_playlist"
            opts_search["skip_download"] = True
            opts_search["sleep_requests"] = 1
            with yt_dlp.YoutubeDL(opts_search) as ydl:
                info = ydl.extract_info(query, download=False)
            break
        except Exception as e:
            err = str(e)
            if "Sign in" in err or "bot" in err.lower():
                if _deneme < 2:
                    logger.warning("Muzik: arama deneme %d basarisiz, tekrar deneniyor...", _deneme + 1)
                    _time.sleep(2)
                    continue
            raise

    if info is None:
        raise RuntimeError("Arama basarisiz")

    if "entries" in info and info.get("entries"):
        info = info["entries"][0]
    video_id = info.get("id") or info.get("url", "").split("v=")[-1].split("&")[0]
    if not video_id or video_id == query:
        url = info.get("url", "")
        if "v=" in url:
            video_id = url.split("v=")[-1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[-1].split("?")[0]
    video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else (info.get("webpage_url") or info.get("url"))
    title = info.get("title", "Bilinmeyen")
    duration = info.get("duration", 0) or 0

    # Arama ve cekim arasinda kisa bekleme (rate limiting onleme)
    import time as _t
    _t.sleep(1)

    # 2. Ses URL'si cekme: sirayla farkli client'lar dene (bot engelini asar)
    clients = [
        ("android", {"player_client": ["android"], "User-Agent": "com.google.android.youtube/19.09.37 (Linux; U; Android 10) gzip"}),
        ("ios", {"player_client": ["ios"], "User-Agent": "com.google.ios.youtube/19.09.37 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)"}),
        ("mweb", {"player_client": ["mweb"], "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36"}),
        ("web", {"player_client": ["web"], "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}),
    ]

    cookies = _cookies_dosyasi()
    if cookies:
        try:
            with open(cookies, "r") as f:
                first_lines = f.read(200)
            logger.info("Muzik: cookies dosyasi okundu, boyut=%s, ilk satirlar: %s", len(first_lines), first_lines[:100].replace(chr(10), " "))
        except Exception as e:
            logger.warning("Muzik: cookies dosyasi okunamadi: %s", e)

    # Cookies ile ve cookies'siz dene (cookies bozuksa cookies'siz calisabilir)
    cookie_variants = [cookies] if cookies else [None]
    if cookies:
        cookie_variants.append(None)  # cookies'siz fallback

    format_strings = ["bestaudio/best", "best", "worst"]
    for cookie_val in cookie_variants:
        for client_name, client_opts in clients:
            for fmt_str in format_strings:
                try:
                    opts = {
                        "quiet": True,
                        "no_warnings": True,
                        "source_address": "0.0.0.0",
                        "format": fmt_str,
                        "remote_components": ["ejs:github"],
                        "extractor_args": {"youtube": {"player_client": [client_opts["player_client"][0]]}},
                        "http_headers": {"User-Agent": client_opts["User-Agent"]},
                    }
                    if cookie_val:
                        opts["cookiefile"] = cookie_val
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info2 = ydl.extract_info(video_url, download=False)
                        audio_url = info2.get("url")
                        if not audio_url and info2.get("formats"):
                            for fmt in reversed(info2["formats"]):
                                if fmt.get("url"):
                                    audio_url = fmt["url"]
                                    break
                        if audio_url:
                            logger.info("Muzik: %s/%s%s ile ses URL'si alindi", client_name, fmt_str, " (cookies)" if cookie_val else " (cookies'siz)")
                            return Track(
                                title=title,
                                url=audio_url,
                                webpage_url=video_url,
                                duration=duration,
                            )
                except Exception as e:
                    err = str(e)[:150]
                    logger.warning("Muzik: %s client basarisiz: %s", client_name, err)
                    continue

    # Son care: varsayilan ile dene
    opts_web = dict(YTDLP_OPTIONS)
    cookies = _cookies_dosyasi()
    if cookies:
        opts_web["cookiefile"] = cookies
    with yt_dlp.YoutubeDL(opts_web) as ydl:
        info3 = ydl.extract_info(video_url, download=False)
        audio_url = info3.get("url")
        if not audio_url and info3.get("formats"):
            for fmt in reversed(info3["formats"]):
                if fmt.get("url"):
                    audio_url = fmt["url"]
                    break
        return Track(
            title=title,
            url=audio_url,
            webpage_url=video_url,
            duration=duration,
        )


class GuildPlayer:
    def __init__(self):
        self.queue = deque()
        self.current = None
        self.volume = 0.5
        self.loop = False
        self.voice_client = None


_players = {}


def get_player(guild_id):
    if guild_id not in _players:
        _players[guild_id] = GuildPlayer()
    return _players[guild_id]


class Muzik(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _ses_kanali(self, interaction):
        if interaction.user.voice and interaction.user.voice.channel:
            return interaction.user.voice.channel
        return None

    async def _baglan(self, interaction, kanal):
        player = get_player(interaction.guild.id)
        if player.voice_client and player.voice_client.is_connected():
            if player.voice_client.channel != kanal:
                await player.voice_client.move_to(kanal)
        else:
            player.voice_client = await kanal.connect()
        # DAVE (E2EE) oturumunu hazir hale getir.
        # discord.py 2.7.1, transition 0 icin execute_transition cagirmiyor;
        # bu yuzden manuel olarak prepare+execute yapiyoruz.
        for i in range(30):
            try:
                conn = player.voice_client._connection
                if conn.can_encrypt:
                    break
                if i == 3 and conn.dave_session is not None and not conn.dave_session.ready:
                    try:
                        conn.dave_session.prepare_transition(0, 1)
                        conn.dave_session.execute_transition(0)
                    except Exception as e:
                        logger.warning("Muzik: DAVE transition hatasi: %s", e)
            except Exception:
                pass
            await asyncio.sleep(0.2)
        try:
            conn = player.voice_client._connection
            logger.info("Muzik: DAVE can_encrypt=%s", conn.can_encrypt)
        except Exception as e:
            logger.exception("DAVE log hatasi: %s", e)
        try:
            conn = player.voice_client._connection
            logger.info("Muzik: DAVE SONUC protocol_version=%s, can_encrypt=%s, mode=%s", conn.dave_protocol_version, conn.can_encrypt, player.voice_client.mode)
        except Exception as e:
            logger.exception("DAVE log hatasi: %s", e)
        return player

    async def _oynat(self, guild, player):
        if player.loop and player.current is not None:
            track = player.current
        else:
            if not player.queue:
                player.current = None
                logger.info("Muzik: kuyruk bos, oynatma bitti")
                return
            track = player.queue.popleft()

        player.current = track
        logger.info("Muzik: oynatiliyor -> %s", track.title)

        def after(err):
            try:
                stderr_file.flush()
                stderr_file.seek(0)
                se = stderr_file.read()
                if se.strip():
                    logger.warning("FFmpeg stderr: %s", se.strip()[:500])
            except Exception:
                pass
            if err:
                logger.error("Muzik oynatma hatasi: %s", err)
            else:
                logger.info("Muzik: parça bitti")
            try:
                asyncio.run_coroutine_threadsafe(self._sonraki(guild, player), self.bot.loop)
            except Exception:
                logger.exception("Sonraki parcaya gecilemedi")

        import subprocess
        stderr_file = open(os.path.join(os.path.dirname(__file__), "..", "ffmpeg_stderr.log"), "w", encoding="utf-8", errors="replace")
        try:
            source = discord.FFmpegPCMAudio(track.url, executable=FFMPEG_PATH, stderr=stderr_file, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=player.volume)
            player.voice_client.play(source, after=after)
            import time
            time.sleep(0.5)
            logger.info("Muzik: play() cagirildi, is_playing=%s, is_connected=%s", player.voice_client.is_playing(), player.voice_client.is_connected())
        except Exception as e:
            logger.exception("FFmpeg baslatilamadi: %s", e)
            await self._sonraki(guild, player)
        finally:
            # dosya handle'i acik birak; process bittiginde okunacak
            pass

    async def _sonraki(self, guild, player):
        if player.loop and player.current is not None:
            player.queue.appendleft(player.current)
        await self._oynat(guild, player)

    @app_commands.command(name="cal", description="Bir şarkı çalar (YouTube araması veya link)")
    @app_commands.describe(sorgu="Şarkı adı veya YouTube linki")
    async def cal(self, interaction: discord.Interaction, sorgu: str):
        kanal = self._ses_kanali(interaction)
        if kanal is None:
            await interaction.response.send_message("❌ Önce bir ses kanalına katıl.", ephemeral=True)
            return

        await interaction.response.defer()
        player = await self._baglan(interaction, kanal)

        try:
            track = await asyncio.get_event_loop().run_in_executor(None, _extract, sorgu)
        except Exception as e:
            logger.exception("Sarki bulunamadi")
            await interaction.followup.send(f"❌ Şarkı bulunamadı: {e}", ephemeral=True)
            return

        player.queue.append(track)
        if not (player.voice_client.is_playing() or player.voice_client.is_paused()):
            await self._oynat(interaction.guild, player)
            await interaction.followup.send(f"▶️ Çalınıyor: **{track.title}**")
        else:
            await interaction.followup.send(f"➕ Kuyruğa eklendi: **{track.title}**")

    @app_commands.command(name="duraklat", description="Çalan şarkıyı duraklatır")
    async def duraklat(self, interaction: discord.Interaction):
        player = get_player(interaction.guild.id)
        if player.voice_client and player.voice_client.is_playing():
            player.voice_client.pause()
            await interaction.response.send_message("⏸️ Duraklatıldı.")
        else:
            await interaction.response.send_message("❌ Çalan bir şey yok.", ephemeral=True)

    @app_commands.command(name="devam", description="Duraklatılan şarkıyı devam ettirir")
    async def devam(self, interaction: discord.Interaction):
        player = get_player(interaction.guild.id)
        if player.voice_client and player.voice_client.is_paused():
            player.voice_client.resume()
            await interaction.response.send_message("▶️ Devam ediyor.")
        else:
            await interaction.response.send_message("❌ Duraklatılmış bir şey yok.", ephemeral=True)

    @app_commands.command(name="atla", description="Şarkıyı atlar")
    async def atla(self, interaction: discord.Interaction):
        player = get_player(interaction.guild.id)
        if player.voice_client and (player.voice_client.is_playing() or player.voice_client.is_paused()):
            player.voice_client.stop()
            await interaction.response.send_message("⏭️ Atlandı.")
        else:
            await interaction.response.send_message("❌ Çalan bir şey yok.", ephemeral=True)

    @app_commands.command(name="durdur", description="Müziği durdurur ve kuyruğu temizler")
    async def durdur(self, interaction: discord.Interaction):
        player = get_player(interaction.guild.id)
        player.queue.clear()
        player.current = None
        player.loop = False
        if player.voice_client:
            player.voice_client.stop()
        await interaction.response.send_message("⏹️ Durduruldu, kuyruk temizlendi.")

    @app_commands.command(name="kuyruk", description="Müzik kuyruğunu gösterir")
    async def kuyruk(self, interaction: discord.Interaction):
        player = get_player(interaction.guild.id)
        if not player.current and not player.queue:
            await interaction.response.send_message("Kuyruk boş.", ephemeral=True)
            return
        satirlar = []
        if player.current:
            satirlar.append(f"▶️ **{player.current.title}** (şu an)")
        for i, t in enumerate(player.queue, 1):
            satirlar.append(f"{i}. {t.title}")
        await interaction.response.send_message("\n".join(satirlar))

    @app_commands.command(name="ses", description="Ses seviyesini ayarlar (0-100)")
    @app_commands.describe(seviye="Ses seviyesi (0-100)")
    async def ses(self, interaction: discord.Interaction, seviye: int):
        player = get_player(interaction.guild.id)
        seviye = max(0, min(100, seviye))
        player.volume = seviye / 100
        if player.voice_client and player.voice_client.source:
            player.voice_client.source.volume = player.volume
        await interaction.response.send_message(f"🔊 Ses: {seviye}%")

    @app_commands.command(name="döngü", description="Döngü modunu açar/kapatır")
    async def dongu(self, interaction: discord.Interaction):
        player = get_player(interaction.guild.id)
        player.loop = not player.loop
        await interaction.response.send_message(f"🔁 Döngü: {'açık' if player.loop else 'kapalı'}")

    @app_commands.command(name="cik", description="Ses kanalından ayrılır")
    async def cik(self, interaction: discord.Interaction):
        player = get_player(interaction.guild.id)
        if player.voice_client:
            player.queue.clear()
            player.current = None
            await player.voice_client.disconnect()
            player.voice_client = None
            await interaction.response.send_message("👋 Ayrıldım.")
        else:
            await interaction.response.send_message("❌ Ses kanalında değilim.", ephemeral=True)


    @app_commands.command(name="testses", description="Test: yerel ses dosyasini calar")
    async def testses(self, interaction: discord.Interaction):
        kanal = self._ses_kanali(interaction)
        if kanal is None:
            await interaction.response.send_message("ses kanalina gir", ephemeral=True)
            return
        await interaction.response.defer()
        player = await self._baglan(interaction, kanal)
        try:
            source = discord.FFmpegPCMAudio(os.path.join(os.path.dirname(__file__), "..", "test_tone.wav"), executable=FFMPEG_PATH)
            player.voice_client.play(source)
            await interaction.followup.send("test ses caliniyor")
        except Exception as e:
            logger.exception("testses hatasi")
            await interaction.followup.send(f"hata: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Muzik(bot))
