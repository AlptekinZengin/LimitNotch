"""Generates LimitNotch visual assets (icon, logo, screenshots, demo GIF, banner)
using synthetic sample data — never reads real user data.

Usage:
    py -3 docs/ekran_uret.py
"""
import math
import os
import sys
import time

from PIL import Image, ImageDraw

os.environ.setdefault("LIMITNOTCH_DIL", "en")

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(BURASI)
ASSETS = os.path.join(KOK, "assets")
if KOK not in sys.path:
    sys.path.insert(0, KOK)

import dil  # noqa: E402
import gorsel_motor as gm  # noqa: E402

ARACLAR = ["claude", "codex", "antigravity", "copilot"]
ARACLAR_DURUM = {
    "claude": {"bes_kalan": 78.0, "hft_kalan": 64.0, "renk": "#D97757"},
    "codex": {"bes_kalan": 34.0, "hft_kalan": 71.0, "renk": "#10B981"},
    "antigravity": {"bes_kalan": 88.0, "hft_kalan": 92.0, "renk": "#38BDF8"},
    "copilot": {"bes_kalan": 99.0, "hft_kalan": 100.0, "renk": "#A78BFA"},
}
W_PANEL = 12 + 76 * len(ARACLAR) + 12 + 42 * 4 + 10  # 494


def _renkli_halka(d, cx, cy, r, kalinlik, oran_yuzde, renk_hex, iz_renk=gm.IZ):
    """Belirli renkte yuvarlak uçlu ilerleme halkası (3x supersampling)."""
    w = max(2, round(kalinlik))
    kutu = (cx - r, cy - r, cx + r, cy + r)
    d.ellipse(kutu, outline=gm._hex_rgba(iz_renk), width=w)
    renk = gm._hex_rgba(renk_hex)
    bas = -90.0
    bit = -90.0 + 3.6 * oran_yuzde
    d.arc(kutu, start=bas, end=bit, fill=renk, width=w)
    r_orta = r - w / 2.0
    cap_r = max(1.0, w / 2.0 - 0.3)
    for aci in (bas, bit):
        rad = math.radians(aci)
        px = cx + r_orta * math.cos(rad)
        py = cy + r_orta * math.sin(rad)
        d.ellipse((px - cap_r, py - cap_r, px + cap_r, py + cap_r), fill=renk)


def uret_logo_ve_ikon():
    """Creates 3x supersampled 256x256 logo PNG and multi-size Windows .ico."""
    os.makedirs(ASSETS, exist_ok=True)
    w = 256
    s = 3
    w_s = w * s
    img = gm._kabuk_olustur(
        w_s, w_s, round(58 * s), False, gm.KENAR_PARLAK, round(3.0 * s),
        ic_ton_renk=gm.VURGU, ic_ton_oran=0.04,
    ).copy()
    d = ImageDraw.Draw(img)

    # Üst çentik pilli + 3 canlı durum LED noktası (Yeşil · Sarı · Kırmızı)
    canli_yesil = "#00E676"
    canli_sari = "#FFD600"
    canli_kirmizi = "#FF2E43"

    pill_w = 114 * s
    pill_h = 28 * s
    px1 = (w_s - pill_w) / 2.0
    py1 = 15 * s
    d.rounded_rectangle(
        (px1, py1, px1 + pill_w, py1 + pill_h),
        radius=14 * s,
        fill=gm._hex_rgba("#090F1D"),
        outline=gm._hex_rgba(gm.KENAR_PARLAK),
        width=max(2, round(1.8 * s)),
    )
    led_y = py1 + pill_h / 2.0
    led_r = 7.2 * s
    for idx, renk in enumerate((canli_yesil, canli_sari, canli_kirmizi)):
        lx = w_s / 2.0 + (idx - 1) * 28.0 * s
        d.ellipse(
            (lx - led_r * 1.65, led_y - led_r * 1.65, lx + led_r * 1.65, led_y + led_r * 1.65),
            fill=gm._karistir_rgba(gm.ZEMIN_ORTA, renk, 0.38),
        )
        d.ellipse((lx - led_r, led_y - led_r, lx + led_r, led_y + led_r), fill=gm._hex_rgba(renk))

    # Ortada kalın ve canlı 3 eşmerkezli kota halkası: Yeşil (%78) -> Sarı (%62) -> Kırmızı (%54)
    cx = w_s / 2.0
    cy = w_s / 2.0 + 14.0 * s
    _renkli_halka(d, cx, cy, 78 * s, 16.0 * s, 78.0, canli_yesil, iz_renk=gm.IZ)
    _renkli_halka(d, cx, cy, 55 * s, 15.0 * s, 62.0, canli_sari, iz_renk="#18243D")
    _renkli_halka(d, cx, cy, 32 * s, 14.5 * s, 54.0, canli_kirmizi, iz_renk="#162138")

    logo = gm._kucult(img, w, w)
    logo.save(os.path.join(BURASI, "logo.png"))

    ico_boyutlari = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    logo.save(os.path.join(ASSETS, "limitnotch.ico"), format="ICO", sizes=ico_boyutlari)
    return logo


