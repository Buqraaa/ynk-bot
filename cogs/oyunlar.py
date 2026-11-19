import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from config import logger
from db import _baglanti, _DB_LOCK

def _ensure_tables():
    with _DB_LOCK:
        conn = _baglanti()
        conn.execute("""CREATE TABLE IF NOT EXISTS ynk_coins (
            user_id INTEGER PRIMARY KEY,
            coins INTEGER DEFAULT 100,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0,
            last_daily TEXT
        )""")
        conn.commit()
        conn.close()

_ensure_tables()

def _get_coins(user_id):
    with _DB_LOCK:
        conn = _baglanti()
        row = conn.execute("SELECT * FROM ynk_coins WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            conn.execute("INSERT INTO ynk_coins (user_id, coins) VALUES (?, 100)", (user_id,))
            conn.commit()
            row = conn.execute("SELECT * FROM ynk_coins WHERE user_id=?", (user_id,)).fetchone()
        result = dict(row)
        conn.close()
        return result

def _update_coins(user_id, delta, win=None):
    with _DB_LOCK:
        conn = _baglanti()
        _get_coins(user_id)
        if win is True:
            conn.execute("UPDATE ynk_coins SET coins=coins+?, wins=wins+1, streak=streak+1, best_streak=MAX(best_streak, streak+1) WHERE user_id=?", (delta, user_id))
        elif win is False:
            conn.execute("UPDATE ynk_coins SET coins=coins+?, losses=losses+1, streak=0 WHERE user_id=?", (delta, user_id))
        else:
            conn.execute("UPDATE ynk_coins SET coins=coins+? WHERE user_id=?", (delta, user_id))
        conn.commit()
        conn.close()

def _format_coins(n):
    if n >= 1000000:
        return f"{n/1000000:.1f}M"
    if n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)

# ============ PENALTI ATIŞI (ANİMASYONLU) ============
class PenaltiView(View):
    def __init__(self, user_id, bahis):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.bahis = bahis
        self.bitti = False

    async def _at(self, interaction, yon):
        if interaction.user.id != self.user_id or self.bitti:
            await interaction.response.send_message("Bu senin oyunun değil!", ephemeral=True)
            return
        self.bitti = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        kaleci = random.choice(["sol", "sag", "orta"])
        # Animasyon: top hareket ediyor
        frames = [
            ("⚽", "Top hareket ediyor..."),
            ("⚽➡️", "Kaleci hazırlanıyor..."),
            ("⚽🥅", "Top kaleye gidiyor!"),
        ]
        for emoji, msg in frames:
            embed = discord.Embed(title="⚽ Penaltı Atışı", color=0x3498db)
            embed.description = f"{emoji} {msg}"
            await interaction.message.edit(embed=embed)
            await asyncio.sleep(0.7)

        gol = yon != kaleci
        data = _get_coins(self.user_id)
        if gol:
            _update_coins(self.user_id, self.bahis, win=True)
            sonuc = "⚽ GOL! Kaleci yanlış köşeye atladı!"
            yeni = data["coins"] + self.bahis
            renk = 0x00ff00
        else:
            _update_coins(self.user_id, -self.bahis, win=False)
            sonuc = "🧤 KURTARILDI! Kaleci aynı köşeyi seçti!"
            yeni = data["coins"] - self.bahis
            renk = 0xff0000

        yon_emoji = "⬅️ Sol" if yon == "sol" else "➡️ Sağ" if yon == "sag" else "⬆️ Orta"
        kaleci_emoji = "⬅️ Sol" if kaleci == "sol" else "➡️ Sağ" if kaleci == "sag" else "⬆️ Orta"
        embed = discord.Embed(title="⚽ Penaltı Atışı", color=renk)
        embed.add_field(name="Senin seçimin", value=yon_emoji, inline=True)
        embed.add_field(name="Kalecinin seçimi", value=kaleci_emoji, inline=True)
        embed.add_field(name="Sonuç", value=sonuc, inline=False)
        embed.add_field(name="Bakiye", value=f"💰 {_format_coins(yeni)} YNK", inline=True)
        await interaction.message.edit(embed=embed, view=None)

    @discord.ui.button(label="⬅️ Sol", style=discord.ButtonStyle.primary)
    async def sol(self, interaction, button):
        await self._at(interaction, "sol")

    @discord.ui.button(label="⬆️ Orta", style=discord.ButtonStyle.success)
    async def orta(self, interaction, button):
        await self._at(interaction, "orta")

    @discord.ui.button(label="➡️ Sağ", style=discord.ButtonStyle.primary)
    async def sag(self, interaction, button):
        await self._at(interaction, "sag")

