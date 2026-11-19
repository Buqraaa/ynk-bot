import random
import asyncio
import datetime
import json
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
from config import logger
from db import _baglanti, _DB_LOCK

# ============ DB TABLES ============
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
            last_decay TEXT,
            channel_id INTEGER DEFAULT 0,
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
        try:
            conn.execute("ALTER TABLE pets ADD COLUMN channel_id INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE pets ADD COLUMN last_decay TEXT")
            conn.commit()
        except Exception:
            pass
        conn.commit()
        conn.close()

_ensure_tables()

# ============ HELPER FUNCTIONS ============
def _format_coins(n):
    if n >= 1000000: return f"{n/1000000:.1f}M"
    if n >= 1000: return f"{n/1000:.1f}K"
    return str(n)

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

def _get_pet(user_id):
    with _DB_LOCK:
        conn = _baglanti()
        row = conn.execute("SELECT * FROM pets WHERE user_id=?", (user_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

def _create_pet(user_id, pet_type, pet_name, channel_id=0):
    now = datetime.datetime.now().isoformat()
    with _DB_LOCK:
        conn = _baglanti()
        conn.execute("INSERT OR REPLACE INTO pets (user_id, pet_type, pet_name, created_at, equipped, last_decay, channel_id) VALUES (?,?,?,?,?,?,?)",
                     (user_id, pet_type, pet_name, now, "{}", now, channel_id))
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

def _is_pet_channel(user_id, channel_id):
    """Kullanıcının kişisel pet kanalı mı?"""
    pet = _get_pet(user_id)
    if not pet:
        return False
    return pet.get("channel_id", 0) == channel_id

# ============ PET TÜRLERİ ============
PET_TYPES = {
    "kedi": {"emoji": "🐱", "name": "Kedi", "stages": ["🐱", "😺", "😸", "😻", "🐈", "🐈‍⬛"],
             "stage_names": ["Yavru", "Genç", "Yetişkin", "Usta", "Efsane", "Mitik"],
             "xp_per_level": [0, 50, 150, 350, 700, 1200], "decay_rate": 3.5},
    "kopek": {"emoji": "🐶", "name": "Köpek", "stages": ["🐶", "🐕", "🐕‍🦺", "🦮", "🐕", " (★)"],
              "stage_names": ["Yavru", "Genç", "Yetişkin", "Usta", "Efsane", "Mitik"],
              "xp_per_level": [0, 50, 150, 350, 700, 1200], "decay_rate": 4.0},
    "kus": {"emoji": "🐦", "name": "Kuş", "stages": ["🐦", "🦜", "🦅", "🦉", " (★)", " (★★)"],
            "stage_names": ["Yavru", "Genç", "Yetişkin", "Usta", "Efsane", "Mitik"],
            "xp_per_level": [0, 50, 150, 350, 700, 1200], "decay_rate": 4.5},
    "balik": {"emoji": "🐟", "name": "Balık", "stages": ["🐟", "🐠", "🐡", "🦈", " (★)", " (★★)"],
              "stage_names": ["Yavru", "Genç", "Yetişkin", "Usta", "Efsane", "Mitik"],
              "xp_per_level": [0, 50, 150, 350, 700, 1200], "decay_rate": 2.5},
}

# ============ MAĞAZA EŞYALARI ============
SHOP_ITEMS = {
    "balik_yemi": {"name": "🐟 Balık Yemi", "type": "food", "cat": "yemek", "price": 15, "hunger": 20, "happiness": 5, "desc": "Taze balık yemi"},
    "et": {"name": "🥩 Et", "type": "food", "cat": "yemek", "price": 25, "hunger": 35, "happiness": 10, "desc": "Lezzetli et parçası"},
    "sut": {"name": "🥛 Süt", "type": "food", "cat": "yemek", "price": 20, "hunger": 25, "happiness": 8, "desc": "Taze süt"},
    "premium_yem": {"name": "⭐ Premium Yem", "type": "food", "cat": "yemek", "price": 60, "hunger": 60, "happiness": 25, "desc": "En kaliteli yem"},
    "top": {"name": "⚽ Top", "type": "toy", "cat": "oyuncak", "price": 40, "happiness": 20, "desc": "Eğlenceli top"},
    "ip": {"name": "🪢 İp", "type": "toy", "cat": "oyuncak", "price": 35, "happiness": 15, "desc": "Çekme ipi"},
    "lazer": {"name": "🔴 Lazer", "type": "toy", "cat": "oyuncak", "price": 50, "happiness": 30, "desc": "Lazer işaretçi"},
    "sapka_kirmizi": {"name": "🎩 Kırmızı Şapka", "type": "cosmetic", "cat": "kozmetik", "slot": "head", "price": 200, "emoji": "🎩", "desc": "Şık kırmızı şapka"},
    "sapka_mavi": {"name": "🎩 Mavi Şapka", "type": "cosmetic", "cat": "kozmetik", "slot": "head", "price": 200, "emoji": "🎩", "desc": "Şık mavi şapka"},
    "tac": {"name": "👑 Taç", "type": "cosmetic", "cat": "kozmetik", "slot": "head", "price": 500, "emoji": "👑", "desc": "Kraliyet tacı"},
    "bandana": {"name": "🥽 Bandana", "type": "cosmetic", "cat": "kozmetik", "slot": "head", "price": 150, "emoji": "🥽", "desc": "Havalı bandana"},
    "papyon": {"name": "🎀 Papyon", "type": "cosmetic", "cat": "kozmetik", "slot": "neck", "price": 120, "emoji": "🎀", "desc": "Şık papyon"},
    "tasma_altin": {"name": "✨ Altın Tasma", "type": "cosmetic", "cat": "kozmetik", "slot": "neck", "price": 300, "emoji": "✨", "desc": "Altın tasma"},
    "kanat": {"name": "🪽 Kanat", "type": "cosmetic", "cat": "kozmetik", "slot": "back", "price": 400, "emoji": "🪽", "desc": "Melek kanatları"},
    "pelerin": {"name": "🦸 Pelerin", "type": "cosmetic", "cat": "kozmetik", "slot": "back", "price": 350, "emoji": "🦸", "desc": "Süper kahraman pelerini"},
    "gunes_gozlugu": {"name": "🕶️ Güneş Gözlüğü", "type": "cosmetic", "cat": "kozmetik", "slot": "face", "price": 180, "emoji": "🕶️", "desc": "Havalı güneş gözlüğü"},
    "maske": {"name": "🎭 Maske", "type": "cosmetic", "cat": "kozmetik", "slot": "face", "price": 220, "emoji": "🎭", "desc": "Gizemli maske"},
}

# ============ DECAY SYSTEM ============
def _apply_decay(pet):
    if not pet: return pet
    ptype = PET_TYPES[pet["pet_type"]]
    decay_rate = ptype["decay_rate"]
    last_decay = pet.get("last_decay")
    if not last_decay:
        last_decay = pet.get("created_at") or datetime.datetime.now().isoformat()
    try:
        last_dt = datetime.datetime.fromisoformat(last_decay)
    except Exception:
        last_dt = datetime.datetime.now()
    now = datetime.datetime.now()
    hours_passed = (now - last_dt).total_seconds() / 3600.0
    if hours_passed < 0.05:
        return pet
    hunger_loss = int(hours_passed * decay_rate)
    happy_loss = int(hours_passed * (decay_rate * 0.6))
    new_hunger = max(0, pet["hunger"] - hunger_loss)
    new_happy = max(0, pet["happiness"] - happy_loss)
    with _DB_LOCK:
        conn = _baglanti()
        conn.execute("UPDATE pets SET hunger=?, happiness=?, last_decay=? WHERE user_id=?", (new_hunger, new_happy, now.isoformat(), pet["user_id"]))
        conn.commit()
        conn.close()
    pet["hunger"] = new_hunger
    pet["happiness"] = new_happy
    pet["last_decay"] = now.isoformat()
    return pet

# ============ RENDER ============
def _render_pet(pet):
    ptype = PET_TYPES[pet["pet_type"]]
    level = pet["level"]
    stage_emoji = ptype["stages"][min(level - 1, len(ptype["stages"]) - 1)]
    equipped = json.loads(pet.get("equipped", "{}") or "{}")
    head = equipped.get("head", "")
    neck = equipped.get("neck", "")
    back = equipped.get("back", "")
    face = equipped.get("face", "")
    lines = []
    top = ""
    if back: top += back + " "
    top += stage_emoji
    if head: top += " " + head
    lines.append(top)
    if neck: lines.append(f"  {neck}")
    if face: lines.append(f"  {face}")
    visual = "\n".join(lines)
    stage_name = ptype["stage_names"][min(level - 1, len(ptype["stage_names"]) - 1)]
    return visual, stage_name

def _add_pet_xp(user_id, amount):
    pet = _get_pet(user_id)
    if not pet: return False, 1
    pet = _apply_decay(pet)
    new_xp = pet["xp"] + amount
    level = pet["level"]
    ptype = PET_TYPES[pet["pet_type"]]
    leveled_up = False
    while level < 6 and new_xp >= ptype["xp_per_level"][level]:
        new_xp -= ptype["xp_per_level"][level]
        level += 1
        leveled_up = True
    with _DB_LOCK:
        conn = _baglanti()
        conn.execute("UPDATE pets SET xp=?, level=? WHERE user_id=?", (new_xp, level, user_id))
        conn.commit()
        conn.close()
    return leveled_up, level

# ============ PET PANEL (PERSISTENT) ============
class PetPanelView(View):
    """Sunucuda sabit duran pet seçim paneli"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="🐾 Pet türünü seç...",
        custom_id="pet_panel_select",
        options=[
            discord.SelectOption(label="Kedi", value="kedi", emoji="🐱", description="Sevimli ve bağımsız"),
            discord.SelectOption(label="Köpek", value="kopek", emoji="🐶", description="Sadık ve enerjik"),
            discord.SelectOption(label="Kuş", value="kus", emoji="🐦", description="Renkli ve neşeli"),
            discord.SelectOption(label="Balık", value="balik", emoji="🐟", description="Sakin ve güzel"),
        ]
    )
    async def secim(self, interaction, select):
        pet_type = select.values[0]
        user = interaction.user
        mevcut = _get_pet(user.id)
        if mevcut:
            await interaction.response.send_message("❌ Zaten bir petin var! Kişisel kanalına git.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        ptype = PET_TYPES[pet_type]
        emoji = ptype["emoji"]

        # Kategori bul veya oluştur
        category = discord.utils.get(guild.categories, name="🐈・Kişisel Pet")
        if not category:
            category = await guild.create_category("🐈・Kişisel Pet")

        # Kanal adı: kullanıcı adı + pet emoji
        safe_name = "".join(c for c in user.name.lower() if c.isalnum() or c == "_")[:20]
        channel_name = f"{safe_name}-{emoji}"

        # İzinler: sadece kullanıcı ve bot
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_messages=True),
        }

        # Kanal oluştur
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"{user.display_name} adlı kullanıcının kişisel pet kanalı"
        )

        # Pet oluştur (isim geçici)
        _create_pet(user.id, pet_type, "İsimsiz", channel.id)

        # Hoşgeldin mesajı
        embed = discord.Embed(title=f"🐾 {ptype['emoji']} Yeni Pet!", color=0xff69b4)
        embed.description = f"Tebrikler! Bir **{ptype['name']}** sahiplendin!\n\n**1 dakika** içinde petine bir isim ver. Bu kanala ismini yaz."
        embed.add_field(name="Pet Türü", value=f"{ptype['emoji']} {ptype['name']}", inline=True)
        embed.set_footer(text="İsim vermezsen rastgele bir isim verilecek.")
        await channel.send(f"{user.mention}", embed=embed)

        # İsim bekleme (background task)
        interaction.client.loop.create_task(_wait_for_name(interaction.client, user, channel, pet_type))

        await interaction.followup.send(f"✅ Petin oluşturuldu! {channel.mention} kanalına git ve petine isim ver.", ephemeral=True)

async def _wait_for_name(bot, user, channel, pet_type):
    """Kanalda isim bekleme"""
    def check(m):
        return m.author.id == user.id and m.channel.id == channel.id

    try:
        msg = await bot.wait_for("message", check=check, timeout=60)
        name = msg.content.strip()[:20]
        if not name:
            name = f"{PET_TYPES[pet_type]['name']}{random.randint(1,999)}"
    except asyncio.TimeoutError:
        name = f"{PET_TYPES[pet_type]['name']}{random.randint(1,999)}"
        await channel.send(f"⏰ Süre doldu! Petinin adı **{name}** olarak ayarlandı.")

    with _DB_LOCK:
        conn = _baglanti()
        conn.execute("UPDATE pets SET pet_name=? WHERE user_id=?", (name, user.id))
        conn.commit()
        conn.close()

    pet = _get_pet(user.id)
    visual, stage_name = _render_pet(pet)
    ptype = PET_TYPES[pet_type]
    xp_needed = ptype["xp_per_level"][pet["level"]] if pet["level"] < 6 else 0
    embed = discord.Embed(title=f"🐾 {name}", color=0xff69b4)
    embed.description = f"Petinin adı **{name}**! 🎉\n\n```\n{visual}\n```"
    embed.add_field(name="Tür", value=f"{ptype['emoji']} {ptype['name']}", inline=True)
    embed.add_field(name="Seviye", value=f"⭐ {pet['level']} - {stage_name}", inline=True)
    embed.add_field(name="Açlık", value=f"🍖 {pet['hunger']}%", inline=True)
    embed.add_field(name="Mutluluk", value=f"😊 {pet['happiness']}%", inline=True)
    embed.add_field(name="Komutlar", value="`/pet` - Görüntüle\n`/pet-besle` - Besle\n`/pet-magaza` - Mağaza\n`/pet-oyna` - Oyna\n`/pet-kuşan` - Kozmetik", inline=False)
    await channel.send(embed=embed)

# ============ MAGAZA VIEW ============
class MagazaView(View):
    def __init__(self, user_id, category="yemek"):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.category = category
        self._build()

    def _build(self):
        self.children.clear()
        items = [(k, v) for k, v in SHOP_ITEMS.items() if v["cat"] == self.category]
        for item_id, item in items:
            label = f"{item['name']} - {item['price']} YNK"
            if len(label) > 80:
                label = label[:77] + "..."
            btn = Button(label=label, style=discord.ButtonStyle.secondary, custom_id=f"buy_{item_id}")
            btn.callback = self._make_buy_callback(item_id)
            self.add_item(btn)

    def _make_buy_callback(self, item_id):
        async def callback(interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("Bu senin mağazan değil!", ephemeral=True)
                return
            item = SHOP_ITEMS[item_id]
            data = _get_coins(self.user_id)
            if data["coins"] < item["price"]:
                await interaction.response.send_message(f"❌ Yetersiz bakiye!\nGerekli: **{item['price']}** YNK\nBakiyen: **{_format_coins(data['coins'])}** YNK", ephemeral=True)
                return
            _update_coins(self.user_id, -item["price"])
            _add_inventory(self.user_id, item_id, item["type"])
            await interaction.response.send_message(f"✅ **{item['name']}** satın alındı!\n-{item['price']} YNK | Kalan: {_format_coins(data['coins'] - item['price'])} YNK", ephemeral=True)
        return callback

# ============ BESLEME VIEW ============
class FeedView(View):
    def __init__(self, user_id, pet):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.pet = pet
        self._build()

    def _build(self):
        self.children.clear()
        inv = _get_inventory(self.user_id)
        foods = [i for i in inv if SHOP_ITEMS.get(i["item_id"], {}).get("type") == "food" and i["quantity"] > 0]
        options = []
        for inv_item in foods:
            item = SHOP_ITEMS[inv_item["item_id"]]
            options.append(discord.SelectOption(label=f"{item['name']} ({inv_item['quantity']}x)", value=inv_item["item_id"],
                                                description=f"+{item['hunger']} açlık, +{item['happiness']} mutluluk"))
        if options:
            select = Select(placeholder="🍖 Yemek seç...", options=options[:25], custom_id="feed_select")
            select.callback = self._feed_callback
            self.add_item(select)

    async def _feed_callback(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Bu senin petin değil!", ephemeral=True)
            return
        item_id = interaction.data["values"][0]
        item = SHOP_ITEMS[item_id]
        pet = _get_pet(self.user_id)
        pet = _apply_decay(pet)
        if _get_item_qty(self.user_id, item_id) < 1:
            await interaction.response.send_message("❌ Bu yemekten kalmadı!", ephemeral=True)
            return
        _remove_inventory(self.user_id, item_id, 1)
        new_hunger = min(100, pet["hunger"] + item["hunger"])
        new_happy = min(100, pet["happiness"] + item["happiness"])
        with _DB_LOCK:
            conn = _baglanti()
            conn.execute("UPDATE pets SET hunger=?, happiness=? WHERE user_id=?", (new_hunger, new_happy, self.user_id))
            conn.commit()
            conn.close()
        xp_gain = item["hunger"] // 5
        leveled, new_level = _add_pet_xp(self.user_id, xp_gain)
        pet2 = _get_pet(self.user_id)
        pet2 = _apply_decay(pet2)
        visual, stage_name = _render_pet(pet2)
        embed = discord.Embed(title=f"🍖 {pet['pet_name']} beslendi!", color=0x00ff00)
        embed.description = f"```\n{visual}\n```"
        embed.add_field(name="Yemek", value=item["name"], inline=True)
        embed.add_field(name="Açlık", value=f"{pet['hunger']}% → {new_hunger}%", inline=True)
        embed.add_field(name="Mutluluk", value=f"{pet['happiness']}% → {new_happy}%", inline=True)
        embed.add_field(name="XP", value=f"+{xp_gain}", inline=True)
        if leveled:
            embed.add_field(name="🎉 SEVİYE ATLADI!", value=f"Seviye {new_level} - {stage_name}!", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)

# ============ KUŞANMA VIEW ============
class EquipView(View):
    def __init__(self, user_id):
        super().__init__(timeout=180)
        self.user_id = user_id
        self._build()

    def _build(self):
        self.children.clear()
        inv = _get_inventory(self.user_id)
        cosmetics = [i for i in inv if SHOP_ITEMS.get(i["item_id"], {}).get("type") == "cosmetic"]
        pet = _get_pet(self.user_id)
        equipped = json.loads(pet.get("equipped", "{}") or "{}") if pet else {}

        if cosmetics:
            options = []
            for inv_item in cosmetics:
                item = SHOP_ITEMS[inv_item["item_id"]]
                options.append(discord.SelectOption(label=f"{item['name']} ({inv_item['quantity']}x)", value=inv_item["item_id"],
                                                    emoji=item.get("emoji", "🎨"), description=f"Slot: {item['slot']}"))
            select = Select(placeholder="🎨 Kozmetik kuşan...", options=options[:25], custom_id="equip_select")
            select.callback = self._equip_callback
            self.add_item(select)

        for slot, item_id in equipped.items():
            if item_id:
                item = SHOP_ITEMS[item_id]
                btn = Button(label=f"❌ {item['name']} çıkar", style=discord.ButtonStyle.danger, custom_id=f"unequip_{slot}")
                btn.callback = self._make_unequip(slot, item_id)
                self.add_item(btn)

    def _make_unequip(self, slot, item_id):
        async def callback(interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("Bu senin petin değil!", ephemeral=True)
                return
            pet = _get_pet(self.user_id)
            equipped = json.loads(pet.get("equipped", "{}") or "{}")
            equipped[slot] = None
            with _DB_LOCK:
                conn = _baglanti()
                conn.execute("UPDATE pets SET equipped=? WHERE user_id=?", (json.dumps(equipped), self.user_id))
                conn.commit()
                conn.close()
            _add_inventory(self.user_id, item_id, "cosmetic")
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
        old_item = equipped.get(slot)
        if old_item:
            _add_inventory(self.user_id, old_item, "cosmetic")
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
        # Persistent panel view kaydet
        bot.add_view(PetPanelView())

    async def cog_load(self):
        self.bot.add_view(PetPanelView())

    def _pet_kanali(self, user_id):
        """Kullanıcının kişisel pet kanal ID'sini döndür"""
        pet = _get_pet(user_id)
        if not pet:
            return 0
        return pet.get("channel_id", 0)

    def _kanal_kontrol(self, interaction):
        """Komutun kişisel pet kanalında mı çalıştığını kontrol et"""
        pet = _get_pet(interaction.user.id)
        if not pet:
            return False, "❌ Önce bir pet sahiplen! Sunucudaki pet panelinden seç."
        if pet.get("channel_id", 0) != interaction.channel.id:
            return False, f"❌ Bu komut sadece kişisel pet kanalında çalışır: <#{pet['channel_id']}>"
        return True, ""

    @app_commands.command(name="pet", description="Petini görüntüle")
    async def pet(self, interaction: discord.Interaction):
        ok, msg = self._kanal_kontrol(interaction)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return
        pet = _get_pet(interaction.user.id)
        pet = _apply_decay(pet)
        visual, stage_name = _render_pet(pet)
        ptype = PET_TYPES[pet["pet_type"]]
        xp_needed = ptype["xp_per_level"][pet["level"]] if pet["level"] < 6 else 0
        embed = discord.Embed(title=f"🐾 {pet['pet_name']}", color=0xff69b4)
        embed.description = f"```\n{visual}\n```"
        embed.add_field(name="Tür", value=f"{ptype['emoji']} {ptype['name']}", inline=True)
        embed.add_field(name="Seviye", value=f"⭐ {pet['level']} - {stage_name}", inline=True)
        embed.add_field(name="XP", value=f"{pet['xp']}/{xp_needed}", inline=True)
        embed.add_field(name="Açlık", value=f"🍖 {pet['hunger']}%", inline=True)
        embed.add_field(name="Mutluluk", value=f"😊 {pet['happiness']}%", inline=True)
        equipped = json.loads(pet.get("equipped", "{}") or "{}")
        cos_list = [f"{SHOP_ITEMS[item_id]['emoji']} {SHOP_ITEMS[item_id]['name']}" for item_id in equipped.values() if item_id]
        if cos_list:
            embed.add_field(name="Kozmetikler", value="\n".join(cos_list), inline=False)
        if pet["hunger"] < 30:
            embed.add_field(name="⚠️ Uyarı", value="Petin aç! Beslemeyi unutma.", inline=False)
        if pet["happiness"] < 30:
            embed.add_field(name="⚠️ Uyarı", value="Petin mutsuz! Oynamayı unutma.", inline=False)
        embed.set_footer(text=f"Oluşturulma: {pet['created_at'][:10]}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pet-besle", description="Petini besle (envanterinden seç)")
    async def pet_besle(self, interaction: discord.Interaction):
        ok, msg = self._kanal_kontrol(interaction)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return
        pet = _get_pet(interaction.user.id)
        pet = _apply_decay(pet)
        inv = _get_inventory(interaction.user.id)
        foods = [i for i in inv if SHOP_ITEMS.get(i["item_id"], {}).get("type") == "food" and i["quantity"] > 0]
        if not foods:
            await interaction.response.send_message("❌ Envanterinde yemek yok! `/pet-magaza`'dan satın al.", ephemeral=True)
            return
        embed = discord.Embed(title=f"🍖 {pet['pet_name']} Besle", color=0x00ff00)
        embed.description = "Envanterinden bir yemek seç."
        view = FeedView(interaction.user.id, pet)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="pet-oyna", description="Petinle oyna")
    async def pet_oyna(self, interaction: discord.Interaction):
        ok, msg = self._kanal_kontrol(interaction)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return
        pet = _get_pet(interaction.user.id)
        pet = _apply_decay(pet)
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
        pet2 = _get_pet(interaction.user.id)
        pet2 = _apply_decay(pet2)
        visual, stage_name = _render_pet(pet2)
        embed = discord.Embed(title=f"🎾 {pet['pet_name']} ile oynadın!", color=0x3498db)
        embed.description = f"```\n{visual}\n```"
        embed.add_field(name="Mutluluk", value=f"{pet['happiness']}% → {new_happy}%", inline=True)
        embed.add_field(name="Açlık", value=f"{pet['hunger']}% → {new_hunger}%", inline=True)
        embed.add_field(name="XP", value=f"+{xp_gain}", inline=True)
        if leveled:
            embed.add_field(name="🎉 SEVİYE ATLADI!", value=f"Seviye {new_level} - {stage_name}!", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pet-magaza", description="Pet mağazası")
    @app_commands.describe(kategori="Kategori: yemek, oyuncak, kozmetik")
    @app_commands.choices(kategori=[
        app_commands.Choice(name="🍖 Yemek", value="yemek"),
        app_commands.Choice(name="🎾 Oyuncak", value="oyuncak"),
        app_commands.Choice(name="🎨 Kozmetik", value="kozmetik"),
    ])
    async def pet_magaza(self, interaction: discord.Interaction, kategori: str = "yemek"):
        ok, msg = self._kanal_kontrol(interaction)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return
        data = _get_coins(interaction.user.id)
        embed = discord.Embed(title="🏪 Pet Mağazası", color=0x9b59b6)
        embed.description = f"Bakiyen: 💰 {_format_coins(data['coins'])} YNK"
        view = MagazaView(interaction.user.id, kategori)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="pet-envanter", description="Pet envanterini görüntüle")
    async def pet_envanter(self, interaction: discord.Interaction):
        ok, msg = self._kanal_kontrol(interaction)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return
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
        ok, msg = self._kanal_kontrol(interaction)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return
        pet = _get_pet(interaction.user.id)
        inv = _get_inventory(interaction.user.id)
        cosmetics = [i for i in inv if SHOP_ITEMS.get(i["item_id"], {}).get("type") == "cosmetic"]
        equipped = json.loads(pet.get("equipped", "{}") or "{}")
        if not cosmetics and not any(equipped.values()):
            await interaction.response.send_message("❌ Kozmetik eşyan yok! `/pet-magaza`'dan al.", ephemeral=True)
            return
        embed = discord.Embed(title="🎨 Kozmetik Kuşan", color=0x9b59b6)
        embed.description = "Aşağıdan kozmetik seç veya çıkar."
        view = EquipView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="pet-birak", description="Petini bırak")
    async def pet_birak(self, interaction: discord.Interaction):
        ok, msg = self._kanal_kontrol(interaction)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return
        pet = _get_pet(interaction.user.id)
        channel_id = pet.get("channel_id", 0)
        with _DB_LOCK:
            conn = _baglanti()
            conn.execute("DELETE FROM pets WHERE user_id=?", (interaction.user.id,))
            conn.execute("DELETE FROM pet_inventory WHERE user_id=?", (interaction.user.id,))
            conn.commit()
            conn.close()
        # Kanalı sil
        if channel_id:
            try:
                ch = self.bot.get_channel(channel_id)
                if ch:
                    await ch.delete()
            except Exception:
                pass
        await interaction.response.send_message(f"😢 **{pet['pet_name']}** bırakıldı.", ephemeral=True)

    @app_commands.command(name="pet-liste", description="Tüm pet türlerini ve seviyelerini göster")
    async def pet_liste(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🐾 Pet Türleri", color=0xff69b4)
        for key, ptype in PET_TYPES.items():
            stages = " → ".join(ptype["stages"])
            embed.add_field(name=f"{ptype['emoji']} {ptype['name']}", value=f"Seviyeler: {stages}", inline=False)
        embed.add_field(name="📦 Mağaza Kategorileri", value="🍖 Yemek | 🎾 Oyuncak | 🎨 Kozmetik", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pet-panel-gonder", description="Pet seçim panelini bir kanala gönder (Admin)")
    @app_commands.describe(kanal="Panelin gönderileceği kanal")
    async def pet_panel_gonder_cmd(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        embed = discord.Embed(title="🐾 Pet Sahiplen", color=0xff69b4)
        embed.description = "Aşağıdan bir pet türü seç. Seçtikten sonra sana özel bir kanal oluşturulacak!\n\nPet türleri:\n🐱 Kedi - Sevimli ve bağımsız\n🐶 Köpek - Sadık ve enerjik\n🐦 Kuş - Renkli ve neşeli\n🐟 Balık - Sakin ve güzel"
        view = PetPanelView()
        await kanal.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Pet paneli {kanal.mention} kanalına gönderildi!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Pet(bot))

def pet_panel_gonder(bot, guild, kanal_adi=None):
    """Web panelinden pet paneli göndermek için"""
    import asyncio
    kanal = None
    if kanal_adi:
        kanal = discord.utils.get(guild.text_channels, name=kanal_adi)
    if not kanal:
        kanal = discord.utils.get(guild.text_channels, name="🐈・pet・oluştur")
    if not kanal:
        # İlk text kanalı kullan
        kanal = guild.text_channels[0] if guild.text_channels else None
    if not kanal:
        return
    embed = discord.Embed(title="🐾 Pet Sahiplen", color=0xff69b4)
    embed.description = "Aşağıdan bir pet türü seç. Seçtikten sonra sana özel bir kanal oluşturulacak!\n\nPet türleri:\n🐱 Kedi - Sevimli ve bağımsız\n🐶 Köpek - Sadık ve enerjik\n🐦 Kuş - Renkli ve neşeli\n🐟 Balık - Sakin ve güzel"
    view = PetPanelView()
    asyncio.run_coroutine_threadsafe(kanal.send(embed=embed, view=view), bot.loop)