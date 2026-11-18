import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_AYARLARI, ayarlari_kaydet, logger
from utils import ayarli_kanal, ayarli_sunucu

import db

TICKET_ON_EKI = "ticket:"


class TicketKapatView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Ticket'ı Kapat", style=discord.ButtonStyle.danger, custom_id=f"{TICKET_ON_EKI}kapat")
    async def kapat(self, interaction: discord.Interaction, button: discord.ui.Button):
        kanal = interaction.channel
        if kanal is None:
            return
        await interaction.response.send_message("Ticket kapatılıyor...", ephemeral=True)
        try:
            db.ticket_kapat(kanal.id)
        except Exception:
            logger.exception("Ticket DB guncellenemedi")
        try:
            await kanal.delete(reason=f"Ticket kapatıldı: {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send("❌ Kanal silinemedi (yetki).", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Hata: {e}", ephemeral=True)


class TicketAcView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Ticket Aç", style=discord.ButtonStyle.primary, custom_id=f"{TICKET_ON_EKI}ac")
    async def ac(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Bu sadece sunucuda çalışır.", ephemeral=True)
            return

        # Zaten açık ticket var mı?
        mevcut = discord.utils.get(guild.text_channels, name=f"ticket-{interaction.user.name.lower()[:20]}")
        if mevcut is not None:
            await interaction.response.send_message(f"Zaten açık bir ticket'ın var: {mevcut.mention}", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        kategori_adi = (BOT_AYARLARI.get("ticket_kategori") or "Tickets").strip()
        kategori = discord.utils.get(guild.categories, name=kategori_adi)
        if kategori is None:
            try:
                kategori = await guild.create_category(kategori_adi)
            except discord.Forbidden:
                await interaction.followup.send("❌ Kategori oluşturulamadı (yetki).", ephemeral=True)
                return

        destek_rol_id = BOT_AYARLARI.get("ticket_destek_rol_id", 0)
        destek_rol = guild.get_role(int(destek_rol_id)) if destek_rol_id else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        if destek_rol is not None:
            overwrites[destek_rol] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        try:
            kanal = await guild.create_text_channel(
                name=f"ticket-{interaction.user.name}"[:90],
                category=kategori,
                overwrites=overwrites,
                topic=f"Ticket sahibi: {interaction.user} ({interaction.user.id})",
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Kanal oluşturulamadı (yetki).", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Hata: {e}", ephemeral=True)
            return

        view = TicketKapatView()
        await kanal.send(
            content=f"{interaction.user.mention}" + (f" {destek_rol.mention}" if destek_rol else ""),
            embed=discord.Embed(
                title="🎫 Destek Talebi",
                description="Sorununu buraya yaz. Kapatmak için aşağıdaki butona tıkla.",
                color=discord.Color.blurple(),
            ),
            view=view,
        )

        try:
            db.ticket_ekle(guild.id, kanal.id, interaction.user.id)
        except Exception:
            logger.exception("Ticket DB'ye kaydedilemedi")
        await interaction.followup.send(f"✅ Ticket oluşturuldu: {kanal.mention}", ephemeral=True)


async def ticket_panel_gonder(bot, guild):
    kanal = ayarli_kanal(guild, "ticket_panel_kanal")
    if kanal is None:
        raise RuntimeError("Ticket panel kanalı bulunamadı. Panelden kanal seçip kaydet.")
    mesaj = BOT_AYARLARI.get("ticket_mesaj") or "Destek talebi oluşturmak için aşağıdaki butona tıkla."
    view = TicketAcView()
    await kanal.send(content=mesaj, view=view)
    bot.add_view(view)
    logger.info("Ticket paneli gönderildi: #%s", kanal.name)


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._yuklendi = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self._yuklendi:
            return
        self.bot.add_view(TicketAcView())
        self.bot.add_view(TicketKapatView())
        self._yuklendi = True
        logger.info("Ticket görünümleri kalıcı olarak yüklendi")


async def setup(bot):
    await bot.add_cog(Tickets(bot))
