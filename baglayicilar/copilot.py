"""Limit Çubuğu - GitHub Copilot bağlayıcısı (deneysel).

Aylık kotayı GitHub'ın resmi komut programı `gh` ile okur: `gh api copilot_internal/user`
(belgesiz uç nokta). Giriş bilgisini `gh` yönetir; burada token/oturum/uç nokta bilgisi
okunmaz, kaydedilmez, yazdırılmaz. Yanıttan yalnız kota yüzdeleri ve sıfırlanma tarihi alınır.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

import dil  # noqa: E402
import durum_ortak as ortak  # noqa: E402
from baglayicilar.taban import Baglayici, DENEYSEL  # noqa: E402

CREATE_NO_WINDOW = 0x08000000
GH_UCU = "copilot_internal/user"  # başında "/" yok: git-bash Windows'ta yola çevirir
KOTA_SIRASI = ("premium_interactions", "chat", "completions")
KOTA_ANAHTARLARI = {"premium_interactions": "copilot_kota_premium", "chat": "copilot_kota_chat",
                    "completions": "copilot_kota_completions"}
YUVALAR = ("bes_saat", "haftalik")


class CopilotHatasi(Exception):
    pass


def gh_komutu():
    yol = shutil.which("gh")
    if yol:
        return yol
    olasi = r"C:\Program Files\GitHub CLI\gh.exe"
    if os.path.isfile(olasi):
        return olasi
    return None


def _copilot_izi_var():
    ev = os.path.expanduser("~")
    # VS Code klasörü yeterli: Copilot VS Code'da yerleşik ve her GitHub hesabında ücretsiz Copilot var.
    if os.path.isdir(os.path.join(ev, ".copilot")):
        return True
    if glob.glob(os.path.join(ev, ".vscode", "extensions", "github.copilot*")):
        return True
    yerel = os.environ.get("LOCALAPPDATA")
    if yerel and os.path.isdir(os.path.join(yerel, "Programs", "Microsoft VS Code")):
        return True
    return False


def _hata_mesaji(stderr, kod):
    """Ham stderr mesaja konmaz; yalnız sabit, eşlenmiş mesajlar döner."""
    m = (stderr or "").lower()
    if "not logged" in m or "gh auth login" in m:
        return dil.t("copilot_gh_giris_yok")
    if "http 401" in m or "http 403" in m:
        return dil.t("copilot_izin_yok")
    if "http 404" in m:
        return dil.t("copilot_404")
    if "could not resolve" in m or "connection" in m or "timeout" in m:
        return dil.t("copilot_ag_hatasi")
    return dil.t("copilot_gh_hata", kod=kod)


def sorgula(zaman_asimi=10):
    """`gh api copilot_internal/user` çalıştırır, JSON sözlüğü döner. Hata: CopilotHatasi."""
    gh = gh_komutu()
    if not gh:
        raise CopilotHatasi(dil.t("copilot_gh_yok"))
    bayrak = CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        s = subprocess.run([gh, "api", GH_UCU], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                           timeout=zaman_asimi, creationflags=bayrak)
    except subprocess.TimeoutExpired:
        raise CopilotHatasi(dil.t("zaman_asimi_sn", sn=f"{zaman_asimi:g}"))
    except OSError as h:
        raise CopilotHatasi(dil.t("copilot_gh_baslatilamadi", tur=type(h).__name__))
    if s.returncode != 0:
        raise CopilotHatasi(_hata_mesaji(s.stderr, s.returncode))
    try:
        veri = json.loads(s.stdout)
    except ValueError:
        raise CopilotHatasi(dil.t("copilot_json_degil"))
    if not isinstance(veri, dict):
        raise CopilotHatasi(dil.t("copilot_bicim_bozuk"))
    return veri


def _sifirlanma(veri):
    t = ortak.zaman_cevir(veri.get("quota_reset_date_utc"))
    if t is not None:
        return t
    d = veri.get("quota_reset_date")
    if isinstance(d, str):
        try:
            t = datetime.strptime(d.strip()[:10], "%Y-%m-%d").replace(
                tzinfo=timezone.utc).timestamp()
            if t > 0:
                return t
        except (ValueError, OSError, OverflowError):
            pass
    return None


def ayristir(veri, simdi=None):
    """gh yanıtından {"bes_saat": ..., "haftalik": ..., "etiketler": ...} üretir."""
    if not isinstance(veri, dict) or not isinstance(veri.get("quota_snapshots"), dict):
        raise CopilotHatasi(dil.t("copilot_snapshots_yok"))
    kotalar = veri["quota_snapshots"]
    resets = _sifirlanma(veri)
    secilen = []
    sinirsiz = 0
    for ad in KOTA_SIRASI:
        k = kotalar.get(ad)
        if not isinstance(k, dict):
            continue
        if k.get("unlimited") is True:
            sinirsiz += 1
            continue
        hak = ortak.sayi(k.get("entitlement"))
        yuzde = ortak.sayi(k.get("percent_remaining"))
        if hak is None or hak <= 0 or yuzde is None:
            continue
        secilen.append((ad, max(0.0, min(100.0, yuzde))))
        if len(secilen) == 2:
            break
    if not secilen:
        if sinirsiz:
            raise CopilotHatasi(dil.t("copilot_sinirsiz"))
        raise CopilotHatasi(dil.t("copilot_kota_yok"))
    alanlar = {"etiketler": {}}
    for yuva, (ad, yuzde) in zip(YUVALAR, secilen):
        alanlar[yuva] = {"kalan": yuzde, "resets_at": resets}
        alanlar["etiketler"][yuva] = dil.t("copilot_aylik_etiket", ad=dil.t(KOTA_ANAHTARLARI[ad]))
    return alanlar


class CopilotBaglayici(Baglayici):
    kimlik = "copilot"
    ad = "GitHub Copilot"
    kisa_ad = "Copilot"
    renk = "#A78BFA"
    durum = DENEYSEL
    sira = 40
    okuma_yolu = ("GitHub'ın resmi gh komutu: gh api copilot_internal/user "
                  "(belgesiz uç nokta; giriş bilgisini gh yönetir)")
    okuma_yolu_anahtari = "yol_copilot"

    def bul(self):
        try:
            return gh_komutu() is not None and _copilot_izi_var()
        except Exception:
            return False

    def yenile(self, yol=None):
        yol = yol or ortak.DURUM_DOSYASI
        try:
            alanlar = ayristir(sorgula())
            alanlar["kaynak"] = dil.t("kaynak_otomatik_gh")
            with ortak.KILIT:
                veri = ortak.oku(yol)
                bolum = veri.get("copilot")
                if not isinstance(bolum, dict):
                    bolum = {}
                for anahtar, deger in alanlar.items():
                    if anahtar in YUVALAR:
                        eski = bolum.get(anahtar) if isinstance(bolum.get(anahtar), dict) else {}
                        eski.update(deger)
                        bolum[anahtar] = eski
                    else:
                        bolum[anahtar] = deger
                for yuva in YUVALAR:
                    if yuva not in alanlar:
                        bolum.pop(yuva, None)
                bolum["guncellendi"] = time.time()
                veri["copilot"] = bolum
                veri.setdefault("surum", 1)
                if not ortak.yaz(veri, yol):
                    return False, dil.t("copilot_yazilamadi")
            return True, dil.t("copilot_yenilendi")
        except CopilotHatasi as h:
            return False, dil.t("copilot_okunamadi", detay=h)
        except Exception as h:
            return False, dil.t("copilot_okunamadi", detay=type(h).__name__)


BAGLAYICI = CopilotBaglayici()
