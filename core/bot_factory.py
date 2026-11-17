import asyncio

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
        self._komut_sync_yapildi = False
        self._sync_task = None

    async def setup_hook(self):
        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                logger.info("Eklenti yüklendi: %s", extension)
            except Exception:
                logger.exception("Eklenti yüklenemedi: %s", extension)

        self.tree.on_error = self.on_app_command_error

    async def on_ready(self):
        self.manager.status = "Aktif (Çalışıyor)"
        logger.info(
            "Bot bağlandı: %s (%s)",
            self.user,
            self.user.id if self.user else "?",
        )
        print(f"[{self.user}] Discord sunucularına başarıyla bağlandı!")

        if not self._komut_sync_yapildi:
            self._komut_sync_yapildi = True
            self._sync_task = self.loop.create_task(
                self._komutlari_senkronize_et()
            )

    async def _komutlari_senkronize_et(self):
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(
                    "Komutlar senkronize edildi (%s): %s",
                    guild.name,
                    len(synced),
                )
            except asyncio.CancelledError:
                logger.info("Komut senkronizasyonu iptal edildi")
                raise
            except Exception:
                logger.exception(
                    "Komut senkronizasyon hatası (%s)", guild.name
                )

    async def close(self):
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception(
                    "Komut senkronizasyonu kapatılırken hata"
                )
        await super().close()

    async def on_guild_join(self, guild):
        try:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(
                "Yeni sunucuda komutlar senkronize edildi (%s): %s",
                guild.name,
                len(synced),
            )
        except Exception:
            logger.exception(
                "Yeni sunucu komut senkronizasyon hatası (%s)", guild.name
            )

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
