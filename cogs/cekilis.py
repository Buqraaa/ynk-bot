import asyncio
import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands, ui
from discord.ext import commands

from config import BOT_AYARLARI, logger
import db


class CekilisButon(ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @ui.button(label="🎉 Katıl", style=discord.ButtonStyle.primary, custom_id="cekilis_katil")
    async def katil(self, interaction: discord.Interaction, button: ui.Button):
        db.giveaway_katil(self.giveaway_id, interaction.user.id)
        katilimcilar = db.giveaway_katilimcilar(self.giveaway_id)
        await interaction.response.send_message(
            f"✅ Katıldın! (Toplam: {len(katilimcilar)})", ephemeral=True
        )


class Cekilis(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._task = None

    async def cog_load(self):
        import asyncio
        self._task = asyncio.get_running_loop().create_task(self._cekilis_loop())

    async def cog_unload(self):
        if self._task:
            self._task.cancel()

    async def _cekilis_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            for g in db.aktif_giveawayler():
                try:
                    end_time = datetime.fromisoformat(g["end_time"])
                    if datetime.now(timezone.utc) >= end_time:
                        await self._bitir(g)
                except Exception:
                    logger.exception("Cekilis loop hatasi")
            await asyncio.sleep(10)

    async def _bitir(self, g):
        db.giveaway_bitir(g["id"])
        kanal = self.bot.get_channel(g["channel_id"])
        if kanal is None:
            return
        try:
            mesaj = await kanal.fetch_message(g["message_id"])
        except Exception:
            return

        katilimcilar = db.giveaway_katilimcilar(g["id"])
        if not katilimcilar:
            await kanal.send(f"🎉 Çekiliş bitti: **{g['prize']}** — Katılımcı yok!")
            return

        kazanan_sayisi = min(g["winners_count"], len(katilimcilar))
        kazananlar = random.sample(katilimcilar, kazanan_sayisi)

        kazanan_mention = ", ".join(f"<@{uid}>" for uid in kazananlar)
        await kanal.send(
            f"🎉 **Çekiliş bitti!**\n"
            f"🏆 Ödül: **{g['prize']}**\n"
            f"👑 Kazanan(lar): {kazanan_mention}\n"
            f"📊 Katılımcı: {len(katilimcilar)}"
        )

    @app_commands.command(name="cekilis", description="Çekiliş başlatır")
    @app_commands.describe(
        odul="Ödül (örn: Nitro, Rol, vb.)",
        sure="Süre (örn: 1h, 30m, 1d)",
        kazanan="Kazanan sayısı (varsayılan: 1)",
    )
    async def cekilis(self, interaction: discord.Interaction, odul: str, sure: str, kazanan: int = 1):
        # Süre parse
        try:
            birim = sure[-1].lower()
            miktar = int(sure[:-1])
            if birim == "s":
                delta = timedelta(seconds=miktar)
            elif birim == "m":
                delta = timedelta(minutes=miktar)
            elif birim == "h":
                delta = timedelta(hours=miktar)
            elif birim == "d":
                delta = timedelta(days=miktar)
            else:
                raise ValueError
        except (ValueError, IndexError):
            await interaction.response.send_message("❌ Süre formatı hatalı. Örn: 1h, 30m, 1d, 60s", ephemeral=True)
            return

        if miktar < 1:
            await interaction.response.send_message("❌ Süre 0'dan büyük olmalı.", ephemeral=True)
            return

        kazanan = max(1, min(20, kazanan))
        end_time = datetime.now(timezone.utc) + delta

        await interaction.response.defer()
        view = CekilisButon(0)  # geçici, ID sonra güncellenecek

        embed = discord.Embed(
            title="🎉 Çekiliş!",
            description=f"**Ödül:** {odul}\n**Kazanan:** {kazanan} kişi\n**Bitiş:** <t:{int(end_time.timestamp())}:R>\n\nKatılmak için butona tıkla!",
            color=discord.Color.gold(),
            timestamp=end_time,
        )
        embed.set_footer(text=f"Başlatan: {interaction.user.display_name}")

        mesaj = await interaction.channel.send(embed=embed, view=view)

        # Giveaway kaydet
        gid = db.giveaway_olustur(
            interaction.guild.id,
            interaction.channel.id,
            mesaj.id,
            odul,
            kazanan,
            interaction.user.id,
            end_time.isoformat(),
        )

        # View'ı güncelle
        view = CekilisButon(gid)
        await mesaj.edit(view=view)
        self.bot.add_view(view)

        await interaction.followup.send(f"🎉 Çekiliş başlatıldı! Bitiş: <t:{int(end_time.timestamp())}:R>")

    @app_commands.command(name="cekilis-bitir", description="Çekilişi erken bitirir")
    @app_commands.describe(mesaj_id="Çekiliş mesaj ID'si")
    async def cekilis_bitir(self, interaction: discord.Interaction, mesaj_id: str):
        try:
            mid = int(mesaj_id)
        except ValueError:
            await interaction.response.send_message("❌ Geçersiz mesaj ID.", ephemeral=True)
            return
        # giveaway bul
        aktifler = db.aktif_giveawayler()
        g = None
        for gg in aktifler:
            if gg["message_id"] == mid:
                g = gg
                break
        if g is None:
            await interaction.response.send_message("❌ Bu mesaj ID'si için aktif çekiliş bulunamadı.", ephemeral=True)
            return
        await interaction.response.defer()
        await self._bitir(g)
        await interaction.followup.send("✅ Çekiliş bitirildi.")

    @app_commands.command(name="cekilis-reroll", description="Çekilişi yeniden çeker")
    @app_commands.describe(mesaj_id="Çekiliş mesaj ID'si")
    async def cekilis_reroll(self, interaction: discord.Interaction, mesaj_id: str):
        try:
            mid = int(mesaj_id)
        except ValueError:
            await interaction.response.send_message("❌ Geçersiz mesaj ID.", ephemeral=True)
            return
        g = db.giveaway_getir(mid) if False else None
        # giveaway bul (ended de olabilir)
        aktifler = db.aktif_giveawayler()
        # ended olanları da kontrol et
        conn = db._baglanti()
        try:
            row = conn.execute("SELECT * FROM giveaways WHERE message_id=?", (mid,)).fetchone()
        finally:
            conn.close()
        if row is None:
            await interaction.response.send_message("❌ Çekiliş bulunamadı.", ephemeral=True)
            return
        g = dict(row)
        katilimcilar = db.giveaway_katilimcilar(g["id"])
        if not katilimcilar:
            await interaction.response.send_message("❌ Katılımcı yok.", ephemeral=True)
            return
        kazanan_sayisi = min(g["winners_count"], len(katilimcilar))
        kazananlar = random.sample(katilimcilar, kazanan_sayisi)
        kazanan_mention = ", ".join(f"<@{uid}>" for uid in kazananlar)
        await interaction.response.send_message(f"🔁 Yeniden çekim: {kazanan_mention}")


async def setup(bot):
    await bot.add_cog(Cekilis(bot))
