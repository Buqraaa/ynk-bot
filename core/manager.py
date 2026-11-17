import asyncio
import threading
import time

from config import logger, token_oku


class BotManager:
    """Discord botunu ayri bir thread + event loop icinde yonetir."""

    def __init__(self):
        self.bot = None
        self.thread = None
        self.loop = None
        self.status = "Kapalı"
        self._lock = threading.RLock()

    @property
    def is_running(self):
        return bool(
            self.thread
            and self.thread.is_alive()
            and self.bot
            and not self.bot.is_closed()
        )

    def start(self):
        with self._lock:
            if self.thread and self.thread.is_alive():
                return False
            token = token_oku()
            if not token:
                self.status = "Kapalı / Token yok (.env)"
                logger.error(
                    "DISCORD_TOKEN bulunamadi. .env dosyasindaki token'i kontrol et."
                )
                return False

            self.status = "Başlatılıyor..."
            self.thread = threading.Thread(
                target=self._run, args=(token,), daemon=True, name="ynk-bot"
            )
            self.thread.start()
            return True

    def _run(self, token):
        loop = asyncio.new_event_loop()
        self.loop = loop
        asyncio.set_event_loop(loop)
        try:
            from core.bot_factory import create_bot

            self.bot = create_bot(self)
            loop.run_until_complete(self.bot.start(token))
        except Exception:
            logger.exception("Bot başlatma hatası")
            self.status = "Kapalı / Hata"
        finally:
            try:
                if self.bot and not self.bot.is_closed():
                    loop.run_until_complete(self.bot.close())
            except Exception:
                logger.exception("Bot kapatma hatası (finally)")
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass

            self.bot = None
            self.loop = None
            if self.status != "Kapalı / Hata":
                self.status = "Kapalı"
            logger.info("Bot thread'i sonlandı. Durum: %s", self.status)

    def stop(self, timeout=15):
        with self._lock:
            bot = self.bot
            loop = self.loop
            thread = self.thread

        if bot and loop and not bot.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(bot.close(), loop)
            except Exception:
                logger.exception("Bot kapatma hatası")

        if thread and thread.is_alive():
            thread.join(timeout)

        with self._lock:
            self.bot = None
            self.loop = None
            if not thread or not thread.is_alive():
                self.thread = None
                self.status = "Kapalı"
            else:
                self.status = "Kapalı / Kapanıyor"
        return True

    def restart(self):
        with self._lock:
            self.status = "Yeniden başlatılıyor..."
            self.stop()
            time.sleep(1)
            return self.start()


bot_manager = BotManager()
