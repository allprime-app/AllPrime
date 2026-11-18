# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""
AllPrime - Transkript Katmani (RefSeq / refGene)
=================================================
NM_ kodundan ekson yapisi, iplik ve CDS sinirlari; c. koordinati <-> cDNA indeksi
cevirisi. Dizi ICERMEZ - sadece annotasyon. Diziyi engine.py genom FASTA'sindan
eksonlari birlestirerek kurar.

Veri kaynaklari (annotations/ klasoru):
  - refGene_hg19.txt.gz / refGene_hg38.txt.gz  (UCSC)  -> ekson yapisi
  - MANE.summary.txt.gz                        (NCBI)  -> MANE Select isareti

ONEMLI: UCSC refGene'de akesyon SURUMSUZ tutulur ('NM_000546', 'NM_000546.6' degil).
Bu yuzden tum eslestirme surumsuz yapilir; kullanicinin girdigi surum bilgi olarak
saklanip ekranda gosterilir.
"""

import os
import re
import sys
import gzip
import glob
import zlib
import bisect
import threading

from lang import t, tr_sayi

# assembly -> UCSC veritabani adi
UCSC_DB = {"GRCh37": "hg19", "GRCh38": "hg38"}

ANNOT_PATHS = {
    "GRCh37": os.environ.get("ALLPRIME_REFGENE_HG19", ""),
    "GRCh38": os.environ.get("ALLPRIME_REFGENE_HG38", ""),
}
MANE_PATH = os.environ.get("ALLPRIME_MANE", "")

# Birincil kromozomlar (alt-haplotip/patch kayitlari elenir: chr17_ctg5_hap1 vb.)
_PRIMARY_CHROM = re.compile(r"^chr([0-9]{1,2}|X|Y|M)$")

# Onbellek yukleyicileri kilitli (inceleme bulgusu 18): Flask istekleri ayri
# is parcaciklarinda; ilk iki istek ayni anda gelince refGene iki kez okunuyordu.
# RLock: _bolge_indeksi kilit icinde _load_index'i cagirir.
_YUKLEME_KILIDI = threading.RLock()
_INDEX_CACHE = {}   # assembly -> {"by_acc": {...}, "by_gene": {...}}
# Yarim/bozuk tablo dosyasinda okuma hatalari. Eskiden yakalanmiyordu: kesik bir
# refGene ya da MANE /transcripts ve /design'da 500 + ham Ingilizce "Compressed file
# ended before the end-of-stream marker" veriyordu (2026-10-29). Elle kopyalanan
# dosya (KURULUM 2b) indirme panelindeki gzip dogrulamasindan gecmez.
_OKUMA_HATALARI = (OSError, EOFError, zlib.error, ValueError, IndexError)


def _bozuk_tablo(ad, yol):
    return TranscriptError(t(
        f"{ad} okunamadı, dosya yarım ya da bozuk: {os.path.basename(yol)}. Veri dosyaları "
        "panelinden yeniden indirin ya da dosyayı yeniden kopyalayın.",
        f"{ad} could not be read; the file is truncated or corrupt: {os.path.basename(yol)}. "
        "Download it again from the data files panel or copy the file again."))
_MANE_CACHE = None  # {surumsuz_acc: ("MANE Select"|"MANE Plus Clinical", surumlu_acc)}


class TranscriptError(Exception):
    """Kullaniciya gosterilebilir transkript hatasi."""
    pass


# ------------------------------------------------------------------
# Dosya bulma (engine.autodetect_genomes ile ayni mantik: exe'nin yanindaki klasor)
# ------------------------------------------------------------------
def _candidate_bases():
    bases = []
    if os.environ.get("ALLPRIME_APP_ROOT"):
        bases.append(os.environ["ALLPRIME_APP_ROOT"])
    d = os.path.dirname(os.path.abspath(sys.executable))
    for _ in range(6):
        bases.append(d)
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    bases.append(os.path.dirname(os.path.abspath(__file__)))
    bases.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out, seen = [], set()
    for b in bases:
        if not b:
            continue
        rb = os.path.normpath(b)
        if rb not in seen:
            seen.add(rb)
            out.append(rb)
    return out


def autodetect_annotations():
    """Uygulamanin yanindaki 'annotations\\' klasorunu bul; bos alanlari doldur."""
    global MANE_PATH
    for base in _candidate_bases():
        adir = os.path.join(base, "annotations")
        if not os.path.isdir(adir):
            continue
        for asm, db in UCSC_DB.items():
            if ANNOT_PATHS.get(asm):
                continue
            hits = [p for p in glob.glob(os.path.join(adir, "*refGene*"))
                    if db in os.path.basename(p).lower()]
            if hits:
                ANNOT_PATHS[asm] = hits[0]
        if not MANE_PATH:
            hits = glob.glob(os.path.join(adir, "MANE*summary*"))
            if hits:
                MANE_PATH = hits[0]


autodetect_annotations()


_BUTUNLUK = {}          # dosya yolu -> ((boyut, degisme zamani), okunabiliyor_mu)


def _tablo_okunur(yol):
    """/health icin ucuz denetim: dosya var ve SONUNA KADAR okunabiliyor mu (gzip
    butunlugu, ~0,1 sn)? Tam ayristirma (~0,8 sn) tasarim yolunda yapilir.
    Eskiden yalnizca dosyanin varligina bakiliyordu: yarim refGene "var" gorunuyor,
    DNA tasarimi da psodogen uyarisini sessizce kaybediyordu (2026-10-31 hata taramasi).
    Sonuc dosya imzasina gore onbellekte tutulur."""
    if not yol or not os.path.exists(yol):
        return False
    try:
        st = os.stat(yol)
    except OSError:
        return False
    imza = (st.st_size, st.st_mtime_ns)
    eski = _BUTUNLUK.get(yol)
    if eski and eski[0] == imza:
        return eski[1]
    try:
        with (gzip.open(yol, "rb") if yol.lower().endswith(".gz") else open(yol, "rb")) as f:
            while f.read(1 << 20):
                pass
        sonuc = True
    except _OKUMA_HATALARI:
        sonuc = False
    _BUTUNLUK[yol] = (imza, sonuc)
    return sonuc


def annotation_status():
    """/health icin: hangi assembly'de transkript verisi hazir (var VE okunabiliyor)?"""
    return {
        "GRCh37": _tablo_okunur(ANNOT_PATHS.get("GRCh37", "")),
        "GRCh38": _tablo_okunur(ANNOT_PATHS.get("GRCh38", "")),
        "mane": _tablo_okunur(MANE_PATH),
    }


