import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_AYARLARI
from utils import ayarli_kanal


def _tavsiye_kanalinda_mi(interaction):
    """Kanal ID'si varsa onu, yoksa kanal adini kontrol eder."""
    kanal = interaction.channel
    hedef_id = BOT_AYARLARI.get("tavsiye_kanal_id", 0)

    if hedef_id:
        try:
            hedef_id = int(hedef_id)
        except (TypeError, ValueError):
            hedef_id = 0

    if hedef_id:
        if getattr(kanal, "id", 0) == hedef_id:
            return True
        # Thread icinde kullanildiysa ust kanala bak.
        parent = getattr(kanal, "parent", None)
        return getattr(parent, "id", 0) == hedef_id

    hedef_ad = (BOT_AYARLARI.get("tavsiye_kanal") or "").strip().lower()
    kanal_adi = (getattr(kanal, "name", None) or "").strip().lower()
    return bool(hedef_ad) and kanal_adi == hedef_ad


class Tavsiye(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="tavsiye", description="Sunucu için tavsiyeni gönder"
    )
    @app_commands.describe(mesaj="Yazmak istediğin tavsiye")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def tavsiye(self, interaction: discord.Interaction, mesaj: str):
        if not _tavsiye_kanalinda_mi(interaction):
            hedef = ayarli_kanal(interaction.guild, "tavsiye_kanal")
            hedef_adi = (
                f"#{hedef.name}"
                if hedef is not None
                else f"#{BOT_AYARLARI.get('tavsiye_kanal', '')}"
            )
            await interaction.response.send_message(
                f"❌ Bu komutu sadece **{hedef_adi}** kanalında "
                "kullanabilirsin!",
                ephemeral=True,
            )
            return

        icerik = (
            f"**{BOT_AYARLARI['tavsiye_baslik']}**\n\n"
            f"**Tavsiye Sahibi:** {interaction.user.mention}\n"
            f"**Tavsiye:** {mesaj}"
        )
        await interaction.response.send_message(icerik)
        msg = await interaction.original_response()
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")


async def setup(bot):
    await bot.add_cog(Tavsiye(bot))
