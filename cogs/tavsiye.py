import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_AYARLARI


class Tavsiye(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="tavsiye", description="Sunucu için tavsiyeni gönder"
    )
    @app_commands.describe(mesaj="Yazmak istediğin tavsiye")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def tavsiye(self, interaction: discord.Interaction, mesaj: str):
        hedef_tavsiye_kanal = BOT_AYARLARI["tavsiye_kanal"]
        kanal_adi = getattr(interaction.channel, "name", None) or ""

        if kanal_adi.lower() != hedef_tavsiye_kanal.lower():
            await interaction.response.send_message(
                f"❌ Bu komutu sadece **#{hedef_tavsiye_kanal}** kanalında "
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