# ============ BLACKJACK (ANİMASYONLU) ============
class BlackjackView(View):
    def __init__(self, user_id, bahis, kartlar_oyuncu, kartlar_krupiye):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bahis = bahis
        self.oyuncu = kartlar_oyuncu
        self.krupiye = kartlar_krupiye
        self.bitti = False

    def _toplam(self, kartlar):
        toplam = 0
        as_sayisi = 0
        for k in kartlar:
            if k in ["J", "Q", "K"]:
                toplam += 10
            elif k == "A":
                toplam += 11
                as_sayisi += 1
            else:
                toplam += int(k)
        while toplam > 21 and as_sayisi > 0:
            toplam -= 10
            as_sayisi -= 1
        return toplam

    async def _guncelle(self, interaction, mesaj=""):
        toplam_o = self._toplam(self.oyuncu)
        toplam_k = self._toplam(self.krupiye)
        embed = discord.Embed(title="🃏 Blackjack", color=0x2f3136)
        embed.add_field(name="Senin kartların", value=f"{' '.join(self.oyuncu)} = **{toplam_o}**", inline=False)
        embed.add_field(name="Krupiyenin kartları", value=f"{' '.join(self.krupiye)} = **{toplam_k}**", inline=False)
        if mesaj:
            embed.add_field(name="Sonuç", value=mesaj, inline=False)
        data = _get_coins(self.user_id)
        embed.add_field(name="Bakiye", value=f"💰 {_format_coins(data['coins'])} YNK", inline=True)
        embed.add_field(name="Bahis", value=f"🎯 {_format_coins(self.bahis)} YNK", inline=True)
        await interaction.response.edit_message(embed=embed, view=None if self.bitti else self)

    @discord.ui.button(label="🃏 Kart Çek", style=discord.ButtonStyle.primary)
    async def hit(self, interaction, button):
        if interaction.user.id != self.user_id or self.bitti:
            await interaction.response.send_message("Bu senin oyunun değil!", ephemeral=True)
            return
        kartlar = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
        # Animasyon: kart çekiliyor
        await interaction.response.edit_message(embed=discord.Embed(title="🃏 Blackjack", description="🃏 Kart çekiliyor...", color=0x2f3136))
        await asyncio.sleep(0.8)
        self.oyuncu.append(random.choice(kartlar))
        toplam = self._toplam(self.oyuncu)
        if toplam > 21:
            self.bitti = True
            _update_coins(self.user_id, -self.bahis, win=False)
            await self._guncelle(interaction, "💥 BAT! 21'i geçtin. Kaybettin.")
        else:
            await self._guncelle(interaction)

    @discord.ui.button(label="✋ Dur", style=discord.ButtonStyle.success)
    async def stand(self, interaction, button):
        if interaction.user.id != self.user_id or self.bitti:
            await interaction.response.send_message("Bu senin oyunun değil!", ephemeral=True)
            return
        self.bitti = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        # Animasyon: krupiye kart çekiyor
        kartlar = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
        while self._toplam(self.krupiye) < 17:
            await interaction.message.edit(embed=discord.Embed(title="🃏 Blackjack", description="🤖 Krupiye kart çekiyor...", color=0x2f3136))
            await asyncio.sleep(0.7)
            self.krupiye.append(random.choice(kartlar))
        toplam_o = self._toplam(self.oyuncu)
        toplam_k = self._toplam(self.krupiye)
        if toplam_k > 21:
            _update_coins(self.user_id, self.bahis, win=True)
            await self._guncelle(interaction, "🎉 Krupiye battı! Kazandın!")
        elif toplam_o > toplam_k:
            _update_coins(self.user_id, self.bahis, win=True)
            await self._guncelle(interaction, "🎉 Kazandın!")
        elif toplam_o < toplam_k:
            _update_coins(self.user_id, -self.bahis, win=False)
            await self._guncelle(interaction, "❌ Kaybettin!")
        else:
            await self._guncelle(interaction, "🤝 Berabere! Bahis iade.")

