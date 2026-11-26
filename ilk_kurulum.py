"""Limit Çubuğu - ilk açılışta "Bilgisayarında şunları buldum" penceresi.

`sec()` bulunan araçları onay kutularıyla gösterir; seçilen kimlik listesini ya da
vazgeçildiyse None döndürür. Pencere mantığı `_Pencere` sınıfındadır (test edilebilir).
"""
import os
import sys
import tkinter as tk

import baglayicilar
import dil
from baglayicilar import taban

BASLIK = "LimitNotch — Araçları bağla"

# gorsel_motor içe aktarılmaz; renkler kopyadır.
ZEMIN = "#0D1424"
YUZEY = "#152036"
YUZEY_HOVER = "#213254"
YAZI = "#F8FAFC"
SOLUK = "#94A3B8"
AMBER = "#FBBF24"
VURGU = "#38BDF8"
FONT = "Segoe UI"


def varsayilan_secim(bulunanlar, onceki=None):
    """Önceki seçim verilmişse listedeki her önceki kimlik; yoksa bulunan kararlılar."""
    if onceki is not None:
        onceki = set(onceki)
        return [b.kimlik for b in bulunanlar if b.kimlik in onceki]
    return [b.kimlik for b in bulunanlar if b.durum == taban.KARARLI]


def _bulunur_mu(b):
    try:
        return bool(b.bul())
    except Exception:
        return False


