import discord
from discord import app_commands
from discord.ext import tasks
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
import threading
import asyncio
import webview
import json
import os
import html
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re

def _load_env_file(path=".env"):
    try:
        with open(path, "r", encoding="utf-8") as env_file:
            for satir in env_file:
                satir = satir.strip()
                if not satir or satir.startswith("#") or "=" not in satir:
                    continue
                anahtar, deger = satir.split("=", 1)
                os.environ.setdefault(anahtar.strip(), deger.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass

_load_env_file()

# --- KALICI AYAR YÖNETİMİ (JSON Veritabanı) ---
CONFIG_FILE = "settings.json"
EXTENSION_FILE = "user_extension.py"

default_settings = {
    "hedef_uye": 1000,
    "sayac_kanal": "genel",
    "giris_mesaji": "Sunucumuza hoş geldin {uye}! 🎉",
    "cikis_mesaji": "{uye} aramızdan ayrıldı.",
    "tavsiye_kanal": "genel",
    "tavsiye_baslik": "✨ Yeni Tavsiye",
    "log_kanal": "genel",
    "youtube_kanal": "duyuru",
    "youtube_channel_id": "",
    "youtube_mesaj": "@everyone Yeni video yayında arkadaşlar! Kaçırmayın 🔥\n{link}",
    "son_video_id": "",
    "sil_max_limit": 100
}

def ayarlari_yukle():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in default_settings.items():
                    if k not in data:
                        data[k] = v
                return data
        except:
            pass
    return default_settings.copy()

def ayarlari_kaydet(yeni_ayarlar):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(yeni_ayarlar, f, ensure_ascii=False, indent=4)

BOT_AYARLARI = ayarlari_yukle()
BOT_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
BOT_DURUMU = "Kapalı"
bot_instance = None
bot_thread = None

def esc(metin):
    return html.escape(str(metin), quote=True)

# --- AKILLI YOUTUBE GİRDİ ÇÖZÜCÜ (Link veya @handle desteği) ---
def kanal_idsini_coz(girdi):
    girdi = girdi.strip()
    if not girdi:
        return ""
    
    # Zaten UC ile başlıyorsa doğrudan döndür
    if girdi.startswith("UC") and len(girdi) >= 24:
        return girdi
        
    # Eğer @handle veya youtube URL'si girildiyse HTML sayfasından canonical ID'yi çek
    if "youtube.com" in girdi or girdi.startswith("@"):
        if girdi.startswith("@"):
            url = f"https://www.youtube.com/@{girdi.lstrip('@')}"
        else:
            url = girdi
            
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=10) as response:
                html_icerik = response.read().decode('utf-8')
            
            # Sayfa kaynağındaki canonical linkten veya externalId'den channel ID'yi bul
            match = re.search(r'\"channelId\"\s*:\s*\"(UC[a-zA-Z0-9_-]{22})\"', html_icerik)
            if match:
                return match.group(1)
            
            match_canonical = re.search(r'href=["\']https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})["\']', html_icerik)
            if match_canonical:
                return match_canonical.group(1)
        except Exception as e:
            print("YouTube kanal ID çözme hatası:", e)
            
    return girdi

# --- YOUTUBE RSS KONTROL FONKSİYONU ---
def son_youtube_videosunu_getir(girdi):
    gercek_id = kanal_idsini_coz(girdi)
    if not gercek_id:
        return None
        
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={gercek_id}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        ns = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
        entry = root.find('atom:entry', ns)
        if entry is not None:
            video_id = entry.find('yt:videoId', ns).text
            title = entry.find('atom:title', ns).text
            link_el = entry.find('atom:link', ns)
            link = link_el.attrib['href'] if link_el is not None else f"https://www.youtube.com/watch?v={video_id}"
            return {"id": video_id, "title": title, "link": link}
    except Exception as e:
        print("YouTube RSS kontrol hatası:", e)
    return None

