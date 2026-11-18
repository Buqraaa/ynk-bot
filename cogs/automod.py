import re
import time

import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_AYARLARI, logger
import db


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._mesaj_gecmisi = {}  # (guild_id, user_id) -> [timestamps]
        self._join_gecmisi = {}  # guild_id -> [timestamps]
        self._uyari_sayaci = {}  # (guild_id, user_id) -> count

    def _ayar(self, anahtar, varsayilan=False):
        return BOT_AYARLARI.get(anahtar, varsayilan)

    async def _aksiyon(self, message, sebep):
        guild = message.guild
        user = message.author

        # Mesaji sil
        try:
            await message.delete()
        except Exception:
            pass

        aksiyon = self._ayar("automod_aksiyon", "uyari")
        log_kanal = None
        try:
            from utils import ayarli_kanal
            log_kanal = ayarli_kanal(guild, "log_kanal")
        except Exception:
            pass

        db.automod_log_ekle(guild.id, user.id, aksiyon, sebep)

        if aksiyon == "uyari":
            # Uyari ver
            db.uyari_ekle(guild.id, user.id, f"AutoMod: {sebep}", self.bot.user.id)
            try:
                await user.send(f"⚠️ **{guild.name}** sunucusunda AutoMod tarafından uyarıldın.\nSebep: {sebep}")
            except Exception:
                pass
        elif aksiyon == "sustur":
            try:
                import datetime
                await user.timeout(datetime.timedelta(minutes=10), reason=f"AutoMod: {sebep}")
            except Exception:
                logger.exception("AutoMod susturma hatasi")
        elif aksiyon == "ban":
            try:
                await user.ban(reason=f"AutoMod: {sebep}")
            except Exception:
                logger.exception("AutoMod ban hatasi")

        # Log kanalina bildir
        if log_kanal:
            try:
                embed = discord.Embed(
                    title="🛡️ AutoMod Aksiyonu",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(name="Kullanıcı", value=f"{user} (`{user.id}`)", inline=True)
                embed.add_field(name="Aksiyon", value=aksiyon, inline=True)
                embed.add_field(name="Sebep", value=sebep, inline=False)
                embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
                await log_kanal.send(embed=embed)
            except Exception:
                logger.exception("AutoMod log gonderilemedi")

    # ===================== SPAM TESPITI =====================

    def _spam_kontrol(self, message):
        if not self._ayar("automod_spam", False):
            return False
        guild_id = message.guild.id
        user_id = message.author.id
        anahtar = (guild_id, user_id)
        simdi = time.time()

        if anahtar not in self._mesaj_gecmisi:
            self._mesaj_gecmisi[anahtar] = []
        self._mesaj_gecmisi[anahtar].append(simdi)

        # Son 10 saniyedeki mesajlar
        pencere = 10
        limit = int(self._ayar("automod_spam_limit", 5))
        self._mesaj_gecmisi[anahtar] = [t for t in self._mesaj_gecmisi[anahtar] if simdi - t < pencere]

        if len(self._mesaj_gecmisi[anahtar]) > limit:
            return True
        return False

    # ===================== LINK FILTRESI =====================

    def _link_kontrol(self, message):
        if not self._ayar("automod_link", False):
            return False
        icerik = message.content.lower()

        # Discord davet linkleri
        if self._ayar("automod_block_invites", True):
            if re.search(r"discord\.gg/\w+", icerik) or re.search(r"discord\.com/invite/\w+", icerik):
                return "Discord davet linki"

        # Yasakli domainler
        yasakli = self._ayar("automod_blocked_domains", [])
        if isinstance(yasakli, list):
            for domain in yasakli:
                if domain and domain.lower() in icerik:
                    return f"Yasaklı domain: {domain}"

        # Link engelleme (tum linkler)
        if self._ayar("automod_block_all_links", False):
            if re.search(r"https?://", icerik):
                return "Link gönderimi engellendi"

        return False

    # ===================== KUFUR FILTRESI =====================

    def _kufur_kontrol(self, message):
        if not self._ayar("automod_word_filter", False):
            return False
        icerik = message.content.lower()
        yasakli = self._ayar("automod_banned_words", [])
        if isinstance(yasakli, list):
            for kelime in yasakli:
                if kelime and kelime.lower() in icerik:
                    return f"Yasaklı kelime: {kelime}"
        return False

    # ===================== CAPS LOCK FILTRESI =====================

    def _caps_kontrol(self, message):
        if not self._ayar("automod_caps", False):
            return False
        icerik = message.content
        if len(icerik) < 8:
            return False
        harfler = [c for c in icerik if c.isalpha()]
        if not harfler:
            return False
        buyuk = sum(1 for c in harfler if c.isupper())
        oran = buyuk / len(harfler)
        esik = float(self._ayar("automod_caps_threshold", 0.7))
        if oran >= esik:
            return "Aşırı büyük harf kullanımı"
        return False

    # ===================== MENTION SPAM =====================

    def _mention_kontrol(self, message):
        if not self._ayar("automod_mention_spam", False):
            return False
        limit = int(self._ayar("automod_mention_limit", 5))
        if len(message.mentions) > limit:
            return f"Aşırı mention ({len(message.mentions)} > {limit})"
        return False

    # ===================== RAID KORUMASI =====================

    def _raid_kontrol(self, member):
        if not self._ayar("automod_raid", False):
            return False
        guild_id = member.guild.id
        simdi = time.time()
        if guild_id not in self._join_gecmisi:
            self._join_gecmisi[guild_id] = []
        self._join_gecmisi[guild_id].append(simdi)
        pencere = 60
        limit = int(self._ayar("automod_raid_limit", 10))
        self._join_gecmisi[guild_id] = [t for t in self._join_gecmisi[guild_id] if simdi - t < pencere]
        if len(self._join_gecmisi[guild_id]) > limit:
            return True
        return False

    # ===================== EVENT LISTENERS =====================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.bot:
            return
        if message.author.guild_permissions.manage_messages:
            return  # Yetkili kullanıcıları atla

        # Kontroller
        sebep = None
        if self._spam_kontrol(message):
            sebep = "Spam (hızlı mesaj)"
        elif self._link_kontrol(message):
            sebep = self._link_kontrol(message)
        elif self._kufur_kontrol(message):
            sebep = self._kufur_kontrol(message)
        elif self._caps_kontrol(message):
            sebep = self._caps_kontrol(message)
        elif self._mention_kontrol(message):
            sebep = self._mention_kontrol(message)

        if sebep:
            await self._aksiyon(message, sebep)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        if self._raid_kontrol(member):
            # Raid tespit edildi
            try:
                await member.ban(reason="AutoMod: Raid tespit edildi")
            except Exception:
                logger.exception("AutoMod raid ban hatasi")
            db.automod_log_ekle(member.guild.id, member.id, "ban", "Raid tespit edildi")
            log_kanal = None
            try:
                from utils import ayarli_kanal
                log_kanal = ayarli_kanal(member.guild, "log_kanal")
            except Exception:
                pass
            if log_kanal:
                try:
                    embed = discord.Embed(title="🚨 AutoMod: Raid Tespit Edildi", color=discord.Color.red(), timestamp=discord.utils.utcnow())
                    embed.add_field(name="Kullanıcı", value=f"{member} (`{member.id}`)", inline=True)
                    embed.add_field(name="Aksiyon", value="Ban", inline=True)
                    await log_kanal.send(embed=embed)
                except Exception:
                    pass

    @app_commands.command(name="automod-durum", description="AutoMod durumunu gösterir")
    async def automod_durum(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🛡️ AutoMod Durumu", color=discord.Color.blue())
        ayarlar = [
            ("Spam filtresi", self._ayar("automod_spam", False)),
            ("Link filtresi", self._ayar("automod_link", False)),
            ("Küfür filtresi", self._ayar("automod_word_filter", False)),
            ("Caps filtresi", self._ayar("automod_caps", False)),
            ("Mention spam", self._ayar("automod_mention_spam", False)),
            ("Raid koruması", self._ayar("automod_raid", False)),
        ]
        for ad, durum in ayarlar:
            embed.add_field(name=ad, value="✅ Açık" if durum else "❌ Kapalı", inline=True)
        embed.add_field(name="Aksiyon", value=self._ayar("automod_aksiyon", "uyari"), inline=True)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
