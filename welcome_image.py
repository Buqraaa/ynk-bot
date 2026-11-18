"""
Hosgeldin gorseli olusturucu (Pillow).
"""
import io
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Varsayilan font yolu (sistem fontu)
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
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


def _yuvarlak_avatar(avatar_bytes, boyut=120):
    """Avatar'i dairesel keser."""
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
    arka_plan_renk=(15, 20, 35),
    vurgu_renk=(88, 101, 242),
    genislik=1000,
    yukseklik=400,
):
    """Hosgeldin gorseli olusturur ve PNG bytes dondurur."""
    img = Image.new("RGBA", (genislik, yukseklik), arka_plan_renk + (255,))
    draw = ImageDraw.Draw(img)

    # Gradient arka plan (ustten alta)
    for y in range(yukseklik):
        oran = y / yukseklik
        r = int(arka_plan_renk[0] + (vurgu_renk[0] - arka_plan_renk[0]) * oran * 0.3)
        g = int(arka_plan_renk[1] + (vurgu_renk[1] - arka_plan_renk[1]) * oran * 0.3)
        b = int(arka_plan_renk[2] + (vurgu_renk[2] - arka_plan_renk[2]) * oran * 0.3)
        draw.line([(0, y), (genislik, y)], fill=(r, g, b, 255))

    # Vurgu cizgisi (sol kenar)
    draw.rectangle([(0, 0), (6, yukseklik)], fill=vurgu_renk + (255,))

    # Avatar (sol taraf, ortalanmis)
    avatar_boyut = 180
    avatar = _yuvarlak_avatar(avatar_bytes, avatar_boyut)
    avatar_x = 50
    avatar_y = (yukseklik - avatar_boyut) // 2

    # Avatar cercevesi
    cerceve_padding = 8
    draw.ellipse(
        (
            avatar_x - cerceve_padding,
            avatar_y - cerceve_padding,
            avatar_x + avatar_boyut + cerceve_padding,
            avatar_y + avatar_boyut + cerceve_padding,
        ),
        outline=vurgu_renk + (255,),
        width=4,
    )

    img.paste(avatar, (avatar_x, avatar_y), avatar)

    # Metin (sag taraf)
    metin_x = avatar_x + avatar_boyut + 50
    metin_y = 80

    font_baslik = _font(48, bold=True)
    font_isim = _font(36, bold=True)
    font_alt = _font(20)
    font_sayi = _font(16)

    # Baslik
    draw.text((metin_x, metin_y), baslik, font=font_baslik, fill=(255, 255, 255, 255))
    metin_y += 60

    # Uye adi
    draw.text((metin_x, metin_y), uye_adi, font=font_isim, fill=vurgu_renk + (255,))
    metin_y += 50

    # Mesaj
    draw.text((metin_x, metin_y), mesaj, font=font_alt, fill=(180, 185, 200, 255))
    metin_y += 35

    # Sunucu adi ve uye sayisi
    draw.text((metin_x, metin_y), f"{sunucu_adi}  •  Üye #{uye_sayisi}", font=font_sayi, fill=(120, 125, 140, 255))

    # PNG olarak bytes'a cevir
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
