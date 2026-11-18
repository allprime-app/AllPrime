# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""
AllPrime - Veri Dosyasi Indirme
=================================
Genom, transkript tablosu ve dbSNP indeksi uygulamayla DAGITILMAZ (toplam ~7 GB).
Bunun yerine kurulumdan sonra kaynagindan indirilir. Boylece:

  - Dagitilan paket kucuk kalir (klasoru USB ile tasima derdi biter),
  - Ucuncu taraf veriyi biz yeniden dagitmiyoruz, herkes kaynagindan aliyor,
  - Hangi surumun indirildigi kayit altina alinabiliyor.

Indirme KALDIGI YERDEN devam eder (HTTP Range). 840 MB'lik bir dosyada kopan
baglanti yuzunden bastan baslamak kabul edilemezdi; kaynaklarin hepsinin
Accept-Ranges destekledigi dogrulandi.

Ayni anda tek indirme calisir: yavas baglantida paralel indirme toplam sureyi
kisaltmaz, sadece ilerlemeyi okunmaz hale getirir.
"""

import os
import re
import sys
import gzip
import json
import time
import zlib
import shutil
import threading

import requests

import lang
from lang import get_lang


class _Iki(str):
    """Iki dilli metin (A7-01). Degeri Turkce; .tr ve .en iki dili de tasir.
    Durum kaydinda iki dil saklanir, /downloads yanitinda istegin diliyle verilir:
    indirme surerken arayuz dili degisirse metin yeni dilde gelir."""

    def __new__(cls, tr, en):
        o = super().__new__(cls, tr)
        o.tr = tr
        o.en = en
        return o


def t(tr, en):
    """lang.t gibi, ama iki dili de tutar (is parcacigi isteginin dilini bilmez)."""
    return _Iki(tr, en)


def _sec(m):
    """Kayitli metni gecerli istek dilinde ver (iki dilli degilse oldugu gibi)."""
    if isinstance(m, _Iki):
        return m.en if get_lang() == "en" else m.tr
    return m


def _iki_cagri(fn, *a):
    """Dile bagli metin ureten fonksiyonu iki dilde cagirip _Iki yapar (tek sonuc None olabilir)."""
    eski = get_lang()
    try:
        lang.set_lang("tr")
        tr = fn(*a)
        lang.set_lang("en")
        en = fn(*a)
    finally:
        lang.set_lang(eski)
    return _Iki(tr, en) if tr and en else tr


CHUNK = 1024 * 1024          # 1 MB
TIMEOUT = 60


class DownloadError(Exception):
    """Kullaniciya gosterilebilir indirme hatasi."""

    def __str__(self):
        # Iki dilli metin (A7-01) istegin dilinde okunur.
        return _sec(self.args[0]) if len(self.args) == 1 else super().__str__()


# ------------------------------------------------------------------
# Hedef klasorler
# ------------------------------------------------------------------
def data_root():
    """genomes/ ve annotations/ klasorlerinin bulunacagi kok.

    Paketlenmis uygulamada sys.executable = <app>/resources/backend/...exe
    oldugu icin iki ust klasor uygulama kokudur. Yazilamiyorsa %APPDATA%'ya
    duseriz (uygulama Program Files altina kurulmus olabilir)."""
    if os.environ.get("ALLPRIME_DATA_ROOT"):
        return os.environ["ALLPRIME_DATA_ROOT"]

    # ONCE MOTORUN BILDIGINE BAK. Motor genom yolunu config.json'dan da ogrenebilir
    # ve bu yol uygulamanin yanindaki klasor OLMAYABILIR (ornegin kaynaktan
    # calisirken). Ikisi ayri karar verince panel "genom yok" deyip indirme
    # onerirken motor ayni genomu kullaniyordu - kullanici icin kafa karistirici.
    try:
        import engine
        for asm in ("GRCh38", "GRCh37"):
            yol = engine.GENOME_PATHS.get(asm) or ""
            if yol and os.path.exists(yol):
                # <kok>/genomes/<dosya.fa>  ->  <kok>
                kok = os.path.dirname(os.path.dirname(os.path.abspath(yol)))
                if _yazilabilir(kok):
                    return kok
    except Exception:
        pass
    try:
        import transcripts
        for asm in ("GRCh38", "GRCh37"):
            yol = transcripts.ANNOT_PATHS.get(asm) or ""
            if yol and os.path.exists(yol):
                kok = os.path.dirname(os.path.dirname(os.path.abspath(yol)))
                if _yazilabilir(kok):
                    return kok
    except Exception:
        pass

    adaylar = []
    d = os.path.dirname(os.path.abspath(sys.executable))
    for _ in range(6):
        adaylar.append(d)
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    adaylar.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Once zaten veri klasoru olan yeri tercih et
    for b in adaylar:
        if os.path.isdir(os.path.join(b, "genomes")) or \
           os.path.isdir(os.path.join(b, "annotations")):
            if _yazilabilir(b):
                return b
    # Yoksa "resources" iceren uygulama koku
    for b in adaylar:
        if os.path.isdir(os.path.join(b, "resources")) and _yazilabilir(b):
            return b
    for b in adaylar:
        if _yazilabilir(b):
            return b
    # %APPDATA%\AllPrime\data (engine.CONFIG_DIR'in altinda). Onceki adla acilmis ayar
    # klasorundeki veri motor acilirken buraya tasinir (engine.eski_ayarlari_tasi).
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                        "AllPrime", "data")


# Yazilabildigi bir kez gorulen klasorler. data_root() indirme panelinin saniyelik
# durum sorgusunda her seferinde diske test dosyasi yazip siliyordu (inceleme
# bulgusu 16). Yalnizca OLUMLU sonuc saklanir: yazilamayan klasor sonradan acilabilir.
_YAZILABILIR = set()


def _yazilabilir(d):
    if d in _YAZILABILIR:
        return True
    try:
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, ".allprime_yazma_testi")
        with open(p, "w") as f:
            f.write("1")
        os.remove(p)
        _YAZILABILIR.add(d)
        return True
    except OSError:
        return False


def _bos_alan(path):
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


# ------------------------------------------------------------------
# Katalog
# ------------------------------------------------------------------
ENSEMBL = {
    "GRCh38": "https://ftp.ensembl.org/pub/current_fasta/homo_sapiens/dna/"
              "Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz",
    "GRCh37": "https://ftp.ensembl.org/pub/grch37/current/fasta/homo_sapiens/dna/"
              "Homo_sapiens.GRCh37.dna.primary_assembly.fa.gz",
}
UCSC_DB = {"GRCh37": "hg19", "GRCh38": "hg38"}
MANE_DIR = "https://ftp.ncbi.nlm.nih.gov/refseq/MANE/MANE_human/current/"


def _mane_url():
    """MANE dosya adi surum tasir (MANE.GRCh38.v1.5.summary.txt.gz); klasoru
    listeleyip guncel adi buluruz - boylece MANE yenilendiginde de calisir."""
    r = requests.get(MANE_DIR, timeout=TIMEOUT)
    r.raise_for_status()
    adlar = re.findall(r'MANE\.GRCh38\.v[\d.]+\.summary\.txt\.gz', r.text)
    if not adlar:
        raise DownloadError(t("MANE dosyasının güncel adı bulunamadı.",
                              "Could not determine the current MANE file name."))
    return MANE_DIR + max(set(adlar), key=_mane_surumu)


def _mane_surumu(ad):
    """'MANE.GRCh38.v1.10.summary.txt.gz' -> (1, 10). Metin siralamasinda v1.10
    v1.9'dan KUCUK sayiliyordu (inceleme bulgusu 11); surum sayisal karsilastirilir."""
    m = re.search(r"\.v([\d.]+?)\.summary", ad)
    return tuple(int(x) for x in m.group(1).split(".") if x) if m else ()


