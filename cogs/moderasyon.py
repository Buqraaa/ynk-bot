import json
import os
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_AYARLARI, ayarlari_kaydet, logger
from utils import ayarli_kanal

import db


def _mod_log_kanal(bot, guild):
    kanal = ayarli_kanal(guild, "log_kanal")
    return kanal


async def _log_gonder(bot, guild, embed):
    kanal = _mod_log_kanal(bot, guild)
    if kanal is None:
        return
    try:
        await kanal.send(embed=embed)
    except Exception:
        logger.exception("Mod log gonderilemedi")


class Moderasyon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- /sil ----------
    @app_commands.command(name="sil", description="Bulunduğun kanaldaki belirtilen sayıda mesajı siler")
    @app_commands.describe(miktar="Silinecek mesaj sayısı (örn: 10, 50, 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def sil(self, interaction: discord.Interaction, miktar: int):
        max_limit = int(BOT_AYARLARI.get("sil_max_limit", 100))
        if miktar < 1 or miktar > max_limit:
            await interaction.response.send_message(
                f"⚠️ Tek seferde **1** ile **{max_limit}** arasında mesaj "
                "silebilirsin!",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        silinenler = await interaction.channel.purge(limit=miktar)
        await interaction.followup.send(
            f"🗑️ **{len(silinenler)}** adet mesaj başarıyla temizlendi!",
            ephemeral=True,
        )

        embed = discord.Embed(
            title="🗑️ Toplu Mesaj Silindi",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Kanal", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        embed.add_field(name="Sayı", value=str(len(silinenler)), inline=True)
        await _log_gonder(self.bot, interaction.guild, embed)

    # ---------- /ban ----------
    @app_commands.command(name="ban", description="Bir üyeyi sunucudan yasaklar")
    @app_commands.describe(uye="Yasaklanacak üye", sebep="Yasaklama sebebi (isteğe bağlı)")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, uye: discord.Member, sebep: str = "Sebep belirtilmedi"):
        if uye == interaction.user:
            await interaction.response.send_message("❌ Kendini yasaklayamazsın.", ephemeral=True)
            return
        if uye.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ Bu üyeyi yasaklayamazsın (rol sırası).", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await uye.ban(reason=f"{interaction.user}: {sebep}")
        except discord.Forbidden:
            await interaction.followup.send("❌ Yetkim yetmiyor (bot rolü daha üstte olmalı).", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Yasaklama başarısız: {e}", ephemeral=True)
            return

        await interaction.followup.send(f"🔨 {uye.mention} yasaklandı. Sebep: {sebep}", ephemeral=True)

        embed = discord.Embed(title="🔨 Üye Yasaklandı (Ban)", color=discord.Color.red(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Üye", value=f"{uye} ({uye.id})", inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        await _log_gonder(self.bot, interaction.guild, embed)

    # ---------- /kick ----------
    @app_commands.command(name="kick", description="Bir üyeyi sunucudan atar")
    @app_commands.describe(uye="Atılacak üye", sebep="Atma sebebi (isteğe bağlı)")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, uye: discord.Member, sebep: str = "Sebep belirtilmedi"):
        if uye == interaction.user:
            await interaction.response.send_message("❌ Kendini atamazsın.", ephemeral=True)
            return
        if uye.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ Bu üyeyi atamazsın (rol sırası).", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await uye.kick(reason=f"{interaction.user}: {sebep}")
        except discord.Forbidden:
            await interaction.followup.send("❌ Yetkim yetmiyor.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Atma başarısız: {e}", ephemeral=True)
            return

        await interaction.followup.send(f"👢 {uye.mention} sunucudan atıldı. Sebep: {sebep}", ephemeral=True)

        embed = discord.Embed(title="👢 Üye Atıldı (Kick)", color=discord.Color.dark_orange(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Üye", value=f"{uye} ({uye.id})", inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        await _log_gonder(self.bot, interaction.guild, embed)

    # ---------- /timeout ----------
    @app_commands.command(name="timeout", description="Bir üyeyi belirtilen süre susturur (dakika)")
    @app_commands.describe(uye="Susturulacak üye", dakika="Süre (dakika)", sebep="Sebep (isteğe bağlı)")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, uye: discord.Member, dakika: int, sebep: str = "Sebep belirtilmedi"):
        if uye == interaction.user:
            await interaction.response.send_message("❌ Kendini susturamazsın.", ephemeral=True)
            return
        if dakika < 1 or dakika > 40320:  # max 28 gün
            await interaction.response.send_message("❌ Süre 1-40320 dakika arasında olmalı.", ephemeral=True)
            return
        if uye.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ Bu üyeyi susturamazsın (rol sırası).", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await uye.timeout(timedelta(minutes=dakika), reason=f"{interaction.user}: {sebep}")
        except discord.Forbidden:
            await interaction.followup.send("❌ Yetkim yetmiyor.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Susturma başarısız: {e}", ephemeral=True)
            return

        await interaction.followup.send(f"🔇 {uye.mention} **{dakika} dakika** susturuldu. Sebep: {sebep}", ephemeral=True)

        embed = discord.Embed(title="🔇 Üye Susturuldu (Timeout)", color=discord.Color.dark_grey(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Üye", value=f"{uye} ({uye.id})", inline=True)
        embed.add_field(name="Süre", value=f"{dakika} dk", inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        await _log_gonder(self.bot, interaction.guild, embed)

    # ---------- /uyari ----------
    @app_commands.command(name="uyari", description="Bir üyeye uyarı verir (kayıtlı)")
    @app_commands.describe(uye="Uyarılacak üye", sebep="Uyarı sebebi")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def uyari(self, interaction: discord.Interaction, uye: discord.Member, sebep: str):
        await interaction.response.defer(ephemeral=True)

        db.uyari_ekle(
            interaction.guild.id,
            uye.id,
            sebep,
            interaction.user.id,
        )
        liste = db.uyari_liste(interaction.guild.id, uye.id)
        sayi = len(liste)
        try:
            await uye.send(f"⚠️ **{interaction.guild.name}** sunucusunda uyarı aldın.\nSebep: {sebep}\nToplam uyarı: {sayi}")
        except discord.Forbidden:
            pass

        esik = int(BOT_AYARLARI.get("mod_uyari_limit", 0) or 0)
        if esik > 0 and sayi >= esik:
            try:
                await uye.timeout(timedelta(minutes=60), reason="Uyarı eşiği aşıldı (otomatik)")
                await interaction.followup.send(
                    f"🚫 {uye.mention} uyarı eşiğine ({esik}) ulaştı; 60 dk susturuldu.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                pass

        await interaction.followup.send(f"⚠️ {uye.mention} uyarıldı. (Toplam: {sayi})", ephemeral=True)

        embed = discord.Embed(title="⚠️ Üye Uyarıldı", color=discord.Color.yellow(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Üye", value=f"{uye} ({uye.id})", inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        embed.add_field(name="Toplam Uyarı", value=str(sayi), inline=True)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        await _log_gonder(self.bot, interaction.guild, embed)

    # ---------- /uyarilar ----------
    @app_commands.command(name="uyarilar", description="Bir üyenin uyarı geçmişini gösterir")
    @app_commands.describe(uye="Üye")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def uyarilar(self, interaction: discord.Interaction, uye: discord.Member):
        liste = db.uyari_liste(interaction.guild.id, uye.id)
        if not liste:
            await interaction.response.send_message(f"✅ {uye.mention} için uyarı kaydı yok.", ephemeral=True)
            return
        satirlar = [f"{i+1}. {w['sebep']} — {('<@' + str(w['yetkili']) + '>') if w['yetkili'] else '?'} ({str(w['tarih'])[:10]})" for i, w in enumerate(liste)]
        await interaction.response.send_message(
            f"⚠️ {uye.mention} uyarıları ({len(liste)}):\n" + "\n".join(satirlar),
            ephemeral=True,
        )

    # ---------- /uyari-temizle ----------
    @app_commands.command(name="uyari-temizle", description="Bir üyenin uyarılarını sıfırlar")
    @app_commands.describe(uye="Üye")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def uyari_temizle(self, interaction: discord.Interaction, uye: discord.Member):
        db.uyari_temizle(interaction.guild.id, uye.id)
        await interaction.response.send_message(f"🧹 {uye.mention} uyarıları temizlendi.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderasyon(bot))