def tablo_uyarisi(assembly, baglam="tasarim"):
    """refGene ya da MANE okunamiyorsa (yok, yarim, bozuk) kullaniciya gosterilecek
    UYARI metni; ikisi de okunabiliyorsa None. baglam: "tasarim" | "degerlendir".

    DNA ve kirilma noktasi tasariminda bu tablolar yalnizca ekzon/intron etiketi ve
    psodogen uyarisi icin kullanilir ve hatalari sessizce yutulur (konum_bolgesi ->
    None, paralog._araliklar -> None): yarim refGene'de PTEN tasarimi PTENP1 uyarisi
    OLMADAN, hicbir not dusulmeden donuyordu (2026-10-31 hata taramasi). Tablolar
    saglamken iki yukleyici de onbellekten aninda doner; metin her cagrida o anki
    dilde uretilir."""
    refgene = mane = None
    try:
        _load_index(assembly)
    except TranscriptError as e:
        refgene = str(e)
    try:
        _load_mane()
    except TranscriptError as e:
        mane = str(e)
    if not refgene and not mane:
        return None
    sebep = " ".join(x for x in (refgene, mane) if x)
    if baglam == "degerlendir":
        return t(f"{sebep} Bu değerlendirmede ürünün hangi gende olduğu ve F/R yönü "
                 "denetlenemedi.",
                 f"{sebep} This evaluation could not check which gene the product is in "
                 "or the F/R orientation.")
    if refgene:
        return t(f"UYARI: {sebep} Bu tasarımda psödogen / yakın-özdeş kopya uyarısı ve "
                 "ekzon/intron etiketleri YOK; kopyası olan bir gende primerler kopyadan da "
                 "ürün verebilir, özgüllük kontrolü yapın.",
                 f"WARNING: {sebep} This design has NO pseudogene / near-identical copy "
                 "warning and no exon/intron labels; in a gene with a copy the primers may "
                 "also amplify the copy, so check specificity.")
    return t(f"UYARI: {sebep} Bu tasarımda ekzon/intron etiketleri YOK.",
             f"WARNING: {sebep} This design has no exon/intron labels.")


def _open_maybe_gz(path):
    if path.lower().endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


# ------------------------------------------------------------------
# MANE
# ------------------------------------------------------------------
def _load_mane():
    """{surumsuz_NM: (durum, surumlu_NM)} - MANE Select / MANE Plus Clinical."""
    if _MANE_CACHE is not None:
        return _MANE_CACHE
    with _YUKLEME_KILIDI:
        return _load_mane_ham()


def _load_mane_ham():
    global _MANE_CACHE
    if _MANE_CACHE is not None:          # kilidi beklerken baskasi yuklemis olabilir
        return _MANE_CACHE
    m = {}
    if MANE_PATH and os.path.exists(MANE_PATH):
        try:
            with _open_maybe_gz(MANE_PATH) as f:
                f.readline()  # baslik
                for line in f:
                    c = line.rstrip("\n").split("\t")
                    if len(c) < 10:
                        continue
                    acc, status = c[5], c[9]
                    if acc.startswith("NM_") or acc.startswith("NR_"):
                        m[strip_version(acc)] = (status, acc)
        except _OKUMA_HATALARI:
            # Yarim liste SESSIZCE kullanilmaz: MANE onceligi eksik kalir, baska
            # transkript secilip ekzon numaralari degisirdi.
            raise _bozuk_tablo(t("MANE listesi", "The MANE list"), MANE_PATH)
    _MANE_CACHE = m
    return m


_GRCH38_ERISIM_CACHE = {}   # MANE dosya yolu -> {kromozom: (erisim, surum)}


def grch38_kromozom_erisimleri():
    """GRCh38 kromozom RefSeq erisimleri: {"17": ("NC_000017", 11), "X": ("NC_000023", 11), ...}.

    Kaynak: yerel MANE ozet dosyasi (MANE_PATH; annotations/MANE.summary.txt.gz), 11. sutun
    "GRCh38_chr" (ornek "NC_000017.11"). Dosyada her kromozom icin tek surum var (olculdu:
    NC_000001.11 ... NC_000024.10); yalniz NC_0000NN erisimleri alinir. MANE dosyasi yoksa ya da
    okunamazsa bos sozluk doner: surum KARSILASTIRILAMAZ (uydurma tablo kullanilmaz).
    GRCh37 icin yerelde dogrulanabilir bir erisim kaynagi yok, bu yuzden yalnizca GRCh38 listesi
    vardir."""
    yol = MANE_PATH
    if not yol or not os.path.exists(yol):
        return {}
    with _YUKLEME_KILIDI:
        if yol in _GRCH38_ERISIM_CACHE:
            return _GRCH38_ERISIM_CACHE[yol]
        sonuc = {}
        try:
            with _open_maybe_gz(yol) as f:
                f.readline()  # baslik
                for line in f:
                    c = line.rstrip(chr(10)).split(chr(9))
                    if len(c) < 11:
                        continue
                    m = re.fullmatch(r"NC_0000(\d\d)\.(\d+)", c[10].strip())
                    if not m:
                        continue
                    n = int(m.group(1))
                    krom = str(n) if 1 <= n <= 22 else {23: "X", 24: "Y"}.get(n)
                    if krom:
                        sonuc[krom] = ("NC_0000%02d" % n, int(m.group(2)))
        except _OKUMA_HATALARI:
            sonuc = {}          # bozuk dosya: karsilastirma yapilmaz (MANE okuma hatasi ayrica bildirilir)
        _GRCH38_ERISIM_CACHE[yol] = sonuc
        return sonuc


