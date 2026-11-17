import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_AYARLARI


class Moderasyon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="sil",
        description="Bulunduğun kanaldaki belirtilen sayıda mesajı siler",
    )
    @app_commands.describe(miktar="Silinecek mesaj sayısı (Örn: 10, 50, 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def sil(self, interaction: discord.Interaction, miktar: int):
        max_limit = int(BOT_AYARLARI.get("sil_max_limit", 100))
        if miktar < 1 or miktar > max_limit:
            await interaction.response.send_message(
                f"❌ Tek seferde **1** ile **{max_limit}** arasında mesaj "
                "silebilirsin!",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        silinenler = await interaction.channel.purge(limit=miktar)
        await interaction.followup.send(
            f"🧹 **{len(silinenler)}** adet mesaj başarıyla temizlendi!",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Moderasyon(bot))
