import asyncio
import re
import urllib.request
import xml.etree.ElementTree as ET

from discord.ext import commands, tasks

from config import BOT_AYARLARI, ayarlari_kaydet, logger
from utils import ayarli_kanal


def kanal_idsini_coz(girdi):
    """YouTube linki, @handle veya UC... ID'sini gercek kanal ID'sine cevirir."""
    girdi = girdi.strip()
    if not girdi:
        return ""

    if girdi.startswith("UC") and len(girdi) >= 24:
        return girdi

    if "youtube.com" in girdi or girdi.startswith("@"):
        if girdi.startswith("@"):
            url = f"https://www.youtube.com/@{girdi.lstrip('@')}"
        else:
            url = girdi

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                    )
                },
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html_icerik = response.read().decode("utf-8")

            match = re.search(
                r'"channelId"\s*:\s*"(UC[a-zA-Z0-9_-]{22})"', html_icerik
            )
            if match:
                return match.group(1)

            match_canonical = re.search(
                r'href=["\']https://www\.youtube\.com/channel/'
                r'(UC[a-zA-Z0-9_-]{22})["\']',
                html_icerik,
            )
            if match_canonical:
                return match_canonical.group(1)
        except Exception as e:
            logger.warning("YouTube kanal ID çözme hatası: %s", e)

    return girdi


def son_youtube_videosunu_getir(girdi):
    gercek_id = kanal_idsini_coz(girdi)
    if not gercek_id:
        return None

    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={gercek_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
        }
        entry = root.find("atom:entry", ns)
        if entry is not None:
            video_id = entry.find("yt:videoId", ns).text
            title = entry.find("atom:title", ns).text
            link_el = entry.find("atom:link", ns)
            link = (
                link_el.attrib["href"]
                if link_el is not None
                else f"https://www.youtube.com/watch?v={video_id}"
            )
            return {"id": video_id, "title": title, "link": link}
    except Exception as e:
        logger.warning("YouTube RSS kontrol hatası: %s", e)
    return None


class YouTube(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.kontrol.start()

    async def cog_unload(self):
        self.kontrol.cancel()

    @tasks.loop(seconds=60)
    async def kontrol(self):
        await self.bot.wait_until_ready()

        yt_input = BOT_AYARLARI.get("youtube_channel_id", "").strip()
        if not yt_input:
            return

        loop = asyncio.get_running_loop()
        video = await loop.run_in_executor(
            None, son_youtube_videosunu_getir, yt_input
        )
        if not video:
            return

        son_kayitli_id = BOT_AYARLARI.get("son_video_id", "")
        if not son_kayitli_id:
            BOT_AYARLARI["son_video_id"] = video["id"]
            ayarlari_kaydet(BOT_AYARLARI)
            return

        if video["id"] != son_kayitli_id:
            BOT_AYARLARI["son_video_id"] = video["id"]
            ayarlari_kaydet(BOT_AYARLARI)

            sablon = BOT_AYARLARI.get(
                "youtube_mesaj", "Yeni video yayında! {link}"
            )
            mesaj_metni = sablon.replace("{link}", video["link"]).replace(
                "{baslik}", video["title"]
            )
            if "{link}" not in sablon:
                mesaj_metni = f"{mesaj_metni}\n{video['link']}"

            for guild in self.bot.guilds:
                channel = ayarli_kanal(guild, "youtube_kanal")
                if channel:
                    try:
                        await channel.send(mesaj_metni)
                    except Exception:
                        logger.exception("YouTube duyuru gönderme hatası")


async def setup(bot):
    await bot.add_cog(YouTube(bot))