def catalog():
    """Indirilebilir ogeler. 'hedef' tamamlandiginda olusan dosya."""
    kok = data_root()
    g = os.path.join(kok, "genomes")
    a = os.path.join(kok, "annotations")
    items = {}
    for asm in ("GRCh37", "GRCh38"):
        items[f"genome_{asm}"] = {
            "grup": "genome", "assembly": asm,
            "ad": f"Referans genom {asm}",
            "name": f"Reference genome {asm}",
            "kaynak": "Ensembl",
            "url": ENSEMBL[asm],
            "hedef": os.path.join(g, f"Homo_sapiens.{asm}.dna.primary_assembly.fa"),
            "islem": "genome",
            "yaklasik": 840 * 2**20,
            "disk": 3400 * 2**20,     # acilmis FASTA + indeks icin gereken yer
        }
        items[f"refgene_{asm}"] = {
            "grup": "annotation", "assembly": asm,
            "ad": f"Transkript tablosu {asm} (refGene)",
            "name": f"Transcript table {asm} (refGene)",
            "kaynak": "UCSC",
            "url": f"https://hgdownload.soe.ucsc.edu/goldenPath/{UCSC_DB[asm]}"
                   "/database/refGene.txt.gz",
            "hedef": os.path.join(a, f"refGene_{UCSC_DB[asm]}.txt.gz"),
            "islem": "kopya",
            "yaklasik": 8 * 2**20,
            "disk": 20 * 2**20,
        }
        items[f"dbsnp_{asm}"] = {
            "grup": "dbsnp", "assembly": asm,
            "ad": f"Yaygin varyant indeksi {asm} (dbSNP)",
            "name": f"Common variant index {asm} (dbSNP)",
            "kaynak": "UCSC snp151Common",
            "url": f"https://hgdownload.soe.ucsc.edu/goldenPath/{UCSC_DB[asm]}"
                   "/database/snp151Common.txt.gz",
            "hedef": os.path.join(a, f"dbsnp_common_{UCSC_DB[asm]}.apidx"),
            "islem": "dbsnp",
            "yaklasik": 760 * 2**20,
            "disk": 1000 * 2**20,
        }
    items["mane"] = {
        "grup": "annotation", "assembly": None,
        "ad": "MANE Select listesi",
        "name": "MANE Select list",
        "kaynak": "NCBI",
        "url": None,                  # calisma aninda cozulur
        "hedef": os.path.join(a, "MANE.summary.txt.gz"),
        "islem": "kopya",
        "yaklasik": 1 * 2**20,
        "disk": 5 * 2**20,
    }
    return items


