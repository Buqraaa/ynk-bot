"""
Hosgeldin gorseli olusturucu (Pillow).
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


def _yuvarlak_avatar(avatar_bytes, boyut=150):
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
    # Mor-mavi gradient arka plan (dikey)
    img = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    for y in range(yukseklik):
        oran = y / yukseklik
        # koyu mor (#1a1033) -> koyu mavi (#0f1a3a)
        r = int(26 + (15 - 26) * oran)
        g = int(16 + (26 - 16) * oran)
        b = int(51 + (58 - 51) * oran)
        draw.line([(0, y), (genislik, y)], fill=(r, g, b, 255))

    # Sol kenar vurgu (mor-mavi)
    for y in range(yukseklik):
        oran = y / yukseklik
        r = int(88 + 26 * oran)
        g = int(101 + 36 * oran)
        b = int(242 - 20 * oran)
        draw.line([(0, y), (4, y)], fill=(r, g, b, 255))

    # Avatar (ust orta)
    avatar_boyut = 130
    avatar = _yuvarlak_avatar(avatar_bytes, avatar_boyut)
    avatar_x = (genislik - avatar_boyut) // 2
    avatar_y = 40

    # Avatar cercevesi
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

    # Metin (ortalanmis)
    metin_x = genislik // 2
    metin_y = avatar_y + avatar_boyut + 30

    font_baslik = _font(40, bold=True)
    font_isim = _font(28, bold=True)
    font_alt = _font(16)
    font_sayi = _font(13)

    # Baslik (ortalanmis)
    bbox = draw.textbbox((0, 0), baslik, font=font_baslik)
    text_w = bbox[2] - bbox[0]
    draw.text((metin_x - text_w // 2, metin_y), baslik, font=font_baslik, fill=(255, 255, 255, 255))
    metin_y += 50

    # Uye adi (mor-mavi, ortalanmis)
    bbox = draw.textbbox((0, 0), uye_adi, font=font_isim)
    text_w = bbox[2] - bbox[0]
    draw.text((metin_x - text_w // 2, metin_y), uye_adi, font=font_isim, fill=(130, 150, 235, 255))
    metin_y += 42

    # Mesaj (ortalanmis)
    bbox = draw.textbbox((0, 0), mesaj, font=font_alt)
    text_w = bbox[2] - bbox[0]
    draw.text((metin_x - text_w // 2, metin_y), mesaj, font=font_alt, fill=(180, 185, 210, 255))
    metin_y += 30

    # Sunucu adi ve uye sayisi (ortalanmis)
    alt_text = f"{sunucu_adi}  •  Üye #{uye_sayisi}"
    bbox = draw.textbbox((0, 0), alt_text, font=font_sayi)
    text_w = bbox[2] - bbox[0]
    draw.text((metin_x - text_w // 2, metin_y), alt_text, font=font_sayi, fill=(120, 125, 150, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
