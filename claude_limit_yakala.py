"""Claude Code statusLine yakalayıcısı.

Claude Code, statusLine komutuna her güncellemede stdin üzerinden JSON gönderir.
Bu betik:
  1) rate_limits.five_hour / rate_limits.seven_day alanlarını okuyup
     kalan = max(0, 100 - used_percentage) olarak durum.json'daki "claude" bölümüne yazar,
  2) Claude Code alt satırı için tek satırlık sade bir durum çıktısı basar.
Hiçbir koşulda çökmez; ağ, token veya kimlik dosyası erişimi yoktur.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import durum_ortak as ortak
except Exception:  # ortak modül bulunamazsa yalnızca statusline basılır
    ortak = None


def stdin_oku():
    try:
        ham = sys.stdin.buffer.read()
        if not ham:
            return {}
        veri = json.loads(ham.decode("utf-8-sig", errors="replace"))
        return veri if isinstance(veri, dict) else {}
    except Exception:
        return {}


def sure_kisa(saniye):
    if saniye is None:
        return ""
    saniye = max(0, int(saniye))
    gun, kalan = divmod(saniye, 86400)
    sa, kalan = divmod(kalan, 3600)
    dk = kalan // 60
    if gun:
        return f"{gun}g {sa}sa"
    if sa:
        return f"{sa}sa {dk}dk"
    return f"{dk}dk"


def pencere_cikar(rate_limits, anahtar):
    """(kalan, resets_at) ya da None döner."""
    p = rate_limits.get(anahtar) if isinstance(rate_limits, dict) else None
    if not isinstance(p, dict):
        return None
    try:
        kullanilan = float(p.get("used_percentage"))
    except (TypeError, ValueError):
        return None
    kalan = max(0.0, min(100.0, 100.0 - kullanilan))
    reset = ortak.zaman_cevir(p.get("resets_at")) if ortak else None
    return kalan, reset


def main():
    veri = stdin_oku()
    rate = veri.get("rate_limits") if isinstance(veri.get("rate_limits"), dict) else {}

    bes = pencere_cikar(rate, "five_hour") if ortak else None
    hft = pencere_cikar(rate, "seven_day") if ortak else None

    # durum.json'a kaydet (yalnızca gerçek veri geldiyse)
    if ortak and (bes or hft):
        alanlar = {"kaynak": "otomatik"}
        if bes:
            alanlar["bes_saat"] = {"kalan": round(bes[0], 1), "resets_at": bes[1]}
        if hft:
            alanlar["haftalik"] = {"kalan": round(hft[0], 1), "resets_at": hft[1]}
        try:
            ortak.guncelle("claude", alanlar)
        except Exception:
            pass

    # Statusline satırı
    parcalar = ["Claude"]
    model = veri.get("model")
    if isinstance(model, dict):
        ad = model.get("display_name") or model.get("id")
        if ad:
            parcalar[0] = f"Claude · {ad}"

    simdi = time.time()
    if bes:
        ek = f" ({sure_kisa(bes[1] - simdi)})" if bes[1] else ""
        parcalar.append(f"5s: %{bes[0]:.0f}{ek}")
    else:
        parcalar.append("5s: –")
    parcalar.append(f"Hft: %{hft[0]:.0f}" if hft else "Hft: –")

    baglam = veri.get("context_window")
    if isinstance(baglam, dict):
        try:
            parcalar.append(f"Bağlam: %{float(baglam.get('used_percentage')):.0f}")
        except (TypeError, ValueError):
            pass

    satir = " | ".join(parcalar)
    try:
        sys.stdout.buffer.write((satir + "\n").encode("utf-8"))
        sys.stdout.flush()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            sys.stdout.write("Claude\n")
        except Exception:
            pass
    sys.exit(0)