# ------------------------------------------------------------------
# Durum
# ------------------------------------------------------------------
_LOCK = threading.Lock()
_STATE = {}          # anahtar -> durum sozlugu
_IPTAL = set()
_AKTIF = None


def _durum_yaz(key, **kw):
    with _LOCK:
        d = _STATE.setdefault(key, {})
        d.update(kw)


def status():
    """Arayuz icin: her ogenin kurulu olup olmadigi + suren islemin ilerlemesi."""
    items = catalog()
    out = {}
    for key, it in items.items():
        kurulu = os.path.exists(it["hedef"])
        boyut = os.path.getsize(it["hedef"]) if kurulu else 0
        with _LOCK:
            st = dict(_STATE.get(key, {}))
        out[key] = {
            "grup": it["grup"], "assembly": it["assembly"],
            "ad": it["ad"], "name": it["name"], "kaynak": it["kaynak"],
            "hedef": it["hedef"],
            "kurulu": kurulu, "boyut": boyut,
            "yaklasik": it["yaklasik"],
            "durum": st.get("durum", "hazir"),
            "indirilen": st.get("indirilen", 0),
            "toplam": st.get("toplam", 0),
            "hiz": st.get("hiz", 0),
            "mesaj": _sec(st.get("mesaj", "")),
            "hata": _sec(st.get("hata", "")),
        }
    with _LOCK:
        aktif = _AKTIF
    return {"kok": data_root(), "aktif": aktif, "ogeler": out,
            "bos_alan": _bos_alan(data_root())}


def cancel(key=None):
    with _LOCK:
        hedef = key or _AKTIF
        if hedef:
            _IPTAL.add(hedef)
    return bool(hedef)


