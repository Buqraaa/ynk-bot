"""
Hosgeldin gorseli olusturucu (Pillow).
Kis (winter) temasi: buz mavisi, kar taneleri, soguk gradient.
"""
import io
import os
import random

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _font(size, bold=False):
    adaylar = _FONT_CANDIDATES[:]
    if bold:
        adaylar = [p.replace(".ttf", "b.ttf") for p in adaylar] + adaylar
    for yol in adaylar:
        if os.path.isfile(yol):
            try:
                return ImageFont.truetype(yol, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _yuvarlak_avatar(avatar_bytes, boyut=160):
    img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    img = img.resize((boyut, boyut), Image.LANCZOS)
    maske = Image.new("L", (boyut, boyut), 0)
    draw = ImageDraw.Draw(maske)
    draw.ellipse((0, 0, boyut, boyut), fill=255)
    sonuc = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    sonuc.paste(img, (0, 0), maske)
    return sonuc


def hosgeldin_gorseli_olustur(
    avatar_bytes,
    uye_adi,
    sunucu_adi,
    uye_sayisi,
    baslik="Hoş geldin!",
    mesaj="Sunucumuza katıldı",
    genislik=600,
    yukseklik=450,
):
    """Hosgeldin gorseli olusturur ve PNG bytes dondurur."""
    random.seed(7)  # tutarli sonuc

    # --- Arka plan: kis gokyuzu gradient (koyu lacivert -> buz mavisi) ---
    img = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    for y in range(yukseklik):
        oran = y / yukseklik
        # koyu gece mavisi (#0a1628) -> buz mavisi (#1a2a4a)
        r = int(10 + 16 * oran)
        g = int(22 + 20 * oran)
        b = int(40 + 35 * oran)
        draw.line([(0, y), (genislik, y)], fill=(r, g, b, 255))

    # --- Kar taneleri (rastgele, farkli boyutlar) ---
    for _ in range(80):
        x = random.randint(0, genislik)
        y = random.randint(0, yukseklik)
        r = random.choice([1, 1, 2, 2, 3])
        alpha = random.randint(40, 120)
        # hafif mavi-beyaz kar tanesi
        draw.ellipse(
            (x - r, y - r, x + r, y + r),
            fill=(200 + random.randint(0, 55), 210 + random.randint(0, 45), 230 + random.randint(0, 25), alpha),
        )

    # --- Uzak kar tanesi (buyuk, bulanik hissi) ---
    for _ in range(12):
        x = random.randint(0, genislik)
        y = random.randint(0, yukseklik)
        r = random.randint(4, 8)
        alpha = random.randint(8, 20)
        draw.ellipse(
            (x - r, y - r, x + r, y + r),
            fill=(180, 200, 230, alpha),
        )

    # --- Sol kenar vurgu (buz mavisi) ---
    for y in range(yukseklik):
        oran = y / yukseklik
        r = int(100 + 40 * oran)
        g = int(160 + 40 * oran)
        b = int(220 + 35 * oran)
        for x in range(4):
            draw.point((x, y), fill=(r, g, b, 200))

    # --- Avatar (sol orta) ---
    avatar_boyut = 160
    avatar = _yuvarlak_avatar(avatar_bytes, avatar_boyut)
    avatar_x = 40
    avatar_y = 85

    # Avatar cercevesi (buz mavisi)
    draw.ellipse(
        (
            avatar_x - 5,
            avatar_y - 5,
            avatar_x + avatar_boyut + 5,
            avatar_y + avatar_boyut + 5,
        ),
        outline=(150, 200, 255, 255),
        width=3,
    )

    img.paste(avatar, (avatar_x, avatar_y), avatar)

    # --- Metin (sag taraf) ---
    metin_x = avatar_x + avatar_boyut + 30
    metin_y = 85

    font_baslik = _font(36, bold=True)
    font_isim = _font(26, bold=True)
    font_alt = _font(15)
    font_sayi = _font(13)

    # Baslik (buz mavisi)
    draw.text((metin_x, metin_y), baslik, font=font_baslik, fill=(220, 235, 255, 255))
    metin_y += 48

    # Uye adi (parlak buz mavisi)
    draw.text((metin_x, metin_y), uye_adi, font=font_isim, fill=(150, 200, 255, 255))
    metin_y += 38

    # Mesaj
    draw.text((metin_x, metin_y), mesaj, font=font_alt, fill=(180, 200, 225, 255))
    metin_y += 30

    # Sunucu adi ve uye sayisi
    draw.text((metin_x, metin_y), f"{sunucu_adi}  •  Üye #{uye_sayisi}", font=font_sayi, fill=(130, 150, 185, 255))

    # Alt bar (buz mavisi gradient)
    bar_y = yukseklik - 45
    bar_genislik = int(genislik * 0.55)
    for i in range(bar_genislik):
        oran = i / bar_genislik
        r = int(100 + 50 * oran)
        g = int(160 + 40 * oran)
        b = int(220 + 35 * oran)
        draw.line([(20 + i, bar_y), (20 + i, bar_y + 3)], fill=(r, g, b, 200))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