# ============ SLOT MAKİNESİ (ANİMASYONLU) ============
class SlotView(View):
    def __init__(self, user_id, bahis):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.bahis = bahis
        self.bitti = False

    @discord.ui.button(label="🎰 Çevir", style=discord.ButtonStyle.danger)
    async def cevir(self, interaction, button):
        if interaction.user.id != self.user_id or self.bitti:
            await interaction.response.send_message("Bu senin oyunun değil!", ephemeral=True)
            return
        self.bitti = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        semboller = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]
        # Animasyon: 4 frame döndür
        for _ in range(4):
            s1, s2, s3 = random.choice(semboller), random.choice(semboller), random.choice(semboller)
            embed = discord.Embed(title="🎰 Slot Makinesi", color=0x9b59b6)
            embed.description = f"**{s1} | {s2} | {s3}**"
            embed.add_field(name="Durum", value="🔄 Çevriliyor...", inline=False)
            await interaction.message.edit(embed=embed)
            await asyncio.sleep(0.5)

        # Final sonuç
        s1, s2, s3 = random.choice(semboller), random.choice(semboller), random.choice(semboller)
        if s1 == s2 == s3:
            if s1 == "7️⃣":
                carpan = 10
            elif s1 == "💎":
                carpan = 7
            elif s1 == "⭐":
                carpan = 5
            else:
                carpan = 3
            kazanc = self.bahis * carpan
            _update_coins(self.user_id, kazanc, win=True)
            sonuc = f"🎉 JACKPOT! x{carpan} = {_format_coins(kazanc)} YNK kazandın!"
            renk = 0xffd700
        elif s1 == s2 or s2 == s3 or s1 == s3:
            kazanc = self.bahis
            _update_coins(self.user_id, kazanc, win=True)
            sonuc = f"✨ İki eşleşme! {_format_coins(kazanc)} YNK kazandın!"
            renk = 0x00ff00
        else:
            _update_coins(self.user_id, -self.bahis, win=False)
            sonuc = f"❌ Kaybettin! {_format_coins(self.bahis)} YNK kaybettin."
            renk = 0xff0000
        data = _get_coins(self.user_id)
        embed = discord.Embed(title="🎰 Slot Makinesi", color=renk)
        embed.add_field(name="Sonuç", value=f"**{s1} | {s2} | {s3}**", inline=False)
        embed.add_field(name="Durum", value=sonuc, inline=False)
        embed.add_field(name="Bakiye", value=f"💰 {_format_coins(data['coins'])} YNK", inline=True)
        await interaction.message.edit(embed=embed, view=None)

# ============ COINFLIP (ANİMASYONLU) ============
class CoinflipView(View):
    def __init__(self, user_id, bahis):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.bahis = bahis
        self.bitti = False

    async def _sec(self, interaction, secim):
        if interaction.user.id != self.user_id or self.bitti:
            await interaction.response.send_message("Bu senin oyunun değil!", ephemeral=True)
            return
        self.bitti = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        # Animasyon: para döndürülüyor
        frames = ["🪙", "👑", "🦅", "👑", "🦅", "🪙"]
        for f in frames:
            embed = discord.Embed(title="🪙 Yazı Tura", color=0xf1c40f)
            embed.description = f"**{f}** Döndürülüyor..."
            await interaction.message.edit(embed=embed)
            await asyncio.sleep(0.4)

        sonuc = random.choice(["yazi", "tura"])
        if secim == sonuc:
            _update_coins(self.user_id, self.bahis, win=True)
            msg = f"🎉 Doğru tahmin! {_format_coins(self.bahis)} YNK kazandın!"
            renk = 0x00ff00
        else:
            _update_coins(self.user_id, -self.bahis, win=False)
            msg = f"❌ Yanlış tahmin! {_format_coins(self.bahis)} YNK kaybettin."
            renk = 0xff0000
        data = _get_coins(self.user_id)
        embed = discord.Embed(title="🪙 Yazı Tura", color=renk)
        embed.add_field(name="Senin seçimin", value="👑 Yazı" if secim == "yazi" else "🦅 Tura", inline=True)
        embed.add_field(name="Sonuç", value="👑 Yazı" if sonuc == "yazi" else "🦅 Tura", inline=True)
        embed.add_field(name="Durum", value=msg, inline=False)
        embed.add_field(name="Bakiye", value=f"💰 {_format_coins(data['coins'])} YNK", inline=True)
        await interaction.message.edit(embed=embed, view=None)

    @discord.ui.button(label="👑 Yazı", style=discord.ButtonStyle.primary)
    async def yazi(self, interaction, button):
        await self._sec(interaction, "yazi")

    @discord.ui.button(label="🦅 Tura", style=discord.ButtonStyle.success)
    async def tura(self, interaction, button):
        await self._sec(interaction, "tura")

