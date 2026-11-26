"""Limit Çubuğu - yalnız kullanıcı "Yenile"ye basınca çalışan yenileme işlemleri.

- Claude: `claude -p /usage --output-format json`ı pencere açmadan çalıştırır. `/usage` Claude
  Code'un yerel komutudur (modele istek yok, jeton yok); 5 saatlik + haftalık yüzde ve yenilenme
  saatini ayrıştırıp durum.json'a yazar. Token / .credentials.json okunmaz; yetkiyi CLI yönetir.
- Codex: `codex app-server`ı pencere açmadan başlatır, JSON-RPC ile `initialize` +
  `account/rateLimits/read` sorar, cevabı alır almaz sunucuyu kapatır.
  Token / auth.json / gizli HTTP uç noktası okunmaz; yetkiyi Codex'in kendisi yönetir.
- Antigravity: çalışan dil sunucusunun yalnız localhost'taki Connect-RPC uç noktası
  (`~/.gemini/antigravity/daemon/hub_<port>.json` portu + csrf başlığı; csrf yazdırılmaz/saklanmaz).
  `RetrieveUserQuotaSummary` iki grup (Gemini, Claude/GPT) için 5 saatlik + haftalık kalan oranı
  verir; bu çağrı başarısızsa `GetUserStatus`tan yalnız 5 saatlik okunur, haftalık mevcut kalır.
  Her pencerede KALANI EN AZ olan grup gösterilir (`grup` alanı). Yalnız okuma çağrıları.

Hiçbir fonksiyon kendiliğinden ya da döngüde çağrılmaz.
Tek seferlik elle deneme:  py -3 yenileyici.py codex   |   py -3 yenileyici.py claude
"""
import glob
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dil  # noqa: E402
import durum_ortak as ortak  # noqa: E402

CODEX_ZAMAN_ASIMI = 9.0  # sn
CODEX_KAYNAK = "Otomatik (yenilendi)"
CREATE_NO_WINDOW = 0x08000000


class CodexHatasi(Exception):
    pass


# ---------------------------------------------------------------- codex
CODEX_BULUNAMADI = "codex bulunamadı (PATH'te ve Codex Desktop'ta yok)"
# Codex Desktop'un kendi çalışan kopyalarının kökü (testlerde değiştirilebilir).
CODEX_DESKTOP_KOKU = os.path.join(os.path.expanduser("~"), ".codex", "packages",
                                  "app-server-daemon", "releases")


def _surum_tuple(ad):
    """'0.167.0-x86_64-pc-windows-msvc' -> (0, 167, 0); sürüm okunamazsa None."""
    m = re.match(r"(\d+(?:\.\d+)*)", ad)
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def _desktop_codex_adaylari(kok):
    """Desktop daemon codex.exe yolları, en yüksek sürüm önce (klasör adındaki sürüme göre)."""
    bulunan = []
    try:
        adlar = os.listdir(kok)
    except OSError:
        return []
    for ad in adlar:
        surum = _surum_tuple(ad)
        exe = os.path.join(kok, ad, "bin", "codex.exe")
        if surum is not None and os.path.isfile(exe):
            bulunan.append((surum, exe))
    bulunan.sort(key=lambda t: t[0], reverse=True)
    return [exe for _, exe in bulunan]


def codex_adaylari(path_codex=None, desktop_koku=None):
    """Denenecek codex komutları, öncelik sırasıyla: PATH/npm vendor exe, sonra Desktop daemon."""
    adaylar = []
    yol = path_codex if path_codex is not None else shutil.which("codex")
    if yol and os.path.isfile(yol):
        kok = os.path.dirname(yol)
        desen = os.path.join(kok, "node_modules", "@openai", "codex", "node_modules",
                             "@openai", "codex-win32-*", "vendor", "*", "bin", "codex.exe")
        vendor = [p for p in sorted(glob.glob(desen)) if os.path.isfile(p)]
        adaylar.append([vendor[0]] if vendor else [yol])
    for exe in _desktop_codex_adaylari(desktop_koku or CODEX_DESKTOP_KOKU):
        adaylar.append([exe])
    return adaylar


