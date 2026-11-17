import html

from config import BOT_AYARLARI


def esc(metin):
    return html.escape(str(metin), quote=True)


def kanal_bul(guild, kanal_id=0, ad=""):
    """Once kanal ID'siyle, bulunamazsa kanal adiyla kanal arar."""
    if guild is None:
        return None

    try:
        if kanal_id:
            channel = guild.get_channel(int(kanal_id))
            if channel is not None:
                return channel
    except (TypeError, ValueError):
        pass

    if not ad:
        return None

    ad = str(ad).strip().lower()
    if not ad:
        return None

    for channel in guild.text_channels:
        if channel.name.lower() == ad:
            return channel
    return None


def ayarli_kanal(guild, anahtar):
    """settings.json'daki '<anahtar>_id' ve '<anahtar>' ile kanal bulur."""
    kanal_id = BOT_AYARLARI.get(f"{anahtar}_id", 0)
    ad = BOT_AYARLARI.get(anahtar, "")
    return kanal_bul(guild, kanal_id, ad)


def ayarli_sunucu(bot):
    """settings.json'daki guild_id'ye gore calisilan sunucuyu secer."""
    if bot is None or not getattr(bot, "guilds", None):
        return None

    guild_id = BOT_AYARLARI.get("guild_id", 0)
    try:
        guild_id = int(guild_id)
    except (TypeError, ValueError):
        guild_id = 0

    if guild_id:
        for guild in bot.guilds:
            if guild.id == guild_id:
                return guild
    return bot.guilds[0]