def strip_version(acc):
    """'NM_000546.6' -> 'NM_000546'."""
    return str(acc).strip().split(".")[0].upper()


# ------------------------------------------------------------------
# refGene okuma
# ------------------------------------------------------------------
def _parse_line(cols):
    """UCSC refGene satiri -> transkript sozlugu (1-tabanli, kapsayici koordinatlar)."""
    acc = cols[1]
    chrom = cols[2]
    strand = cols[3]
    tx_start = int(cols[4]) + 1           # UCSC 0-tabanli -> 1-tabanli
    tx_end = int(cols[5])
    cds_start0 = int(cols[6])
    cds_end = int(cols[7])
    starts = [int(x) + 1 for x in cols[9].rstrip(",").split(",") if x != ""]
    ends = [int(x) for x in cols[10].rstrip(",").split(",") if x != ""]
    gene = cols[12] if len(cols) > 12 else ""

    exons = sorted(zip(starts, ends))     # genomik artan
    coding = cds_start0 < cds_end         # NR_ transkriptlerde cdsStart == cdsEnd

    return {
        "acc": acc,
        "gene": gene,
        "chrom": chrom,
        "strand": strand,
        "tx_start": tx_start,
        "tx_end": tx_end,
        "cds_start_g": cds_start0 + 1 if coding else None,   # 1-tabanli, kapsayici
        "cds_end_g": cds_end if coding else None,
        "coding": coding,
        "exons": exons,
        "exon_count": len(exons),
    }


def _load_index(assembly):
    """refGene'i tamamen okuyup akesyon ve gen sembolu indeksleri kur (ilk cagrida)."""
    if assembly in _INDEX_CACHE:
        return _INDEX_CACHE[assembly]
    with _YUKLEME_KILIDI:
        return _load_index_ham(assembly)


def _load_index_ham(assembly):
    if assembly in _INDEX_CACHE:         # kilidi beklerken baskasi yuklemis olabilir
        return _INDEX_CACHE[assembly]

    path = ANNOT_PATHS.get(assembly, "")
    if not path or not os.path.exists(path):
        raise TranscriptError(t(
            f"{assembly} için transkript tablosu (refGene) bulunamadı. "
            "annotations/ klasörünü kontrol edin.",
            f"No transcript table (refGene) found for {assembly}. "
            "Check the annotations/ folder."))

    by_acc, by_gene = {}, {}
    ad = t("Transkript tablosu (refGene)", "The transcript table (refGene)")
    try:
        with _open_maybe_gz(path) as f:
            for line in f:
                cols = line.rstrip("\n").split("\t")
                if len(cols) < 11:
                    continue
                if not _PRIMARY_CHROM.match(cols[2]):
                    continue                      # alt-haplotip / patch kayitlari
                tx = _parse_line(cols)
                by_acc.setdefault(strip_version(tx["acc"]), []).append(tx)
                if tx["gene"]:
                    by_gene.setdefault(tx["gene"].upper(), []).append(tx)
    except _OKUMA_HATALARI:
        raise _bozuk_tablo(ad, path)
    if not by_acc:
        raise _bozuk_tablo(ad, path)

    idx = {"by_acc": by_acc, "by_gene": by_gene}
    _INDEX_CACHE[assembly] = idx
    return idx


_MANE_KONUM_CACHE = {}   # MANE dosya yolu -> {surumsuz_acc: (kromozom, bas, son)}


def _load_mane_konum():
    """GRCh38 MANE konumu: {surumsuz_NM: ("chr5", bas, son)} (1-tabanli, kapsayici).
    Kaynak: MANE ozet dosyasinin GRCh38_chr / chr_start / chr_end sutunlari. Konumu
    yama ya da alternatif iskelede olan transkript (NC_0000NN disi erisim) listeye
    GIRMEZ: o transkriptte eski kural (en uzun yayilim) kalir. Dosya yoksa ya da
    okunamazsa bos sozluk doner (hata MANE yuklemesinde ayrica bildirilir)."""
    yol = MANE_PATH
    if not yol or not os.path.exists(yol):
        return {}
    with _YUKLEME_KILIDI:
        if yol in _MANE_KONUM_CACHE:
            return _MANE_KONUM_CACHE[yol]
        sonuc = {}
        try:
            with _open_maybe_gz(yol) as f:
                f.readline()  # baslik
                for line in f:
                    c = line.rstrip("\n").split("\t")
                    if len(c) < 13 or not (c[5].startswith("NM_") or c[5].startswith("NR_")):
                        continue
                    m = re.fullmatch(r"NC_0000(\d\d)\.\d+", c[10].strip())
                    if not m:
                        continue
                    n = int(m.group(1))
                    krom = str(n) if 1 <= n <= 22 else {23: "X", 24: "Y"}.get(n)
                    if krom:
                        sonuc[strip_version(c[5])] = ("chr" + krom, int(c[11]), int(c[12]))
        except _OKUMA_HATALARI:
            sonuc = {}
        _MANE_KONUM_CACHE[yol] = sonuc
        return sonuc


def _en_uzun(rows):
    return max(rows, key=lambda r: (r["tx_end"] - r["tx_start"], r["exon_count"]))


def _lokus_sec(rows, assembly=None):
    """(secilen_satir, neden): neden None (tek satir), "mane" (GRCh38'de MANE konumuyla
    ortusen satir) ya da "uzun" (en uzun yayilim; birden cok satir var ve MANE konumu
    kullanilamadi: GRCh37, MANE disi transkript ya da MANE konumu yama iskelesinde).
    GRCh37 icin MANE konumu yoktur; o derlemede secim kurali uydurulmaz."""
    if len(rows) == 1:
        return rows[0], None
    if assembly == "GRCh38":
        konum = _load_mane_konum().get(strip_version(rows[0]["acc"]))
        if konum:
            krom, bas, son = konum
            ort = [r for r in rows if r["chrom"] == krom and r["tx_start"] <= son and r["tx_end"] >= bas]
            if ort:
                return max(ort, key=lambda r: (min(r["tx_end"], son) - max(r["tx_start"], bas),
                                               r["tx_end"] - r["tx_start"], r["exon_count"])), "mane"
    return _en_uzun(rows), "uzun"


