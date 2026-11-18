"""
Hosgeldin gorseli olusturucu (Pillow).
"""
import io
import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

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
    """Avatar'i yuksek kalitede dairesel keser."""
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
    # Mor-mavi gradient arka plan
    img = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # Gradient: koyu mor -> koyu mavi
    for y in range(yukseklik):
        oran = y / yukseklik
        r = int(18 + (40 - 18) * oran)
        g = int(15 + (25 - 15) * oran)
        b = int(45 + (80 - 45) * oran)
        draw.line([(0, y), (genislik, y)], fill=(r, g, b, 255))

    # Hafif desen: ince diagonal cizgiler
    for i in range(0, genislik + yukseklik, 40):
        draw.line([(i, 0), (i - yukseklik, yukseklik)], fill=(88, 101, 242, 12), width=1)

    # Vurgu cizgisi (sol kenar, mor-mavi gradient)
    for y in range(yukseklik):
        oran = y / yukseklik
        r = int(88 + (114 - 88) * oran)
        g = int(101 + (137 - 101) * oran)
        b = int(242 + (222 - 242) * oran)
        draw.point((4, y), fill=(r, g, b, 255))
        draw.point((5, y), fill=(r, g, b, 255))

    # Sag ust köşe glow (mor)
    glow = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for radius in range(120, 0, -1):
        alpha = int(18 * (1 - radius / 120))
        gdraw.ellipse(
            (genislik - radius - 40, -radius + 40, genislik + radius - 40, radius + 40),
            fill=(114, 137, 222, alpha),
        )
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # Sol alt köşe glow (mavi)
    glow2 = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 0))
    gdraw2 = ImageDraw.Draw(glow2)
    for radius in range(100, 0, -1):
        alpha = int(12 * (1 - radius / 100))
        gdraw2.ellipse(
            (-radius + 20, yukseklik - radius - 20, radius + 20, yukseklik + radius - 20),
            fill=(88, 101, 242, alpha),
        )
    img = Image.alpha_composite(img, glow2)
    draw = ImageDraw.Draw(img)

    # Avatar (sol taraf)
    avatar_boyut = 180
    avatar = _yuvarlak_avatar(avatar_bytes, avatar_boyut)
    avatar_x = 50
    avatar_y = (yukseklik - avatar_boyut) // 2

    # Avatar cercevesi (mor-mavi gradient)
    cerceve_padding = 8
    for i in range(3):
        draw.ellipse(
            (
                avatar_x - cerceve_padding - i,
                avatar_y - cerceve_padding - i,
                avatar_x + avatar_boyut + cerceve_padding + i,
                avatar_y + avatar_boyut + cerceve_padding + i,
            ),
            outline=(88 + i * 10, 101 + i * 12, 242 - i * 5, 255 - i * 60),
            width=2,
        )

    img.paste(avatar, (avatar_x, avatar_y), avatar)

    # Metin (sag taraf)
    metin_x = avatar_x + avatar_boyut + 50
    metin_y = 70

    font_baslik = _font(52, bold=True)
    font_isim = _font(38, bold=True)
    font_alt = _font(20)
    font_sayi = _font(16)

    # Baslik
    draw.text((metin_x, metin_y), baslik, font=font_baslik, fill=(255, 255, 255, 255))
    metin_y += 65

    # Uye adi (mor-mavi vurgu)
    draw.text((metin_x, metin_y), uye_adi, font=font_isim, fill=(114, 137, 222, 255))
    metin_y += 52

    # Mesaj
    draw.text((metin_x, metin_y), mesaj, font=font_alt, fill=(180, 185, 210, 255))
    metin_y += 36

    # Sunucu adi ve uye sayisi
    draw.text((metin_x, metin_y), f"{sunucu_adi}  •  Üye #{uye_sayisi}", font=font_sayi, fill=(120, 125, 150, 255))

    # PNG olarak bytes'a cevir (yuksek kalite)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
