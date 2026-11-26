"""LimitNotch - iki dilli arayüz ve mesaj metinleri (Türkçe / İngilizce).

Dil seçimi sırası:
1. Ortam değişkeni `LIMITNOTCH_DIL` ("tr" veya "en", testler için)
2. `durum.json` içindeki `"dil"` ayarı
3. Windows arayüz dili (`GetUserDefaultUILanguage`: birincil dil 0x1F ise "tr", değilse "en")

Hiçbir fonksiyon istisna fırlatmaz.
"""
import ctypes
import os

import durum_ortak as ortak

DESTEKLENEN_DILLER = ("tr", "en")

METINLER = {
    "tr": {
        "uygulama_adi": "LimitNotch",
        "kurulum_baslik": "LimitNotch — Araçları bağla",
        "kurulum_hic_yok": "Desteklenen araçlardan hiçbiri bu bilgisayarda bulunamadı.",
        "kurulum_desteklenenler": "Desteklenenler:",
        "kapat": "Kapat",
        "kurulum_bulunanlar": "Bilgisayarında şunları buldum:",
        "kurulum_bulunamadi_etiket": "bulunamadı · son okunan veri gösterilir",
        "deneysel": "deneysel",
        "kurulum_bulunmayanlar": "Bu bilgisayarda bulunamayanlar:",
        "hepsini_bagla": "Hepsini bağla",
        "secilenleri_bagla": "Seçilenleri bağla",
        "vazgec": "Vazgeç",
        "panel_yenile": "Yenile",
        "panel_sabit": "Sabit",
        "panel_ekran": "Ekran",
        "panel_cikis": "Çıkış",
        "yenileniyor_ucnokta": "Yenileniyor...",
        "yenileniyor": "Yenileniyor",
        "centik_bos": "LİMİT",
        "centik_yuzde": "{ad} %{yuzde}",
        "kart_5s_baslik": "5 Saatlik Limit",
        "kart_hft_baslik": "Haftalık Limit",
        "kart_baska_yok": "Başka limit yok",
        "veri_yok_kucuk": "veri yok",
        "veri_yok": "Veri yok",
        "yuzde_kaldi_yenilendi": "%100 kaldı (yenilendi)",
        "yuzde_kaldi": "%{yuzde} kaldı",
        "yeni_pencere_sure_bilinmiyor": "Yeni pencere başladı — süre bilinmiyor",
        "yenilenme_tarih_sure": "Yenilenme: {tarih} ({sure} sonra)",
        "yenilenir_sure": "{sure} sonra yenilenir",
        "yenilenme_bilinmiyor": "Yenilenme zamanı bilinmiyor",
        "son_guncelleme_on": "Son güncelleme: {deger}",
        "son_guncelleme_hic": "Son güncelleme: hiç",
        "once_hic": "hiç",
        "once_az_once": "az önce",
        "once_dk": "{n} dk önce",
        "once_sa": "{n} sa önce",
        "once_g": "{n} g önce",
        "bugun": "Bugün",
        "yarin": "Yarın",
        "gun_0": "Pzt",
        "gun_1": "Sal",
        "gun_2": "Çar",
        "gun_3": "Per",
        "gun_4": "Cum",
        "gun_5": "Cmt",
        "gun_6": "Paz",
        "sure_g_sa": "{g} g {sa} sa",
        "sure_sa_dk": "{sa} sa {dk} dk",
        "sure_dk": "{dk} dk",
        "sure_az": "1 dk'dan az",
        "ksure_g": "{g}g",
        "ksure_sa": "{sa}sa",
        "ksure_dk": "{dk}dk",
        "ksure_az": "<1dk",
        "kaynak_statusline": "Otomatik (statusLine)",
        "kaynak_eski_elle": "Eski elle veri",
        "kaynak_otomatik_yenilendi": "Otomatik (yenilendi)",
        "kaynak_otomatik_gh": "Otomatik (gh)",
        "diger_grup_satir": "{ad}: 5 saatlik {b5} · haftalık {bh}",
        "diger_grup_yuzde": "%{deger}",
        "bildirim_yenilendi": "✓ {adlar} yenilendi! (%100)",
        "bildirim_azaldi": "⚠ {ad} limiti azaldı (%{yuzde})",
        "secim_kaydedilemedi": "Seçim kaydedilemedi",
        "yenilenemedi_hata": "Yenilenemedi ({hata})",
        "yenilenemedi_gecersiz": "Yenilenemedi (geçersiz sonuç)",
        "menu_araclari_sec": "Araçları seç…",
        "menu_dil": "Dil / Language",
        "menu_dil_tr": "Türkçe",
        "menu_dil_en": "English",
        "agy_5s_hf_etiket": "{kaynak} · 5s {g5} / hf {gh}",
        "agy_5_saatlik": "5 Saatlik",
        "agy_haftalik": "Haftalık",
        "yol_claude": "Claude Code'un kendi komutu: claude -p /usage (giriş bilgisine dokunulmaz)",
        "yol_codex": "Codex'in kendi sunucusu: codex app-server, rate limit sorgusu (giriş bilgisine dokunulmaz)",
        "yol_antigravity": "Antigravity'nin bu bilgisayarda açtığı yerel kapı (hub_*.json + RetrieveUserQuotaSummary); yalnız uygulama açıkken okunur, güncellemeyle bozulabilir",
        "yol_copilot": "GitHub'ın resmi gh komutu: gh api copilot_internal/user (belgesiz uç nokta; giriş bilgisini gh yönetir)",
        "copilot_kota_premium": "Premium istek",
        "copilot_kota_chat": "Sohbet",
        "copilot_kota_completions": "Kod tamamlama",
        "copilot_aylik_etiket": "{ad} · aylık",
        "hata_yenileme_tanimsiz": "{ad}: yenileme tanımlı değil",
        "hata_bilinmeyen_arac": "Bilinmeyen araç: {arac}",
        "zaman_asimi_sn": "zaman aşımı ({sn} sn)",
        "claude_yenilendi": "Claude limitleri yenilendi",
        "claude_okunamadi": "Claude okunamadı, mevcut veri korundu ({detay})",
        "claude_okunamadi_kisa": "Claude okunamadı ({detay})",
        "claude_yazilamadi": "Claude okundu ama durum.json yazılamadı",
        "claude_komut_yok": "claude komutu bulunamadı",
        "claude_cikti_bos": "Claude /usage çıktısı boş",
        "claude_satir_yok": "limit satırı bulunamadı: {ilk}",
        "claude_baslatilamadi": "claude başlatılamadı: {hata}",
        "claude_hata_dondu": "claude hata döndü: {detay}",
        "claude_cikis_kodu": "çıkış kodu {kod}",
        "claude_bilinmeyen_hata": "bilinmeyen hata",
        "codex_yenilendi": "Codex limitleri yenilendi",
        "codex_okunamadi": "Codex okunamadı, mevcut veri korundu ({detay})",
        "codex_okunamadi_kisa": "Codex okunamadı ({detay})",
        "codex_yazilamadi": "Codex okundu ama durum.json yazılamadı",
        "codex_bulunamadi": "codex bulunamadı (PATH'te ve Codex Desktop'ta yok)",
        "codex_cevap_bozuk": "Codex cevabı beklenen biçimde değil",
        "codex_pencere_yok": "Codex cevabında limit penceresi yok",
        "codex_baslatilamadi": "codex başlatılamadı: {hata}",
        "codex_kapandi": "codex app-server beklenmedik şekilde kapandı",
        "codex_hata_dondu": "codex hata döndü: {mesaj}",
        "codex_iletisim_yok": "codex ile iletişim kurulamadı: {hata}",
        "agy_yenilendi": "Antigravity limitleri yenilendi",
        "agy_bes_saat_yenilendi": "Antigravity 5 saatlik yenilendi (haftalık alınamadı)",
        "agy_kapali_not": "Antigravity kapalı · açılınca kendiliğinden okunur",
        "agy_okunamadi": "Antigravity okunamadı, mevcut veri korundu ({detay})",
        "agy_okunamadi_kisa": "Antigravity okunamadı ({detay})",
        "agy_yazilamadi": "Antigravity okundu ama durum.json yazılamadı",
        "agy_hub_yok": "hub dosyası yok, Antigravity kapalı olabilir",
        "agy_kapali_hata": "Antigravity kapalı (çalışan dil sunucusu yok)",
        "agy_baglanamadi": "sunucuya bağlanılamadı",
        "agy_yanit_gecersiz": "yanıt biçimi geçersiz",
        "agy_kota_yok": "kota bilgisi bulunamadı",
        "copilot_yenilendi": "Copilot limitleri yenilendi",
        "copilot_okunamadi": "Copilot okunamadı, mevcut veri korundu ({detay})",
        "copilot_yazilamadi": "Copilot okunamadı, mevcut veri korundu (yazılamadı)",
        "copilot_gh_yok": "gh komutu bulunamadı",
        "copilot_gh_giris_yok": "gh'de GitHub girişi yok",
        "copilot_izin_yok": "GitHub izin vermedi (401/403)",
        "copilot_404": "Copilot bilgisi bulunamadı (404)",
        "copilot_ag_hatasi": "ağ hatası",
        "copilot_gh_hata": "gh hatası (çıkış kodu {kod})",
        "copilot_gh_baslatilamadi": "gh başlatılamadı: {tur}",
        "copilot_json_degil": "gh yanıtı JSON değil",
        "copilot_bicim_bozuk": "gh yanıtı beklenen biçimde değil",
        "copilot_snapshots_yok": "quota_snapshots yok",
        "copilot_sinirsiz": "sınırsız plan: gösterilecek limit yok",
        "copilot_kota_yok": "kullanılabilir kota bulunamadı",
    },
    "en": {
        "uygulama_adi": "LimitNotch",
        "kurulum_baslik": "LimitNotch — Connect tools",
        "kurulum_hic_yok": "None of the supported tools were found on this computer.",
        "kurulum_desteklenenler": "Supported tools:",
        "kapat": "Close",
        "kurulum_bulunanlar": "Found on your computer:",
        "kurulum_bulunamadi_etiket": "not found · showing last read data",
        "deneysel": "experimental",
        "kurulum_bulunmayanlar": "Not found on this computer:",
        "hepsini_bagla": "Connect all",
        "secilenleri_bagla": "Connect selected",
        "vazgec": "Cancel",
        "panel_yenile": "Refresh",
        "panel_sabit": "Pin",
        "panel_ekran": "Display",
        "panel_cikis": "Quit",
        "yenileniyor_ucnokta": "Refreshing...",
        "yenileniyor": "Refreshing",
        "centik_bos": "LIMIT",
        "centik_yuzde": "{ad} {yuzde}%",
        "kart_5s_baslik": "5-Hour Limit",
        "kart_hft_baslik": "Weekly Limit",
        "kart_baska_yok": "No other limit",
        "veri_yok_kucuk": "no data",
        "veri_yok": "No data",
        "yuzde_kaldi_yenilendi": "100% left (reset)",
        "yuzde_kaldi": "{yuzde}% left",
        "yeni_pencere_sure_bilinmiyor": "New window started — duration unknown",
        "yenilenme_tarih_sure": "Resets: {tarih} (in {sure})",
        "yenilenir_sure": "Resets in {sure}",
        "yenilenme_bilinmiyor": "Reset time unknown",
        "son_guncelleme_on": "Last updated: {deger}",
        "son_guncelleme_hic": "Last updated: never",
        "once_hic": "never",
        "once_az_once": "just now",
        "once_dk": "{n}m ago",
        "once_sa": "{n}h ago",
        "once_g": "{n}d ago",
        "bugun": "Today",
        "yarin": "Tomorrow",
        "gun_0": "Mon",
        "gun_1": "Tue",
        "gun_2": "Wed",
        "gun_3": "Thu",
        "gun_4": "Fri",
        "gun_5": "Sat",
        "gun_6": "Sun",
        "sure_g_sa": "{g}d {sa}h",
        "sure_sa_dk": "{sa}h {dk}m",
        "sure_dk": "{dk}m",
        "sure_az": "< 1m",
        "ksure_g": "{g}d",
        "ksure_sa": "{sa}h",
        "ksure_dk": "{dk}m",
        "ksure_az": "<1m",
        "kaynak_statusline": "Auto (statusLine)",
        "kaynak_eski_elle": "Legacy manual data",
        "kaynak_otomatik_yenilendi": "Auto (refreshed)",
        "kaynak_otomatik_gh": "Auto (gh)",
        "diger_grup_satir": "{ad}: 5h {b5} · weekly {bh}",
        "diger_grup_yuzde": "{deger}%",
        "bildirim_yenilendi": "✓ {adlar} reset! (100%)",
        "bildirim_azaldi": "⚠ {ad} limit low ({yuzde}%)",
        "secim_kaydedilemedi": "Could not save selection",
        "yenilenemedi_hata": "Refresh failed ({hata})",
        "yenilenemedi_gecersiz": "Refresh failed (invalid result)",
        "menu_araclari_sec": "Select tools…",
        "menu_dil": "Dil / Language",
        "menu_dil_tr": "Türkçe",
        "menu_dil_en": "English",
        "agy_5s_hf_etiket": "{kaynak} · 5h {g5} / wk {gh}",
        "agy_5_saatlik": "5-Hour",
        "agy_haftalik": "Weekly",
        "yol_claude": "Claude Code CLI: claude -p /usage (never touches credentials)",
        "yol_codex": "Codex local server: codex app-server rate limit query (never touches credentials)",
        "yol_antigravity": "Antigravity local port (hub_*.json + RetrieveUserQuotaSummary); works only while the app is open, undocumented",
        "yol_copilot": "Official GitHub CLI: gh api copilot_internal/user (undocumented endpoint; gh handles auth)",
        "copilot_kota_premium": "Premium requests",
        "copilot_kota_chat": "Chat",
        "copilot_kota_completions": "Completions",
        "copilot_aylik_etiket": "{ad} · monthly",
        "hata_yenileme_tanimsiz": "{ad}: refresh not implemented",
        "hata_bilinmeyen_arac": "Unknown tool: {arac}",
        "zaman_asimi_sn": "timeout ({sn}s)",
        "claude_yenilendi": "Claude limits refreshed",
        "claude_okunamadi": "Claude read failed, existing data kept ({detay})",
        "claude_okunamadi_kisa": "Claude read failed ({detay})",
        "claude_yazilamadi": "Claude read OK, but failed to write durum.json",
        "claude_komut_yok": "claude command not found",
        "claude_cikti_bos": "Claude /usage output is empty",
        "claude_satir_yok": "limit line not found: {ilk}",
        "claude_baslatilamadi": "failed to start claude: {hata}",
        "claude_hata_dondu": "claude returned error: {detay}",
        "claude_cikis_kodu": "exit code {kod}",
        "claude_bilinmeyen_hata": "unknown error",
        "codex_yenilendi": "Codex limits refreshed",
        "codex_okunamadi": "Codex read failed, existing data kept ({detay})",
        "codex_okunamadi_kisa": "Codex read failed ({detay})",
        "codex_yazilamadi": "Codex read OK, but failed to write durum.json",
        "codex_bulunamadi": "codex not found (not in PATH or Codex Desktop)",
        "codex_cevap_bozuk": "unexpected Codex response format",
        "codex_pencere_yok": "no limit window in Codex response",
        "codex_baslatilamadi": "failed to start codex: {hata}",
        "codex_kapandi": "codex app-server closed unexpectedly",
        "codex_hata_dondu": "codex returned error: {mesaj}",
        "codex_iletisim_yok": "could not communicate with codex: {hata}",
        "agy_yenilendi": "Antigravity limits refreshed",
        "agy_bes_saat_yenilendi": "Antigravity 5h refreshed (weekly unavailable)",
        "agy_kapali_not": "Antigravity closed · auto-reads when opened",
        "agy_okunamadi": "Antigravity read failed, existing data kept ({detay})",
        "agy_okunamadi_kisa": "Antigravity read failed ({detay})",
        "agy_yazilamadi": "Antigravity read OK, but failed to write durum.json",
        "agy_hub_yok": "no hub file, Antigravity may be closed",
        "agy_kapali_hata": "Antigravity closed (no running language server)",
        "agy_baglanamadi": "could not connect to server",
        "agy_yanit_gecersiz": "invalid response format",
        "agy_kota_yok": "quota info not found",
        "copilot_yenilendi": "Copilot limits refreshed",
        "copilot_okunamadi": "Copilot read failed, existing data kept ({detay})",
        "copilot_yazilamadi": "Copilot read failed, existing data kept (write error)",
        "copilot_gh_yok": "gh command not found",
        "copilot_gh_giris_yok": "not logged in to GitHub via gh",
        "copilot_izin_yok": "GitHub denied access (401/403)",
        "copilot_404": "Copilot info not found (404)",
        "copilot_ag_hatasi": "network error",
        "copilot_gh_hata": "gh error (exit code {kod})",
        "copilot_gh_baslatilamadi": "failed to start gh: {tur}",
        "copilot_json_degil": "gh output is not JSON",
        "copilot_bicim_bozuk": "unexpected gh response format",
        "copilot_snapshots_yok": "missing quota_snapshots",
        "copilot_sinirsiz": "unlimited plan: no limit to show",
        "copilot_kota_yok": "no usable quota found",
    },
}


