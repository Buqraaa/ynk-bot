import random
import asyncio
import datetime
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
from config import logger
from db import _baglanti, _DB_LOCK
import json

# ============ DB TABLES ============
def _ensure_tables():
    with _DB_LOCK:
        conn = _baglanti()
        conn.execute("""CREATE TABLE IF NOT EXISTS pets (
            user_id INTEGER PRIMARY KEY,
            pet_type TEXT NOT NULL,
            pet_name TEXT NOT NULL,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            hunger INTEGER DEFAULT 100,
            happiness INTEGER DEFAULT 100,
            last_feed TEXT,
            last_play TEXT,
            created_at TEXT,
            equipped TEXT DEFAULT '{}'
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS pet_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            item_type TEXT NOT NULL,
            quantity INTEGER DEFAULT 1
        )""")
        conn.commit()
        conn.close()

_ensure_tables()

# ============ PET TÜRLERİ ============
PET_TYPES = {
    "kedi": {
        "emoji": "🐱",
        "name": "Kedi",
        "stages": ["🐱", "😺", "😸", "😻", "🐈", "🐈‍⬛"],
        "stage_names": ["Yavru", "Genç", "Yetişkin", "Usta", "Efsane", "Mitik"],
        "xp_per_level": [0, 50, 150, 350, 700, 1200],
    },
    "kopek": {
        "emoji": "🐶",
        "name": "Köpek",
        "stages": ["🐶", "🐕", "🐕‍🦺", "🦮", "🐕", " (★)"],
        "stage_names": ["Yavru", "Genç", "Yetişkin", "Usta", "Efsane", "Mitik"],
        "xp_per_level": [0, 50, 150, 350, 700, 1200],
    },
    "kus": {
        "emoji": "🐦",
        "name": "Kuş",
        "stages": ["🐦", "🦜", "🦅", "🦉", " (★)", " (★★)"],
        "stage_names": ["Yavru", "Genç", "Yetişkin", "Usta", "Efsane", "Mitik"],
        "xp_per_level": [0, 50, 150, 350, 700, 1200],
    },
    "balik": {
        "emoji": "🐟",
        "name": "Balık",
        "stages": ["🐟", "🐠", "🐡", "🦈", " (★)", " (★★)"],
        "stage_names": ["Yavru", "Genç", "Yetişkin", "Usta", "Efsane", "Mitik"],
        "xp_per_level": [0, 50, 150, 350, 700, 1200],
    },
}

# ============ MAĞAZA EŞYALARI ============
SHOP_ITEMS = {
    # Yemekler (ucuz)
    "balik_yemi": {"name": "🐟 Balık Yemi", "type": "food", "price": 15, "hunger": 20, "happiness": 5, "desc": "Taze balık yemi"},
    "et": {"name": "🥩 Et", "type": "food", "price": 25, "hunger": 35, "happiness": 10, "desc": "Lezzetli et parçası"},
    "sut": {"name": "🥛 Süt", "type": "food", "price": 20, "hunger": 25, "happiness": 8, "desc": "Taze süt"},
    "premium_yem": {"name": "⭐ Premium Yem", "type": "food", "price": 60, "hunger": 60, "happiness": 25, "desc": "En kaliteli yem"},
    # Oyuncaklar
    "top": {"name": "⚽ Top", "type": "toy", "price": 40, "happiness": 20, "desc": "Eğlenceli top"},
    "ip": {"name": "🪢 İp", "type": "toy", "price": 35, "happiness": 15, "desc": "Çekme ipi"},
    "lazer": {"name": "🔴 Lazer", "type": "toy", "price": 50, "happiness": 30, "desc": "Lazer işaretçi"},
    # Kozmetikler (pahalı)
    "sapka_kirmizi": {"name": "🎩 Kırmızı Şapka", "type": "cosmetic", "slot": "head", "price": 200, "emoji": "🎩", "desc": "Şık kırmızı şapka"},
    "sapka_mavi": {"name": "🎩 Mavi Şapka", "type": "cosmetic", "slot": "head", "price": 200, "emoji": "🎩", "desc": "Şık mavi şapka"},
    "tac": {"name": "👑 Taç", "type": "cosmetic", "slot": "head", "price": 500, "emoji": "👑", "desc": "Kraliyet tacı"},
    "bandana": {"name": "🥽 Bandana", "type": "cosmetic", "slot": "head", "price": 150, "emoji": "🥽", "desc": "Havalı bandana"},
    "papyon": {"name": "🎀 Papyon", "type": "cosmetic", "slot": "neck", "price": 120, "emoji": "🎀", "desc": "Şık papyon"},
    "tasma_altin": {"name": "✨ Altın Tasma", "type": "cosmetic", "slot": "neck", "price": 300, "emoji": "✨", "desc": "Altın tasma"},
    "kanat": {"name": "🪽 Kanat", "type": "cosmetic", "slot": "back", "price": 400, "emoji": "🪽", "desc": "Melek kanatları"},
    "pelerin": {"name": "🦸 Pelerin", "type": "cosmetic", "slot": "back", "price": 350, "emoji": "🦸", "desc": "Süper kahraman pelerini"},
    "gunes_gozlugu": {"name": "🕶️ Güneş Gözlüğü", "type": "cosmetic", "slot": "face", "price": 180, "emoji": "🕶️", "desc": "Havalı güneş gözlüğü"},
    "maske": {"name": "🎭 Maske", "type": "cosmetic", "slot": "face", "price": 220, "emoji": "🎭", "desc": "Gizemli maske"},
}