def codex_komutu(path_codex=None, desktop_koku=None):
    """Codex'i başlatacak ilk komutu döner (yoksa None). Sıra: PATH/npm vendor, Codex Desktop."""
    adaylar = codex_adaylari(path_codex, desktop_koku)
    return adaylar[0] if adaylar else None


def _pencere(snap, sira):
    """RateLimitSnapshot içinden 'primary'/'secondary' penceresini okur (camelCase + snake_case)."""
    if not isinstance(snap, dict):
        return None
    p = snap.get(sira)
    if not isinstance(p, dict):
        return None
    kullanilan = ortak.sayi(p.get("usedPercent", p.get("used_percent")))
    if kullanilan is None:
        return None
    reset = ortak.zaman_cevir(p.get("resetsAt", p.get("resets_at")))
    sure = ortak.sayi(p.get("windowDurationMins", p.get("window_duration_mins", p.get("window_minutes"))))
    return {"kalan": max(0.0, min(100.0, 100.0 - kullanilan)), "resets_at": reset, "dk": sure}


def codex_ayristir(sonuc):
    """account/rateLimits/read sonucunu {"bes_saat": {...}, "haftalik": {...}} biçimine çevirir."""
    if not isinstance(sonuc, dict):
        raise CodexHatasi(dil.t("codex_cevap_bozuk"))
    snap = sonuc.get("rateLimits", sonuc.get("rate_limits"))
    coklu = sonuc.get("rateLimitsByLimitId")
    if isinstance(coklu, dict) and isinstance(coklu.get("codex"), dict):
        snap = coklu["codex"]
    pencereler = [w for w in (_pencere(snap, "primary"), _pencere(snap, "secondary")) if w]
    if not pencereler:
        raise CodexHatasi(dil.t("codex_pencere_yok"))
    alanlar = {}
    for i, w in enumerate(pencereler):
        dk = w.pop("dk")
        if dk is not None:
            anahtar = "bes_saat" if dk <= 24 * 60 else "haftalik"
        else:
            anahtar = "bes_saat" if i == 0 else "haftalik"
        alanlar.setdefault(anahtar, w)
    return alanlar


def codex_sorgula(zaman_asimi=CODEX_ZAMAN_ASIMI, komut=None):
    """codex app-server'dan ham rateLimits sonucunu döner. Hata olursa CodexHatasi.

    komut verilmezse adaylar sırayla denenir; biri hata verirse sonrakine geçilir."""
    if komut:
        return _codex_sorgula_tek(komut, zaman_asimi)
    adaylar = codex_adaylari()
    if not adaylar:
        raise CodexHatasi(dil.t("codex_bulunamadi"))
    son = None
    for aday in adaylar:
        try:
            return _codex_sorgula_tek(aday, zaman_asimi)
        except CodexHatasi as h:
            son = h
    raise son