def _windows_ui_dili():
    """Windows kullanıcı arayüz dilini okur; birincil dil Türkçe (0x1F) ise 'tr', değilse 'en'."""
    try:
        if os.name == "nt":
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if (int(lang_id) & 0x3FF) == 0x1F:
                return "tr"
    except Exception:
        pass
    return "en"


def etkin_dil(durum=None, yol=None):
    """Etkin dil kodunu döner: 'tr' veya 'en'. Asla istisna fırlatmaz."""
    try:
        ortam = (os.environ.get("LIMITNOTCH_DIL") or "").strip().lower()
        if ortam in DESTEKLENEN_DILLER:
            return ortam
    except Exception:
        pass
    try:
        veri = durum if isinstance(durum, dict) else ortak.oku(yol or ortak.DURUM_DOSYASI)
        if isinstance(veri, dict):
            kayitli = (veri.get("dil") or "").strip().lower()
            if kayitli in DESTEKLENEN_DILLER:
                return kayitli
    except Exception:
        pass
    return _windows_ui_dili()


def dil_ayarla(kod, yol=None):
    """Kullanıcı dil tercihini durum.json'a kaydeder -> bool."""
    try:
        temiz = (kod or "").strip().lower()
        if temiz not in DESTEKLENEN_DILLER:
            return False
        return ortak.ayar_guncelle({"dil": temiz}, yol or ortak.DURUM_DOSYASI)
    except Exception:
        return False


def t(anahtar, **kw):
    """Etkin dildeki metni döner; eksikse TR'ye, o da yoksa anahtarın kendisine düşer."""
    try:
        d = etkin_dil()
        sablon = METINLER.get(d, {}).get(anahtar)
        if sablon is None:
            sablon = METINLER["tr"].get(anahtar)
        if sablon is None:
            return str(anahtar)
        if kw:
            try:
                return sablon.format(**kw)
            except Exception:
                return sablon
        return sablon
    except Exception:
        return str(anahtar)
