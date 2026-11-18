import io

import discord
from discord.ext import commands

from config import BOT_AYARLARI, logger
from utils import ayarli_kanal
from welcome_image import hosgeldin_gorseli_olustur

VARSAYILAN_RENK = discord.Color.blurple()


def _renk_coz(deger):
    try:
        return discord.Color(int(str(deger).lstrip("#"), 16))
    except (TypeError, ValueError):
        return VARSAYILAN_RENK


def _mesaj_hazirla(sablon, member):
    return (
        str(sablon or "")
        .replace("{uye}", member.mention)
        .replace("{isim}", member.display_name)
        .replace("{sunucu}", member.guild.name)
        .replace("{uye_sayisi}", str(member.guild.member_count))
    )


def _karsilama_embed(member, test=False):
    embed = discord.Embed(
        title=BOT_AYARLARI.get("hosgeldin_baslik") or "👋 Hoş geldin!",
        description=_mesaj_hazirla(
            BOT_AYARLARI.get("hosgeldin_mesaj", "{uye}"), member
        ),
        color=_renk_coz(BOT_AYARLARI.get("hosgeldin_renk")),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(
        name="👥 Üye Sayısı",
        value=f"`{member.guild.member_count}`",
        inline=True,
    )
    alt_yazi = f"{member.guild.name} • {member.name}"
    if test:
        alt_yazi = "🧪 Test mesajı • " + alt_yazi
    embed.set_footer(
        text=alt_yazi,
        icon_url=member.guild.icon.url if member.guild.icon else None,
    )
    return embed


async def test_mesaji_gonder(bot, guild):
    """Paneldeki test butonu icin ornek karşilama mesaji gonderir."""
    kanal = ayarli_kanal(guild, "hosgeldin_kanal")
    if kanal is None:
        raise RuntimeError(
            "Karşılama kanalı bulunamadı. Panelden kanal seçip kaydet."
        )

    uye = guild.me
    if uye is None:
        raise RuntimeError("Botun sunucu üyeliği bulunamadı")

    embed = _karsilama_embed(uye, test=True)
    await kanal.send(embed=embed)
    logger.info("Karşılama test mesajı gönderildi: #%s", kanal.name)


class Karsilama(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _otomatik_rol_ver(self, member):
        rol_id = BOT_AYARLARI.get("hosgeldin_rol_id", 0)
        try:
            rol_id = int(rol_id)
        except (TypeError, ValueError):
            rol_id = 0
        if not rol_id:
            return

        rol = member.guild.get_role(rol_id)
        if rol is None:
            logger.warning("Otomatik rol bulunamadı: %s", rol_id)
            return

        try:
            await member.add_roles(rol, reason="Otomatik karşılama rolü")
            logger.info(
                "Otomatik rol verildi: %s -> %s", member, rol.name
            )
        except discord.Forbidden:
            logger.warning(
                "Otomatik rol verilemedi (yetki): %s -> %s",
                member,
                rol.name,
            )
        except Exception:
            logger.exception("Otomatik rol verme hatası")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        botlari_dahil = bool(
            BOT_AYARLARI.get("hosgeldin_botlari_dahil", False)
        )
        if member.bot and not botlari_dahil:
            return

        if not member.bot:
            await self._otomatik_rol_ver(member)

        kanal = ayarli_kanal(member.guild, "hosgeldin_kanal")
        if kanal is None:
            return

        try:
            embed = _karsilama_embed(member)
            dosyalar = []
            if BOT_AYARLARI.get("hosgeldin_gorsel", True):
                try:
                    avatar_bytes = await member.display_avatar.read()
                    gorsel = hosgeldin_gorseli_olustur(
                        avatar_bytes=avatar_bytes,
                        uye_adi=member.display_name,
                        sunucu_adi=member.guild.name,
                        uye_sayisi=member.guild.member_count,
                        baslik=BOT_AYARLARI.get("hosgeldin_gorsel_baslik") or "Hoş geldin!",
                        mesaj=BOT_AYARLARI.get("hosgeldin_gorsel_mesaj") or "Sunucumuza katıldı",
                    )
                    dosya = discord.File(io.BytesIO(gorsel), filename="hosgeldin.png")
                    embed.set_image(url="attachment://hosgeldin.png")
                    dosyalar.append(dosya)
                except Exception:
                    logger.exception("Hosgeldin gorseli olusturulamadi")
            await kanal.send(
                content=member.mention,
                embed=embed,
                files=dosyalar,
            )
        except Exception:
            logger.exception("Karşılama mesajı gönderilemedi")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.bot:
            return

        kanal = ayarli_kanal(member.guild, "veda_kanal")
        if kanal is None:
            return

        embed = discord.Embed(
            title="👋 Görüşürüz!",
            description=_mesaj_hazirla(
                BOT_AYARLARI.get("veda_mesaj", "{uye}"), member
            ),
            color=discord.Color.dark_grey(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="👥 Kalan Üye",
            value=f"`{member.guild.member_count}`",
            inline=True,
        )
        embed.set_footer(text=member.guild.name)

        try:
            await kanal.send(embed=embed)
        except Exception:
            logger.exception("Veda mesajı gönderilemedi")


async def setup(bot):
    await bot.add_cog(Karsilama(bot))