def _pick_mapping(rows, assembly=None):
    """Ayni akesyon birden fazla yere eslenmisse (PAR, kopya bolgeler, SMN2, U2AF1...)
    GRCh38'de MANE konumuyla ortusen satiri, aksi halde en uzun genomik yayilimi
    olani sec."""
    return _lokus_sec(rows, assembly)[0]


def _lokus_notu(rows, secilen, neden, assembly):
    """Birden cok yere hizalanan transkriptte hangi lokusun kullanildigini ve oteki
    lokuslari soyleyen kisa not (TR/EN); MANE konumuyla secildiyse ya da tek satirsa None."""
    if neden != "uzun":
        return None

    def yaz(r):
        return f"{r['chrom']}:{r['tx_start']:,}-{r['tx_end']:,}"

    def yaz_tr(r):
        return f"{r['chrom']}:{tr_sayi(r['tx_start'])}-{tr_sayi(r['tx_end'])}"
    digerleri = [yaz(r) for r in rows if r is not secilen]
    ek = f" (+{len(digerleri) - 4})" if len(digerleri) > 4 else ""
    liste = "; ".join(digerleri[:4]) + ek
    liste_tr = "; ".join([yaz_tr(r) for r in rows if r is not secilen][:4]) + ek
    acc = strip_version(rows[0]["acc"])
    if assembly == "GRCh37":
        sebep_tr = "GRCh37 için MANE konumu olmadığından en uzun hizalama seçildi"
        sebep_en = "no MANE position exists for GRCh37, so the longest alignment was used"
    else:
        sebep_tr = "MANE konumu yok ya da yama iskelesinde olduğundan en uzun hizalama seçildi"
        sebep_en = "no usable MANE position (absent or on a patch scaffold), so the longest alignment was used"
    return t(
        f"{acc} genomda {len(rows)} yere hizalanıyor; {yaz_tr(secilen)} kullanıldı ({sebep_tr}). "
        f"Öteki lokuslar: {liste_tr}. Doğru lokus bu değilse koordinatı ve diziyi doğrulayın "
        "(bu ürün kopya lokusun dizisiyle aynı olmayabilir).",
        f"{acc} aligns to {len(rows)} places in the genome; {yaz(secilen)} was used ({sebep_en}). "
        f"Other loci: {liste}. If this is not the intended locus, verify the coordinate and the "
        "sequence (the product may differ from the sequence of the copy locus).")


def get_transcript(acc, assembly):
    """NM_ kodundan transkripti getir. Surum numarasi yok sayilir."""
    idx = _load_index(assembly)
    key = strip_version(acc)
    rows = idx["by_acc"].get(key)
    if not rows:
        raise TranscriptError(t(
            f"{acc} bu tabloda bulunamadı ({assembly}). Kodu kontrol edin veya "
            "gen sembolü ile arayın.",
            f"{acc} was not found in this table ({assembly}). Check the accession "
            "or search by gene symbol."))
    secilen, neden = _lokus_sec(rows, assembly)
    tx = dict(secilen)
    tx["locus_note"] = _lokus_notu(rows, secilen, neden, assembly)

    # Kullanicinin girdigi surum ile tablodaki durum (tabloda surum yok)
    asked = str(acc).strip()
    tx["requested_acc"] = asked
    tx["version_note"] = None
    if "." in asked:
        tx["version_note"] = t(
            f"refGene tablosunda sürüm numarası tutulmaz; {asked} kaydı "
            f"{strip_version(asked)} olarak eşleştirildi.",
            f"The refGene table does not keep version numbers; {asked} was matched "
            f"as {strip_version(asked)}.")

    mane = _load_mane().get(key)
    tx["mane_status"] = mane[0] if mane else None
    tx["mane_acc"] = mane[1] if mane else None
    # MANE dosyasi SURUMLU kimlik tasir; refGene tasimaz. Kullanicinin yazdigi
    # surum MANE'ninkinden farkliysa ekson yapisi ve c. numaralari farkli olabilir:
    # bilgi notu degil UYARI (inceleme bulgusu 21). MANE disi transkriptte surumu
    # karsilastiracak veri yok; orada eski not kalir.
    tx["version_warning"] = None
    if "." in asked and tx["mane_acc"] and tx["mane_acc"] != asked:
        tx["version_warning"] = t(
            f"UYARI: {asked} istendi, ancak tablodaki güncel kayıt {tx['mane_acc']} "
            "(MANE). Sürümler arasında ekzon yapısı ve c. numaraları değişmiş olabilir; "
            f"varyant {asked} üzerinden bildirildiyse koordinatı {tx['mane_acc']} için "
            "doğrulayın (ör. Mutalyzer / VariantValidator).",
            f"WARNING: {asked} was requested, but the current record in the table is "
            f"{tx['mane_acc']} (MANE). Exon structure and c. numbering may differ between "
            f"versions; if the variant was reported on {asked}, verify the coordinate for "
            f"{tx['mane_acc']} (e.g. Mutalyzer / VariantValidator).")
    _annotate_cdna(tx)
    return tx


