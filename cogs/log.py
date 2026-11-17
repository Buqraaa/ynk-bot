import discord
from discord.ext import commands

from config import BOT_AYARLARI, logger
from utils import kanal_bul


class Log(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        # DM'lerde guild olmaz; ayrica botlarin sildigi mesajlari loglamayalim.
        if message.guild is None or message.author.bot:
            return

        kanal = kanal_bul(message.guild, BOT_AYARLARI["log_kanal"])
        if kanal is None:
            return

        embed = discord.Embed(
            title="Message deleted",
            description=(
                f"**Kanal:** {message.channel.mention}\n"
                f"**Yazan:** {message.author}\n\n"
                f"**Silinen:**\n{message.content or '*İçerik yok*'}"
            ),
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(
            name=f"@{message.author.name}",
            icon_url=message.author.display_avatar.url,
        )

        try:
            await kanal.send(embed=embed)
        except Exception:
            logger.exception("Mesaj silme logu gönderilemedi")


async def setup(bot):
    await bot.add_cog(Log(bot))
