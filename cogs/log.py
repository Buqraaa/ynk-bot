import discord
from discord.ext import commands

from config import logger
from utils import ayarli_kanal

MAVI = discord.Color.blue()
YESIL = discord.Color.green()
TURUNCU = discord.Color.orange()
KIRMIZI = discord.Color.red()
KOYU_KIRMIZI = discord.Color.dark_red()
MOR = discord.Color.purple()


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

    # ===================== MESAJ OLAYLARI =====================

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild is None or message.author.bot:
            return
        embed = discord.Embed(title="🗑️ Mesaj silindi", color=KIRMIZI, timestamp=discord.utils.utcnow())
        embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
        embed.add_field(name="Yazan", value=_kisi_bilgisi(message.author), inline=True)
        embed.add_field(name="Silinen mesaj", value=_kirp(message.content), inline=False)
        embed.set_author(name=f"@{message.author.name}", icon_url=message.author.display_avatar.url)
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
            satirlar.append(f"**{message.author}** (`{message.channel.name}`): {_kirp(message.content, 120)}")
        if len(messages) > 10:
            satirlar.append(f"… ve **{len(messages) - 10}** mesaj daha")
        embed = discord.Embed(
            title="🗑️ Toplu mesaj silindi",
            description=f"**{len(messages)}** mesaj silindi.\n\n" + "\n".join(satirlar),
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
        embed = discord.Embed(title="✏️ Mesaj düzenlendi", color=TURUNCU, timestamp=discord.utils.utcnow(), url=after.jump_url)
        embed.add_field(name="Kanal", value=before.channel.mention, inline=True)
        embed.add_field(name="Yazan", value=_kisi_bilgisi(before.author), inline=True)
        embed.add_field(name="Eski hali", value=_kirp(before.content), inline=False)
        embed.add_field(name="Yeni hali", value=_kirp(after.content), inline=False)
        embed.set_author(name=f"@{before.author.name}", icon_url=before.author.display_avatar.url)
        await _gonder(before.guild, embed, "Mesaj düzenleme")

    @commands.Cog.listener()
    async def on_guild_channel_pins_update(self, channel, last_pin):
        embed = discord.Embed(title="📌 Kanal pinleri güncellendi", color=TURUNCU, timestamp=discord.utils.utcnow())
        embed.add_field(name="Kanal", value=channel.mention, inline=True)
        embed.add_field(name="Son pin", value=str(last_pin) if last_pin else "Yok", inline=True)
        await _gonder(channel.guild, embed, "Pin güncelleme")

    # ===================== BAN / UNBAN =====================

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = discord.Embed(title="🔨 Kullanıcı banlandı", description=_kisi_bilgisi(user), color=KOYU_KIRMIZI, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=user.display_avatar.url)
        await _gonder(guild, embed, "Ban")

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        embed = discord.Embed(title="✅ Ban kaldırıldı", description=_kisi_bilgisi(user), color=YESIL, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=user.display_avatar.url)
        await _gonder(guild, embed, "Unban")

    # ===================== KANAL OLAYLARI =====================

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(title="➕ Kanal oluşturuldu", description=f"{channel.mention} (`{channel.name}`)", color=YESIL, timestamp=discord.utils.utcnow())
        await _gonder(channel.guild, embed, "Kanal oluşturma")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(title="🗑️ Kanal silindi", description=f"`{channel.name}`", color=KIRMIZI, timestamp=discord.utils.utcnow())
        await _gonder(channel.guild, embed, "Kanal silme")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        degisiklikler = []
        if before.name != after.name:
            degisiklikler.append(f"**Ad:** `{before.name}` → `{after.name}`")
        if getattr(before, "topic", None) != getattr(after, "topic", None):
            degisiklikler.append(f"**Konu:** {_kirp(before.topic, 300)} → {_kirp(after.topic, 300)}")
        if getattr(before, "slowmode_delay", 0) != getattr(after, "slowmode_delay", 0):
            degisiklikler.append(f"**Yavaş mod:** `{before.slowmode_delay}s` → `{after.slowmode_delay}s`")
        if getattr(before, "nsfw", None) != getattr(after, "nsfw", None):
            degisiklikler.append(f"**NSFW:** `{before.nsfw}` → `{after.nsfw}`")
        if getattr(before, "category", None) != getattr(after, "category", None):
            eski = before.category.name if before.category else "Yok"
            yeni = after.category.name if after.category else "Yok"
            degisiklikler.append(f"**Kategori:** `{eski}` → `{yeni}`")
        if not degisiklikler:
            return
        embed = discord.Embed(title="✏️ Kanal güncellendi", description=f"{after.mention}\n\n" + "\n".join(degisiklikler), color=TURUNCU, timestamp=discord.utils.utcnow())
        await _gonder(after.guild, embed, "Kanal güncelleme")

    # ===================== ROL OLAYLARI =====================

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        embed = discord.Embed(title="➕ Rol oluşturuldu", description=f"{role.mention} (`{role.name}`)", color=YESIL, timestamp=discord.utils.utcnow())
        await _gonder(role.guild, embed, "Rol oluşturma")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        embed = discord.Embed(title="🗑️ Rol silindi", description=f"`{role.name}`", color=KIRMIZI, timestamp=discord.utils.utcnow())
        await _gonder(role.guild, embed, "Rol silme")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        degisiklikler = []
        if before.name != after.name:
            degisiklikler.append(f"**Ad:** `{before.name}` → `{after.name}`")
        if before.color != after.color:
            degisiklikler.append(f"**Renk:** `{before.color}` → `{after.color}`")
        if before.hoist != after.hoist:
            degisiklikler.append(f"**Ayrı göster:** `{before.hoist}` → `{after.hoist}`")
        if before.mentionable != after.mentionable:
            degisiklikler.append(f"**Etiketlenebilir:** `{before.mentionable}` → `{after.mentionable}`")
        if before.permissions != after.permissions:
            eklenen = [ad for ad, deger in after.permissions if deger and not getattr(before.permissions, ad)]
            kaldirilan = [ad for ad, deger in before.permissions if deger and not getattr(after.permissions, ad)]
            if eklenen:
                degisiklikler.append("**Eklenen izinler:** " + ", ".join(eklenen))
            if kaldirilan:
                degisiklikler.append("**Kaldırılan izinler:** " + ", ".join(kaldirilan))
            if not eklenen and not kaldirilan:
                degisiklikler.append("**İzinler değişti**")
        if not degisiklikler:
            return
        embed = discord.Embed(title="✏️ Rol güncellendi", description=f"{after.mention}\n\n" + "\n".join(degisiklikler), color=TURUNCU, timestamp=discord.utils.utcnow())
        await _gonder(after.guild, embed, "Rol güncelleme")

    # ===================== EMOJI / STICKER =====================

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        eklenen = set(after) - set(before)
        kaldirilan = set(before) - set(after)
        degisen = [e for e in after if e in before and e.name != before[before.index(e)].name] if False else []
        satirlar = []
        for e in eklenen:
            satirlar.append(f"➕ {e} (`{e.name}`)")
        for e in kaldirilan:
            satirlar.append(f"🗑️ `{e.name}`")
        if not satirlar:
            return
        embed = discord.Embed(title="😀 Emoji güncellendi", description="\n".join(satirlar), color=TURUNCU, timestamp=discord.utils.utcnow())
        await _gonder(guild, embed, "Emoji güncelleme")

    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild, before, after):
        eklenen = set(after) - set(before)
        kaldirilan = set(before) - set(after)
        satirlar = []
        for s in eklenen:
            satirlar.append(f"➕ {s.name}")
        for s in kaldirilan:
            satirlar.append(f"🗑️ {s.name}")
        if not satirlar:
            return
        embed = discord.Embed(title="🏷️ Sticker güncellendi", description="\n".join(satirlar), color=TURUNCU, timestamp=discord.utils.utcnow())
        await _gonder(guild, embed, "Sticker güncelleme")

    # ===================== WEBHOOK =====================

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        embed = discord.Embed(title="🔗 Webhook güncellendi", description=f"Kanal: {channel.mention}", color=TURUNCU, timestamp=discord.utils.utcnow())
        await _gonder(channel.guild, embed, "Webhook güncelleme")

    # ===================== SUNUCU OLAYLARI =====================

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        degisiklikler = []
        if before.name != after.name:
            degisiklikler.append(f"**Sunucu adı:** `{before.name}` → `{after.name}`")
        if before.icon != after.icon:
            degisiklikler.append("**Sunucu ikonu değişti**")
        if before.splash != after.splash:
            degisiklikler.append("**Splash (davet arka planı) değişti**")
        if before.vanity_url_code != after.vanity_url_code:
            degisiklikler.append(f"**Vanity URL:** `{before.vanity_url_code}` → `{after.vanity_url_code}`")
        if before.system_channel != after.system_channel:
            eski = before.system_channel.name if before.system_channel else "Yok"
            yeni = after.system_channel.name if after.system_channel else "Yok"
            degisiklikler.append(f"**Sistem kanalı:** `{eski}` → `{yeni}`")
        if before.description != after.description:
            degisiklikler.append("**Sunucu açıklaması değişti**")
        if not degisiklikler:
            return
        embed = discord.Embed(title="🏠 Sunucu güncellendi", description="\n".join(degisiklikler), color=TURUNCU, timestamp=discord.utils.utcnow())
        await _gonder(after, embed, "Sunucu güncelleme")

    # ===================== DAVET OLAYLARI =====================

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        embed = discord.Embed(title="🔗 Davet oluşturuldu", color=YESIL, timestamp=discord.utils.utcnow())
        embed.add_field(name="Kod", value=invite.code, inline=True)
        embed.add_field(name="Kanal", value=invite.channel.mention if invite.channel else "?", inline=True)
        if invite.inviter:
            embed.add_field(name="Oluşturan", value=_kisi_bilgisi(invite.inviter), inline=True)
        await _gonder(invite.guild, embed, "Davet oluşturma")

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        embed = discord.Embed(title="🗑️ Davet silindi", description=f"`{invite.code}`", color=KIRMIZI, timestamp=discord.utils.utcnow())
        await _gonder(invite.guild, embed, "Davet silme")

    # ===================== ENTEGRASYON / UYGULAMA =====================

    @commands.Cog.listener()
    async def on_integration_create(self, integration):
        guild = getattr(integration, "guild", None)
        if guild is None:
            return
        embed = discord.Embed(title="➕ Entegrasyon eklendi", description=f"`{integration.name}` ({integration.type})", color=YESIL, timestamp=discord.utils.utcnow())
        await _gonder(guild, embed, "Entegrasyon ekleme")

    @commands.Cog.listener()
    async def on_integration_delete(self, integration):
        guild = getattr(integration, "guild", None)
        if guild is None:
            return
        embed = discord.Embed(title="🗑️ Entegrasyon kaldırıldı", description=f"`{integration.name}` ({integration.type})", color=KIRMIZI, timestamp=discord.utils.utcnow())
        await _gonder(guild, embed, "Entegrasyon kaldırma")

    # ===================== THREAD OLAYLARI =====================

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        embed = discord.Embed(title="🧵 Thread oluşturuldu", description=f"{thread.mention} (`{thread.name}`)", color=YESIL, timestamp=discord.utils.utcnow())
        await _gonder(thread.guild, embed, "Thread oluşturma")

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        embed = discord.Embed(title="🗑️ Thread silindi", description=f"`{thread.name}`", color=KIRMIZI, timestamp=discord.utils.utcnow())
        await _gonder(thread.guild, embed, "Thread silme")

    @commands.Cog.listener()
    async def on_thread_update(self, before, after):
        degisiklikler = []
        if before.name != after.name:
            degisiklikler.append(f"**Ad:** `{before.name}` → `{after.name}`")
        if getattr(before, "slowmode_delay", 0) != getattr(after, "slowmode_delay", 0):
            degisiklikler.append(f"**Yavaş mod:** `{before.slowmode_delay}s` → `{after.slowmode_delay}s`")
        if getattr(before, "locked", None) != getattr(after, "locked", None):
            degisiklikler.append(f"**Kilit:** `{before.locked}` → `{after.locked}`")
        if getattr(before, "archived", None) != getattr(after, "archived", None):
            degisiklikler.append(f"**Arşiv:** `{before.archived}` → `{after.archived}`")
        if not degisiklikler:
            return
        embed = discord.Embed(title="✏️ Thread güncellendi", description=f"{after.mention}\n\n" + "\n".join(degisiklikler), color=TURUNCU, timestamp=discord.utils.utcnow())
        await _gonder(after.guild, embed, "Thread güncelleme")

    # ===================== SES OLAYLARI =====================

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        # Kanal değişikliği
        if before.channel != after.channel:
            if before.channel is None and after.channel is not None:
                embed = discord.Embed(title="🔊 Ses kanalına katıldı", description=f"{_kisi_bilgisi(member)} → {after.channel.mention}", color=YESIL, timestamp=discord.utils.utcnow())
                await _gonder(member.guild, embed, "Ses katılım")
            elif before.channel is not None and after.channel is None:
                embed = discord.Embed(title="🔇 Ses kanalından ayrıldı", description=f"{_kisi_bilgisi(member)} ← {before.channel.mention}", color=KIRMIZI, timestamp=discord.utils.utcnow())
                await _gonder(member.guild, embed, "Ses ayrılma")
            elif before.channel is not None and after.channel is not None:
                embed = discord.Embed(title="🔀 Ses kanalı değiştirildi", description=f"{_kisi_bilgisi(member)}: {before.channel.mention} → {after.channel.mention}", color=TURUNCU, timestamp=discord.utils.utcnow())
                await _gonder(member.guild, embed, "Ses kanal değişimi")
        # Susturma/deaf değişikliği
        if before.self_mute != after.self_mute or before.self_deaf != after.self_deaf or before.mute != after.mute or before.deaf != after.deaf:
            degisiklikler = []
            if before.self_mute != after.self_mute:
                degisiklikler.append(f"**Self-mute:** `{before.self_mute}` → `{after.self_mute}`")
            if before.self_deaf != after.self_deaf:
                degisiklikler.append(f"**Self-deaf:** `{before.self_deaf}` → `{after.self_deaf}`")
            if before.mute != after.mute:
                degisiklikler.append(f"**Server mute:** `{before.mute}` → `{after.mute}`")
            if before.deaf != after.deaf:
                degisiklikler.append(f"**Server deaf:** `{before.deaf}` → `{after.deaf}`")
            if degisiklikler:
                embed = discord.Embed(title="  Ses durumu güncellendi", description=f"{_kisi_bilgisi(member)}\n\n" + "\n".join(degisiklikler), color=MAVI, timestamp=discord.utils.utcnow())
                await _gonder(member.guild, embed, "Ses durum güncelleme")

    # ===================== STAGE OLAYLARI =====================

    @commands.Cog.listener()
    async def on_stage_instance_create(self, stage_instance):
        embed = discord.Embed(title="🎤 Stage başladı", description=f"`{stage_instance.topic}`", color=YESIL, timestamp=discord.utils.utcnow())
        await _gonder(stage_instance.guild, embed, "Stage başlatma")

    @commands.Cog.listener()
    async def on_stage_instance_delete(self, stage_instance):
        embed = discord.Embed(title="🎤 Stage bitti", description=f"`{stage_instance.topic}`", color=KIRMIZI, timestamp=discord.utils.utcnow())
        await _gonder(stage_instance.guild, embed, "Stage bitirme")

    @commands.Cog.listener()
    async def on_stage_instance_update(self, before, after):
        if before.topic != after.topic:
            embed = discord.Embed(title="✏️ Stage konusu güncellendi", description=f"`{before.topic}` → `{after.topic}`", color=TURUNCU, timestamp=discord.utils.utcnow())
            await _gonder(after.guild, embed, "Stage konu güncelleme")

    # ===================== SCHEDULED EVENT OLAYLARI =====================

    @commands.Cog.listener()
    async def on_scheduled_event_create(self, event):
        embed = discord.Embed(title="📅 Etkinlik oluşturuldu", description=f"`{event.name}`", color=YESIL, timestamp=discord.utils.utcnow())
        await _gonder(event.guild, embed, "Etkinlik oluşturma")

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event):
        embed = discord.Embed(title="🗑️ Etkinlik silindi", description=f"`{event.name}`", color=KIRMIZI, timestamp=discord.utils.utcnow())
        await _gonder(event.guild, embed, "Etkinlik silme")

    @commands.Cog.listener()
    async def on_scheduled_event_update(self, before, after):
        degisiklikler = []
        if before.name != after.name:
            degisiklikler.append(f"**Ad:** `{before.name}` → `{after.name}`")
        if before.description != after.description:
            degisiklikler.append("**Açıklama değişti**")
        if before.status != after.status:
            degisiklikler.append(f"**Durum:** `{before.status}` → `{after.status}`")
        if not degisiklikler:
            return
        embed = discord.Embed(title="✏️ Etkinlik güncellendi", description=f"`{after.name}`\n\n" + "\n".join(degisiklikler), color=TURUNCU, timestamp=discord.utils.utcnow())
        await _gonder(after.guild, embed, "Etkinlik güncelleme")

    # ===================== AUTOMOD OLAYLARI =====================

    @commands.Cog.listener()
    async def on_automod_rule_create(self, rule):
        embed = discord.Embed(title="🛡️ AutoMod kuralı oluşturuldu", description=f"`{rule.name}`", color=YESIL, timestamp=discord.utils.utcnow())
        await _gonder(rule.guild, embed, "AutoMod kural oluşturma")

    @commands.Cog.listener()
    async def on_automod_rule_delete(self, rule):
        embed = discord.Embed(title="🗑️ AutoMod kuralı silindi", description=f"`{rule.name}`", color=KIRMIZI, timestamp=discord.utils.utcnow())
        await _gonder(rule.guild, embed, "AutoMod kural silme")

    @commands.Cog.listener()
    async def on_automod_rule_update(self, before, after):
        if before.name != after.name:
            embed = discord.Embed(title="✏️ AutoMod kuralı güncellendi", description=f"`{before.name}` → `{after.name}`", color=TURUNCU, timestamp=discord.utils.utcnow())
            await _gonder(after.guild, embed, "AutoMod kural güncelleme")

    @commands.Cog.listener()
    async def on_automod_action(self, execution):
        embed = discord.Embed(title="🚨 AutoMod aksiyonu", description=f"Kural: `{execution.rule_name}`", color=KOYU_KIRMIZI, timestamp=discord.utils.utcnow())
        await _gonder(execution.guild, embed, "AutoMod aksiyon")

    # ===================== POLL OLAYLARI =====================

    @commands.Cog.listener()
    async def on_poll_vote_add(self, user, answer):
        # Çok spam olabilir; sadece log kanalına kısa mesaj
        pass

    # ===================== ÜYE OLAYLARI =====================

    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = discord.Embed(title="📥 Üye katıldı", description=_kisi_bilgisi(member), color=YESIL, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        await _gonder(member.guild, embed, "Üye katılım")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = discord.Embed(title="📤 Üye ayrıldı", description=_kisi_bilgisi(member), color=KIRMIZI, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        await _gonder(member.guild, embed, "Üye ayrılma")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        degisiklikler = []
        if before.nick != after.nick:
            degisiklikler.append(f"**Takma ad:** `{before.nick or 'Yok'}` → `{after.nick or 'Yok'}`")
        eklenen_roller = set(after.roles) - set(before.roles)
        kaldirilan_roller = set(before.roles) - set(after.roles)
        if eklenen_roller:
            degisiklikler.append("**Eklenen roller:** " + ", ".join(rol.mention for rol in eklenen_roller))
        if kaldirilan_roller:
            degisiklikler.append("**Kaldırılan roller:** " + ", ".join(rol.mention for rol in kaldirilan_roller))
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until is None:
                degisiklikler.append("**Susturma kaldırıldı**")
            else:
                bitis = discord.utils.format_dt(after.timed_out_until, style="R")
                degisiklikler.append(f"**Susturuldu:** {bitis}")
        if not degisiklikler:
            return
        embed = discord.Embed(title="✏️ Üye güncellendi", description=f"{_kisi_bilgisi(after)}\n\n" + "\n".join(degisiklikler), color=MAVI, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=after.display_avatar.url)
        await _gonder(after.guild, embed, "Üye güncelleme")

    # ===================== KULLANICI GÜNCELLEME =====================

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        # Bot kullanıcısı için; guild bağlamı yok, atla
        pass


async def setup(bot):
    await bot.add_cog(Log(bot))