# ============ DICE (ANİMASYONLU) ============
class DiceView(View):
    def __init__(self, user_id, bahis, hedef):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.bahis = bahis
        self.hedef = hedef
        self.bitti = False

    @discord.ui.button(label="🎲 Zar At", style=discord.ButtonStyle.danger)
    async def at(self, interaction, button):
        if interaction.user.id != self.user_id or self.bitti:
            await interaction.response.send_message("Bu senin oyunun değil!", ephemeral=True)
            return
        self.bitti = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        # Animasyon: zar döndürülüyor
        for _ in range(5):
            zar = random.randint(1, 6)
            embed = discord.Embed(title="🎲 Zar Oyunu", color=0xe74c3c)
            embed.description = f"**🎲 {zar}** Döndürülüyor..."
            await interaction.message.edit(embed=embed)
            await asyncio.sleep(0.4)

        zar = random.randint(1, 6)
        kazandi = (self.hedef == "yuksek" and zar >= 4) or (self.hedef == "dusuk" and zar <= 3)
        if kazandi:
            _update_coins(self.user_id, self.bahis, win=True)
            msg = f"🎉 Kazandın! Zar: {zar}"
            renk = 0x00ff00
        else:
            _update_coins(self.user_id, -self.bahis, win=False)
            msg = f"❌ Kaybettin! Zar: {zar}"
            renk = 0xff0000
        data = _get_coins(self.user_id)
        embed = discord.Embed(title="🎲 Zar Oyunu", color=renk)
        embed.add_field(name="Hedefin", value="⬆️ Yüksek (4-6)" if self.hedef == "yuksek" else "⬇️ Düşük (1-3)", inline=True)
        embed.add_field(name="Zar", value=f"**{zar}**", inline=True)
        embed.add_field(name="Sonuç", value=msg, inline=False)
        embed.add_field(name="Bakiye", value=f"💰 {_format_coins(data['coins'])} YNK", inline=True)
        await interaction.message.edit(embed=embed, view=None)