def _codex_sorgula_tek(komut, zaman_asimi):
    bayrak = CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        surec = subprocess.Popen(
            komut + ["app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, creationflags=bayrak,
        )
    except OSError as h:
        raise CodexHatasi(dil.t("codex_baslatilamadi", hata=h))

    satirlar = queue.Queue()

    def okuyucu():
        try:
            for satir in iter(surec.stdout.readline, b""):
                satirlar.put(satir)
        except Exception:
            pass
        satirlar.put(None)

    threading.Thread(target=okuyucu, daemon=True).start()
    bitis = time.time() + zaman_asimi

    def gonder(mesaj):
        surec.stdin.write((json.dumps(mesaj) + "\n").encode("utf-8"))
        surec.stdin.flush()

    def cevap_bekle(istek_id):
        while True:
            kalan = bitis - time.time()
            if kalan <= 0:
                raise CodexHatasi(dil.t("zaman_asimi_sn", sn=f"{zaman_asimi:.0f}"))
            try:
                satir = satirlar.get(timeout=kalan)
            except queue.Empty:
                raise CodexHatasi(dil.t("zaman_asimi_sn", sn=f"{zaman_asimi:.0f}"))
            if satir is None:
                raise CodexHatasi(dil.t("codex_kapandi"))
            try:
                m = json.loads(satir.decode("utf-8", "replace"))
            except ValueError:
                continue
            if isinstance(m, dict) and m.get("id") == istek_id:
                if "error" in m:
                    hata = m["error"]
                    mesaj = hata.get("message") if isinstance(hata, dict) else hata
                    raise CodexHatasi(dil.t("codex_hata_dondu", mesaj=mesaj))
                return m.get("result")

    try:
        gonder({"id": 1, "method": "initialize",
                "params": {"clientInfo": {"name": "limitnotch", "title": "LimitNotch", "version": "1.0"}}})
        cevap_bekle(1)
        gonder({"method": "initialized"})
        gonder({"id": 2, "method": "account/rateLimits/read"})
        return cevap_bekle(2)
    except (OSError, ValueError) as h:
        raise CodexHatasi(dil.t("codex_iletisim_yok", hata=h))
    finally:
        _kapat(surec)


def _kapat(surec):
    try:
        surec.stdin.close()
    except Exception:
        pass
    try:
        surec.wait(timeout=1.5)
        return
    except Exception:
        pass
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(surec.pid)], capture_output=True,
                           creationflags=CREATE_NO_WINDOW, timeout=5)
        except Exception:
            pass
    try:
        surec.kill()
        surec.wait(timeout=2)
    except Exception:
        pass


# ---------------------------------------------------------------- claude
class ClaudeHatasi(Exception):
    pass


