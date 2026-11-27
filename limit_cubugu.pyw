"""Limit Çubuğu - üst orta kamera hizası (Dinamik Ada) limit göstergesi (Claude · Codex · Antigravity).

Yalnızca standart kütüphane (tkinter) kullanır. Veri kaynağı yerel durum.json'dur.
durum.json açılışta bir kez okunur; ardından arka planda otomatik yenilenir (5 dk'da bir,
pilde 15 dk, hatada artan bekleme; LIMIT_CUBUGU_OTOMATIK=0 kapatır) veya kullanıcı
"Yenile" yaptığında güncellenir (bkz. otomatik.py, yenileyici.py).
Araçlar baglayicilar/ kayıt defterinden gelir ve kullanıcı seçimine göre gösterilir.
İlk açılışta "Araçları bağla" seçim penceresi açılır; sonra panelde sağ tıkla değiştirilebilir.
"""
import ctypes
import hashlib
import json
import math
import os
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime, timedelta

from PIL import ImageTk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baglayicilar  # noqa: E402
import dil  # noqa: E402
import durum_ortak as ortak  # noqa: E402
import gorsel_motor as gm  # noqa: E402
import ilk_kurulum  # noqa: E402
import otomatik  # noqa: E402
import secim  # noqa: E402
import yenileyici  # noqa: E402

# ---------------------------------------------------------------- tema
ARKA = gm.ZEMIN_ORTA
KART = gm.YUZEY
YAZI = gm.YAZI
SOLUK = gm.IKINCIL
ALT_YAZI = gm.IKINCIL
IZ = gm.IZ
SEFFAF = "#010203"  # pencere köşelerini şeffaf yapmak için anahtar renk

YESIL = gm.YESIL
AMBER = gm.AMBER
KIRMIZI = gm.KIRMIZI
GRI = gm.GRI


def arac_bilgi(arac):
    return secim.bilgi(arac)

OPAKLIK = 1.0
VURGU = "#38BDF8"
ADA_MS, KART_MS, DOLUM_MS = 160, 130, 200
KARE_MS = 16
ACILMA_GECIKMESI = 0.18   # sn (~180 ms)
KAPANMA_GECIKMESI = 0.50  # sn
YOKLAMA_MS = 50
MONITOR_KONTROL_SN = 2.0  # yalnız monitör düzeni; durum.json burada okunmaz
CENTIK_DONGU_SN = 5.0
CENTIK_GECIS_SN = 0.35
CENTIK_KRITIK_ESIK = 15.0
CENTIK_GECIS_KARE_SN = 1.0 / 30.0

GUNLER = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
FONT = "Segoe UI"


def ease_out(t):
    return 1 - (1 - max(0.0, min(1.0, t))) ** 3


def renk_karistir(a, b, t):
    return "#" + "".join(f"{round(int(a[i:i+2], 16) * (1-t) + int(b[i:i+2], 16) * t):02X}"
                         for i in (1, 3, 5))