# ============ RPS (ANİMASYONLU) ============
class RPSView(View):
    def __init__(self, user_id, bahis):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.bahis = bahis
        self.bitti = False

    async def _sec(self, interaction, secim):
        if interaction.user.id != self.user_id or self.bitti:
            await interaction.response.send_message("Bu senin oyunun değil!", ephemeral=True)
            return
        self.bitti = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        emoji = {"tas": "🪨", "kagit": "📄", "makas": "✂️"}
        # Animasyon: bot düşünüyor
        frames = ["🤔", "✊", "✋", "✌️", "🤔", "✊"]
        for f in frames:
            embed = discord.Embed(title="✊✋✌️ Taş Kağıt Makas", color=0x9b59b6)
            embed.description = f"**{f}** Bot düşünüyor..."
            await interaction.message.edit(embed=embed)
            await asyncio.sleep(0.35)

        bot_secim = random.choice(["tas", "kagit", "makas"])
        if secim == bot_secim:
            _update_coins(self.user_id, 0)
            msg = "🤝 Berabere!"
            renk = 0xffff00
        elif (secim == "tas" and bot_secim == "makas") or (secim == "kagit" and bot_secim == "tas") or (secim == "makas" and bot_secim == "kagit"):
            _update_coins(self.user_id, self.bahis, win=True)
            msg = f"🎉 Kazandın! +{_format_coins(self.bahis)} YNK"
            renk = 0x00ff00
        else:
            _update_coins(self.user_id, -self.bahis, win=False)
            msg = f"❌ Kaybettin! -{_format_coins(self.bahis)} YNK"
            renk = 0xff0000
        data = _get_coins(self.user_id)
        embed = discord.Embed(title="✊✋✌️ Taş Kağıt Makas", color=renk)
        embed.add_field(name="Sen", value=f"{emoji[secim]} {secim.title()}", inline=True)
        embed.add_field(name="Bot", value=f"{emoji[bot_secim]} {bot_secim.title()}", inline=True)
        embed.add_field(name="Sonuç", value=msg, inline=False)
        embed.add_field(name="Bakiye", value=f"💰 {_format_coins(data['coins'])} YNK", inline=True)
        await interaction.message.edit(embed=embed, view=None)

    @discord.ui.button(label="🪨 Taş", style=discord.ButtonStyle.primary)
    async def tas(self, interaction, button):
        await self._sec(interaction, "tas")

    @discord.ui.button(label="📄 Kağıt", style=discord.ButtonStyle.success)
    async def kagit(self, interaction, button):
        await self._sec(interaction, "kagit")

    @discord.ui.button(label="✂️ Makas", style=discord.ButtonStyle.danger)
    async def makas(self, interaction, button):
        await self._sec(interaction, "makas")