CLAUDE_ZAMAN_ASIMI = 25.0  # sn (ölçülen: ~1.5-4 sn)
CLAUDE_KAYNAK = "Otomatik (yenilendi)"
# `/usage` Claude Code'un yerel komutudur: modele istek atmaz, jeton harcamaz (total_cost_usd = 0).
# --safe-mode + --strict-mcp-config eklentileri/MCP'yi yüklemez -> açılış ~2 sn.
CLAUDE_HIZLI_BAYRAKLAR = ["--safe-mode", "--strict-mcp-config"]
_AYLAR = {a: i for i, a in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
_SATIR_DESENI = {
    "bes_saat": re.compile(r"Current session\s*:\s*(?P<yuzde>\d+(?:\.\d+)?)\s*%\s*used(?P<kuyruk>[^\n]*)", re.I),
    "haftalik": re.compile(r"Current week(?:\s*\(all models\))?\s*:\s*(?P<yuzde>\d+(?:\.\d+)?)\s*%\s*used(?P<kuyruk>[^\n]*)", re.I),
}
_RESET_DESENI = re.compile(
    r"resets\s+(?:(?P<ay>[A-Za-z]{3})[a-z]*\.?\s+(?P<gun>\d{1,2}),?\s+(?:at\s+)?)?"
    r"(?P<saat>\d{1,2})(?::(?P<dk>\d{2}))?\s*(?P<ampm>am|pm)?\s*(?:\((?P<tz>[^)]+)\))?", re.I)


def claude_komutu():
    """Kurulu claude CLI'nin yolunu bulur (kimlik doğrulamayı CLI kendisi yönetir)."""
    yol = shutil.which("claude")
    if yol:
        return yol
    aday = os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")
    return aday if os.path.isfile(aday) else None


def _saat_dilimi(ad):
    if not ad:
        return None
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(ad.strip())
    except Exception:
        return None


def claude_reset_coz(kuyruk, simdi=None):
    """'· resets Nov 26, 12:09am (Europe/Istanbul)' -> epoch sn. Çözülemezse None."""
    m = _RESET_DESENI.search(kuyruk or "")
    if not m:
        return None
    simdi = time.time() if simdi is None else simdi
    saat, dk = int(m.group("saat")), int(m.group("dk") or 0)
    ampm = (m.group("ampm") or "").lower()
    if ampm == "pm" and saat != 12:
        saat += 12
    elif ampm == "am" and saat == 12:
        saat = 0
    if saat > 23 or dk > 59:
        return None
    tz = _saat_dilimi(m.group("tz"))
    bugun = datetime.fromtimestamp(simdi, tz) if tz else datetime.fromtimestamp(simdi)
    try:
        if m.group("ay"):
            ay = _AYLAR.get(m.group("ay")[:3].lower())
            if not ay:
                return None
            hedef = bugun.replace(month=ay, day=int(m.group("gun")), hour=saat, minute=dk,
                                  second=0, microsecond=0)
            if hedef.timestamp() < simdi - 2 * 86400:  # yıl dönümü (ör. Aralık -> Ocak)
                hedef = hedef.replace(year=hedef.year + 1)
        else:
            hedef = bugun.replace(hour=saat, minute=dk, second=0, microsecond=0)
            if hedef.timestamp() <= simdi:
                hedef += timedelta(days=1)
    except ValueError:
        return None
    return hedef.timestamp()


def claude_ayristir(metin, simdi=None):
    """`claude -p /usage` metnini {"bes_saat": {...}, "haftalik": {...}} biçimine çevirir."""
    if not isinstance(metin, str) or not metin.strip():
        raise ClaudeHatasi(dil.t("claude_cikti_bos"))
    alanlar = {}
    for anahtar, desen in _SATIR_DESENI.items():
        m = desen.search(metin)
        if not m:
            continue
        kullanilan = float(m.group("yuzde"))
        alanlar[anahtar] = {"kalan": round(max(0.0, min(100.0, 100.0 - kullanilan)), 1),
                            "resets_at": claude_reset_coz(m.group("kuyruk"), simdi)}
    if not alanlar:
        ilk = metin.strip().splitlines()[0][:80]
        raise ClaudeHatasi(dil.t("claude_satir_yok", ilk=ilk))
    return alanlar


def claude_sorgula(zaman_asimi=CLAUDE_ZAMAN_ASIMI, komut=None):
    """`claude -p /usage --output-format json` çalıştırır, sonuç metnini döner. Hata: ClaudeHatasi."""
    komut = komut or claude_komutu()
    if not komut:
        raise ClaudeHatasi(dil.t("claude_komut_yok"))
    temel = [komut, "-p", "/usage", "--output-format", "json", "--no-session-persistence"]
    bayrak = CREATE_NO_WINDOW if os.name == "nt" else 0
    bitis = time.time() + zaman_asimi
    son_hata = dil.t("claude_bilinmeyen_hata")
    # Önce hızlı bayraklarla dene; eski bir sürüm bayrağı tanımazsa düz komutla bir kez daha dene.
    for ek in (CLAUDE_HIZLI_BAYRAKLAR, []):
        kalan = bitis - time.time()
        if kalan <= 0:
            break
        try:
            s = subprocess.run(temel + ek, stdin=subprocess.DEVNULL, capture_output=True,
                               timeout=kalan, cwd=tempfile.gettempdir(), creationflags=bayrak)
        except subprocess.TimeoutExpired:
            raise ClaudeHatasi(dil.t("zaman_asimi_sn", sn=f"{zaman_asimi:.0f}"))
        except OSError as h:
            raise ClaudeHatasi(dil.t("claude_baslatilamadi", hata=h))
        cikti = s.stdout.decode("utf-8", "replace").strip()
        try:
            veri = json.loads(cikti.splitlines()[-1]) if cikti else None
        except ValueError:
            veri = None
        if isinstance(veri, dict):
            if veri.get("is_error"):
                raise ClaudeHatasi(dil.t("claude_hata_dondu", detay=str(veri.get("result"))[:80]))
            return veri.get("result") or ""
        hata = (s.stderr.decode("utf-8", "replace").strip() or cikti or dil.t("claude_cikis_kodu", kod=s.returncode))
        son_hata = hata.splitlines()[0][:80] if hata else son_hata
    raise ClaudeHatasi(son_hata)


# ---------------------------------------------------------------- antigravity
class AntigravityHatasi(Exception):
    pass


ANTIGRAVITY_ZAMAN_ASIMI = 4.0  # sn (hub başına)
ANTIGRAVITY_KAYNAK = "Otomatik (yenilendi)"
ANTIGRAVITY_HUB_DESENI = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity",
                                      "daemon", "hub_*.json")