def _ornek_kart(arac, simdi):
    if arac == "claude":
        return gm.kart_gorseli(
            368, 356,
            arac_ad="Claude Code",
            marka_renk="#D97757",
            kaynak_etiketi=(dil.t("kaynak_otomatik_yenilendi"), gm.YESIL),
            bes_durum=(78.0, simdi + 2 * 3600 + 24 * 60, False),
            hft_durum=(64.0, simdi + 3 * 86400 + 5 * 3600, False),
            bes_anim_oran=0.78,
            hft_anim_oran=0.64,
            son_guncelleme=dil.t("once_dk", n=2),
            not_metni=dil.t("claude_yenilendi"),
            not_renk=gm.YESIL,
        )[0]
    return gm.kart_gorseli(
        368, 356,
        arac_ad="Codex",
        marka_renk="#10B981",
        kaynak_etiketi=(dil.t("kaynak_otomatik_yenilendi"), gm.YESIL),
        bes_durum=(34.0, simdi + 1 * 3600 + 18 * 60, False),
        hft_durum=(71.0, simdi + 4 * 86400 + 2 * 3600, False),
        bes_anim_oran=0.34,
        hft_anim_oran=0.71,
        son_guncelleme=dil.t("once_dk", n=1),
        not_metni=dil.t("codex_yenilendi"),
        not_renk=gm.YESIL,
    )[0]


def uret_statik_ekranlar(simdi):
    cubuk = gm.centik_gorseli(
        168, 24,
        [gm.YESIL, gm.AMBER, gm.YESIL, gm.YESIL],
        dil.t("centik_yuzde", ad="Codex", yuzde="34"),
        vurgu_renk=gm.AMBER, nefes=0.65,
    )
    cubuk.save(os.path.join(BURASI, "cubuk.png"))

    panel, _ = gm.panel_gorseli(
        W_PANEL, 86, ARACLAR_DURUM,
        secili_arac="claude", hover_arac="claude",
        coklu_monitor=True, araclar=ARACLAR,
    )
    panel.save(os.path.join(BURASI, "panel.png"))

    kart = _ornek_kart("claude", simdi)
    kart.save(os.path.join(BURASI, "kart.png"))
    return cubuk, panel, kart


def _gif_zemin(w, h):
    """Dark desktop top-edge backdrop for animated demo GIF."""
    serit = Image.new("RGBA", (1, h))
    pix = serit.load()
    for y in range(h):
        t = y / max(1, h - 1)
        pix[0, y] = gm._karistir_rgba("#0A1220", "#111B30", t)
    bg = serit.resize((w, h))
    d = ImageDraw.Draw(bg)
    # Subtle window border & faint grid dots for desktop context
    d.rounded_rectangle((12, 0, w - 13, h - 13), radius=14, outline=gm._hex_rgba("#1C2944"))
    return bg


