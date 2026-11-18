# YNK BOT

Discord botu + yerel yönetim paneli. Tek bir `bot.py` dosyası yerine artık
küçük ve yönetilebilir modüllerden oluşur.

## Hızlı başlangıç

1. Gerekli paketleri kur:
   ```powershell
   pip install -r requirements.txt
   ```
2. `.env.example` dosyasını `.env` olarak kopyala ve Discord token'ını yaz:
   ```
   DISCORD_TOKEN=yeni_token_buraya
   ```
3. Botu ve paneli başlat:
   ```powershell
   python bot.py
   ```
4. Panel: http://127.0.0.1:8000
5. Panelden **Botu Başlat** butonuna bas.

> **Önemli:** `.env` dosyası gizlidir ve Git'e eklenmez. Token'ı kimseyle
> paylaşma. Token yenilendiyse `.env` içindeki `DISCORD_TOKEN` satırını güncelle.

## Proje yapısı

```
YNK BOT/
├── bot.py                  # Başlatıcı: panel sunucusu + webview penceresi
├── config.py               # Token, ayarlar, log, .env okuyucu
├── utils.py                # Ortak yardımcılar (kanal bulma, escape)
├── core/
│   ├── manager.py          # Botu ayrı thread'de başlat/durdur/yeniden başlat
│   ├── bot_factory.py      # Discord botu ve hata yönetimi
│   └── user_extension.py   # Kullanıcı kod uzantısını yükleme
├── cogs/
│   ├── sayac.py            # Üye giriş/çıkış sayaç sistemi
│   ├── karsilama.py        # Karşılama, veda ve otomatik rol
│   ├── tavsiye.py          # /tavsiye komutu
│   ├── moderasyon.py       # /sil komutu
│   ├── log.py              # Denetim günlüğü
│   ├── youtube.py          # YouTube video/Shorts bildirimi
│   ├── moderasyon.py       # /sil, /ban, /kick, /timeout, /uyari komutları
│   └── tickets.py          # Ticket (destek) sistemi
├── web/
│   ├── app.py              # FastAPI panel rotaları
│   └── templates/
│       └── index.html      # Panel arayüzü (Jinja2)
├── settings.json           # Bot ayarları
├── user_extension.py       # Paneldeki kod uzantısı dosyası
├── bot.log                 # Çalışma logları
├── .env                    # Gizli token (Git'e girmez)
├── .env.example            # Token örneği
├── requirements.txt
└── bot.spec                # PyInstaller derleme ayarları
```

## Komutlar

| Komut | Açıklama |
|-------|----------|
| `/sil [miktar]` | Bulunduğun kanaldan belirtilen sayıda mesajı siler. |
| `/tavsiye [mesaj]` | Tavsiye kanalına öneri gönderir, ✅/❌ tepkileri ekler. |
| `/ban [üye] [sebep]` | Üyeyi sunucudan yasaklar. |
| `/kick [üye] [sebep]` | Üyeyi sunucudan atar. |
| `/timeout [üye] [dakika] [sebep]` | Üyeyi belirtilen süre susturur. |
| `/uyari [üye] [sebep]` | Üyeye uyarı verir (kayıtlı). |
| `/uyarilar [üye]` | Üyenin uyarı geçmişini gösterir. |
| `/uyari-temizle [üye]` | Üyenin uyarılarını sıfırlar. |

## Panel özellikleri