def find_by_gene(symbol, assembly):
    """Gen sembolunden transkript listesi. MANE Select en uste gelir."""
    idx = _load_index(assembly)
    rows = idx["by_gene"].get(str(symbol).strip().upper(), [])
    if not rows:
        raise TranscriptError(t(f"Gen bulunamadı: {symbol} ({assembly})",
                              f"Gene not found: {symbol} ({assembly})"))

    mane = _load_mane()
    seen, out = set(), []
    for tx in rows:
        key = strip_version(tx["acc"])
        if key in seen:
            continue
        seen.add(key)
        # ayni NM_ birden cok yere hizalanmissa liste de get_transcript'in kullanacagi
        # lokusu gostersin (gen indeksindeki ilk satir yanlis kopya olabilir)
        tx = _pick_mapping(idx["by_acc"].get(key) or [tx], assembly)
        m = mane.get(key)
        cdna_len = sum(e - s + 1 for s, e in tx["exons"])
        out.append({
            "acc": tx["acc"],
            "mane_acc": m[1] if m else None,        # surumlu hali (varsa)
            "gene": tx["gene"],
            "chrom": tx["chrom"],
            "strand": tx["strand"],
            "exon_count": tx["exon_count"],
            "cdna_length": cdna_len,
            "coding": tx["coding"],
            "mane_status": m[0] if m else None,
        })

    def sort_key(t):
        rank = {"MANE Select": 0, "MANE Plus Clinical": 1}.get(t["mane_status"], 2)
        return (rank, -t["cdna_length"])

    out.sort(key=sort_key)
    return out


# ------------------------------------------------------------------
# cDNA koordinat sistemi
# ------------------------------------------------------------------
def _annotate_cdna(tx):
    """Transkript sirasina gore ekson listesi, cDNA uzunlugu, ekson sinir
    ofsetleri ve CDS ofsetlerini hesapla (hepsi 0-tabanli cDNA indeksi)."""
    exons_tx = tx["exons"] if tx["strand"] == "+" else list(reversed(tx["exons"]))
    tx["exons_tx"] = exons_tx                      # transkript sirasi: ekson 1, 2, ...

    offsets, junctions, pos = [], [], 0
    for s, e in exons_tx:
        ln = e - s + 1
        offsets.append((pos, pos + ln - 1))        # eksonun cDNA'daki [ilk, son] indeksi
        pos += ln
        junctions.append(pos)                      # sinir: bu indeksten onceki baz ekson sonu
    tx["exon_cdna_spans"] = offsets
    tx["cdna_length"] = pos
    tx["junctions"] = junctions[:-1]               # son ekson sonrasi sinir yok

    if tx["coding"]:
        first_g = tx["cds_start_g"] if tx["strand"] == "+" else tx["cds_end_g"]
        last_g = tx["cds_end_g"] if tx["strand"] == "+" else tx["cds_start_g"]
        tx["cds_offset"] = genomic_to_cdna(tx, first_g)   # c.1'in cDNA indeksi
        tx["cds_end_offset"] = genomic_to_cdna(tx, last_g)  # stop kodonun son bazi
    else:
        tx["cds_offset"] = None
        tx["cds_end_offset"] = None
    return tx


def genomic_to_cdna(tx, gpos):
    """1-tabanli genomik koordinat -> 0-tabanli cDNA indeksi. Intronik/disarida ise None."""
    gpos = int(gpos)
    consumed = 0
    for s, e in tx["exons_tx"]:
        if s <= gpos <= e:
            off = (gpos - s) if tx["strand"] == "+" else (e - gpos)
            return consumed + off
        consumed += e - s + 1
    return None


def cdna_to_genomic(tx, idx):
    """0-tabanli cDNA indeksi -> 1-tabanli genomik koordinat."""
    idx = int(idx)
    if idx < 0 or idx >= tx["cdna_length"]:
        return None
    consumed = 0
    for s, e in tx["exons_tx"]:
        ln = e - s + 1
        if idx < consumed + ln:
            off = idx - consumed
            return (s + off) if tx["strand"] == "+" else (e - off)
        consumed += ln
    return None


def exon_number_of(tx, idx):
    """cDNA indeksi hangi eksonda (1-tabanli, transkript sirasi)?"""
    for n, (a, b) in enumerate(tx["exon_cdna_spans"], start=1):
        if a <= idx <= b:
            return n
    return None


# HGVS c. gosterimi: c.1234 | c.-45 | c.*120 | c.123+45 | c.124-8 | c.76_78del
_C_RE = re.compile(
    r"""^\s*(?:c\.)?
        (?P<utr5>-)?
        (?P<utr3>\*)?
        (?P<num>\d+)
        (?P<intron>[+-]\d+)?
    """, re.VERBOSE | re.IGNORECASE)


def _intronik_hatasi(c_str, ne):
    return TranscriptError(t(
        f"{c_str} intronik bir konum ({ne}). "
        "İntronlar mRNA'da bulunmaz; bu varyant için DNA sekmesini kullanın.",
        f"{c_str} is an intronic position ({ne}). "
        "Introns are not present in mRNA; use the DNA tab for this variant."))