# ------------------------------------------------------------------
# Indirme
# ------------------------------------------------------------------
# Yarim parcanin HANGI dosya surumune ait oldugu. Kaynaklar "current" adresleri
# (Ensembl current_fasta); iki deneme arasinda yeni surum cikarsa duz Range ile
# devam etmek iki farkli dosyayi uc uca ekliyordu: acarken hata, ustelik bozuk
# parca silinmedigi icin her yeni denemede ayni yerden devam - kalici dongu.
# If-Range ile sunucu, dosya degismisse devami degil tamamini gonderir.
# Ad bilerek desensiz: annotations/ klasorundeki "*refGene*" / "MANE*" taramasina
# (Windows'ta buyuk-kucuk harf duyarsiz) takilmamali.
DOGRULAYICI_DOSYASI = ".indirme_dogrulayici.json"


def _dogrulayici_yolu(gecici):
    return os.path.join(os.path.dirname(gecici), DOGRULAYICI_DOSYASI)


def _dogrulayici_oku(gecici, url):
    try:
        with open(_dogrulayici_yolu(gecici), "r", encoding="utf-8") as f:
            d = json.load(f).get(os.path.basename(gecici)) or {}
    except (OSError, ValueError, AttributeError):
        return None
    return d.get("dogrulayici") if d.get("url") == url else None


def _dogrulayici_yaz(gecici, url, dogrulayici):
    yol = _dogrulayici_yolu(gecici)
    try:
        with open(yol, "r", encoding="utf-8") as f:
            hepsi = json.load(f)
        if not isinstance(hepsi, dict):
            hepsi = {}
    except (OSError, ValueError):
        hepsi = {}
    ad = os.path.basename(gecici)
    if dogrulayici:
        hepsi[ad] = {"url": url, "dogrulayici": dogrulayici}
    else:
        hepsi.pop(ad, None)
    try:
        if hepsi:
            with open(yol, "w", encoding="utf-8") as f:
                json.dump(hepsi, f, indent=2)
        elif os.path.exists(yol):
            os.remove(yol)
    except OSError:
        pass


def _yanit_dogrulayicisi(r):
    """If-Range icin GUCLU dogrulayici: zayif ETag (W/...) kullanilamaz (RFC 9110)."""
    etag = r.headers.get("ETag") or ""
    if etag and not etag.startswith("W/"):
        return etag
    return r.headers.get("Last-Modified") or None


def _parcayi_sil(gecici):
    """Yarim/bozuk parcayi ve dogrulayici kaydini birlikte sil."""
    try:
        if os.path.exists(gecici):
            os.remove(gecici)
    except OSError:
        pass
    _dogrulayici_yaz(gecici, None, None)


def _indir(key, url, gecici):
    """Kaldigi yerden indir. Doner: tamamlanan gecici dosya yolu."""
    var = os.path.getsize(gecici) if os.path.exists(gecici) else 0
    dogrulayici = _dogrulayici_oku(gecici, url) if var else None
    if var and not dogrulayici:
        # Parcanin hangi surume ait oldugu bilinmiyor: uzerine eklemek guvenli degil
        _parcayi_sil(gecici)
        var = 0
    basliklar = {"Range": f"bytes={var}-", "If-Range": dogrulayici} if var else {}

    with requests.get(url, headers=basliklar, stream=True, timeout=TIMEOUT) as r:
        if var and r.status_code == 416:      # zaten tam inmis (If-Range tuttu)
            return gecici
        if var and r.status_code != 206:      # dosya degismis ya da devam yok -> bastan
            r.close()
            return _indir_bastan(key, url, gecici)
        r.raise_for_status()
        if not var:
            _dogrulayici_yaz(gecici, url, _yanit_dogrulayicisi(r))
        uzunluk = int(r.headers.get("Content-Length") or 0) + var
        _durum_yaz(key, durum="indiriliyor", indirilen=var, toplam=uzunluk,
                   mesaj=t("İndiriliyor…", "Downloading…"))

        t0, son_bayt, son_t = time.time(), var, time.time()
        with open(gecici, "ab" if var else "wb") as f:
            for parca in r.iter_content(CHUNK):
                if key in _IPTAL:
                    raise DownloadError(t("İndirme iptal edildi.",
                                          "Download cancelled."))
                if not parca:
                    continue
                f.write(parca)
                var += len(parca)
                simdi = time.time()
                if simdi - son_t >= 0.5:
                    hiz = (var - son_bayt) / (simdi - son_t)
                    _durum_yaz(key, indirilen=var, toplam=uzunluk, hiz=hiz)
                    son_bayt, son_t = var, simdi
    _durum_yaz(key, indirilen=var, toplam=uzunluk)
    return gecici


