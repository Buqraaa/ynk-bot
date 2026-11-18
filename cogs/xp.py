import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_AYARLARI, logger
import db


def _xp_gereken(level):
    """Bir sonraki seviye icin gereken XP."""
    return 100 * (level + 1) * (level + 2) // 2


def _level_hesapla(xp):
    level = 0
    while xp >= _xp_gereken(level):
        xp -= _xp_gereken(level)
        level += 1
    return level


class XP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._son_mesaj = {}  # (guild_id, user_id) -> timestamp
        self._voice_task = None

    async def cog_load(self):
        import asyncio
        self._voice_task = asyncio.get_running_loop().create_task(self._voice_xp_loop())

    async def cog_unload(self):
        if self._voice_task:
            self._voice_task.cancel()

    async def _voice_xp_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            for guild in self.bot.guilds:
                for vc in guild.voice_channels:
                    for member in vc.members:
                        if member.bot:
                            continue
                        if member.voice and member.voice.self_mute:
                            continue
                        if member.voice and member.voice.self_deaf:
                            continue
                        xp_miktar = int(BOT_AYARLARI.get("xp_voice_per_minute", 5))
                        db.xp_ekle(guild.id, member.id, xp_miktar)
                        db.voice_xp_ekle(guild.id, member.id, 60)
                        # level kontrol
                        veri = db.xp_getir(guild.id, member.id)
                        yeni_level = _level_hesapla(veri["xp"])
                        if yeni_level > veri["level"]:
                            db.xp_level_guncelle(guild.id, member.id, yeni_level)
                            await self._level_atlama(member, yeni_level)
            await asyncio.sleep(60)

    async def _level_atlama(self, member, level):
        kanal_id = BOT_AYARLARI.get("xp_duyuru_kanal_id", 0) or BOT_AYARLARI.get("xp_duyuru_kanal", "")
        kanal = None
        if kanal_id:
            try:
                kanal = member.guild.get_channel(int(kanal_id))
            except (TypeError, ValueError):
                pass
        if kanal is None:
            kanal = member.guild.system_channel
        if kanal is None:
            return
        try:
            await kanal.send(f"🎉 {member.mention} **{level}. seviyeye** ulaştı!")
        except Exception:
            pass

        # Level rolü ver
        roller = BOT_AYARLARI.get("xp_level_roller", {})
        if isinstance(roller, dict):
            rol_id = roller.get(str(level))
            if rol_id:
                try:
                    rol = member.guild.get_role(int(rol_id))
                    if rol:
                        await member.add_roles(rol, reason="XP seviye rolü")
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.bot:
            return

        cooldown = int(BOT_AYARLARI.get("xp_mesaj_cooldown", 60))
        anahtar = (message.guild.id, message.author.id)
        simdi = time.time()
        if anahtar in self._son_mesaj and simdi - self._son_mesaj[anahtar] < cooldown:
            return
        self._son_mesaj[anahtar] = simdi

        xp_miktar = int(BOT_AYARLARI.get("xp_mesaj", 10))
        db.xp_ekle(message.guild.id, message.author.id, xp_miktar)

        veri = db.xp_getir(message.guild.id, message.author.id)
        yeni_level = _level_hesapla(veri["xp"])
        if yeni_level > veri["level"]:
            db.xp_level_guncelle(message.guild.id, message.author.id, yeni_level)
            await self._level_atlama(message.author, yeni_level)

    @app_commands.command(name="rank", description="Seviye ve XP bilgini gösterir")
    @app_commands.describe(uye="Üye (boş bırakırsan kendin)")
    async def rank(self, interaction: discord.Interaction, uye: discord.Member = None):
        if uye is None:
            uye = interaction.user
        veri = db.xp_getir(interaction.guild.id, uye.id)
        level = veri["level"]
        xp = veri["xp"]
        gereken = _xp_gereken(level)
        ilerleme = min(xp, gereken)
        bar_uzunluk = 20
        dolu = int(ilerleme / gereken * bar_uzunluk) if gereken > 0 else 0
        bar = "█" * dolu + "░" * (bar_uzunluk - dolu)

        embed = discord.Embed(title=f"📊 {uye.display_name}", color=discord.Color.blurple())
        embed.add_field(name="Seviye", value=f"**{level}**", inline=True)
        embed.add_field(name="XP", value=f"**{xp}** / {gereken}", inline=True)
        embed.add_field(name="İlerleme", value=f"`{bar}` {ilerleme}/{gereken}", inline=False)
        embed.add_field(name="Ses süresi", value=f"{veri['voice_seconds'] // 60} dk", inline=True)
        embed.set_thumbnail(url=uye.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="top", description="En yüksek XP'li 10 üyeyi gösterir")
    async def top(self, interaction: discord.Interaction):
        liste = db.top_xp_listesi(interaction.guild.id, 10)
        if not liste:
            await interaction.response.send_message("Henüz XP verisi yok.", ephemeral=True)
            return
        satirlar = []
        for i, veri in enumerate(liste, 1):
            satirlar.append(f"**{i}.** <@{veri['user_id']}> — Seviye {veri['level']} ({veri['xp']} XP)")
        embed = discord.Embed(title="🏆 XP Liderlik Tablosu", description="\n".join(satirlar), color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(XP(bot))