_AG_SERVIS = "/exa.language_server_pb.LanguageServerService/"
_AG_GOVDE = b'{"metadata":{"ideName":"antigravity","extensionName":"antigravity"}}'
_AG_PENCERE = {"5h": "bes_saat", "weekly": "haftalik"}
ANTIGRAVITY_ANA_GRUP = "Gemini"
_AG_ETIKET = {"bes_saat": "5 Saatlik", "haftalik": "Haftalık"}


def antigravity_hub_dosyalari(desen=None):
    """hub_*.json dosyalarını en yeni değişiklik zamanından başlayarak sıralar."""
    def mtime(f):
        try:
            return os.path.getmtime(f)
        except OSError:
            return 0.0
    return sorted(glob.glob(desen or ANTIGRAVITY_HUB_DESENI), key=mtime, reverse=True)


def _antigravity_rpc(port, csrf, yontem, zaman_asimi):
    istek = urllib.request.Request(
        f"http://127.0.0.1:{int(port)}{_AG_SERVIS}{yontem}", data=_AG_GOVDE, method="POST",
        headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1",
                 "x-codeium-csrf-token": csrf})
    with urllib.request.urlopen(istek, timeout=zaman_asimi) as c:
        return json.loads(c.read().decode("utf-8", "replace"))


def surec_calisiyor_mu(pid):
    """pid'li süreç yaşıyor mu? True/False; bilinmiyorsa None. İstisna fırlatmaz.

    Windows'ta os.kill(pid, 0) süreci SONLANDIRIR; bu yüzden orada yalnız OpenProcess kullanılır.
    """
    try:
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return None
        if os.name == "nt":
            import ctypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.OpenProcess.restype = ctypes.c_void_p
            k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            k32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
            k32.CloseHandle.argtypes = [ctypes.c_void_p]
            tutamac = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not tutamac:
                hata = ctypes.get_last_error()
                if hata == 87:  # ERROR_INVALID_PARAMETER: böyle bir süreç yok
                    return False
                if hata == 5:  # ERROR_ACCESS_DENIED: süreç var, başka kullanıcının
                    return True
                return None
            try:
                kod = ctypes.c_uint32(0)
                if not k32.GetExitCodeProcess(tutamac, ctypes.byref(kod)):
                    return None
                return kod.value == 259  # STILL_ACTIVE
            finally:
                k32.CloseHandle(tutamac)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    except Exception:
        return None


def surec_adi(pid):
    """pid'li sürecin exe dosya adı (küçük harf); alınamazsa/Windows dışında None. İstisna yok."""
    try:
        if os.name != "nt" or isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return None
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        k32.QueryFullProcessImageNameW.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)]
        k32.QueryFullProcessImageNameW.restype = ctypes.c_int
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        tutamac = k32.OpenProcess(0x1000, False, pid)
        if not tutamac:
            return None
        try:
            tampon = ctypes.create_unicode_buffer(32768)
            boy = ctypes.c_uint32(len(tampon))
            if not k32.QueryFullProcessImageNameW(tutamac, 0, tampon, ctypes.byref(boy)):
                return None
            return os.path.basename(tampon.value[:boy.value]).lower() or None
        finally:
            k32.CloseHandle(tutamac)
    except Exception:
        return None


def antigravity_sureci_mi(pid):
    """pid canlı VE Antigravity dil sunucusu mu? Ölü/başka program False; bilinmiyorsa None."""
    canli = surec_calisiyor_mu(pid)
    if canli is not True:
        return canli
    ad = surec_adi(pid)
    if ad is None:
        return True
    return ad.startswith("language_server")


ANTIGRAVITY_EN_COK_HUB = 2


