"""LimitNotch kişisel veri ve gizli anahtar tarayıcısı.

Yayın öncesi `git ls-files` + izlenecek yeni dosyaları tarar.
Bulgu varsa dosya:satır yazar ve 1 çıkış koduyla döner; temizse 0 döner.
"""
import os
import re
import subprocess
import sys

KOK = os.path.dirname(os.path.abspath(__file__))

ATLANAN_UZANTILAR = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".exe", ".dll", ".pyd", ".pyc", ".woff", ".ttf",
}
ATLANAN_DIZINLER = {".git", "__pycache__", "build", "dist", "test_cikti"}

DESENLER = [
    ("e-posta", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("kisisel-yol", re.compile(r"[A-Za-z]:[\\/]Users[\\/](?!<|%|\{)[^\s\"'`]+", re.IGNORECASE)),
    ("kisisel-ad", re.compile(r"\b(Alptekin|alpptek)\b", re.IGNORECASE)),
    ("token-gh", re.compile(r"\b(ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{10,}")),
    ("token-api", re.compile(r"\b(sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{20,})")),
    ("bearer", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{16,}")),
    ("uzun-hex", re.compile(r"\b[0-9a-fA-F]{32,}\b")),
]

# Yalnız bilinen zararsız satırlar (dosya adına göre)
IZIN_VERILENLER = {
    "LICENSE": (re.compile(r"^Copyright \(c\) 2026 Alptekin Zengin$"),),
    # Örnek sahte e-posta/isim yok; uzun hex gibi yanlış pozitifler gerekirse buraya değil desenlerle ele alınır.
}


def _dosyalar():
    """git ls-files + untracked (ama gitignore dışı) dosyaları döner."""
    secilen = set()
    try:
        s = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=KOK, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if s.returncode == 0:
            for satir in s.stdout.splitlines():
                satir = satir.strip()
                if satir:
                    secilen.add(satir.replace("\\", "/"))
    except Exception:
        pass
    if not secilen:
        for kok, dizinler, dosyalar in os.walk(KOK):
            dizinler[:] = [d for d in dizinler if d not in ATLANAN_DIZINLER]
            for ad in dosyalar:
                yol = os.path.relpath(os.path.join(kok, ad), KOK).replace("\\", "/")
                secilen.add(yol)
    return sorted(secilen)


def tara_dosya(goreli_yol):
    """Tek dosyayı tarar -> [(satir_no, tur, metin)]."""
    if goreli_yol.split("/")[0] in ATLANAN_DIZINLER:
        return []
    _, uzanti = os.path.splitext(goreli_yol.lower())
    if uzanti in ATLANAN_UZANTILAR:
        return []
    tam = os.path.join(KOK, goreli_yol)
    if not os.path.isfile(tam):
        return []
    izinler = IZIN_VERILENLER.get(goreli_yol, ())
    try:
        with open(tam, "r", encoding="utf-8") as f:
            satirlar = f.readlines()
    except (UnicodeDecodeError, OSError):
        return []

    bulgular = []
    for no, ham in enumerate(satirlar, 1):
        satir = ham.rstrip("\r\n")
        if any(rx.search(satir) for rx in izinler):
            continue
        for tur, rx in DESENLER:
            if rx.search(satir):
                # test_arayuz içindeki sahte UUID/hash kontrolü gibi belirgin test kodlarını değil,
                # gerçek bulguları yakalamak için tüm eşleşmeleri raporla.
                bulgular.append((no, tur, satir.strip()[:120]))
    return bulgular


def main():
    toplam = 0
    for yol in _dosyalar():
        if yol == "tara.py":
            continue
        for no, tur, onizleme in tara_dosya(yol):
            print(f"{yol}:{no}: [{tur}] {onizleme}")
            toplam += 1
    if toplam:
        print(f"TOPLAM {toplam} bulgu!", file=sys.stderr)
        return 1
    print("Tarama temiz (0 bulgu).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