# Windows SetWindowPos ve DWM yuvarlak köşe sabitleri
HWND_TOPMOST = ctypes.c_void_p(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_USTTE_BAYRAK = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2

_MUTEX_HANDLE = None
_ONE_AC_EVENT = None
_ORNEK_K32 = None


def _baslangic_sn_oku():
    ham = os.environ.get("LIMIT_CUBUGU_BASLANGIC_SN")
    if ham is None:
        return 2.0
    try:
        v = float(ham)
        return max(0.0, v) if math.isfinite(v) else 2.0
    except ValueError:
        return 2.0


def durum_rengi(kalan):
    if kalan is None:
        return GRI
    if kalan >= 50:
        return YESIL
    if kalan >= 20:
        return AMBER
    return KIRMIZI


def antigravity_etiketi(kaynak: str, bolum: dict | None) -> str:
    if not isinstance(bolum, dict):
        return kaynak
    bes = bolum.get("bes_saat")
    hft = bolum.get("haftalik")
    g5 = (bes.get("grup") if isinstance(bes, dict) else None) or None
    gh = (hft.get("grup") if isinstance(hft, dict) else None) or None
    if g5 is None and gh is None:
        return kaynak
    if g5 == gh:
        return f"{kaynak} · {g5}"
    return dil.t("agy_5s_hf_etiket", kaynak=kaynak, g5=g5 or "?", gh=gh or "?")


def sure_metni(saniye):
    saniye = max(0, int(saniye))
    gun, k = divmod(saniye, 86400)
    sa, k = divmod(k, 3600)
    dk = k // 60
    if gun:
        return dil.t("sure_g_sa", g=gun, sa=sa)
    if sa:
        return dil.t("sure_sa_dk", sa=sa, dk=dk)
    if dk:
        return dil.t("sure_dk", dk=dk)
    return dil.t("sure_az")


def kisa_sure_metni(saniye):
    """Çentik mini özeti için kompakt kalan süre (ör. 6dk, 2sa, 3g)."""
    saniye = max(0, int(saniye))
    gun, k = divmod(saniye, 86400)
    sa, k = divmod(k, 3600)
    dk = k // 60
    if gun:
        return dil.t("ksure_g", g=gun)
    if sa:
        return dil.t("ksure_sa", sa=sa)
    if dk:
        return dil.t("ksure_dk", dk=dk)
    return dil.t("ksure_az")


def _win32_tus_basili(vk):
    try:
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
    except Exception:
        return False


def once_metni(epoch, simdi):
    if not epoch:
        return dil.t("once_hic")
    fark = max(0, simdi - epoch)
    if fark < 45:
        return dil.t("once_az_once")
    if fark < 3600:
        return dil.t("once_dk", n=int(fark // 60) or 1)
    if fark < 86400:
        return dil.t("once_sa", n=int(fark // 3600))
    return dil.t("once_g", n=int(fark // 86400))


def tarih_metni(epoch):
    d = datetime.fromtimestamp(epoch)
    bugun = datetime.now().date()
    if d.date() == bugun:
        gun = dil.t("bugun")
    elif d.date() == bugun + timedelta(days=1):
        gun = dil.t("yarin")
    else:
        gun = f"{dil.t(f'gun_{d.weekday()}')} {d.day:02d}.{d.month:02d}"
    return f"{gun} {d.hour:02d}:{d.minute:02d}"


def yuvarlak_dikdortgen(c, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    n = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
         x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(n, smooth=True, splinesteps=24, **kw)


def geometri_metni(g, y, x, yy):
    """Tcl/Tk geometry dizgisi.

    Tk'de '+' sol/üst kenardan uzaklık, '-' ise sağ/alt kenardan uzaklık demektir.
    Negatif sanal ekran koordinatlarında (ör. sol monitör X=-1142) '+-1142+0' gerekir.
    """
    return f"{int(g)}x{int(y)}+{int(x)}+{int(yy)}"


def dpi_farkindaligi():
    """Monitör başına DPI farkındalığı: tüm koordinatlar fiziksel piksel olur."""
    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class _MonitorBilgiEx(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", ctypes.c_long * 4),
        ("rcWork", ctypes.c_long * 4),
        ("dwFlags", ctypes.c_ulong),
        ("szDevice", ctypes.c_wchar * 32),
    ]


def monitorleri_listele(kok=None):
    """Tüm bağlı monitörleri listeler (birincil monitör her zaman ilk sırada)."""
    sonuc = []
    try:
        u32 = ctypes.windll.user32
        u32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MonitorBilgiEx)]
        u32.GetMonitorInfoW.restype = ctypes.c_int
        cb_tur = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_void_p, ctypes.c_void_p)

        def cb(hmon, _hdc, _rc, _lp):
            mi = _MonitorBilgiEx()
            mi.cbSize = ctypes.sizeof(_MonitorBilgiEx)
            if u32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                ad = mi.szDevice or f"DISPLAY{len(sonuc) + 1}"
                kisa = ad.split("\\")[-1] or ad
                sonuc.append({
                    "ad": ad,
                    "kisa_ad": kisa,
                    "birincil": bool(mi.dwFlags & 1),
                    "ekran": tuple(mi.rcMonitor),
                    "calisma": tuple(mi.rcWork),
                })
            return 1

        u32.EnumDisplayMonitors.argtypes = [ctypes.c_void_p, ctypes.c_void_p, cb_tur, ctypes.c_void_p]
        u32.EnumDisplayMonitors.restype = ctypes.c_int
        u32.EnumDisplayMonitors(None, None, cb_tur(cb), None)
    except Exception:
        sonuc = []

    if sonuc:
        # Birincil monitör başa, ardından soldan sağa deterministik sıra
        sonuc.sort(key=lambda m: (not m["birincil"], m["ekran"][0], m["ekran"][1], m["kisa_ad"]))
        return sonuc

    if kok is not None:
        g, y = kok.winfo_screenwidth(), kok.winfo_screenheight()
    else:
        g, y = 1920, 1080
    return [{
        "ad": "\\\\.\\DISPLAY1",
        "kisa_ad": "DISPLAY1",
        "birincil": True,
        "ekran": (0, 0, g, y),
        "calisma": (0, 0, g, y),
    }]


GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
SW_HIDE = 0
SW_SHOWNA = 8


def gorev_cubugundan_gizle(w):
    """Pencereyi görev çubuğundan ve Alt+Tab'dan gizler (WS_EX_TOOLWINDOW ekler, WS_EX_APPWINDOW kaldırır).

    Tk, overrideredirect pencereyi yeniden gösterirken/odaklarken APPWINDOW'u geri getirip görev çubuğu
    düğmesi açabildiği için her gösterimde yeniden uygulanır. Windows dışında etkisizdir.
    Stil değiştiyse True döner."""
    if sys.platform != "win32":
        return False
    try:
        if not w.winfo_exists():
            return False
        wid = w.winfo_id()
        if not wid:
            return False
        u32 = ctypes.windll.user32
        u32.GetParent.argtypes = [ctypes.c_void_p]
        u32.GetParent.restype = ctypes.c_void_p
        u32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        u32.GetWindowLongW.restype = ctypes.c_long
        u32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
        u32.SetWindowLongW.restype = ctypes.c_long
        u32.IsWindowVisible.argtypes = [ctypes.c_void_p]
        u32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        u32.SetWindowPos.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_uint,
        ]
        hwnd = u32.GetParent(ctypes.c_void_p(wid)) or ctypes.c_void_p(wid)
        eski = u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        yeni = (eski | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        if yeni == eski:
            return False
        gorunur = bool(u32.IsWindowVisible(hwnd))
        if gorunur:
            u32.ShowWindow(hwnd, SW_HIDE)  # görev çubuğu düğmesi ancak gizle/göster ile güncellenir
        u32.SetWindowLongW(hwnd, GWL_EXSTYLE, yeni)
        u32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                         SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        if gorunur:
            u32.ShowWindow(hwnd, SW_SHOWNA)
        return True
    except Exception:
        return False


def en_uste_al(w):
    """Windows SetWindowPos ile pencerenin gerçekten en üstte kalmasını garantiler."""
    try:
        if not w.winfo_exists():
            return False
        wid = w.winfo_id()
        if not wid:
            return False
        u32 = ctypes.windll.user32
        u32.GetParent.argtypes = [ctypes.c_void_p]
        u32.GetParent.restype = ctypes.c_void_p
        u32.SetWindowPos.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_uint,
        ]
        u32.SetWindowPos.restype = ctypes.c_int
        hwnd = u32.GetParent(ctypes.c_void_p(wid)) or ctypes.c_void_p(wid)
        gorev_cubugundan_gizle(w)
        return bool(u32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_USTTE_BAYRAK))
    except Exception:
        return False


def dwm_yuvarlak_kose(w, tercih=DWMWCP_ROUND):
    """Windows 11 DWM yuvarlak pencere köşelerini etkinleştirir (desteklenmezse sessizce geçer)."""
    try:
        if not w.winfo_exists():
            return False
        wid = w.winfo_id()
        if not wid:
            return False
        u32 = ctypes.windll.user32
        u32.GetParent.argtypes = [ctypes.c_void_p]
        u32.GetParent.restype = ctypes.c_void_p
        hwnd = u32.GetParent(ctypes.c_void_p(wid)) or ctypes.c_void_p(wid)
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
        ]
        dwm.DwmSetWindowAttribute.restype = ctypes.c_long
        val = ctypes.c_int(int(tercih))
        hr = dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(val), ctypes.sizeof(val)
        )
        return hr == 0
    except Exception:
        return False


def _ornek_adi():
    """Test verisi kullanan süreçleri gerçek uygulamadan ayırır."""
    ad = os.environ.get("LIMIT_CUBUGU_ORNEK_ADI")
    if ad:
        return "Local\\" + ad
    yol = os.environ.get("LIMIT_CUBUGU_DOSYA")
    ek = ""
    if yol:
        yol = os.path.normcase(os.path.abspath(yol))
        ek = "_" + hashlib.sha256(yol.encode("utf-8")).hexdigest()[:24]
    return "Local\\LimitCubuguTekOrnek" + ek


def tek_ornek_temizle():
    """Yalnız bu sürecin tuttuğu event ve mutex handle'larını kapatır."""
    global _MUTEX_HANDLE, _ONE_AC_EVENT, _ORNEK_K32
    if _ORNEK_K32 is not None:
        for h in (_ONE_AC_EVENT, _MUTEX_HANDLE):
            if h:
                _ORNEK_K32.CloseHandle(h)
    _ONE_AC_EVENT = _MUTEX_HANDLE = _ORNEK_K32 = None


def one_ac_istendi():
    """Otomatik sıfırlanan event'i beklemeden tüketir; Tk ana döngüsünde çağrılır."""
    return bool(_ONE_AC_EVENT and _ORNEK_K32.WaitForSingleObject(_ONE_AC_EVENT, 0) == 0)


def tek_ornek():
    """İkinci kopya mevcut örneğe paneli aç sinyali gönderip çıkar."""
    global _MUTEX_HANDLE, _ONE_AC_EVENT, _ORNEK_K32
    if _MUTEX_HANDLE:
        return True
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        k32.CreateMutexW.restype = ctypes.c_void_p
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.CloseHandle.restype = ctypes.c_int
        k32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
        k32.CreateEventW.restype = ctypes.c_void_p
        k32.SetEvent.argtypes = [ctypes.c_void_p]
        k32.SetEvent.restype = ctypes.c_int
        k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.WaitForSingleObject.restype = ctypes.c_uint32
        _ORNEK_K32 = k32
        ad = _ornek_adi()
        # Mutex görünür olmadan event hazırdır; erken ikinci başlatma kaybolmaz.
        _ONE_AC_EVENT = k32.CreateEventW(None, False, False, ad + "OneAc")
        if not _ONE_AC_EVENT:
            raise ctypes.WinError(ctypes.get_last_error())
        h = k32.CreateMutexW(None, False, ad)
        err = ctypes.get_last_error()
        _MUTEX_HANDLE = h
        if not h:
            raise ctypes.WinError(err)
        if err == 183:  # ERROR_ALREADY_EXISTS
            k32.SetEvent(_ONE_AC_EVENT)
            tek_ornek_temizle()
            return False
        return True
    except Exception:
        tek_ornek_temizle()
        return True


# ================================================================ uygulama
class LimitCubugu:
    def __init__(self, kok, baslangic_sn=None, araclar=None):
        self.kok = kok
        self.olcek = max(1.0, kok.winfo_fpixels("1i") / 96.0)
        o = self.olcek

        # Canlı mini özetin rahat sığması için genişletilmiş yatay çentik (~168x24 px).
        self.centik_g = int(168 * o)
        self.centik_y = int(24 * o)

        self.araclar = list(araclar) if araclar else secim.etkin_kimlikler(ortak.oku())
        if not self.araclar:
            self.araclar = list(ortak.ARACLAR)

        self._panel_olcu_hesapla()

        # Detay kartı boyutları
        self.kart_g, self.kart_y = int(368 * o), int(356 * o)
        self._ada_deger = 0.0
        self._ada_bas = None
        self._kart_bas = None
        self._dolum_bas = None
        self._dolum = 1.0
        self._hover_arac = None
        self._hover_dugme = None
        self._kart_hover_dugme = None
        self._animasyon_id = None
        self._son_nefes = None
        self._hareket_saati = time.perf_counter()
        self._centik_dongu_bas = None
        self._centik_son_adim = None
        self._centik_aktif_arac = None
        self._centik_son_etiket = None
        self._centik_son_renk = None
        self._centik_gecis_bas = None
        self._centik_gecis_onceki_metin = None
        self._centik_gecis_onceki_renk = None
        self._son_gecis_cizim = 0.0
        self._centik_dongu_var = None
        self._panel_hitboxes = {}
        self._kart_hitboxes = {}
        self._panel_foto = None
        self._panel_img_id = None
        self._kart_foto = None
        self._kart_img_id = None
        self._bildirim_foto = None
        self._bildirim_img_id = None
        self._son_centik_img = None
        self._son_panel_img = None
        self._son_kart_img = None
        self._son_bildirim_img = None

        self.durum = ortak.oku()  # açılışta bir kez; sonrası Yenile (elle/otomatik)
        self.son_monitor_kontrol = 0.0

        # Bildirim (toast), yeşil yenilenme parlaması ve az-limit uyarı takibi
        self._parlama_bitis = 0.0
        self._bildirim_bitis = 0.0
        self._bildirim_metin = ""
        self._bildirim_renk = YESIL
        self._centik_vurgu = VURGU
        self._onceki_durum = self._durum_anlik_al(time.time())
        self._az_uyarildi = set()

        # Global klavye kısayolu (Alt + X) kenar tetiklemesi
        self._tus_basili_fn = _win32_tus_basili
        self._kisayol_onceki = False
        self._kisayol_aktif = os.environ.get("LIMIT_CUBUGU_KISAYOL", "1") != "0"

        # Yenileme durumu (iş parçacığı sonuçları kuyruktan ana döngüde alınır)
        self.yenile_fn = yenileyici.yenile
        self.yenileniyor = set()
        self.yenileme_notu = {}
        self._yenileme_kuyrugu = queue.Queue()
        self.otomatik = otomatik.OtomatikPlan()
        self._otomatik_baslangic = time.time()
        self.otomatik_acik = os.environ.get("LIMIT_CUBUGU_OTOMATIK", "1") != "0"
        self._ag_son_pid = None
        self._ag_son_kontrol = 0.0
        self._ag_son_okuma = 0.0

        self.monitorler = monitorleri_listele(kok)
        self.secili_monitor = self._monitor_sec(self.durum.get("monitor"))

        self.acik = False
        self.sabit = False
        self.uzerinde_bas = None
        self.ayrilma_bas = None
        self.kart_arac = None
        self._secim_acik = False

        bas_sn = _baslangic_sn_oku() if baslangic_sn is None else max(0.0, float(baslangic_sn))
        self._baslangic_bitis = (time.time() + bas_sn) if bas_sn > 0 else 0.0

        self._pencere_kur(kok)
        self.kart = tk.Toplevel(kok)
        self._pencere_kur(self.kart)
        self.kart.withdraw()
        self.kart_tuval = tk.Canvas(self.kart, bg=SEFFAF, highlightthickness=0, bd=0)
        self.kart_tuval.pack(fill="both", expand=True)
        self.kart_tuval.bind("<Button-1>", self._kart_tik)

        self.bildirim = tk.Toplevel(kok)
        self._pencere_kur(self.bildirim)
        self.bildirim.withdraw()
        self.bildirim_tuval = tk.Canvas(self.bildirim, bg=SEFFAF, highlightthickness=0, bd=0)
        self.bildirim_tuval.pack(fill="both", expand=True)

        self.tuval = tk.Canvas(kok, bg=SEFFAF, highlightthickness=0, bd=0)
        self.tuval.pack(fill="both", expand=True)
        self.tuval.bind("<Button-1>", self._panel_tik)
        self.tuval.bind("<Button-3>", self._sag_tik)

        if self._baslangic_bitis > 0:
            self.ac()
        else:
            self._kapat_gorunum()

        self.kok.after(60, lambda: (en_uste_al(self.kok), dwm_yuvarlak_kose(self.kok)))
        self._yokla()
        self._saniyelik()
        self.kok.bind("<Destroy>", self._animasyon_durdur, add="+")
        self._animasyon_adim()

    def _panel_olcu_hesapla(self):
        o = self.olcek
        # Açık yatay kapsül boyutları
        self.panel_sol = int(12 * o)
        self.simge_adim = int(76 * o)
        self.ayrac_g = int(12 * o)
        self.dugme_adim = int(42 * o)
        self.panel_sag = int(10 * o)
        self.panel_g = (
            self.panel_sol
            + self.simge_adim * len(self.araclar)
            + self.ayrac_g
            + self.dugme_adim * 4
            + self.panel_sag
        )
        self.panel_y = int(86 * o)

    def _tuvale_gorsel_koy(self, tuval, attr_foto, attr_id, pil_img):
        """3× supersampled PIL görselini titreşimsiz ve bellek sızıntısız Tk tuvaline yazar."""
        foto = ImageTk.PhotoImage(pil_img)
        setattr(self, attr_foto, foto)
        img_id = getattr(self, attr_id, None)
        if img_id is not None and tuval.find_withtag(img_id):
            tuval.itemconfigure(img_id, image=foto)
        else:
            tuval.delete("all")
            img_id = tuval.create_image(0, 0, anchor="nw", image=foto, tags="gorsel")
            setattr(self, attr_id, img_id)

    def _animasyon_durdur(self, e):
        if e.widget is self.kok and self._animasyon_id is not None:
            self.kok.after_cancel(self._animasyon_id)
            self._animasyon_id = None

    def _ada_baslat(self, hedef):
        self._ada_ilk = self._ada_deger
        self._ada_hedef = hedef
        self._ada_bas = time.perf_counter()
        self._ada_ciz()

    def _ada_ciz(self):
        t = self._ada_deger
        g = round(self.centik_g + (self.panel_g - self.centik_g) * t)
        y = round(self.centik_y + (self.panel_y - self.centik_y) * t)
        self._konumla(g, y)
        self.tuval.config(width=g, height=y)
        if self._ada_bas is None:
            self._yeniden_ciz()
            return
        # Geçişte 3× pürüzsüz tek kabuk çizilir; yazılar dar alanda üst üste binmez.
        img = gm.gecis_gorseli(g, y, vurgu_renk=self._centik_vurgu)
        self._tuvale_gorsel_koy(self.tuval, "_panel_foto", "_panel_img_id", img)

    def _dolum_baslat(self):
        self._dolum_bas = time.perf_counter()
        self._dolum = 0.0

    def _animasyon_adim(self):
        self._animasyon_id = None
        simdi = time.perf_counter()
        self._hareket_saati = simdi
        if self._ada_bas is not None:
            t = (simdi - self._ada_bas) * 1000 / ADA_MS
            self._ada_deger = self._ada_ilk + (self._ada_hedef - self._ada_ilk) * ease_out(t)
            if t >= 1:
                self._ada_bas = None
            self._ada_ciz()
        elif self.yenileniyor:
            self._yeniden_ciz()
        elif not self.acik:
            dongu_tetik = self._centik_dongu_adim_degisti(simdi)
            gecis_suruyor = self._centik_gecis_bas is not None
            if dongu_tetik:
                self._son_gecis_cizim = simdi
                self._centik_ciz(saat=simdi)
            elif gecis_suruyor:
                if (simdi - self._son_gecis_cizim >= CENTIK_GECIS_KARE_SN
                        or (simdi - self._centik_gecis_bas) >= CENTIK_GECIS_SN):
                    self._son_gecis_cizim = simdi
                    self._centik_ciz(saat=simdi)
            else:
                # Yavaş nefes (veya yenilenme sonrası ~3 sn yumuşak yeşil parlama)
                parliyor = time.time() < self._parlama_bitis
                periyot = 1.2 if parliyor else 4.0
                nefes_adim = round((1.0 + math.sin(simdi * math.tau / periyot)) / 2.0, 2)
                if nefes_adim != self._son_nefes:
                    self._son_nefes = nefes_adim
                    self._centik_ciz(saat=simdi)
        if self.kart_arac:
            if self._kart_bas is not None:
                t = (simdi - self._kart_bas) * 1000 / KART_MS
                e = ease_out(t)
                x, y = self._kart_hedef
                self.kart.attributes("-alpha", OPAKLIK * e)
                self.kart.geometry(geometri_metni(self.kart_g, self.kart_y, x,
                                                  y - round(6*self.olcek*(1-e))))
                if t >= 1:
                    self._kart_bas = None
            if self._dolum_bas is not None:
                t = (simdi - self._dolum_bas) * 1000 / DOLUM_MS
                self._dolum = ease_out(t)
                if t >= 1:
                    self._dolum_bas = None
                self._kart_ciz(self.kart_arac)
        self._animasyon_id = self.kok.after(KARE_MS, self._animasyon_adim)

    def _tarama_ciz(self, c, g):
        o = self.olcek
        sol, sag = 18*o, g-18*o
        uzunluk = 62*o
        merkez = sol + ((self._hareket_saati / 1.15) % 1) * (sag-sol)
        for i in range(12):
            x1 = max(sol, merkez - uzunluk/2 + i*uzunluk/12)
            x2 = min(sag, merkez - uzunluk/2 + (i+1)*uzunluk/12)
            if x2 > x1:
                c.create_line(x1, 2*o, x2, 2*o,
                              fill=renk_karistir("#2563EB", "#BAE6FD", 1-abs(i-5.5)/6),
                              width=3*o, tags="tarama")

    def _donen_yenile(self, c, x, y, r):
        c.create_text(x, y, text="↻", fill=VURGU, font=(FONT, round(r/self.olcek*2), "bold"),
                      angle=(-self._hareket_saati*360/0.9) % 360, tags="donen_yenile")

    # ------------------------------------------------------------ pencere & monitör
    @staticmethod
    def _pencere_kur(w):
        w.overrideredirect(True)  # kenarlıksız
        # overrideredirect tek başına görev çubuğu düğmesini engellemez (tıklama/odakta Tk APPWINDOW'u
        # geri getirir): TOOLWINDOW stilini şimdi ve her gösterimde (<Map>) uygula.
        gorev_cubugundan_gizle(w)
        w.bind("<Map>", lambda e, p=w: gorev_cubugundan_gizle(p) if e.widget is p else None, add="+")
        w.attributes("-topmost", True)
        w.attributes("-alpha", OPAKLIK)
        w.configure(bg=SEFFAF)
        try:
            w.attributes("-transparentcolor", SEFFAF)
        except tk.TclError:
            pass

    def _monitor_sec(self, tercih=None):
        """Tercih edilen monitörü bulur; yoksa birincil monitörü döner."""
        if not self.monitorler:
            self.monitorler = monitorleri_listele(self.kok)
        if tercih:
            hedef = str(tercih).strip().lower()
            for m in self.monitorler:
                if m["ad"].lower() == hedef or m["kisa_ad"].lower() == hedef:
                    return m
        for m in self.monitorler:
            if m["birincil"]:
                return m
        return self.monitorler[0]

    def _monitorleri_tazele(self):
        """Monitör listesini günceller; aktif monitör değiştiyse veya söküldüyse True döner."""
        eski = self.secili_monitor
        yeni_liste = monitorleri_listele(self.kok)
        self.monitorler = yeni_liste
        hedef_ad = eski["kisa_ad"] if eski else self.durum.get("monitor")
        yeni = self._monitor_sec(hedef_ad)
        self.secili_monitor = yeni
        return (
            eski is None
            or eski["kisa_ad"] != yeni["kisa_ad"]
            or eski["ekran"] != yeni["ekran"]
            or eski["calisma"] != yeni["calisma"]
        )

    def _ekran_alani(self):
        """Aktif monitörün tam ekran sınırı: (sol, üst, sağ, alt)."""
        return self.secili_monitor["ekran"]

    def _calisma_alani(self):
        """Aktif monitörün çalışma alanı (görev çubuğu hariç): (sol, üst, sağ, alt)."""
        return self.secili_monitor["calisma"]

    def _konumla(self, g, y):
        """Pencereyi seçili monitörün en üst ortasına yerleştirir."""
        sol, ust, sag, _alt = self._ekran_alani()
        x = sol + (sag - sol - g) // 2
        yy = ust
        self.kok.geometry(geometri_metni(g, y, x, yy))
        self.kok.update_idletasks()
        return x, yy

    def ekran_degistir(self):
        """Sıradaki monitöre geçer, seçimi durum.json'a kaydeder ve yeniden konumlanır."""
        self.monitorler = monitorleri_listele(self.kok)
        if len(self.monitorler) > 1:
            mevcut_ad = self.secili_monitor["kisa_ad"].lower()
            indeks = 0
            for i, m in enumerate(self.monitorler):
                if m["kisa_ad"].lower() == mevcut_ad:
                    indeks = i
                    break
            self.secili_monitor = self.monitorler[(indeks + 1) % len(self.monitorler)]
        else:
            self.secili_monitor = self.monitorler[0]

        ortak.ayar_guncelle({"monitor": self.secili_monitor["kisa_ad"]})
        self.durum["monitor"] = self.secili_monitor["kisa_ad"]

        self.kart_gizle()
        self.ayrilma_bas = None
        if self.acik:
            self._konumla(self.panel_g, self.panel_y)
            self._panel_ciz()
        else:
            self._kapat_gorunum()
        en_uste_al(self.kok)
        return self.secili_monitor["kisa_ad"]

    def araclari_degistir(self, kimlikler):
        """Gösterilen araç listesini canlı günceller, paneli yeniden ölçüp çizer."""
        yeni = list(kimlikler or ())
        if not yeni or yeni == self.araclar:
            return False
        self.araclar = yeni
        self._panel_olcu_hesapla()
        self._hover_arac = None
        self._hover_dugme = None
        self._kart_hover_dugme = None
        self._panel_hitboxes = {}
        self._kart_hitboxes = {}
        self._ada_bas = None
        self._ada_deger = 1.0 if self.acik else 0.0
        self._centik_dongu_sifirla()
        if self.kart_arac and self.kart_arac not in self.araclar:
            self.kart_gizle()
        if self.acik:
            self._konumla(self.panel_g, self.panel_y)
            self.tuval.config(width=self.panel_g, height=self.panel_y)
            self._panel_ciz()
            if self.kart_arac:
                self.kart_goster(self.kart_arac)
        else:
            self._kapat_gorunum()
        en_uste_al(self.kok)
        return True

    def _alan(self, w):
        try:
            if not w.winfo_viewable():
                return None
            return (w.winfo_rootx(), w.winfo_rooty(),
                    w.winfo_rootx() + w.winfo_width(), w.winfo_rooty() + w.winfo_height())
        except tk.TclError:
            return None

    @staticmethod
    def _icinde(alan, x, y, pay=0):
        return bool(alan) and alan[0] - pay <= x < alan[2] + pay and alan[1] - pay <= y < alan[3] + pay

    # ------------------------------------------------------------ veri & yenileme
    def yenile(self, araclar=None):
        """Seçilen araçları arka plan iş parçacıklarında yeniler.

        Araçlar aynı anda okunur, sonucu hazır olan hemen işlenir.
        Elle veya otomatik planla çağrılır (5 dk'da bir, pilde 15 dk, hatada artan
        bekleme; LIMIT_CUBUGU_OTOMATIK=0 kapatır).
        """
        hedef = self.araclar if araclar is None else araclar
        araclar = [a for a in hedef if a not in self.yenileniyor]
        if not araclar:
            return False
        self.yenileniyor.update(araclar)
        for a in araclar:
            self.otomatik.basladi(a)
            self.yenileme_notu[a] = (dil.t("yenileniyor_ucnokta"), SOLUK)
        fn, kuyruk = self.yenile_fn, self._yenileme_kuyrugu

        def tek(a):
            try:
                sonuc = fn(a)
            except Exception as h:
                sonuc = (False, dil.t("yenilenemedi_hata", hata=type(h).__name__))
            if not (isinstance(sonuc, tuple) and len(sonuc) == 2):
                sonuc = (False, dil.t("yenilenemedi_gecersiz"))
            kuyruk.put((a, sonuc))

        for a in araclar:
            threading.Thread(target=tek, args=(a,), daemon=True).start()
        self._yeniden_ciz()
        return True

    def _yenileme_sonuclarini_al(self):
        geldi = []
        while True:
            try:
                arac, (basarili, mesaj) = self._yenileme_kuyrugu.get_nowait()
            except queue.Empty:
                break
            geldi.append(arac)
            self.yenileniyor.discard(arac)
            self.otomatik.sonuc_bildir(arac, basarili)
            self.yenileme_notu[arac] = (mesaj, YESIL if basarili else AMBER)
        if geldi:
            self.durum = ortak.oku()
            self._bildirim_kontrol(time.time(), az_kontrol_araclar=geldi)
            if self.kart_arac:
                self._dolum_baslat()
        return bool(geldi)

    def _otomatik_kontrol(self):
        try:
            if not self.otomatik_acik:
                return
            if time.time() - self._otomatik_baslangic < 60:
                return
            if self.yenileniyor:
                return
            vade = self.otomatik.vadesi_gelenler(list(self.araclar))
            if vade:
                self.yenile([vade[0]])
        except Exception:
            pass

    def _antigravity_izle(self, simdi=None):
        try:
            if not self.otomatik_acik:
                return
            if "antigravity" not in self.araclar or "antigravity" in self.yenileniyor:
                return
            if simdi is None:
                simdi = time.time()
            if simdi - self._ag_son_kontrol < 5.0:
                return
            self._ag_son_kontrol = simdi
            pid_fn = getattr(yenileyici, "antigravity_canli_pid", None)
            if callable(pid_fn):
                try:
                    pid = pid_fn()
                except Exception:
                    pid = None
            else:
                pid = None
            if pid is None:
                self._ag_son_pid = None
                return
            if pid != self._ag_son_pid or (simdi - self._ag_son_okuma >= 60.0):
                self._ag_son_pid = pid
                self._ag_son_okuma = simdi
                self.yenile(["antigravity"])
        except Exception:
            pass

    # ------------------------------------------------------------ bildirim & kısayol
    def _durum_anlik_al(self, simdi):
        anlik = {}
        for a in self.araclar:
            bolum = self.durum.get(a)
            for p in ortak.PENCERELER:
                anlik[(a, p)] = ortak.pencere_durumu(bolum, p, simdi)
        return anlik

    def _bildirim_kontrol(self, simdi, az_kontrol_araclar=None):
        """Süresi dolup %100'e dönen araçlarda yeşil bildirim, <=%15 için tekil amber uyarı gösterir."""
        yeni = self._durum_anlik_al(simdi)
        yenilenenler = []
        for a in self.araclar:
            for p in ortak.PENCERELER:
                eski = self._onceki_durum.get((a, p))
                kalan, reset, yenilendi = yeni[(a, p)]
                if (eski is not None and eski[0] is not None and eski[0] < 100.0
                        and not eski[2] and yenilendi):
                    if a not in yenilenenler:
                        yenilenenler.append(a)
        self._onceki_durum = yeni

        if yenilenenler:
            adlar = ", ".join(arac_bilgi(a)["ad"] for a in yenilenenler)
            self._parlama_bitis = simdi + 3.0
            self.bildirim_goster(dil.t("bildirim_yenilendi", adlar=adlar), YESIL, sure_sn=4.0)
            return

        if not az_kontrol_araclar:
            return
        for a in az_kontrol_araclar:
            dusuk = None
            for p in ortak.PENCERELER:
                kalan, reset, yenilendi = yeni.get((a, p), (None, None, False))
                if kalan is not None and not yenilendi and kalan <= 15.0:
                    if dusuk is None or kalan < dusuk[0]:
                        dusuk = (kalan, reset)
            if dusuk is not None:
                anahtar = (a, round(dusuk[0], 1), dusuk[1])
                if anahtar not in self._az_uyarildi:
                    self._az_uyarildi.add(anahtar)
                    self.bildirim_goster(
                        dil.t("bildirim_azaldi", ad=arac_bilgi(a)["ad"], yuzde=f"{dusuk[0]:.0f}"),
                        AMBER,
                        sure_sn=4.0,
                    )
                    break
            else:
                self._az_uyarildi = {k for k in self._az_uyarildi if k[0] != a}

    def bildirim_goster(self, metin, renk=YESIL, sure_sn=4.0):
        """Üst çentiğin hemen altında odak çalmayan 3× pürüzsüz yüzer bildirim (toast) gösterir."""
        o = self.olcek
        self._bildirim_metin = metin
        self._bildirim_renk = renk
        self._bildirim_bitis = time.time() + max(0.2, float(sure_sn))

        gen, yuk = gm.toast_boyut_hesapla(metin, o)
        img = gm.toast_gorseli(gen, yuk, metin, vurgu_renk=renk)
        self._son_bildirim_img = img

        sol, ust, sag, _ = self._ekran_alani()
        c_sol, c_ust, c_sag, c_alt = self._calisma_alani()
        pay = int(8 * o)
        x = sol + (sag - sol - gen) // 2
        ust_yuk = self.panel_y if self.acik else self.centik_y
        y = ust + ust_yuk + pay
        x = max(c_sol + pay, min(x, c_sag - gen - pay))
        y = max(c_ust + pay, min(y, c_alt - yuk - pay))

        self.bildirim.geometry(geometri_metni(gen, yuk, x, y))
        self.bildirim_tuval.config(width=gen, height=yuk)
        self._tuvale_gorsel_koy(self.bildirim_tuval, "_bildirim_foto", "_bildirim_img_id", img)
        self.bildirim.deiconify()
        self.bildirim.lift()
        self.bildirim.update_idletasks()
        dwm_yuvarlak_kose(self.bildirim)
        en_uste_al(self.bildirim)

    def bildirim_gizle(self):
        self._bildirim_bitis = 0.0
        try:
            if self.bildirim.winfo_exists():
                self.bildirim.withdraw()
        except tk.TclError:
            pass

    def panel_degistir(self):
        """Paneli açar (kısa görünürlük payıyla) veya zaten açıksa kapatır (Alt + X)."""
        if self.acik:
            self.kapat()
        else:
            self._baslangic_bitis = time.time() + 3.0
            self.ac()

    def _kisayol_kontrol(self):
        """Global Alt + X kısayolu için kenar tetiklemeli güvenli kontrol."""
        if not self._kisayol_aktif:
            return
        try:
            alt = bool(self._tus_basili_fn(0x12))    # VK_MENU
            x_tusu = bool(self._tus_basili_fn(0x58))  # VK_X
            ctrl = bool(self._tus_basili_fn(0x11))   # VK_CONTROL
            aktif = alt and x_tusu and not ctrl
        except Exception:
            aktif = False
        if aktif and not self._kisayol_onceki:
            self.panel_degistir()
        self._kisayol_onceki = aktif

    def _one_ac_kontrol(self):
        if one_ac_istendi():
            self._baslangic_bitis = time.time() + 3.0
            self.ayrilma_bas = None
            self.ac()
            self.kok.deiconify()
            self.kok.attributes("-topmost", True)
            self.kok.lift()
            en_uste_al(self.kok)

    def _arac_ozeti(self, arac, simdi):
        bolum = self.durum.get(arac)
        bes = ortak.pencere_durumu(bolum, "bes_saat", simdi)
        hft = ortak.pencere_durumu(bolum, "haftalik", simdi)
        kaynak = bolum.get("kaynak") if isinstance(bolum, dict) else None
        guncel = ortak.sayi(bolum.get("guncellendi")) if isinstance(bolum, dict) else None
        return bes, hft, kaynak, guncel

    def _en_kotu(self, simdi):
        degerler = []
        for a in self.araclar:
            bes, hft, _, _ = self._arac_ozeti(a, simdi)
            degerler += [v for v in (bes[0], hft[0]) if v is not None]
        return min(degerler) if degerler else None

    # ------------------------------------------------------------ durum makinesi
    def _yokla(self):
        try:
            self._yokla_adim()
        finally:
            self.kok.after(YOKLAMA_MS, self._yokla)

    def _yokla_adim(self):
        simdi = time.time()
        self._one_ac_kontrol()
        self._kisayol_kontrol()
        if self._bildirim_bitis > 0 and simdi >= self._bildirim_bitis:
            self.bildirim_gizle()
        degisti = self._yenileme_sonuclarini_al()
        if simdi - self.son_monitor_kontrol >= MONITOR_KONTROL_SN:
            self.son_monitor_kontrol = simdi
            if self._monitorleri_tazele():
                if self.acik:
                    self._konumla(self.panel_g, self.panel_y)
                    if self.kart_arac:
                        self.kart_goster(self.kart_arac)
                else:
                    self._konumla(self.centik_g, self.centik_y)
                degisti = True
        if degisti:
            self._yeniden_ciz()

        px, py = self.kok.winfo_pointerxy()
        panel = self._alan(self.kok)

        if not self.acik:
            if self._icinde(panel, px, py, pay=int(3 * self.olcek)):
                if self.uzerinde_bas is None:
                    self.uzerinde_bas = simdi
                elif simdi - self.uzerinde_bas >= ACILMA_GECIKMESI:
                    self.ac()
            else:
                self.uzerinde_bas = None
            return

        if self._ada_bas is not None:
            return

        kart = self._alan(self.kart)
        panelde = self._icinde(panel, px, py, pay=int(2 * self.olcek))
        kartta = self._icinde(kart, px, py, pay=int(4 * self.olcek))

        if panelde:
            lx, ly = px - panel[0], py - panel[1]
            arac = self._simge_altinda(lx, ly)
            dugme = self._dugme_altinda(lx, ly)
            if arac and arac != self.kart_arac:
                self.kart_goster(arac)
        else:
            arac = None
            dugme = None
        if arac != self._hover_arac or dugme != self._hover_dugme:
            self._hover_arac = arac
            self._hover_dugme = dugme
            self._panel_ciz()

        if kartta and self.kart_arac:
            k_dugme = self._kart_dugme_altinda(px - kart[0], py - kart[1])
        else:
            k_dugme = None
        if k_dugme != self._kart_hover_dugme:
            self._kart_hover_dugme = k_dugme
            if self.kart_arac:
                self._kart_ciz(self.kart_arac)

        if panelde or kartta or self._secim_acik:
            self.ayrilma_bas = None
            if self._baslangic_bitis > 0 and panelde:
                # Kullanıcı ilk açılışta panele gelirse normal kapanma akışına geç
                self._baslangic_bitis = 0.0
            return

        # İlk açılış tanıtım süresi dolmadıysa açık tut
        if self._baslangic_bitis > 0:
            if simdi < self._baslangic_bitis:
                return
            self._baslangic_bitis = 0.0
            if not self.sabit:
                self.kapat()
            return

        if self.ayrilma_bas is None:
            self.ayrilma_bas = simdi
        elif simdi - self.ayrilma_bas >= KAPANMA_GECIKMESI:
            self.ayrilma_bas = None
            self.kart_gizle()
            if not self.sabit:
                self.kapat()

    def _saniyelik(self):
        # canlı geri sayım, yenilenme bildirimi, "x dk önce" metinleri ve periyodik topmost garantisi
        try:
            self._otomatik_kontrol()
            self._antigravity_izle()
            self._bildirim_kontrol(time.time())
            self._yeniden_ciz()
            en_uste_al(self.kok)
            if self.kart_arac and self.kart.winfo_viewable():
                en_uste_al(self.kart)
            if self._bildirim_bitis > 0 and self.bildirim.winfo_viewable():
                en_uste_al(self.bildirim)
        finally:
            self.kok.after(1000, self._saniyelik)

    def _yeniden_ciz(self):
        if self._ada_bas is not None:
            return
        if self.acik:
            self._panel_ciz()
            if self.kart_arac:
                self._kart_ciz(self.kart_arac)
        else:
            self._centik_ciz()

    # ------------------------------------------------------------ çentik (kapalı hâl)
    def _kapat_gorunum(self):
        self._konumla(self.centik_g, self.centik_y)
        self.tuval.config(width=self.centik_g, height=self.centik_y)
        self._centik_ciz()
        en_uste_al(self.kok)

    def _arac_rengi(self, arac, simdi):
        bes, hft, _, _ = self._arac_ozeti(arac, simdi)
        degerler = [v for v in (bes[0], hft[0]) if v is not None]
        return durum_rengi(min(degerler) if degerler else None)

    def _centik_dongu_acik(self):
        if not isinstance(self.durum, dict):
            return True
        if "centik_dongu" not in self.durum:
            return True
        return bool(self.durum["centik_dongu"])

    def _centik_dongu_sifirla(self):
        self._centik_dongu_bas = None
        self._centik_son_adim = None
        self._centik_aktif_arac = None
        self._centik_son_etiket = None
        self._centik_son_renk = None
        self._centik_gecis_bas = None
        self._centik_gecis_onceki_metin = None
        self._centik_gecis_onceki_renk = None
        self._son_gecis_cizim = 0.0

    def _centik_dongu_adim_degisti(self, saat):
        if not self._centik_dongu_acik():
            return False
        if self._centik_dongu_bas is None or self._centik_son_adim is None:
            return False
        if saat < self._centik_dongu_bas:
            return True
        adim = int((max(0.0, saat - self._centik_dongu_bas) + 1e-9) // CENTIK_DONGU_SN)
        return adim != self._centik_son_adim

    def _centik_arac_ozeti(self, arac, simdi):
        """Tek araç için çentik bilgisi: veri yoksa None, varsa sözlük."""
        bolum = self.durum.get(arac) if isinstance(self.durum, dict) else None
        dolmus_sn = None
        en_dusuk = None
        for pencere in ortak.PENCERELER:
            kalan, reset, yenilendi = ortak.pencere_durumu(bolum, pencere, simdi)
            if kalan is None:
                continue
            if kalan <= 0.0 and not yenilendi and reset is not None and reset > simdi:
                kalan_sn = reset - simdi
                if dolmus_sn is None or kalan_sn < dolmus_sn:
                    dolmus_sn = kalan_sn
            if en_dusuk is None or kalan < en_dusuk:
                en_dusuk = kalan
        if dolmus_sn is not None:
            return {
                "arac": arac,
                "metin": f"{arac_bilgi(arac)['kisa_ad']} {kisa_sure_metni(dolmus_sn)}",
                "renk": KIRMIZI,
                "kritik": True,
                "oncelik": (0, dolmus_sn),
                "kalan": 0.0,
            }
        if en_dusuk is not None:
            kritik = en_dusuk < CENTIK_KRITIK_ESIK
            return {
                "arac": arac,
                "metin": dil.t("centik_yuzde", ad=arac_bilgi(arac)["kisa_ad"], yuzde=f"{en_dusuk:.0f}"),
                "renk": KIRMIZI if kritik else durum_rengi(en_dusuk),
                "kritik": kritik,
                "oncelik": (1, en_dusuk),
                "kalan": en_dusuk,
            }
        return None

    def _centik_adaylar(self, simdi):
        """Verisi olan etkin araçlar için (indeks, arac, bilgi) listesi."""
        adaylar = []
        for idx, arac in enumerate(self.araclar):
            bilgi = self._centik_arac_ozeti(arac, simdi)
            if bilgi is not None:
                adaylar.append((idx, arac, bilgi))
        return adaylar

    def _centik_en_dusuk(self, simdi):
        """Klasik en kritik / en düşük kalan araç özeti: (metin, vurgu_rengi, aktif_nokta)."""
        adaylar = self._centik_adaylar(simdi)
        if not adaylar:
            return dil.t("centik_bos"), VURGU, None
        idx, _arac, bilgi = min(adaylar, key=lambda oge: oge[2]["oncelik"])
        return bilgi["metin"], bilgi["renk"], idx

    def _centik_ozeti(self, simdi):
        """Kapalı çentik için en kritik tek bakışlık özet: (metin, vurgu_rengi)."""
        etiket, renk, _aktif = self._centik_en_dusuk(simdi)
        return etiket, renk

    def _centik_secim_hesapla(self, simdi, saat):
        adaylar = self._centik_adaylar(simdi)
        if not adaylar:
            return dil.t("centik_bos"), VURGU, None, None, "bos", None, None

        kritikler = [oge for oge in adaylar if oge[2]["kritik"]]
        if kritikler:
            idx, arac, bilgi = min(kritikler, key=lambda oge: oge[2]["oncelik"])
            return bilgi["metin"], KIRMIZI, idx, arac, "kritik", None, None

        if not self._centik_dongu_acik():
            idx, arac, bilgi = min(adaylar, key=lambda oge: oge[2]["oncelik"])
            return bilgi["metin"], bilgi["renk"], idx, arac, "sabit", None, None

        if len(adaylar) == 1:
            idx, arac, bilgi = adaylar[0]
            return bilgi["metin"], bilgi["renk"], idx, arac, "tek", None, None

        if self._centik_dongu_bas is None or saat < self._centik_dongu_bas:
            self._centik_dongu_bas = saat
        gecen = max(0.0, saat - self._centik_dongu_bas)
        adim = int((gecen + 1e-9) // CENTIK_DONGU_SN)
        slot = adim % len(adaylar)
        slot_bas = self._centik_dongu_bas + adim * CENTIK_DONGU_SN
        idx, arac, bilgi = adaylar[slot]
        return bilgi["metin"], bilgi["renk"], idx, arac, "dongu", adim, slot_bas

    def _centik_durumu(self, simdi, saat=None):
        """Kapalı çentik durumu (5 sn döngü / kritik kilit / sabit): (metin, vurgu_rengi, aktif_nokta)."""
        if saat is None:
            saat = self._hareket_saati if self._hareket_saati > 0 else time.perf_counter()
        if self._centik_dongu_bas is not None and saat < self._centik_dongu_bas:
            self._centik_dongu_sifirla()
        etiket, renk, aktif_nokta, _arac, mod, _adim, _slot_bas = self._centik_secim_hesapla(simdi, saat)
        if mod != "dongu":
            self._centik_dongu_bas = None
            self._centik_son_adim = None
        return etiket, renk, aktif_nokta

    def _centik_gecis_durumu(self, simdi, saat=None):
        """Çentik çizimi için geçişli durum: (metin, vurgu_rengi, aktif_nokta, onceki_metin, gecis_t)."""
        if saat is None:
            saat = self._hareket_saati if self._hareket_saati > 0 else time.perf_counter()
        if self._centik_dongu_bas is not None and saat < self._centik_dongu_bas:
            self._centik_dongu_sifirla()

        etiket, hedef_renk, aktif_nokta, arac, mod, adim, slot_bas = self._centik_secim_hesapla(simdi, saat)

        if mod != "dongu":
            self._centik_dongu_bas = None
            self._centik_son_adim = None
            self._centik_gecis_bas = None
            self._centik_gecis_onceki_metin = None
            self._centik_gecis_onceki_renk = None
            self._centik_aktif_arac = None
            self._centik_son_etiket = None
            self._centik_son_renk = None
            return etiket, hedef_renk, aktif_nokta, None, 1.0

        if self._centik_gecis_bas is not None and saat < self._centik_gecis_bas:
            self._centik_gecis_bas = None
            self._centik_gecis_onceki_metin = None
            self._centik_gecis_onceki_renk = None

        self._centik_son_adim = adim

        if (self._centik_aktif_arac is not None
                and arac != self._centik_aktif_arac
                and self._centik_son_etiket is not None
                and self._centik_son_renk is not None):
            if (self._centik_gecis_bas is not None
                    and self._centik_gecis_onceki_renk is not None):
                eski_t = ease_out((saat - self._centik_gecis_bas) / CENTIK_GECIS_SN)
                bas_renk = renk_karistir(self._centik_gecis_onceki_renk, self._centik_son_renk, eski_t)
            else:
                bas_renk = self._centik_son_renk
            self._centik_gecis_onceki_metin = self._centik_son_etiket
            self._centik_gecis_onceki_renk = bas_renk
            self._centik_gecis_bas = slot_bas if (slot_bas is not None and slot_bas <= saat) else saat

        self._centik_aktif_arac = arac
        self._centik_son_etiket = etiket
        self._centik_son_renk = hedef_renk

        if self._centik_gecis_bas is not None and self._centik_gecis_onceki_metin is not None:
            ham_t = (saat - self._centik_gecis_bas) / CENTIK_GECIS_SN
            if ham_t < 1.0:
                t = ease_out(max(0.0, ham_t))
                onceki_renk = self._centik_gecis_onceki_renk or hedef_renk
                karisik_renk = renk_karistir(onceki_renk, hedef_renk, t)
                return etiket, karisik_renk, aktif_nokta, self._centik_gecis_onceki_metin, t
            self._centik_gecis_bas = None
            self._centik_gecis_onceki_metin = None
            self._centik_gecis_onceki_renk = None

        return etiket, hedef_renk, aktif_nokta, None, 1.0

    def _centik_ciz(self, simdi=None, saat=None):
        if simdi is None:
            simdi = time.time()
        if saat is None:
            saat = self._hareket_saati if self._hareket_saati > 0 else time.perf_counter()
        etiket, vurgu_rengi, aktif_nokta, onceki_metin, gecis_t = self._centik_gecis_durumu(simdi, saat=saat)
        self._centik_vurgu = vurgu_rengi
        parliyor = simdi < self._parlama_bitis
        cizgi_rengi = YESIL if parliyor else vurgu_rengi
        periyot = 1.2 if parliyor else 4.0
        nefes_t = (1.0 + math.sin(saat * math.tau / periyot)) / 2.0
        self._son_nefes = round(nefes_t, 2)
        tarama_faz = ((saat / 1.15) % 1.0) if self.yenileniyor else None
        noktalar = [self._arac_rengi(a, simdi) for a in self.araclar]
        img = gm.centik_gorseli(
            self.centik_g,
            self.centik_y,
            noktalar,
            etiket,
            vurgu_renk=cizgi_rengi,
            nefes=nefes_t,
            tarama_faz=tarama_faz,
            aktif_nokta=aktif_nokta,
            onceki_metin=onceki_metin,
            gecis_t=gecis_t,
        )
        self._son_centik_img = img
        self._tuvale_gorsel_koy(self.tuval, "_panel_foto", "_panel_img_id", img)

    def ac(self):
        if self.acik:
            return
        self.acik = True
        self.uzerinde_bas = None
        self.ayrilma_bas = None
        self._ada_baslat(1.0)
        en_uste_al(self.kok)

    def kapat(self):
        if not self.acik:
            return
        self.acik = False
        self._baslangic_bitis = 0.0
        self.kart_gizle()
        self._hover_arac = None
        self._hover_dugme = None
        self._centik_dongu_sifirla()
        self._ada_baslat(0.0)

    # ------------------------------------------------------------ panel (açık hâl)
    def _simge_merkez(self, i):
        arac = self.araclar[i]
        kutu = self._panel_hitboxes.get(arac)
        if kutu:
            return (kutu[0] + kutu[2]) / 2.0, 32.5 * self.olcek
        o = self.olcek
        cx = self.panel_sol + self.simge_adim * i + self.simge_adim / 2
        cy = 32.5 * o
        return cx, cy

    def _simge_altinda(self, x, y):
        if self._panel_hitboxes:
            for arac in self.araclar:
                kutu = self._panel_hitboxes.get(arac)
                if kutu and kutu[0] <= x < kutu[2] and kutu[1] <= y < kutu[3]:
                    return arac
            return None
        if y < 0 or y >= self.panel_y:
            return None
        for i, arac in enumerate(self.araclar):
            sol = self.panel_sol + self.simge_adim * i
            if sol <= x < sol + self.simge_adim:
                return arac
        return None

    def _dugme_altinda(self, x, y):
        for kimlik in ("yenile", "sabit", "ekran", "cikis"):
            kutu = self._panel_hitboxes.get(kimlik)
            if kutu and kutu[0] <= x <= kutu[2] and kutu[1] <= y <= kutu[3]:
                return kimlik
        return None

    def _dugme_konumlari(self):
        """(yenile, sabitle, ekran, cikis) düğme merkezlerini döner."""
        if all(k in self._panel_hitboxes for k in ("yenile", "sabit", "ekran", "cikis")):
            sonuc = []
            for k in ("yenile", "sabit", "ekran", "cikis"):
                x1, y1, x2, y2 = self._panel_hitboxes[k]
                sonuc.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
            return tuple(sonuc)
        o = self.olcek
        bas_x = self.panel_sol + self.simge_adim * len(self.araclar) + self.ayrac_g + self.dugme_adim / 2
        cy = 32.5 * o
        return tuple((bas_x + self.dugme_adim * i, cy) for i in range(4))

    def _panel_ciz(self):
        simdi = time.time()
        araclar_durum = {}
        for arac in self.araclar:
            bes, hft, _, _ = self._arac_ozeti(arac, simdi)
            araclar_durum[arac] = {
                "bes_kalan": bes[0],
                "hft_kalan": hft[0],
                "renk": arac_bilgi(arac)["renk"],
            }

        tarama_faz = (self._hareket_saati / 1.15) % 1.0
        donus_aci = (self._hareket_saati * 360.0 / 0.9) % 360.0
        mesgul = bool(self.yenileniyor)
        img, hitboxes = gm.panel_gorseli(
            self.panel_g,
            self.panel_y,
            araclar_durum,
            secili_arac=self.kart_arac,
            hover_arac=self._hover_arac,
            hover_dugme=self._hover_dugme,
            sabit=self.sabit,
            yenileniyor=mesgul,
            tarama_faz=tarama_faz,
            donus_aci=donus_aci,
            durum_metni=dil.t("yenileniyor_ucnokta") if mesgul else None,
            coklu_monitor=len(self.monitorler) > 1,
            araclar=list(self.araclar),
        )
        self._panel_hitboxes = hitboxes
        self._son_panel_img = img
        self._tuvale_gorsel_koy(self.tuval, "_panel_foto", "_panel_img_id", img)

    def _panel_tik(self, e):
        # Erken tıklama koruması: kapalıysa önce aç, detay kartı takılı kalmasın
        if not self.acik:
            self.ac()
            return
        if self._ada_bas is not None:
            return

        dugme = self._dugme_altinda(e.x, e.y)
        if dugme == "yenile":
            self.yenile()
        elif dugme == "sabit":
            self.sabit = not self.sabit
            self._panel_ciz()
        elif dugme == "ekran":
            self.ekran_degistir()
        elif dugme == "cikis":
            self.kok.destroy()
        else:
            arac = self._simge_altinda(e.x, e.y)
            if arac:
                self.kart_goster(arac)

    def dil_degistir(self, kod):
        """Arayüz dilini değiştirip kaydeder ve görünümü hemen günceller."""
        if kod not in dil.DESTEKLENEN_DILLER:
            return False
        dil.dil_ayarla(kod)
        self.durum["dil"] = kod
        self._centik_gecis_bas = None
        self._centik_gecis_onceki_metin = None
        self._centik_gecis_onceki_renk = None
        self._centik_son_etiket = None
        self._son_nefes = None
        self._yeniden_ciz()
        return True

    def centik_dongu_ayarla(self, acik=None):
        """Çentikte sırayla gösterme ayarını değiştirir, kaydeder ve görünümü tazeler."""
        yeni_deger = (not self._centik_dongu_acik()) if acik is None else bool(acik)
        ortak.ayar_guncelle({"centik_dongu": yeni_deger})
        if isinstance(self.durum, dict):
            self.durum["centik_dongu"] = yeni_deger
        self._centik_dongu_sifirla()
        self._son_nefes = None
        if not self.acik and self._ada_bas is None:
            self._centik_ciz()
        return yeni_deger

    def _arac_secimi_ac(self):
        """'Araçları bağla' penceresini açar ve seçimi canlı uygular."""
        if self._secim_acik:
            return
        self._secim_acik = True
        try:
            if self.kart_arac:
                self.kart_gizle()
            if not self.acik:
                self.ac()
            onceki = list(self.araclar)
            sonuc = ilk_kurulum.sec(ana=self.kok, onceki=onceki)
            if sonuc:
                kaydedildi = secim.secimi_kaydet(sonuc)
                if not kaydedildi:
                    self.bildirim_goster(dil.t("secim_kaydedilemedi"), AMBER, sure_sn=4.0)
                self.durum[secim.AYAR_ANAHTARI] = list(sonuc)
                self.araclari_degistir(sonuc)
                yeniler = [a for a in sonuc if a not in onceki]
                if yeniler:
                    self.yenile(yeniler)
        except Exception:
            pass
        finally:
            self._secim_acik = False

    def _sag_tik(self, e=None):
        """Sağ tıkta araç seçimi + dil menüsü açar (olay nesnesi yoksa doğrudan seçim)."""
        if e is None:
            self._arac_secimi_ac()
            return
        if self._secim_acik:
            return
        self._secim_acik = True
        try:
            menu = tk.Menu(self.kok, tearoff=0, bg=KART, fg=YAZI,
                           activebackground=gm.YUZEY_HOVER, activeforeground=YAZI,
                           font=(FONT, 9))
            menu.add_command(label=dil.t("menu_araclari_sec"),
                             command=lambda: self.kok.after(10, self._arac_secimi_ac))
            dongu_var = tk.BooleanVar(master=self.kok, value=self._centik_dongu_acik())
            self._centik_dongu_var = dongu_var
            menu.add_checkbutton(
                label=dil.t("menu_centik_dongu"),
                variable=dongu_var,
                command=lambda v=dongu_var: self.centik_dongu_ayarla(bool(v.get())),
            )
            dil_menu = tk.Menu(menu, tearoff=0, bg=KART, fg=YAZI,
                               activebackground=gm.YUZEY_HOVER, activeforeground=YAZI,
                               font=(FONT, 9))
            etkin = dil.etkin_dil(self.durum)
            dil_var = tk.StringVar(master=self.kok, value=etkin)
            for kod, etiket_anahtari in (("tr", "menu_dil_tr"), ("en", "menu_dil_en")):
                dil_menu.add_radiobutton(
                    label=dil.t(etiket_anahtari),
                    value=kod,
                    variable=dil_var,
                    command=lambda k=kod: self.dil_degistir(k),
                )
            menu.add_cascade(label=dil.t("menu_dil"), menu=dil_menu)
            try:
                menu.tk_popup(e.x_root, e.y_root)
            finally:
                menu.grab_release()
        except Exception:
            pass
        finally:
            self._secim_acik = False

    # ------------------------------------------------------------ detay kartı
    def kart_goster(self, arac):
        if arac not in self.araclar:
            return
        if not self.acik:
            self.ac()
        self.ayrilma_bas = None
        self.kart_arac = arac
        self._kart_bas = time.perf_counter()
        self._dolum_baslat()
        o = self.olcek
        i = self.araclar.index(arac)
        px, py = self.kok.winfo_rootx(), self.kok.winfo_rooty()
        cx, _ = self._simge_merkez(i)
        c_sol, c_ust, c_sag, c_alt = self._calisma_alani()
        pay = int(8 * o)
        # Simgenin hemen altında ortalanmış
        x = int(px + cx - self.kart_g / 2)
        y = int(py + self.panel_y + pay)
        x = max(c_sol + pay, min(x, c_sag - self.kart_g - pay))
        y = max(c_ust + pay, min(y, c_alt - self.kart_y - pay))
        self._kart_hedef = (x, y)
        self.kart.attributes("-alpha", 0.0)
        self.kart.geometry(geometri_metni(self.kart_g, self.kart_y, x, y - int(6*o)))
        self.kart_tuval.config(width=self.kart_g, height=self.kart_y)
        self.kart.deiconify()
        self.kart.lift()
        self.kart.update_idletasks()
        dwm_yuvarlak_kose(self.kart)
        en_uste_al(self.kart)
        self._kart_ciz(arac)
        self._panel_ciz()

    def kart_gizle(self):
        self._kart_bas = None
        self._dolum_bas = None
        self._kart_hover_dugme = None
        if self.kart_arac is not None:
            self.kart_arac = None
            self.kart.withdraw()
            if self.acik:
                self._panel_ciz()

    def _kart_dugme_altinda(self, x, y):
        for kimlik in ("yenile",):
            kutu = self._kart_hitboxes.get(kimlik)
            if kutu and kutu[0] <= x <= kutu[2] and kutu[1] <= y <= kutu[3]:
                return kimlik
        return None

    def _kart_ciz(self, arac):
        simdi = time.time()
        bilgi = arac_bilgi(arac)
        bes, hft, kaynak, guncel = self._arac_ozeti(arac, simdi)
        bolum = self.durum.get(arac) if isinstance(getattr(self, "durum", None), dict) else None
        if kaynak == "otomatik":
            kaynak_etiketi = (dil.t("kaynak_statusline"), YESIL)
        elif isinstance(kaynak, str) and (kaynak.startswith("Otomatik") or kaynak.startswith("Auto")):
            if arac == "antigravity":
                kaynak_etiketi = (antigravity_etiketi(kaynak, bolum), YESIL)
            else:
                kaynak_etiketi = (kaynak, YESIL)
        elif kaynak == "elle":
            kaynak_etiketi = (dil.t("kaynak_eski_elle"), AMBER)
        else:
            kaynak_etiketi = (dil.t("veri_yok"), GRI)
        if bilgi.get("durum") == "deneysel":
            kaynak_etiketi = (f"{kaynak_etiketi[0]} · {dil.t('deneysel')}", kaynak_etiketi[1])

        etiketler = bolum.get("etiketler") if isinstance(bolum, dict) else None
        if isinstance(etiketler, dict):
            bes_ham = etiketler.get("bes_saat")
            hft_ham = etiketler.get("haftalik")
            bes_baslik = bes_ham if isinstance(bes_ham, str) and bes_ham else dil.t("kart_5s_baslik")
            hft_baslik = hft_ham if isinstance(hft_ham, str) and hft_ham else dil.t("kart_baska_yok")
        else:
            bes_baslik = dil.t("kart_5s_baslik")
            hft_baslik = dil.t("kart_hft_baslik")

        notu, nrenk = self.yenileme_notu.get(arac, ("", SOLUK))
        if (
            not notu
            and arac == "antigravity"
            and isinstance(bolum, dict)
            and isinstance(bolum.get("diger_gruplar"), dict)
        ):
            parcalar = []
            for gad, gveri in bolum["diger_gruplar"].items():
                if not isinstance(gveri, dict):
                    continue
                b5 = ortak.sayi(gveri.get("bes_saat"))
                bh = ortak.sayi(gveri.get("haftalik"))
                b5_str = dil.t("diger_grup_yuzde", deger=round(b5)) if b5 is not None else "—"
                bh_str = dil.t("diger_grup_yuzde", deger=round(bh)) if bh is not None else "—"
                parcalar.append(dil.t("diger_grup_satir", ad=gad, b5=b5_str, bh=bh_str))
            if parcalar:
                notu, nrenk = " · ".join(parcalar), SOLUK
        bes_anim = ((bes[0] or 0.0) / 100.0) * self._dolum if bes[0] is not None else 0.0
        hft_anim = ((hft[0] or 0.0) / 100.0) * self._dolum if hft[0] is not None else 0.0
        tarama_faz = (self._hareket_saati / 1.15) % 1.0
        donus_aci = (self._hareket_saati * 360.0 / 0.9) % 360.0

        img, hitboxes = gm.kart_gorseli(
            self.kart_g,
            self.kart_y,
            bilgi["ad"],
            bilgi["renk"],
            kaynak_etiketi,
            bes,
            hft,
            bes_anim_oran=bes_anim,
            hft_anim_oran=hft_anim,
            son_guncelleme=once_metni(guncel, simdi),
            not_metni=notu,
            not_renk=nrenk,
            hover_dugme=self._kart_hover_dugme,
            yenileniyor=(arac in self.yenileniyor),
            donus_aci=donus_aci,
            tarama_faz=tarama_faz,
            bes_baslik=bes_baslik,
            hft_baslik=hft_baslik,
        )
        self._kart_hitboxes = hitboxes
        self._yenile_alan = hitboxes.get("yenile")
        self._son_kart_img = img
        self._tuvale_gorsel_koy(self.kart_tuval, "_kart_foto", "_kart_img_id", img)

    def _kart_tik(self, e):
        if not self.kart_arac:
            return
        a = getattr(self, "_yenile_alan", None)
        if a and a[0] <= e.x <= a[2] and a[1] <= e.y <= a[3]:
            self.yenile([self.kart_arac])


def kendini_sina(cikti_yolu):
    """Pencere ve mutex açmadan modülleri, bağlayıcıları, dili ve çizimi doğrular."""
    sonuc = {
        "basarili": False,
        "baglayicilar": [],
        "yukleme_hatalari": {},
        "dil": "",
        "cizim_boyutu": None,
        "hata": None,
    }
    try:
        yuklenen = baglayicilar.hepsi()
        sonuc["baglayicilar"] = [b.kimlik for b in yuklenen]
        sonuc["yukleme_hatalari"] = baglayicilar.yukleme_hatalari()
        sonuc["dil"] = dil.etkin_dil()
        img = gm.centik_gorseli(168, 24, [gm.YESIL, gm.AMBER, gm.VURGU], dil.t("centik_bos"))
        sonuc["cizim_boyutu"] = list(img.size)
        sonuc["basarili"] = (
            bool(sonuc["baglayicilar"])
            and not sonuc["yukleme_hatalari"]
            and sonuc["cizim_boyutu"] == [168, 24]
        )
    except Exception as h:
        sonuc["hata"] = f"{type(h).__name__}: {h}"
    if cikti_yolu:
        klasor = os.path.dirname(os.path.abspath(cikti_yolu))
        if klasor:
            os.makedirs(klasor, exist_ok=True)
        with open(cikti_yolu, "w", encoding="utf-8") as f:
            json.dump(sonuc, f, ensure_ascii=False, indent=2)
    return 0 if sonuc["basarili"] else 1


def main():
    if "--kendini-sina" in sys.argv:
        idx = sys.argv.index("--kendini-sina")
        cikti = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        sys.exit(kendini_sina(cikti))
    if not tek_ornek():
        return
    try:
        dpi_farkindaligi()
        try:
            durum = ortak.oku()
            if os.environ.get("LIMIT_CUBUGU_KURULUM") != "0" and secim.kurulum_gerekli(durum):
                sonuc = ilk_kurulum.sec()
                if sonuc:
                    secim.secimi_kaydet(sonuc)
                else:
                    secim.secimi_kaydet(secim.etkin_kimlikler(durum))
        except Exception:
            pass
        kok = tk.Tk()
        kok.title(dil.t("uygulama_adi"))
        try:
            taban_yol = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            ikon = os.path.join(taban_yol, "assets", "limitnotch.ico")
            if os.path.isfile(ikon):
                kok.iconbitmap(ikon)
        except Exception:
            pass
        LimitCubugu(kok)
        kok.mainloop()
    finally:
        tek_ornek_temizle()


if __name__ == "__main__":
    main()