# ============ HELPER FUNCTIONS ============
def _get_pet(user_id):
    with _DB_LOCK:
        conn = _baglanti()
        row = conn.execute("SELECT * FROM pets WHERE user_id=?", (user_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return dict(row)

def _create_pet(user_id, pet_type, pet_name):
    with _DB_LOCK:
        conn = _baglanti()
        conn.execute("INSERT OR REPLACE INTO pets (user_id, pet_type, pet_name, created_at, equipped) VALUES (?,?,?,?,?)",
                     (user_id, pet_type, pet_name, datetime.datetime.now().isoformat(), "{}"))
        conn.commit()
        conn.close()

def _get_inventory(user_id):
    with _DB_LOCK:
        conn = _baglanti()
        rows = conn.execute("SELECT * FROM pet_inventory WHERE user_id=?", (user_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

def _add_inventory(user_id, item_id, item_type, qty=1):
    with _DB_LOCK:
        conn = _baglanti()
        existing = conn.execute("SELECT id, quantity FROM pet_inventory WHERE user_id=? AND item_id=?", (user_id, item_id)).fetchone()
        if existing:
            conn.execute("UPDATE pet_inventory SET quantity=quantity+? WHERE id=?", (qty, existing["id"]))
        else:
            conn.execute("INSERT INTO pet_inventory (user_id, item_id, item_type, quantity) VALUES (?,?,?,?)", (user_id, item_id, item_type, qty))
        conn.commit()
        conn.close()

def _remove_inventory(user_id, item_id, qty=1):
    with _DB_LOCK:
        conn = _baglanti()
        existing = conn.execute("SELECT id, quantity FROM pet_inventory WHERE user_id=? AND item_id=?", (user_id, item_id)).fetchone()
        if existing:
            if existing["quantity"] <= qty:
                conn.execute("DELETE FROM pet_inventory WHERE id=?", (existing["id"],))
            else:
                conn.execute("UPDATE pet_inventory SET quantity=quantity-? WHERE id=?", (qty, existing["id"]))
            conn.commit()
        conn.close()

def _get_item_qty(user_id, item_id):
    with _DB_LOCK:
        conn = _baglanti()
        row = conn.execute("SELECT quantity FROM pet_inventory WHERE user_id=? AND item_id=?", (user_id, item_id)).fetchone()
        conn.close()
        return row["quantity"] if row else 0

def _render_pet(pet):
    """Pet'i görsel olarak render et"""
    ptype = PET_TYPES[pet["pet_type"]]
    level = pet["level"]
    stage_emoji = ptype["stages"][min(level - 1, len(ptype["stages"]) - 1)]
    equipped = json.loads(pet.get("equipped", "{}") or "{}")

    # Kozmetik emojileri
    head = equipped.get("head", "")
    neck = equipped.get("neck", "")
    back = equipped.get("back", "")
    face = equipped.get("face", "")

    # Görsel çizim
    lines = []
    # Üst (back + head)
    top = ""
    if back:
        top += back + " "
    top += stage_emoji
    if head:
        top += " " + head
    lines.append(top)
    if neck:
        lines.append(f"  {neck}")
    if face:
        lines.append(f"  {face}")

    visual = "\n".join(lines)
    stage_name = ptype["stage_names"][min(level - 1, len(ptype["stage_names"]) - 1)]
    return visual, stage_name

def _xp_for_level(level):
    if level >= 6:
        return 999999
    return PET_TYPES["kedi"]["xp_per_level"][level]  # same for all

def _add_pet_xp(user_id, amount):
    pet = _get_pet(user_id)
    if not pet:
        return
    new_xp = pet["xp"] + amount
    level = pet["level"]
    leveled_up = False
    while level < 6 and new_xp >= PET_TYPES[pet["pet_type"]]["xp_per_level"][level]:
        new_xp -= PET_TYPES[pet["pet_type"]]["xp_per_level"][level]
        level += 1
        leveled_up = True
    with _DB_LOCK:
        conn = _baglanti()
        conn.execute("UPDATE pets SET xp=?, level=? WHERE user_id=?", (new_xp, level, user_id))
        conn.commit()
        conn.close()
    return leveled_up, level

# ============ DM GÖNDERME (PET ALMA) ============
async def _send_naming_dm(user, pet_type):
    """Pet alındıktan sonra DM'den isim sor"""
    try:
        embed = discord.Embed(title="🐾 Yeni Pet!", color=0xff69b4)
        embed.description = f"Tebrikler! Bir **{PET_TYPES[pet_type]['name']}** sahiplendin!\n\nPetine bir isim ver. Bu mesaja **1 dakika** içinde cevap ver."
        embed.add_field(name="Pet Türü", value=f"{PET_TYPES[pet_type]['emoji']} {PET_TYPES[pet_type]['name']}", inline=True)
        await user.send(embed=embed)

        def check(m):
            return m.author == user and m.guild is None

        msg = await user.bot.wait_for("message", check=check, timeout=60)
        name = msg.content.strip()[:20]
        if not name:
            name = f"{PET_TYPES[pet_type]['name']}{random.randint(1,999)}"

        with _DB_LOCK:
            conn = _baglanti()
            conn.execute("UPDATE pets SET pet_name=? WHERE user_id=?", (name, user.id))
            conn.commit()
            conn.close()

        embed2 = discord.Embed(title="✅ Pet İsimlendirildi!", color=0x00ff00)
        embed2.description = f"Petinin adı artık **{name}**! 🎉\n\nKomutlar:\n`/pet` - Petini görüntüle\n`/pet-besle` - Besle\n`/pet-magaza` - Mağaza\n`/pet-oyna` - Oyna"
        await user.send(embed=embed2)
    except asyncio.TimeoutError:
        # İsim verilmezse rastgele isim
        name = f"{PET_TYPES[pet_type]['name']}{random.randint(1,999)}"
        with _DB_LOCK:
            conn = _baglanti()
            conn.execute("UPDATE pets SET pet_name=? WHERE user_id=?", (name, user.id))
            conn.commit()
            conn.close()
        await user.send(f"⏰ Süre doldu! Petinin adı **{name}** olarak ayarlandı.")
    except discord.Forbidden:
        pass  # DM kapalı

# ============ SELECT MENÜ (PET SEÇİMİ) ============
class PetSecimView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bitti = False

    @discord.ui.select(
        placeholder="🐾 Pet türü seç...",
        options=[
            discord.SelectOption(label="Kedi", value="kedi", emoji="🐱", description="Sevimli ve bağımsız"),
            discord.SelectOption(label="Köpek", value="kopek", emoji="🐶", description="Sadık ve enerjik"),
            discord.SelectOption(label="Kuş", value="kus", emoji="🐦", description="Renkli ve neşeli"),
            discord.SelectOption(label="Balık", value="balik", emoji="🐟", description="Sakin ve güzel"),
        ]
    )
    async def secim(self, interaction, select):
        if interaction.user.id != self.user_id or self.bitti:
            await interaction.response.send_message("Bu senin seçimin değil!", ephemeral=True)
            return
        self.bitti = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        pet_type = select.values[0]
        # Mevcut pet var mı?
        mevcut = _get_pet(self.user_id)
        if mevcut:
            await interaction.followup.send("❌ Zaten bir petin var! Petini değiştirmek için önce `/pet-birak` kullan.", ephemeral=True)
            return

        _create_pet(self.user_id, pet_type, "İsimsiz")
        embed = discord.Embed(title="🐾 Pet Sahiplenildi!", color=0xff69b4)
        embed.description = f"**{PET_TYPES[pet_type]['emoji']} {PET_TYPES[pet_type]['name']}** sahiplendin!\n\nDM'ne isim seçimi için mesaj gönderildi. DM'lerini kontrol et!"
        await interaction.followup.send(embed=embed)

        # DM gönder
        asyncio.ensure_future(_send_naming_dm(interaction.user, pet_type))

# ============ MAĞAZA VIEW ============
class MagazaView(View):
    def __init__(self, user_id, page=0):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.page = page
        self.items_per_page = 5
        self.item_ids = list(SHOP_ITEMS.keys())
        self._build()

    def _build(self):
        self.children.clear()
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.item_ids[start:end]

        for item_id in page_items:
            item = SHOP_ITEMS[item_id]
            btn = Button(label=f"{item['name']} - {item['price']} YNK", style=discord.ButtonStyle.secondary, custom_id=f"buy_{item_id}")
            btn.callback = self._make_buy_callback(item_id)
            self.add_item(btn)

        # Sayfa navigasyon
        if self.page > 0:
            prev_btn = Button(label="◀️ Önceki", style=discord.ButtonStyle.primary, custom_id="prev")
            prev_btn.callback = self._prev
            self.add_item(prev_btn)
        if end < len(self.item_ids):
            next_btn = Button(label="▶️ Sonraki", style=discord.ButtonStyle.primary, custom_id="next")
            next_btn.callback = self._next
            self.add_item(next_btn)

    def _make_buy_callback(self, item_id):
        async def callback(interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("Bu senin mağazan değil!", ephemeral=True)
                return
            item = SHOP_ITEMS[item_id]
            data = _get_coins(self.user_id)
            if data["coins"] < item["price"]:
                await interaction.response.send_message(f"❌ Yetersiz bakiye! Gerekli: {item['price']} YNK, Bakiyen: {_format_coins(data['coins'])} YNK", ephemeral=True)
                return
            _update_coins(self.user_id, -item["price"])
            _add_inventory(self.user_id, item_id, item["type"])
            await interaction.response.send_message(f"✅ **{item['name']}** satın alındı! (-{item['price']} YNK)", ephemeral=True)
        return callback

    async def _prev(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Bu senin mağazan değil!", ephemeral=True)
            return
        self.page -= 1
        self._build()
        await interaction.response.edit_message(view=self)

    async def _next(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Bu senin mağazan değil!", ephemeral=True)
            return
        self.page += 1
        self._build()
        await interaction.response.edit_message(view=self)

# ============ KUŞANMA VIEW ============
class EquipView(View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id
        self._build()

    def _build(self):
        self.children.clear()
        inv = _get_inventory(self.user_id)
        cosmetics = [i for i in inv if SHOP_ITEMS.get(i["item_id"], {}).get("type") == "cosmetic"]
        if not cosmetics:
            return
        options = []
        for inv_item in cosmetics:
            item = SHOP_ITEMS[inv_item["item_id"]]
            options.append(discord.SelectOption(
                label=f"{item['name']} ({inv_item['quantity']}x)",
                value=inv_item["item_id"],
                emoji=item.get("emoji", "🎨"),
            ))
        select = Select(placeholder="🎨 Kozmetik seç...", options=options[:25])
        select.callback = self._equip_callback
        self.add_item(select)

        # Çıkar butonları
        pet = _get_pet(self.user_id)
        if pet:
            equipped = json.loads(pet.get("equipped", "{}") or "{}")
            for slot, item_id in equipped.items():
                if item_id:
                    btn = Button(label=f"❌ {SHOP_ITEMS[item_id]['name']} çıkar", style=discord.ButtonStyle.danger, custom_id=f"unequip_{slot}")
                    btn.callback = self._make_unequip(slot)
                    self.add_item(btn)

    def _make_unequip(self, slot):
        async def callback(interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("Bu senin petin değil!", ephemeral=True)
                return
            pet = _get_pet(self.user_id)
            equipped = json.loads(pet.get("equipped", "{}") or "{}")
            item_id = equipped.get(slot)
            if item_id:
                equipped[slot] = None
                with _DB_LOCK:
                    conn = _baglanti()
                    conn.execute("UPDATE pets SET equipped=? WHERE user_id=?", (json.dumps(equipped), self.user_id))
                    conn.commit()
                    conn.close()
                await interaction.response.send_message(f"✅ {SHOP_ITEMS[item_id]['name']} çıkarıldı!", ephemeral=True)
                self._build()
                await interaction.message.edit(view=self)
        return callback

    async def _equip_callback(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Bu senin petin değil!", ephemeral=True)
            return
        item_id = interaction.data["values"][0]
        item = SHOP_ITEMS[item_id]
        slot = item["slot"]
        pet = _get_pet(self.user_id)
        equipped = json.loads(pet.get("equipped", "{}") or "{}")
        # Eski eşyayı envantere geri koy (çıkar)
        old_item = equipped.get(slot)
        if old_item:
            _add_inventory(self.user_id, old_item, "cosmetic")
        # Yeni eşyayı kuşan
        equipped[slot] = item_id
        with _DB_LOCK:
            conn = _baglanti()
            conn.execute("UPDATE pets SET equipped=? WHERE user_id=?", (json.dumps(equipped), self.user_id))
            conn.commit()
            conn.close()
        _remove_inventory(self.user_id, item_id, 1)
        await interaction.response.send_message(f"✅ {item['name']} kuşanıldı! (Slot: {slot})", ephemeral=True)
        self._build()
        await interaction.message.edit(view=self)

# ============ COG ============
class Pet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pet-sec", description="Bir pet sahiplen! (Kedi, Köpek, Kuş, Balık)")
    async def pet_sec(self, interaction: discord.Interaction):
        mevcut = _get_pet(interaction.user.id)
        if mevcut:
            await interaction.response.send_message("❌ Zaten bir petin var! `/pet` ile görüntüle.", ephemeral=True)
            return
        embed = discord.Embed(title="🐾 Pet Sahiplen", color=0xff69b4)
        embed.description = "Aşağıdan bir pet türü seç. Seçtikten sonra DM'den isim vereceksin!"
        embed.add_field(name="🐱 Kedi", value="Sevimli ve bağımsız", inline=True)
        embed.add_field(name="🐶 Köpek", value="Sadık ve enerjik", inline=True)
        embed.add_field(name="🐦 Kuş", value="Renkli ve neşeli", inline=True)
        embed.add_field(name="🐟 Balık", value="Sakin ve güzel", inline=True)
        view = PetSecimView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="pet", description="Petini görüntüle")
    async def pet(self, interaction: discord.Interaction):
        pet = _get_pet(interaction.user.id)
        if not pet:
            await interaction.response.send_message("❌ Henüz petin yok! `/pet-sec` ile sahiplen.", ephemeral=True)
            return
        visual, stage_name = _render_pet(pet)
        ptype = PET_TYPES[pet["pet_type"]]
        xp_needed = PET_TYPES[pet["pet_type"]]["xp_per_level"][pet["level"]] if pet["level"] < 6 else 0
        embed = discord.Embed(title=f"🐾 {pet['pet_name']}", color=0xff69b4)
        embed.description = f"```\n{visual}\n```"
        embed.add_field(name="Tür", value=f"{ptype['emoji']} {ptype['name']}", inline=True)
        embed.add_field(name="Seviye", value=f"⭐ {pet['level']} - {stage_name}", inline=True)
        embed.add_field(name="XP", value=f"{pet['xp']}/{xp_needed}", inline=True)
        embed.add_field(name="Açlık", value=f"🍖 {pet['hunger']}%", inline=True)
        embed.add_field(name="Mutluluk", value=f"😊 {pet['happiness']}%", inline=True)
        # Kozmetikler
        equipped = json.loads(pet.get("equipped", "{}") or "{}")
        cos_list = []
        for slot, item_id in equipped.items():
            if item_id:
                cos_list.append(f"{SHOP_ITEMS[item_id]['emoji']} {SHOP_ITEMS[item_id]['name']}")
        if cos_list:
            embed.add_field(name="Kozmetikler", value="\n".join(cos_list), inline=False)
        embed.set_footer(text=f"Oluşturulma: {pet['created_at'][:10]}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pet-besle", description="Petini besle")
    @app_commands.describe(yemek="Yemek türü (magazadan al)")
    async def pet_besle(self, interaction: discord.Interaction, yemek: str = "balik_yemi"):
        pet = _get_pet(interaction.user.id)
        if not pet:
            await interaction.response.send_message("❌ Petin yok! `/pet-sec` ile sahiplen.", ephemeral=True)
            return
        if yemek not in SHOP_ITEMS or SHOP_ITEMS[yemek]["type"] != "food":
            await interaction.response.send_message("❌ Geçersiz yemek! `/pet-magaza`'dan al.", ephemeral=True)
            return
        if _get_item_qty(interaction.user.id, yemek) < 1:
            await interaction.response.send_message(f"❌ Envanterinde **{SHOP_ITEMS[yemek]['name']}** yok! `/pet-magaza`'dan al.", ephemeral=True)
            return

        item = SHOP_ITEMS[yemek]
        _remove_inventory(interaction.user.id, yemek, 1)
        new_hunger = min(100, pet["hunger"] + item["hunger"])
        new_happy = min(100, pet["happiness"] + item["happiness"])
        xp_gain = item["hunger"] // 5
        with _DB_LOCK:
            conn = _baglanti()
            conn.execute("UPDATE pets SET hunger=?, happiness=? WHERE user_id=?", (new_hunger, new_happy, interaction.user.id))
            conn.commit()
            conn.close()

        leveled, new_level = _add_pet_xp(interaction.user.id, xp_gain)
        visual, stage_name = _render_pet(_get_pet(interaction.user.id))
        embed = discord.Embed(title=f"🍖 {pet['pet_name']} beslendi!", color=0x00ff00)
        embed.description = f"```\n{visual}\n```"
        embed.add_field(name="Yemek", value=item["name"], inline=True)
        embed.add_field(name="Açlık", value=f"{pet['hunger']}% → {new_hunger}%", inline=True)
        embed.add_field(name="Mutluluk", value=f"{pet['happiness']}% → {new_happy}%", inline=True)
        embed.add_field(name="XP", value=f"+{xp_gain}", inline=True)
        if leveled:
            embed.add_field(name="🎉 SEVİYE ATLADI!", value=f"Seviye {new_level} - {stage_name}!", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pet-oyna", description="Petinle oyna")
    async def pet_oyna(self, interaction: discord.Interaction):
        pet = _get_pet(interaction.user.id)
        if not pet:
            await interaction.response.send_message("❌ Petin yok!", ephemeral=True)
            return
        if pet["happiness"] >= 100:
            await interaction.response.send_message("😊 Petin zaten çok mutlu!", ephemeral=True)
            return
        xp_gain = random.randint(5, 15)
        new_happy = min(100, pet["happiness"] + random.randint(15, 30))
        new_hunger = max(0, pet["hunger"] - random.randint(5, 10))
        with _DB_LOCK:
            conn = _baglanti()
            conn.execute("UPDATE pets SET happiness=?, hunger=? WHERE user_id=?", (new_happy, new_hunger, interaction.user.id))
            conn.commit()
            conn.close()
        leveled, new_level = _add_pet_xp(interaction.user.id, xp_gain)
        visual, stage_name = _render_pet(_get_pet(interaction.user.id))
        embed = discord.Embed(title=f"🎾 {pet['pet_name']} ile oynadın!", color=0x3498db)
        embed.description = f"```\n{visual}\n```"
        embed.add_field(name="Mutluluk", value=f"{pet['happiness']}% → {new_happy}%", inline=True)
        embed.add_field(name="Açlık", value=f"{pet['hunger']}% → {new_hunger}%", inline=True)
        embed.add_field(name="XP", value=f"+{xp_gain}", inline=True)
        if leveled:
            embed.add_field(name="🎉 SEVİYE ATLADI!", value=f"Seviye {new_level} - {stage_name}!", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pet-magaza", description="Pet mağazası - yemek, oyuncak, kozmetik")
    async def pet_magaza(self, interaction: discord.Interaction):
        data = _get_coins(interaction.user.id)
        embed = discord.Embed(title="🏪 Pet Mağazası", color=0x9b59b6)
        embed.description = f"Bakiyen: 💰 {_format_coins(data['coins'])} YNK\nSayfa değiştir: ◀️ ▶️\nSatın almak için butona bas."
        view = MagazaView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="pet-envanter", description="Pet envanterini görüntüle")
    async def pet_envanter(self, interaction: discord.Interaction):
        inv = _get_inventory(interaction.user.id)
        if not inv:
            await interaction.response.send_message("📦 Envanterin boş! `/pet-magaza`'dan satın al.", ephemeral=True)
            return
        embed = discord.Embed(title="📦 Pet Envanteri", color=0x3498db)
        for item in inv:
            item_info = SHOP_ITEMS.get(item["item_id"], {})
            embed.add_field(name=item_info.get("name", item["item_id"]), value=f"Adet: {item['quantity']} | {item_info.get('desc', '')}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pet-kuşan", description="Kozmetik kuşan/çıkar")
    async def pet_kusan(self, interaction: discord.Interaction):
        pet = _get_pet(interaction.user.id)
        if not pet:
            await interaction.response.send_message("❌ Petin yok!", ephemeral=True)
            return
        inv = _get_inventory(interaction.user.id)
        cosmetics = [i for i in inv if SHOP_ITEMS.get(i["item_id"], {}).get("type") == "cosmetic"]
        if not cosmetics and not json.loads(pet.get("equipped", "{}") or "{}"):
            await interaction.response.send_message("❌ Kozmetik eşyan yok! `/pet-magaza`'dan al.", ephemeral=True)
            return
        embed = discord.Embed(title="🎨 Kozmetik Kuşan", color=0x9b59b6)
        embed.description = "Aşağıdan kozmetik seç veya çıkar."
        view = EquipView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="pet-birak", description="Petini bırak (dikkat: geri alınamaz!)")
    async def pet_birak(self, interaction: discord.Interaction):
        pet = _get_pet(interaction.user.id)
        if not pet:
            await interaction.response.send_message("❌ Petin yok!", ephemeral=True)
            return
        with _DB_LOCK:
            conn = _baglanti()
            conn.execute("DELETE FROM pets WHERE user_id=?", (interaction.user.id,))
            conn.execute("DELETE FROM pet_inventory WHERE user_id=?", (interaction.user.id,))
            conn.commit()
            conn.close()
        await interaction.response.send_message(f"😢 **{pet['pet_name']}** bırakıldı. Yeni pet almak için `/pet-sec` kullan.", ephemeral=True)

    @app_commands.command(name="pet-liste", description="Tüm pet türlerini ve seviyelerini göster")
    async def pet_liste(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🐾 Pet Türleri", color=0xff69b4)
        for key, ptype in PET_TYPES.items():
            stages = " → ".join(ptype["stages"])
            embed.add_field(name=f"{ptype['emoji']} {ptype['name']}", value=f"Seviyeler: {stages}\nXP: {ptype['xp_per_level']}", inline=False)
        embed.add_field(name="📦 Mağaza Eşyaları", value=f"Yemek: {len([i for i in SHOP_ITEMS.values() if i['type']=='food'])} çeşit\nOyuncak: {len([i for i in SHOP_ITEMS.values() if i['type']=='toy'])} çeşit\nKozmetik: {len([i for i in SHOP_ITEMS.values() if i['type']=='cosmetic'])} çeşit", inline=False)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Pet(bot))