- Botu başlat / kapat / Hot Reset
- Sayaç sistemi (hedef üye, giriş/çıkış mesajları, kanal)
- Karşılama & veda (kanal, başlık, mesaj, renk, otomatik rol, botları da karşılama)
- Karşılama test mesajı gönderme
- Tavsiye sistemi (kanal ve başlık)
- Mod log kanalı
- YouTube otomasyonu (`@handle`, link veya `UC...` kanal ID'si)
- Canlı duyuru gönderme
- Kod uzantısı dosyasını düzenleme
- SQLite veritabanı (ynk.db) ile kalıcı ayarlar, uyarılar, ticket kayıtları

### Kanal ID'leri

Ayarlar artık kanal **adı** ile birlikte kanal **ID'sini** de saklar:
`sayac_kanal_id`, `tavsiye_kanal_id`, `log_kanal_id`, `youtube_kanal_id`.
Bot ilk bağlandığında eksik ID'leri kanal adından bulup `settings.json`'a
otomatik yazar. Kanal yeniden adlandırılsa bile sistem çalışmaya devam eder.
ID bulunamazsa eski davranış olarak kanal adı kullanılır.

> `guild_id` alanı, ayarların hangi sunucuya ait olduğunu belirtir. Bot birden
> fazla sunucudaysa panel ve duyurular bu sunucuyu kullanır.

> **Kod Uzantısı:** `user_extension.py` içindeki kod bot her başladığında
> otomatik çalışır. Dosyada `async def setup(bot)` tanımlarsan bu fonksiyon
> çağrılır; içinde `await bot.add_cog(...)` ile yeni özellik ekleyebilirsin.
> Kodda hata olursa bot durmaz, hata panelde ve `bot.log` dosyasında görünür.

## Loglar

- `bot.log`: bot, panel ve hata logları.
- PyInstaller ile derlenen exe'de `console=False` olduğu için hataları görmek
  için bu dosyaya bak.

### Log kanalına yazılan olaylar

| Olay | Açıklama |
|------|----------|
| Mesaj silindi / toplu silindi / düzenlendi | Kanal, yazar, içerik |
| Kanal pin güncellemesi | |
| Ban / unban | Banlanan veya banı kaldırılan kullanıcı |
| Kanal oluşturma / silme / güncelleme | Ad, konu, yavaş mod, NSFW, kategori |
| Rol oluşturma / silme / güncelleme | Ad, renk, izinler, görünürlük |
| Emoji / sticker güncelleme | |
| Webhook güncelleme | |
| Sunucu güncelleme | Ad, ikon, splash, vanity URL, sistem kanalı |
| Davet oluşturma / silme | |
| Entegrasyon ekleme / kaldırma | |
| Thread oluşturma / silme / güncelleme | |
| Ses kanalı katılım / ayrılma / değiştirme | |
| Ses durumu güncelleme | Self-mute, self-deaf, server mute/deaf |
| Stage başlatma / bitirme / konu güncelleme | |
| Etkinlik oluşturma / silme / güncelleme | |
| AutoMod kural oluşturma / silme / güncelleme / aksiyon | |
| Üye katılım / ayrılma / güncelleme | Takma ad, rol ekleme/çıkarma, susturma |
| Üye güncelleme | Takma ad, rol ekleme/çıkarma, susturma |

## EXE olarak çalıştırma (tek tık)

- `YNK-BOT.exe` dosyasına çift tıkla → panel penceresi açılır.
- Masaüstündeki **YNK BOT** kısayolu da aynı exe'yi açar.
- `.env`, `settings.json` ve `user_extension.py` exe ile aynı klasörde kalmalı.
- İlk açılışta Windows "Bilinmeyen yayıncı" uyarısı verebilir:
  **Daha fazla bilgi → Yine de çalıştır**.

### Kod değiştirme

| Ne yapmak istiyorsun? | Yol |
|---|---|
| Küçük ekleme/deneme | Panel → **Kod Uzantısı** → kaydet (bot yeniden başlar, exe gerekmez) |
| Kaynak koddan hızlı çalıştırma | `GELISTIR.bat` çift tık (kod değişiklikleri hemen geçerli) |
| Yeni exe üretme | `DERLE.bat` çift tık → `YNK-BOT.exe` güncellenir (1-2 dk) |

> Exe'nin içindeki kodu doğrudan düzenleyemezsin. Kaynak `.py` dosyalarını
> düzenleyip `DERLE.bat` ile yeniden paketle. Derlemeden önce uygulamayı kapat.

### Manuel derleme

```powershell
python -m PyInstaller --noconfirm --clean bot.spec
copy dist\bot.exe YNK-BOT.exe
```

- `.env` ve `settings.json` dosyaları exe ile aynı klasörde olmalı.
- Şablonlar exe içine gömülür.

## Git ile geri dönüş

Her önemli adımdan sonra commit atılır. Bir şey bozulursa:

```powershell
git log --oneline
git checkout -- dosya.py
```

## Hoşgeldin Görseli

Karşılama sisteminde resimli hoşgeldin kartı (avatar + isim + üye sayısı) gönderilebilir. Panelde "Karşılama" sekmesinden aç/kapat ve metinleri özelleştir.

## Cloud / 7-24 Çalıştırma

Oracle Cloud Free Tier ile botu 7/24 çalıştırabilirsiniz:

1. Oracle Cloud hesabı oluştur (free tier, kredi kartı ister ama ücret alınmaz).
2. Compute → Create Instance → Ubuntu 22.04/24.04, Always Free shape (VM.Standard.E2.1.Micro).
3. SSH ile bağlan.
4. `setup_oracle.sh` scriptini çalıştır.
5. `.env` dosyasına token yaz, `settings.json` ve `ynk.db` dosyalarını `scp` ile yükle.
6. `ynk-bot.service` dosyasını systemd'ye kur (script içindeki adımlar).
7. Oracle Cloud Console → Networking → Security Lists → Ingress Rules → port 8000'i aç (0.0.0.0/0).
8. Panel: `http://SUNUCU_IP:8000`

Not: GUI (pywebview) sunucuda çalışmaz; panel tarayıcıdan açılır. Bot headless olarak `bot_headless.py` ile çalışır.

## Yedek

Faz 0 sırasında eski sürüm şu klasöre yedeklendi:

```
Masaüstü\YNK BOT - Yedek (2026-11-17)
```

## Faz 2 yol haritası

1. ~~"Kod Uzantısı" sekmesini gerçekten çalıştırma~~ ✅
2. ~~Hot Reset'i daha güvenilir hale getirme~~ ✅
3. ~~Log sistemini tamamlama (ban, kick, mesaj düzenleme, kanal/rol olayları)~~ ✅
4. ~~Kanal adları yerine kanal ID'leri~~ ✅
5. SQLite veritabanı + sunucu bazlı ayarlar
6. Moderasyon komutları (ban, kick, timeout, warn)
7. Otomatik moderasyon (spam, reklam, küfür, raid)
8. Topluluk özellikleri:
   - ~~Karşılama & veda + otomatik rol~~ ✅
   - Reaksiyon rolleri / butonlu rol menüsü
   - Ticket sistemi
   - Seviye/XP sistemi