def _c_ucu(tx, parca, c_str):
    """Tek bir c. konumu -> (cDNA indeksi, gosterim, intron ofseti|None).
    Intronik konumda indeks, ofsetin baglandigi EKZONIK bazdir (c.123+5 -> c.123)."""
    m = _C_RE.match(parca)
    if not m:
        raise TranscriptError(t(
            f"c. koordinatı anlaşılamadı: {c_str}  (örnek: c.1234, c.-45, c.*120)",
            f"Could not parse the c. coordinate: {c_str}  (e.g. c.1234, c.-45, c.*120)"))
    # Konumdan sonra yalnizca HGVS eki (del, dup, insAT, A ...) gelebilir. Eskiden kalan
    # her sey sessizce atiliyordu: "c.1.234" (Turkce binlik yazimi) c.1, "c.1 234" c.1,
    # "400.9" c.400 oluyordu - tasarim yanlis yerde yapiliyordu (2026-10-29).
    kalan = parca[m.end():].strip()
    ek = kalan[:-1] if kalan.endswith("=") else kalan     # 'c.76=' : HGVS "degisiklik yok"
    if ek and not ek.isalpha():
        if re.match(r"[.,\s]?\d", kalan):
            # Binlik yazimi gibi duruyor ("c.1.234", "c.1 234"): ipucu buna yonelik
            raise TranscriptError(t(
                f"c. koordinatının sonunda anlaşılamayan kısım var: '{kalan}' (girilen: {c_str}). "
                "Binlik ayırıcı ya da boşluk kullanmayın: örn. c.1234, c.76_78del.",
                f"The c. coordinate has an unreadable trailing part: '{kalan}' (got {c_str}). "
                "Do not use thousands separators or spaces: e.g. c.1234, c.76_78del."))
        raise TranscriptError(t(
            f"c. koordinatının sonunda anlaşılamayan kısım var: '{kalan}' (girilen: {c_str}). "
            "Konumdan sonra yalnızca değişiklik yazılabilir: örn. c.76A>T, c.76_78del, c.76dup.",
            f"The c. coordinate has an unreadable trailing part: '{kalan}' (got {c_str}). "
            "Only the change may follow the position: e.g. c.76A>T, c.76_78del, c.76dup."))
    num = int(m.group("num"))
    if num == 0 and (m.group("utr5") or m.group("utr3")):
        # c.-0 / c.*0 HGVS'te yok; eskiden c.1'e ve son kodlayan baza sessizce
        # ceviriliyordu (2026-10-31 hata taramasi).
        raise TranscriptError(t(
            f"{c_str} geçerli bir konum değil: 5' UTR c.-1'den (c.1'den önceki baz), 3' UTR "
            "c.*1'den (durdurma kodonundan sonraki ilk baz) başlar.",
            f"{c_str} is not a valid position: the 5' UTR starts at c.-1 (the base before "
            "c.1) and the 3' UTR at c.*1 (the first base after the stop codon)."))
    if m.group("utr5"):
        idx = tx["cds_offset"] - num                 # c.-1 = ATG'den bir onceki baz
        yazi = f"-{num}"
    elif m.group("utr3"):
        idx = tx["cds_end_offset"] + num             # c.*1 = stop kodondan sonraki baz
        yazi = f"*{num}"
    else:
        if num < 1:
            raise TranscriptError(t("c. numarası 1'den küçük olamaz.",
                                    "The c. number cannot be smaller than 1."))
        idx = tx["cds_offset"] + num - 1
        yazi = f"{num}"
    if idx < 0 or idx >= tx["cdna_length"]:
        raise TranscriptError(t(
            f"{c_str} transkript sınırları dışında ({tx['acc']}, cDNA uzunluğu "
            f"{tx['cdna_length']} nt).",
            f"{c_str} is outside the transcript ({tx['acc']}, cDNA length "
            f"{tx['cdna_length']} nt)."))
    intron = m.group("intron")
    return idx, yazi + (intron or ""), intron


def parse_c_range(tx, c_str):
    """
    HGVS c. gosterimini 0-tabanli, kapsayici cDNA araligina cevir.
    Doner: (bas_indeksi, bit_indeksi, aciklama). Tek konumda bas == bit.

    'c.76_78del' gibi araliklarin IKI ucu da okunur. Eskiden yalnizca ilk konum
    aliniyordu: DNA sekmesinde 2026-10-25'te duzeltilen hatanin aynisi - cok bazli
    varyantta primer varyantin icine dusebiliyor, o primer varyantli alele
    baglanmadigi icin heterozigot ornek homozigot gorunuyordu.

    Intronik konum: tek konumsa hata (mRNA'da intron yok). Araligin bir ucu
    intronda ise varyantin EKZONIK kismi alinir (c.123_124+5del -> c.123..c.124);
    tamami intronda kaliyorsa yine hata.
    """
    s = str(c_str).strip()
    if not s:
        raise TranscriptError(t("c. koordinatı boş.", "The c. coordinate is empty."))
    # 'c.123A>G' -> yalnizca konum kismi
    parcalar = s.split(">")[0].split("_")
    if len(parcalar) > 2:
        raise TranscriptError(t(
            f"c. koordinatı anlaşılamadı: {c_str}  (örnek: c.1234, c.76_78del)",
            f"Could not parse the c. coordinate: {c_str}  (e.g. c.1234, c.76_78del)"))
    if len(parcalar) == 1:
        m = _C_RE.match(parcalar[0])
        if m and m.group("intron"):
            raise _intronik_hatasi(c_str, f"{m.group('num')}{m.group('intron')}")

    if not tx["coding"]:
        raise TranscriptError(t(
            f"{tx['acc']} kodlamayan bir transkript (NR_); c. gösterimi tanımsız.",
            f"{tx['acc']} is a non-coding transcript (NR_); c. notation is undefined."))

    uclar = [_c_ucu(tx, x, c_str) for x in parcalar]
    if len(uclar) == 1:
        idx, yazi, _ = uclar[0]
        ek = " (5'UTR)" if yazi.startswith("-") else " (3'UTR)" if yazi.startswith("*") else ""
        return idx, idx, f"c.{yazi}{ek}"

    (i1, y1, in1), (i2, y2, in2) = uclar
    # Ekzonik kisim: c.100+5 intron 'sonrasinda' -> ilk ekzonik baz c.101;
    # c.101-5 intron 'oncesinde' -> ilk ekzonik baz c.101. Bitis ucu tersine.
    bas = i1 + 1 if (in1 and in1.startswith("+")) else i1
    bit = i2 - 1 if (in2 and in2.startswith("-")) else i2
    if i2 < i1:
        raise TranscriptError(t(
            f"{c_str}: aralığın bitişi başlangıcından önce geliyor.",
            f"{c_str}: the end of the range comes before its start."))
    if bit < bas:
        raise _intronik_hatasi(c_str, f"{y1}_{y2}")
    return bas, bit, f"c.{y1}_{y2}"


# Tek baz degisimi: c.524A>G | c.-45C>T | c.*120G>A (intronik konum ve del/dup/ins disarida)
_C_SNV_RE = re.compile(r"^\s*(?:c\.)?(?P<konum>[-*]?\d+)\s*(?P<ref>[ACGTU])\s*>\s*(?P<alt>[ACGTU])\s*$",
                       re.IGNORECASE)