# ============ COG ============
class Oyunlar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="bakiye", description="YNK coin bakiyeni ve istatistiklerini gösterir")
    async def bakiye(self, interaction: discord.Interaction):
        data = _get_coins(interaction.user.id)
        embed = discord.Embed(title=f"💰 {interaction.user.display_name} - YNK Cüzdan", color=0xffd700)
        embed.add_field(name="Coin", value=f"**{_format_coins(data['coins'])}** YNK", inline=True)
        embed.add_field(name="Kazanma", value=f"🏆 {data['wins']}", inline=True)
        embed.add_field(name="Kaybetme", value=f"💔 {data['losses']}", inline=True)
        embed.add_field(name="Seri", value=f"🔥 {data['streak']} (En iyi: {data['best_streak']})", inline=True)
        if data["wins"] + data["losses"] > 0:
            oran = data["wins"] / (data["wins"] + data["losses"]) * 100
            embed.add_field(name="Kazanma Oranı", value=f"%{oran:.1f}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="gunluk", description="Günlük 50 YNK coin ödülünü al")
    async def gunluk(self, interaction: discord.Interaction):
        import datetime
        data = _get_coins(interaction.user.id)
        today = datetime.date.today().isoformat()
        if data.get("last_daily") == today:
            await interaction.response.send_message("❌ Bugün zaten ödülünü aldın! Yarın gel.", ephemeral=True)
            return
        with _DB_LOCK:
            conn = _baglanti()
            conn.execute("UPDATE ynk_coins SET coins=coins+50, last_daily=? WHERE user_id=?", (today, interaction.user.id))
            conn.commit()
            conn.close()
        yeni = data["coins"] + 50
        embed = discord.Embed(title="🎁 Günlük Ödül", color=0x00ff00)
        embed.description = f"**50 YNK** coin kazandın! Bakiye: {_format_coins(yeni)} YNK"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="penalti", description="Penaltı atışı oyunu - bahis yap ve gol at!")
    @app_commands.describe(bahis="Bahis miktarı (YNK coin)")
    async def penalti(self, interaction: discord.Interaction, bahis: int = 10):
        data = _get_coins(interaction.user.id)
        if bahis < 1:
            await interaction.response.send_message("❌ Bahis en az 1 YNK olmalı.", ephemeral=True)
            return
        if data["coins"] < bahis:
            await interaction.response.send_message(f"❌ Yetersiz bakiye! Bakiyen: {_format_coins(data['coins'])} YNK", ephemeral=True)
            return
        embed = discord.Embed(title="⚽ Penaltı Atışı", color=0x3498db)
        embed.description = "Kaleciyi geç! Hangi köşeye atacaksın?"
        embed.add_field(name="Bahis", value=f"🎯 {_format_coins(bahis)} YNK", inline=True)
        embed.add_field(name="Bakiye", value=f"💰 {_format_coins(data['coins'])} YNK", inline=True)
        view = PenaltiView(interaction.user.id, bahis)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="blackjack", description="Blackjack oyunu - krupiyeyi geç!")
    @app_commands.describe(bahis="Bahis miktarı (YNK coin)")
    async def blackjack(self, interaction: discord.Interaction, bahis: int = 10):
        data = _get_coins(interaction.user.id)
        if bahis < 1:
            await interaction.response.send_message("❌ Bahis en az 1 YNK olmalı.", ephemeral=True)
            return
        if data["coins"] < bahis:
            await interaction.response.send_message(f"❌ Yetersiz bakiye! Bakiyen: {_format_coins(data['coins'])} YNK", ephemeral=True)
            return
        kartlar = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
        oyuncu = [random.choice(kartlar), random.choice(kartlar)]
        krupiye = [random.choice(kartlar), random.choice(kartlar)]
        view = BlackjackView(interaction.user.id, bahis, oyuncu, krupiye)
        embed = discord.Embed(title="🃏 Blackjack", color=0x2f3136)
        embed.add_field(name="Senin kartların", value=f"{' '.join(oyuncu)}", inline=False)
        embed.add_field(name="Krupiyenin kartları", value=f"{krupiye[0]} ❓", inline=False)
        embed.add_field(name="Bahis", value=f"🎯 {_format_coins(bahis)} YNK", inline=True)
        embed.add_field(name="Bakiye", value=f"💰 {_format_coins(data['coins'])} YNK", inline=True)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="slot", description="Slot makinesi - jackpot'u vur!")
    @app_commands.describe(bahis="Bahis miktarı (YNK coin)")
    async def slot(self, interaction: discord.Interaction, bahis: int = 10):
        data = _get_coins(interaction.user.id)
        if bahis < 1:
            await interaction.response.send_message("❌ Bahis en az 1 YNK olmalı.", ephemeral=True)
            return
        if data["coins"] < bahis:
            await interaction.response.send_message(f"❌ Yetersiz bakiye! Bakiyen: {_format_coins(data['coins'])} YNK", ephemeral=True)
            return
        embed = discord.Embed(title="🎰 Slot Makinesi", color=0x9b59b6)
        embed.description = "Çevir butonuna bas!"
        embed.add_field(name="Bahis", value=f"🎯 {_format_coins(bahis)} YNK", inline=True)
        embed.add_field(name="Bakiye", value=f"💰 {_format_coins(data['coins'])} YNK", inline=True)
        view = SlotView(interaction.user.id, bahis)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="yazi-tura", description="Yazı tura oyunu - bahis yap!")
    @app_commands.describe(bahis="Bahis miktarı (YNK coin)")
    async def yazi_tura(self, interaction: discord.Interaction, bahis: int = 10):
        data = _get_coins(interaction.user.id)
        if bahis < 1:
            await interaction.response.send_message("❌ Bahis en az 1 YNK olmalı.", ephemeral=True)
            return
        if data["coins"] < bahis:
            await interaction.response.send_message(f"❌ Yetersiz bakiye! Bakiyen: {_format_coins(data['coins'])} YNK", ephemeral=True)
            return
        embed = discord.Embed(title="🪙 Yazı Tura", color=0xf1c40f)
        embed.description = "Yazı mı tura mı?"
        embed.add_field(name="Bahis", value=f"🎯 {_format_coins(bahis)} YNK", inline=True)
        embed.add_field(name="Bakiye", value=f"💰 {_format_coins(data['coins'])} YNK", inline=True)
        view = CoinflipView(interaction.user.id, bahis)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="zar", description="Zar oyunu - yüksek mi düşük mü?")
    @app_commands.describe(bahis="Bahis miktarı (YNK coin)", tahmin="yuksek (4-6) veya dusuk (1-3)")
    @app_commands.choices(tahmin=[
        app_commands.Choice(name="⬆️ Yüksek (4-6)", value="yuksek"),
        app_commands.Choice(name="⬇️ Düşük (1-3)", value="dusuk"),
    ])
    async def zar(self, interaction: discord.Interaction, bahis: int = 10, tahmin: str = "yuksek"):
        data = _get_coins(interaction.user.id)
        if bahis < 1:
            await interaction.response.send_message("❌ Bahis en az 1 YNK olmalı.", ephemeral=True)
            return
        if data["coins"] < bahis:
            await interaction.response.send_message(f"❌ Yetersiz bakiye! Bakiyen: {_format_coins(data['coins'])} YNK", ephemeral=True)
            return
        embed = discord.Embed(title="🎲 Zar Oyunu", color=0xe74c3c)
        embed.description = "Zar atmak için butona bas!"
        embed.add_field(name="Tahmin", value="⬆️ Yüksek (4-6)" if tahmin == "yuksek" else "⬇️ Düşük (1-3)", inline=True)
        embed.add_field(name="Bahis", value=f"🎯 {_format_coins(bahis)} YNK", inline=True)
        embed.add_field(name="Bakiye", value=f"💰 {_format_coins(data['coins'])} YNK", inline=True)
        view = DiceView(interaction.user.id, bahis, tahmin)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="rps", description="Taş Kağıt Makas - bot'a karşı oyna!")
    @app_commands.describe(bahis="Bahis miktarı (YNK coin)")
    async def rps(self, interaction: discord.Interaction, bahis: int = 10):
        data = _get_coins(interaction.user.id)
        if bahis < 1:
            await interaction.response.send_message("❌ Bahis en az 1 YNK olmalı.", ephemeral=True)
            return
        if data["coins"] < bahis:
            await interaction.response.send_message(f"❌ Yetersiz bakiye! Bakiyen: {_format_coins(data['coins'])} YNK", ephemeral=True)
            return
        embed = discord.Embed(title="✊✋✌️ Taş Kağıt Makas", color=0x9b59b6)
        embed.description = "Seçimini yap!"
        embed.add_field(name="Bahis", value=f"🎯 {_format_coins(bahis)} YNK", inline=True)
        embed.add_field(name="Bakiye", value=f"💰 {_format_coins(data['coins'])} YNK", inline=True)
        view = RPSView(interaction.user.id, bahis)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="liderlik", description="YNK coin liderlik tablosu")
    async def liderlik(self, interaction: discord.Interaction):
        with _DB_LOCK:
            conn = _baglanti()
            rows = conn.execute("SELECT user_id, coins, wins, losses, best_streak FROM ynk_coins ORDER BY coins DESC LIMIT 10").fetchall()
            conn.close()
        embed = discord.Embed(title="🏆 YNK Coin Liderlik Tablosu", color=0xffd700)
        if not rows:
            embed.description = "Henüz kimse oynamadı!"
        else:
            for i, r in enumerate(rows, 1):
                try:
                    user = await self.bot.fetch_user(r["user_id"])
                    name = user.display_name
                except:
                    name = f"Kullanıcı {r['user_id']}"
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                embed.add_field(name=f"{medal} {name}", value=f"💰 {_format_coins(r['coins'])} YNK | 🏆 {r['wins']}W/{r['losses']}L | 🔥 {r['best_streak']}", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="transfer", description="Başka kullanıcıya YNK coin gönder")
    @app_commands.describe(kullanici="Coin gönderilecek kullanıcı", miktar="Gönderilecek miktar")
    async def transfer(self, interaction: discord.Interaction, kullanici: discord.User, miktar: int):
        if kullanici.id == interaction.user.id:
            await interaction.response.send_message("❌ Kendine coin gönderemezsin!", ephemeral=True)
            return
        if miktar < 1:
            await interaction.response.send_message("❌ Miktar en az 1 olmalı.", ephemeral=True)
            return
        data = _get_coins(interaction.user.id)
        if data["coins"] < miktar:
            await interaction.response.send_message(f"❌ Yetersiz bakiye! Bakiyen: {_format_coins(data['coins'])} YNK", ephemeral=True)
            return
        _update_coins(interaction.user.id, -miktar)
        _update_coins(kullanici.id, miktar)
        embed = discord.Embed(title="💸 Transfer", color=0x00ff00)
        embed.description = f"**{interaction.user.display_name}** → **{kullanici.display_name}**: {_format_coins(miktar)} YNK gönderildi!"
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Oyunlar(bot))