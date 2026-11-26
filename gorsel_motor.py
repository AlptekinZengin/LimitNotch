"""Limit Çubuğu yüksek kaliteli 3× supersampling görsel çizim motoru.

Pillow (PIL) + Windows TrueType Segoe UI + LANCZOS anti-aliasing kullanarak
çentik, açık panel, detay kartı ve yüzer bildirim (toast) görsellerini
sıfır tırtıkla, cam gibi keskin ve göz yormayan koyu temada üretir.

Harici bağımlılık: yalnızca Pillow (PIL) ve Python standart kütüphanesi.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
import math
import os
import time
from typing import Any

from PIL import Image, ImageDraw, ImageFont

import dil

# ---------------------------------------------------------------- sabitler & palet
S = 3  # 3× supersampling katsayısı
_RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS

# Göz yormayan derin koyu lacivert-antrasit palet
ZEMIN_UST = "#121C32"
ZEMIN_ORTA = "#0D1424"
ZEMIN_ALT = "#090F1D"
YUZEY = "#152036"
YUZEY_AKTIF = "#1B2A47"
YUZEY_HOVER = "#213254"
IZ = "#1C2944"
IZ_KOYU = "#0B1120"
KENAR = "#24324D"
KENAR_PARLAK = "#33476B"

YAZI = "#F8FAFC"
IKINCIL = "#CBD5E1"
SOLUK = "#94A3B8"

YESIL = "#34D399"
AMBER = "#FBBF24"
KIRMIZI = "#F87171"
VURGU = "#38BDF8"
GRI = "#94A3B8"

ARAC_SIRA = ("claude", "codex", "antigravity")
ARAC_BILGI = {
    "claude": {"ad": "Claude", "renk": "#D97757"},
    "codex": {"ad": "Codex", "renk": "#10B981"},
    "antigravity": {"ad": "Antigravity", "renk": "#38BDF8"},
}

GUNLER = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")

_FONT_DIZIN = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
_FONT_ADAYLARI = {
    "bold": ("segoeuib.ttf", "seguisb.ttf", "SegoeUIVF.ttf", "segoeui.ttf"),
    "semibold": ("seguisb.ttf", "segoeuib.ttf", "SegoeUIVF.ttf", "segoeui.ttf"),
    "regular": ("segoeui.ttf", "seguisb.ttf", "SegoeUIVF.ttf"),
}


# ---------------------------------------------------------------- renk & metin yardımcıları
def _hex_rgba(renk: str, alpha: int = 255) -> tuple[int, int, int, int]:
    """'#RRGGBB' veya '#RRGGBBAA' dizgisini (r, g, b, a) demetine çevirir."""
    if not isinstance(renk, str):
        return (203, 213, 225, max(0, min(255, int(alpha))))
    h = renk.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), max(0, min(255, int(alpha))))
    if len(h) == 8:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16))
    return (203, 213, 225, max(0, min(255, int(alpha))))


def _karistir_rgba(
    a: str | tuple[int, int, int, int],
    b: str | tuple[int, int, int, int],
    t: float,
    alpha: int = 255,
) -> tuple[int, int, int, int]:
    """İki rengi oranlayıp opak RGBA (alpha=255) üretir; Pillow RGBA üstüne temiz çizilir."""
    ca = _hex_rgba(a) if isinstance(a, str) else a
    cb = _hex_rgba(b) if isinstance(b, str) else b
    t = max(0.0, min(1.0, float(t)))
    r = round(ca[0] * (1.0 - t) + cb[0] * t)
    g = round(ca[1] * (1.0 - t) + cb[1] * t)
    bl = round(ca[2] * (1.0 - t) + cb[2] * t)
    return (r, g, bl, max(0, min(255, int(alpha))))


def durum_rengi(kalan: float | None) -> str:
    if kalan is None:
        return GRI
    try:
        v = float(kalan)
    except (TypeError, ValueError):
        return GRI
    if not math.isfinite(v):
        return GRI
    if v >= 50.0:
        return YESIL
    if v >= 20.0:
        return AMBER
    return KIRMIZI


def _oran_kirp(deger: Any) -> float | None:
    if deger is None:
        return None
    try:
        v = float(deger)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return max(0.0, min(100.0, v))


def _sure_metni(saniye: float) -> str:
    sn = max(0, int(saniye))
    gun, k = divmod(sn, 86400)
    sa, k = divmod(k, 3600)
    dk = k // 60
    if gun:
        return dil.t("sure_g_sa", g=gun, sa=sa)
    if sa:
        return dil.t("sure_sa_dk", sa=sa, dk=dk)
    if dk:
        return dil.t("sure_dk", dk=dk)
    return dil.t("sure_az")


def _tarih_metni(epoch: float) -> str:
    d = datetime.fromtimestamp(epoch)
    bugun = datetime.now().date()
    if d.date() == bugun:
        gun = dil.t("bugun")
    elif d.date() == bugun + timedelta(days=1):
        gun = dil.t("yarin")
    else:
        gun_adi = dil.t(f"gun_{d.weekday()}")
        gun = f"{gun_adi} {d.day:02d}.{d.month:02d}"
    return f"{gun} {d.hour:02d}:{d.minute:02d}"


# ---------------------------------------------------------------- font önbelleği
@lru_cache(maxsize=16)
def _font_yolu_bul(agirlik: str) -> str | None:
    adaylar = _FONT_ADAYLARI.get(agirlik, _FONT_ADAYLARI["regular"])
    for dosya in adaylar:
        yol = os.path.join(_FONT_DIZIN, dosya)
        if os.path.isfile(yol):
            return yol
    return None


@lru_cache(maxsize=128)
def _font_al(px_boyut: int, agirlik: str = "semibold") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    boyut = max(8, int(px_boyut))
    yol = _font_yolu_bul(agirlik)
    if yol:
        try:
            return ImageFont.truetype(yol, boyut)
        except OSError:
            pass
    return ImageFont.load_default()


def _metin_boyut(draw: ImageDraw.ImageDraw, metin: str, font: ImageFont.ImageFont) -> tuple[float, float]:
    if not metin:
        return (0.0, 0.0)
    bbox = draw.textbbox((0, 0), metin, font=font)
    return (float(bbox[2] - bbox[0]), float(bbox[3] - bbox[1]))


def _metin_sigdir_font(
    draw: ImageDraw.ImageDraw,
    metin: str,
    max_g: float,
    bas_px: int,
    min_px: int,
    agirlik: str = "semibold",
) -> ImageFont.ImageFont:
    """Metin verilen genişliğe sığana kadar fontu kademeli küçültür."""
    px = max(min_px, int(bas_px))
    while px > min_px:
        f = _font_al(px, agirlik)
        tw, _ = _metin_boyut(draw, metin, f)
        if tw <= max_g:
            return f
        px = max(min_px, px - S)
    return _font_al(min_px, agirlik)


def _metin_kirp(draw: ImageDraw.ImageDraw, metin: str, font: ImageFont.ImageFont, max_g: float) -> str:
    if not metin:
        return ""
    tw, _ = _metin_boyut(draw, metin, font)
    if tw <= max_g:
        return metin
    parca = metin
    while len(parca) > 1:
        parca = parca[:-1]
        tw, _ = _metin_boyut(draw, parca.rstrip() + "…", font)
        if tw <= max_g:
            return parca.rstrip() + "…"
    return "…"


def _metin_sar(
    draw: ImageDraw.ImageDraw,
    metin: str,
    font: ImageFont.ImageFont,
    max_g: float,
    max_satir: int = 2,
) -> list[str]:
    """Metni piksel genişliğine göre en fazla `max_satir` satıra böler; taşmayı önler."""
    if not metin:
        return []
    kelimeler = str(metin).replace("\r", " ").replace("\n", " ").split()
    if not kelimeler:
        return []
    satirlar: list[str] = []
    aktif = ""
    for k in kelimeler:
        aday = f"{aktif} {k}".strip() if aktif else k
        tw, _ = _metin_boyut(draw, aday, font)
        if tw <= max_g:
            aktif = aday
        else:
            if aktif:
                satirlar.append(aktif)
                if len(satirlar) >= max_satir:
                    satirlar[-1] = _metin_kirp(draw, satirlar[-1] + " " + k, font, max_g)
                    return satirlar
                aktif = k
            else:
                satirlar.append(_metin_kirp(draw, k, font, max_g))
                if len(satirlar) >= max_satir:
                    return satirlar
                aktif = ""
    if aktif and len(satirlar) < max_satir:
        satirlar.append(_metin_kirp(draw, aktif, font, max_g))
    return satirlar


# ---------------------------------------------------------------- arka plan & kabuk önbelleği
@lru_cache(maxsize=48)
def _kabuk_olustur(
    w_s: int,
    h_s: int,
    yaricap_s: int,
    ust_duz: bool,
    kenar_renk: str,
    kenar_kalinlik_s: int,
    ic_ton_renk: str = "",
    ic_ton_oran: float = 0.0,
) -> Image.Image:
    """3× çözünürlükte dikey degrade + yuvarlatılmış maske + zarif kenarlıklı kabuk üretir."""
    serit = Image.new("RGBA", (1, max(1, h_s)))
    pix = serit.load()
    c_ust = _karistir_rgba(ZEMIN_UST, ic_ton_renk, ic_ton_oran) if ic_ton_renk and ic_ton_oran > 0 else _hex_rgba(ZEMIN_UST)
    c_orta = _karistir_rgba(ZEMIN_ORTA, ic_ton_renk, ic_ton_oran) if ic_ton_renk and ic_ton_oran > 0 else _hex_rgba(ZEMIN_ORTA)
    c_alt = _karistir_rgba(ZEMIN_ALT, ic_ton_renk, ic_ton_oran) if ic_ton_renk and ic_ton_oran > 0 else _hex_rgba(ZEMIN_ALT)
    payda = max(1, h_s - 1)
    for y in range(h_s):
        t = y / payda
        if t < 0.45:
            renk = _karistir_rgba(c_ust, c_orta, t / 0.45)
        else:
            renk = _karistir_rgba(c_orta, c_alt, (t - 0.45) / 0.55)
        pix[0, y] = renk
    bilinear = Image.Resampling.BILINEAR if hasattr(Image, "Resampling") else Image.BILINEAR
    degrade = serit.resize((w_s, h_s), bilinear)

    maske = Image.new("L", (w_s, h_s), 0)
    md = ImageDraw.Draw(maske)
    r = max(0, min(yaricap_s, w_s // 2, h_s // 2 if not ust_duz else h_s))
    if ust_duz:
        md.rounded_rectangle((0, -r, w_s - 1, h_s - 1), radius=r, fill=255)
    else:
        md.rounded_rectangle((0, 0, w_s - 1, h_s - 1), radius=r, fill=255)

    kabuk = Image.new("RGBA", (w_s, h_s), (0, 0, 0, 0))
    kabuk.paste(degrade, (0, 0), maske)

    d = ImageDraw.Draw(kabuk)
    # Yumuşak üst iç ışık (opak önceden harmanlanmış — saydam delik bırakmaz)
    if not ust_duz and h_s > kenar_kalinlik_s * 4:
        ic_isik_opak = _karistir_rgba(c_ust, "#FFFFFF", 0.08)
        d.rounded_rectangle(
            (kenar_kalinlik_s, kenar_kalinlik_s, w_s - 1 - kenar_kalinlik_s, h_s - 1 - kenar_kalinlik_s),
            radius=max(0, r - kenar_kalinlik_s),
            outline=ic_isik_opak,
            width=max(1, kenar_kalinlik_s),
        )

    # Zarif dış çerçeve
    if ust_duz:
        d.rounded_rectangle(
            (0, -r, w_s - 1, h_s - 1),
            radius=r,
            outline=_hex_rgba(kenar_renk, 255),
            width=max(1, kenar_kalinlik_s),
        )
    else:
        d.rounded_rectangle(
            (0, 0, w_s - 1, h_s - 1),
            radius=r,
            outline=_hex_rgba(kenar_renk, 255),
            width=max(1, kenar_kalinlik_s),
        )
    return kabuk


def _kucult(img_s: Image.Image, w: int, h: int) -> Image.Image:
    return img_s.resize((max(1, int(w)), max(1, int(h))), _RESAMPLE)


# ---------------------------------------------------------------- vektör çizim yardımcıları (3×)
def _cizgi_yuvarlak(
    d: ImageDraw.ImageDraw,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    renk: tuple[int, int, int, int],
    kalinlik: float,
) -> None:
    w = max(1, round(kalinlik))
    d.line((x1, y1, x2, y2), fill=renk, width=w)
    r = kalinlik / 2.0
    if r >= 1.2:
        d.ellipse((x1 - r, y1 - r, x1 + r, y1 + r), fill=renk)
        d.ellipse((x2 - r, y2 - r, x2 + r, y2 + r), fill=renk)


def _coklu_cizgi_yuvarlak(
    d: ImageDraw.ImageDraw,
    noktalar: list[tuple[float, float]],
    renk: tuple[int, int, int, int],
    kalinlik: float,
) -> None:
    w = max(1, round(kalinlik))
    r = kalinlik / 2.0
    for i in range(len(noktalar) - 1):
        p1, p2 = noktalar[i], noktalar[i + 1]
        d.line((p1[0], p1[1], p2[0], p2[1]), fill=renk, width=w)
    if r >= 1.2:
        for px, py in noktalar:
            d.ellipse((px - r, py - r, px + r, py + r), fill=renk)


def _tarama_seridi_ciz(d: ImageDraw.ImageDraw, w_s: int, faz: float, o: float) -> None:
    """Üst kenar boyunca kayan yumuşak mavi tarama ışığı."""
    sol = 18.0 * o * S
    sag = w_s - 18.0 * o * S
    if sag <= sol:
        return
    uzunluk = min(66.0 * o * S, (sag - sol) * 0.55)
    faz = float(faz) % 1.0
    merkez = sol + faz * (sag - sol)
    y = 2.0 * o * S
    kalin = max(2, round(2.6 * o * S))
    adim = 14
    for i in range(adim):
        x1 = max(sol, merkez - uzunluk / 2 + i * uzunluk / adim)
        x2 = min(sag, merkez - uzunluk / 2 + (i + 1) * uzunluk / adim)
        if x2 > x1:
            oran = 1.0 - abs(i - (adim - 1) / 2.0) / (adim / 2.0)
            parlak = _karistir_rgba("#2563EB", "#BAE6FD", oran)
            col = _karistir_rgba(ZEMIN_UST, parlak, 0.35 + 0.65 * oran)
            d.line((x1, y, x2, y), fill=col, width=kalin)


def _halka_ciz(
    d: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    r: float,
    kalinlik: float,
    kalan: float | None,
    iz_renk: str = IZ,
) -> None:
    """Dairesel ilerleme halkası (yuvarlak uçlu, 3× keskin)."""
    w = max(2, round(kalinlik))
    kutu = (cx - r, cy - r, cx + r, cy + r)
    d.ellipse(kutu, outline=_hex_rgba(iz_renk), width=w)
    oran = _oran_kirp(kalan)
    if oran is None or oran <= 0.0:
        return
    renk = _hex_rgba(durum_rengi(oran))
    if oran >= 99.6:
        d.ellipse(kutu, outline=renk, width=w)
        return
    bas = -90.0
    bit = -90.0 + 3.6 * oran
    d.arc(kutu, start=bas, end=bit, fill=renk, width=w)
    r_orta = r - w / 2.0
    cap_r = max(1.0, w / 2.0 - 0.3)
    for aci in (bas, bit):
        rad = math.radians(aci)
        px = cx + r_orta * math.cos(rad)
        py = cy + r_orta * math.sin(rad)
        d.ellipse((px - cap_r, py - cap_r, px + cap_r, py + cap_r), fill=renk)


def _marka_simgesi_ciz(
    d: ImageDraw.ImageDraw,
    arac: str,
    cx: float,
    cy: float,
    r: float,
    marka_renk: str | None = None,
    harf: str | None = None,
) -> None:
    renk = _hex_rgba(marka_renk or ARAC_BILGI.get(arac, {}).get("renk", VURGU))
    if arac == "claude":
        kalin = max(2.2, r * 0.23)
        for k in range(8):
            a = math.radians(k * 45.0 + 22.5)
            uz = r * (1.0 if k % 2 == 0 else 0.72)
            _cizgi_yuvarlak(
                d,
                cx + math.cos(a) * r * 0.22,
                cy + math.sin(a) * r * 0.22,
                cx + math.cos(a) * uz,
                cy + math.sin(a) * uz,
                renk,
                kalin,
            )
    elif arac == "codex":
        kalin = max(2.2, r * 0.22)
        _coklu_cizgi_yuvarlak(
            d,
            [
                (cx - r * 0.72, cy - r * 0.52),
                (cx - r * 0.12, cy),
                (cx - r * 0.72, cy + r * 0.52),
            ],
            renk,
            kalin,
        )
        _cizgi_yuvarlak(d, cx + r * 0.14, cy + r * 0.56, cx + r * 0.82, cy + r * 0.56, renk, kalin)
    elif arac == "antigravity":
        # Antigravity: yukarı süzülen çift şevron
        kalin = max(2.2, r * 0.22)
        _coklu_cizgi_yuvarlak(
            d,
            [
                (cx - r * 0.76, cy + r * 0.12),
                (cx, cy - r * 0.64),
                (cx + r * 0.76, cy + r * 0.12),
            ],
            renk,
            kalin,
        )
        _coklu_cizgi_yuvarlak(
            d,
            [
                (cx - r * 0.52, cy + r * 0.68),
                (cx, cy + r * 0.16),
                (cx + r * 0.52, cy + r * 0.68),
            ],
            _hex_rgba("#A78BFA"),
            kalin,
        )
    elif arac == "copilot":
        # Copilot: sade vizör çerçevesi + iki parlak göz kapsülü
        v_renk = _hex_rgba(marka_renk or "#A78BFA")
        kalin = max(2, int(round(max(2.0, r * 0.19))))
        d.rounded_rectangle(
            (cx - r * 0.88, cy - r * 0.46, cx + r * 0.88, cy + r * 0.52),
            radius=max(2, round(r * 0.42)),
            outline=v_renk,
            width=kalin,
        )
        # Üst başlık kemeri
        d.arc(
            (cx - r * 0.64, cy - r * 0.82, cx + r * 0.64, cy - r * 0.10),
            start=195,
            end=345,
            fill=v_renk,
            width=max(2, int(round(kalin * 0.85))),
        )
        # İki göz kapsülü
        goz_r_x = max(1.4, r * 0.14)
        goz_r_y = max(2.2, r * 0.24)
        for gx in (cx - r * 0.34, cx + r * 0.34):
            d.rounded_rectangle(
                (gx - goz_r_x, cy + r * 0.03 - goz_r_y, gx + goz_r_x, cy + r * 0.03 + goz_r_y),
                radius=max(1, round(goz_r_x)),
                fill=v_renk,
            )
    else:
        # Genel araç simgesi: ince halka + ortada ilk harf
        kalin = max(2, int(round(max(2.2, r * 0.16))))
        d.ellipse(
            (cx - r, cy - r, cx + r, cy + r),
            outline=renk,
            width=kalin,
        )
        simge_harf = (arac or "?")[:1].upper() if harf is None else (str(harf)[:1].upper() if harf else "?")
        font = _font_al(round(r * 1.1), "semibold")
        tw, th = _metin_boyut(d, simge_harf, font)
        bbox = d.textbbox((0, 0), simge_harf, font=font)
        d.text(
            (cx - tw / 2.0 - bbox[0], cy - th / 2.0 - bbox[1]),
            simge_harf,
            fill=renk,
            font=font,
        )


def _yenile_ikonu_ciz(
    d: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    r: float,
    renk: tuple[int, int, int, int],
    aci_deg: float = 0.0,
) -> None:
    """Dönebilen keskin vektör yenileme (↻) ikonu."""
    kalin = max(2.0, r * 0.27)
    w = max(2, round(kalin))
    bas = -60.0 + aci_deg
    bit = 225.0 + aci_deg
    d.arc((cx - r, cy - r, cx + r, cy + r), start=bas, end=bit, fill=renk, width=w)
    r_orta = r - w / 2.0
    rad = math.radians(bas)
    tx = cx + r_orta * math.cos(rad)
    ty = cy + r_orta * math.sin(rad)
    ok_uz = r * 0.46
    for sapma in (-145.0, -55.0):
        krad = math.radians(bas + sapma)
        _cizgi_yuvarlak(d, tx, ty, tx + ok_uz * math.cos(krad), ty + ok_uz * math.sin(krad), renk, kalin * 0.9)


def _igne_ikonu_ciz(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, renk: tuple[int, int, int, int]) -> None:
    kalin = max(2.0, r * 0.27)
    w = max(2, round(kalin))
    d.ellipse((cx - r * 0.55, cy - r * 0.95, cx + r * 0.55, cy - r * 0.05), outline=renk, width=w)
    _cizgi_yuvarlak(d, cx - r * 0.85, cy - r * 0.05, cx + r * 0.85, cy - r * 0.05, renk, kalin)
    _cizgi_yuvarlak(d, cx, cy - r * 0.05, cx, cy + r * 0.95, renk, kalin)


def _ekran_ikonu_ciz(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, renk: tuple[int, int, int, int]) -> None:
    kalin = max(2.0, r * 0.25)
    w = max(2, round(kalin))
    d.rounded_rectangle(
        (cx - r * 0.98, cy - r * 0.72, cx + r * 0.98, cy + r * 0.42),
        radius=max(2, round(r * 0.22)),
        outline=renk,
        width=w,
    )
    _cizgi_yuvarlak(d, cx, cy + r * 0.42, cx, cy + r * 0.88, renk, kalin)
    _cizgi_yuvarlak(d, cx - r * 0.54, cy + r * 0.88, cx + r * 0.54, cy + r * 0.88, renk, kalin)


def _cikis_ikonu_ciz(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, renk: tuple[int, int, int, int]) -> None:
    kalin = max(2.0, r * 0.28)
    d_r = r * 0.68
    _cizgi_yuvarlak(d, cx - d_r, cy - d_r, cx + d_r, cy + d_r, renk, kalin)
    _cizgi_yuvarlak(d, cx - d_r, cy + d_r, cx + d_r, cy - d_r, renk, kalin)


def _onay_ikonu_ciz(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, renk: tuple[int, int, int, int]) -> None:
    """Toast bildirimleri için keskin vektör onay (✓) ikonu."""
    kalin = max(2.2, r * 0.28)
    _coklu_cizgi_yuvarlak(
        d,
        [
            (cx - r * 0.56, cy + r * 0.04),
            (cx - r * 0.14, cy + r * 0.50),
            (cx + r * 0.62, cy - r * 0.42),
        ],
        renk,
        kalin,
    )


def _uyari_ikonu_ciz(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, renk: tuple[int, int, int, int]) -> None:
    """Toast bildirimleri için keskin vektör uyarı (⚠) üçgeni."""
    kalin = max(2.0, r * 0.24)
    ust = (cx, cy - r * 0.82)
    sol = (cx - r * 0.86, cy + r * 0.72)
    sag = (cx + r * 0.86, cy + r * 0.72)
    _coklu_cizgi_yuvarlak(d, [ust, sag, sol, ust], renk, kalin)
    _cizgi_yuvarlak(d, cx, cy - r * 0.24, cx, cy + r * 0.22, renk, kalin)
    nokta_r = max(1.4, kalin * 0.55)
    d.ellipse((cx - nokta_r, cy + r * 0.48 - nokta_r, cx + nokta_r, cy + r * 0.48 + nokta_r), fill=renk)


# ================================================================ 1. ÇENTİK
def centik_gorseli(
    w: int,
    h: int,
    noktalar: list[str] | tuple[str, ...],
    metin: str,
    vurgu_renk: str = VURGU,
    nefes: float = 0.0,
    tarama_faz: float | None = None,
) -> Image.Image:
    """Üst orta kapalı çentik (Dinamik Ada) görselini 3× supersampling ile üretir."""
    w = max(48, int(round(w)))
    h = max(16, int(round(h)))
    w_s, h_s = w * S, h * S
    o = h / 24.0
    yaricap_s = round(min(11.0 * o, h * 0.46) * S)

    img = _kabuk_olustur(w_s, h_s, yaricap_s, True, KENAR, max(2, round(1.0 * o * S))).copy()
    d = ImageDraw.Draw(img)

    # Alt nefes alan parlak vurgu çizgisi + yumuşak opak aura
    nefes_t = max(0.0, min(1.0, float(nefes)))
    cizgi_renk = _karistir_rgba(_karistir_rgba(ZEMIN_ORTA, vurgu_renk, 0.50), vurgu_renk, nefes_t)
    aura_renk = _karistir_rgba(ZEMIN_ALT, vurgu_renk, 0.20 + 0.22 * nefes_t)
    cx1, cx2 = 15.0 * o * S, w_s - 15.0 * o * S
    cy_bar = h_s - 2.3 * o * S
    _cizgi_yuvarlak(d, cx1, cy_bar, cx2, cy_bar, aura_renk, max(4.0, 4.4 * o * S))
    _cizgi_yuvarlak(d, cx1, cy_bar, cx2, cy_bar, cizgi_renk, max(2.0, 2.0 * o * S))

    if tarama_faz is not None:
        _tarama_seridi_ciz(d, w_s, tarama_faz, o)

    # Sol tarafta durum noktaları (3 araç: Claude, Codex, Antigravity)
    cy = (h_s - 2.5 * o * S) / 2.0
    r_nokta = max(2.8, 3.1 * o) * S
    bas_x = 16.0 * o * S
    adim = 10.5 * o * S
    nokta_list = list(noktalar or ())
    for i, renk in enumerate(nokta_list):
        nx = bas_x + i * adim
        # Yumuşak opak LED parıltı halkası
        d.ellipse(
            (nx - r_nokta * 1.48, cy - r_nokta * 1.48, nx + r_nokta * 1.48, cy + r_nokta * 1.48),
            fill=_karistir_rgba(ZEMIN_ORTA, renk, 0.26),
        )
        d.ellipse(
            (nx - r_nokta, cy - r_nokta, nx + r_nokta, cy + r_nokta),
            fill=_hex_rgba(renk),
        )

    # Dikey ince ayraç
    if nokta_list:
        ax = bas_x + (len(nokta_list) - 1) * adim + 9.0 * o * S
        d.line(
            (ax, 5.5 * o * S, ax, h_s - 6.5 * o * S),
            fill=_karistir_rgba(ZEMIN_ORTA, KENAR_PARLAK, 0.72),
            width=max(2, round(1.0 * o * S)),
        )
        metin_sol = ax + 6.0 * o * S
    else:
        metin_sol = 10.0 * o * S

    metin_sag = w_s - 10.0 * o * S
    max_metin_g = max(20.0, metin_sag - metin_sol)
    etiket = str(metin or "").strip()
    if etiket:
        font = _metin_sigdir_font(d, etiket, max_metin_g, round(11.5 * o * S), round(8.5 * o * S), "semibold")
        etiket = _metin_kirp(d, etiket, font, max_metin_g)
        d.text(((metin_sol + metin_sag) / 2.0, cy), etiket, fill=_hex_rgba(YAZI), font=font, anchor="mm")

    return _kucult(img, w, h)


# ================================================================ 2. GEÇİŞ KABUĞU
def gecis_gorseli(w: int, h: int, vurgu_renk: str = VURGU) -> Image.Image:
    """Ada açılış/kapanış animasyonu sırasında pürüzsüz boş geçiş kabuğu üretir."""
    w = max(32, int(round(w)))
    h = max(16, int(round(h)))
    w_s, h_s = w * S, h * S
    o = max(0.8, min(w / 168.0, h / 24.0))
    yaricap_s = round(min(18.0 * o, h * 0.45) * S)
    img = _kabuk_olustur(w_s, h_s, yaricap_s, True, KENAR, max(2, round(1.1 * S))).copy()
    d = ImageDraw.Draw(img)
    pad = min(w_s * 0.12, 18.0 * S)
    _cizgi_yuvarlak(d, pad, h_s - 2.2 * S, w_s - pad, h_s - 2.2 * S, _hex_rgba(vurgu_renk), max(2.0, 2.0 * S))
    return _kucult(img, w, h)


# ================================================================ 3. AÇIK PANEL
def _arac_durumu_coz(araclar_durum: Any, arac: str) -> tuple[float | None, float | None, str]:
    """Esnek sözlük/liste yapısından (bes_kalan, hft_kalan, marka_renk) çıkarır."""
    varsayilan_renk = ARAC_BILGI.get(arac, {}).get("renk", VURGU)
    veri = None
    if isinstance(araclar_durum, dict):
        veri = araclar_durum.get(arac)
    elif isinstance(araclar_durum, (list, tuple)):
        for oge in araclar_durum:
            if isinstance(oge, dict) and oge.get("id") == arac:
                veri = oge
                break
    if not isinstance(veri, dict):
        return (None, None, varsayilan_renk)

    def _al(anahtarlar: tuple[str, ...]) -> float | None:
        for k in anahtarlar:
            if k in veri:
                val = veri[k]
                if isinstance(val, (tuple, list)) and val:
                    val = val[0]
                elif isinstance(val, dict):
                    val = val.get("kalan")
                return _oran_kirp(val)
        return None

    bes = _al(("bes_kalan", "bes", "bes_saat"))
    hft = _al(("hft_kalan", "hft", "haftalik"))
    ham_renk = veri.get("renk")
    if not (isinstance(ham_renk, str) and len(ham_renk) == 7 and ham_renk.startswith("#")):
        ham_renk = veri.get("marka_renk")
    if isinstance(ham_renk, str) and len(ham_renk) == 7 and ham_renk.startswith("#"):
        renk = ham_renk
    else:
        renk = varsayilan_renk
    return (bes, hft, renk)


def panel_gorseli(
    w: int,
    h: int,
    araclar_durum: Any,
    secili_arac: str | None = None,
    hover_arac: str | None = None,
    hover_dugme: str | None = None,
    sabit: bool = False,
    yenileniyor: bool | set[str] | list[str] = False,
    tarama_faz: float = 0.0,
    donus_aci: float = 0.0,
    durum_metni: str | None = None,
    coklu_monitor: bool = False,
    araclar: list[str] | tuple[str, ...] | None = None,
) -> tuple[Image.Image, dict[str, tuple[int, int, int, int]]]:
    """Açık yatay kontrol panelini ve tüm etkileşim kutularını (hitboxes) üretir."""
    sira = tuple(araclar) if araclar else ARAC_SIRA
    n = len(sira)
    w = max(240, int(round(w)))
    h = max(64, int(round(h)))
    w_s, h_s = w * S, h * S
    o = h / 86.0
    yaricap_s = round(20.0 * o * S)

    img = _kabuk_olustur(w_s, h_s, yaricap_s, True, KENAR, max(2, round(1.1 * o * S))).copy()
    d = ImageDraw.Draw(img)

    # Alt ince vurgu şeridi
    _cizgi_yuvarlak(
        d,
        24.0 * o * S,
        h_s - 2.0 * o * S,
        w_s - 24.0 * o * S,
        h_s - 2.0 * o * S,
        _karistir_rgba(ZEMIN_ALT, VURGU, 0.85),
        max(2.0, 1.8 * o * S),
    )

    mesgul = bool(yenileniyor)
    if mesgul:
        _tarama_seridi_ciz(d, w_s, tarama_faz, o)

    # Orantılı yatay yerleşim (limit_cubugu.pyw ölçüleriyle uyumlu)
    baz_sol, baz_simge, baz_ayrac, baz_dugme, baz_sag = 12.0, 76.0, 12.0, 42.0, 10.0
    baz_toplam = baz_sol + baz_simge * n + baz_ayrac + baz_dugme * 4 + baz_sag
    kx = w / baz_toplam

    panel_sol = baz_sol * kx
    simge_adim = baz_simge * kx
    ayrac_g = baz_ayrac * kx
    dugme_adim = baz_dugme * kx

    hitboxes: dict[str, tuple[int, int, int, int]] = {}
    cy_simge = 32.5 * o

    # Araç halkaları + marka simgesi + yüzde etiketi
    yuzde_font = _font_al(round(12.0 * o * S), "bold")
    for i, arac in enumerate(sira):
        sol = panel_sol + simge_adim * i
        sag = sol + simge_adim
        cx = (sol + sag) / 2.0
        hitboxes[arac] = (int(round(sol)), 0, int(round(sag)), h)

        bes_kalan, hft_kalan, marka_renk = _arac_durumu_coz(araclar_durum, arac)
        secili = arac == secili_arac
        hover = arac == hover_arac

        kutu_s = ((sol + 3.0 * o) * S, 5.0 * o * S, (sag - 3.0 * o) * S, (h - 7.5 * o) * S)
        r_kutu = round(14.0 * o * S)
        if hover:
            # Yumuşak koyu cam hover dolgusu + marka parıltı çerçevesi (tam opak, sıfır halo hatası)
            ic_dolgu = _karistir_rgba(YUZEY_AKTIF if secili else ZEMIN_ORTA, marka_renk, 0.13)
            dis_parilti = _karistir_rgba(ZEMIN_ORTA, marka_renk, 0.34)
            d.rounded_rectangle(
                ((sol + 1.5 * o) * S, 3.5 * o * S, (sag - 1.5 * o) * S, (h - 6.0 * o) * S),
                radius=round(15.0 * o * S),
                outline=dis_parilti,
                width=max(4, round(3.4 * o * S)),
            )
            d.rounded_rectangle(
                kutu_s,
                radius=r_kutu,
                fill=ic_dolgu,
                outline=_hex_rgba(marka_renk),
                width=max(2, round(1.35 * o * S)),
            )
        elif secili:
            d.rounded_rectangle(
                kutu_s,
                radius=r_kutu,
                fill=_hex_rgba(YUZEY_AKTIF),
                outline=_hex_rgba(KENAR_PARLAK),
                width=max(2, round(1.0 * o * S)),
            )

        _halka_ciz(d, cx * S, cy_simge * S, 21.5 * o * S, 3.2 * o * S, bes_kalan, iz_renk=IZ)
        _halka_ciz(d, cx * S, cy_simge * S, 15.6 * o * S, 2.3 * o * S, hft_kalan, iz_renk="#162138")
        _marka_simgesi_ciz(d, arac, cx * S, cy_simge * S, 9.4 * o * S, marka_renk=marka_renk)

        metin = "—" if bes_kalan is None else (f"{bes_kalan:.0f}%" if dil.etkin_dil() == "en" else f"%{bes_kalan:.0f}")
        metin_renk = _hex_rgba(durum_rengi(bes_kalan) if bes_kalan is not None else IKINCIL)
        d.text((cx * S, (cy_simge + 33.5 * o) * S), metin, fill=metin_renk, font=yuzde_font, anchor="mm")

    # Dikey ayraç
    ax = (panel_sol + simge_adim * n + ayrac_g / 2.0) * S
    d.line((ax, 15.0 * o * S, ax, h_s - 15.0 * o * S), fill=_karistir_rgba(ZEMIN_ORTA, KENAR_PARLAK, 0.72), width=max(2, round(1.0 * o * S)))

    # 4 eylem düğmesi: yenile, sabit, ekran, cikis
    dugme_bas = panel_sol + simge_adim * n + ayrac_g
    cy_dugme = 32.5 * o
    r_dugme = 13.0 * o
    etiket_font = _font_al(round(10.5 * o * S), "semibold")

    dugme_tanimlari = [
        ("yenile", dil.t("panel_yenile"), mesgul),
        ("sabit", dil.t("panel_sabit"), bool(sabit)),
        ("ekran", dil.t("panel_ekran"), bool(coklu_monitor)),
        ("cikis", dil.t("panel_cikis"), False),
    ]

    dugme_merkez_x: list[float] = []
    for idx, (kimlik, etiket, aktif) in enumerate(dugme_tanimlari):
        sol = dugme_bas + dugme_adim * idx
        sag = sol + dugme_adim
        bx = (sol + sag) / 2.0
        dugme_merkez_x.append(bx)
        hitboxes[kimlik] = (int(round(sol)), int(round(6 * o)), int(round(sag)), int(round(h - 6 * o)))

        is_hover = hover_dugme == kimlik
        if kimlik == "cikis" and is_hover:
            dolgu = _karistir_rgba(YUZEY, KIRMIZI, 0.22)
            kenar = _hex_rgba(KIRMIZI)
            ikon_renk = _hex_rgba(KIRMIZI)
            yazi_renk = _hex_rgba(KIRMIZI)
        elif aktif:
            dolgu = _hex_rgba("#163254")
            kenar = _hex_rgba(VURGU)
            ikon_renk = _hex_rgba(VURGU)
            yazi_renk = _hex_rgba(VURGU)
        elif is_hover:
            dolgu = _hex_rgba(YUZEY_HOVER)
            kenar = _karistir_rgba(KENAR_PARLAK, VURGU, 0.72)
            ikon_renk = _hex_rgba(YAZI)
            yazi_renk = _hex_rgba(YAZI)
        else:
            dolgu = _hex_rgba(YUZEY)
            kenar = _hex_rgba(KENAR_PARLAK)
            ikon_renk = _hex_rgba(YAZI if kimlik == "yenile" else IKINCIL)
            yazi_renk = _hex_rgba(IKINCIL)

        bx_s, by_s, r_s = bx * S, cy_dugme * S, r_dugme * S
        d.ellipse(
            (bx_s - r_s, by_s - r_s, bx_s + r_s, by_s + r_s),
            fill=dolgu,
            outline=kenar,
            width=max(2, round(1.2 * o * S)),
        )

        ir = 5.6 * o * S
        if kimlik == "yenile":
            _yenile_ikonu_ciz(d, bx_s, by_s, ir, ikon_renk, aci_deg=float(donus_aci) if mesgul else 0.0)
        elif kimlik == "sabit":
            _igne_ikonu_ciz(d, bx_s, by_s, ir, ikon_renk)
        elif kimlik == "ekran":
            _ekran_ikonu_ciz(d, bx_s, by_s, ir, ikon_renk)
        else:
            _cikis_ikonu_ciz(d, bx_s, by_s, ir, ikon_renk)

        d.text((bx_s, (cy_dugme + 24.5 * o) * S), etiket, fill=yazi_renk, font=etiket_font, anchor="mm")

    # Yenileniyor / durum metni hapı
    goster_durum = (durum_metni or "").strip() if durum_metni else (dil.t("yenileniyor_ucnokta") if mesgul else "")
    if goster_durum:
        sx1 = (dugme_merkez_x[0] - r_dugme - 3.0 * o) * S
        sx2 = (dugme_merkez_x[-1] + r_dugme + 3.0 * o) * S
        sy1 = (cy_dugme + 17.0 * o) * S
        sy2 = (cy_dugme + 32.0 * o) * S
        d.rounded_rectangle(
            (sx1, sy1, sx2, sy2),
            radius=round(7.5 * o * S),
            fill=_hex_rgba("#122642"),
            outline=_karistir_rgba("#122642", VURGU, 0.65),
            width=max(2, round(1.0 * o * S)),
        )
        max_dg = max(20.0, sx2 - sx1 - 12.0 * o * S)
        dfont = _metin_sigdir_font(d, goster_durum, max_dg, round(10.5 * o * S), round(8.5 * o * S), "semibold")
        goster_durum = _metin_kirp(d, goster_durum, dfont, max_dg)
        d.text(((sx1 + sx2) / 2.0, (sy1 + sy2) / 2.0), goster_durum, fill=_hex_rgba(VURGU), font=dfont, anchor="mm")

    return _kucult(img, w, h), hitboxes


# ================================================================ 4. DETAY KARTI
def _pencere_durumu_coz(durum: Any, haftalik: bool) -> tuple[float | None, str, str, bool]:
    """Dict veya (kalan, reset_epoch, yenilendi) demetinden (kalan, deger_metni, alt_metin, yenilendi) döner."""
    simdi = time.time()
    kalan: float | None = None
    reset: float | None = None
    yenilendi = False
    deger_ozel = None
    alt_ozel = None

    if isinstance(durum, dict):
        kalan = _oran_kirp(durum.get("kalan"))
        reset = durum.get("resets_at") if durum.get("resets_at") is not None else durum.get("reset")
        yenilendi = bool(durum.get("yenilendi", False))
        deger_ozel = durum.get("deger_metni")
        alt_ozel = durum.get("alt_metin")
    elif isinstance(durum, (tuple, list)):
        if len(durum) >= 1:
            kalan = _oran_kirp(durum[0])
        if len(durum) >= 2:
            reset = durum[1]
        if len(durum) >= 3:
            yenilendi = bool(durum[2])

    if deger_ozel is not None:
        deger_metni = str(deger_ozel)
    elif kalan is None:
        deger_metni = dil.t("veri_yok_kucuk")
    elif yenilendi:
        deger_metni = dil.t("yuzde_kaldi_yenilendi")
    else:
        deger_metni = dil.t("yuzde_kaldi", yuzde=f"{kalan:.0f}")

    if alt_ozel is not None:
        alt_metin = str(alt_ozel)
    elif yenilendi:
        alt_metin = dil.t("yeni_pencere_sure_bilinmiyor")
    elif reset:
        try:
            r_epoch = float(reset)
            if haftalik:
                alt_metin = dil.t("yenilenme_tarih_sure", tarih=_tarih_metni(r_epoch), sure=_sure_metni(r_epoch - simdi))
            else:
                alt_metin = dil.t("yenilenir_sure", sure=_sure_metni(r_epoch - simdi))
        except (TypeError, ValueError):
            alt_metin = dil.t("yenilenme_bilinmiyor")
    else:
        alt_metin = dil.t("yenilenme_bilinmiyor")

    return (kalan, deger_metni, alt_metin, yenilendi)


def _kaynak_etiketi_coz(kaynak_etiketi: Any) -> tuple[str, str]:
    if isinstance(kaynak_etiketi, (tuple, list)) and len(kaynak_etiketi) >= 2:
        return (str(kaynak_etiketi[0]), str(kaynak_etiketi[1]))
    metin = str(kaynak_etiketi or dil.t("veri_yok")).strip()
    kucuk = metin.lower()
    if any(k in kucuk for k in ("otomatik", "canlı", "canli", "statusline", "auto", "live")):
        return (metin, YESIL)
    if any(k in kucuk for k in ("elle", "geri sayım", "geri sayim", "manual", "countdown")):
        return (metin, AMBER)
    return (metin, GRI)


def _kart_pencere_blogu_ciz(
    d: ImageDraw.ImageDraw,
    x_s: float,
    y_s: float,
    g_s: float,
    h_s: float,
    baslik: str,
    durum: Any,
    anim_oran: float | None,
    haftalik: bool,
    o: float,
) -> None:
    kalan, deger_metni, alt_metin, _ = _pencere_durumu_coz(durum, haftalik)
    renk = durum_rengi(kalan)

    d.rounded_rectangle(
        (x_s, y_s, x_s + g_s, y_s + h_s),
        radius=round(11.0 * o * S),
        fill=_hex_rgba(YUZEY),
        outline=_hex_rgba(KENAR),
        width=max(2, round(1.0 * o * S)),
    )

    pad_x = 12.0 * o * S
    ic_sol = x_s + pad_x
    ic_sag = x_s + g_s - pad_x
    ic_g = ic_sag - ic_sol

    baslik_font = _font_al(round(12.5 * o * S), "semibold")
    deger_font = _font_al(round(13.0 * o * S), "bold")

    ust_y = y_s + 17.0 * o * S
    d.text((ic_sol, ust_y), baslik, fill=_hex_rgba(IKINCIL), font=baslik_font, anchor="lm")

    bw, _ = _metin_boyut(d, baslik, baslik_font)
    max_deger_g = max(40.0, ic_g - bw - 10.0 * o * S)
    deger_font = _metin_sigdir_font(d, deger_metni, max_deger_g, round(13.0 * o * S), round(10.0 * o * S), "bold")
    deger_metni = _metin_kirp(d, deger_metni, deger_font, max_deger_g)
    d.text(
        (ic_sag, ust_y),
        deger_metni,
        fill=_hex_rgba(renk if kalan is not None else SOLUK),
        font=deger_font,
        anchor="rm",
    )

    # İlerleme çubuğu (pürüzsüz hap)
    bar_y = y_s + 37.0 * o * S
    bar_h = 7.0 * o * S
    bar_r = bar_h / 2.0
    d.rounded_rectangle(
        (ic_sol, bar_y - bar_r, ic_sag, bar_y + bar_r),
        radius=bar_r,
        fill=_hex_rgba(IZ_KOYU),
        outline=_karistir_rgba(IZ_KOYU, KENAR, 0.75),
        width=max(1, round(0.8 * o * S)),
    )

    if anim_oran is None:
        dolum = (kalan / 100.0) if kalan is not None else 0.0
    else:
        try:
            dolum = float(anim_oran)
            if not math.isfinite(dolum):
                dolum = 0.0
        except (TypeError, ValueError):
            dolum = 0.0
        dolum = max(0.0, min(1.0, dolum))

    dolu_g = ic_g * dolum
    if dolu_g >= 2.0:
        r_dolu = min(bar_r, dolu_g / 2.0)
        d.rounded_rectangle(
            (ic_sol, bar_y - bar_r, ic_sol + dolu_g, bar_y + bar_r),
            radius=r_dolu,
            fill=_hex_rgba(renk),
        )

    alt_y = y_s + 57.0 * o * S
    alt_font = _metin_sigdir_font(d, alt_metin, ic_g, round(11.0 * o * S), round(9.2 * o * S), "regular")
    alt_metin = _metin_kirp(d, alt_metin, alt_font, ic_g)
    d.text((ic_sol, alt_y), alt_metin, fill=_hex_rgba(SOLUK), font=alt_font, anchor="lm")


def kart_gorseli(
    w: int,
    h: int,
    arac_ad: str,
    marka_renk: str,
    kaynak_etiketi: str | tuple[str, str],
    bes_durum: Any,
    hft_durum: Any,
    bes_anim_oran: float | None = None,
    hft_anim_oran: float | None = None,
    son_guncelleme: str = "",
    not_metni: str = "",
    not_renk: str | None = None,
    hover_dugme: str | None = None,
    yenileniyor: bool = False,
    donus_aci: float = 0.0,
    tarama_faz: float = 0.0,
    bes_baslik: str | None = None,
    hft_baslik: str | None = None,
) -> tuple[Image.Image, dict[str, tuple[int, int, int, int]]]:
    """Araç detay kartını ve düğme etkileşim kutusunu (`yenile`) üretir."""
    if bes_baslik is None:
        bes_baslik = dil.t("kart_5s_baslik")
    if hft_baslik is None:
        hft_baslik = dil.t("kart_hft_baslik")
    w = max(280, int(round(w)))
    h = max(280, int(round(h)))
    w_s, h_s = w * S, h * S
    o = min(w / 368.0, h / 356.0)
    yaricap_s = round(16.0 * o * S)

    img = _kabuk_olustur(w_s, h_s, yaricap_s, False, KENAR, max(2, round(1.1 * o * S))).copy()
    d = ImageDraw.Draw(img)

    # Üst marka vurgu şeridi + yumuşak opak parıltı (köşe yuvarlaklarından içeride)
    _cizgi_yuvarlak(
        d,
        24.0 * o * S,
        2.6 * o * S,
        w_s - 24.0 * o * S,
        2.6 * o * S,
        _karistir_rgba(ZEMIN_UST, marka_renk, 0.32),
        max(4.0, 4.6 * o * S),
    )
    _cizgi_yuvarlak(
        d,
        24.0 * o * S,
        2.2 * o * S,
        w_s - 24.0 * o * S,
        2.2 * o * S,
        _hex_rgba(marka_renk),
        max(2.0, 2.2 * o * S),
    )

    if yenileniyor:
        _tarama_seridi_ciz(d, w_s, tarama_faz, o)

    p = 16.0 * o
    p_s = p * S
    ic_g_s = w_s - 2.0 * p_s

    # Üst başlık: marka noktası + araç adı + sağda kaynak rozeti
    baslik_y_s = 29.0 * o * S
    nokta_r = 4.2 * o * S
    d.ellipse(
        (p_s, baslik_y_s - nokta_r, p_s + nokta_r * 2.0, baslik_y_s + nokta_r),
        fill=_hex_rgba(marka_renk),
    )
    ad_font = _font_al(round(16.5 * o * S), "bold")
    ad_metin = str(arac_ad or "")
    d.text((p_s + nokta_r * 2.0 + 8.0 * o * S, baslik_y_s), ad_metin, fill=_hex_rgba(YAZI), font=ad_font, anchor="lm")

    etiket, erenk = _kaynak_etiketi_coz(kaynak_etiketi)
    ad_w, _ = _metin_boyut(d, ad_metin, ad_font)
    max_rozet_g = max(60.0, ic_g_s - ad_w - 28.0 * o * S)
    rozet_font = _metin_sigdir_font(d, etiket, max_rozet_g - 16.0 * o * S, round(10.5 * o * S), round(8.5 * o * S), "semibold")
    etiket = _metin_kirp(d, etiket, rozet_font, max_rozet_g - 16.0 * o * S)
    rw, rh = _metin_boyut(d, etiket, rozet_font)
    pad_rx, pad_ry = 9.0 * o * S, 4.5 * o * S
    rx2 = w_s - p_s
    rx1 = rx2 - rw - pad_rx * 2.0
    ry1 = baslik_y_s - rh / 2.0 - pad_ry
    ry2 = baslik_y_s + rh / 2.0 + pad_ry
    d.rounded_rectangle(
        (rx1, ry1, rx2, ry2),
        radius=(ry2 - ry1) / 2.0,
        fill=_karistir_rgba(ZEMIN_UST, erenk, 0.14),
        outline=_karistir_rgba(ZEMIN_UST, erenk, 0.55),
        width=max(2, round(1.0 * o * S)),
    )
    d.text(((rx1 + rx2) / 2.0, baslik_y_s), etiket, fill=_hex_rgba(erenk), font=rozet_font, anchor="mm")

    # 5 Saatlik ve Haftalık limit blokları
    blok_h_s = 74.0 * o * S
    _kart_pencere_blogu_ciz(d, p_s, 52.0 * o * S, ic_g_s, blok_h_s, bes_baslik, bes_durum, bes_anim_oran, False, o)
    _kart_pencere_blogu_ciz(d, p_s, 136.0 * o * S, ic_g_s, blok_h_s, hft_baslik, hft_durum, hft_anim_oran, True, o)

    # Ayraç çizgisi
    ayrac_y_s = 224.0 * o * S
    d.line((p_s, ayrac_y_s, w_s - p_s, ayrac_y_s), fill=_karistir_rgba(ZEMIN_ORTA, KENAR, 0.85), width=max(2, round(1.0 * o * S)))

    # Son güncelleme satırı
    sg_metin = str(son_guncelleme or "").strip()
    if sg_metin and not sg_metin.lower().startswith(("son güncelleme", "last updated")):
        sg_metin = dil.t("son_guncelleme_on", deger=sg_metin)
    elif not sg_metin:
        sg_metin = dil.t("son_guncelleme_hic")
    sg_font = _font_al(round(11.0 * o * S), "semibold")
    sg_metin = _metin_kirp(d, sg_metin, sg_font, ic_g_s)
    d.text((p_s, 240.0 * o * S), sg_metin, fill=_hex_rgba(SOLUK), font=sg_font, anchor="lm")

    # Opsiyonel durum/yenileme notu (en fazla 2 satır)
    temiz_not = str(not_metni or "").strip()
    if temiz_not:
        not_font = _font_al(round(11.0 * o * S), "semibold")
        satirlar = _metin_sar(d, temiz_not, not_font, ic_g_s, max_satir=2)
        nrenk = _hex_rgba(not_renk or IKINCIL)
        for idx, satir in enumerate(satirlar):
            d.text((p_s, (259.0 + idx * 17.0) * o * S), satir, fill=nrenk, font=not_font, anchor="lm")

    # Alt eylem düğmesi: Yenile (mevcut düğme ölçüsü korunur, satırda ortalı)
    dy = h - 28.0 * o
    dh_yari = 15.0 * o
    ara = 8.0 * o
    dugme_g = (w - 2.0 * p - 2.0 * ara) / 3.0

    hitboxes: dict[str, tuple[int, int, int, int]] = {}
    dugmeler = [
        ("yenile", dil.t("yenileniyor") if yenileniyor else dil.t("panel_yenile")),
    ]
    toplam_dugme_g = len(dugmeler) * dugme_g + max(0, len(dugmeler) - 1) * ara
    baslangic_x = (w - toplam_dugme_g) / 2.0
    for idx, (kimlik, metin_d) in enumerate(dugmeler):
        x1 = baslangic_x + idx * (dugme_g + ara)
        x2 = x1 + dugme_g
        y1 = dy - dh_yari
        y2 = dy + dh_yari
        hitboxes[kimlik] = (int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)))

        is_hover = hover_dugme == kimlik
        mesgul_bu = kimlik == "yenile" and yenileniyor
        if mesgul_bu:
            dolgu = _hex_rgba("#162B47")
            kenar = _karistir_rgba("#162B47", VURGU, 0.78)
            yazi_c = _hex_rgba(IKINCIL)
            ikon_c = _hex_rgba(VURGU)
        elif is_hover:
            dolgu = _karistir_rgba(YUZEY_HOVER, marka_renk, 0.16)
            kenar = _hex_rgba(marka_renk)
            yazi_c = _hex_rgba(YAZI)
            ikon_c = _hex_rgba(marka_renk)
        else:
            dolgu = _hex_rgba(YUZEY)
            kenar = _karistir_rgba(KENAR_PARLAK, marka_renk, 0.42)
            yazi_c = _hex_rgba(YAZI)
            ikon_c = _hex_rgba(marka_renk)

        d.rounded_rectangle(
            (x1 * S, y1 * S, x2 * S, y2 * S),
            radius=round(10.0 * o * S),
            fill=dolgu,
            outline=kenar,
            width=max(2, round(1.15 * o * S)),
        )

        ikon_r = 5.0 * o * S
        bosluk = 6.0 * o * S
        max_ty = (x2 - x1) * S - (ikon_r * 2.0 + bosluk + 12.0 * o * S)
        f_d = _metin_sigdir_font(d, metin_d, max_ty, round(11.5 * o * S), round(9.0 * o * S), "semibold")
        metin_d = _metin_kirp(d, metin_d, f_d, max_ty)
        tw, _ = _metin_boyut(d, metin_d, f_d)
        toplam_g = ikon_r * 2.0 + bosluk + tw
        bas_x = (x1 + x2) * S / 2.0 - toplam_g / 2.0
        icx = bas_x + ikon_r
        icy = dy * S

        _yenile_ikonu_ciz(d, icx, icy, ikon_r, ikon_c, aci_deg=float(donus_aci) if mesgul_bu else 0.0)

        d.text((bas_x + ikon_r * 2.0 + bosluk, icy), metin_d, fill=yazi_c, font=f_d, anchor="lm")

    return _kucult(img, w, h), hitboxes


# ================================================================ 5. TOAST (YÜZER BİLDİRİM)
def toast_boyut_hesapla(metin: str, olcek: float = 1.0) -> tuple[int, int]:
    """Bildirim metni için taşmasız ideal (genişlik, yükseklik) döner."""
    o = max(0.75, float(olcek))
    yuk = int(round(34 * o))
    gecici = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(gecici)
    temiz = str(metin or "").strip()
    ikon_pay = 22.0 * o if temiz.startswith(("✓", "⚠")) else 0.0
    if temiz.startswith(("✓", "⚠")):
        temiz = temiz[1:].strip()
    font = _font_al(round(12.0 * o * S), "semibold")
    tw_s, _ = _metin_boyut(d, temiz, font)
    gen = max(int(round(184 * o)), int(math.ceil(tw_s / S + ikon_pay + 36.0 * o)))
    return (gen, yuk)


def toast_gorseli(w: int, h: int, metin: str, vurgu_renk: str = YESIL) -> Image.Image:
    """Üst çentik altı odak çalmayan şık yüzer bildirim (toast) görselini üretir."""
    w = max(120, int(round(w)))
    h = max(24, int(round(h)))
    w_s, h_s = w * S, h * S
    o = h / 34.0
    yaricap_s = round(min(13.0 * o, h * 0.45) * S)

    # Hafif vurgu tonlu koyu cam kabuk (tam opak iç zemin, net kontrast)
    img = _kabuk_olustur(
        w_s,
        h_s,
        yaricap_s,
        False,
        vurgu_renk,
        max(2, round(1.4 * o * S)),
        ic_ton_renk=vurgu_renk,
        ic_ton_oran=0.08,
    ).copy()
    d = ImageDraw.Draw(img)

    ham = str(metin or "").strip()
    ikon_tur: str | None = None
    if ham.startswith("✓"):
        ikon_tur = "onay"
        temiz = ham[1:].strip()
    elif ham.startswith("⚠"):
        ikon_tur = "uyari"
        temiz = ham[1:].strip()
    else:
        temiz = ham

    cy = h_s / 2.0
    pad_x = 14.0 * o * S
    ikon_r = 6.2 * o * S
    ikon_blok = (ikon_r * 2.0 + 8.0 * o * S) if ikon_tur else 0.0
    max_metin_g = max(30.0, w_s - 2.0 * pad_x - ikon_blok)
    font = _metin_sigdir_font(d, temiz, max_metin_g, round(12.0 * o * S), round(9.0 * o * S), "semibold")
    temiz = _metin_kirp(d, temiz, font, max_metin_g)
    tw, _ = _metin_boyut(d, temiz, font)

    toplam_g = ikon_blok + tw
    bas_x = (w_s - toplam_g) / 2.0
    v_rgba = _hex_rgba(vurgu_renk)

    if ikon_tur == "onay":
        icx = bas_x + ikon_r
        d.ellipse(
            (icx - ikon_r * 1.22, cy - ikon_r * 1.22, icx + ikon_r * 1.22, cy + ikon_r * 1.22),
            fill=_karistir_rgba(ZEMIN_ORTA, vurgu_renk, 0.24),
        )
        _onay_ikonu_ciz(d, icx, cy, ikon_r * 0.85, v_rgba)
        metin_x = bas_x + ikon_blok
    elif ikon_tur == "uyari":
        icx = bas_x + ikon_r
        _uyari_ikonu_ciz(d, icx, cy, ikon_r * 0.95, v_rgba)
        metin_x = bas_x + ikon_blok
    else:
        metin_x = bas_x

    d.text((metin_x, cy), temiz, fill=_hex_rgba(YAZI), font=font, anchor="lm")
    return _kucult(img, w, h)