def antigravity_sorgula(zaman_asimi=ANTIGRAVITY_ZAMAN_ASIMI, hub_dosyalari=None, rpc=None,
                        surec_kontrol=None):
    """Canlı dil sunucusundan kota JSON'u döner (önce kota özeti, olmazsa GetUserStatus).

    Hub dosyaları en yeniden eskiye gezilir; pid'i ölü olanlar bağlanmadan atlanır (pid yoksa/
    bilinmiyorsa eskisi gibi denenir). Canlı hub'lardan en çok 2'si denenir. Hata: AntigravityHatasi.
    """
    rpc = rpc or _antigravity_rpc
    surec_kontrol = surec_kontrol or antigravity_sureci_mi
    dosyalar = antigravity_hub_dosyalari() if hub_dosyalari is None else hub_dosyalari
    if not dosyalar:
        raise AntigravityHatasi(dil.t("agy_hub_yok"))
    adaylar = []
    for dosya in dosyalar:
        try:
            with open(dosya, "r", encoding="utf-8") as f:
                hub = json.load(f)
            port, csrf = hub["httpPort"], hub["csrfToken"]
        except Exception:
            continue
        try:
            canli = surec_kontrol(hub.get("pid"))
        except Exception:
            canli = None
        if canli is False:
            continue
        adaylar.append((port, csrf))
        if len(adaylar) >= ANTIGRAVITY_EN_COK_HUB:
            break
    if not adaylar:
        raise AntigravityHatasi(dil.t("agy_kapali_hata"))
    son = dil.t("agy_baglanamadi")
    for port, csrf in adaylar:
        for yontem in ("RetrieveUserQuotaSummary", "GetUserStatus"):
            try:
                veri = rpc(port, csrf, yontem, zaman_asimi)
            except Exception as h:
                son = type(h).__name__
                if yontem == "RetrieveUserQuotaSummary" and not isinstance(h, OSError):
                    continue  # uç nokta yok / biçim hatası: GetUserStatus'a düş
                break  # bağlantı hatası: sonraki hub
            if isinstance(veri, dict):
                return veri
    raise AntigravityHatasi(son)


def _ag_pencere(kalan_orani, reset, grup):
    kalan = ortak.sayi(kalan_orani)
    if kalan is None:
        return None
    return {"kalan": round(max(0.0, min(100.0, kalan * 100.0)), 1),
            "resets_at": ortak.zaman_cevir(reset), "grup": grup}


def _ag_en_az(adaylar):
    """Kalanı en az olanı seçer; eşitlikte sıfırlanma zamanı bilinen kazanır."""
    adaylar = [a for a in adaylar if a]
    if not adaylar:
        return None
    return min(adaylar, key=lambda a: (a["kalan"], a["resets_at"] is None))


def _ag_grup(ad):
    return "Claude/GPT" if re.search(r"claude|gpt", ad, re.I) else "Gemini"


def antigravity_canli_pid(hub_dosyalari=None, surec_kontrol=None):
    """Antigravity şu an açık mı? Hub'ları en yeniden eskiye gezer, canlı ilk hub'ın pid'ini döner.

    Ağ yok, istisna yok; yalnız dosya okuma + süreç sorgusu. Canlı yoksa None.
    """
    try:
        surec_kontrol = surec_kontrol or antigravity_sureci_mi
        dosyalar = antigravity_hub_dosyalari() if hub_dosyalari is None else hub_dosyalari
        for dosya in dosyalar:
            try:
                with open(dosya, "r", encoding="utf-8") as f:
                    pid = json.load(f).get("pid")
                if surec_kontrol(pid) is True:
                    return pid
            except Exception:
                continue
    except Exception:
        pass
    return None


