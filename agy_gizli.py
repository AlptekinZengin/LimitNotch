"""LimitNotch - Antigravity kapalıyken ayrı Windows masaüstünde gizli kota okuma.

Antigravity'yi kullanıcının masaüstünde pencere göstermeden `LimitNotchGizli` masaüstünde
ve ayrı `--user-data-dir` profiliyle başlatır, yeni açılan dil sunucusunun hub dosyasından
kotayı okur, ardından yalnız kendi başlattığı süreç ağacını kapatır.
"""
import ctypes
import json
import os
import subprocess
import threading
import time

MASAUSTU_ADI = "LimitNotchGizli"
MASAUSTU_YOLU = "WinSta0\\LimitNotchGizli"
ORTAM_ANAHTARI = "LIMIT_CUBUGU_AGY_GIZLI"

GENERIC_ALL = 0x10000000
CREATE_SUSPENDED = 0x00000004
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NO_WINDOW = 0x08000000
TH32CS_SNAPPROCESS = 0x00000002
JOB_OBJECT_EXTENDED_LIMIT_CLASS = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
WM_CLOSE = 0x0010
WAIT_OBJECT_0 = 0x00000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

SIKLIK_SINIRI = 600.0  # 10 dakika
HUB_ARALIK = 0.1
SORGU_ZAMAN_ASIMI = 15.0
SORGU_ARALIK = 1.0
KAPANMA_BEKLEME = 5.0

_KILIT = threading.Lock()
_son_deneme = None
_K32 = None
_U32 = None
_WNDENUMPROC = None


class STARTUPINFOW(ctypes.Structure):
    """Win32 STARTUPINFOW yapısı."""

    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("lpReserved", ctypes.c_wchar_p),
        ("lpDesktop", ctypes.c_wchar_p),
        ("lpTitle", ctypes.c_wchar_p),
        ("dwX", ctypes.c_uint32),
        ("dwY", ctypes.c_uint32),
        ("dwXSize", ctypes.c_uint32),
        ("dwYSize", ctypes.c_uint32),
        ("dwXCountChars", ctypes.c_uint32),
        ("dwYCountChars", ctypes.c_uint32),
        ("dwFillAttribute", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("wShowWindow", ctypes.c_uint16),
        ("cbReserved2", ctypes.c_uint16),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", ctypes.c_void_p),
        ("hStdOutput", ctypes.c_void_p),
        ("hStdError", ctypes.c_void_p),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    """Win32 PROCESS_INFORMATION yapısı."""

    _fields_ = [
        ("hProcess", ctypes.c_void_p),
        ("hThread", ctypes.c_void_p),
        ("dwProcessId", ctypes.c_uint32),
        ("dwThreadId", ctypes.c_uint32),
    ]


class PROCESSENTRY32W(ctypes.Structure):
    """Win32 PROCESSENTRY32W yapısı."""

    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("cntUsage", ctypes.c_uint32),
        ("th32ProcessID", ctypes.c_uint32),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.c_uint32),
        ("cntThreads", ctypes.c_uint32),
        ("th32ParentProcessID", ctypes.c_uint32),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_uint32),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    """Win32 JOBOBJECT_EXTENDED_LIMIT_INFORMATION yapısı (x64/x86 uyumlu)."""

    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _kernel32():
    """argtypes/restype tanımlı kernel32 WinDLL örneğini döner."""
    global _K32
    if _K32 is None:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateProcessW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_int, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_wchar_p,
            ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION),
        ]
        k32.CreateProcessW.restype = ctypes.c_int
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        k32.CreateJobObjectW.restype = ctypes.c_void_p
        k32.SetInformationJobObject.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32,
        ]
        k32.SetInformationJobObject.restype = ctypes.c_int
        k32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        k32.AssignProcessToJobObject.restype = ctypes.c_int
        k32.ResumeThread.argtypes = [ctypes.c_void_p]
        k32.ResumeThread.restype = ctypes.c_uint32
        k32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.TerminateProcess.restype = ctypes.c_int
        k32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.TerminateJobObject.restype = ctypes.c_int
        k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.WaitForSingleObject.restype = ctypes.c_uint32
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.CloseHandle.restype = ctypes.c_int
        k32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
        k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
        k32.Process32FirstW.restype = ctypes.c_int
        k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
        k32.Process32NextW.restype = ctypes.c_int
        _K32 = k32
    return _K32