class _Pencere:
    """Pencere ve düğme komutları. Sonuç `self.sonuc`'ta (None = vazgeçildi/kapatıldı)."""

    def __init__(self, ana, baglayicilar_listesi, onceki=None):
        self.sonuc = None
        onceki_kume = set(onceki) if onceki is not None else set()
        self.bulunan = []      # bulunanlar + önceki seçimde olup bulunamayanlar (liste sırasıyla)
        self.eksik = set()     # bulunan içindeki "bulunamadı ama önceki seçimde var" kimlikleri
        self.bulunmayan = []
        for b in baglayicilar_listesi:
            if _bulunur_mu(b):
                self.bulunan.append(b)
            elif b.kimlik in onceki_kume:
                self.bulunan.append(b)
                self.eksik.add(b.kimlik)
            else:
                self.bulunmayan.append(b)
        self.degiskenler = {}  # kimlik -> tk.BooleanVar
        self.ana = ana
        self.pencere = tk.Toplevel(ana)
        self.pencere.withdraw()
        self.pencere.title(dil.t("kurulum_baslik"))
        try:
            taban_yol = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            ikon = os.path.join(taban_yol, "assets", "limitnotch.ico")
            if os.path.isfile(ikon):
                self.pencere.iconbitmap(ikon)
        except Exception:
            pass
        self.pencere.configure(bg=ZEMIN)
        self.pencere.resizable(False, False)
        self.pencere.protocol("WM_DELETE_WINDOW", self.vazgec)
        self.secilenler_dugmesi = None
        self._kur(onceki)
        self._ortala()
        self.pencere.attributes("-topmost", True)
        self.pencere.deiconify()
        self.one_al()

    def one_al(self):
        try:
            self.pencere.lift()
            self.pencere.focus_force()
        except tk.TclError:
            pass

    # -- yerleşim -------------------------------------------------------------
    def _etiket(self, ust, metin, boyut=10, renk=YAZI, kalin=False, **kw):
        return tk.Label(ust, text=metin, bg=ZEMIN, fg=renk, anchor="w", justify="left",
                        font=(FONT, boyut, "bold" if kalin else "normal"), **kw)

    def _dugme(self, ust, metin, komut, birincil=False):
        return tk.Button(
            ust, text=metin, command=komut, relief="flat", bd=0, cursor="hand2",
            bg=VURGU if birincil else YUZEY, fg=ZEMIN if birincil else YAZI,
            activebackground="#7DD3FC" if birincil else YUZEY_HOVER,
            activeforeground=ZEMIN if birincil else YAZI,
            disabledforeground=SOLUK, font=(FONT, 10, "bold" if birincil else "normal"),
            padx=16, pady=7)

    def _kur(self, onceki):
        kok = tk.Frame(self.pencere, bg=ZEMIN, padx=22, pady=18)
        kok.pack(fill="both", expand=True)
        if not self.bulunan:
            self._etiket(kok, dil.t("kurulum_hic_yok"),
                         11, kalin=True, wraplength=420).pack(fill="x")
            self._etiket(kok, dil.t("kurulum_desteklenenler"), 9, SOLUK).pack(fill="x", pady=(12, 2))
            for b in self.bulunmayan:
                self._etiket(kok, f"•  {b.ad or b.kimlik}", 10, SOLUK).pack(fill="x")
            alt = tk.Frame(kok, bg=ZEMIN)
            alt.pack(fill="x", pady=(18, 0))
            self._dugme(alt, dil.t("kapat"), self.vazgec, birincil=True).pack(side="right")
            return

        self._etiket(kok, dil.t("kurulum_bulunanlar"), 12, kalin=True).pack(fill="x")
        varsayilan = set(varsayilan_secim(self.bulunan, onceki))
        for b in self.bulunan:
            satir = tk.Frame(kok, bg=ZEMIN)
            satir.pack(fill="x", pady=(10, 0))
            var = tk.BooleanVar(master=self.pencere, value=b.kimlik in varsayilan)
            var.trace_add("write", lambda *_: self._dugmeleri_guncelle())
            self.degiskenler[b.kimlik] = var
            ust = tk.Frame(satir, bg=ZEMIN)
            ust.pack(fill="x")
            tk.Checkbutton(
                ust, text=b.ad or b.kimlik, variable=var, bg=ZEMIN, fg=YAZI,
                selectcolor=YUZEY, activebackground=ZEMIN, activeforeground=YAZI,
                font=(FONT, 11, "bold"), bd=0, highlightthickness=0, cursor="hand2",
            ).pack(side="left")
            if b.kimlik in self.eksik:
                tk.Label(ust, text=dil.t("kurulum_bulunamadi_etiket"), bg=ZEMIN,
                         fg=SOLUK, font=(FONT, 8)).pack(side="left", padx=(8, 0))
            if b.durum == taban.DENEYSEL:
                tk.Label(ust, text=dil.t("deneysel"), bg=ZEMIN, fg=AMBER,
                         font=(FONT, 8, "bold")).pack(side="left", padx=(8, 0))
            yol_metni = b.gorunen_okuma_yolu() if hasattr(b, "gorunen_okuma_yolu") else b.okuma_yolu
            if yol_metni:
                self._etiket(satir, yol_metni, 8, SOLUK, wraplength=420).pack(
                    fill="x", padx=(24, 0))

        if self.bulunmayan:
            self._etiket(kok, dil.t("kurulum_bulunmayanlar"), 9, SOLUK).pack(
                fill="x", pady=(18, 2))
            for b in self.bulunmayan:
                self._etiket(kok, f"•  {b.ad or b.kimlik}", 10, SOLUK).pack(fill="x")

        alt = tk.Frame(kok, bg=ZEMIN)
        alt.pack(fill="x", pady=(20, 0))
        self._dugme(alt, dil.t("hepsini_bagla"), self.hepsini_bagla, birincil=True).pack(side="right")
        self.secilenler_dugmesi = self._dugme(alt, dil.t("secilenleri_bagla"), self.secilenleri_bagla)
        self.secilenler_dugmesi.pack(side="right", padx=(0, 8))
        self._dugme(alt, dil.t("vazgec"), self.vazgec).pack(side="left")
        self._dugmeleri_guncelle()

    def _dugmeleri_guncelle(self):
        if self.secilenler_dugmesi is None:
            return
        var_mi = any(v.get() for v in self.degiskenler.values())
        self.secilenler_dugmesi.configure(state="normal" if var_mi else "disabled")

    def _ortala(self):
        try:
            self.pencere.update_idletasks()
            g, y = self.pencere.winfo_reqwidth(), self.pencere.winfo_reqheight()
            x = (self.pencere.winfo_screenwidth() - g) // 2
            yy = max(0, (self.pencere.winfo_screenheight() - y) // 3)
            self.pencere.geometry(f"+{x}+{yy}")
        except tk.TclError:
            pass

    # -- düğme komutları ------------------------------------------------------
    def _kapat(self):
        try:
            self.pencere.grab_release()
        except tk.TclError:
            pass
        try:
            self.pencere.destroy()
        except tk.TclError:
            pass

    def hepsini_bagla(self):
        self.sonuc = [b.kimlik for b in self.bulunan]
        self._kapat()

    def secilenleri_bagla(self):
        secilen = [b.kimlik for b in self.bulunan
                   if self.degiskenler.get(b.kimlik) is not None
                   and self.degiskenler[b.kimlik].get()]
        if not secilen:
            return
        self.sonuc = secilen
        self._kapat()

    def vazgec(self):
        self.sonuc = None
        self._kapat()


def sec(ana=None, baglayicilar_listesi=None, onceki=None):
    """Pencereyi açar -> seçilen kimlik listesi ya da None (vazgeçildi/bulunamadı)."""
    if baglayicilar_listesi is None:
        try:
            baglayicilar_listesi = baglayicilar.hepsi()
        except Exception:
            baglayicilar_listesi = []
    kendi = ana is None
    if kendi:
        ana = tk.Tk()
        ana.withdraw()
    pen = None
    try:
        pen = _Pencere(ana, baglayicilar_listesi, onceki)
        if not kendi:
            try:
                pen.pencere.wait_visibility()
                pen.pencere.grab_set()
            except tk.TclError:
                pass
            pen.one_al()
        ana.wait_window(pen.pencere)
        return pen.sonuc
    finally:
        if pen is not None:
            try:
                pen.pencere.grab_release()
            except tk.TclError:
                pass
            try:
                if pen.pencere.winfo_exists():
                    pen.pencere.destroy()
            except tk.TclError:
                pass
        if kendi:
            try:
                ana.destroy()
            except tk.TclError:
                pass