def antigravity_ayristir(veri):
    """Kota özetini (ya da GetUserStatus'u) ayrıştırır.

    Ana pencereler ("bes_saat", "haftalik") ANTIGRAVITY_ANA_GRUP'un (Gemini) değerleridir; ana
    grup o pencerede yoksa kalanı en az olan grup seçilir. Ek alanlar: "etiketler" (ana grup
    kullanılan yuvalar) ve "diger_gruplar" (ana grup dışındakilerin yalnız kalan yüzdeleri).
    """
    if not isinstance(veri, dict):
        raise AntigravityHatasi(dil.t("agy_yanit_gecersiz"))
    gruplar = {}  # grup -> {pencere: [değerler]}
    ozet = veri.get("response") if isinstance(veri.get("response"), dict) else veri
    for g in ozet.get("groups") or []:
        if not isinstance(g, dict):
            continue
        grup = _ag_grup(str(g.get("displayName") or ""))
        for b in g.get("buckets") or []:
            anahtar = _AG_PENCERE.get(str(b.get("window")).lower()) if isinstance(b, dict) else None
            if anahtar:
                gruplar.setdefault(grup, {}).setdefault(anahtar, []).append(
                    _ag_pencere(b.get("remainingFraction"), b.get("resetTime"), grup))
    if not any(x for pen in gruplar.values() for lst in pen.values() for x in lst):
        gruplar = {}  # yedek: GetUserStatus (yalnız 5 saatlik)
        kfg = (veri.get("userStatus") or {}).get("cascadeModelConfigData") or {}
        for c in kfg.get("clientModelConfigs") or []:
            k = c.get("quotaInfo") if isinstance(c, dict) else None
            if isinstance(k, dict):
                grup = _ag_grup(str(c.get("label") or c.get("modelId") or ""))
                gruplar.setdefault(grup, {}).setdefault("bes_saat", []).append(
                    _ag_pencere(k.get("remainingFraction"), k.get("resetTime"), grup))
    secilen = {g: {p: _ag_en_az(liste) for p, liste in pen.items()} for g, pen in gruplar.items()}
    alanlar, etiketler = {}, {}
    ana = secilen.get(ANTIGRAVITY_ANA_GRUP) or {}
    ag_etiket = {"bes_saat": dil.t("agy_5_saatlik"), "haftalik": dil.t("agy_haftalik")}
    for anahtar in ("bes_saat", "haftalik"):
        if ana.get(anahtar):
            alanlar[anahtar] = ana[anahtar]
            etiketler[anahtar] = f"{ag_etiket[anahtar]} · {ANTIGRAVITY_ANA_GRUP} (Neon)"
        else:
            en_az = _ag_en_az([pen.get(anahtar) for pen in secilen.values()])
            if en_az:
                alanlar[anahtar] = en_az
    if not alanlar:
        raise AntigravityHatasi(dil.t("agy_kota_yok"))
    diger = {}
    if any(ana.values()):
        for grup, pen in secilen.items():
            if grup == ANTIGRAVITY_ANA_GRUP:
                continue
            diger[grup] = {p: (pen[p]["kalan"] if pen.get(p) else None)
                           for p in ("bes_saat", "haftalik")}
    alanlar["etiketler"] = etiketler
    alanlar["diger_gruplar"] = diger
    return alanlar


# ---------------------------------------------------------------- araç başına yenileme
def yenile_claude(yol=None, sorgu=None):
    """`claude -p /usage` ile canlı okur; başarısızsa durum.json'daki mevcut veriye dokunmaz."""
    sorgu = sorgu or claude_sorgula
    try:
        alanlar = claude_ayristir(sorgu())
    except ClaudeHatasi as h:
        return False, dil.t("claude_okunamadi", detay=h)
    except Exception as h:
        return False, dil.t("claude_okunamadi", detay=type(h).__name__)
    alanlar["kaynak"] = dil.t("kaynak_otomatik_yenilendi")
    if not ortak.guncelle("claude", alanlar, yol or ortak.DURUM_DOSYASI):
        return False, dil.t("claude_yazilamadi")
    return True, dil.t("claude_yenilendi")


def yenile_antigravity(yol=None, sorgu=None):
    """Canlı Antigravity kotasını okur; başarısızsa durum.json'daki mevcut veriye dokunmaz.

    Haftalık bilgi gelmezse yalnız 5 saatlik güncellenir, haftalık mevcut değerinde kalır.
    """
    sorgu = sorgu or antigravity_sorgula
    try:
        alanlar = antigravity_ayristir(sorgu())
    except AntigravityHatasi as h:
        if any(k in str(h).lower() for k in ("kapalı", "closed")):
            return False, dil.t("agy_kapali_not")
        return False, dil.t("agy_okunamadi", detay=h)
    except Exception as h:
        return False, dil.t("agy_okunamadi", detay=type(h).__name__)
    alanlar["kaynak"] = dil.t("kaynak_otomatik_yenilendi")
    if not ortak.guncelle("antigravity", alanlar, yol or ortak.DURUM_DOSYASI):
        return False, dil.t("agy_yazilamadi")
    if "haftalik" not in alanlar:
        return True, dil.t("agy_bes_saat_yenilendi")
    return True, dil.t("agy_yenilendi")