# --- DİSCORD BOT FABRİKASI ---
def create_bot():
    intents = discord.Intents.default()
    intents.members = True
    intents.moderation = True
    intents.guilds = True
    intents.message_content = True
    
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    @tasks.loop(seconds=60)
    async def youtube_kontrol_dongusu():
        yt_input = BOT_AYARLARI.get("youtube_channel_id", "").strip()
        if not yt_input:
            return
        
        loop = asyncio.get_running_loop()
        video = await loop.run_in_executor(None, son_youtube_videosunu_getir, yt_input)
        if not video:
            return

        son_kayitli_id = BOT_AYARLARI.get("son_video_id", "")
        if not son_kayitli_id:
            BOT_AYARLARI["son_video_id"] = video["id"]
            ayarlari_kaydet(BOT_AYARLARI)
            return

        if video["id"] != son_kayitli_id:
            BOT_AYARLARI["son_video_id"] = video["id"]
            ayarlari_kaydet(BOT_AYARLARI)
            
            hedef_kanal = BOT_AYARLARI.get("youtube_kanal", "duyuru")
            sablon = BOT_AYARLARI.get("youtube_mesaj", "Yeni video yayında! {link}")
            mesaj_metni = sablon.replace("{link}", video["link"]).replace("{baslik}", video["title"])
            if "{link}" not in sablon:
                mesaj_metni = f"{mesaj_metni}\n{video['link']}"

            for guild in client.guilds:
                for channel in guild.text_channels:
                    if channel.name.lower() == hedef_kanal.lower():
                        try:
                            await channel.send(mesaj_metni)
                        except Exception as e:
                            print("YouTube duyuru gönderme hatası:", e)
                        break

    @client.event
    async def on_ready():
        global BOT_DURUMU
        BOT_DURUMU = "Aktif (Çalışıyor)"
        if not youtube_kontrol_dongusu.is_running():
            youtube_kontrol_dongusu.start()
        print(f"[{client.user}] Discord sunucularına başarıyla bağlandı!")

    @client.event
    async def on_member_join(member):
        hedef_kanal_adi = BOT_AYARLARI["sayac_kanal"]
        for channel in member.guild.text_channels:
            if channel.name.lower() == hedef_kanal_adi.lower():
                aktif_uye = member.guild.member_count
                hedef = BOT_AYARLARI["hedef_uye"]
                kalan = hedef - aktif_uye
                aciklama = BOT_AYARLARI["giris_mesaji"].replace("{uye}", member.mention)
                embed = discord.Embed(title="📥 Yeni Üye Katıldı!", description=aciklama, color=discord.Color.green(), timestamp=discord.utils.utcnow())
                embed.add_field(name="🎯 Hedef Üye", value=f"`{hedef}`", inline=True)
                embed.add_field(name="⏳ Kalan", value=f"`{kalan}`", inline=True)
                embed.add_field(name="👥 Anlık Üye", value=f"`{aktif_uye}`", inline=True)
                await channel.send(embed=embed)
                break

    @client.event
    async def on_member_remove(member):
        hedef_kanal_adi = BOT_AYARLARI["sayac_kanal"]
        for channel in member.guild.text_channels:
            if channel.name.lower() == hedef_kanal_adi.lower():
                aktif_uye = member.guild.member_count
                hedef = BOT_AYARLARI["hedef_uye"]
                kalan = hedef - aktif_uye
                aciklama = BOT_AYARLARI["cikis_mesaji"].replace("{uye}", member.mention)
                embed = discord.Embed(title="📤 Bir Üye Ayrıldı", description=aciklama, color=discord.Color.red(), timestamp=discord.utils.utcnow())
                embed.add_field(name="🎯 Hedef Üye", value=f"`{hedef}`", inline=True)
                embed.add_field(name="⏳ Kalan", value=f"`{kalan}`", inline=True)
                embed.add_field(name="👥 Anlık Üye", value=f"`{aktif_uye}`", inline=True)
                await channel.send(embed=embed)
                break

    @client.event
    async def on_message_delete(message):
        if message.author.bot:
            return
        kanal_adi = BOT_AYARLARI["log_kanal"]
        for channel in message.guild.text_channels:
            if channel.name.lower() == kanal_adi.lower():
                embed = discord.Embed(title="Message deleted", description=f"**Kanal:** {message.channel.mention}\n**Yazan:** {message.author}\n\n**Silinen:**\n{message.content or '*İçerik yok*'}", color=discord.Color.red(), timestamp=discord.utils.utcnow())
                embed.set_author(name=f"@{message.author.name}", icon_url=message.author.display_avatar.url)
                await channel.send(embed=embed)
                break

    @tree.command(name="tavsiye", description="Sunucu için tavsiyeni gönder")
    @app_commands.describe(mesaj="Yazmak istediğin tavsiye")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def tavsiye(interaction: discord.Interaction, mesaj: str):
        hedef_tavsiye_kanal = BOT_AYARLARI["tavsiye_kanal"]
        if interaction.channel.name.lower() != hedef_tavsiye_kanal.lower():
            await interaction.response.send_message(f"❌ Bu komutu sadece **#{hedef_tavsiye_kanal}** kanalında kullanabilirsin!", ephemeral=True)
            return

        icerik = f"**{BOT_AYARLARI['tavsiye_baslik']}**\n\n**Tavsiye Sahibi:** {interaction.user.mention}\n**Tavsiye:** {mesaj}"
        await interaction.response.send_message(icerik)
        msg = await interaction.original_response()
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

    @tree.command(name="sil", description="Bulunduğun kanaldaki belirtilen sayıda mesajı siler")
    @app_commands.describe(miktar="Silinecek mesaj sayısı (Örn: 10, 50, 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def sil(interaction: discord.Interaction, miktar: int):
        max_limit = int(BOT_AYARLARI.get("sil_max_limit", 100))
        if miktar < 1 or miktar > max_limit:
            await interaction.response.send_message(f"❌ Tek seferde **1** ile **{max_limit}** arasında mesaj silebilirsin!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        silinenler = await interaction.channel.purge(limit=miktar)
        await interaction.followup.send(f"🧹 **{len(silinenler)}** adet mesaj başarıyla temizlendi!", ephemeral=True)

    @tree.error
    async def on_app_command_error(interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CommandOnCooldown):
            kalan = int(error.retry_after)
            await interaction.response.send_message(f"⏳ Bu komutu tekrar kullanmak için **{kalan} saniye** beklemelisin!", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Bu komutu kullanmak için **Mesajları Yönet** yetkisine sahip olmalısın!", ephemeral=True)

    async def setup_hook():
        await tree.sync()
    client.setup_hook = setup_hook

    return client

# --- CANLI SUNUCU KANALLARINI ÇEKME ---
def sunucu_kanallarini_getir():
    kanallar = []
    try:
        if bot_instance and bot_instance.guilds:
            for guild in bot_instance.guilds:
                for channel in guild.text_channels:
                    kanallar.append(channel.name)
    except Exception as e:
        print("Kanal çekme hatası:", e)
    
    if not kanallar:
        kanallar = [
            BOT_AYARLARI["sayac_kanal"], 
            BOT_AYARLARI["tavsiye_kanal"], 
            BOT_AYARLARI["log_kanal"], 
            BOT_AYARLARI["youtube_kanal"]
        ]
    return sorted(list(set(kanallar)))

# --- FASTAPI & MEE6 TARZI DASHBOARD PANELİ ---
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def panel_ana_sayfa():
    kanallar = sunucu_kanallarini_getir()

    sayac_opts = "".join([f'<option value="{esc(k)}" {"selected" if k == BOT_AYARLARI["sayac_kanal"] else ""}>#{esc(k)}</option>' for k in kanallar])
    tavsiye_opts = "".join([f'<option value="{esc(k)}" {"selected" if k == BOT_AYARLARI["tavsiye_kanal"] else ""}>#{esc(k)}</option>' for k in kanallar])
    log_opts = "".join([f'<option value="{esc(k)}" {"selected" if k == BOT_AYARLARI["log_kanal"] else ""}>#{esc(k)}</option>' for k in kanallar])
    youtube_opts = "".join([f'<option value="{esc(k)}" {"selected" if k == BOT_AYARLARI["youtube_kanal"] else ""}>#{esc(k)}</option>' for k in kanallar])
    duyuru_opts = "".join([f'<option value="{esc(k)}">#{esc(k)}</option>' for k in kanallar])

    durum_renk = "#10b981" if BOT_DURUMU == "Aktif (Çalışıyor)" else "#ef4444"

    if not os.path.exists(EXTENSION_FILE):
        with open(EXTENSION_FILE, "w", encoding="utf-8") as f:
            f.write("# Buraya dilediğin ek Python kodlarını yazabilirsin.\n")
            
    with open(EXTENSION_FILE, "r", encoding="utf-8") as f:
        kod_icerigi = f.read()

    return f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>YNK Studio - MEE6 Dashboard</title>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
            body {{ background-color: #0b0f19; color: #f3f4f6; display: flex; height: 100vh; overflow: hidden; }}
            
            /* MEE6 Sidebar */
            .sidebar {{ width: 260px; background: #11131c; border-right: 1px solid #1e2130; display: flex; flex-direction: column; justify-content: space-between; padding: 18px; z-index: 2; }}
            .server-header {{ display: flex; align-items: center; gap: 12px; padding-bottom: 16px; border-bottom: 1px solid #1e2130; }}
            .server-avatar {{ width: 42px; height: 42px; background: linear-gradient(135deg, #5865F2, #7c3aed); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold; color: white; box-shadow: 0 4px 12px rgba(88, 101, 242, 0.3); }}
            .server-info h3 {{ font-size: 14px; font-weight: 600; color: #fff; }}
            .server-info p {{ font-size: 11px; color: {durum_renk}; margin-top: 2px; font-weight: 500; display: flex; align-items: center; gap: 5px; }}
            .server-info p::before {{ content: ''; display: inline-block; width: 7px; height: 7px; background: {durum_renk}; border-radius: 50%; box-shadow: 0 0 6px {durum_renk}; }}
            
            .search-box {{ margin: 16px 0; }}
            .search-box input {{ width: 100%; padding: 9px 12px; background: #090a0f; border: 1px solid #2a2e43; border-radius: 8px; color: #94a3b8; font-size: 12px; outline: none; }}
            
            .menu-category {{ font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; margin: 14px 8px 6px 8px; }}
            .menu {{ display: flex; flex-direction: column; gap: 4px; overflow-y: auto; flex: 1; padding-right: 2px; }}
            .menu-btn {{ background: transparent; border: none; color: #94a3b8; padding: 10px 12px; text-align: left; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s; display: flex; align-items: center; gap: 10px; }}
            .menu-btn:hover {{ background: rgba(124, 58, 237, 0.1); color: #fff; }}
            .menu-btn.active {{ background: #5865F2; color: #fff; font-weight: 600; box-shadow: 0 4px 12px rgba(88, 101, 242, 0.3); }}
            
            /* Main Dashboard & Subtle Animated Ambient Background */
            .main-content {{ 
                flex: 1; 
                background-color: #0d1220;
                background-image: 
                    radial-gradient(circle at 15% 20%, rgba(88, 101, 242, 0.09) 0%, transparent 45%),
                    radial-gradient(circle at 85% 75%, rgba(124, 58, 237, 0.08) 0%, transparent 45%),
                    linear-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255, 255, 255, 0.015) 1px, transparent 1px);
                background-size: 140% 140%, 140% 140%, 36px 36px, 36px 36px;
                animation: ambientFloat 16s ease-in-out infinite alternate;
                padding: 32px 40px; 
                overflow-y: auto; 
                position: relative;
            }}
            @keyframes ambientFloat {{
                0% {{ background-position: 0% 0%, 100% 100%, 0 0, 0 0; }}
                50% {{ background-position: 50% 30%, 50% 70%, 0 0, 0 0; }}
                100% {{ background-position: 100% 15%, 10% 85%, 0 0, 0 0; }}
            }}

            .tab-pane {{ display: none; animation: fadeIn 0.3s ease; }}
            .tab-pane.active {{ display: block; }}
            @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: translateY(0); }} }}
            
            .top-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }}
            h1 {{ font-size: 22px; font-weight: 700; color: #fff; }}
            .subtitle {{ color: #94a3b8; font-size: 13px; margin-bottom: 24px; }}
            
            /* MEE6 Style Cards & Grids */
            .card {{ background: rgba(22, 27, 46, 0.92); backdrop-filter: blur(8px); border: 1px solid #1f263d; border-radius: 14px; padding: 24px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.25); }}
            .card h3 {{ font-size: 16px; font-weight: 600; color: #fff; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }}
            
            .features-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; margin-top: 20px; }}
            .feature-card {{ background: rgba(22, 27, 46, 0.92); border: 1px solid #1f263d; border-radius: 12px; padding: 20px; cursor: pointer; transition: all 0.2s; display: flex; flex-direction: column; justify-content: space-between; }}
            .feature-card:hover {{ border-color: #5865F2; transform: translateY(-2px); box-shadow: 0 6px 20px rgba(88,101,242,0.15); }}
            .feature-card-top {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }}
            .feature-icon {{ width: 36px; height: 36px; background: rgba(88,101,242,0.15); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; }}
            .badge {{ font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 6px; background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }}
            .feature-title {{ font-size: 14px; font-weight: 600; color: #fff; margin-bottom: 4px; }}
            .feature-desc {{ font-size: 12px; color: #94a3b8; line-height: 1.4; }}
            
            label {{ display: block; font-size: 12px; font-weight: 500; color: #94a3b8; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
            input[type="number"], input[type="text"], select {{ width: 100%; padding: 11px 14px; background: #0b0f19; border: 1px solid #2a2e43; border-radius: 8px; color: white; font-size: 13px; margin-bottom: 18px; outline: none; transition: border-color 0.2s; }}
            input:focus, select:focus, textarea:focus {{ border-color: #5865F2; box-shadow: 0 0 0 3px rgba(88, 101, 242, 0.15); }}
            
            textarea {{ width: 100%; height: 110px; padding: 12px 14px; background: #0b0f19; border: 1px solid #2a2e43; border-radius: 8px; color: #e2e8f0; font-size: 13px; outline: none; resize: vertical; line-height: 1.5; margin-bottom: 16px; }}
            textarea.code-editor {{ height: 300px; color: #38bdf8; font-family: 'Courier New', Courier, monospace; }}
            
            .save-btn {{ background: #5865F2; color: white; border: none; padding: 11px 22px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; transition: background 0.2s; box-shadow: 0 4px 12px rgba(88,101,242,0.3); }}
            .save-btn:hover {{ background: #4752C4; }}
            
            .control-btn-green {{ background: #10b981; color: white; padding: 11px 20px; border-radius: 8px; text-decoration: none; display: inline-block; font-weight: 600; font-size: 13px; box-shadow: 0 4px 12px rgba(16,185,129,0.3); }}
            .control-btn-green:hover {{ background: #059669; }}
            .control-btn-red {{ background: #ef4444; color: white; padding: 11px 20px; border-radius: 8px; text-decoration: none; display: inline-block; font-weight: 600; font-size: 13px; box-shadow: 0 4px 12px rgba(239,68,68,0.3); }}
            .control-btn-red:hover {{ background: #dc2626; }}
            .control-btn-blue {{ background: #3b82f6; color: white; padding: 11px 20px; border-radius: 8px; text-decoration: none; display: inline-block; font-weight: 600; font-size: 13px; box-shadow: 0 4px 12px rgba(59,130,246,0.3); }}
            .control-btn-blue:hover {{ background: #2563eb; }}
            
            .tag-pill {{ background: #1f263d; color: #cbd5e1; border: 1px solid #2e3856; padding: 5px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; transition: all 0.15s; }}
            .tag-pill:hover {{ background: #5865F2; color: #fff; border-color: #5865F2; }}
            
            .flex-row {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
            .refresh-btn {{ background: #2a2e43; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; margin-bottom: 16px; transition: background 0.2s; }}
            .refresh-btn:hover {{ background: #3b4259; }}
            .hint-box {{ background: rgba(88, 101, 242, 0.08); border-left: 3px solid #5865F2; padding: 10px 14px; border-radius: 6px; font-size: 12px; color: #cbd5e1; margin-bottom: 18px; line-height: 1.5; }}
        </style>
    </head>
    <body>
        <div class="sidebar">
            <div>
                <div class="server-header">
                    <div class="server-avatar">YN</div>
                    <div class="server-info">
                        <h3>YNK Studio</h3>
                        <p>{esc(BOT_DURUMU)}</p>
                    </div>
                </div>
                
                <div class="search-box">
                    <input type="text" id="pluginSearch" onkeyup="filterPlugins()" placeholder="Modül veya komut ara...">
                </div>
                
                <div class="menu">
                    <div class="menu-category">Dashboard</div>
                    <button class="menu-btn active" onclick="switchTab('home', this)">🏠 Genel Bakış</button>
                    <button class="menu-btn" onclick="switchTab('komutlar', this)">⌨️ Komutlar</button>
                    
                    <div class="menu-category">Plugins & Modules</div>
                    <button class="menu-btn" onclick="switchTab('sayac', this)">📊 Sayaç Sistemi</button>
                    <button class="menu-btn" onclick="switchTab('tavsiye', this)">💡 Tavsiye Sistemi</button>
                    <button class="menu-btn" onclick="switchTab('log', this)">🛡️ Mod Log Sistemi</button>
                    <button class="menu-btn" onclick="switchTab('youtube', this)">📺 YouTube Bildirim</button>
                    <button class="menu-btn" onclick="switchTab('duyuru', this)">📢 Canlı Duyuru Gönder</button>
                    
                    <div class="menu-category">Advanced</div>
                    <button class="menu-btn" onclick="switchTab('kod', this)">💻 Kod Uzantısı (Extension)</button>
                </div>
            </div>
            
            <div style="font-size: 11px; color: #64748b; text-align: center; padding-top: 10px; border-top: 1px solid #1e2130;">MEE6 Dashboard v20.0</div>
        </div>

        <div class="main-content">
            <!-- GENEL BAKIŞ -->
            <div id="home" class="tab-pane active">
                <div class="top-bar">
                    <div>
                        <h1>Dashboard & Plugins</h1>
                        <p class="subtitle" style="margin-bottom: 0;">Sunucu modüllerini yönet, Hot Reset at ve bot gücünü kontrol et.</p>
                    </div>
                </div>
                
                <div class="card">
                    <h3>⚡ Bot Güç & Hot Reset Merkezi</h3>
                    <p style="color: #94a3b8; margin-bottom: 20px; font-size: 13px;">Botu yeniden başlatmadan güncellemeleri anında uygulamak için <b>Hot Reset</b> kullanabilirsin.</p>
                    <div class="flex-row">
                        <a href="/bot-ac" class="control-btn-green">🤖 Botu Başlat</a>
                        <a href="/bot-reset" class="control-btn-blue">🔄 Hot Reset (Yeniden Başlat)</a>
                        <a href="/bot-kapat" class="control-btn-red">🛑 Botu Kapat</a>
                    </div>
                </div>

                <div class="menu-category" style="margin-left: 0; margin-bottom: 12px;">Aktif Modüller & Komutlar</div>
                <div class="features-grid">
                    <div class="feature-card" onclick="switchTab('komutlar', document.querySelectorAll('.menu-btn')[1])">
                        <div>
                            <div class="feature-card-top"><div class="feature-icon">⌨️</div><span class="badge">Aktif</span></div>
                            <div class="feature-title">Slash Komutlar (/sil, /tavsiye)</div>
                            <div class="feature-desc">Toplu mesaj temizleme (/sil) ve tavsiye komutlarının ayarlarını yönet.</div>
                        </div>
                    </div>
                    <div class="feature-card" onclick="switchTab('youtube', document.querySelectorAll('.menu-btn')[5])">
                        <div>
                            <div class="feature-card-top"><div class="feature-icon">📺</div><span class="badge">Otomasyon</span></div>
                            <div class="feature-title">YouTube Video & Shorts</div>
                            <div class="feature-desc">Kanal linki (@ardinus) ile otomatik video ve Shorts algılama ve duyuru.</div>
                        </div>
                    </div>
                    <div class="feature-card" onclick="switchTab('duyuru', document.querySelectorAll('.menu-btn')[6])">
                        <div>
                            <div class="feature-card-top"><div class="feature-icon">📢</div><span class="badge">Canlı</span></div>
                            <div class="feature-title">Canlı Duyuru Gönder</div>
                            <div class="feature-desc">Discord'a girmeden istediğin kanala @everyone etiketli duyuru at.</div>
                        </div>
                    </div>
                    <div class="feature-card" onclick="switchTab('sayac', document.querySelectorAll('.menu-btn')[2])">
                        <div>
                            <div class="feature-card-top"><div class="feature-icon">📊</div><span class="badge">Aktif</span></div>
                            <div class="feature-title">Sayaç Sistemi</div>
                            <div class="feature-desc">Üye katılımlarını, çıkışlarını ve hedef sayaç oda takibini yönet.</div>
                        </div>
                    </div>
                    <div class="feature-card" onclick="switchTab('tavsiye', document.querySelectorAll('.menu-btn')[3])">
                        <div>
                            <div class="feature-card-top"><div class="feature-icon">💡</div><span class="badge">Aktif</span></div>
                            <div class="feature-title">Tavsiye Sistemi</div>
                            <div class="feature-desc">Kullanıcıların öneri bırakabileceği özel kanal ve reaksiyon yönetimi.</div>
                        </div>
                    </div>
                    <div class="feature-card" onclick="switchTab('log', document.querySelectorAll('.menu-btn')[4])">
                        <div>
                            <div class="feature-card-top"><div class="feature-icon">🛡️</div><span class="badge">Aktif</span></div>
                            <div class="feature-title">Mod Log Sistemi</div>
                            <div class="feature-desc">Mesaj silinmeleri, banlar, kanal ve rol hareketlerinin denetim günlüğü.</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- KOMUTLAR SEKMESİ -->
            <div id="komutlar" class="tab-pane">
                <h1>⌨️ Bot Komutları Yönetimi</h1>
                <p class="subtitle">Sunucudaki tüm slash komutlarını görüntüle ve üzerine tıklayarak ayarlarını yapılandır.</p>
                
                <div class="features-grid" style="margin-bottom: 24px;">
                    <div class="feature-card" onclick="document.getElementById('sil-ayar-karti').scrollIntoView({{behavior: 'smooth'}});">
                        <div>
                            <div class="feature-card-top"><div class="feature-icon">🧹</div><span class="badge">/sil [miktar]</span></div>
                            <div class="feature-title">/sil Komutu</div>
                            <div class="feature-desc">Bulunulan sohbet odasındaki belirtilen sayı kadar (Örn: /sil 100) mesajı tek seferde temizler. Ayarlamak için tıkla.</div>
                        </div>
                    </div>
                    <div class="feature-card" onclick="switchTab('tavsiye', document.querySelectorAll('.menu-btn')[3])">
                        <div>
                            <div class="feature-card-top"><div class="feature-icon">💡</div><span class="badge">/tavsiye [mesaj]</span></div>
                            <div class="feature-title">/tavsiye Komutu</div>
                            <div class="feature-desc">Sadece belirlenen odada üyelerin öneri göndermesini ve oylama emojileri eklenmesini sağlar. Ayarlara gitmek için tıkla.</div>
                        </div>
                    </div>
                </div>

                <div class="card" id="sil-ayar-karti">
                    <h3>🧹 /sil Komutu Ayarları</h3>
                    <p style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">Discord'da <b>/sil 100</b> yazdığında bot tek seferde en fazla kaç mesaj silebilsin? (Discord API sınırı gereği en fazla 100 önerilir).</p>
                    <form action="/guncelle-komutlar" method="post">
                        <label>Maksimum Tek Seferde Silinebilecek Mesaj Sayısı:</label>
                        <input type="number" name="sil_max_limit" min="1" max="100" value="{esc(BOT_AYARLARI['sil_max_limit'])}">
                        <button type="submit" class="save-btn">Komut Ayarını Kaydet</button>
                    </form>
                </div>
            </div>

            <!-- SAYAÇ SİSTEMİ -->
            <div id="sayac" class="tab-pane">
                <h1>📊 Sayaç Sistemi Yönetimi</h1>
                <p class="subtitle">Üye hedeflerini ve duyuru kanalını yapılandır.</p>
                <div class="card">
                    <button class="refresh-btn" onclick="window.location.reload();">🔄 Kanalları Yenile</button>
                    <form action="/guncelle-sayac" method="post">
                        <label>Hedef Üye:</label>
                        <input type="number" name="hedef" value="{esc(BOT_AYARLARI['hedef_uye'])}">
                        <label>Sayaç Kanalı (Anlık Sunucu Odaları):</label>
                        <select name="kanal">{sayac_opts}</select>
                        <label>Giriş Mesajı:</label>
                        <input type="text" name="giris" value="{esc(BOT_AYARLARI['giris_mesaji'])}">
                        <label>Çıkış Mesajı:</label>
                        <input type="text" name="cikis" value="{esc(BOT_AYARLARI['cikis_mesaji'])}">
                        <button type="submit" class="save-btn">Ayarları Kaydet</button>
                    </form>
                </div>
            </div>

            <!-- TAVSİYE SİSTEMİ -->
            <div id="tavsiye" class="tab-pane">
                <h1>💡 Tavsiye Sistemi Ayarları</h1>
                <p class="subtitle">Kullanıcıların tavsiye bırakabileceği özel kanal.</p>
                <div class="card">
                    <button class="refresh-btn" onclick="window.location.reload();">🔄 Kanalları Yenile</button>
                    <form action="/guncelle-tavsiye" method="post">
                        <label>Tavsiye Kanalı (Anlık Sunucu Odaları):</label>
                        <select name="kanal">{tavsiye_opts}</select>
                        <label>Başlık Etiketi:</label>
                        <input type="text" name="baslik" value="{esc(BOT_AYARLARI['tavsiye_baslik'])}">
                        <button type="submit" class="save-btn">Ayarları Kaydet</button>
                    </form>
                </div>
            </div>

            <!-- MOD LOG SİSTEMİ -->
            <div id="log" class="tab-pane">
                <h1>🛡️ Mod Log (Denetim Günlüğü) Ayarları</h1>
                <p class="subtitle">Sunucu içi güvenlik ve moderasyon olaylarının raporlandığı kanal.</p>
                <div class="card">
                    <button class="refresh-btn" onclick="window.location.reload();">🔄 Kanalları Yenile</button>
                    <form action="/guncelle-log" method="post">
                        <label>Log Bildirim Kanalı (Anlık Sunucu Odaları):</label>
                        <select name="log_kanal">{log_opts}</select>
                        <button type="submit" class="save-btn">Ayarları Kaydet</button>
                    </form>
                </div>
            </div>

            <!-- YOUTUBE OTOMASYON SİSTEMİ -->
            <div id="youtube" class="tab-pane">
                <h1>📺 YouTube Otomatik Video & Shorts Bildirimi</h1>
                <p class="subtitle">Kanal linkini (Örn: https://www.youtube.com/@ardinus) veya ID'sini yapıştır; yeni içerikleri otomatik duyursun.</p>
                <div class="card">
                    <button class="refresh-btn" onclick="window.location.reload();">🔄 Kanalları Yenile</button>
                    <div class="hint-box">
                        <b>💡 Esnek Giriş Desteği:</b><br>
                        Buraya doğrudan <b>https://www.youtube.com/@ardinus</b> linkini, <b>@ardinus</b> yazısını veya <b>UC...</b> ile başlayan kanal ID'sini yapıştırabilirsin. Sistem hepsini otomatik tanır.<br>
                        Mesaj şablonunda <b>{{link}}</b> veya <b>{{baslik}}</b> etiketlerini kullanabilirsin.
                    </div>
                    <form action="/guncelle-youtube" method="post">
                        <label>YouTube Kanal Linki, @handle veya ID:</label>
                        <input type="text" name="youtube_channel_id" placeholder="https://www.youtube.com/@ardinus veya @ardinus" value="{esc(BOT_AYARLARI.get('youtube_channel_id', ''))}">
                        
                        <label>Bildirimin Gideceği Discord Odası:</label>
                        <select name="youtube_kanal">{youtube_opts}</select>
                        
                        <label>Otomatik Paylaşım Mesajı:</label>
                        <div class="flex-row" style="margin-bottom: 8px;">
                            <button type="button" class="tag-pill" onclick="ekleMetin('yt_mesaj', '@everyone ')">+ @everyone</button>
                            <button type="button" class="tag-pill" onclick="ekleMetin('yt_mesaj', '{{link}}')">+ {{link}}</button>
                            <button type="button" class="tag-pill" onclick="ekleMetin('yt_mesaj', '{{baslik}}')">+ {{baslik}}</button>
                        </div>
                        <textarea id="yt_mesaj" name="youtube_mesaj">{esc(BOT_AYARLARI.get('youtube_mesaj', ''))}</textarea>
                        
                        <button type="submit" class="save-btn">💾 YouTube Otomasyonunu Kaydet</button>
                    </form>
                </div>
            </div>

            <!-- CANLI DUYURU GÖNDERME SEKMESİ -->
            <div id="duyuru" class="tab-pane">
                <h1>📢 Canlı Sunucu Duyurusu Gönder</h1>
                <p class="subtitle">Discord'a girmeden doğrudan bu panelden istediğin kanala etiketli duyuru gönder.</p>
                <div class="card">
                    <button class="refresh-btn" onclick="window.location.reload();">🔄 Kanalları Yenile</button>
                    <form action="/duyuru-gonder" method="post">
                        <label>Duyurunun Atılacağı Sohbet Odası:</label>
                        <select name="hedef_kanal">{duyuru_opts}</select>
                        
                        <label>Hızlı Etiket Ekle:</label>
                        <div class="flex-row" style="margin-bottom: 8px;">
                            <button type="button" class="tag-pill" onclick="ekleMetin('duyuru_metni', '@everyone ')">+ @everyone</button>
                            <button type="button" class="tag-pill" onclick="ekleMetin('duyuru_metni', '@here ')">+ @here</button>
                        </div>
                        
                        <label>Duyuru Mesajın:</label>
                        <textarea id="duyuru_metni" name="duyuru_mesaji" placeholder="Buraya sunucuya göndermek istediğin duyuruyu yaz..." required></textarea>
                        
                        <button type="submit" class="save-btn">🚀 Duyuruyu Şimdi Sunucuya Gönder</button>
                    </form>
                </div>
            </div>

            <!-- KOD UZANTISI -->
            <div id="kod" class="tab-pane">
                <h1>💻 Harici Python Kod Editörü (Extension)</h1>
                <p class="subtitle">Buraya yazdığın kodlar güvenli alanda saklanır ve botu genişletir.</p>
                <div class="card">
                    <form action="/guncelle-kod" method="post">
                        <textarea class="code-editor" name="yeni_kod">{esc(kod_icerigi)}</textarea><br><br>
                        <button type="submit" class="save-btn">💾 Kodu Kaydet ve Hot Reset Uygula</button>
                    </form>
                </div>
            </div>
        </div>

        <script>
            function switchTab(tabId, btn) {{
                document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
                document.querySelectorAll('.menu-btn').forEach(b => b.classList.remove('active'));
                document.getElementById(tabId).classList.add('active');
                if(btn) btn.classList.add('active');
            }}

            function ekleMetin(elementId, metin) {{
                const alan = document.getElementById(elementId);
                alan.value += metin;
                alan.focus();
            }}

            function filterPlugins() {{
                const input = document.getElementById('pluginSearch').value.toLowerCase();
                document.querySelectorAll('.menu-btn').forEach(btn => {{
                    btn.style.display = btn.innerText.toLowerCase().includes(input) ? 'flex' : 'none';
                }});
            }}
        </script>
    </body>
    </html>
    """

# --- BOT ÇALIŞTIRMA & HOT RESET MEKANİZMASI ---
def botu_baslat_arka_planda():
    global bot_instance, BOT_DURUMU
    try:
        if bot_instance and not bot_instance.is_closed():
            asyncio.run_coroutine_threadsafe(bot_instance.close(), bot_instance.loop)
    except:
        pass
    
    try:
        bot_instance = create_bot()
        BOT_DURUMU = "Aktif (Çalışıyor)"
        bot_instance.run(BOT_TOKEN)
    except Exception as e:
        BOT_DURUMU = "Kapalı / Hata"
        print("Bot başlatma hatası:", e)

@app.get("/bot-ac", response_class=RedirectResponse)
def bot_ac():
    global bot_thread, BOT_DURUMU
    if BOT_DURUMU != "Aktif (Çalışıyor)":
        BOT_DURUMU = "Başlatılıyor..."
        bot_thread = threading.Thread(target=botu_baslat_arka_planda)
        bot_thread.daemon = True
        bot_thread.start()
    return RedirectResponse(url="/", status_code=303)

@app.get("/bot-reset", response_class=RedirectResponse)
def bot_reset():
    global BOT_DURUMU
    BOT_DURUMU = "🔄 Hot Reset Atılıyor..."
    try:
        if bot_instance and not bot_instance.is_closed():
            asyncio.run_coroutine_threadsafe(bot_instance.close(), bot_instance.loop)
    except:
        pass

    def yeniden_baslat():
        import time
        time.sleep(1)
        botu_baslat_arka_planda()
    
    t = threading.Thread(target=yeniden_baslat)
    t.daemon = True
    t.start()
    return RedirectResponse(url="/", status_code=303)

@app.get("/bot-kapat", response_class=RedirectResponse)
def bot_kapat():
    global BOT_DURUMU, bot_instance
    BOT_DURUMU = "Kapalı"
    try:
        if bot_instance and not bot_instance.is_closed():
            asyncio.run_coroutine_threadsafe(bot_instance.close(), bot_instance.loop)
    except:
        pass
    return RedirectResponse(url="/", status_code=303)

@app.post("/guncelle-sayac", response_class=RedirectResponse)
def guncelle_sayac(hedef: int = Form(...), kanal: str = Form(...), giris: str = Form(...), cikis: str = Form(...)):
    BOT_AYARLARI["hedef_uye"] = hedef
    BOT_AYARLARI["sayac_kanal"] = kanal
    BOT_AYARLARI["giris_mesaji"] = giris
    BOT_AYARLARI["cikis_mesaji"] = cikis
    ayarlari_kaydet(BOT_AYARLARI)
    return RedirectResponse(url="/", status_code=303)

@app.post("/guncelle-tavsiye", response_class=RedirectResponse)
def guncelle_tavsiye(kanal: str = Form(...), baslik: str = Form(...)):
    BOT_AYARLARI["tavsiye_kanal"] = kanal
    BOT_AYARLARI["tavsiye_baslik"] = baslik
    ayarlari_kaydet(BOT_AYARLARI)
    return RedirectResponse(url="/", status_code=303)

@app.post("/guncelle-log", response_class=RedirectResponse)
def guncelle_log(log_kanal: str = Form(...)):
    BOT_AYARLARI["log_kanal"] = log_kanal
    ayarlari_kaydet(BOT_AYARLARI)
    return RedirectResponse(url="/", status_code=303)

@app.post("/guncelle-youtube", response_class=RedirectResponse)
def guncelle_youtube(youtube_channel_id: str = Form(""), youtube_kanal: str = Form(...), youtube_mesaj: str = Form(...)):
    eski_giris = BOT_AYARLARI.get("youtube_channel_id", "")
    yeni_giris = youtube_channel_id.strip()
    if eski_giris != yeni_giris:
        BOT_AYARLARI["son_video_id"] = ""
    BOT_AYARLARI["youtube_channel_id"] = yeni_giris
    BOT_AYARLARI["youtube_kanal"] = youtube_kanal
    BOT_AYARLARI["youtube_mesaj"] = youtube_mesaj
    ayarlari_kaydet(BOT_AYARLARI)
    return RedirectResponse(url="/", status_code=303)

@app.post("/guncelle-komutlar", response_class=RedirectResponse)
def guncelle_komutlar(sil_max_limit: int = Form(...)):
    BOT_AYARLARI["sil_max_limit"] = max(1, min(100, sil_max_limit))
    ayarlari_kaydet(BOT_AYARLARI)
    return RedirectResponse(url="/", status_code=303)

@app.post("/duyuru-gonder", response_class=RedirectResponse)
def duyuru_gonder(hedef_kanal: str = Form(...), duyuru_mesaji: str = Form(...)):
    if bot_instance and not bot_instance.is_closed() and bot_instance.guilds:
        async def mesaj_at():
            for guild in bot_instance.guilds:
                for channel in guild.text_channels:
                    if channel.name.lower() == hedef_kanal.lower():
                        await channel.send(duyuru_mesaji)
                        return
        try:
            asyncio.run_coroutine_threadsafe(mesaj_at(), bot_instance.loop)
        except Exception as e:
            print("Canlı duyuru hatası:", e)
    return RedirectResponse(url="/", status_code=303)

@app.post("/guncelle-kod", response_class=RedirectResponse)
def guncelle_kod(yeni_kod: str = Form(...)):
    try:
        with open(EXTENSION_FILE, "w", encoding="utf-8") as f:
            f.write(yeni_kod)
    except Exception as e:
        print("Kod kaydetme hatası:", e)
    return RedirectResponse(url="/bot-reset", status_code=303)

def fastapi_baslat():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

if __name__ == "__main__":
    server_thread = threading.Thread(target=fastapi_baslat)
    server_thread.daemon = True
    server_thread.start()

    webview.create_window("YNK Studio - MEE6 Dashboard", "http://127.0.0.1:8000", width=1280, height=800)
    webview.start()