"""
Hosgeldin gorseli olusturucu (Pillow).
Referans: temiz, modern, mor-mavi, avatar sol, metin sag, alt bar.
"""
import io
import os

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
    # Mor-mavi gradient arka plan (dikey, koyu)
    img = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    for y in range(yukseklik):
        oran = y / yukseklik
        # koyu lacivert (#0a0e1a) -> koyu mor (#1a1030)
        r = int(10 + 16 * oran)
        g = int(14 + 6 * oran)
        b = int(26 + 25 * oran)
        draw.line([(0, y), (genislik, y)], fill=(r, g, b, 255))

    # Avatar (sol orta)
    avatar_boyut = 160
    avatar = _yuvarlak_avatar(avatar_bytes, avatar_boyut)
    avatar_x = 40
    avatar_y = 90

    # Avatar cercevesi (mor-mavi, ince)
    draw.ellipse(
        (
            avatar_x - 5,
            avatar_y - 5,
            avatar_x + avatar_boyut + 5,
            avatar_y + avatar_boyut + 5,
        ),
        outline=(88, 101, 242, 255),
        width=3,
    )

    img.paste(avatar, (avatar_x, avatar_y), avatar)

    # Metin (sag taraf)
    metin_x = avatar_x + avatar_boyut + 30
    metin_y = 90

    font_baslik = _font(34, bold=True)
    font_isim = _font(26, bold=True)
    font_alt = _font(15)
    font_sayi = _font(13)

    # Baslik
    draw.text((metin_x, metin_y), baslik, font=font_baslik, fill=(255, 255, 255, 255))
    metin_y += 46

    # Uye adi (mor-mavi vurgu)
    draw.text((metin_x, metin_y), uye_adi, font=font_isim, fill=(114, 137, 222, 255))
    metin_y += 38

    # Mesaj
    draw.text((metin_x, metin_y), mesaj, font=font_alt, fill=(170, 175, 200, 255))
    metin_y += 30

    # Sunucu adi ve uye sayisi
    draw.text((metin_x, metin_y), f"{sunucu_adi}  •  Üye #{uye_sayisi}", font=font_sayi, fill=(110, 115, 145, 255))

    # Alt bar (mor-mavi gradient, sol kenardan baslayip ortaya kadar)
    bar_y = yukseklik - 50
    bar_genislik = int(genislik * 0.6)
    for i in range(bar_genislik):
        oran = i / bar_genislik
        r = int(88 + 26 * oran)
        g = int(101 + 36 * oran)
        b = int(242 - 20 * oran)
        draw.line([(20 + i, bar_y), (20 + i, bar_y + 4)], fill=(r, g, b, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
