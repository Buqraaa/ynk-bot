import discord
from discord import app_commands
from discord.ext import commands

from config import logger

EXTENSIONS = (
    "cogs.sayac",
    "cogs.tavsiye",
    "cogs.moderasyon",
    "cogs.log",
    "cogs.youtube",
)


class YNKBot(commands.Bot):
    def __init__(self, manager):
        intents = discord.Intents.default()
        intents.members = True
        intents.moderation = True
        intents.guilds = True
        intents.message_content = True

        super().__init__(command_prefix="!", intents=intents)
        self.manager = manager

    async def setup_hook(self):
        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                logger.info("Eklenti yüklendi: %s", extension)
            except Exception:
                logger.exception("Eklenti yüklenemedi: %s", extension)

        self.tree.on_error = self.on_app_command_error

        try:
            synced = await self.tree.sync()
            logger.info("Slash komutları senkronize edildi: %s", len(synced))
        except Exception:
            logger.exception("Komut senkronizasyon hatası")

    async def on_ready(self):
        self.manager.status = "Aktif (Çalışıyor)"
        logger.info(
            "Bot bağlandı: %s (%s)",
            self.user,
            self.user.id if self.user else "?",
        )
        print(f"[{self.user}] Discord sunucularına başarıyla bağlandı!")

    async def on_disconnect(self):
        if self.manager.status.startswith("Aktif"):
            self.manager.status = "Bağlantı koptu"
        logger.warning("Bot bağlantısı koptu.")

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ):
        if isinstance(error, app_commands.CommandOnCooldown):
            mesaj = (
                f"⏳ Bu komutu tekrar kullanmak için "
                f"**{int(error.retry_after)} saniye** beklemelisin!"
            )
        elif isinstance(error, app_commands.MissingPermissions):
            mesaj = "❌ Bu komutu kullanmak için gerekli yetkiye sahip değilsin!"
        else:
            logger.error("Slash komut hatası: %s", error, exc_info=error)
            mesaj = "❌ Bir hata oluştu. Lütfen daha sonra tekrar dene."

        try:
            if interaction.response.is_done():
                await interaction.followup.send(mesaj, ephemeral=True)
            else:
                await interaction.response.send_message(mesaj, ephemeral=True)
        except Exception:
            logger.exception("Hata mesajı gönderilemedi")


def create_bot(manager):
    return YNKBot(manager)