def _user32():
    """argtypes/restype tanımlı user32 WinDLL örneğini döner."""
    global _U32, _WNDENUMPROC
    if _U32 is None:
        _WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_ssize_t)
        u32 = ctypes.WinDLL("user32", use_last_error=True)
        u32.CreateDesktopW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p,
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ]
        u32.CreateDesktopW.restype = ctypes.c_void_p
        u32.CloseDesktop.argtypes = [ctypes.c_void_p]
        u32.CloseDesktop.restype = ctypes.c_int
        u32.EnumDesktopWindows.argtypes = [ctypes.c_void_p, _WNDENUMPROC, ctypes.c_ssize_t]
        u32.EnumDesktopWindows.restype = ctypes.c_int
        u32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        u32.GetWindowThreadProcessId.restype = ctypes.c_uint32
        u32.PostMessageW.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_ssize_t,
        ]
        u32.PostMessageW.restype = ctypes.c_int
        _U32 = u32
    return _U32


def _varsayilan_exe():
    """Antigravity.exe varsayılan kurulum yolunu döner."""
    yerel = os.environ.get("LOCALAPPDATA") or ""
    return os.path.join(yerel, "Programs", "antigravity", "Antigravity.exe") if yerel else ""


def _varsayilan_profil():
    """Gizli örnek için ayrı --user-data-dir klasör yolunu döner."""
    yerel = os.environ.get("LOCALAPPDATA") or ""
    return os.path.join(yerel, "LimitNotch", "agy-gizli-profil") if yerel else ""


def _hub_pid_oku(dosya):
    """Hub JSON dosyasından pid alanını okur; okunamazsa None."""
    try:
        with open(dosya, "r", encoding="utf-8") as f:
            pid = json.load(f).get("pid")
        return pid if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0 else None
    except Exception:
        return None


def _surec_agaci(kok_pid):
    """Toolhelp32 snapshot ile kok_pid altındaki canlı süreç ağacının PID kümesini döner."""
    if os.name != "nt" or isinstance(kok_pid, bool) or not isinstance(kok_pid, int) or kok_pid <= 0:
        return set()
    k32 = _kernel32()
    anlik = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not anlik or anlik == INVALID_HANDLE_VALUE:
        return set()
    cocuklar = {}
    canli = set()
    try:
        girdi = PROCESSENTRY32W()
        girdi.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if k32.Process32FirstW(anlik, ctypes.byref(girdi)):
            while True:
                pid = int(girdi.th32ProcessID)
                ppid = int(girdi.th32ParentProcessID)
                if pid > 0:
                    canli.add(pid)
                    cocuklar.setdefault(ppid, []).append(pid)
                if not k32.Process32NextW(anlik, ctypes.byref(girdi)):
                    break
    finally:
        k32.CloseHandle(anlik)

    agac = {kok_pid}
    kuyruk = [kok_pid]
    while kuyruk:
        mevcut = kuyruk.pop()
        for cocuk in cocuklar.get(mevcut, ()):
            if cocuk not in agac:
                agac.add(cocuk)
                kuyruk.append(cocuk)
    return {p for p in agac if p in canli}


def _pencereler(pidler, masaustu):
    """Gizli masaüstünde verilen PID kümesine ait üst düzey pencerelerin listesini döner."""
    if os.name != "nt" or not pidler or not masaustu:
        return []
    pid_kumesi = set(pidler)
    bulunan = []
    u32 = _user32()

    def geri_cagri(hwnd, _lparam):
        pid = ctypes.c_uint32(0)
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) in pid_kumesi:
            bulunan.append(hwnd)
        return 1

    try:
        u32.EnumDesktopWindows(masaustu, _WNDENUMPROC(geri_cagri), 0)
    except Exception:
        pass
    return bulunan


def _pencere_kapat(hwnd):
    """Üst düzey pencereye WM_CLOSE gönderir."""
    if os.name == "nt" and hwnd:
        _user32().PostMessageW(hwnd, WM_CLOSE, 0, 0)


def _surec_bekle(surec_tutamac, saniye):
    """Süreç tutamacının belirtilen sürede kapanmasını bekler -> kapandı mı."""
    if os.name != "nt" or not surec_tutamac:
        return False
    ms = int(max(0.0, float(saniye)) * 1000)
    return _kernel32().WaitForSingleObject(surec_tutamac, ms) == WAIT_OBJECT_0