def c_referans_uyarisi(tx, c_str, cdna):
    """A2-01: 'c.NNNX>Y' yazildiysa X, transkriptin (transkript yonundeki) c.NNN bazi ile
    ayni mi? Uyusmuyorsa kullaniciya gosterilecek uyari metni, uyusuyorsa (ya da girdi tek
    baz degisimi bicimi degilse: del/dup/ins, aralik, intronik) None. Reddetmez: yalnizca uyarir.
    cdna: transkript yonunde cDNA dizisi (engine.build_cdna); indeks tx["cds_offset"]'e gore."""
    m = _C_SNV_RE.match(str(c_str))
    if not m:
        return None
    try:
        idx, yazi, _ = _c_ucu(tx, m.group("konum"), c_str)
    except TranscriptError:
        return None
    if not (0 <= idx < len(cdna)):
        return None
    girilen = m.group("ref").upper().replace("U", "T")
    gercek = cdna[idx].upper()
    if gercek not in "ACGT" or girilen == gercek:
        return None
    # Karsilastirilan sey NM dizisi degil, genom dizisinden kurulan transkripttir (K1):
    # metin kullaniciyi suclamaz; isaretli transkriptte kayma, saglamda referans genomun
    # NM'den farkli olabilecegi soylenir.
    asm = tx.get("rna_derleme") or "GRCh38"
    isaretli = (tx.get("kod_denetimi") or {}).get("isaretli")
    if isaretli:
        return t(
            f"Girilen referans baz ({girilen}), {asm} genom dizisinden kurulan {tx['acc']} "
            f"transkriptinde c.{yazi} konumundaki bazla ({gercek}) uyuşmuyor. Bu transkriptin "
            "genom hizalaması NM dizisiyle birebir olmayabilir (yukarıdaki uyarı): c. numarası "
            "kaymış olabilir, yani sorun sizin varyantınızda olmayabilir. NM dizisiyle "
            "karşılaştırın ya da DNA sekmesinde genomik koordinatla tasarlayın.",
            f"The reference base entered ({girilen}) does not match the base at c.{yazi} of "
            f"{tx['acc']} built from the {asm} genome sequence ({gercek}). This transcript's "
            "genome alignment may not match the NM sequence exactly (warning above): the c. "
            "number may be shifted, so the problem may not be in your variant. Compare with the "
            "NM sequence or design in the DNA tab with a genomic coordinate.")
    return t(
        f"Girilen referans baz ({girilen}), {asm} genom dizisinden kurulan {tx['acc']} "
        f"transkriptinde c.{yazi} konumundaki bazla ({gercek}) uyuşmuyor. Varyantı ve "
        "transkripti kontrol edin; referans genom bu konumda NM dizisinden farklı olabilir "
        "(ör. referansta varyantlı alel taşıyan yerler).",
        f"The reference base entered ({girilen}) does not match the base at c.{yazi} of "
        f"{tx['acc']} built from the {asm} genome sequence ({gercek}). Check the variant and "
        "the transcript; the reference genome may differ from the NM sequence at this position "
        "(e.g. sites where the reference carries a variant allele).")


def parse_c_position(tx, c_str):
    """Geriye donuk: (araligin ilk cDNA indeksi, aciklama). Bkz. parse_c_range."""
    bas, _bit, label = parse_c_range(tx, c_str)
    return bas, label


def transcript_summary(tx):
    """Arayuze donen sade transkript ozeti."""
    return {
        "acc": tx["acc"],
        "requested_acc": tx.get("requested_acc"),
        "version_note": tx.get("version_note"),
        "version_warning": tx.get("version_warning"),
        "mane_status": tx.get("mane_status"),
        "mane_acc": tx.get("mane_acc"),
        "gene": tx["gene"],
        "chrom": tx["chrom"],
        "strand": tx["strand"],
        "exon_count": tx["exon_count"],
        "cdna_length": tx["cdna_length"],
        "coding": tx["coding"],
        "cds_offset": tx.get("cds_offset"),
        "tx_start": tx["tx_start"],
        "tx_end": tx["tx_end"],
        "kod_denetimi": tx.get("kod_denetimi"),   # engine.kod_denetimi (K1); yoksa None
    }


# ------------------------------------------------------------------
# Konumdan gen bolgesi (ekzon / intron)  - "primer genin neresine oturuyor?"
# ------------------------------------------------------------------
_BOLGE_CACHE = {}


def _krom_adi(chrom):
    """'chr17' -> '17'; mitokondri tek ada: refGene 'chrM', Ensembl/motor 'MT'
    (inceleme bulgusu 17: mitokondri primerlerine bolge etiketi dusmuyordu)."""
    c = str(chrom).replace("chr", "")
    return "M" if c in ("M", "MT") else c


def _bolge_indeksi(assembly):
    """{kromozom: (baslangiclar, [(tx_start, tx_end, satir), ...], en_uzun)} -
    baslangica gore sirali. refGene zaten bellekte; burada yalnizca kromozom basina
    siralanmis bir gorunum kuruluyor (bir kez, assembly basina)."""
    if assembly in _BOLGE_CACHE:
        return _BOLGE_CACHE[assembly]
    with _YUKLEME_KILIDI:
        if assembly in _BOLGE_CACHE:
            return _BOLGE_CACHE[assembly]
        idx = _load_index(assembly)
        out = {}
        for rows in idx["by_acc"].values():
            for r in rows:
                out.setdefault(_krom_adi(r["chrom"]), []).append(
                    (r["tx_start"], r["tx_end"], r))
        for c, lst in out.items():
            lst.sort(key=lambda x: x[0])
            out[c] = ([x[0] for x in lst], lst, max(x[1] - x[0] for x in lst))
        _BOLGE_CACHE[assembly] = out
        return out