def _indir_bastan(key, url, gecici):
    _parcayi_sil(gecici)
    return _indir(key, url, gecici)


def _gunzip(kaynak, hedef, key, etiket):
    """Buyuk dosyayi akis halinde ac (bellege almadan)."""
    _durum_yaz(key, durum="isleniyor", mesaj=etiket, hiz=0)
    gecici = hedef + ".part"
    with gzip.open(kaynak, "rb") as gz, open(gecici, "wb") as out:
        while True:
            if key in _IPTAL:
                raise DownloadError(t("İşlem iptal edildi.", "Cancelled."))
            try:
                b = gz.read(CHUNK)
            except _GZIP_HATALARI as e:
                raise _bozuk_dosya_hatasi(e)
            if not b:
                break
            out.write(b)
    os.replace(gecici, hedef)


def _sil(yol):
    try:
        if os.path.exists(yol):
            os.remove(yol)
    except OSError:
        pass


_GZIP_HATALARI = (OSError, EOFError, zlib.error)   # BadGzipFile bir OSError


def _bozuk_dosya_hatasi(e):
    return DownloadError(t(
        f"İndirilen dosya bozuk ({type(e).__name__}); silindi, yeniden indirin.",
        f"The downloaded file is corrupt ({type(e).__name__}); it was deleted, "
        "download it again."))


def _gzip_dogrula(yol):
    """gzip dosyasini sonuna kadar oku; bozuksa anlasilir hata."""
    try:
        with gzip.open(yol, "rb") as gz:
            while gz.read(CHUNK):
                pass
    except _GZIP_HATALARI as e:
        raise _bozuk_dosya_hatasi(e)


def _isle(key, it, inen):
    """Indirilen dosyayi son haline getir."""
    hedef = it["hedef"]
    os.makedirs(os.path.dirname(hedef), exist_ok=True)

    if it["islem"] == "kopya":
        if inen.endswith(".gz") or hedef.endswith(".gz"):
            # Butunluk: gzip sonundaki CRC32/boy sarti bozuk ya da karisik
            # parcayi yakalar (dosya kucuk; bir kez okumak ucuz).
            _durum_yaz(key, durum="isleniyor", mesaj=t("Doğrulanıyor…", "Verifying…"))
            _gzip_dogrula(inen)
        os.replace(inen, hedef)
        return

    if it["islem"] == "genome":
        _gunzip(inen, hedef, key, t("Arşiv açılıyor…", "Extracting…"))
        os.remove(inen)
        # Acilan dosya gercekten bir insan genomu mu? Buradaki hata "tamam"
        # yazip sonraki oturumda "genom var ama calismiyor" olarak geri
        # donuyordu; kaynagina en yakin yerde yakalanmali.
        import engine
        k = engine.genome_check(hedef)
        if not k["ok"]:
            # Kalirsa panel "kurulu" gosterir; bu calismada uretilen dosya, silinir
            _sil(hedef)
            raise DownloadError(k["reason"])
        # FASTA indeksi (.fai) olmadan ne dizi cekilebilir ne ozgulluk taranabilir.
        # Onceki (yarim kalmis olabilecek) indeks silinir: pyfaidx rebuild=False ile
        # var olani oldugu gibi kullanir, eksik kromozomlari "bulunamadi" der.
        _durum_yaz(key, durum="isleniyor",
                   mesaj=t("FASTA indeksi oluşturuluyor…", "Building FASTA index…"))
        _sil(hedef + ".fai")
        from pyfaidx import Fasta
        try:
            Fasta(hedef, as_raw=True, sequence_always_upper=True, rebuild=False).close()
        except BaseException:
            _sil(hedef + ".fai")
            raise
        if not engine.fai_tutarli(hedef):
            _sil(hedef + ".fai")
            raise DownloadError(t(
                "FASTA indeksi (.fai) eksik oluştu; yeniden deneyin.",
                "The FASTA index (.fai) came out incomplete; try again."))
        # Indirilen genom eksik/kesik mi (kromozom yok ya da uzunluk bilinenden farkli)? D3-04
        eksik = _iki_cagri(engine.tamlik_mesaji, hedef, it["assembly"])
        if eksik:
            _sil(hedef + ".fai")
            _sil(hedef)
            raise DownloadError(eksik)
        return

    if it["islem"] == "dbsnp":
        _durum_yaz(key, durum="isleniyor",
                   mesaj=t("Varyant indeksi oluşturuluyor…", "Building variant index…"))
        import dbsnp
        dbsnp.build_index(inen, hedef, it["assembly"])
        os.remove(inen)      # 750 MB ham tablo artik gereksiz
        return

    raise DownloadError(t(f"Bilinmeyen işlem: {it['islem']}", f"Unknown operation: {it['islem']}"))