def _surec_canli_mi(pid):
    """Verilen PID hâlâ yaşıyor mu?"""
    import yenileyici
    return yenileyici.surec_calisiyor_mu(pid) is True


def _taskkill(pid):
    """Tek PID ağacını konsol penceresi açmadan taskkill ile sonlandırır."""
    if os.name != "nt" or isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=5,
        )
    except Exception:
        pass


def _is_bitir(is_nesnesi):
    """Job'daki tüm süreçleri sonlandırır; başarılıysa True. PID'e dayanmaz."""
    if os.name != "nt" or not is_nesnesi:
        return False
    try:
        return bool(_kernel32().TerminateJobObject(is_nesnesi, 1))
    except Exception:
        return False


def _tutamac_kapat(tutamac):
    """Win32 handle'ını güvenle kapatır."""
    if os.name == "nt" and tutamac:
        try:
            _kernel32().CloseHandle(tutamac)
        except Exception:
            pass


def _masaustu_kapat(masaustu):
    """Win32 masaüstü handle'ını güvenle kapatır."""
    if os.name == "nt" and masaustu:
        try:
            _user32().CloseDesktop(masaustu)
        except Exception:
            pass


def _baslat(exe, profil):
    """Antigravity'yi ayrı masaüstünde, ayrı profille ve Job Object altında başlatır."""
    if os.name != "nt":
        raise OSError("Gizli başlatma yalnız Windows'ta desteklenir")
    os.makedirs(profil, exist_ok=True)
    k32 = _kernel32()
    u32 = _user32()

    masaustu = u32.CreateDesktopW(MASAUSTU_ADI, None, None, 0, GENERIC_ALL, None)
    if not masaustu:
        raise OSError(f"CreateDesktopW başarısız: {ctypes.get_last_error()}")

    is_nesnesi = None
    pi = PROCESS_INFORMATION()
    try:
        is_nesnesi = k32.CreateJobObjectW(None, None)
        if not is_nesnesi:
            raise OSError(f"CreateJobObjectW başarısız: {ctypes.get_last_error()}")

        bilgi = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        bilgi.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(
            is_nesnesi, JOB_OBJECT_EXTENDED_LIMIT_CLASS,
            ctypes.byref(bilgi), ctypes.sizeof(bilgi),
        ):
            raise OSError(f"SetInformationJobObject başarısız: {ctypes.get_last_error()}")

        si = STARTUPINFOW()
        si.cb = ctypes.sizeof(STARTUPINFOW)
        si.lpDesktop = MASAUSTU_YOLU

        komut = subprocess.list2cmdline([exe, "--user-data-dir=" + profil])
        komut_tampon = ctypes.create_unicode_buffer(komut)
        calisma_dizini = os.path.dirname(exe) or None

        if not k32.CreateProcessW(
            exe, komut_tampon, None, None, False,
            CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT,
            None, calisma_dizini, ctypes.byref(si), ctypes.byref(pi),
        ):
            raise OSError(f"CreateProcessW başarısız: {ctypes.get_last_error()}")

        if not k32.AssignProcessToJobObject(is_nesnesi, pi.hProcess):
            hata = ctypes.get_last_error()
            k32.TerminateProcess(pi.hProcess, 1)
            raise OSError(f"AssignProcessToJobObject başarısız: {hata}")

        if k32.ResumeThread(pi.hThread) == 0xFFFFFFFF:
            hata = ctypes.get_last_error()
            k32.TerminateProcess(pi.hProcess, 1)
            raise OSError(f"ResumeThread başarısız: {hata}")

        k32.CloseHandle(pi.hThread)
        pi.hThread = None
        return {
            "pid": int(pi.dwProcessId),
            "surec": pi.hProcess,
            "is_nesnesi": is_nesnesi,
            "masaustu": masaustu,
        }
    except Exception:
        if pi.hThread:
            _tutamac_kapat(pi.hThread)
        if pi.hProcess:
            _tutamac_kapat(pi.hProcess)
        if is_nesnesi:
            _tutamac_kapat(is_nesnesi)
        _masaustu_kapat(masaustu)
        raise


