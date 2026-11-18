"""
Hosgeldin gorseli olusturucu (Pillow).
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


def _yuvarlak_avatar(avatar_bytes, boyut=200):
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
    genislik=1100,
    yukseklik=420,
):
    """Hosgeldin gorseli olusturur ve PNG bytes dondurur."""
    random.seed(42)  # tutarli sonuc

    # --- Arka plan: koyu mor-mavi gradient (diagonal) ---
    img = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    for y in range(yukseklik):
        for x in range(0, genislik, 2):
            oran = (x / genislik + y / yukseklik) / 2
            r = int(12 + 30 * oran)
            g = int(8 + 20 * oran)
            b = int(35 + 55 * oran)
            draw.point((x, y), fill=(r, g, b, 255))
            draw.point((x + 1, y), fill=(r, g, b, 255))

    # --- Geometrik desen: hexagonal grid (noktalar) ---
    nokta_renk = (88, 101, 242)
    for row in range(0, yukseklik + 40, 35):
        offset = 0 if (row // 35) % 2 == 0 else 17
        for col in range(offset, genislik + 40, 35):
            # rastgele boyut ve opaklik
            r = random.randint(1, 3)
            alpha = random.randint(20, 60)
            draw.ellipse(
                (col - r, row - r, col + r, row + r),
                fill=(nokta_renk[0], nokta_renk[1], nokta_renk[2], alpha),
            )

    # --- Buyuk dekoratif daireler (glow) ---
    # Sol ust: mor daire
    for radius in range(180, 0, -2):
        alpha = int(6 * (1 - radius / 180))
        draw.ellipse(
            (-radius + 60, -radius + 60, radius + 60, radius + 60),
            fill=(114, 137, 222, alpha),
        )
    # Sag alt: mavi daire
    for radius in range(150, 0, -2):
        alpha = int(5 * (1 - radius / 150))
        draw.ellipse(
            (genislik - radius - 40, yukseklik - radius - 40, genislik + radius - 40, yukseklik + radius - 40),
            fill=(88, 101, 242, alpha),
        )

    # --- Diagonal accent cizgileri (ince, mor) ---
    for i in range(0, genislik, 80):
        draw.line([(i, 0), (i + yukseklik, yukseklik)], fill=(114, 137, 222, 15), width=1)

    # --- Sol kenar vurgu (kalın, gradient) ---
    for y in range(yukseklik):
        oran = y / yukseklik
        r = int(88 + 26 * oran)
        g = int(101 + 36 * oran)
        b = int(242 - 20 * oran)
        draw.line([(0, y), (5, y)], fill=(r, g, b, 255))

    # --- Avatar (sol taraf) ---
    avatar_boyut = 180
    avatar = _yuvarlak_avatar(avatar_bytes, avatar_boyut)
    avatar_x = 55
    avatar_y = (yukseklik - avatar_boyut) // 2

    # Avatar cercevesi (glow ring)
    for i in range(6, 0, -1):
        alpha = int(80 * (1 - i / 6))
        draw.ellipse(
            (
                avatar_x - i - 4,
                avatar_y - i - 4,
                avatar_x + avatar_boyut + i + 4,
                avatar_y + avatar_boyut + i + 4,
            ),
            outline=(88, 101, 242, alpha),
            width=2,
        )
    draw.ellipse(
        (
            avatar_x - 4,
            avatar_y - 4,
            avatar_x + avatar_boyut + 4,
            avatar_y + avatar_boyut + 4,
        ),
        outline=(114, 137, 222, 255),
        width=3,
    )

    img.paste(avatar, (avatar_x, avatar_y), avatar)

    # --- Metin (sag taraf) ---
    metin_x = avatar_x + avatar_boyut + 55
    metin_y = 65

    font_baslik = _font(54, bold=True)
    font_isim = _font(40, bold=True)
    font_alt = _font(20)
    font_sayi = _font(15)

    # Baslik
    draw.text((metin_x, metin_y), baslik, font=font_baslik, fill=(255, 255, 255, 255))
    metin_y += 68

    # Uye adi (mor-mavi)
    draw.text((metin_x, metin_y), uye_adi, font=font_isim, fill=(130, 150, 235, 255))
    metin_y += 54

    # Mesaj
    draw.text((metin_x, metin_y), mesaj, font=font_alt, fill=(170, 175, 200, 255))
    metin_y += 38

    # Sunucu adi ve uye sayisi
    draw.text((metin_x, metin_y), f"{sunucu_adi}  •  Üye #{uye_sayisi}", font=font_sayi, fill=(110, 115, 145, 255))

    # PNG olarak bytes'a cevir
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
