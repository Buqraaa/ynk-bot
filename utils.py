import html


def esc(metin):
    return html.escape(str(metin), quote=True)


def kanal_bul(guild, ad):
    """Sunucuda kanal adina gore kanal bulur. Kanal ID'lerine gecis Faz 2'de."""
    if guild is None or not ad:
        return None

    ad = str(ad).strip().lower()
    if not ad:
        return None

    for channel in guild.text_channels:
        if channel.name.lower() == ad:
            return channel
    return None
