import discord
from discord.ext import commands

from config import BOT_AYARLARI, logger
from utils import kanal_bul


class Sayac(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        kanal = kanal_bul(member.guild, BOT_AYARLARI["sayac_kanal"])
        if kanal is None:
            return

        aktif_uye = member.guild.member_count
        hedef = BOT_AYARLARI["hedef_uye"]
        kalan = hedef - aktif_uye
        aciklama = BOT_AYARLARI["giris_mesaji"].replace("{uye}", member.mention)

        embed = discord.Embed(
            title="📥 Yeni Üye Katıldı!",
            description=aciklama,
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="🎯 Hedef Üye", value=f"`{hedef}`", inline=True)
        embed.add_field(name="⏳ Kalan", value=f"`{kalan}`", inline=True)
        embed.add_field(name="👥 Anlık Üye", value=f"`{aktif_uye}`", inline=True)

        try:
            await kanal.send(embed=embed)
        except Exception:
            logger.exception("Sayaç giriş mesajı gönderilemedi")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        kanal = kanal_bul(member.guild, BOT_AYARLARI["sayac_kanal"])
        if kanal is None:
            return

        aktif_uye = member.guild.member_count
        hedef = BOT_AYARLARI["hedef_uye"]
        kalan = hedef - aktif_uye
        aciklama = BOT_AYARLARI["cikis_mesaji"].replace("{uye}", member.mention)

        embed = discord.Embed(
            title="📤 Bir Üye Ayrıldı",
            description=aciklama,
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="🎯 Hedef Üye", value=f"`{hedef}`", inline=True)
        embed.add_field(name="⏳ Kalan", value=f"`{kalan}`", inline=True)
        embed.add_field(name="👥 Anlık Üye", value=f"`{aktif_uye}`", inline=True)

        try:
            await kanal.send(embed=embed)
        except Exception:
            logger.exception("Sayaç çıkış mesajı gönderilemedi")


async def setup(bot):
    await bot.add_cog(Sayac(bot))