def rescan(it):
    """Indirilen dosyayi CALISAN uygulamaya tanit. Modüller yollari acilista
    tespit ediyor; bu olmadan kullanici yeniden baslatmak zorunda kalirdi."""
    hedef, asm = it["hedef"], it["assembly"]
    try:
        if it["islem"] == "genome":
            import engine
            engine.GENOME_PATHS[asm] = hedef
            engine.save_config()
            engine._FASTA_CACHE.pop(hedef, None)
        elif it["islem"] == "dbsnp":
            import dbsnp
            dbsnp.DBSNP_PATHS[asm] = hedef
            eski = dbsnp._INDEX_CACHE.pop(asm, None)
            if eski:
                eski.close()
        else:                                  # refGene / MANE
            import transcripts
            if "refGene" in os.path.basename(hedef):
                transcripts.ANNOT_PATHS[asm] = hedef
                transcripts._INDEX_CACHE.pop(asm, None)
                transcripts._BOLGE_CACHE.pop(asm, None)    # bolge gorunumu de eski tablodan
            else:
                transcripts.MANE_PATH = hedef
                transcripts._MANE_CACHE = None
    except Exception:
        pass                                   # tanitilamazsa yeniden baslatma yeterli


def _ag_hatasi(e):
    """requests istisnasini iki dilli aciklamaya cevir (E1-04); ag istisnasi degilse None.
    Ham metin tani icin parantez icinde kalir ("404 Client Error: Not Found for url: ..."
    Turkce arayuzde tek basina Ingilizce gorunuyordu)."""
    if not isinstance(e, requests.exceptions.RequestException):
        return None
    ham = " ".join(str(e).split())
    ham = ham if len(ham) <= 200 else ham[:200] + "…"
    if isinstance(e, requests.exceptions.HTTPError):
        kod = getattr(getattr(e, "response", None), "status_code", None)
        if kod is None:
            m = re.match(r"(\d{3})\b", ham)      # yanitsiz HTTPError: "404 Client Error: ..."
            kod = int(m.group(1)) if m else None
        if kod == 404 or kod == 410:
            tr, en = "dosya bulunamadı", "file not found"
        elif kod in (401, 403):
            tr, en = "erişim reddedildi", "access denied"
        elif kod == 429:
            tr, en = "çok fazla istek; biraz bekleyip yeniden deneyin", \
                     "too many requests; wait a little and try again"
        elif isinstance(kod, int) and kod >= 500:
            tr, en = "sunucu hatası; daha sonra yeniden deneyin", \
                     "server error; try again later"
        else:
            tr, en = "istek reddedildi", "request rejected"
        if kod is None:
            return t(f"Sunucu hata döndürdü ({ham}).", f"The server returned an error ({ham}).")
        return t(f"Sunucu {kod} döndürdü ({tr}). Ayrıntı: {ham}",
                 f"The server returned {kod} ({en}). Details: {ham}")
    if isinstance(e, requests.exceptions.Timeout):
        return t(f"Bağlantı zaman aşımına uğradı; internet bağlantınızı kontrol edip yeniden "
                 f"deneyin. Ayrıntı: {ham}",
                 f"The connection timed out; check your internet connection and try again. "
                 f"Details: {ham}")
    if isinstance(e, requests.exceptions.ConnectionError):
        return t(f"Bağlantı kurulamadı; internet bağlantınızı kontrol edip yeniden deneyin. "
                 f"Ayrıntı: {ham}",
                 f"Could not connect; check your internet connection and try again. "
                 f"Details: {ham}")
    return t(f"Ağ hatası; yeniden deneyin. Ayrıntı: {ham}",
             f"Network error; try again. Details: {ham}")