def _kapat(oturum):
    """Yalnız başlattığımız süreç ağacını temizce kapatır, job ve masaüstü handle'larını bırakır."""
    if not isinstance(oturum, dict):
        return
    kok_pid = oturum.get("pid")
    surec = oturum.get("surec")
    is_nesnesi = oturum.get("is_nesnesi")
    masaustu = oturum.get("masaustu")

    try:
        agac = set(_surec_agaci(kok_pid)) if kok_pid else set()
        if kok_pid and kok_pid not in agac and _surec_canli_mi(kok_pid):
            agac.add(kok_pid)

        if agac and masaustu:
            for hwnd in _pencereler(agac, masaustu):
                try:
                    _pencere_kapat(hwnd)
                except Exception:
                    pass

        kapandi = True
        if surec:
            kapandi = _surec_bekle(surec, KAPANMA_BEKLEME)
        elif kok_pid:
            bitis = time.monotonic() + KAPANMA_BEKLEME
            kapandi = False
            while time.monotonic() < bitis:
                if not _surec_canli_mi(kok_pid):
                    kapandi = True
                    break
                time.sleep(0.1)

        # Kalanları Job üzerinden bitir: PID yeniden kullanılsa bile yalnız bizim ağacımız ölür.
        if _is_bitir(is_nesnesi):
            return

        if not kapandi and kok_pid:
            _taskkill(kok_pid)

        kalan_agac = set(_surec_agaci(kok_pid)) if kok_pid else set()
        for pid in sorted(agac | kalan_agac):
            if _surec_canli_mi(pid):
                _taskkill(pid)
    finally:
        _tutamac_kapat(surec)
        _tutamac_kapat(is_nesnesi)
        _masaustu_kapat(masaustu)


def kullanilabilir_mi(simdi=None, exe=None):
    """Gizli başlatma şu an kullanılabilir mi? Ortam, OS, exe varlığı ve 10 dk sınırı."""
    try:
        if os.name != "nt":
            return False
        if os.environ.get(ORTAM_ANAHTARI) == "0":
            return False
        exe_yolu = _varsayilan_exe() if exe is None else exe
        if not exe_yolu or not os.path.isfile(exe_yolu):
            return False
        an = time.monotonic() if simdi is None else float(simdi)
        if _son_deneme is not None and (an - _son_deneme) < SIKLIK_SINIRI:
            return False
        return True
    except Exception:
        return False


def gizli_oku(sorgu=None, zaman_asimi=60.0, exe=None, profil=None, simdi=None):
    """Antigravity'yi gizli masaüstünde açıp kotasını okur, sonra kapatır -> dict | None.

    Denemediyse veya başaramadıysa None döner; asla istisna fırlatmaz.
    """
    global _son_deneme
    try:
        if not _KILIT.acquire(blocking=False):
            return None
        try:
            an = time.monotonic() if simdi is None else float(simdi)
            exe_yolu = _varsayilan_exe() if exe is None else exe
            if not kullanilabilir_mi(simdi=an, exe=exe_yolu):
                return None
            profil_yolu = _varsayilan_profil() if profil is None else profil
            if not profil_yolu:
                return None

            import yenileyici

            eski_hublar = set(yenileyici.antigravity_hub_dosyalari())
            _son_deneme = an

            oturum = _baslat(exe_yolu, profil_yolu)
            if not oturum:
                return None
            try:
                yeni_hub = None
                bitis = time.monotonic() + max(0.0, float(zaman_asimi))
                while True:
                    for dosya in yenileyici.antigravity_hub_dosyalari():
                        if dosya in eski_hublar:
                            continue
                        pid = _hub_pid_oku(dosya)
                        if pid is not None and yenileyici.antigravity_sureci_mi(pid) is True:
                            yeni_hub = dosya
                            break
                    if yeni_hub is not None:
                        break
                    kalan = bitis - time.monotonic()
                    if kalan <= 0:
                        return None
                    time.sleep(min(HUB_ARALIK, kalan))

                sorgu_fn = (
                    sorgu if sorgu is not None
                    else (lambda hub: yenileyici.antigravity_sorgula(hub_dosyalari=[hub]))
                )
                sorgu_bitis = time.monotonic() + SORGU_ZAMAN_ASIMI
                while True:
                    try:
                        veri = sorgu_fn(yeni_hub)
                        return veri if isinstance(veri, dict) else None
                    except yenileyici.AntigravityHatasi:
                        kalan = sorgu_bitis - time.monotonic()
                        if kalan <= 0:
                            return None
                        time.sleep(min(SORGU_ARALIK, kalan))
                    except Exception:
                        return None
            finally:
                try:
                    _kapat(oturum)
                except Exception:
                    pass
        finally:
            _KILIT.release()
    except Exception:
        return None