def yenile_codex(yol=None, sorgu=None):
    """Başarılıysa durum.json'daki codex bölümünü günceller; değilse mevcut veriye dokunmaz."""
    sorgu = sorgu or codex_sorgula
    try:
        alanlar = codex_ayristir(sorgu())
    except CodexHatasi as h:
        return False, dil.t("codex_okunamadi", detay=h)
    except Exception as h:  # beklenmeyen biçim vb. - mevcut veri korunur
        return False, dil.t("codex_okunamadi", detay=type(h).__name__)
    alanlar["kaynak"] = dil.t("kaynak_otomatik_yenilendi")
    if not ortak.guncelle("codex", alanlar, yol or ortak.DURUM_DOSYASI):
        return False, dil.t("codex_yazilamadi")
    return True, dil.t("codex_yenilendi")


YENILEYICILER = {
    "claude": yenile_claude,
    "codex": yenile_codex,
    "antigravity": yenile_antigravity,
}


def yenile(arac, yol=None):
    """Tek aracı yeniler (önce bağlayıcı kayıt defteri, yoksa YENILEYICILER): (basarili, kisa_mesaj). Asla istisna fırlatmaz."""
    b = None
    try:
        import baglayicilar  # döngüsel içe aktarma olmasın diye burada
        b = baglayicilar.getir(arac)
    except Exception:
        b = None
    try:
        if b is not None:
            return b.yenile(yol)
        if arac in YENILEYICILER:
            return YENILEYICILER[arac](yol)
        return False, dil.t("hata_bilinmeyen_arac", arac=arac)
    except Exception as h:
        return False, dil.t("yenilenemedi_hata", hata=type(h).__name__)


if __name__ == "__main__":
    # Tek seferlik canlı deneme: yalnız okur ve ekrana basar, durum.json'a yazmaz.
    if len(sys.argv) > 1 and sys.argv[1] == "codex":
        print("komut:", codex_komutu())
        bas = time.time()
        try:
            ham = codex_sorgula()
            print(f"süre: {time.time() - bas:.1f} sn")
            snap = ham.get("rateLimits") if isinstance(ham, dict) else None
            print("üst alanlar:", sorted(ham.keys()) if isinstance(ham, dict) else type(ham))
            for s in ("primary", "secondary"):
                print(s, json.dumps(snap.get(s) if isinstance(snap, dict) else None))
            print("ayrıştırılan:", json.dumps(codex_ayristir(ham), ensure_ascii=False))
        except CodexHatasi as h:
            print(f"süre: {time.time() - bas:.1f} sn")
            print("HATA:", h)
    elif len(sys.argv) > 1 and sys.argv[1] == "claude":
        print("komut:", claude_komutu())
        bas = time.time()
        try:
            metin = claude_sorgula()
            print(f"süre: {time.time() - bas:.1f} sn")
            for satir in metin.splitlines():
                if satir.lower().startswith(("current session", "current week")):
                    print("ham:", satir)
            alanlar = claude_ayristir(metin)
            for anahtar, w in alanlar.items():
                r = w["resets_at"]
                print(f"{anahtar}: kalan %{w['kalan']}  resets_at {r} "
                      f"({datetime.fromtimestamp(r):%Y-%m-%d %H:%M} yerel)" if r else
                      f"{anahtar}: kalan %{w['kalan']}  resets_at ?")
            print("ayrıştırılan:", json.dumps(alanlar, ensure_ascii=False))
        except ClaudeHatasi as h:
            print(f"süre: {time.time() - bas:.1f} sn")
            print("HATA:", h)