def _calistir(key):
    global _AKTIF
    items = catalog()
    it = items[key]
    gecici = it["hedef"] + ".indiriliyor"
    try:
        os.makedirs(os.path.dirname(it["hedef"]), exist_ok=True)

        bos = _bos_alan(os.path.dirname(it["hedef"]))
        if bos is not None and bos < it["disk"]:
            raise DownloadError(t(
                f"Yetersiz disk alanı: {it['disk'] / 2**30:.1f} GB gerekiyor, "
                f"{bos / 2**30:.1f} GB boş.",
                f"Not enough disk space: {it['disk'] / 2**30:.1f} GB needed, "
                f"{bos / 2**30:.1f} GB free."))

        url = it["url"] or _mane_url()
        inen = _indir(key, url, gecici)
        try:
            _isle(key, it, inen)
        except BaseException:
            # Isleme (acma, dogrulama, indeks) iptal disi bir sebeple bozulduysa
            # inen dosya guvenilmez: kalirsa sonraki deneme ayni bozuk dosyadan
            # devam ediyor, hata hic gecmiyordu. Iptalde tam inmis dosya korunur.
            if key not in _IPTAL:
                _parcayi_sil(gecici)
            _sil(it["hedef"] + ".part")
            raise
        _dogrulayici_yaz(gecici, None, None)
        rescan(it)
        _durum_yaz(key, durum="tamam", hiz=0,
                   mesaj=t("Hazır.", "Ready."), hata="")
    except Exception as e:
        iletiler = (e.args[0] if e.args and isinstance(e.args[0], _Iki)
                    else _ag_hatasi(e) or str(e))
        _durum_yaz(key, durum="hata", hiz=0, hata=iletiler, mesaj="")
    finally:
        with _LOCK:
            _IPTAL.discard(key)
            if _AKTIF == key:
                _AKTIF = None


def start(key):
    """Indirmeyi arka planda baslat. Ayni anda tek is calisir."""
    global _AKTIF
    items = catalog()
    if key not in items:
        raise DownloadError(t(f"Bilinmeyen öğe: {key}", f"Unknown item: {key}"))
    with _LOCK:
        if _AKTIF:
            raise DownloadError(t(
                "Zaten bir indirme sürüyor; yavaş bağlantıda paralel indirme "
                "toplam süreyi kısaltmaz.",
                "A download is already running; on a slow link, parallel downloads "
                "do not shorten the total time."))
        _AKTIF = key
        _IPTAL.discard(key)
    _durum_yaz(key, durum="basliyor", indirilen=0, toplam=0, hiz=0, hata="",
               mesaj=t("Başlatılıyor…", "Starting…"))
    dil = get_lang()

    def _is():
        # Is parcacigi istegin ContextVar'ini miras almaz (A7-01): dili elle kur ki
        # indirme sirasinda cagrilan diger modullerin (dbsnp vb.) mesajlari da
        # baslatma dilinde olsun; durum metinleri zaten iki dilli saklanir.
        lang.set_lang(dil)
        _calistir(key)

    th = threading.Thread(target=_is, daemon=True)
    th.start()
    return True