def uret_demo_gif(simdi):
    """Produces smooth looped notch -> panel -> cards -> notch demo GIF (<500 KB)."""
    w, h = 560, 470
    zemin = _gif_zemin(w, h)
    noktalar = [gm.YESIL, gm.AMBER, gm.YESIL, gm.YESIL]
    centik_y = 24
    centik_g = 168

    def kare_yap(ust_img, kart_img=None, kart_cx=None, kart_alpha=1.0):
        canvas = zemin.copy()
        ux = (w - ust_img.width) // 2
        canvas.alpha_composite(ust_img, (ux, 0))
        if kart_img is not None:
            k = kart_img
            if kart_alpha < 1.0:
                r, g, b, a = k.split()
                a = a.point(lambda p: int(p * kart_alpha))
                k = Image.merge("RGBA", (r, g, b, a))
            kx = max(16, min(w - k.width - 16, int((kart_cx or w // 2) - k.width / 2)))
            canvas.alpha_composite(k, (kx, 86 + 10))
        return canvas.convert("P", palette=Image.ADAPTIVE, colors=128)

    cubuk = gm.centik_gorseli(
        centik_g, centik_y, noktalar,
        dil.t("centik_yuzde", ad="Codex", yuzde="34"),
        vurgu_renk=gm.AMBER, nefes=0.65,
    )
    panel_sade, hb = gm.panel_gorseli(
        W_PANEL, 86, ARACLAR_DURUM, coklu_monitor=True, araclar=ARACLAR,
    )
    panel_claude, _ = gm.panel_gorseli(
        W_PANEL, 86, ARACLAR_DURUM, secili_arac="claude", hover_arac="claude",
        coklu_monitor=True, araclar=ARACLAR,
    )
    panel_codex, _ = gm.panel_gorseli(
        W_PANEL, 86, ARACLAR_DURUM, secili_arac="codex", hover_arac="codex",
        coklu_monitor=True, araclar=ARACLAR,
    )
    kart_claude = _ornek_kart("claude", simdi)
    kart_codex = _ornek_kart("codex", simdi)

    panel_x0 = (w - W_PANEL) // 2
    cx_claude = panel_x0 + (hb["claude"][0] + hb["claude"][2]) / 2
    cx_codex = panel_x0 + (hb["codex"][0] + hb["codex"][2]) / 2

    kareler = []
    sureler = []

    # 1) Closed notch
    kareler.append(kare_yap(cubuk))
    sureler.append(950)

    # 2) Expand transition
    for t in (0.25, 0.55, 0.82):
        gw = round(centik_g + (W_PANEL - centik_g) * t)
        gh = round(centik_y + (86 - centik_y) * t)
        kareler.append(kare_yap(gm.gecis_gorseli(gw, gh, gm.VURGU)))
        sureler.append(55)

    # 3) Expanded panel
    kareler.append(kare_yap(panel_sade))
    sureler.append(650)

    # 4) Claude card fade in & hold
    kareler.append(kare_yap(panel_claude, kart_claude, cx_claude, kart_alpha=0.55))
    sureler.append(70)
    kareler.append(kare_yap(panel_claude, kart_claude, cx_claude, kart_alpha=1.0))
    sureler.append(1450)

    # 5) Switch to Codex
    kareler.append(kare_yap(panel_codex, kart_codex, cx_codex, kart_alpha=1.0))
    sureler.append(1350)

    # 6) Collapse back to notch
    for t in (0.72, 0.38):
        gw = round(centik_g + (W_PANEL - centik_g) * t)
        gh = round(centik_y + (86 - centik_y) * t)
        kareler.append(kare_yap(gm.gecis_gorseli(gw, gh, gm.AMBER)))
        sureler.append(55)

    cikti = os.path.join(BURASI, "demo.gif")
    kareler[0].save(
        cikti,
        save_all=True,
        append_images=kareler[1:],
        duration=sureler,
        loop=0,
        optimize=True,
    )
    return cikti


def uret_banner(logo, cubuk, panel, kart):
    """Creates 1280x640 GitHub social preview / README hero banner."""
    w, h = 1280, 640
    # Smooth gradient backdrop
    serit = Image.new("RGBA", (1, h))
    pix = serit.load()
    for y in range(h):
        t = y / max(1, h - 1)
        pix[0, y] = gm._karistir_rgba("#09111E", "#122136", t)
    bg = serit.resize((w, h))

    # Subtle radial glow behind right showcase
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r, a in ((340, 14), (240, 22), (140, 28)):
        gd.ellipse((900 - r, 340 - r, 900 + r, 340 + r), fill=(56, 189, 248, a))
    bg.alpha_composite(glow)

    d = ImageDraw.Draw(bg)

    # Top-center mini notch accent at very top
    bg.alpha_composite(cubuk, ((w - cubuk.width) // 2, 0))

    # Left column: Logo + Title + Subtitle + Tool badges
    lx = 76
    logo_kucuk = logo.resize((72, 72), gm._RESAMPLE)
    bg.alpha_composite(logo_kucuk, (lx, 128))

    title_font = gm._font_al(64, "bold")
    d.text((lx + 92, 164), "LimitNotch", fill=gm._hex_rgba(gm.YAZI), font=title_font, anchor="lm")

    sub_font = gm._font_al(25, "regular")
    d.text(
        (lx, 242),
        "Real-time AI coding limits in a sleek",
        fill=gm._hex_rgba(gm.IKINCIL), font=sub_font, anchor="lm",
    )
    d.text(
        (lx, 276),
        "Windows Dynamic Island notch.",
        fill=gm._hex_rgba(gm.IKINCIL), font=sub_font, anchor="lm",
    )

    # Feature pills
    ozellik_font = gm._font_al(16, "semibold")
    for idx, (metin, renk) in enumerate([
        ("No passwords or cookies", gm.YESIL),
        ("Single .exe · TR / EN", gm.VURGU),
        ("Alt + X shortcut", "#A78BFA"),
    ]):
        py = 344 + idx * 42
        d.ellipse((lx, py - 5, lx + 10, py + 5), fill=gm._hex_rgba(renk))
        d.text((lx + 22, py), metin, fill=gm._hex_rgba(gm.SOLUK), font=ozellik_font, anchor="lm")

    # Tool chips row at bottom left
    chip_font = gm._font_al(15, "semibold")
    cx = lx
    cy = 520
    for ad, renk in (
        ("Claude Code", "#D97757"),
        ("Codex", "#10B981"),
        ("Antigravity", "#38BDF8"),
        ("Copilot", "#A78BFA"),
    ):
        tw, th = gm._metin_boyut(d, ad, chip_font)
        cw = tw + 34
        ch = 34
        d.rounded_rectangle(
            (cx, cy - ch / 2, cx + cw, cy + ch / 2),
            radius=17,
            fill=gm._karistir_rgba(gm.ZEMIN_ORTA, renk, 0.14),
            outline=gm._karistir_rgba(gm.ZEMIN_ORTA, renk, 0.55),
            width=2,
        )
        d.ellipse((cx + 12, cy - 4, cx + 20, cy + 4), fill=gm._hex_rgba(renk))
        d.text((cx + 26, cy), ad, fill=gm._hex_rgba(gm.YAZI), font=chip_font, anchor="lm")
        cx += cw + 12

    # Right column: Live panel + Claude card showcase
    rx = 685
    panel_x = rx
    panel_y = 92
    bg.alpha_composite(panel, (panel_x, panel_y))
    kart_x = rx + 62
    kart_y = panel_y + panel.height + 16
    bg.alpha_composite(kart, (kart_x, kart_y))

    cikti = os.path.join(BURASI, "banner.png")
    bg.save(cikti)
    return cikti


def main():
    os.makedirs(BURASI, exist_ok=True)
    simdi = time.time()
    logo = uret_logo_ve_ikon()
    cubuk, panel, kart = uret_statik_ekranlar(simdi)
    gif_yol = uret_demo_gif(simdi)
    banner_yol = uret_banner(logo, cubuk, panel, kart)
    gif_kb = round(os.path.getsize(gif_yol) / 1024, 1)
    print(f"Generated assets in {BURASI} & {ASSETS} (demo.gif: {gif_kb} KB, banner: {banner_yol})")


if __name__ == "__main__":
    main()