def _kesisen_transkriptler(bolgeler, chrom, a, b):
    """[a, b] ile kesisen transkript satirlari. Eskiden kromozomdaki BUTUN
    transkriptler her primer icin taraniyordu (inceleme bulgusu 17); baslangica
    gore ikili arama + en uzun transkript payi ile yalnizca aday dilim taranir."""
    kayit = bolgeler.get(_krom_adi(chrom))
    if not kayit:
        return []
    baslar, lst, en_uzun = kayit
    i = bisect.bisect_left(baslar, a - en_uzun)
    j = bisect.bisect_right(baslar, b)
    return [r for s, e, r in lst[i:j] if s <= b and a <= e]


def _transkript_sec(adaylar):
    """Ekzon numarasi TRANSKRIPTE gore degisir; o yuzden tek bir transkript secilir
    ve hangisi oldugu kullaniciya yazilir. Oncelik: MANE Select > MANE Plus Clinical
    > kodlayan ve en cok ekzonlu > en cok ekzonlu."""
    mane = _load_mane()

    def sira(r):
        durum = (mane.get(strip_version(r["acc"])) or (None,))[0]
        return (0 if durum == "MANE Select" else 1 if durum == "MANE Plus Clinical" else 2,
                0 if r["coding"] else 1,
                -r["exon_count"],
                r["acc"])
    return sorted(adaylar, key=sira)[0]


def _ekzonlar_tx(r):
    """Transkript sirasinda ekzonlar (ekzon 1 bastadir)."""
    return r["exons"] if r["strand"] == "+" else list(reversed(r["exons"]))


def konum_bolgesi(assembly, chrom, start, end=None):
    """Genomik aralik genin neresine denk geliyor?

    Doner: None (transkript tablosu yok / uygun transkript yok) ya da
      {"gene", "acc", "mane", "strand", "kind": "ekzon"|"intron"|"sinir"|"dis",
       "exon", "intron", "exon_count", "label_tr", "label_en"}

    'sinir': aralik bir ekzon-intron sinirini asiyor. Genomik tasarimda bu sorun
    degil (sablon gDNA), ama kullanicinin bilmesi gerekir: RNA/cDNA'da o primer
    ayni bicimde baglanmaz.
    """
    try:
        bolgeler = _bolge_indeksi(assembly)
        _load_mane()                 # bozuk MANE burada yakalansin (etiket bilgi amacli)
    except TranscriptError:
        return None
    a = int(start)
    b = int(end if end is not None else start)
    if b < a:
        a, b = b, a
    adaylar = _kesisen_transkriptler(bolgeler, chrom, a, b)
    if not adaylar:
        return None
    r = _transkript_sec(adaylar)
    mane = (_load_mane().get(strip_version(r["acc"])) or (None,))[0]
    ekz = _ekzonlar_tx(r)

    kesisen = [n for n, (es, ee) in enumerate(ekz, start=1) if es <= b and a <= ee]
    # Arayuz etiketi KENDI kurar (TR/EN dugmesi sonuclari yeniden cizerken
    # sunucudan gelen metin eski dilde kalirdi). label_tr/label_en yine doner:
    # CSV ve API icin hazir metin, ayrica bilinmeyen bir kind'a karsi yedek.
    sonuc = {"gene": r["gene"], "acc": r["acc"], "mane": mane, "strand": r["strand"],
             "exon_count": len(ekz), "exon": None, "exon_to": None,
             "intron": None, "side": None}

    if len(kesisen) > 1:
        # Birden cok ekzona degiyor: arada en az bir intron var (kisa intron)
        sonuc.update(kind="aralik", exon=kesisen[0], exon_to=kesisen[-1])
        sonuc["label_tr"] = f"ekzon {kesisen[0]}–{kesisen[-1]} arası"
        sonuc["label_en"] = f"exons {kesisen[0]}–{kesisen[-1]}"
        return sonuc
    if kesisen:
        n = kesisen[0]
        es, ee = ekz[n - 1]
        if a >= es and b <= ee:
            sonuc.update(kind="ekzon", exon=n)
            sonuc["label_tr"] = f"ekzon {n}"
            sonuc["label_en"] = f"exon {n}"
        else:
            # Ekzonun disina tasiyor. HANGI tarafa tastigini soyle: "ekzon 8 sınırı"
            # tek basina belirsizdi. Ekzon n'in transkript sirasindaki komsulari:
            # oncesi intron n-1, sonrasi intron n. Eksi iplikte genomik yon terstir.
            asagi = a < es            # genomik olarak ekzonun altina tasiyor
            komsu = (n - 1) if (asagi == (r["strand"] == "+")) else n
            if 1 <= komsu <= len(ekz) - 1:
                sonuc.update(kind="sinir", exon=n, intron=komsu)
                sonuc["label_tr"] = f"ekzon {n} / intron {komsu} sınırı"
                sonuc["label_en"] = f"exon {n} / intron {komsu} boundary"
            else:
                # Komsu intron yok: genin ilk ekzonunun oncesi ya da son ekzonunun sonrasi
                uc_tr = "gen başı" if komsu == 0 else "gen sonu"
                uc_en = "gene start" if komsu == 0 else "gene end"
                sonuc.update(kind="sinir", exon=n, side=("bas" if komsu == 0 else "son"))
                sonuc["label_tr"] = f"ekzon {n} / {uc_tr} sınırı"
                sonuc["label_en"] = f"exon {n} / {uc_en} boundary"
        return sonuc

    # Hicbir ekzona degmiyor: hangi iki ekzonun arasinda?
    for n in range(len(ekz) - 1):
        onceki, sonraki = ekz[n], ekz[n + 1]
        ara_bas = min(onceki[1], sonraki[1]) + 1
        ara_bit = max(onceki[0], sonraki[0]) - 1
        if ara_bas <= a and b <= ara_bit:
            sonuc.update(kind="intron", intron=n + 1)
            sonuc["label_tr"] = f"intron {n + 1}"
            sonuc["label_en"] = f"intron {n + 1}"
            return sonuc
    # Transkript sinirlari icinde ama ekzon/intron agina girmiyor (nadir)
    sonuc.update(kind="dis")
    sonuc["label_tr"] = "gen gövdesi dışı"
    sonuc["label_en"] = "outside the gene body"
    return sonuc
