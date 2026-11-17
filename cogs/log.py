import discord
from discord.ext import commands

from config import logger
from utils import ayarli_kanal

MAVI = discord.Color.blue()
YESIL = discord.Color.green()
TURUNCU = discord.Color.orange()
KIRMIZI = discord.Color.red()
KOYU_KIRMIZI = discord.Color.dark_red()


def _kirp(metin, limit=1000):
    metin = str(metin or "").strip()
    if not metin:
        return "*İçerik yok*"
    if len(metin) <= limit:
        return metin
    return metin[:limit] + "… *(kısaltıldı)*"


def _kisi_bilgisi(kisi):
    return f"{kisi} (`{kisi.id}`)"


async def _gonder(guild, embed, aciklama):
    """Log kanalina embed gonderir; hata olursa botu durdurmaz."""
    kanal = ayarli_kanal(guild, "log_kanal")
    if kanal is None:
        return

    try:
        await kanal.send(embed=embed)
    except Exception:
        logger.exception("%s logu gönderilemedi", aciklama)


class Log(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- Mesaj olayları -------------------------------------------------

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild is None or message.author.bot:
            return

        embed = discord.Embed(
            title="🗑️ Mesaj silindi",
            color=KIRMIZI,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Kanal", value=message.channel.mention, inline=True
        )
        embed.add_field(
            name="Yazan",
            value=_kisi_bilgisi(message.author),
            inline=True,
        )
        embed.add_field(
            name="Silinen mesaj",
            value=_kirp(message.content),
            inline=False,
        )
        embed.set_author(
            name=f"@{message.author.name}",
            icon_url=message.author.display_avatar.url,
        )
        await _gonder(message.guild, embed, "Mesaj silme")

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages:
            return

        guild = messages[0].guild
        if guild is None:
            return

        satirlar = []
        for message in messages[:10]:
            satirlar.append(
                f"**{message.author}** (`{message.channel.name}`): "
                f"{_kirp(message.content, 120)}"
            )
        if len(messages) > 10:
            satirlar.append(f"… ve **{len(messages) - 10}** mesaj daha")

        embed = discord.Embed(
            title="🧹 Toplu mesaj silindi",
            description=f"**{len(messages)}** mesaj silindi.\n\n"
            + "\n".join(satirlar),
            color=KOYU_KIRMIZI,
            timestamp=discord.utils.utcnow(),
        )
        await _gonder(guild, embed, "Toplu mesaj silme")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.guild is None or before.author.bot:
            return
        if before.content == after.content:
            return

        embed = discord.Embed(
            title="✏️ Mesaj düzenlendi",
            color=TURUNCU,
            timestamp=discord.utils.utcnow(),
            url=after.jump_url,
        )
        embed.add_field(
            name="Kanal", value=before.channel.mention, inline=True
        )
        embed.add_field(
            name="Yazan", value=_kisi_bilgisi(before.author), inline=True
        )
        embed.add_field(
            name="Eski hali", value=_kirp(before.content), inline=False
        )
        embed.add_field(
            name="Yeni hali", value=_kirp(after.content), inline=False
        )
        embed.set_author(
            name=f"@{before.author.name}",
            icon_url=before.author.display_avatar.url,
        )
        await _gonder(before.guild, embed, "Mesaj düzenleme")

    # --- Ban / unban ----------------------------------------------------

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = discord.Embed(
            title="🔨 Kullanıcı banlandı",
            description=_kisi_bilgisi(user),
            color=KOYU_KIRMIZI,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await _gonder(guild, embed, "Ban")

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        embed = discord.Embed(
            title="♻️ Ban kaldırıldı",
            description=_kisi_bilgisi(user),
            color=YESIL,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await _gonder(guild, embed, "Unban")

    # --- Kanal olayları -------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(
            title="📁 Kanal oluşturuldu",
            description=f"{channel.mention} (`{channel.name}`)",
            color=YESIL,
            timestamp=discord.utils.utcnow(),
        )
        await _gonder(channel.guild, embed, "Kanal oluşturma")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(
            title="🗂️ Kanal silindi",
            description=f"`{channel.name}`",
            color=KIRMIZI,
            timestamp=discord.utils.utcnow(),
        )
        await _gonder(channel.guild, embed, "Kanal silme")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        degisiklikler = []

        if before.name != after.name:
            degisiklikler.append(
                f"**Ad:** `{before.name}` → `{after.name}`"
            )
        if getattr(before, "topic", None) != getattr(after, "topic", None):
            degisiklikler.append(
                "**Konu:** "
                f"{_kirp(before.topic, 300)} → {_kirp(after.topic, 300)}"
            )
        if getattr(before, "slowmode_delay", 0) != getattr(
            after, "slowmode_delay", 0
        ):
            degisiklikler.append(
                "**Yavaş mod:** "
                f"`{before.slowmode_delay}s` → `{after.slowmode_delay}s`"
            )
        if getattr(before, "nsfw", None) != getattr(after, "nsfw", None):
            degisiklikler.append(
                f"**NSFW:** `{before.nsfw}` → `{after.nsfw}`"
            )
        if getattr(before, "category", None) != getattr(
            after, "category", None
        ):
            eski = before.category.name if before.category else "Yok"
            yeni = after.category.name if after.category else "Yok"
            degisiklikler.append(f"**Kategori:** `{eski}` → `{yeni}`")

        if not degisiklikler:
            return

        embed = discord.Embed(
            title="🔧 Kanal güncellendi",
            description=f"{after.mention}\n\n" + "\n".join(degisiklikler),
            color=TURUNCU,
            timestamp=discord.utils.utcnow(),
        )
        await _gonder(after.guild, embed, "Kanal güncelleme")

    # --- Rol olayları ---------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        embed = discord.Embed(
            title="🏷️ Rol oluşturuldu",
            description=f"{role.mention} (`{role.name}`)",
            color=YESIL,
            timestamp=discord.utils.utcnow(),
        )
        await _gonder(role.guild, embed, "Rol oluşturma")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        embed = discord.Embed(
            title="🏷️ Rol silindi",
            description=f"`{role.name}`",
            color=KIRMIZI,
            timestamp=discord.utils.utcnow(),
        )
        await _gonder(role.guild, embed, "Rol silme")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        degisiklikler = []

        if before.name != after.name:
            degisiklikler.append(
                f"**Ad:** `{before.name}` → `{after.name}`"
            )
        if before.color != after.color:
            degisiklikler.append(
                f"**Renk:** `{before.color}` → `{after.color}`"
            )
        if before.hoist != after.hoist:
            degisiklikler.append(
                f"**Ayrı göster:** `{before.hoist}` → `{after.hoist}`"
            )
        if before.mentionable != after.mentionable:
            degisiklikler.append(
                "**Etiketlenebilir:** "
                f"`{before.mentionable}` → `{after.mentionable}`"
            )

        if before.permissions != after.permissions:
            eklenen = [
                ad
                for ad, deger in after.permissions
                if deger and not getattr(before.permissions, ad)
            ]
            kaldirilan = [
                ad
                for ad, deger in before.permissions
                if deger and not getattr(after.permissions, ad)
            ]
            if eklenen:
                degisiklikler.append(
                    "**Eklenen izinler:** " + ", ".join(eklenen)
                )
            if kaldirilan:
                degisiklikler.append(
                    "**Kaldırılan izinler:** " + ", ".join(kaldirilan)
                )
            if not eklenen and not kaldirilan:
                degisiklikler.append("**İzinler değişti**")

        if not degisiklikler:
            return

        embed = discord.Embed(
            title="🏷️ Rol güncellendi",
            description=f"{after.mention}\n\n" + "\n".join(degisiklikler),
            color=TURUNCU,
            timestamp=discord.utils.utcnow(),
        )
        await _gonder(after.guild, embed, "Rol güncelleme")

    # --- Üye olayları ---------------------------------------------------

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        degisiklikler = []

        if before.nick != after.nick:
            degisiklikler.append(
                f"**Takma ad:** `{before.nick or 'Yok'}` → "
                f"`{after.nick or 'Yok'}`"
            )

        eklenen_roller = set(after.roles) - set(before.roles)
        kaldirilan_roller = set(before.roles) - set(after.roles)
        if eklenen_roller:
            degisiklikler.append(
                "**Eklenen roller:** "
                + ", ".join(rol.mention for rol in eklenen_roller)
            )
        if kaldirilan_roller:
            degisiklikler.append(
                "**Kaldırılan roller:** "
                + ", ".join(rol.mention for rol in kaldirilan_roller)
            )

        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until is None:
                degisiklikler.append("**Susturma kaldırıldı**")
            else:
                bitis = discord.utils.format_dt(
                    after.timed_out_until, style="R"
                )
                degisiklikler.append(f"**Susturuldu:** {bitis}")

        if not degisiklikler:
            return

        embed = discord.Embed(
            title="👤 Üye güncellendi",
            description=f"{_kisi_bilgisi(after)}\n\n"
            + "\n".join(degisiklikler),
            color=MAVI,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=after.display_avatar.url)
        await _gonder(after.guild, embed, "Üye güncelleme")


async def setup(bot):
    await bot.add_cog(Log(bot))
