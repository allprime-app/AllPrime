# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""
AllPrime - Cekirdek Motor
=========================================
Varyanta ozgu genomik koordinat -> varyanti cevreleyen en iyi primer ciftleri.

- Hesaplama: primer3 (SantaLucia 1998 NN Tm + tuz/Mg/dNTP duzeltmeleri,
  termodinamik hairpin/dimer hizalama - ntthal). Sektor standardi.
- Dizi kaynagi: oncelik YEREL FASTA (pyfaidx, GRCh37/GRCh38), yoksa Ensembl REST API.
- Strand/transkript haritalamasi YOK: primerler dogrudan genomik (+) sarmal uzerinde
  tasarlanir; forward = (+) sarmal, reverse = (-) sarmal. (Eski koddaki en kirilgan kisim.)
"""

import os
import re
import sys
import glob
import json
import threading
import time
import requests
from functools import lru_cache

import primer3

import ayarlar
import transcripts as tr
import dbsnp
import specificity as S
import par
import paralog
from lang import t, tr_sayi, warn_prefix

try:
    from pyfaidx import Fasta
    _HAS_PYFAIDX = True
except Exception:  # pragma: no cover
    _HAS_PYFAIDX = False


# ------------------------------------------------------------------
# primer3 saglik kontrolu
# ------------------------------------------------------------------
# primer3'un __init__'i derlenmis modul yuklenemezse hatayi YUTAR: motor normal
# acilir, ilk tasarimda "module 'primer3' has no attribute 'calc_tm'" gibi
# anlamsiz bir hata cikar. Gercekte iki kez yasandi: Windows Akilli Uygulama
# Denetimi primer3'un dosyasini engelledi (2026-10-01 ve 10-10), OneDrive'in
# yarim tasimasinda ise parametre dosyalari (primer3_config) eksik kalmisti.
# Acilista bilerek denenir; sebep /health'te bildirilir, primer3 isteyen uclar
# anlasilir bir mesajla kesilir (server.py), arayuz kirmizi uyari gosterir.
def _primer3_dene():
    try:
        from primer3 import thermoanalysis  # noqa: F401  (yutulan hatayi gorunur kilar)
        primer3.calc_tm("GCTGAGGAAGTTGGTGACCA")   # parametre dosyalari burada okunur
        return {"ok": True, "tur": None, "ham": None}
    except Exception as e:
        ham = f"{type(e).__name__}: {e}"
        return {"ok": False, "tur": primer3_hata_turu(ham), "ham": ham}


def primer3_hata_turu(ham):
    """Ham hata metninden sebep: 'sac' | 'eksik' | 'diger'."""
    h = str(ham).lower()
    if "uygulama denetimi" in h or "application control" in h or "4551" in h:
        return "sac"
    if "thermodynamic config" in h or "primer3_config" in h:
        return "eksik"
    return "diger"


def primer3_mesaji(durum=None):
    """Kullaniciya gosterilecek aciklama; primer3 calisiyorsa None."""
    d = durum or PRIMER3_DURUM
    if d["ok"]:
        return None
    etki_tr = "Tasarım ve Değerlendir sekmeleri çalışmaz."
    etki_en = "The design and evaluation tabs will not work."
    if d["tur"] == "sac":
        return t(
            "Hesaplama motoru (primer3) yüklenemedi: Windows Akıllı Uygulama Denetimi "
            f"primer3'ün dosyasını engelledi. {etki_tr} Çözüm: Windows Güvenliği → Uygulama "
            "ve tarayıcı denetimi → Akıllı Uygulama Denetimi ayarları → Kapalı; ardından "
            "AllPrime'ı kapatıp yeniden açın.",
            "The calculation engine (primer3) could not be loaded: Windows Smart App "
            f"Control blocked primer3's file. {etki_en} Fix: Windows Security → App & "
            "browser control → Smart App Control settings → Off; then close and reopen "
            "AllPrime.")
    if d["tur"] == "eksik":
        return t(
            "Hesaplama motoru (primer3) yüklenemedi: parametre dosyaları (primer3_config) "
            f"eksik. Uygulama klasörü eksik kopyalanmış olabilir; klasörü yeniden kopyalayın. "
            f"{etki_tr}",
            "The calculation engine (primer3) could not be loaded: its parameter files "
            "(primer3_config) are missing. The application folder may have been copied "
            f"incompletely; copy it again. {etki_en}")
    return t(f"Hesaplama motoru (primer3) yüklenemedi: {d['ham']}. {etki_tr}",
             f"The calculation engine (primer3) could not be loaded: {d['ham']}. {etki_en}")


PRIMER3_DURUM = _primer3_dene()


# ------------------------------------------------------------------
# Genom kayit defteri: assembly -> yerel FASTA yolu
# Genom dosyalari indirilince buraya (veya ortam degiskeniyle) tanitilir.
# ------------------------------------------------------------------
GENOME_PATHS = {
    "GRCh38": os.environ.get("ALLPRIME_GENOME_GRCH38", ""),
    "GRCh37": os.environ.get("ALLPRIME_GENOME_GRCH37", ""),
}

# Kayitli genom yolu icin alt sinir: insan genomu FASTA'si ~3 GB'dir, bunun
# altindaki bir dosya yanlis/bozuk demektir (test dosyasi, yarim indirme vb.).
MIN_GENOME_BYTES = 100 * 1024 * 1024

# Reddedilen genom yollari: yol -> sebep. "Genom neden gorunmuyor?" sorusu
# disaridan bakarak cevaplanamiyordu; reddi sebebiyle birlikte saklamak sart.
GENOME_REJECTED = {}


def fai_tutarli(fasta_path):
    """FASTA'nin .fai indeksi tam ve bu dosyaya ait mi? pyfaidx indeksi okudukca
    yazar; yarida kesilirse son kromozomlar eksik kalir ve rebuild=False ile oyle
    kullanilir. Tam indekste SON kaydin bittigi bayt dosyanin sonuna denk gelir.
    Kayitlarin bu dosyaya ait olup olmadigini specificity.fai_denetle sinar."""
    return S.fai_denetle(fasta_path) == "tamam"


# Bilinen ana kromozom uzunluklari (bp), 1-22, X, Y. Kaynak: bu makinedeki gercek genom
# .fai dosyalari (olculdu 2026-11-10): Homo_sapiens.GRCh37.dna.primary_assembly.fa.fai ve
# Homo_sapiens.GRCh38.dna.primary_assembly.fa.fai (kurulum klasorunun genomes altinda;
# Ensembl primary_assembly). 1-22, X, Y uzunluklari ayni derlemede saglayicilar arasinda
# aynidir (UCSC "chr1" = Ensembl "1"): genel bilgi, yerelde yalniz Ensembl dosyasiyla dogrulandi.
# Alt/random/Un contig'leri, yamalar ve haplotipler saglayiciya gore degisir: denetime KATILMAZ.
ANA_KROMOZOM_UZUNLUK = {
    "GRCh37": {"1": 249250621, "2": 243199373, "3": 198022430, "4": 191154276, "5": 180915260,
               "6": 171115067, "7": 159138663, "8": 146364022, "9": 141213431, "10": 135534747,
               "11": 135006516, "12": 133851895, "13": 115169878, "14": 107349540,
               "15": 102531392, "16": 90354753, "17": 81195210, "18": 78077248, "19": 59128983,
               "20": 63025520, "21": 48129895, "22": 51304566, "X": 155270560, "Y": 59373566},
    "GRCh38": {"1": 248956422, "2": 242193529, "3": 198295559, "4": 190214555, "5": 181538259,
               "6": 170805979, "7": 159345973, "8": 145138636, "9": 138394717, "10": 133797422,
               "11": 135086622, "12": 133275309, "13": 114364328, "14": 107043718,
               "15": 101991189, "16": 90338345, "17": 83257441, "18": 80373285, "19": 58617616,
               "20": 64444167, "21": 46709983, "22": 50818468, "X": 156040895, "Y": 57227415},
}
# Mitokondri: iki derlemede de YALNIZ rCRS (NC_012920.1, 16.569 bp; bu makinedeki iki .fai'de
# olculdu). UCSC hg19'un eski chrM dizisi (NC_001807, 16.571 bp; genel bilgi, yerelde
# dogrulanmadi) rCRS degildir: kullanici karari (2026-11-10) geregi GRCh37'de de KABUL EDILMEZ.
MT_UZUNLUK = {"GRCh37": (16569,), "GRCh38": (16569,)}
ESKI_HG19_CHRM = 16571
# Derleme ayrimi (yanlis derleme) yalniz uzunlugu iki derlemede de farkli uc kromozoma bakar;
# ANA_KROMOZOM_UZUNLUK'un alt kumesidir.
_DERLEME_KROMOZOMLARI = ("1", "17", "X")
DERLEME_UZUNLUK = {asm: {k: ANA_KROMOZOM_UZUNLUK[asm][k] for k in _DERLEME_KROMOZOMLARI}
                   for asm in ANA_KROMOZOM_UZUNLUK}
_DERLEME_ONBELLEK = {}      # yol -> (fai imzasi, {kromozom: uzunluk} | None)


def _kromozom_adi(ad):
    """'chr1' -> '1', 'chrM'/'M' -> 'MT' (yalniz karsilastirma icin)."""
    a = ad[3:] if ad[:3].lower() == "chr" else ad
    a = a.upper() if a.upper() in ("X", "Y", "MT", "M") else a
    return "MT" if a == "M" else a


def _fai_uzunluklari(path):
    """.fai'den ana kromozomlarin (1-22, X, Y, MT; 'chr' oneki olsa da) uzunluklari; .fai
    okunamazsa None. Yalniz .fai okunur (FASTA'ya dokunulmaz); .fai imzasiyla onbelleklenir."""
    imza = S.fai_imzasi(path)
    eski = _DERLEME_ONBELLEK.get(path)
    if eski and eski[0] == imza:
        return eski[1]
    out = {}
    try:
        with open(path + ".fai", "r", encoding="utf-8", errors="replace") as f:
            for satir in f:
                c = satir.rstrip("\r\n").split("\t")
                if len(c) < 2:
                    continue
                ad = _kromozom_adi(c[0])
                if (ad in ANA_KROMOZOM_UZUNLUK["GRCh38"] or ad == "MT") and ad not in out:
                    out[ad] = int(c[1])
    except (OSError, ValueError):
        out = None
    _DERLEME_ONBELLEK[path] = (imza, out)
    return out


def derleme_denetle(path, asm):
    """FASTA'nin .fai kromozom uzunluklari `asm` derlemesine uyuyor mu?
    durum: "uyumlu" (bakilan hepsi uyuyor) | "karsi" (yalniz OBUR derlemeye uyuyor) |
           "bilinmiyor" (hicbirine uymuyor / karisik / adlar taninmadi; ozel genom olabilir) |
           "yok" (.fai yok ya da okunamadi: denetlenemez, reddedilmez).
    A6-01 (2026-11-09): GRCh37 FASTA'si GRCh38 yuvasina uyarisiz kabul ediliyor, tasarim yanlis
    derlemede yapiliyordu. Yalniz 1, 17, X'e bakar; eksik/kesik genom icin tamlik_mesaji."""
    tum = _fai_uzunluklari(path) if (asm in DERLEME_UZUNLUK and os.path.exists(path + ".fai")) else None
    if tum is None:
        return {"durum": "yok", "olcum": {}, "karsi": None}
    olc = {k: v for k, v in tum.items() if k in _DERLEME_KROMOZOMLARI}
    diger = "GRCh37" if asm == "GRCh38" else "GRCh38"
    bu = sum(1 for k, v in olc.items() if DERLEME_UZUNLUK[asm][k] == v)
    oteki = sum(1 for k, v in olc.items() if DERLEME_UZUNLUK[diger][k] == v)
    if oteki and not bu:
        durum = "karsi"
    elif olc and bu == len(olc):
        durum = "uyumlu"
    else:
        durum = "bilinmiyor"
    return {"durum": durum, "olcum": olc, "karsi": diger if durum == "karsi" else None}


def tamlik_sorunlari(path, asm):
    """Ana kromozomlarin (1-22, X, Y, MT) .fai'deki durumu `asm` icin tam mi?
    [(ad, beklenen, bulunan | None), ...]; bos liste = tam. .fai yoksa/okunamazsa None."""
    if asm not in ANA_KROMOZOM_UZUNLUK or not os.path.exists(path + ".fai"):
        return None
    tum = _fai_uzunluklari(path)
    if tum is None:
        return None
    sorun = []
    for ad, bek in ANA_KROMOZOM_UZUNLUK[asm].items():
        if tum.get(ad) != bek:
            sorun.append((ad, bek, tum.get(ad)))
    mt = MT_UZUNLUK[asm]
    if tum.get("MT") not in mt:
        sorun.append(("MT", mt, tum.get("MT")))
    return sorun


# Tamlik denetiminin uygulandigi en kucuk dosya boyutu. MIN_GENOME_BYTES'tan AYRI tutulur:
# eski testler MIN_GENOME_BYTES'i 0'a cekip kucuk yapay genomlar kaydeder; onlar etkilenmesin.
# Arayuzden, config.json'dan ya da ortam degiskeninden degistirilemez (yalnizca kod/test).
TAMLIK_MIN_BYTES = 100 * 1024 * 1024


def _bp_tr(n):
    return tr_sayi(n) + " bp"


def tamlik_mesaji(path, asm=None):
    """Genom eksik ya da kesik mi (D3-04)? Evetse kullaniciya donen mesaj, degilse None.
    Yalniz .fai okunur. Yalnizca gercek boyutlu dosyalara (>= TAMLIK_MIN_BYTES, 100 MB) uygulanir:
    kucuk dosya zaten genome_check'te reddedilir; testlerdeki yapay genomlar bu esigin altindadir.
    asm verilmezse dosya GENOME_PATHS'te hangi derlemeye kayitliysa ona bakilir.
    Obur derlemenin uzunluklari burada sorun SAYILMAZ (yanlis derleme ayri ele alinir)."""
    try:
        if os.path.getsize(path) < TAMLIK_MIN_BYTES:
            return None
    except OSError:
        return None
    adaylar = [asm] if asm else [a for a, y in GENOME_PATHS.items() if y and y == path]
    son = None
    for a in adaylar:
        if a not in ANA_KROMOZOM_UZUNLUK:
            continue
        if derleme_denetle(path, a)["durum"] == "karsi":
            return None
        sorun = tamlik_sorunlari(path, a)
        if sorun is None:
            continue
        if not sorun:
            return None
        son = _tamlik_metni(a, sorun)
    return son


def _tamlik_metni(asm, sorun):
    eski_mt = any(ad == "MT" and bul == ESKI_HG19_CHRM for ad, _, bul in sorun)
    if eski_mt and len(sorun) == 1:
        # Tek sorun eski hg19 chrM'si: genom kesik degil, mitokondri dizisi yanlis (rCRS degil)
        return t(
            f"Genomun mitokondri dizisi rCRS değil ({asm}): chrMT dosyada 16.571 bp; bu UCSC hg19'daki "
            "eski chrM dizisidir. Beklenen: rCRS (NC_012920.1, 16.569 bp). Mitokondride yanlış primer ve "
            "yanlış özgüllük sonucu vermemek için genom kullanılmadı. Mitokondrisi rCRS olan bir genom "
            "kullanın (ör. Ensembl GRCh37 primary_assembly).",
            f"The genome's mitochondrial sequence is not the rCRS ({asm}): chrMT in the file is 16,571 bp, "
            "the old UCSC hg19 chrM sequence. Expected: rCRS (NC_012920.1, 16,569 bp). To avoid wrong "
            "primers and wrong specificity results in the mitochondrion, the genome was not used. Use a "
            "genome with the rCRS mitochondrion (e.g. Ensembl GRCh37 primary_assembly).")
    parca_tr, parca_en = [], []
    for ad, bek, bul in sorun[:3]:
        if isinstance(bek, tuple):
            bek_tr = " ya da ".join(_bp_tr(x) for x in bek)
            bek_en = " or ".join(f"{x:,} bp" for x in bek)
        else:
            bek_tr, bek_en = _bp_tr(bek), f"{bek:,} bp"
        parca_tr.append(f"chr{ad} bekleniyor {bek_tr}, dosyada " +
                        (_bp_tr(bul) if bul is not None else "yok"))
        parca_en.append(f"chr{ad} expected {bek_en}, file has " +
                        (f"{bul:,} bp" if bul is not None else "none"))
    daha_tr = f" (toplam {len(sorun)} kromozom)" if len(sorun) > 3 else ""
    daha_en = f" ({len(sorun)} chromosomes in total)" if len(sorun) > 3 else ""
    y_tr = y_en = ""
    if any(ad == "Y" for ad, _, _ in sorun):
        y_tr = (" Y kromozomu eksik ya da kesik: erkek bir örnekte Y'deki yan ürünler kaçırılabilir, "
                "özgüllük sonucu güvenilmez olur.")
        y_en = (" Chromosome Y is missing or truncated: in a male sample, off-target products on Y could be "
                "missed and the specificity result would be unreliable.")
    if eski_mt:
        y_tr += " chrMT 16.571 bp: UCSC hg19'un eski chrM dizisi, rCRS (NC_012920.1, 16.569 bp) değil."
        y_en += " chrMT 16,571 bp: the old UCSC hg19 chrM sequence, not the rCRS (NC_012920.1, 16,569 bp)."
    return t(
        f"Genom eksik ya da kesik olabilir ({asm}): " + "; ".join(parca_tr) + daha_tr + "." + y_tr +
        " Eksik genomda özgüllük taraması yanlışlıkla \"özgül\" diyebileceği için genom "
        "kullanılmadı. Genomu yeniden indirin ya da kopyalayın.",
        f"The genome may be incomplete or truncated ({asm}): " + "; ".join(parca_en) + daha_en + "." +
        y_en + " A specificity scan on an incomplete genome could wrongly report \"specific\", so "
        "the genome was not used. Download or copy the genome again.")


def _uzunluk_metni_tr_en(uz):
    tr_ = ", ".join(f"{k}: {tr_sayi(n)} bp" for k, n in uz.items())
    en = ", ".join(f"{k}: {n:,} bp" for k, n in uz.items())
    return tr_, en


def derleme_karsi_mesaji(asm, d):
    """Yanlis derleme reddi: hangi derlemeye benzedigini ve neye bakildigini soyler."""
    diger = d["karsi"]
    olc = d["olcum"]
    o_tr, o_en = _uzunluk_metni_tr_en(olc)
    b_asm_tr, b_asm_en = _uzunluk_metni_tr_en({k: DERLEME_UZUNLUK[asm][k] for k in olc})
    b_dg_tr, b_dg_en = _uzunluk_metni_tr_en({k: DERLEME_UZUNLUK[diger][k] for k in olc})
    return t(
        f"Bu dosya {asm} olarak tanıtılmak istendi ama indeksindeki (.fai) kromozom uzunlukları "
        f"{diger} genomuna uyuyor ({o_tr}). Bilinen değerler: {asm} → {b_asm_tr}; "
        f"{diger} → {b_dg_tr}. Yanlış sürümde koordinatlar kayar ve tasarım yanlış yerde "
        f"yapılır; bu yüzden dosya kabul edilmedi. Dosyayı {diger} olarak tanıtın ya da "
        f"{asm} FASTA'sını seçin.",
        f"This file was offered as {asm}, but the chromosome lengths in its index (.fai) match "
        f"the {diger} genome ({o_en}). Known values: {asm} → {b_asm_en}; {diger} → {b_dg_en}. "
        f"In the wrong build coordinates shift and the design is made at the wrong place, so the "
        f"file was not accepted. Register it as {diger}, or choose the {asm} FASTA.")


def derleme_bilinmiyor_mesaji(asm, d):
    olc = d["olcum"]
    if olc:
        o_tr, o_en = _uzunluk_metni_tr_en(olc)
    else:
        o_tr = "1, 17 ve X kromozomları bulunamadı"
        o_en = "chromosomes 1, 17 and X were not found"
    return t(
        f"{asm} olarak tanıtılan genomun kromozom uzunlukları ({o_tr}) bilinen GRCh37 ya da "
        "GRCh38 değerleriyle tutmuyor. Özel ya da farklı adlandırılmış bir genom olabilir: "
        "sürümü doğrulanamadı, genom yine de kullanılıyor. Koordinatların bu dosyanın "
        "sürümüne ait olduğundan emin olun.",
        f"The chromosome lengths of the genome registered as {asm} ({o_en}) do not match the "
        "known GRCh37 or GRCh38 values. It may be a custom or differently named genome: its "
        "build could not be verified, and it is still used. Make sure your coordinates belong "
        "to this file's build.")


def genom_uyarisi(path, asm=None):
    """(engelli, uyari): engelli=True ise genom hicbir yolda kullanilmaz (kesik/yarim/uyusmuyor)."""
    parcalar = []
    engelli = False
    durum = S.fai_denetle(path)
    if durum in S.FAI_ENGEL:
        # Genom kayitli kalir ama okuma engellenir (_open_fasta_ham, S.read_fai): kayittan
        # dusurulse tasarim sessizce Ensembl'e giderdi. Sebep burada ve her istekte soylenir.
        engelli = True
        parcalar.append(S.fai_sorun_mesaji(path, durum))
    elif durum == "yok":
        # pyfaidx ilk acilista indeksi kendi kurar, ama 3 GB'lik dosyada bu
        # birkac dakika surer ve o sirada ozgulluk taramasi da calismaz.
        parcalar.append(t(
            "FASTA indeksi (.fai) yok. İlk kullanımda otomatik oluşturulacak; "
            "3 GB'lık dosyada bu birkaç dakika sürebilir. İndeks hazır olana "
            "kadar özgüllük kontrolü çalışmaz.",
            "The FASTA index (.fai) is missing. It will be built automatically on "
            "first use; for a 3 GB file this can take a few minutes. The specificity "
            "check will not work until the index is ready."))
    if asm and not engelli:      # kullanilmayan genomun surumu hakkinda ikinci bir uyari gereksiz
        d = derleme_denetle(path, asm)
        if d["durum"] == "karsi":      # kayit disi yoldan gelen genom
            parcalar.append(derleme_karsi_mesaji(asm, d))
        else:
            eksik = tamlik_mesaji(path, asm)      # D3-04: eksik/kesik genom kullanilmaz
            if eksik:
                engelli = True
                parcalar.append(eksik)
            elif d["durum"] == "bilinmiyor":
                parcalar.append(derleme_bilinmiyor_mesaji(asm, d))
    return engelli, (" ".join(parcalar) or None)


def genom_durumu(asm):
    """/health icin: {'var', 'engelli', 'uyari'}. Uyari istegin dilinde, her seferinde uretilir."""
    yol = GENOME_PATHS.get(asm, "") or ""
    if not yol or not os.path.exists(yol):
        return {"var": False, "engelli": False, "uyari": None}
    engelli, uyari = genom_uyarisi(yol, asm)
    return {"var": True, "engelli": engelli, "uyari": uyari}


def genome_check(path, asm=None):
    """Bir FASTA yolu kullanilabilir bir insan genomu mu? `asm` verilirse (GRCh37 / GRCh38)
    kromozom uzunluklari o derlemeyle de karsilastirilir; OBUR derlemeye uyan dosya reddedilir.
    Doner: {"ok": bool, "reason": str|None, "warning": str|None, "usable": bool}
    usable=False: genom kayitli kalabilir ama kullanilmaz (kesik/yarim/uyusmuyor .fai).

    Neden ayri fonksiyon: genom UC ayri kapidan tanitiliyor - kayitli ayar
    dosyasi, uygulama klasorunu otomatik tarama, ve kullanicinin elle secmesi.
    Dogrulama yalnizca bir kapida durunca digerlerinden bozuk dosya sizip
    "hicbir sey bulunamadi" seklinde SESSIZ bir hataya donusuyordu; bir tani
    aracinda en tehlikeli davranis budur.
    """
    if not path:
        return {"ok": False, "warning": None,
                "reason": t("Yol boş.", "The path is empty.")}
    if not os.path.exists(path):
        return {"ok": False, "warning": None,
                "reason": t(f"Dosya bulunamadı: {path}", f"File not found: {path}")}
    if not os.path.isfile(path):
        return {"ok": False, "warning": None,
                "reason": t(f"Bu bir dosya değil: {path}",
                            f"This is not a file: {path}")}
    # Sikistirilmis (gzip / bgzip) FASTA: uzantiya degil ilk iki bayta (1f 8b) bakilir.
    # Motor .fai ile dogrudan konum okur; sikistirilmis dosyada bu calismaz (BioPython yok).
    try:
        with open(path, "rb") as f:
            gz = f.read(2) == b"\x1f\x8b"
    except OSError as e:
        return {"ok": False, "warning": None,
                "reason": t(f"Dosya okunamadı: {e}", f"File could not be read: {e}")}
    if gz:
        return {"ok": False, "warning": None, "usable": False, "reason": t(
            "Sıkıştırılmış FASTA (.gz) desteklenmiyor. Dosyayı açıp (.fa) tanıtın; "
            "Veri dosyaları panelinden indirilen genom zaten açılmış gelir.",
            "Compressed FASTA (.gz) is not supported. Unpack the file and register "
            "the .fa; a genome downloaded from the Data files panel already comes unpacked.")}
    try:
        boyut = os.path.getsize(path)
    except OSError as e:
        return {"ok": False, "warning": None,
                "reason": t(f"Dosya okunamadı: {e}", f"File could not be read: {e}")}
    if boyut < MIN_GENOME_BYTES:
        mb = boyut / (1024 * 1024)
        return {"ok": False, "warning": None, "reason": t(
            f"Dosya yalnızca {mb:.1f} MB; insan genomu ~3 GB olmalı. Yarım inmiş "
            "ya da yanlış dosya seçilmiş olabilir.",
            f"The file is only {mb:.1f} MB; a human genome should be ~3 GB. It may "
            "be a partial download or the wrong file.")}

    if asm:
        d = derleme_denetle(path, asm)
        if d["durum"] == "karsi":
            return {"ok": False, "warning": None, "usable": False,
                    "reason": derleme_karsi_mesaji(asm, d)}
    engelli, uyari = genom_uyarisi(path, asm)
    return {"ok": True, "reason": None, "warning": uyari, "usable": not engelli}

# Kalici ayar dosyasi (%APPDATA%\AllPrime\config.json) - genom yollarini hatirlar.
# Electron'un kullanici klasoruyle ayni yer. Uygulama klasoru yazilamazsa indirilen
# veri de bunun altindaki data\ klasorune iner (downloads.data_root).
_AYAR_KOKU = os.environ.get("APPDATA", os.path.expanduser("~"))
CONFIG_DIR = os.path.join(_AYAR_KOKU, "AllPrime")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
# Uygulamanin onceki adiyla acilmis ayar klasoru: icindekiler acilista bir kez
# yukaridakine tasinir. Tasinmasa onceki surumlerde elle secilmis genom yollari ve
# oraya indirilmis veri sessizce kaybolurdu.
ESKI_CONFIG_DIR = os.path.join(_AYAR_KOKU, "EK-Primer")         # onceki-ad-uyumu


def eski_ayarlari_tasi(eski=None, yeni=None):
    """Eski ayar klasorunun icindekileri (config.json, data\\) yenisine tasir ve
    bosalan eski klasoru siler. Yenide ayni adli oge varsa ikisine de dokunulmaz,
    eski klasor de yerinde kalir. Tasinan oge adlarini dondurur."""
    eski = eski or ESKI_CONFIG_DIR
    yeni = yeni or CONFIG_DIR
    if not os.path.isdir(eski):
        return []
    tasinan = []
    try:
        os.makedirs(yeni, exist_ok=True)
        for ad in os.listdir(eski):
            hedef = os.path.join(yeni, ad)
            if not os.path.exists(hedef):
                os.replace(os.path.join(eski, ad), hedef)
                tasinan.append(ad)
        os.rmdir(eski)                  # bos degilse OSError: yenide ayni adli oge vardi
    except OSError:
        pass
    return tasinan


def load_config():
    """Acilista kayitli genom yollarini oku."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for asm in ("GRCh37", "GRCh38"):
            p = (cfg.get("genomes") or {}).get(asm, "")
            # ortam degiskeni onceligi korunur
            if not p or GENOME_PATHS.get(asm):
                continue
            k = genome_check(p, asm)
            if k["ok"]:
                GENOME_PATHS[asm] = p
            else:
                GENOME_REJECTED[p] = k["reason"]
    except (FileNotFoundError, ValueError, OSError):
        pass


def save_config():
    """Genom yollarini kalici kaydet."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"genomes": dict(GENOME_PATHS)}, f, indent=2)
    except OSError:
        pass



def config_diagnostics():
    """Ayar dosyasi okunurken NE OLDUGUNU raporlar. Genom 'gorunmuyor' dendiginde
    disaridan bakarak anlasilamiyordu; motorun kendi gozunden bakmak gerekiyor."""
    out = {"path": CONFIG_PATH, "exists": os.path.exists(CONFIG_PATH),
           "error": None, "entries": {}, "cwd": os.getcwd(),
           "appdata": os.environ.get("APPDATA", ""),
           "app_root": os.environ.get("ALLPRIME_APP_ROOT", ""),
           "rejected": dict(GENOME_REJECTED),
           "executable": sys.executable}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        return out
    for asm in ("GRCh37", "GRCh38"):
        p = (cfg.get("genomes") or {}).get(asm, "")
        d = {"config_path": p, "current": GENOME_PATHS.get(asm, "")}
        if p:
            try:
                d["exists"] = os.path.exists(p)
                d["size"] = os.path.getsize(p) if d["exists"] else 0
                d["min_required"] = MIN_GENOME_BYTES
            except Exception as e:
                d["error"] = f"{type(e).__name__}: {e}"
        out["entries"][asm] = d
    return out

def autodetect_genomes():
    """config.json olmadan da: exe'nin/uygulamanin yanindaki 'genomes\\' klasorunu
    otomatik bul. Boylece tum klasor baska bilgisayara kopyalaninca offline calisir.
    Sadece bos (config/env ile dolmamis) assembly'leri doldurur."""
    bases = []
    if os.environ.get("ALLPRIME_APP_ROOT"):
        bases.append(os.environ["ALLPRIME_APP_ROOT"])
    # PyInstaller onedir: sys.executable = ...\resources\backend\allprime-server.exe
    # Gelistirme: sys.executable = ...\.venv\Scripts\python.exe
    d = os.path.dirname(os.path.abspath(sys.executable))
    for _ in range(6):
        bases.append(d)
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    bases.append(os.path.dirname(os.path.abspath(__file__)))  # script yani (gelistirme)
    seen = set()
    for b in bases:
        if not b:
            continue
        rb = os.path.normpath(b)
        if rb in seen:
            continue
        seen.add(rb)
        gdir = os.path.join(rb, "genomes")
        if not os.path.isdir(gdir):
            continue
        for asm in ("GRCh38", "GRCh37"):
            if GENOME_PATHS.get(asm):
                continue
            matches = [p for p in glob.glob(os.path.join(gdir, "*.fa"))
                       if asm.lower() in os.path.basename(p).lower()]
            # ILK eslesmeyi degil, ilk GECERLI eslesmeyi al: yarim inmis bir
            # dosya (".fa" uzantili ama 40 MB) klasorde durabiliyor.
            for m in matches:
                k = genome_check(m, asm)
                if k["ok"]:
                    GENOME_PATHS[asm] = m
                    break
                GENOME_REJECTED[m] = k["reason"]


def _tamlik_kancasi(path):
    return tamlik_mesaji(path)


S.TAMLIK_KANCASI = _tamlik_kancasi      # specificity.fai_engeli her okumada tamligi da sorar


def ortam_genomlarini_denetle():
    """ALLPRIME_GENOME_* ortam degiskeniyle gelen yollar da config.json ve /set_genome gibi
    genome_check'ten gecer (D3-04): yarim/kucuk dosya ya da obur derlemenin dosyasi kayda girmez."""
    for asm in ("GRCh37", "GRCh38"):
        p = GENOME_PATHS.get(asm)
        if not p:
            continue
        k = genome_check(p, asm)
        if not k["ok"]:
            GENOME_REJECTED[p] = k["reason"]
            GENOME_PATHS[asm] = ""


eski_ayarlari_tasi()
ortam_genomlarini_denetle()
load_config()
autodetect_genomes()

ENSEMBL_SERVER = {
    "GRCh38": "https://rest.ensembl.org",
    "GRCh37": "https://grch37.rest.ensembl.org",
}

_FASTA_CACHE = {}


class PrimerError(Exception):
    """Kullaniciya gosterilebilir hata."""
    pass


# ------------------------------------------------------------------
# Dizi cekme
# ------------------------------------------------------------------
def normalize_chrom(chrom):
    """'chr1' -> '1', 'CHR X' -> 'X' vb. Ensembl tarzi cikti."""
    c = str(chrom).strip()
    c = re.sub(r"^chr", "", c, flags=re.IGNORECASE)
    c = c.upper() if c.upper() in ("X", "Y", "MT", "M") else c
    if c == "M":
        c = "MT"
    return c


_FASTA_KILIDI = threading.Lock()
_FASTA_IMZA = {}       # yol -> acildigi andaki FASTA/.fai imzasi (dosya degisirse yeniden ac)


def _open_fasta(path):
    if path in _FASTA_CACHE and _FASTA_IMZA.get(path) == S.fai_imzasi(path):
        return _FASTA_CACHE[path]
    with _FASTA_KILIDI:                # eszamanli ilk istekler ayni dosyayi iki kez acmasin
        return _open_fasta_ham(path)


def _open_fasta_ham(path):
    imza = S.fai_imzasi(path)
    if path not in _FASTA_CACHE or _FASTA_IMZA.get(path) != imza:
        if not _HAS_PYFAIDX:
            raise PrimerError(t("pyfaidx yüklü değil; yerel FASTA okunamıyor.",
                                "pyfaidx is not installed; local FASTA cannot be read."))
        if not os.path.exists(path):
            raise PrimerError(t(f"Genom dosyası bulunamadı: {path}",
                                f"Genome file not found: {path}"))
        # Eski/baska bir dosyanin .fai'si: pyfaidx onu oldugu gibi kullanir ve diziler
        # sessizce yanlis okunur (2026-10-31 hata taramasi). Acmadan once denetlenir;
        # dosya calisirken degisirse imza tutmaz ve buraya yeniden gelinir.
        # Kesik / yarim indeksli genom da acilmaz (A7-04): okunan dizi eksik genomdan gelirdi.
        engel = S.fai_engeli(path)
        if engel:
            _FASTA_CACHE.pop(path, None)
            raise PrimerError(engel)
        # as_raw=True -> duz string; sequence_always_upper -> buyuk harf
        _FASTA_CACHE[path] = Fasta(path, as_raw=True, sequence_always_upper=True,
                                   rebuild=False)
        # .fai ilk kez az once kurulduysa (kesik dosyadan da kurulabilir) tamlik hemen denetlenir (D3-04)
        engel = S.fai_engeli(path)
        if engel:
            _FASTA_CACHE.pop(path, None)
            raise PrimerError(engel)
        _FASTA_IMZA[path] = S.fai_imzasi(path)     # .fai az once kurulduysa yeni imza
    return _FASTA_CACHE[path]


def _fasta_key(fa, chrom):
    """FASTA icindeki dogru anahtari bul ('1' veya 'chr1')."""
    if chrom in fa:
        return chrom
    alt = "chr" + chrom
    if alt in fa:
        return alt
    # MT bazen 'chrM'
    if chrom == "MT" and "chrM" in fa:
        return "chrM"
    return None


def _kromozom_disi(assembly, chrom, pos, uzunluk):
    c = normalize_chrom(chrom)
    return PrimerError(t(
        f"Koordinat kromozomun dışında: chr{c}:{tr_sayi(pos)} — chr{c} {assembly} sürümünde "
        f"{tr_sayi(uzunluk)} bp. Koordinatı ve genom sürümünü (GRCh37 / GRCh38) kontrol edin; "
        "iki sürümün koordinatları farklıdır.",
        f"The coordinate is outside the chromosome: chr{c}:{pos:,} — chr{c} is "
        f"{uzunluk:,} bp in {assembly}. Check the coordinate and the genome build "
        "(GRCh37 / GRCh38); their coordinates differ."))


def kromozom_uzunlugu(assembly, chrom):
    """Yerel genomdaki kromozom boyu; yerel genom yoksa None."""
    path = GENOME_PATHS.get(assembly, "")
    if not path:
        return None
    fa = _open_fasta(path)
    key = _fasta_key(fa, normalize_chrom(chrom))
    if key is None:
        raise PrimerError(t(f"Kromozom FASTA'da bulunamadı: {chrom} ({assembly})",
                            f"Chromosome not found in the FASTA: {chrom} ({assembly})"))
    return len(fa[key])


def fetch_sequence_local(assembly, chrom, start, end):
    """1-tabanli, kapsayici [start, end] araligini yerel FASTA'dan dondurur.
    Aralik kromozom sonunu asiyorsa sonda kirpilir; tamamen disindaysa hata."""
    path = GENOME_PATHS.get(assembly, "")
    if not path:
        return None
    uzunluk = kromozom_uzunlugu(assembly, chrom)
    if start > uzunluk:
        raise _kromozom_disi(assembly, chrom, start, uzunluk)
    fa = _open_fasta(path)
    key = _fasta_key(fa, normalize_chrom(chrom))
    seq = str(fa[key][start - 1:min(end, uzunluk)]).upper()  # pyfaidx 0-tabanli yari-acik
    # Son savunma: okunan dizi istenen boyda ve yalnizca IUPAC harfleri mi? Indeks ile
    # dosya uyusmazsa satir sonlari / baska kayitlar diziye karisabilir.
    beklenen = min(end, uzunluk) - start + 1
    if seq and (len(seq) != beklenen or set(seq) - _GENOM_HARFLERI):
        raise PrimerError(t(
            f"Yerel genomdan okunan dizi beklenen biçimde değil ({assembly} "
            f"{normalize_chrom(chrom)}:{tr_sayi(start)}-{tr_sayi(min(end, uzunluk))}: {tr_sayi(len(seq))} baz "
            f"okundu, {tr_sayi(beklenen)} bekleniyordu ya da geçersiz karakter var). Genom dosyası "
            "ya da .fai indeksi bozuk olabilir; .fai dosyasını silip yeniden oluşturun.",
            f"The sequence read from the local genome is malformed ({assembly} "
            f"{normalize_chrom(chrom)}:{start:,}-{min(end, uzunluk):,}: {len(seq):,} bases "
            f"read, {beklenen:,} expected, or invalid characters). The genome file or its "
            ".fai index may be damaged; delete the .fai file so it is rebuilt."))
    return seq


_GENOM_HARFLERI = set("ACGTNRYKMSWBDHV")     # genom FASTA'sinda gecerli harfler (IUPAC)


def fetch_sequence_ensembl(assembly, chrom, start, end):
    """Yedek: Ensembl REST API'den dizi cek (internet gerekir)."""
    server = ENSEMBL_SERVER.get(assembly)
    if not server:
        raise PrimerError(t(f"Bilinmeyen assembly: {assembly}",
                            f"Unknown assembly: {assembly}"))
    c = normalize_chrom(chrom)
    ext = f"/sequence/region/human/{c}:{start}..{end}:1"
    try:
        r = requests.get(server + ext,
                         headers={"Content-Type": "text/plain"}, timeout=30)
    except requests.RequestException:
        raise PrimerError(t(
            f"Yerel genom tanıtılmadığı için dizi Ensembl'den istenecekti ama internete "
            f"ulaşılamadı ({assembly}). Veri dosyaları panelinden genomu indirin ya da "
            "internet bağlantısını kontrol edin.",
            f"No local genome is configured, so the sequence was to be fetched from "
            f"Ensembl, but the internet could not be reached ({assembly}). Download the "
            "genome from the data files panel or check the connection."))
    if not r.ok:
        raise PrimerError(t(
            f"Ensembl'den dizi alınamadı ({assembly} {c}:{start}-{end}; HTTP {r.status_code}). "
            "Yerel genom tanıtılmadığı için dizi internetten istendi, ama Ensembl isteği "
            "yanıtlamadı. İnternet bağlantınızı kontrol edip biraz sonra yeniden deneyin ya da "
            "Veri dosyaları panelinden genomu indirin.",
            f"Could not get the sequence from Ensembl ({assembly} {c}:{start}-{end}; HTTP "
            f"{r.status_code}). No local genome is configured, so the sequence was requested "
            "over the internet, but Ensembl did not answer the request. Check your internet "
            "connection and try again in a little while, or download the genome from the "
            "data files panel."))
    return r.text.strip().upper()


def get_sequence(assembly, chrom, start, end):
    """Yerel genom tanitilmissa YALNIZCA yerel FASTA; tanitilmamissa Ensembl API.

    Eskiden yerel okuma bos donunce (kromozom sonunu asan koordinat) sessizce
    Ensembl'e gidiliyordu: kullanici yerel genomla calistigini sanirken istek
    internete cikiyor, cevrimdisiyken "Beklenmeyen hata" goruyordu (2026-10-01
    rastgele testte bulundu). Yerel genom varken internete dusmek hicbir zaman
    dogru cevap degil - koordinat yanlistir ve bu soylenmeli."""
    if start < 1:
        start = 1
    if GENOME_PATHS.get(assembly, ""):
        local = fetch_sequence_local(assembly, chrom, start, end)
        if not local:
            raise PrimerError(t(
                f"Yerel genomdan dizi alınamadı ({assembly} {normalize_chrom(chrom)}:"
                f"{tr_sayi(start)}-{tr_sayi(end)}).",
                f"No sequence could be read from the local genome ({assembly} "
                f"{normalize_chrom(chrom)}:{start:,}-{end:,})."))
        return local, "local"
    return fetch_sequence_ensembl(assembly, chrom, start, end), "ensembl"


@lru_cache(maxsize=256)
def lookup_gene(gene_symbol, assembly):
    """Gen adindan kromozom + sinirlari bul (Ensembl). YEDEK yol: yalnizca
    transkript tablosu (refGene) indirilmemisse kullanilir - bkz. gen_konumu."""
    server = ENSEMBL_SERVER.get(assembly)
    ext = f"/lookup/symbol/homo_sapiens/{gene_symbol}?expand=0"
    try:
        r = requests.get(server + ext,
                         headers={"Content-Type": "application/json"}, timeout=30)
    except requests.RequestException:
        raise PrimerError(t(
            f"Transkript tablosu indirilmediği için {gene_symbol} Ensembl'de aranacaktı "
            "ama internete ulaşılamadı. Kromozomu elle girin ya da Veri dosyaları "
            "panelinden transkript tablosunu indirin.",
            f"The transcript table is not downloaded, so {gene_symbol} was to be looked "
            "up on Ensembl, but the internet could not be reached. Enter the chromosome "
            "or download the transcript table from the data files panel."))
    if not r.ok:
        raise PrimerError(t(f"Gen bulunamadı: {gene_symbol} ({assembly})",
                            f"Gene not found: {gene_symbol} ({assembly})"))
    d = r.json()
    return {
        "chrom": d.get("seq_region_name"),
        "start": d.get("start"),
        "end": d.get("end"),
        "strand": d.get("strand"),
        "id": d.get("id"),
    }


# Gen adi yazilip koordinat genin bu kadar DISINDA kalirsa uyari verilir. Sik
# hata: GRCh37 koordinati GRCh38 seciliyken (ya da tersi) girilir. Ornek: TP53
# hg19 ekson 8 koordinati hg38'de genin ~84 kb disina duser. Gen disi
# (duzenleyici bolge) varyantlar icin hata DEGIL uyaridir.
GEN_UZAKLIK_UYARI = 10_000


def gen_bolgeleri(sembol, assembly):
    """Yerel transkript tablosunda genin kromozom(lar)i ve genomik siniri.
    Doner: {kromozom: (baslangic, bitis, iplik)} - gen tabloda yoksa {};
    tablo hic indirilmemisse None (o zaman cagiran Ensembl'e dusebilir)."""
    try:
        idx = tr._load_index(assembly)
    except tr.TranscriptError:
        return None
    out = {}
    for r in idx["by_gene"].get(str(sembol).strip().upper(), []):
        c = normalize_chrom(r["chrom"])
        a, b, s = out.get(c, (r["tx_start"], r["tx_end"], r["strand"]))
        out[c] = (min(a, r["tx_start"]), max(b, r["tx_end"]), s)
    return out


def gen_konumu(gene_symbol, assembly):
    """Gen adindan kromozom ve genin siniri.

    Once YEREL transkript tablosu (refGene; RNA sekmesiyle ayni dosya). Eskiden
    her seferinde Ensembl'e soruluyordu: cevrimdisiyken "Beklenmeyen hata",
    ustelik yerel genomla calisirken bile istek internete cikiyordu. Ensembl
    yalnizca tablo indirilmemisse kullanilir (genomdaki kuralla ayni: yerel veri
    varsa internete gidilmez). Olculen (2026-10-07): tablo 28 bin gen adi,
    protein kodlayan genlerin tamami; eski adlari (MLL -> KMT2A) Ensembl de
    tanimiyor, yani bu konuda kayip yok."""
    sembol = str(gene_symbol).strip().upper()
    bolgeler = gen_bolgeleri(sembol, assembly)
    if bolgeler is None:
        d = dict(lookup_gene(sembol, assembly))
        d["chrom"] = normalize_chrom(d["chrom"]) if d.get("chrom") else d.get("chrom")
        d["source"] = "ensembl"
        return d
    if not bolgeler:
        raise PrimerError(t(
            f"{gene_symbol} transkript tablosunda ({assembly}) bulunamadı. Güncel gen adını "
            "kullanın (ör. MLL değil KMT2A) ya da kromozomu elle girin.",
            f"{gene_symbol} was not found in the transcript table ({assembly}). Use the "
            "current gene symbol (e.g. KMT2A, not MLL) or enter the chromosome."))
    if len(bolgeler) > 1:
        if set(bolgeler) == {"X", "Y"}:
            # X ile Y'nin ortak uclarindaki (PAR) gen. Ensembl de X dondurur;
            # bu bolgede Y, X'in birebir kopyasidir.
            secim = "X"
        else:
            # Ornegin kopyalanmis miRNA'lar. Ensembl burada sessizce birini
            # seciyordu; hangisinin kastedildigi bilinmeden secmek yanlis.
            kromlar = ", ".join("chr" + c for c in sorted(bolgeler, key=_kromozom_sirasi))
            raise PrimerError(t(
                f"{gene_symbol} birden fazla kromozomda geçiyor ({kromlar}). Kromozomu "
                "elle girin.",
                f"{gene_symbol} occurs on more than one chromosome ({kromlar}). Enter the "
                "chromosome."))
    else:
        secim = next(iter(bolgeler))
    a, b, s = bolgeler[secim]
    return {"chrom": secim, "start": a, "end": b, "strand": s, "id": None,
            "source": "local"}


def _kromozom_sirasi(c):
    return (0, int(c)) if c.isdigit() else (1, c)


def gen_uzaklik_notu(gene_symbol, gene_info, chrom, position, assembly):
    """Koordinat yazilan genin uzaginda mi? Uzaktaysa uyari metni, degilse None."""
    if not gene_info or not gene_info.get("start") or not gene_info.get("end"):
        return None
    c = normalize_chrom(chrom)
    if gene_info.get("chrom") and normalize_chrom(gene_info["chrom"]) != c:
        g = normalize_chrom(gene_info["chrom"])
        return t(
            f"UYARI: Girilen kromozom chr{c}, ama {gene_symbol} chr{g} üzerinde ({assembly}). "
            "Kromozomu ya da gen adını kontrol edin.",
            f"WARNING: The chromosome entered is chr{c}, but {gene_symbol} is on chr{g} "
            f"({assembly}). Check the chromosome or the gene symbol.")
    a, b = int(gene_info["start"]), int(gene_info["end"])
    mesafe = (a - position) if position < a else (position - b) if position > b else 0
    if mesafe <= GEN_UZAKLIK_UYARI:
        return None
    return t(
        f"UYARI: Koordinat {gene_symbol} geninin {tr_sayi(mesafe)} bp dışında (gen chr{c}:"
        f"{tr_sayi(a)}-{tr_sayi(b)}, {assembly}). Genom sürümünü (GRCh37 / GRCh38) ve koordinatı kontrol "
        "edin; gen dışı bir bölgeyi hedefliyorsanız bu uyarıyı yok sayabilirsiniz.",
        f"WARNING: The coordinate lies {mesafe:,} bp outside {gene_symbol} (gene chr{c}:"
        f"{a:,}-{b:,}, {assembly}). Check the genome build (GRCh37 / GRCh38) and the "
        "coordinate; if you are targeting a region outside the gene, ignore this warning.")


# ------------------------------------------------------------------
# primer3 tasarim
# ------------------------------------------------------------------
FLANK_MAKS = 10_000            # varyantin her yanindan en fazla bu kadar bp

DEFAULTS = {
    "flank": 700,                # varyantin her iki yanindan cekilecek bp (en fazla FLANK_MAKS)
    "product_size_min": 180,
    "product_size_max": 650,
    # Laboratuvarda guvenle cogaltilabilen en uzun urun (bp). Kullanicinin
    # laboratuvarinda ~700 bp (2026-10-25); baska lablar daha uzun cogaltabilir,
    # arayuzde ayar olarak kaydedilir. Hicbir modda urun ust siniri bunu asmaz;
    # kirilma noktasinda normal alel / kontrol / dup bantlari buna gore degerlendirilir.
    "pcr_max": 700,
    # Urunun (amplikonun) GC yuzdesi bu aralikta olsun. 0-100 = kisit yok (varsayilan;
    # GC yalnizca bilgi + DMSO/betain notu). Kullanici istegi (2026-10-25): GC'ce
    # zengin urunden kacinmak icin ust sinir konabilsin.
    "product_min_gc": 0.0,
    "product_max_gc": 100.0,
    "primer_min_size": 18,
    "primer_opt_size": 20,
    "primer_max_size": 24,
    "primer_min_tm": 55.0,        # 55-65 bandi disi reddedilir
    "primer_max_tm": 65.0,
    "primer_max_tm_diff": 2.0,    # cift ici Tm farki siniri (F/R birbirine yakin kalsin)
    # Tm optimizasyonu KAPALI (=0): 55-65 sadece bir kapi, band icinde Tm hic rol oynamaz;
    # secimi tamamen self/dimer kalitesi belirler. (primer3 varsayilani 1.0 idi -> "60'a it".)
    # NOT: 0 olunca en temiz cift primer3'un dondurdugu havuza girsin diye dimer_pool BUYUK olmali.
    "wt_tm_lt": 0.0,
    "wt_tm_gt": 0.0,
    "primer_min_gc": 40.0,
    "primer_max_gc": 60.0,
    "primer_gc_clamp": 1,
    # 3' ucun DIGER yonu: son 5 bazda en fazla bu kadar G/C. Clamp "en az 1"
    # derken bunu sinirlamamak tutarsizdi - 4-5 G/C'li uc asiri kararli olur,
    # yanlis yerde bile tutunup uzar. Standart oneri "son 5'te 1-3 G/C";
    # Degerlendir sekmesi zaten 4+ icin uyariyordu, tasarim da ayni olcuye uydu.
    # primer3 varsayilani 5 (fiilen sinirsiz).
    "primer_max_end_gc": 3,
    "primer_max_poly_x": 4,       # ardisik ayni baz (homopolimer) siniri
    "salt_monovalent": 50.0,      # mM (Na+/K+)
    "salt_divalent": 1.5,         # mM (Mg2+)
    "dntp_conc": 0.6,             # mM
    "dna_conc": 50.0,             # nM (primer)
    # DMSO (%, h/h). Tm'i dusurur (primer3: Tm - 0,6 x %DMSO). Program GC'ce zengin
    # urunde DMSO onerdigi halde Tm'i DMSO'suz hesapliyordu (inceleme bulgusu 22).
    "dmso_conc": 0.0,
    "min_dist_from_variant": 50,  # primerin varyanta en az uzakligi (bp)
    "num_return": 10,             # kullaniciya donen cift sayisi

    # --- self/dimer yeniden siralama (LEGACY hizalama = NCBI Primer-BLAST ile ayni birim) ---
    # ONEMLI: self/dimer icin primer3 LEGACY hizalama kullanilir (asagida OLIGO_ALIGNMENT=0).
    # Boylece degerler NCBI Primer-BLAST'takiyle BIREBIR ayni (Self complementarity ~0-12,
    # esik 8; Self 3' complementarity esik 3). Termodinamik metrik self'e "kor" oldugu icin
    # (hepsine 0 der) bu daha ayirt edici ve kullanicinin dogruladigi olcuyle uyumlu.
    # primer3'ten istenecek aday sayisi (self/dimer'e gore yeniden siralanir).
    # 300'du; o havuz CESITLILIKTEN yoksundu: TP53'te 300 cift yalnizca 42 farkli
    # forward ve 29 farkli reverse iceriyordu, gerisi 1-2 baz kaymis kopyalardi ve
    # gercekten daha iyi bir cift havuza hic girmiyordu (kullanici bildirdi,
    # olculdu 2026-10-27). 1000'de 12 gende ortalama dimer 4,48 -> 4,17, urun
    # 442 -> 423 bp, maliyet +0,1 sn. 2000 ayni sonucu veriyor, iki kat yavas.
    "dimer_pool": 1000,
    # Oncelik sirasi (kullanici tercihi): self-3' > self > primer-dimer.
    "w_self_end": 1.0,            # 1) self 3' complementarity (SELF_END) - EN ONEMLI
    "w_self_any": 0.7,            # 2) self complementarity (SELF_ANY)
    "w_compl_end": 0.5,           # 3) primer dimer - 3' uc (PAIR_COMPL_END)
    "w_compl_any": 0.3,           # 3) primer dimer - genel (PAIR_COMPL_ANY)
    "dimer_scale": 0.20,          # legacy skoru (~0-12) -> ceza olcegi (birim kucuk oldugu icin buyuk)
    "prefer_short_product": 0.001,   # kisa amplikon tercihi (bp basina hafif ceza; kalite benzerse
                                     # kisayi sec). Guvenli tiebreaker: self'i bozmaz (0.002 bozuyordu).
    "self3p_warn": 3.0,           # ust cift 3' self/dimer bu legacy skoru asarsa uyari (NCBI 3' esigi=3)
    # Legacy self/dimer ust sinirlari (NCBI Primer-BLAST varsayilanlari): asan primer elenir
    "max_self_any": 8.0,
    "max_self_end": 3.0,
    "max_pair_compl_any": 8.0,
    "max_pair_compl_end": 3.0,

    # --- Yaygin varyant (dbSNP) kacinmasi -------------------------------------
    # Primerin baglandigi yerdeki yaygin varyant o alleli cogaltmaz: heterozigot
    # hasta HOMOZIGOT gorunur. Bu yuzden varsayilan davranis "uyarmak" degil,
    # primer3'e o konumlari bastan yasaklamaktir.
    "avoid_common_snps": True,
    "snp_min_maf": 0.0,        # 0 = tabloda ne varsa hepsinden kacin (tablo zaten MAF>=%1)
}


def _ayar_birlestir(tabanlar, params):
    """Varsayilanlarin ustune kullanici ayarlarini koy ve TIPLERINI dogrula.

    Eskiden ayarlar oldugu gibi aktariliyordu; sayi beklenen yere metin gelince
    ("abc") ilk float()/int() cagrisinda ValueError -> HTTP 500 "Beklenmeyen hata"
    donuyordu (2026-10-10 testinde dort uc). Burada anlasilir bir hataya cevrilir
    ve sayilar varsayilanin tipine getirilir ("12" -> 12). Her sayi ayrica alt/ust
    sinirina karsi denetlenir (bkz. ayarlar.TASARIM_SINIRLARI).

    primer_opt_tm artik ayar degil (agirligi 0, sirayi etkilemiyordu; alan kaldirildi):
    eski bir istemciden gelirse yok sayilir. primer3'un istedigi optimum Tm
    _primer3_ayarlari'nda alt/ust sinirin ortasindan turetilir."""
    if isinstance(params, dict) and "primer_opt_tm" in params:
        params = {k: v for k, v in params.items() if k != "primer_opt_tm"}
    return ayarlar.birlestir(tabanlar, params, ayarlar.TASARIM_SINIRLARI, PrimerError)


def _dogrula_parametreler(p):
    """Kendi icinde tutarsiz ayarlari ONCEDEN yakala.

    primer3 bunlari kendi de reddediyor ama ham C mesajiyla ("Optimum primer Tm
    lower than minimum or higher than maximum") ve bu bize HTTP 500 "beklenmeyen
    hata" olarak donuyordu. Kullanicinin kendi girdigi bir deger yuzunden
    "beklenmeyen hata" gormesi yanlis; ne yapmasi gerektigi soylenmeli."""
    def sayi(k):
        return float(p[k])

    if sayi("primer_min_tm") > sayi("primer_max_tm"):
        raise PrimerError(t(
            f"Tm alt sınırı ({sayi('primer_min_tm')}) üst sınırdan "
            f"({sayi('primer_max_tm')}) büyük olamaz.",
            f"The minimum Tm ({sayi('primer_min_tm')}) cannot exceed the maximum "
            f"({sayi('primer_max_tm')})."))
    if sayi("primer_min_size") > sayi("primer_max_size"):
        raise PrimerError(t(
            "Primer uzunluğu alt sınırı üst sınırdan büyük olamaz.",
            "The minimum primer length cannot exceed the maximum."))
    if not sayi("primer_min_size") <= sayi("primer_opt_size") <= sayi("primer_max_size"):
        raise PrimerError(t(
            f"Hedef primer uzunluğu ({int(sayi('primer_opt_size'))} nt), izin verilen "
            f"aralığın ({int(sayi('primer_min_size'))}-{int(sayi('primer_max_size'))} nt) "
            "dışında.",
            f"The optimum primer length ({int(sayi('primer_opt_size'))} nt) is outside "
            f"the allowed range ({int(sayi('primer_min_size'))}-"
            f"{int(sayi('primer_max_size'))} nt)."))
    if sayi("primer_min_gc") > sayi("primer_max_gc"):
        raise PrimerError(t(
            "GC alt sınırı üst sınırdan büyük olamaz.",
            "The minimum GC cannot exceed the maximum."))
    clamp = int(p.get("primer_gc_clamp", 0))
    uc_gc = int(p.get("primer_max_end_gc", 5))
    if not 0 <= uc_gc <= 5:
        raise PrimerError(t(
            "3' uçtaki en fazla G/C sayısı 0-5 arasında olmalı (son 5 baz).",
            "The maximum 3' G/C count must be between 0 and 5 (last 5 bases)."))
    if clamp > uc_gc:
        raise PrimerError(t(
            f"GC clamp ({clamp}) 3' uçtaki en fazla G/C sayısından ({uc_gc}) büyük "
            "olamaz — bu şartları aynı anda sağlayan primer yok.",
            f"GC clamp ({clamp}) cannot exceed the maximum 3' G/C count ({uc_gc}) — "
            "no primer can satisfy both."))
    if sayi("product_size_min") > sayi("product_size_max"):
        raise PrimerError(t(
            "Ürün boyu alt sınırı üst sınırdan büyük olamaz.",
            "The minimum product size cannot exceed the maximum."))
    if p.get("skip_min_flank") is not None and p.get("skip_max_flank") is not None \
            and sayi("skip_min_flank") > sayi("skip_max_flank"):
        raise PrimerError(t(
            "Ekson atlama: eksonun yanındaki en kısa ürün payı en uzunundan büyük olamaz.",
            "Exon skipping: the minimum flank beside the exon cannot exceed the maximum."))
    if p.get("product_min_gc") is not None and p.get("product_max_gc") is not None:
        if not 0 <= sayi("product_min_gc") <= sayi("product_max_gc") <= 100:
            raise PrimerError(t(
                "Ürün GC aralığı 0-100 arasında olmalı ve alt sınır üst sınırdan büyük olmamalı.",
                "The product GC range must lie within 0-100 and its minimum cannot exceed "
                "its maximum."))
    if p.get("pcr_max") is not None:
        if sayi("pcr_max") < 100:
            raise PrimerError(t(
                "Çoğaltılabilen en uzun ürün en az 100 bp olmalı.",
                "The longest amplifiable product must be at least 100 bp."))
        if not p.get("ignore_product_size") and sayi("product_size_min") > sayi("pcr_max"):
            raise PrimerError(t(
                f"Ürün boyu alt sınırı ({int(sayi('product_size_min'))} bp), çoğaltılabilen en "
                f"uzun üründen ({int(sayi('pcr_max'))} bp) büyük. Alt sınırı düşürün ya da "
                "gelişmiş parametrelerden çoğaltılabilen en uzun ürünü yükseltin.",
                f"The minimum product size ({int(sayi('product_size_min'))} bp) exceeds the "
                f"longest amplifiable product ({int(sayi('pcr_max'))} bp). Lower the minimum "
                "or raise the longest amplifiable product under advanced parameters."))


def _urun_araligi(p):
    """primer3 urun araligi: ust sinir laboratuvarin cogaltabildigi en uzun urunu
    (pcr_max) asmaz. 'Mesafe bilinmiyor' (iki dizi) modunda urun boyu kisiti
    bilincli olarak kaldirildigi icin orada uygulanmaz."""
    alt, ust = int(p["product_size_min"]), int(p["product_size_max"])
    if p.get("pcr_max") is not None and not p.get("ignore_product_size"):
        ust = min(ust, int(p["pcr_max"]))
    return [[alt, ust]]


def _dahil_bolge(sablon_boyu, hedef, p):
    """primer3'un aday arayacagi pencere [bas, uzunluk]: urun hedefi kapsamak ve en
    fazla 'ust' boyda olmak zorunda, yani primerler [hedef_sonu - ust, hedef_basi + ust]
    disina dusemez. Bu pencere disindaki adaylar zaten urun veremez.

    Neden (2026-10-29 hata taramasi): primer3 hedefin solundaki her adayi sagindaki
    her adayla eslestirip boyu SONRA kontrol ediyor; sure sablon uzunluguyla karesel
    buyuyordu. RNA modunda transkriptin tamami sablon: DMD (14 kb) 16,5 sn, NEB (26 kb)
    80 sn, SYNE1 (28 kb) 99 sn, TTN (104 kb) 10 dakikada bitmiyordu; 20 kb'lik hedefli
    dizi 56 sn (hedefsiz 0,9 sn). Sonuc degismez, yalnizca imkansiz adaylar elenir."""
    if not hedef:
        return None
    ust = _urun_araligi(p)[0][1]
    a, n = int(hedef[0]), int(hedef[1])
    bas = max(0, a + n - ust)
    son = min(int(sablon_boyu), a + ust)
    if son - bas <= 0:
        return None              # hedef urune sigmiyor; cagiran zaten acik hata verir
    return [bas, son - bas]


def _pcr_sinir_notu(p):
    """Kullanicinin amplikon ust siniri, cogaltilabilen en uzun urunun USTUNDEyse
    gecerli sinir ikincisidir. Bunu sessizce yapmak kafa karistiriyordu: "amplikon
    max 2000 yazdim, 583 bp urun geldi" (2026-10-25)."""
    if p.get("pcr_max") is None or p.get("ignore_product_size"):
        return None
    ust, sinir = int(p["product_size_max"]), int(p["pcr_max"])
    if ust <= sinir:
        return None
    return t(
        f"Amplikon üst sınırı ({tr_sayi(ust)} bp), çoğaltılabilen en uzun üründen ({tr_sayi(sinir)} bp) "
        f"büyük; geçerli üst sınır {tr_sayi(sinir)} bp oldu. Daha uzun ürün istiyorsanız gelişmiş "
        "parametrelerden \"Çoğaltılabilen en uzun ürün\" değerini de yükseltin.",
        f"The amplicon maximum ({ust:,} bp) is above the longest amplifiable product "
        f"({sinir:,} bp), so the effective maximum is {sinir:,} bp. For longer products, "
        "raise \"Longest amplifiable product\" under advanced parameters as well.")


def _build_global_args(p):
    _dogrula_parametreler(p)
    return {
        "PRIMER_TASK": "generic",
        "PRIMER_PICK_LEFT_PRIMER": 1,
        "PRIMER_PICK_RIGHT_PRIMER": 1,
        "PRIMER_PICK_INTERNAL_OLIGO": 0,
        # Yeniden siralama icin genis aday havuzu iste (sonra num_return'e kirpilir)
        "PRIMER_NUM_RETURN": int(p.get("dimer_pool", p["num_return"])),

        "PRIMER_MIN_SIZE": int(p["primer_min_size"]),
        "PRIMER_OPT_SIZE": int(p["primer_opt_size"]),
        "PRIMER_MAX_SIZE": int(p["primer_max_size"]),

        "PRIMER_MIN_TM": float(p["primer_min_tm"]),
        # Optimum Tm ayar degil: agirliklar 0 oldugundan sirayi etkilemez; primer3 yalniz
        # alt <= opt <= ust ister, bu yuzden araligin ortasi (varsayilan 55-65 -> 60)
        "PRIMER_OPT_TM": (float(p["primer_min_tm"]) + float(p["primer_max_tm"])) / 2,
        "PRIMER_MAX_TM": float(p["primer_max_tm"]),
        "PRIMER_PAIR_MAX_DIFF_TM": float(p["primer_max_tm_diff"]),
        # Tm sapma cezasini hafiflet (60'a zorlamamak icin) -> band icinde self/dimer one cikar
        "PRIMER_WT_TM_LT": float(p.get("wt_tm_lt", 1.0)),
        "PRIMER_WT_TM_GT": float(p.get("wt_tm_gt", 1.0)),

        "PRIMER_MIN_GC": float(p["primer_min_gc"]),
        "PRIMER_MAX_GC": float(p["primer_max_gc"]),
        "PRIMER_GC_CLAMP": int(p["primer_gc_clamp"]),
        "PRIMER_MAX_END_GC": int(p.get("primer_max_end_gc", 5)),
        "PRIMER_MAX_POLY_X": int(p["primer_max_poly_x"]),

        # Tm: termodinamik (dogru hesap). Ama self/dimer HIZALAMASI: LEGACY (=NCBI ile ayni).
        "PRIMER_TM_FORMULA": 1,                 # SantaLucia 1998 (Tm)
        "PRIMER_SALT_CORRECTIONS": 1,           # SantaLucia 1998 tuz duzeltmesi (Tm)
        "PRIMER_THERMODYNAMIC_OLIGO_ALIGNMENT": 0,   # self/dimer = LEGACY (NCBI Primer-BLAST ile ayni)
        "PRIMER_THERMODYNAMIC_TEMPLATE_ALIGNMENT": 0,
        # Legacy self/dimer ust sinirlari (NCBI varsayilanlari) - asan primer/cift elenir
        "PRIMER_MAX_SELF_ANY": float(p.get("max_self_any", 8.0)),
        "PRIMER_MAX_SELF_END": float(p.get("max_self_end", 3.0)),
        "PRIMER_PAIR_MAX_COMPL_ANY": float(p.get("max_pair_compl_any", 8.0)),
        "PRIMER_PAIR_MAX_COMPL_END": float(p.get("max_pair_compl_end", 3.0)),

        "PRIMER_SALT_MONOVALENT": float(p["salt_monovalent"]),
        "PRIMER_SALT_DIVALENT": float(p["salt_divalent"]),
        "PRIMER_DNTP_CONC": float(p["dntp_conc"]),
        "PRIMER_DNA_CONC": float(p["dna_conc"]),
        "PRIMER_DMSO_CONC": float(p.get("dmso_conc", 0.0)),

        "PRIMER_PRODUCT_SIZE_RANGE": _urun_araligi(p),
    }


def _val(res, tag):
    """primer3 ciktisindaki degeri getir; yoksa 0.0."""
    return float(res.get(tag, 0.0))


def _hairpin_tm(seq):
    """Termodinamik hairpin erime sicakligi (°C). Legacy hizalamada primer3 hairpin
    vermez; bu yuzden ayrica hesaplanip GOSTERIM ve hairpin uyarisi icin kullanilir (siralamada degil)."""
    try:
        return round(float(primer3.calc_hairpin(seq).tm), 1)
    except Exception:
        return 0.0


def dimer_score(res, i, p):
    """Bir cift icin self/dimer skoru (yuksek = kotu). Degerler primer3 LEGACY hizalama
    skoru = NCBI Primer-BLAST ile ayni birim. Oncelik: self-3' > self > primer-dimer."""
    se = max(_val(res, f"PRIMER_LEFT_{i}_SELF_END"),
             _val(res, f"PRIMER_RIGHT_{i}_SELF_END"))
    sa = max(_val(res, f"PRIMER_LEFT_{i}_SELF_ANY"),
             _val(res, f"PRIMER_RIGHT_{i}_SELF_ANY"))
    ce = _val(res, f"PRIMER_PAIR_{i}_COMPL_END")
    ca = _val(res, f"PRIMER_PAIR_{i}_COMPL_ANY")
    return (float(p["w_self_end"]) * se + float(p["w_compl_end"]) * ce +
            float(p["w_self_any"]) * sa + float(p["w_compl_any"]) * ca)


class _Sira(list):
    """_rank_order sonucu. gc_elenen: urun GC'si kullanicinin araligi disinda kaldigi
    icin, tekrar_elenen: primeri sablonda birden fazla yere oturdugu icin elenen aday
    sayisi (not yazmak icin; dilimlenince kaybolur, once okuyun)."""
    gc_elenen = 0
    tekrar_elenen = 0


# Tekrar suzgecinde primerin 3' ucundan bakilan uzunluk. Olculdu (2026-10-28, GRCh38;
# 5 bilinen tasarim + 30 rastgele konum, havuz 1000): 15'te bilinen tasarimlarin
# hicbiri degismedi, ilk 10'lardan yalnizca tekrar bolgelerindeki 2 cift cikti;
# 12'de 9 cift cikti (asiri). Tam boy eslesme 3' ucu ayni, 5' ucu farkli kopyalari
# kaciriyordu - polimeraz 3' uctan uzatir.
TEKRAR_UC3_NT = 15


def _tekrar_sayisi(sablon, primer):
    """Primerin 3' ucunun (son TEKRAR_UC3_NT baz) sablonda IKI iplikte kac yere
    oturdugu, kendi yeri dahil. >1 ise primer baska kopyalardan da uzar: birden cok
    bant, F+F / R+R urunu. Ic ice gecenler de sayilir ((CA)n'de primer 2 baz kayar).
    sablon BUYUK harf olmali."""
    uc = primer.upper()[-TEKRAR_UC3_NT:]
    if not uc:
        return 0

    def say(alt):
        n, i = 0, sablon.find(alt)
        while i != -1:
            n += 1
            i = sablon.find(alt, i + 1)
        return n

    ters = revcomp(uc)
    return say(uc) + (0 if ters == uc else say(ters))


def _rank_order(res, p, template=None):
    """Aday havuzunu YENIDEN sirala:
       toplam = primer3_cezasi + dimer_scale*dimer_skoru + kisa_amplikon_tercihi.
    template verilirse kesmeden ONCE iki suzgec (havuz zaten genis):
      - urun GC'si [product_min_gc, product_max_gc] disindakiler (primer3'te yok);
      - primerinin 3' ucu sablonda birden fazla yere oturanlar (tekrar dizisi).
        Eskiden yalnizca Kirilma noktasi sekmesinde vardi (inceleme bulgusu 9).
    Donen: (orijinal_index, dimer_skoru, toplam_skor) listesi, en iyiden kotuye."""
    n = int(res.get("PRIMER_PAIR_NUM_RETURNED", 0))
    scale = float(p["dimer_scale"])
    pshort = float(p.get("prefer_short_product", 0.0))
    items = []
    for i in range(n):
        pen = float(res.get(f"PRIMER_PAIR_{i}_PENALTY", 0.0))
        ds = dimer_score(res, i, p)
        psize = int(res.get(f"PRIMER_PAIR_{i}_PRODUCT_SIZE", 0))
        total = pen + scale * ds + pshort * psize   # kisa amplikon hafif tercih edilir
        items.append((i, ds, total))
    items.sort(key=lambda it: it[2])
    sira = _Sira(items)
    gmin = float(p.get("product_min_gc", 0.0))
    gmax = float(p.get("product_max_gc", 100.0))
    if template and (gmin > 0 or gmax < 100):
        kalan = []
        for it in items:
            f_s, _f_e, _r_s, r_e = _primer_spans(res, it[0])
            gc = amplikon_gc(template[f_s:r_e + 1])
            if gc is not None and not gmin <= gc <= gmax:
                sira.gc_elenen += 1
            else:
                kalan.append(it)
        sira[:] = kalan
    if template:
        sablon = template.upper()
        kalan = []
        for it in sira:
            i = it[0]
            if (_tekrar_sayisi(sablon, res.get(f"PRIMER_LEFT_{i}_SEQUENCE", "")) > 1
                    or _tekrar_sayisi(sablon, res.get(f"PRIMER_RIGHT_{i}_SEQUENCE", "")) > 1):
                sira.tekrar_elenen += 1
            else:
                kalan.append(it)
        sira[:] = kalan
    return sira


def _suzgec_notlari(sira, p, kalan_cift):
    """_rank_order suzgeclerinin notlari (liste; eleme yoksa bos)."""
    notlar = []
    gc_notu = _gc_suzgec_notu(sira, p, kalan_cift)
    if gc_notu:
        notlar.append(gc_notu)
    if sira.tekrar_elenen:
        notlar.append(_tekrar_notu(sira.tekrar_elenen))
    return notlar


def _gc_suzgec_notu(sira, p, kalan_cift):
    """Urun GC suzgeci aday eledi mi? Eledi ise kac tane; hic cift kalmadiysa ne yapilmali."""
    n = getattr(sira, "gc_elenen", 0)
    if not n:
        return None
    a = f"{float(p['product_min_gc']):g}"
    b = f"{float(p['product_max_gc']):g}"
    if kalan_cift:
        return t(f"{n} aday çift, ürün GC içeriği %{a}–%{b} aralığının dışında kaldığı için elendi.",
                 f"{n} candidate pairs were dropped because the product GC content was outside "
                 f"{a}–{b}%.")
    return t(f"Ürün GC içeriği %{a}–%{b} aralığında olan çift bulunamadı ({n} aday elendi). "
             "Gelişmiş parametrelerden ürün GC aralığını genişletin.",
             f"No pair has a product GC content within {a}–{b}% ({n} candidates dropped). "
             "Widen the product GC range under advanced parameters.")


def _primer_spans(res, i):
    """Bir cift icin sablon uzerindeki 0-tabanli araliklar:
    (fwd_start, fwd_end, rev_start, rev_end) - hepsi kapsayici, sablon yonunde."""
    left = res[f"PRIMER_LEFT_{i}"]          # (0-tabanli baslangic, uzunluk)
    right = res[f"PRIMER_RIGHT_{i}"]        # (5' uc indeksi = yuksek koordinat, uzunluk)
    l_start0, l_len = int(left[0]), int(left[1])
    r_pos0, r_len = int(right[0]), int(right[1])
    return l_start0, l_start0 + l_len - 1, r_pos0 - r_len + 1, r_pos0


# --- Amplikon GC icerigi esikleri ------------------------------------------
# Kaynaklar (2026-09-14'te bakildi):
#  - Thermo Phusion protokolu: GC Enhancer "yalnizca >%65 GC hedefler icin";
#    Phusion HiFi kilavuzu: >%75 GC'de %5 DMSO onerilir.
#  - PLOS One 2016 (Improved PCR Amplification of Broad Spectrum GC DNA
#    Templates): sorunlu sablonlar "<%30 veya >%70"; >%75'te ikincil yapi
#    nedeniyle eksik urun.
#  - Betain (NAR 1997) ~1 M; DMSO %2,5-5; 7-deaza-dGTP; GC tamponlari.
# Yani: 65 = katki dusunulmeye baslanir, 75 = neredeyse sart, 30 = AT'ce
# zengin (dusuk Tm, kayma) - ayri bir uyari.
AMPLIKON_GC_YUKSEK = 65.0
AMPLIKON_GC_COK_YUKSEK = 75.0
AMPLIKON_GC_DUSUK = 30.0


def amplikon_gc(dizi):
    """Amplikonun GC yuzdesi. N'ler (iki dizi modundaki bilinmeyen bolge) sayilmaz."""
    s = dizi.upper()
    bilinen = sum(1 for c in s if c in "ACGT")
    if not bilinen:
        return None
    return round(100.0 * sum(1 for c in s if c in "GC") / bilinen, 1)


def amplikon_gc_bayragi(gc):
    """None | 'dusuk' | 'yuksek' | 'cok_yuksek'"""
    if gc is None:
        return None
    if gc >= AMPLIKON_GC_COK_YUKSEK:
        return "cok_yuksek"
    if gc >= AMPLIKON_GC_YUKSEK:
        return "yuksek"
    if gc <= AMPLIKON_GC_DUSUK:
        return "dusuk"
    return None


def amplikon_gc_notu(gc):
    """Bayraga gore eyleme donuk oneri metni (bilgi amacli; tasarim etkilenmez)."""
    b = amplikon_gc_bayragi(gc)
    if b == "cok_yuksek":
        return t(
            f"Amplikon GC'ce çok zengin (%{gc}). Bu bölgede standart PCR çoğu zaman "
            "eksik ürün verir: %5 DMSO ve/veya ~1 M betain, GC tamponu, gerekirse "
            "7-deaza-dGTP kullanın; denatürasyonu uzatın. (Thermo: >%75'te %5 DMSO)",
            f"The amplicon is very GC-rich ({gc}%). Standard PCR often gives incomplete "
            "product here: use 5% DMSO and/or ~1 M betaine, a GC buffer, 7-deaza-dGTP if "
            "needed; lengthen denaturation. (Thermo: 5% DMSO above 75%)")
    if b == "yuksek":
        return t(
            f"Amplikon GC'ce zengin (%{gc}). GC tamponu/enhancer önerilir; sorun "
            "çıkarsa %3-5 DMSO veya ~1 M betain ekleyin. (Thermo: >%65'te GC Enhancer)",
            f"The amplicon is GC-rich ({gc}%). A GC buffer/enhancer is recommended; if "
            "it struggles, add 3-5% DMSO or ~1 M betaine. (Thermo: GC Enhancer above 65%)")
    if b == "dusuk":
        return t(
            f"Amplikon AT'ce zengin (%{gc} GC). Düşük Tm ve polimeraz kayması görülebilir; "
            "annealing/ekstansiyon sıcaklığını düşürmeyi ve ekstansiyonu uzatmayı düşünün.",
            f"The amplicon is AT-rich ({gc}% GC). Expect low Tm and polymerase slippage; "
            "consider lowering annealing/extension temperature and lengthening extension.")
    return None


def _amplikon_ekle(d, res, i, template, gap_span=None, hedef=None):
    """Cifte, cogaltacagi DIZININ KENDISINI ekle.

    Amplikon sablonun bir dilimidir ve sablon zaten elimizde - yeniden dizi
    cekmeye gerek yok. Primerlerin amplikon icindeki ofsetleri de verilir ki
    arayuz onlari isaretleyebilsin: bas taraf forward, son taraf reverse'un
    ters tumleyeni. Boylece kullanici "bu primerler tam olarak neyi cogaltiyor"
    sorusunu tek bakista goruyor.

    gap_span: iki dizi modunda aradaki BILINMEYEN bolge (N ile dolduruldu);
    amplikon icindeki [baslangic, bitis] ofseti olarak isaretlenir.

    hedef: kullanicinin girdigi konum, sablon icinde (bas, bit) 0-tabanli, kapsayici.
    Amplikon icindeki yeri variant_span olarak verilir: arayuz o bazi ayri renkle isaretler.
    """
    if not template:
        return d
    f_s, f_e, r_s, r_e = _primer_spans(res, i)
    dizi = template[f_s:r_e + 1]
    gc = amplikon_gc(dizi)
    amp = {
        "sequence": dizi,
        "length": len(dizi),
        # amplikon icinde 0-tabanli, kapsayici
        "forward_span": [0, f_e - f_s],
        "reverse_span": [r_s - f_s, r_e - f_s],
        # GC icerigi: kullanicinin DMSO/betain karari icin. Tasarimi etkilemez.
        "gc_percent": gc,
        "gc_flag": amplikon_gc_bayragi(gc),
        "gc_note": amplikon_gc_notu(gc),
    }
    if gap_span:
        a, b = gap_span
        if b >= a:                      # bilinmeyen bolge amplikonun icinde mi?
            amp["unknown_span"] = [max(0, a - f_s), min(len(dizi) - 1, b - f_s)]
            amp["unknown_length"] = b - a + 1
    if hedef:
        a, b = hedef[0] - f_s, hedef[1] - f_s
        if b >= 0 and a < len(dizi):    # girilen konum amplikonun icinde mi?
            amp["variant_span"] = [max(0, a), min(len(dizi) - 1, b)]
    d["amplicon"] = amp
    return d


# Baglanma sicakligi (Ta) onerisi: dusuk Tm'li primerin Tm'inin bu kadar alti.
# Taq icin yaygin baslangic noktasi (Tm - 5 °C); Tm zaten tuz, primer ve DMSO
# kosullariyla hesaplandigi icin bunlari icerir. Kesin deger gradyan PCR ile bulunur.
TA_PAYI = 5.0


def ta_onerisi(tm_f, tm_r):
    return round(min(tm_f, tm_r) - TA_PAYI, 1)


# Hairpin uyarisi (F-05, kullanici karari 2026-11-11): bir primerin hairpin Tm'i kartta
# gosterilen Ta onerisinin bu kadar altini gecerse (hairpin Tm >= Ta - 5 °C) primer
# 'Ta'da kendi uzerine katlanabilir. Yalniz uyari: siralamaya, rozete ve "En iyi Ozgul
# cift"e katilmaz. Kural tek yerde (burasi); DNA, RNA, Dizi ve Kirilma noktasi ayni
# _pair_core'dan gectigi icin dortunde ayni. Degerler kartta gorunen yuvarlanmis degerlerdir.
HAIRPIN_UYARI_PAYI = 5.0


def hairpin_uyarisi(f_hp, r_hp, ta):
    """Esigi gecen primerlerin listesi: [{primer, hairpin_tm, ta, esik}]. Bos liste = uyari yok.
    'primer' motorun adidir ('forward' / 'reverse'); arayuz eksi iplikte gorunen adi kendisi cevirir."""
    esik = round(ta - HAIRPIN_UYARI_PAYI, 1)
    uyari = []
    for ad, hp in (("forward", f_hp), ("reverse", r_hp)):
        if hp > 0 and hp >= esik:
            uyari.append({"primer": ad, "hairpin_tm": hp, "ta": ta, "esik": esik})
    return uyari


def _pair_core(res, i, ds, total, rank, p):
    """Bir cift icin KOORDINATSIZ ortak alanlar. DNA ve cDNA modlari bunu paylasir;
    koordinatlari cagiran taraf ekler (genomik / cDNA farkli)."""
    warn = float(p["self3p_warn"])
    f_seq = res[f"PRIMER_LEFT_{i}_SEQUENCE"]
    r_seq = res[f"PRIMER_RIGHT_{i}_SEQUENCE"]
    f_self3p = round(_val(res, f"PRIMER_LEFT_{i}_SELF_END"), 1)
    r_self3p = round(_val(res, f"PRIMER_RIGHT_{i}_SELF_END"), 1)
    pair_3p = round(_val(res, f"PRIMER_PAIR_{i}_COMPL_END"), 1)
    # Ust cift kalite bayragi: en kotu 3' bileseni (legacy skor)
    self3p_max = round(max(f_self3p, r_self3p, pair_3p), 1)
    f_hp = _hairpin_tm(f_seq)
    r_hp = _hairpin_tm(r_seq)
    ta = ta_onerisi(float(res[f"PRIMER_LEFT_{i}_TM"]), float(res[f"PRIMER_RIGHT_{i}_TM"]))

    return {
        "rank": rank,
        "pair_penalty": round(float(res[f"PRIMER_PAIR_{i}_PENALTY"]), 3),
        "dimer_score": round(ds, 1),
        "total_score": round(total, 3),
        "self3p_max": self3p_max,                 # en kotu 3' self/dimer (legacy skor)
        "high_3p_self": self3p_max >= warn,       # uyari bayragi
        "product_size": int(res[f"PRIMER_PAIR_{i}_PRODUCT_SIZE"]),
        "hetero_dimer_tm": round(_val(res, f"PRIMER_PAIR_{i}_COMPL_ANY"), 1),  # primer-dimer (legacy)
        "hetero_dimer_3p_tm": pair_3p,            # primer-dimer 3' (legacy)
        "ta_suggested": ta,
        "hairpin_warn": hairpin_uyarisi(f_hp, r_hp, ta),   # uyari bilgisi; siralamayi etkilemez
        "forward": {
            "sequence": f_seq,
            "length": int(res[f"PRIMER_LEFT_{i}"][1]),
            "tm": round(float(res[f"PRIMER_LEFT_{i}_TM"]), 1),
            "gc": round(float(res[f"PRIMER_LEFT_{i}_GC_PERCENT"]), 1),
            "hairpin_tm": f_hp,                    # termodinamik (°C); esigi gecerse uyari (hairpin_warn)
            "self_dimer_tm": round(_val(res, f"PRIMER_LEFT_{i}_SELF_ANY"), 1),   # self (legacy)
            "self_dimer_3p_tm": f_self3p,          # self 3' (legacy)
            "end_stability": round(_val(res, f"PRIMER_LEFT_{i}_END_STABILITY"), 2),
            "penalty": round(float(res.get(f"PRIMER_LEFT_{i}_PENALTY", 0.0)), 3),
        },
        "reverse": {
            "sequence": r_seq,
            "length": int(res[f"PRIMER_RIGHT_{i}"][1]),
            "tm": round(float(res[f"PRIMER_RIGHT_{i}_TM"]), 1),
            "gc": round(float(res[f"PRIMER_RIGHT_{i}_GC_PERCENT"]), 1),
            "hairpin_tm": r_hp,                    # termodinamik (°C); esigi gecerse uyari (hairpin_warn)
            "self_dimer_tm": round(_val(res, f"PRIMER_RIGHT_{i}_SELF_ANY"), 1),  # self (legacy)
            "self_dimer_3p_tm": r_self3p,          # self 3' (legacy)
            "end_stability": round(_val(res, f"PRIMER_RIGHT_{i}_END_STABILITY"), 2),
            "penalty": round(float(res.get(f"PRIMER_RIGHT_{i}_PENALTY", 0.0)), 3),
        },
    }


def bolge_sozlugu(b, assembly=None):
    """transcripts.konum_bolgesi sonucunu arayuze giden 'gene_region' sozlugune cevir.
    Degerlendir'in baglanma tablosu da bunu kullanir: iki ekranda ayni etiket.
    assembly verilirse (K1) kodlayan dizisi tutarsiz transkriptte 'kod_isareti' True olur:
    arayuz ekson numarasinin NM'ninkinden farkli olabilecegini ipucuna yazar."""
    isaret = False
    if assembly:
        try:
            isaret = kod_isareti(tr.get_transcript(b["acc"], assembly), assembly)
        except (tr.TranscriptError, PrimerError):
            isaret = False
    return {
        "kod_isareti": isaret,
        "label": t(b["label_tr"], b["label_en"]),
        "kind": b["kind"],
        "exon": b["exon"],
        "exon_to": b["exon_to"],
        "intron": b["intron"],
        "side": b["side"],
        "exon_count": b["exon_count"],
        "gene": b["gene"],
        "acc": b["acc"],
        "mane": b["mane"],
    }


def _bolge_ekle(ciftler, assembly, chrom):
    """Her primere genin neresine oturdugunu yaz (ekzon 7 / intron 7 ...).

    Ekzon numarasi TRANSKRIPTE gore degistigi icin hangi transkriptin esas
    alindigi da yazilir (MANE Select varsa o). Transkript tablosu yoksa ya da
    konum hicbir gene denk gelmiyorsa alan hic eklenmez - arayuz bos gosterir.
    """
    for c in ciftler or []:
        for alan in ("forward", "reverse", "control"):
            x = c.get(alan)
            if not isinstance(x, dict) or not x.get("genomic_start"):
                continue
            b = tr.konum_bolgesi(assembly, chrom, x["genomic_start"], x["genomic_end"])
            if not b:
                continue
            # Ad bilerek 'gene_region': Dizi modunda primerlerde zaten 'region'
            # alani var ve "F / R" (hangi girdi dizisi) anlamina geliyor.
            x["gene_region"] = bolge_sozlugu(b, assembly)


def _collect_pairs(res, template_start, order, p, template=None, hedef=None):
    """DNA modu: primer3 ciktisini YENIDEN SIRALANMIS index listesine (order) gore
    genomik koordinatli sozluk listesine cevir."""
    pairs = []
    for rank, (i, ds, total) in enumerate(order, start=1):
        f_s, f_e, r_s, r_e = _primer_spans(res, i)
        d = _amplikon_ekle(_pair_core(res, i, ds, total, rank, p), res, i, template, hedef=hedef)
        # Genomik koordinatlar (1-tabanli). template_start sablonun ilk bazi.
        d["forward"]["genomic_start"] = template_start + f_s
        d["forward"]["genomic_end"] = template_start + f_e
        d["reverse"]["genomic_start"] = template_start + r_s
        d["reverse"]["genomic_end"] = template_start + r_e
        d["amplicon_genomic_start"] = template_start + f_s
        d["amplicon_genomic_end"] = template_start + r_e
        pairs.append(d)
    return pairs


# ------------------------------------------------------------------
# Yaygin varyant (dbSNP) katmani
# ------------------------------------------------------------------
def _collect_snps(assembly, chrom, start, end, p):
    """Verilen genomik araliktaki yaygin varyantlar. Frekansi bilinmeyen kayitlar
    DAHIL EDILIR: tablo zaten 'common' alt kumesi, guvenli taraf onlari da elemek.

    NOT: Toplama her zaman yapilir; 'avoid_common_snps' yalnizca YASAKLAMAYI kapatir.
    Kullanici kacinmayi bilerek kapattiginda primerin uzerinde hangi varyantin
    oldugunu gormesi asil o zaman gerekir."""
    idx = dbsnp.get_index(assembly)
    if idx is None:
        return []
    min_maf = float(p.get("snp_min_maf", 0.0) or 0.0)
    return [s for s in idx.overlaps(chrom, start, end)
            if s["maf"] == 0.0 or s["maf"] >= min_maf]


def _snp_template_offsets(snps, tpl_start):
    """Genomik SNP kayitlarina sablon uzerindeki 0-tabanli ofseti ekle (DNA modu)."""
    out = []
    for s in snps:
        s = dict(s)
        s["template_offset"] = s["position"] - tpl_start
        out.append(s)
    return out


# primer3 bir etikette en fazla 200 aralik kabul ediyor (PR_MAX_INTERVAL_ARRAY);
# fazlasinda "Too many elements for tag SEQUENCE_EXCLUDED_REGION" diyip 500'e
# donuyordu (genis sablonda yaygin SNP sayisi bunu asiyor). Pay birakildi.
PRIMER3_BOLGE_MAKS = 190


def _bolge_sinirla(regions, limit=PRIMER3_BOLGE_MAKS):
    """Aralik sayisi siniri asarsa EN YAKIN komsulari birlestir. Birlestirme
    aradaki bazlari da yasaklar - yani kisit gevser degil SIKILASIR; hicbir
    SNP serbest kalmaz. En kucuk bosluklar secildigi icin kaybedilen baz en az."""
    if len(regions) <= limit:
        return regions
    r = sorted(regions)
    bosluk = sorted(range(len(r) - 1), key=lambda i: r[i + 1][0] - (r[i][0] + r[i][1]))
    birlestir = set(bosluk[:len(r) - limit])
    out = []
    for i, (a, n) in enumerate(r):
        if out and (i - 1) in birlestir:
            pa, pn = out[-1]
            out[-1] = [pa, max(pa + pn, a + n) - pa]
        else:
            out.append([a, n])
    return out


def _excluded_from_snps(snps, tpl_len, limit=PRIMER3_BOLGE_MAKS):
    """primer3 SEQUENCE_EXCLUDED_REGION listesi: [[baslangic, uzunluk], ...]"""
    regions = []
    for s in snps:
        a = s["template_offset"]
        n = s["span"]
        if a < 0:
            n += a
            a = 0
        if a >= tpl_len or n <= 0:
            continue
        regions.append([a, min(n, tpl_len - a)])
    return _bolge_sinirla(regions, limit)


def uc3_uzakligi(uc3, bas, span):
    """Primerin 3' ucundaki baz (uc3) ile [bas, bas+span-1] varyant araligi
    arasindaki baz sayisi; varyant 3' ucu ORTUYORSA 0. Iplikten bagimsiz.

    Eskiden forward primerde varyantin BASLANGICI esas aliniyordu: 3' ucu ortan
    20 bp'lik bir indel "3' uctan 14 bp" gorunuyor, 3' uyarisi cikmiyordu;
    reverse'de ise ortusme negatif uzaklik veriyordu (2026-10-28)."""
    son = bas + span - 1
    if bas <= uc3 <= son:
        return 0
    return bas - uc3 if bas > uc3 else uc3 - son


def _annotate_pair_snps(pairs, res, order, snps):
    """Her primere, uzerine denk gelen yaygin varyantlari ekle.
    3' uctan uzaklik onemli: 3' uctaki bir SNP uzamayi tamamen engeller,
    5' uctaki cogu zaman tolere edilir."""
    if not snps:
        for pr in pairs:
            pr["forward"]["snps"] = []
            pr["reverse"]["snps"] = []
            pr["snp_count"] = 0
            pr["snp_at_3p"] = False
        return pairs

    for pr, (i, _ds, _tot) in zip(pairs, order):
        f_s, f_e, r_s, r_e = _primer_spans(res, i)
        worst_3p = False
        for key, (a, b), three_p in (("forward", (f_s, f_e), f_e),
                                     ("reverse", (r_s, r_e), r_s)):
            hits = []
            for s in snps:
                off, span = s["template_offset"], s["span"]
                if off + span - 1 < a or off > b:
                    continue
                # forward'da 3' uc yuksek ofset, reverse'de dusuk ofset (three_p)
                dist = uc3_uzakligi(three_p, off, span)
                hits.append({
                    "rsid": s["rsid"], "maf": s["maf"], "indel": s["indel"],
                    "distance_from_3p": dist,
                })
                if dist <= 5:
                    worst_3p = True
            hits.sort(key=lambda h: h["distance_from_3p"])
            pr[key]["snps"] = hits
        pr["snp_count"] = len(pr["forward"]["snps"]) + len(pr["reverse"]["snps"])
        pr["snp_at_3p"] = worst_3p
    return pairs


# ------------------------------------------------------------------
# "Uygun primer bulunamadi" - sebebini insan diliyle soyle
# ------------------------------------------------------------------
# primer3 sonuc cikmayinca sebebi zaten yaziyor, ama kendi diliyle:
#   "considered 11204, unacceptable product size 10044, tm diff too large 1160, ok 0"
# Arayuz bu metni oldugu gibi gosteriyordu. Sebep icinde duruyor ama kullanicinin
# bunu cozmesini beklemek yanlis; primer tasarimindaki en sik hayal kirikligi
# "hicbir sey bulamadi, neden bilmiyorum" durumudur.
_EXPLAIN_KALEM = re.compile(r"^(.*?)\s+(\d+)$")


def _explain_coz(metin):
    """'considered 330, GC content failed 3, ok 37' -> {'considered': 330, ...}

    primer3 bir elemeyi ETIKETLEMIYOR: PRIMER_MAX_END_GC (3' ucta fazla G/C)
    yuzunden atilan adaylar 'considered' icinde sayiliyor ama hicbir kaleme
    yazilmiyor. Olculdu: sinir 5 iken fark 0, sinir 3'te 21, sinir 0'da 312 -
    fark tam olarak bu eleme. Kalani hesaplayip kendimiz etiketliyoruz; yoksa
    kullanici "adaylar nereye gitti" sorusuna cevap bulamaz.
    """
    out = {}
    for parca in (metin or "").split(","):
        m = _EXPLAIN_KALEM.match(parca.strip())
        if m:
            out[m.group(1).strip().lower()] = int(m.group(2))
    if "considered" in out:
        etiketli = sum(v for k, v in out.items() if k != "considered")
        kalan = out["considered"] - etiketli
        if kalan > 0:
            out["high end gc"] = kalan
    return out


def _explain_baskin(d):
    """considered/ok disindaki en buyuk kalem: (sebep, sayi) veya (None, 0)."""
    aday = [(k, v) for k, v in d.items() if k not in ("considered", "ok") and v > 0]
    if not aday:
        return None, 0
    return max(aday, key=lambda kv: kv[1])


# primer3'un eleme sebepleri icin kisa etiketler (dokum satirinda kullanilir)
_ELEME_ETIKET = {
    "gc content failed": ("GC oranı", "GC content"),
    "gc clamp failed": ("GC clamp", "GC clamp"),
    "high end gc": ("3' uçta fazla G/C", "too much 3' G/C"),
    "low tm": ("Tm düşük", "Tm too low"),
    "high tm": ("Tm yüksek", "Tm too high"),
    "high any compl": ("kendine katlanma", "self-complementarity"),
    "high end compl": ("3' katlanma", "3' self-complementarity"),
    "high self any": ("kendine katlanma", "self-complementarity"),
    "high self end": ("3' katlanma", "3' self-complementarity"),
    "long poly-x seq": ("homopolimer", "homopolymer"),
    "overlap excluded region": ("dışlanan bölge", "excluded region"),
    "unacceptable product size": ("ürün boyu", "product size"),
    "tm diff too large": ("Tm farkı", "Tm difference"),
    "too many ns": ("belirsiz baz (N)", "ambiguous bases (N)"),
    "not in any ok left region": ("bölge kısıtı", "region constraint"),
    "not in any ok right region": ("bölge kısıtı", "region constraint"),
    # "Primer ekson sinirinin uzerine otursun" acikken: ciftin hicbir primeri sinira oturmuyor
    "no overlap of required point": ("ekson sınırı şartı", "exon-junction requirement"),
}


def _explain_dokum(kaynak):
    """'Eleme dökümü: GC oranı 2197, GC clamp 178, homopolimer 138' satiri.

    Tek bir baskin sebep her zaman yeterli degil: primer3 filtreleri SIRAYLA
    uygular, yani erken filtreler (GC gibi) sayica hep one cikar ve asil
    darbogazi gizleyebilir. Tam dokum kullaniciya kendi karar verme sansi verir.
    """
    kalem = sorted(((k, v) for k, v in kaynak.items()
                    if k not in ("considered", "ok") and v > 0),
                   key=lambda kv: -kv[1])
    if not kalem:
        return ""
    parcalar = []
    for k, v in kalem[:5]:
        etiket = _ELEME_ETIKET.get(k)
        ad = t(etiket[0], etiket[1]) if etiket else k
        parcalar.append(f"{ad} {v}")
    return t("Eleme dökümü: ", "Rejection breakdown: ") + ", ".join(parcalar) + "."


def _sablon_uzunlugu(sonuc):
    """Sonuc sozlugunden sablon uzunlugunu cikarabiliyorsak cikar."""
    try:
        if sonuc.get("template_length"):
            return int(sonuc["template_length"])
        if sonuc.get("mode") == "breakpoint":
            return None     # input.length orada delesyon/dup boyu, sablon degil
        g = (sonuc.get("input") or {}).get("length")
        if g:
            return int(g)
        a, b = sonuc.get("template_start"), sonuc.get("template_end")
        if a and b:
            return int(b) - int(a) + 1
    except (TypeError, ValueError):
        pass
    return None


def _explain_oneri(sebep, p, sablon):
    """Baskin sebep -> tek cumlelik, EYLEME DONUK aciklama. Bilinmeyen sebepte None."""
    sayi = lambda k, v=0: p.get(k, v)
    if sebep == "unacceptable product size":
        ek_tr = f" Şablon {sablon} bp." if sablon else ""
        ek_en = f" The template is {sablon} bp." if sablon else ""
        return t(
            f"Adayların çoğu ürün boyu kısıtına takıldı: istenen aralık "
            f"{sayi('product_size_min')}-{sayi('product_size_max')} bp.{ek_tr} "
            "Gelişmiş ayarlardan ürün boyu aralığını genişletin ya da küçültün.",
            f"Most candidates failed the product-size constraint: the requested range "
            f"is {sayi('product_size_min')}-{sayi('product_size_max')} bp.{ek_en} "
            "Widen or shrink the product size range under advanced settings.")
    if sebep == "tm diff too large":
        return t(
            f"Çiftler F/R arasındaki Tm farkı sınırını ({sayi('primer_max_tm_diff')} °C) "
            "aştı. Gelişmiş ayarlardan bu sınırı gevşetmeyi deneyin.",
            f"Pairs exceeded the F/R Tm difference limit ({sayi('primer_max_tm_diff')} °C). "
            "Try relaxing that limit under advanced settings.")
    if sebep == "gc content failed":
        return t(
            f"Adayların çoğu GC oranı aralığının (%{sayi('primer_min_gc')}-"
            f"%{sayi('primer_max_gc')}) dışında kaldı — bölge GC açısından çok fakir "
            "ya da çok zengin. GC aralığını genişletin.",
            f"Most candidates fell outside the GC range ({sayi('primer_min_gc')}-"
            f"{sayi('primer_max_gc')}%) — the region is unusually GC-poor or GC-rich. "
            "Widen the GC range.")
    if sebep in ("low tm", "high tm"):
        yon_tr = "altında" if sebep == "low tm" else "üstünde"
        yon_en = "below" if sebep == "low tm" else "above"
        sinir = sayi("primer_min_tm") if sebep == "low tm" else sayi("primer_max_tm")
        return t(
            f"Adayların çoğunun Tm'i sınırın ({sinir} °C) {yon_tr} kaldı. Primer "
            "uzunluğu sınırlarını veya Tm aralığını genişletmeyi deneyin.",
            f"Most candidates had a Tm {yon_en} the limit ({sinir} °C). Try widening "
            "the primer length limits or the Tm range.")
    if sebep == "gc clamp failed":
        return t(
            "Adayların çoğu 3' ucunda G/C bulundurma şartını (GC clamp) sağlamadı. "
            "Gelişmiş ayarlardan GC clamp şartını kaldırabilirsiniz.",
            "Most candidates failed the GC clamp requirement (G/C at the 3' end). "
            "You can drop the GC clamp requirement under advanced settings.")
    if sebep == "high end gc":
        return t(
            f"Adayların çoğunun 3' ucunda (son 5 baz) {sayi('primer_max_end_gc', 3)}'ten "
            "fazla G/C var — bölge GC'ce zengin. Gelişmiş ayarlardan '3' uçta en fazla "
            "G/C' değerini 4'e çıkarabilirsiniz; ama aşırı kararlı 3' uç yanlış yere "
            "oturma riskini artırır.",
            f"Most candidates carry more than {sayi('primer_max_end_gc', 3)} G/C in the "
            "last 5 bases — the region is GC-rich. You can raise 'max 3' G/C' to 4 under "
            "advanced settings, but an over-stable 3' end increases mispriming risk.")
    if sebep in ("high any compl", "high end compl", "high self any", "high self end"):
        return t(
            "Adayların çoğu kendi üzerine katlanma / dimer sınırını aştı. Bölge "
            "tekrarlı ya da palindromik olabilir; hedefi biraz kaydırmayı deneyin.",
            "Most candidates exceeded the self-folding / dimer limits. The region may "
            "be repetitive or palindromic; try shifting the target slightly.")
    if sebep == "long poly-x seq":
        return t(
            f"Adayların çoğunda {sayi('primer_max_poly_x')} bazdan uzun homopolimer "
            "var (AAAA gibi). Homopolimer sınırını artırabilirsiniz.",
            f"Most candidates contain a homopolymer longer than "
            f"{sayi('primer_max_poly_x')} bases (e.g. AAAA). You can raise that limit.")
    if sebep == "overlap excluded region":
        return t(
            "Yaygın varyantlardan kaçınma bu bölgede yerleşebilecek çoğu yeri kapattı. "
            "Gelişmiş ayarlardan 'yaygın varyantlardan kaçın'ı kapatıp tekrar deneyin — "
            "o zaman primer üzerindeki varyantlar işaretlenerek gösterilir.",
            "Avoiding common variants closed off most of the usable positions here. Turn "
            "off 'avoid common variants' under advanced settings and retry — variants "
            "falling on the primers will then be flagged instead.")
    if sebep in ("not in any ok left region", "not in any ok right region",
                 "not in any ok region"):
        return t(
            "Primerlerin yerleşebileceği bölge kısıtı çok dar kaldı. İki dizi modundaysanız "
            "'mesafe bilinmiyor' seçeneğini işaretleyin; ekson modundaysanız sınır şartını "
            "gevşetin.",
            "The allowed placement region was too narrow. In two-sequence mode tick "
            "'distance unknown'; in exon mode relax the junction requirement.")
    if sebep in ("too many ns", "too many ns in the sequence"):
        return t(
            "Şablonda çok fazla N (belirsiz baz) var — genomun boşluklu bir bölgesi "
            "olabilir. Hedefi biraz kaydırmayı deneyin.",
            "The template contains too many Ns (ambiguous bases) — this may be a gapped "
            "region of the genome. Try shifting the target slightly.")
    return None


def _dizi_ucu_notu(sonuc, sol, sag):
    """A3-02: Dizi modunda hedef dizinin ucuna yakin oldugu icin cift cikmadiysa dogru sebep.
    Hedef (min_dist_from_variant kadar genisletilmis) primerlere yer birakmali: her yanda en az
    primer_min_size baz. Bu SERT sinirdir (altinda primer3 hic aday uretemez; bkz.
    _seq_target_region). Sert sinirin ustunde ama yer 2 x primer_max_size'tan azken o yanin
    primer3 dokumu 'ok 0' ise sebep yine uca yakinlik olarak soylenir (yumusak durum:
    ornek TP53'te hedef 75: yer 25 baz, adaylarin hepsi GC/clamp'te elendi). Baska sebep
    (orta bolgede GC vb.) ise None doner, genel aciklama calisir."""
    p = sonuc.get("params_used") or {}
    girdi = sonuc.get("input") or {}
    tgt, uzunluk = girdi.get("target"), girdi.get("length")
    if sonuc.get("mode") != "sequence" or not tgt or not uzunluk:
        return None
    a, n = int(tgt[0]), int(tgt[1])
    excl, mn, mx = (int(p["min_dist_from_variant"]), int(p["primer_min_size"]),
                    int(p["primer_max_size"]))
    uzunluk = int(uzunluk)
    # primer3'e verilen SEQUENCE_TARGET'in iki yanindaki bos yer (bkz. _seq_target_region)
    bas = max(0, a - excl)
    son = min(uzunluk - 1, a + n - 1 + excl)
    yer = {"bas": bas, "son": uzunluk - 1 - son}
    once, sonra = a, uzunluk - (a + n)         # hedefin kendisinden once / sonra kalan baz
    gerek = excl + mn
    ok0 = {"bas": sol.get("ok", 0) == 0, "son": sag.get("ok", 0) == 0}
    sinirli = [k for k in ("bas", "son")
               if yer[k] < mn or (ok0[k] and yer[k] < 2 * mx)]
    if not sinirli:
        return None
    parcalar = []
    for k in sinirli:
        sert = yer[k] < mn
        kal = once if k == "bas" else sonra
        if k == "bas":
            konum_tr = f"başına çok yakın (hedef {a + 1}. baz)"
            konum_en = f"start (target at base {a + 1})"
            ek_tr, ek_en = "dizinin başını uzatın", "extend the start of the sequence"
            kaynak = sol
        else:
            konum_tr = f"sonuna çok yakın (hedeften sonra {sonra} baz kalıyor)"
            konum_en = f"end (only {sonra} bases remain after the target)"
            ek_tr, ek_en = "dizinin sonunu uzatın", "extend the end of the sequence"
            kaynak = sag
        if sert:
            parcalar.append(t(
                f"Hedef dizinin {konum_tr}: primer için yer yok. Hedeften {'önce' if k == 'bas' else 'sonra'} "
                f"en az {gerek} baz gerekir ('varyanta min uzaklık' {excl} + en kısa primer {mn}); "
                f"burada {kal} baz var. {ek_tr[0].upper() + ek_tr[1:]} ya da gelişmiş "
                "ayarlardan varyanta min uzaklığı küçültün.",
                f"The target is too close to the {konum_en}: there is no room for a primer. "
                f"At least {gerek} bases are needed {'before' if k == 'bas' else 'after'} the target "
                f"(minimum distance to the variant {excl} + shortest primer {mn}); there are "
                f"{kal}. {ek_en[0].upper() + ek_en[1:]} or reduce the minimum distance to the "
                "variant under advanced settings."))
        else:
            dokum = _explain_dokum(kaynak)
            parcalar.append(t(
                f"Hedef dizinin {konum_tr.replace('çok yakın', 'yakın')}: primere ayrılan bölge "
                f"yalnızca {yer[k]} baz ve bu dar bölgede ölçütleri sağlayan primer çıkmadı. "
                f"{ek_tr[0].upper() + ek_tr[1:]} ya da gelişmiş ayarlardan varyanta min uzaklığı "
                f"küçültün. {dokum}".strip(),
                f"The target is close to the {konum_en}: the region left for the primer is only "
                f"{yer[k]} bases and no primer in it met the criteria. "
                f"{ek_en[0].upper() + ek_en[1:]} or reduce the minimum distance to the variant "
                f"under advanced settings. {dokum}".strip()))
    return " ".join(parcalar)


def explain_notu(sonuc):
    """Sonuc bossa sebebini notes'a insan diliyle ekler. Sonucu yerinde degistirir."""
    if sonuc.get("num_returned"):
        return sonuc
    ex = sonuc.get("explain") or {}
    p = sonuc.get("params_used") or {}
    sol, sag, cift = (_explain_coz(ex.get("left")), _explain_coz(ex.get("right")),
                      _explain_coz(ex.get("pair")))
    # primer3 kabul edilebilir cift URETTIYSE liste bizim suzgeclerimizde (urun GC,
    # yerel tekrar, ekson siniri sarti) bosalmistir; sebebi onlar zaten yaziyor.
    # primer3'un dokumune bakmak yanlis sucluyordu: GC suzgeci bosalttiginda
    # "adaylarin cogu urun boyu kisitina takildi" deniyordu (2026-10-25).
    if cift.get("ok", 0) > 0:
        # Arayuz primer3'un ham dokumunu de gosteriyor; o da ayni yanlis sebebi
        # yaziyordu. Bayrak konur, arayuz bu durumda ham dokumu gizler.
        sonuc["self_filtered"] = True
        return sonuc
    if sonuc.get("mode") == "breakpoint":
        # Bu modda sablonun yarisi forward'a, yarisi reverse'e YAPISI GEREGI kapali;
        # "bolge kisiti" her zaman en buyuk kalem cikip asil sebebi (GC vb.) gizliyor
        # ve iki dizi / ekson modlarina ait bir oneri yazdiriyordu (2026-10-17).
        for d in (sol, sag):
            d.pop("not in any ok left region", None)
            d.pop("not in any ok right region", None)

    # Tek primer duzeyinde mi tikandi, yoksa ciftlestirmede mi? Ayrimi yapmak
    # sart: "urun boyu tutmadi" ile "hic uygun forward yok" cok farkli sorunlar.
    sol_ok, sag_ok = sol.get("ok", 0), sag.get("ok", 0)
    uc_notu = _dizi_ucu_notu(sonuc, sol, sag)           # A3-02
    if uc_notu:
        sonuc["notes"] = list(sonuc.get("notes") or []) + [uc_notu]
        sonuc["self_filtered"] = True       # ham primer3 dokumu yanlis sebep gosteriyordu
        return sonuc
    # DNA ve kirilma noktasinda sol / sag genomiktir; arayuz eksi iplikteki genlerde
    # F/R adlarini genin yonune cevirdigi icin (yon.js) burada yon adi degil koordinat
    # tarafi yazilir: "Forward tarafinda" orada gosterilen Reverse'in tarafi olurdu.
    genomik = sonuc.get("mode") in (None, "breakpoint")
    if sol_ok == 0 and sag_ok == 0 and (sol or sag):
        taraf = t("Her iki yönde de: ", "On both sides: ")
        kaynak = {k: sol.get(k, 0) + sag.get(k, 0) for k in set(sol) | set(sag)}
    elif sol_ok == 0 and sol:
        taraf, kaynak = (t("Küçük koordinat tarafında (soldaki primer): ",
                           "On the lower-coordinate side (left primer): ") if genomik
                         else t("Forward tarafında: ", "On the forward side: ")), sol
    elif sag_ok == 0 and sag:
        taraf, kaynak = (t("Büyük koordinat tarafında (sağdaki primer): ",
                           "On the higher-coordinate side (right primer): ") if genomik
                         else t("Reverse tarafında: ", "On the reverse side: ")), sag
    else:
        taraf, kaynak = "", cift

    sebep, _ = _explain_baskin(kaynak)
    oneri = _explain_oneri(sebep, p, _sablon_uzunlugu(sonuc))
    dokum = _explain_dokum(kaynak)
    if oneri or dokum:
        metin = (taraf + oneri) if oneri else ""
        if dokum:
            metin = (metin + " " + dokum).strip()
        sonuc["notes"] = list(sonuc.get("notes") or []) + [metin]
    return sonuc


# Kromozom oneki ancak IKI NOKTA ile birlikte sayilir. Once ":" istege bagliydi ve
# "[\dXYMT]*" baslangic koordinatini yutuyordu: "50000001-50000120" -> chr 50000000,
# bas 1 (2026-10-25). Onek varsa en fazla iki karakter (2, X, MT).
_ARALIK = re.compile(r"^\s*(?:(?:chr)?[\dXYMT]{1,2}\s*:\s*)?([\d.,]+)\s*[-–—_]\s*([\d.,]+)\s*$",
                     re.I)


# Binlik ayiricili koordinat: "7.676.154", "7,676,154", "7 676 154" (tek tur ayirici,
# uclu gruplar). Eskiden nokta ve virgul GOZETMEKSIZIN siliniyordu: "7676154.5"
# sessizce 76.761.545 oluyordu - kromozomun icinde kaldigi icin hata da vermiyordu
# (2026-10-29 hata taramasi). Ondalik gorunumlu girdi artik reddedilir.
_BINLIKLI = re.compile(r"^[0-9]{1,3}(?:([.,\s])[0-9]{3})(?:\1[0-9]{3})*$")

# Konum en cok 12 basamak: en uzun kromozom 9 basamakli (chr1 ~249 Mb); bundan uzunu yazim
# hatasidir ve Python'un int() siniri (4.300 basamak) 500 "Beklenmeyen hata" veriyordu.
_SAYI_EN_COK_BASAMAK = 12


def _sayi(metin):
    """Basindaki eksi KORUNUR: "-5" burada degil, "1'den kucuk olamaz" kontrolunde
    reddedilsin - kullanici sayi yazmistir, sorun isaretidir.
    Yalniz ASCII rakam (0-9): str.isdigit() ust simge "²" ve baska yazi sistemlerinin
    rakamlarini da sayip int()'in ValueError'una (500) dusuyordu. Okunamayan her girdi
    PrimerError (400) olur."""
    s = str(metin).strip()
    isaret = "-" if s.startswith("-") else ""
    govde = s[1:].strip() if isaret else s
    gir = repr(s if len(s) <= 40 else s[:40] + "…")      # uzun girdi mesaji sisirmesin
    if not re.fullmatch(r"[0-9]+", govde):
        if _BINLIKLI.match(govde):
            govde = re.sub(r"[.,\s]", "", govde)
        elif re.fullmatch(r"[0-9.,\s]+", govde):
            raise PrimerError(t(
                f"Koordinat tam sayı olmalı (girilen: {gir}). Ondalık kısım ya da "
                "hatalı basamak gruplaması var; ayırıcısız yazın (örn. 7676154).",
                f"The coordinate must be a whole number (got {gir}). It has a decimal "
                "part or wrong digit grouping; write it without separators (e.g. 7676154)."))
        else:
            raise PrimerError(t(f"Koordinat sadece rakam olmalı (girilen: {gir}).",
                                f"The coordinate must contain digits only (got {gir})."))
    if len(govde) > _SAYI_EN_COK_BASAMAK:
        raise PrimerError(t(
            f"Koordinat çok uzun ({tr_sayi(len(govde))} basamak): en fazla "
            f"{_SAYI_EN_COK_BASAMAK} basamaklı bir konum yazın (girilen: {gir}).",
            f"The coordinate is too long ({len(govde):,} digits): write a position of at most "
            f"{_SAYI_EN_COK_BASAMAK} digits (got {gir})."))
    return int(isaret + govde)


def konum_oneki(position):
    """Konum metnindeki kromozom onekini normalize edilmis olarak doner
    ("chr2:50,000,001-50,000,300" -> "2"); onek yoksa ya da konum liste ise None."""
    if isinstance(position, (list, tuple)):
        return None
    metin = str(position)
    if ":" not in metin:
        return None
    onek = "".join(metin.rsplit(":", 1)[0].split())
    if not onek:
        return None
    # RefSeq kromozom erisim numarasi (ClinVar/HGVS: "NC_000017.11:g.7676154") -> kromozom
    m = re.fullmatch(r"NC_0*(\d+)(?:\.(\d+))?", onek, flags=re.IGNORECASE)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 22:
            return str(n)
        if n in (23, 24, 12920):
            return {23: "X", 24: "Y", 12920: "MT"}[n]
    return normalize_chrom(onek)


def konum_erisim_surumu(position):
    """Konum metnindeki RefSeq kromozom erisiminin SURUMU: "NC_000017.10:7676154" ->
    ("17", "NC_000017", 10); surumsuz erisimde, erisim olmayan onekte ya da liste girdisinde
    None. Mitokondri (NC_012920) icin de doner; denetimde atlanir (bkz. erisim_surumu_denetimi)."""
    if isinstance(position, (list, tuple)):
        return None
    metin = str(position)
    if ":" not in metin:
        return None
    onek = "".join(metin.rsplit(":", 1)[0].split())
    m = re.fullmatch(r"(NC_0*)(\d+)\.(\d+)", onek, flags=re.IGNORECASE)
    if not m:
        return None
    n = int(m.group(2))
    krom = str(n) if 1 <= n <= 22 else {23: "X", 24: "Y", 12920: "MT"}.get(n)
    if not krom:
        return None
    return krom, "NC_%06d" % n, int(m.group(3))


def erisim_surumu_denetimi(position, assembly):
    """Konumdaki RefSeq erisim SURUMU secili derlemeye uymuyorsa acik hata firlatir.
    NC_000017.10 GRCh37, NC_000017.11 GRCh38 koordinatidir; eskiden surum eki yok sayiliyor,
    GRCh38 secili iken GRCh37 koordinati sessizce kabul edilip baska lokusun primerleri
    uretiliyordu (2026-11-10 denetimi D3-02).
    Dogrulanabilir kaynak: GRCh38 surumleri yerel MANE dosyasindan (transcripts.
    grch38_kromozom_erisimleri). GRCh37 icin yerelde dogrulanabilir bir erisim listesi YOK;
    bu yuzden: GRCh38 secili -> MANE'deki surumden farkli her surum reddedilir; GRCh37 secili ->
    yalniz GRCh38'in surumu reddedilir, baska surum kabul edilir. Surumsuz erisim, mitokondri
    (NC_012920.1 iki derlemede de rCRS) ve MANE dosyasi yokken (karsilastirilamaz) kabul."""
    if assembly not in ("GRCh37", "GRCh38"):
        return
    ayr = konum_erisim_surumu(position)
    if ayr is None:
        return
    krom, acc, surum = ayr
    if krom == "MT":
        return
    ref = tr.grch38_kromozom_erisimleri().get(krom)
    if ref is None:
        return
    ref_acc, ref_surum = ref
    yazilan = "%s.%d" % (acc, surum)
    grch38 = "%s.%d" % (ref_acc, ref_surum)
    if assembly == "GRCh38" and surum != ref_surum:
        raise PrimerError(t(
            f"Konumdaki erişim numarası ({yazilan}) seçili derlemeye (GRCh38) ait değil; GRCh37 "
            f"koordinatı olabilir (GRCh38 için {grch38}). Tasarım yapılmadı. Derleme seçimini "
            "ya da konumu kontrol edin; iki sürümün koordinatları farklıdır.",
            f"The accession in the position ({yazilan}) does not belong to the selected assembly "
            f"(GRCh38); it may be a GRCh37 coordinate (GRCh38 uses {grch38}). No design was made. "
            "Check the assembly selection or the position; the coordinates of the two versions "
            "differ."))
    if assembly == "GRCh37" and surum == ref_surum:
        raise PrimerError(t(
            f"Konumdaki erişim numarası ({yazilan}) GRCh38'e ait; seçili derleme GRCh37. Tasarım "
            "yapılmadı. Derleme seçimini ya da konumu kontrol edin; iki sürümün koordinatları "
            "farklıdır.",
            f"The accession in the position ({yazilan}) belongs to GRCh38, but GRCh37 is "
            "selected. No design was made. Check the assembly selection or the position; the "
            "coordinates of the two versions differ."))


_BILINEN_KROMOZOM = frozenset([str(i) for i in range(1, 23)] + ["X", "Y", "MT"])


def kromozom_celiskisi(onek, chrom):
    """Konum oneki ile secili kromozom (kromozom alani ya da genin kromozomu) ayni degilse
    acik bir hata firlatir. Eskiden onek sessizce atiliyor, tasarim kromozom alanindaki
    kromozomda yapiliyordu: UCSC'den "chr2:..." yapistiran kullanici baska bir lokusun
    primerlerini aliyordu. Ayni kromozom ("chr17:" ile 17) sessizce kabul edilir."""
    if onek is None:
        return
    secili = normalize_chrom(chrom)
    if onek == secili:
        return
    if onek not in _BILINEN_KROMOZOM:
        raise PrimerError(t(
            f"Konumdaki önek ({onek}) bir kromozom olarak tanınmadı. Tasarım yapılmadı; öneki "
            f"silin ya da kromozomu \"chr{secili}:\" biçiminde yazın.",
            f"The position prefix ({onek}) was not recognised as a chromosome. No design was "
            f"made; remove the prefix or write the chromosome as \"chr{secili}:\"."))
    if onek != secili:
        raise PrimerError(t(
            f"Kromozom çelişkisi: konumdaki önek chr{onek} diyor, kromozom alanı (ya da gen) "
            f"chr{secili} diyor. Tasarım yapılmadı; ikisini aynı kromozoma getirin ya da "
            "konumdaki \"chr…:\" önekini silin.",
            f"Chromosome conflict: the position prefix says chr{onek}, but the chromosome "
            f"field (or gene) says chr{secili}. No design was made; make them the same "
            "chromosome or remove the \"chr…:\" prefix from the position."))


def oneksiz_koordinat(deger, chrom, assembly=None):
    """Tek koordinat alani ("chr7:117559000") icin: onek chrom ile celisirse hata, ayniysa
    onek atilip yalniz koordinat doner (kirilma noktasi baslangic/bitis alanlari).
    assembly verilirse RefSeq erisim surumu de secili derlemeyle karsilastirilir."""
    onek = konum_oneki(deger)
    if onek is None or not str(chrom or "").strip():
        return deger
    kromozom_celiskisi(onek, chrom)
    erisim_surumu_denetimi(deger, assembly)
    return re.sub(r"^g\.\s*", "", str(deger).rsplit(":", 1)[1].strip(), flags=re.I)


def varyant_araligi(position):
    """Konum girdisini (bas, bit) araligina cevir.

    Tek koordinat ("50000001") nokta varyanttir -> (50000001, 50000001).
    Aralik ("50000001-50000300", "chr2:50,000,001-50,000,300") cok bazli varyantin
    TAMAMIDIR; yasak bolge bu araligin tamamini kapsar. Eskiden yalnizca tek nokta
    alinirdi ve 120 bp'lik bir delesyonun baslangici verilince primerlerin 5'i
    varyantin ICINE dusuyordu (olculdu 2026-10-25) - o primer delesyonlu alele
    baglanmaz, heterozigot hasta homozigot gorunur."""
    if isinstance(position, (list, tuple)):
        if len(position) != 2:
            raise PrimerError(t("Konum aralığı iki koordinattan oluşmalı.",
                                "A position range must have two coordinates."))
        bas, bit = _sayi(position[0]), _sayi(position[1])
    else:
        metin = str(position).strip()
        # Onek ("chr2:", "NC_000017.11:") burada atilir; kromozom ve surum denetimi
        # cagiranda (konum_oneki, erisim_surumu_denetimi). HGVS "g." oneki de atilir:
        # "NC_000017.11:g.7676154" ve "NC_000017.11:7676154-7676160" (E1-01).
        if ":" in metin:
            metin = metin.rsplit(":", 1)[1].strip()
        metin = re.sub(r"^g\.\s*", "", metin, flags=re.I)
        m = _ARALIK.match(metin)
        if m:
            bas, bit = _sayi(m.group(1)), _sayi(m.group(2))
        else:
            bas = bit = _sayi(metin)
    if bit < bas:
        raise PrimerError(t(
            f"Konum aralığının bitişi ({tr_sayi(bit)}) başlangıcından ({tr_sayi(bas)}) küçük olamaz.",
            f"The end of the position range ({bit:,}) cannot be before its start ({bas:,})."))
    return bas, bit


def design_primers(assembly, chrom, position, gene=None, params=None, havuz=None):
    """
    Ana giris noktasi.
    assembly: 'GRCh37' | 'GRCh38'
    chrom:    '1', 'X', 'chr17' (normalize edilir)
    position: 1-tabanli genomik koordinat ya da varyantin tamamini kapsayan
              aralik ("50000001-50000300"); bkz. varyant_araligi.
    gene:     opsiyonel; verilmezse kromozom zorunlu.
    havuz:    sozluk verilirse primer3 yaniti ve sirali aday havuzu buraya yazilir (kopya.py);
              donen sonuc etkilenmez.
    """
    p = _ayar_birlestir([DEFAULTS], params)

    if assembly not in ("GRCh37", "GRCh38"):
        raise PrimerError(t("assembly 'GRCh37' veya 'GRCh38' olmalı.",
                            "assembly must be 'GRCh37' or 'GRCh38'."))

    # Kromozom yoksa gen adindan bul (once yerel tablo; bkz. gen_konumu)
    gene_info = None
    gen_adi = str(gene).strip() if gene else ""
    if gen_adi and not chrom:
        gene_info = gen_konumu(gen_adi, assembly)
        chrom = gene_info["chrom"]
    elif gen_adi:
        # Kromozom da girilmis: gen adi yalnizca TUTARLILIK kontrolu icin
        # kullanilir. Bunun icin internete gidilmez; tablo yoksa kontrol atlanir.
        bolgeler = gen_bolgeleri(gen_adi, assembly) or {}
        c = normalize_chrom(chrom)
        secim = c if c in bolgeler else (
            "X" if "X" in bolgeler else
            sorted(bolgeler, key=_kromozom_sirasi)[0] if bolgeler else None)
        if secim:
            a, b, s = bolgeler[secim]
            gene_info = {"chrom": secim, "start": a, "end": b, "strand": s, "id": None,
                         "source": "local"}
    if not chrom:
        raise PrimerError(t("Kromozom belirtilmeli (veya gen adi verilmeli).",
                            "A chromosome (or a gene name) must be given."))

    # Konumdaki "chr2:" oneki kromozomla celisirse tasarim yapilmaz (kromozom alanindan ya da
    # gen adindan gelen kromozom icin ayni kural)
    kromozom_celiskisi(konum_oneki(position), chrom)
    erisim_surumu_denetimi(position, assembly)
    v_bas, v_bit = varyant_araligi(position)
    position = v_bas                     # geriye donuk: tek koordinat alanlari
    aralik_verildi = v_bit > v_bas
    # Kromozom disi koordinat: acik mesajla reddedilir. Negatif/sifir koordinat
    # eskiden primer3'e kadar gidip "Beklenmeyen hata" (500) veriyordu; kromozom
    # sonunu asan koordinat ise sessizce Ensembl'e (internete) gidiyordu.
    if v_bas < 1:
        raise PrimerError(t("Koordinat 1'den küçük olamaz.",
                            "The coordinate cannot be smaller than 1."))
    uzunluk = kromozom_uzunlugu(assembly, chrom)
    if uzunluk is not None and v_bit > uzunluk:
        raise _kromozom_disi(assembly, chrom, v_bit, uzunluk)
    # Psodootozomal bolge: dizi X ve Y'de ayni. Y'nin PAR'i GRCh37 Ensembl
    # dosyasinda N ile maskeli (tasarim orada imkansiz), GRCh38'de ise X ile
    # birebir ayni; bu yuzden Y koordinati X'teki esine cevrilip tek yerde
    # tasarlanir (bkz. par.py). Not her durumda kullaniciya yazilir.
    par_notlari = []
    pb = par.bolge(assembly, chrom, position)
    if pb and pb["kromozom"] == "Y":
        _xk, x_pos = par.es_konum(assembly, "Y", position)
        par_notlari.append(t(
            f"chrY:{tr_sayi(position)} psödootozomal bölgede ({pb['ad']}); dizisi X ile birebir aynı "
            f"olduğu için tasarım X'teki eş konumda (chrX:{tr_sayi(x_pos)}) yapıldı.",
            f"chrY:{position:,} lies in the pseudoautosomal region ({pb['ad']}); its sequence "
            f"is identical to X, so the design was made at the equivalent X position "
            f"(chrX:{x_pos:,})."))
        chrom, position = "X", x_pos
        v_bas, v_bit = x_pos, x_pos + (v_bit - v_bas)
        if gene_info and normalize_chrom(gene_info.get("chrom")) == "Y" and gen_adi:
            xb = (gen_bolgeleri(gen_adi, assembly) or {}).get("X")
            if xb:
                gene_info = {"chrom": "X", "start": xb[0], "end": xb[1], "strand": xb[2],
                             "id": None, "source": "local"}
    if pb:
        par_notlari.append(par.not_metni(pb["ad"]))
    # Koordinat yazilan genin uzagindaysa (cogunlukla GRCh37/GRCh38 karisikligi) uyar
    gen_notu = gen_uzaklik_notu(gen_adi, gene_info, chrom, (v_bas + v_bit) // 2, assembly)
    # Yakin-ozdes paralogu olan gen mi (PMS2/PMS2CL gibi)? Ozgulluk taramasi
    # istege bagli oldugu icin bu, kullanicinin dugmeye basmasi gerektigini
    # ONCEDEN haber veren tek yer.
    # rozet: DNA sonuclarini arayuz otomatik tarar; uyari dugme yerine rozetlere yonlendirir
    paralog_notu = paralog.notu(assembly, gen_adi, chrom, v_bas, v_bit, mod="dna", rozet=True)
    flank = int(p["flank"])
    # Ust sinir: 5 Mb'lik bir flank 28 sn surup primer3'te 500 ile bitiyordu
    # (2026-10-10). 10 kb'lik iki yan, standart PCR urununun cok ustunde.
    if not 1 <= flank <= FLANK_MAKS:
        raise PrimerError(t(
            f"Bölge genişliği (flank) 1-{tr_sayi(FLANK_MAKS)} bp arasında olmalı (girilen: {tr_sayi(flank)}).",
            f"The region width (flank) must be between 1 and {FLANK_MAKS:,} bp (got {flank:,})."))
    tpl_start = max(1, v_bas - flank)
    tpl_end = v_bit + flank

    template, source = get_sequence(assembly, chrom, tpl_start, tpl_end)
    if not template or len(template) < p["product_size_min"]:
        raise PrimerError(t("Çekilen dizi çok kısa veya boş.",
                            "The retrieved sequence is too short or empty."))

    # Varyantin sablon icindeki 0-tabanli indeksleri (tek koordinatta ikisi ayni)
    v_index = v_bas - tpl_start
    v_index_son = v_bit - tpl_start
    excl = int(p["min_dist_from_variant"])

    # Kromozom ucuna cok yakin varyant: bir yanda primer koyacak yer yok. Eskiden
    # sablon kromozom sonunda kesildigi icin hedef bolge sablonun disina tasiyor,
    # primer3 "TARGET beyond end of sequence" deyip 500 veriyordu (2026-10-08,
    # gercek primer3 ile rastgele testte bulundu). Her iki yanda en az
    # (varyant mesafesi + en kisa primer) kadar dizi gerekir.
    gerek = excl + int(p["primer_min_size"])
    sol, sag = v_index, len(template) - 1 - v_index_son
    if sol < gerek or sag < gerek:
        c = normalize_chrom(chrom)
        yer_tr, yer_en = ("başına", "start") if sol < gerek else ("sonuna", "end")
        raise PrimerError(t(
            f"Varyant kromozomun {yer_tr} çok yakın (chr{c}:{tr_sayi(position)}). Varyanta en az "
            f"{excl} bp uzaklıkta en az {int(p['primer_min_size'])} nt'lik bir primer koymak "
            f"için iki yanda da {gerek} bp dizi gerekir; bu yanda yalnızca "
            f"{min(sol, sag)} bp var.",
            f"The variant is too close to the chromosome {yer_en} (chr{c}:{position:,}). "
            f"Placing a primer of at least {int(p['primer_min_size'])} nt at least {excl} bp "
            f"from the variant needs {gerek} bp of sequence on both sides; this side has "
            f"only {min(sol, sag)} bp."))

    tgt_start = max(0, v_index - excl)
    tgt_son = min(len(template) - 1, v_index_son + excl)
    tgt_len = max(1, tgt_son - tgt_start + 1)
    # Urun hedefin TAMAMINI kapsamak zorunda; sigmiyorsa primer3 bos doner ve
    # sebebi "urun boyu" gibi gorunur. Onceden ve cozumuyle birlikte soyle.
    _ust = int(p["product_size_max"])
    if p.get("pcr_max") is not None:
        _ust = min(_ust, int(p["pcr_max"]))
    _gerekli = tgt_len + 2 * int(p["primer_min_size"])
    if _gerekli > _ust:
        raise PrimerError(t(
            f"Varyant aralığı {tr_sayi(v_bit - v_bas + 1)} bp; iki yanda {excl} bp pay ve primerlerle "
            f"birlikte ürün en az {tr_sayi(_gerekli)} bp olur, geçerli üst sınır ise {tr_sayi(_ust)} bp. "
            "Delesyon ya da duplikasyon için Kırılma noktası sekmesini kullanın (primerler "
            "bölgenin dışına konur, ürün kısa kalır); ya da payı/ürün sınırını değiştirin.",
            f"The variant range is {v_bit - v_bas + 1:,} bp; with {excl} bp on each side plus "
            f"the primers the product would be at least {_gerekli:,} bp, while the effective "
            f"maximum is {_ust:,} bp. For a deletion or duplication use the Breakpoint tab "
            "(primers go outside the region, so the product stays short), or change the "
            "margin / product limit."))

    # Yaygin varyantlar: uyarmak yerine primer3'e bastan yasak bolge olarak verilir
    snps = _snp_template_offsets(
        _collect_snps(assembly, normalize_chrom(chrom), tpl_start, tpl_end, p), tpl_start)
    # Yasaklama sadece secenek acikken; toplama her zaman yapilir (raporlama icin)
    excluded = (_excluded_from_snps(snps, len(template))
                if p.get("avoid_common_snps", True) else [])

    seq_args = {
        "SEQUENCE_ID": f"{assembly}_{chrom}_{v_bas}_{v_bit}",
        "SEQUENCE_TEMPLATE": template,
        "SEQUENCE_TARGET": [tgt_start, tgt_len],
    }
    if excluded:
        seq_args["SEQUENCE_EXCLUDED_REGION"] = excluded
    global_args = _build_global_args(p)

    dahil = _dahil_bolge(len(template), seq_args.get("SEQUENCE_TARGET"), p)
    if dahil:
        seq_args["SEQUENCE_INCLUDED_REGION"] = dahil
    res = primer3.bindings.design_primers(seq_args, global_args)

    notes = ([gen_notu] if gen_notu else []) + ([paralog_notu] if paralog_notu else []) + par_notlari
    if aralik_verildi:
        notes.append(t(
            f"Varyant {tr_sayi(v_bit - v_bas + 1)} bp olarak verildi (chr{normalize_chrom(chrom)}:"
            f"{tr_sayi(v_bas)}-{tr_sayi(v_bit)}); primerler bu aralığın tamamının ve iki yanda {excl} bp'lik "
            "payın dışına kondu. Böylece hiçbir primer varyantın içine düşmez — düşseydi "
            "varyantlı alele bağlanamaz, heterozigot örnek homozigot görünürdü.",
            f"The variant was given as {v_bit - v_bas + 1:,} bp (chr{normalize_chrom(chrom)}:"
            f"{v_bas:,}-{v_bit:,}); the primers were placed outside the whole range plus "
            f"{excl} bp on each side. No primer can fall inside the variant — one that did "
            "would not bind the variant allele, making a heterozygous sample look homozygous."))
    sinir_notu = _pcr_sinir_notu(p)
    if sinir_notu:
        notes.append(sinir_notu)
    if excluded and int(res.get("PRIMER_PAIR_NUM_RETURNED", 0)) == 0:
        # SNP yogun bolge: kisiti kaldirmak zorundayiz ama bunu SESSIZCE yapmak
        # en kotusu olurdu - kullanici primerin SNP uzerinde oldugunu bilmeli.
        seq_args.pop("SEQUENCE_EXCLUDED_REGION")
        res = primer3.bindings.design_primers(seq_args, global_args)
        # Kisit kaldirildiginda da cift cikmadiysa "varyantlar isaretlendi" demek yanlis
        if int(res.get("PRIMER_PAIR_NUM_RETURNED", 0)):
            notes.append(t(
                f"UYARI: Bölge yaygın varyant açısından yoğun ({len(excluded)} varyant); "
                "hepsinden kaçınılınca uygun primer kalmadı. Kısıt kaldırıldı - aşağıdaki "
                "primerlerin üzerindeki varyantlar işaretlendi, özellikle 3' uca yakın "
                "olanlara dikkat edin.",
                f"WARNING: This region is dense in common variants ({len(excluded)}); "
                "avoiding all of them left no usable primer. The constraint was lifted - "
                "variants falling on the primers below are flagged; pay particular "
                "attention to those close to the 3' end."))

    # Genis havuzu 3'-odakli dimer skoruyla YENIDEN sirala, sonra num_return'e kirp
    sira = _rank_order(res, p, template=template)
    if havuz is not None:
        # kopya.ara ayni girdiyle primer3'ten kurallara uyan BUTUN ciftleri ister (v0.8.36)
        havuz.update(res=res, sira=sira, seq_args=dict(seq_args), global_args=dict(global_args),
                     template=template)
    order = sira[:int(p["num_return"])]
    pairs = _collect_pairs(res, tpl_start, order, p, template=template, hedef=(v_index, v_index_son))
    _bolge_ekle(pairs, assembly, chrom)
    notes.extend(_suzgec_notlari(sira, p, pairs))
    _annotate_pair_snps(pairs, res, order, snps)

    explain = {
        "left": res.get("PRIMER_LEFT_EXPLAIN", ""),
        "right": res.get("PRIMER_RIGHT_EXPLAIN", ""),
        "pair": res.get("PRIMER_PAIR_EXPLAIN", ""),
    }

    return {
        "input": {
            "assembly": assembly,
            "chrom": normalize_chrom(chrom),
            "position": v_bas,
            "position_end": v_bit,
            "variant_length": v_bit - v_bas + 1,
            "gene": gene,
        },
        "sequence_source": source,
        "template_start": tpl_start,
        "template_end": tpl_end,
        "variant_index_in_template": v_index,
        "params_used": p,
        "num_returned": len(pairs),
        "pairs": pairs,
        "explain": explain,
        "gene_info": gene_info,
        "notes": notes,
        # Yalnizca psodogen uyarisi cikan genlerde: arayuz kopyadan ayrisan cift arar (kopya.py)
        **({"paralog_var": True} if paralog_notu else {}),
        "dbsnp": {
            "available": dbsnp.get_index(assembly) is not None,
            "in_template": len(snps),
            "excluded": len(excluded),
            "applied": bool(excluded) and "SEQUENCE_EXCLUDED_REGION" in seq_args,
        },
    }


# ------------------------------------------------------------------
# RNA / cDNA modu
# ------------------------------------------------------------------
CDNA_DEFAULTS = {
    # Ekson siniri davranisi
    "junction_flanking": True,    # (b) F ve R farkli eksonlarda; urun en az bir siniri kapsar
    "junction_overlap": False,    # (a) primerlerden biri sinirin UZERINE otursun (gDNA'ya baglanmaz);
                                  #     ekson atlama testinde de gecerli (yalniz blogun disindaki sinirlar)
    "min_3p_overlap_junction": 4, # (a) modunda primerin sinirin otesine gecen 3' baz sayisi
    "min_5p_overlap_junction": 7, # (a) modunda 5' tarafta kalan baz sayisi
    # Ekson atlama testi
    "skip_margin": 5,             # primer, hedef eksonun sinirlarina bu kadar bp yaklasmasin
    "skip_min_flank": 120,        # atlama testinde eksonun her iki yanindan en az bu kadar urun
    "skip_max_flank": 400,        # ... en fazla bu kadar (kisa urun = kucuk eksonda jelde ayrilabilirlik)
    "skip_resolution_warn": 40,   # iki bandin farki bu bp'nin altindaysa "jelde ayrimi zor" uyarisi
    "skip_ratio_warn": 0.90,      # atlanmis/normal orani bunun ustundeyse bantlar cok yakin
    "skip_wt_long_product": 0.02, # uzun urun cezasi (bp basina) - kisa amplikonu one cikarir
}

_COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")


def revcomp(seq):
    """Ters tumleyen."""
    return seq.translate(_COMPLEMENT)[::-1]


def build_cdna(tx, assembly):
    """Transkriptin cDNA dizisini genom FASTA'sindan kur: eksonlari birlestir,
    eksi iplikte ters tumleyenini al. Doner: (cdna, kaynak)."""
    span, source = get_sequence(assembly, tx["chrom"], tx["tx_start"], tx["tx_end"])
    if not span or len(span) < (tx["tx_end"] - tx["tx_start"] + 1):
        raise PrimerError(t(
            f"{tx['acc']} için genomik dizi eksik alındı ({tx['chrom']}:"
            f"{tx['tx_start']}-{tx['tx_end']}).",
            f"Incomplete genomic sequence retrieved for {tx['acc']} ({tx['chrom']}:"
            f"{tx['tx_start']}-{tx['tx_end']})."))

    # exons genomik artan sirada; span'in ilk bazi tx_start
    pieces = [span[s - tx["tx_start"]: e - tx["tx_start"] + 1] for s, e in tx["exons"]]
    cdna = "".join(pieces)
    if tx["strand"] == "-":
        cdna = revcomp(cdna)

    if len(cdna) != tx["cdna_length"]:  # pragma: no cover - tutarlilik kontrolu
        raise PrimerError(t(
            f"cDNA uzunluğu beklenenden farklı ({len(cdna)} != {tx['cdna_length']}).",
            f"cDNA length differs from the expected value "
            f"({len(cdna)} != {tx['cdna_length']})."))
    return cdna, source


# ------------------------------------------------------------------
# K1 (F-01): RNA yollari transkripti HER ZAMAN GRCh38'den kurar; kodlayan dizi denetimi
# ------------------------------------------------------------------
# cDNA, NM dizisinden degil genom + UCSC refGene hizalamasindan kurulur. Hizalama
# boslukluysa c. ve ekson numaralari kayar. MANE Select GRCh38 ile gelir; GRCh37 satirinda
# kayma 6 kat daha sik (olcum: 185 / 18.751 isaretli, GRCh38'de 64 / 18.761). Bu yuzden RNA
# yollari (tasarim, ekson atlama, ekson dugmeleri, Degerlendir, transkript listesi) ustte
# hangi derleme secili olursa olsun GRCh38'i kullanir.
RNA_DERLEME = "GRCh38"
_DURDURMA_KODONLARI = frozenset(("TAA", "TAG", "TGA"))
_KOD_ONBELLEK = {}          # kodlayan dizi denetimi sonuclari (transkript + genom yolu basina)
_ISARET_ONBELLEK = {}       # DNA / Kirilma noktasi etiketi icin isaret (derleme + NM + genom yolu)
_ONBELLEK_MAKS = 50000


def rna_derleme(secilen=None):
    """RNA yollarinda kullanilacak derleme (secilen ne olursa olsun GRCh38)."""
    return RNA_DERLEME


def rna_derleme_notu(secilen):
    """Ustte GRCh37 secili iken RNA sonucuna konan kisa not (TR/EN); aksi halde None."""
    if secilen == RNA_DERLEME:
        return None
    return t(
        f"Not: RNA sekmesi transkripti her zaman {RNA_DERLEME} genomundan kurar (MANE Select "
        f"{RNA_DERLEME} üzerinde tanımlıdır); gösterilen genomik konumlar {RNA_DERLEME} konumlarıdır.",
        f"Note: the RNA tab always builds the transcript from the {RNA_DERLEME} genome (MANE Select "
        f"is defined on {RNA_DERLEME}); the genomic positions shown are {RNA_DERLEME} positions.")


def _kod_hesapla(cds):
    """Kodlayan dizi (c.1 ... durdurma kodonu) uc olcutle denetlenir: (a) uzunluk 3'un
    kati degil, (b) son kodon durdurma kodonu degil, (c) son kodondan onceki kodonlarda
    durdurma kodonu var. ATG ile baslamama olcut DEGILDIR (MYC, VEGFA gibi gercek ATG disi
    baslangiclar var). Selenoprotein ve gercek durdurma tasiyan genler eleme yapilmadan
    isaretlenir; uyari metni bunu soyler."""
    n = len(cds)
    kodonlar = [cds[j:j + 3] for j in range(0, n - 2, 3)]
    govde = kodonlar[:-1] if n >= 3 else []
    ic = [i + 1 for i, k in enumerate(govde) if k in _DURDURMA_KODONLARI]
    son = cds[-3:] if n >= 3 else cds
    a = n % 3 != 0
    b = son not in _DURDURMA_KODONLARI
    c = bool(ic)
    nedenler = [ad for ad, v in (("mod3", a), ("son_kodon", b), ("erken_durdurma", c)) if v]
    return {"isaretli": bool(nedenler), "nedenler": nedenler, "cds_uzunluk": n,
            "son_kodon": son, "ilk_durdurma_kodon_no": ic[0] if ic else None,
            "durdurma_sayisi": len(ic)}


def _cds_yerel(tx, assembly):
    """Yalniz kodlayan bolgenin dizisi (transkript yonunde), yerel genomdan: tum aralik
    okunmaz, yalniz CDS ile kesisen eksonlar. build_cdna ile ayni dizi."""
    cs, ce = tx["cds_start_g"], tx["cds_end_g"]
    parca = []
    for s, e in tx["exons"]:
        a, b = max(s, cs), min(e, ce)
        if a <= b:
            seq = fetch_sequence_local(assembly, tx["chrom"], a, b)
            if not seq or len(seq) != b - a + 1:
                raise PrimerError(t(
                    f"{tx['acc']} için kodlayan dizi eksik okundu.",
                    f"The coding sequence of {tx['acc']} was read incompletely."))
            parca.append(seq)
    cds = "".join(parca)
    return revcomp(cds) if tx["strand"] == "-" else cds


def kod_denetimi(tx, assembly, cdna=None):
    """Transkriptin kodlayan dizisi denetimi (tek yer; sonuc onbellekte). cdna verilirse
    (build_cdna sonucu) ondan okunur; verilmezse YALNIZ yerel genomdan (internete cikmaz).
    Doner: _kod_hesapla sozlugu ya da None (kodlamayan transkript / yerel genom yok)."""
    if not tx.get("coding") or tx.get("cds_offset") is None:
        return None
    yol = GENOME_PATHS.get(assembly, "") or ""
    anahtar = (assembly, tr.strip_version(tx["acc"]), tx["chrom"], tx["tx_start"], tx["tx_end"],
               tx["cds_offset"], tx["cds_end_offset"], yol)
    if anahtar in _KOD_ONBELLEK:
        return _KOD_ONBELLEK[anahtar]
    if cdna is not None:
        cds = cdna[tx["cds_offset"]: tx["cds_end_offset"] + 1].upper()
    else:
        if not yol or not os.path.exists(yol):
            return None
        try:
            cds = _cds_yerel(tx, assembly).upper()
        except (PrimerError, OSError, ValueError):
            return None
    sonuc = _kod_hesapla(cds)
    if len(_KOD_ONBELLEK) >= _ONBELLEK_MAKS:
        _KOD_ONBELLEK.clear()
    _KOD_ONBELLEK[anahtar] = sonuc
    return sonuc


def _kodlayan_uzunluk(tx):
    if not tx.get("coding") or tx.get("cds_offset") is None:
        return 0
    return tx["cds_end_offset"] - tx["cds_offset"] + 1


def d_farki(tx):
    """GRCh37 transkripti icin (d) olcutu: ayni NM'nin GRCh38 satirina gore ekson sayisi ya da
    kodlayan uzunluk farki. Genom okunmaz (yalniz tablolar). GRCh38 satiri yoksa None."""
    try:
        t38 = tr.get_transcript(tx["acc"], RNA_DERLEME)
    except tr.TranscriptError:
        return None
    e37, e38 = tx["exon_count"], t38["exon_count"]
    c37, c38 = _kodlayan_uzunluk(tx), _kodlayan_uzunluk(t38)
    return {"ekson": [e37, e38], "cds": [c37, c38], "farkli": e37 != e38 or c37 != c38}


def kod_isareti(tx, assembly):
    """DNA ve Kirilma noktasi sekmelerindeki ekson etiketi icin: bu transkript secili derlemede
    (a)(b)(c) ile isaretli mi ya da GRCh37'de (d) farki var mi? Sonuc onbellekte."""
    yol = GENOME_PATHS.get(assembly, "") or ""
    anahtar = (assembly, tr.strip_version(tx["acc"]), yol)
    if anahtar in _ISARET_ONBELLEK:
        return _ISARET_ONBELLEK[anahtar]
    den = kod_denetimi(tx, assembly)
    sonuc = bool(den and den["isaretli"])
    if not sonuc and assembly == "GRCh37":
        d = d_farki(tx)
        sonuc = bool(d and d["farkli"])
    if len(_ISARET_ONBELLEK) >= _ONBELLEK_MAKS:
        _ISARET_ONBELLEK.clear()
    _ISARET_ONBELLEK[anahtar] = sonuc
    return sonuc


def kod_uyari_metni(tx, den, tasarim=True, onek=True):
    """Isaretli transkript icin goze carpan uyari (TR/EN). 'UYARI:' / 'WARNING:' onekiyle
    baslar: arayuz not kutusunu vurgulu cizer. tasarim=False: "Tasarim yine de yapildi" yok;
    onek=False: onek yok (Degerlendir bulgusu ve ekson dugmeleri kendi seviyesini gosterir)."""
    acc = tx.get("acc", "")
    n = den["cds_uzunluk"]
    tr_n, en_n = [], []
    if "mod3" in den["nedenler"]:
        tr_n.append(f"kodlayan uzunluk 3'ün katı değil ({tr_sayi(n)} baz)")
        en_n.append(f"the coding length is not a multiple of 3 ({n:,} bases)")
    if "son_kodon" in den["nedenler"]:
        tr_n.append(f"son kodon durdurma kodonu değil ({den['son_kodon']})")
        en_n.append(f"the last codon is not a stop codon ({den['son_kodon']})")
    if "erken_durdurma" in den["nedenler"]:
        tr_n.append(f"{den['ilk_durdurma_kodon_no']}. kodonda erken durdurma kodonu "
                    f"(toplam {den['durdurma_sayisi']})")
        en_n.append(f"a premature stop codon at codon {den['ilk_durdurma_kodon_no']} "
                    f"({den['durdurma_sayisi']} in total)")
    son_tr = " Tasarım yine de yapıldı." if tasarim else ""
    on = f"{warn_prefix()}: " if onek else ""
    son_en = " The design was made anyway." if tasarim else ""
    return t(
        f"{on}{acc} transkripti {RNA_DERLEME} genom dizisinden kurulduğunda "
        f"kodlayan bölge tutarsız görünüyor: {'; '.join(tr_n)}. Genom hizalaması NM dizisiyle "
        "birebir olmayabilir; c. ve ekson numaraları NM'ninkinden kayabilir. Gerçek bir "
        "durdurma kodonu da olabilir (ör. selenoproteinler). NM dizisiyle karşılaştırın ya da "
        f"DNA sekmesinde genomik koordinatla tasarlayın.{son_tr}",
        f"{on}when {acc} is built from the {RNA_DERLEME} genome sequence, the "
        f"coding region looks inconsistent: {'; '.join(en_n)}. The genome alignment may not "
        "match the NM sequence exactly; c. and exon numbers may differ from the NM's. It "
        "may also be a genuine stop codon (e.g. selenoproteins). Compare with the NM sequence "
        f"or design in the DNA tab with a genomic coordinate.{son_en}")


def _rna_basi_notlari(tx, secilen):
    """Sonucun en ustune konan RNA notlari: isaretli transkriptte kodlayan dizi uyarisi,
    secili derleme GRCh37 ise 'GRCh38 kullanildi' notu."""
    out = []
    den = tx.get("kod_denetimi")
    if den and den["isaretli"]:
        out.append(kod_uyari_metni(tx, den))
    dn = rna_derleme_notu(secilen)
    if dn:
        out.append(dn)
    return out


def transkript_listesi(gene, secilen):
    """GET /transcripts: gen sembolunden NM listesi. RNA yolu: her zaman GRCh38; kodlayan
    transkriptlerde dizi denetimi (yerel genom varsa) 'kod_denetimi' alaninda."""
    liste = tr.find_by_gene(gene, RNA_DERLEME)
    for x in liste:
        x["kod_denetimi"] = None
        if x["coding"]:
            try:
                x["kod_denetimi"] = kod_denetimi(tr.get_transcript(x["acc"], RNA_DERLEME), RNA_DERLEME)
            except tr.TranscriptError:
                pass
    return {"gene": gene, "transcripts": liste, "assembly": RNA_DERLEME,
            "assembly_note": rna_derleme_notu(secilen)}


def _spans_junction(tx, start_idx, end_idx):
    """[start_idx, end_idx] araligi (0-tabanli, kapsayici) bir ekson sinirini kapsiyor mu?
    Sinir ofseti j = bir sonraki eksonun ilk bazinin indeksi."""
    return any(start_idx < j <= end_idx for j in tx["junctions"])


def _junctions_within(tx, start_idx, end_idx):
    """Aralikta kalan ekson sinirlarinin listesi."""
    return [j for j in tx["junctions"] if start_idx < j <= end_idx]


def _primer_exons(tx, start_idx, end_idx):
    """Bir primerin oturdugu ekson(lar) - sinir uzerindeyse birden fazla."""
    ex = []
    for n, (a, b) in enumerate(tx["exon_cdna_spans"], start=1):
        if start_idx <= b and end_idx >= a:
            ex.append(n)
    return ex


def _cdna_pair_coords(tx, res, i, d):
    """cDNA modunda bir cifte konum alanlarini ekle: cDNA indeksi (1-tabanli gosterim),
    ekson numaralari, genomik karsilik ve gDNA urun boyu."""
    f_s, f_e, r_s, r_e = _primer_spans(res, i)

    for key, (a, b) in (("forward", (f_s, f_e)), ("reverse", (r_s, r_e))):
        d[key]["cdna_start"] = a + 1              # gosterim icin 1-tabanli
        d[key]["cdna_end"] = b + 1
        d[key]["exons"] = _primer_exons(tx, a, b)
        d[key]["spans_junction"] = _spans_junction(tx, a, b)
        # Primerin genomik ayak izi (sinir uzerindeyse iki parcali olur; uc koordinatlar)
        d[key]["genomic_start"] = tr.cdna_to_genomic(tx, a)
        d[key]["genomic_end"] = tr.cdna_to_genomic(tx, b)

    d["amplicon_cdna_start"] = f_s + 1
    d["amplicon_cdna_end"] = r_e + 1
    d["junctions_in_amplicon"] = len(_junctions_within(tx, f_s, r_e))
    d["amplicon_exons"] = sorted(set(_primer_exons(tx, f_s, r_e)))

    # gDNA'daki urun boyu: ayni primerler genomik DNA uzerinde ne verir?
    g1 = tr.cdna_to_genomic(tx, f_s)
    g2 = tr.cdna_to_genomic(tx, r_e)
    if g1 is not None and g2 is not None:
        d["gdna_product_size"] = abs(g2 - g1) + 1
        d["amplicon_genomic_start"] = min(g1, g2)
        d["amplicon_genomic_end"] = max(g1, g2)
    else:  # pragma: no cover
        d["gdna_product_size"] = None
    return d


def _collect_pairs_cdna(tx, res, order, p, template=None, hedef=None):
    """cDNA modu: yeniden siralanmis ciftleri transkript koordinatlariyla dondur."""
    pairs = []
    for rank, (i, ds, total) in enumerate(order, start=1):
        d = _amplikon_ekle(_pair_core(res, i, ds, total, rank, p), res, i, template, hedef=hedef)
        d = _cdna_pair_coords(tx, res, i, d)
        _sinir_saglamligi(tx, res, i, d, p)
        pairs.append(d)
    return pairs


def _sinir_saglamligi(tx, res, i, d, p):
    """Her primere 'junction_solid' ekler: primer bir ekson sinirini tasarim kuralindaki kadar
    asiyor mu (3' tarafta >= min_3p_overlap_junction, 5' tarafta >= min_5p_overlap_junction)?
    Yalnizca boyle bir primer genomik DNA'da uzamaz sayilir; sinira bir iki bazla degen primer
    gDNA'ya baglanabilir ('spans_junction' dogru olsa da). Arayuz "gDNA: cogalmaz" hukmunu buna
    gore verir (v1.1.2). Forward'in 3' ucu buyuk indekste, Reverse'in 3' ucu kucuk indekstedir."""
    min3 = int(p.get("min_3p_overlap_junction", 4))
    min5 = int(p.get("min_5p_overlap_junction", 7))
    f_s, f_e, r_s, r_e = _primer_spans(res, i)
    for key, a, b, ileri in (("forward", f_s, f_e, True), ("reverse", r_s, r_e, False)):
        saglam = False
        for j in tx["junctions"]:
            if a < j <= b:
                sol, sag = j - a, b - j + 1          # sinirin solunda / saginda kalan baz
                bes, uc = (sol, sag) if ileri else (sag, sol)
                if uc >= min3 and bes >= min5:
                    saglam = True
        d[key]["junction_solid"] = saglam


def _cdna_snps(tx, assembly, p):
    """Transkriptin eksonlarina denk gelen yaygin varyantlari cDNA ofsetine cevir.
    Genomik koordinat -> cDNA indeksi; eksi iplikte siralama tersine dondugu icin
    varyantin iki ucu de eslenip kucuk olan baslangic kabul edilir."""
    out = []
    for gs, ge in tx["exons"]:
        for rec in _collect_snps(assembly, tx["chrom"], gs, ge, p):
            i1 = tr.genomic_to_cdna(tx, rec["position"])
            i2 = tr.genomic_to_cdna(tx, rec["position"] + rec["span"] - 1)
            idxs = [i for i in (i1, i2) if i is not None]
            if not idxs:
                continue                      # intronik / ekson disi
            r = dict(rec)
            r["template_offset"] = min(idxs)
            r["span"] = max(idxs) - min(idxs) + 1
            out.append(r)
    out.sort(key=lambda r: r["template_offset"])
    return out


def _cdna_params(params):
    """DEFAULTS + CDNA_DEFAULTS + kullanici parametreleri."""
    return _ayar_birlestir([DEFAULTS, CDNA_DEFAULTS], params)


def _resolve_transcript(acc, assembly):
    try:
        return tr.get_transcript(acc, assembly)
    except tr.TranscriptError as e:
        raise PrimerError(str(e))


def _par_tx_notu(assembly, tx):
    """Transkript psodootozomal bolgedeyse (SHOX, CSF2RA...) aciklama notu."""
    pb = par.bolge(assembly, tx.get("chrom"), tx.get("tx_start") or 0, tx.get("tx_end") or 0)
    return [par.not_metni(pb["ad"])] if pb else []


def _surum_tx_notu(tx):
    """Istenen NM surumu MANE surumuyle uyusmuyorsa uyari; NM_ genomda birden cok yere
    hizalanmis ve MANE konumuyla secilemediyse kullanilan lokusu soyleyen not
    (transcripts.get_transcript)."""
    return [n for n in (tx.get("version_warning"), tx.get("locus_note")) if n]


def _paralog_tx_notu(tx):
    """Transkriptin geninin yakin-ozdes kopyasi varsa (SMN1/SMN2 gibi) uyari.
    cDNA sablonunda intron yok, bu yuzden ekzon benzerligi esas alinir."""
    gen = (tx.get("gene") or "").strip().upper()
    n = paralog.not_metni(gen, paralog.gen_paraloglari(gen), mod="cdna")
    return [n] if n else []


def design_primers_cdna(assembly, acc, c_pos, params=None):
    """
    RNA modu: NM_ kodu + c. koordinatindan cDNA uzerinde primer tasarla.
    Sablon TAMAMEN cDNA'dir (intron yok), boylece primer3 tum ekson sinirlarini gorur.
    """
    if assembly not in ("GRCh37", "GRCh38"):
        raise PrimerError(t("assembly 'GRCh37' veya 'GRCh38' olmalı.",
                            "assembly must be 'GRCh37' or 'GRCh38'."))
    p = _cdna_params(params)

    secilen = assembly
    assembly = rna_derleme(secilen)       # RNA yolu: her zaman GRCh38 (K1)
    tx = _resolve_transcript(acc, assembly)
    cdna, source = build_cdna(tx, assembly)
    tx["kod_denetimi"] = kod_denetimi(tx, assembly, cdna)

    try:
        v_index, v_son, c_label = tr.parse_c_range(tx, c_pos)
    except tr.TranscriptError as e:
        raise PrimerError(str(e))

    # Hedef = varyantin TAMAMI + iki yanda pay (DNA modundaki varyant araligiyla ayni)
    excl = int(p["min_dist_from_variant"])
    # Transkript ucuna cok yakin varyant: bir yanda primer koyacak yer yok (DNA
    # modundaki kromozom ucu kontroluyle ayni). Eskiden primer3 bos donuyor, sebep
    # "urun boyu" gorunuyordu (olculdu: NM_000546 c.-100 ve c.*1150, 2026-10-28).
    gerek = excl + int(p["primer_min_size"])
    sol, sag = v_index, len(cdna) - 1 - v_son
    if sol < gerek or sag < gerek:
        yer_tr, yer_en = ("5' ucuna", "5' end") if sol < gerek else ("3' ucuna", "3' end")
        raise PrimerError(t(
            f"Varyant transkriptin {yer_tr} çok yakın ({c_label}; cDNA {tr_sayi(v_index + 1)} / "
            f"{tr_sayi(len(cdna))} nt). Varyanta en az {excl} nt uzaklıkta en az "
            f"{int(p['primer_min_size'])} nt'lik bir primer koymak için iki yanda da {gerek} nt "
            f"cDNA gerekir; bu yanda yalnızca {min(sol, sag)} nt var. Varyanta min uzaklığı "
            "küçültün ya da varyantı DNA modunda (genomik koordinatla) tasarlayın.",
            f"The variant is too close to the transcript's {yer_en} ({c_label}; cDNA "
            f"{v_index + 1:,} / {len(cdna):,} nt). Placing a primer of at least "
            f"{int(p['primer_min_size'])} nt at least {excl} nt from the variant needs {gerek} nt "
            f"of cDNA on both sides; this side has only {min(sol, sag)} nt. Reduce the minimum "
            "distance to the variant or design it in DNA mode (genomic coordinate)."))
    tgt_start = max(0, v_index - excl)
    tgt_len = min(len(cdna) - 1, v_son + excl) - tgt_start + 1
    _ust = int(p["product_size_max"])
    if p.get("pcr_max") is not None:
        _ust = min(_ust, int(p["pcr_max"]))
    _gerekli = tgt_len + 2 * int(p["primer_min_size"])
    if _gerekli > _ust:
        raise PrimerError(t(
            f"Varyant aralığı {tr_sayi(v_son - v_index + 1)} nt; iki yanda {excl} nt pay ve primerlerle "
            f"birlikte ürün en az {tr_sayi(_gerekli)} bp olur, geçerli üst sınır ise {tr_sayi(_ust)} bp. "
            "Payı ya da ürün sınırını değiştirin; ekzonun tamamı etkileniyorsa Ekson atlama "
            "testi daha uygun olabilir.",
            f"The variant range is {v_son - v_index + 1:,} nt; with {excl} nt on each side plus "
            f"the primers the product would be at least {_gerekli:,} bp, while the effective "
            f"maximum is {_ust:,} bp. Change the margin or the product limit; if a whole exon "
            "is affected, the exon skipping assay may suit better."))

    snps = _cdna_snps(tx, assembly, p)
    excluded = (_excluded_from_snps(snps, len(cdna))
                if p.get("avoid_common_snps", True) else [])

    seq_args = {
        "SEQUENCE_ID": f"{tx['acc']}_{c_label}",
        "SEQUENCE_TEMPLATE": cdna,
        "SEQUENCE_TARGET": [tgt_start, tgt_len],
    }
    dahil = _dahil_bolge(len(cdna), [tgt_start, tgt_len], p)
    if dahil:
        seq_args["SEQUENCE_INCLUDED_REGION"] = dahil
    if excluded:
        seq_args["SEQUENCE_EXCLUDED_REGION"] = excluded
    global_args = _build_global_args(p)

    # (a) modu: primerlerden biri ekson sinirinin UZERINE otursun.
    # primer3 sinirlari "sinirdan onceki son bazin indeksi" olarak bekler.
    junction_overlap = bool(p.get("junction_overlap"))
    if junction_overlap:
        if not tx["junctions"]:
            raise PrimerError(t(
                f"{tx['acc']} tek eksonlu; ekson sınırı üzerine primer tasarlanamaz.",
                f"{tx['acc']} has a single exon; no primer can be placed on an "
                "exon junction."))
        seq_args["SEQUENCE_OVERLAP_JUNCTION_LIST"] = [j - 1 for j in tx["junctions"]]
        global_args["PRIMER_MIN_3_PRIME_OVERLAP_OF_JUNCTION"] = \
            int(p["min_3p_overlap_junction"])
        global_args["PRIMER_MIN_5_PRIME_OVERLAP_OF_JUNCTION"] = \
            int(p["min_5p_overlap_junction"])

    res = primer3.bindings.design_primers(seq_args, global_args)

    notes = _surum_tx_notu(tx) + _par_tx_notu(assembly, tx) + _paralog_tx_notu(tx)
    notes = _rna_basi_notlari(tx, secilen) + notes
    ref_uyari = tr.c_referans_uyarisi(tx, c_pos, cdna)      # A2-01
    if ref_uyari:
        notes.insert(1 if (tx.get("kod_denetimi") or {}).get("isaretli") else 0,
                     f"{warn_prefix()}: {ref_uyari}")
    if v_son > v_index:
        notes.append(t(
            f"Varyant {tr_sayi(v_son - v_index + 1)} nt olarak alındı ({c_label}; cDNA "
            f"{tr_sayi(v_index + 1)}-{tr_sayi(v_son + 1)}); primerler bu aralığın tamamının ve iki yanda "
            f"{excl} nt'lik payın dışına kondu. Böylece hiçbir primer varyantın içine düşmez.",
            f"The variant was taken as {v_son - v_index + 1:,} nt ({c_label}; cDNA "
            f"{v_index + 1:,}-{v_son + 1:,}); the primers were placed outside the whole range "
            f"plus {excl} nt on each side, so no primer can fall inside the variant."))
    sinir_notu = _pcr_sinir_notu(p)
    if sinir_notu:
        notes.append(sinir_notu)
    if excluded and int(res.get("PRIMER_PAIR_NUM_RETURNED", 0)) == 0:
        seq_args.pop("SEQUENCE_EXCLUDED_REGION")
        res = primer3.bindings.design_primers(seq_args, global_args)
        # Kisit kaldirildiginda da cift cikmadiysa "varyantlar isaretlendi" demek yanlis
        if int(res.get("PRIMER_PAIR_NUM_RETURNED", 0)):
            notes.append(t(
                f"UYARI: Bölge yaygın varyant açısından yoğun ({len(excluded)} varyant); "
                "hepsinden kaçınılınca uygun primer kalmadı. Kısıt kaldırıldı - primer "
                "üzerindeki varyantlar işaretlendi.",
                f"WARNING: This region is dense in common variants ({len(excluded)}); "
                "avoiding all of them left no usable primer. The constraint was lifted - "
                "variants falling on the primers are flagged."))

    sira = _rank_order(res, p, template=cdna)
    order = sira
    notes.extend(_suzgec_notlari(sira, p, order))

    # (b) modu: urun en az bir ekson sinirini kapsasin (gDNA'da intron kadar uzar).
    # Hic aday yoksa "hicbir cift sinir kapsamiyor" uyarisi yanlis olur.
    if bool(p.get("junction_flanking")) and not junction_overlap and order:
        kept = []
        for item in order:
            f_s, _f_e, _r_s, r_e = _primer_spans(res, item[0])
            if _spans_junction(tx, f_s, r_e):
                kept.append(item)
        if kept:
            if len(kept) < len(order):
                notes.append(t(
                    f"{len(order) - len(kept)} çift ekson sınırı kapsamadığı için elendi "
                    "(gDNA'dan ayırt edilemezdi).",
                    f"{len(order) - len(kept)} pairs were discarded because they span no "
                    "exon junction (they could not be told apart from gDNA)."))
            order = kept
        else:
            notes.append(t(
                "UYARI: Hiçbir çift ekson sınırını kapsamıyor - hepsi tek eksonun içinde "
                "kalıyor. Bu primerler gDNA kontaminasyonundan AYIRT EDİLEMEZ. "
                "Amplikon boyunu büyütmeyi deneyin.",
                "WARNING: No pair spans an exon junction - all of them stay inside a "
                "single exon. These primers CANNOT be distinguished from gDNA "
                "contamination. Try increasing the amplicon size."))

    order = order[:int(p["num_return"])]
    pairs = _collect_pairs_cdna(tx, res, order, p, template=cdna, hedef=(v_index, v_son))
    _annotate_pair_snps(pairs, res, order, snps)

    # (a) modunda gercekten sinir uzerine oturmus mu? (sessiz basarisizlik olmasin)
    if junction_overlap:
        for pr in pairs:
            if not (pr["forward"]["spans_junction"] or pr["reverse"]["spans_junction"]):
                notes.append(t(
                    f"Çift {pr['rank']}: primer3 sınır üstü primer döndürmedi; "
                    "bu çift gDNA'ya da bağlanabilir.",
                    f"Pair {pr['rank']}: primer3 did not return a junction-spanning "
                    "primer; this pair can also bind gDNA."))

    return {
        "mode": "cdna",
        "input": {
            "assembly": assembly,
            "assembly_requested": secilen,
            "acc": acc,
            "c_position": str(c_pos),
            "c_label": c_label,
        },
        "transcript": tr.transcript_summary(tx),
        "sequence_source": source,
        "variant_cdna_index": v_index + 1,
        "variant_cdna_end": v_son + 1,
        "variant_length": v_son - v_index + 1,
        "variant_exon": tr.exon_number_of(tx, v_index),
        "variant_genomic": tr.cdna_to_genomic(tx, v_index),
        "junction_mode": "overlap" if junction_overlap else
                         ("flanking" if p.get("junction_flanking") else "off"),
        "params_used": p,
        "num_returned": len(pairs),
        "pairs": pairs,
        "notes": notes,
        "dbsnp": {
            "available": dbsnp.get_index(assembly) is not None,
            "in_template": len(snps),
            "excluded": len(excluded),
            "applied": bool(excluded) and "SEQUENCE_EXCLUDED_REGION" in seq_args,
        },
        "explain": {
            "left": res.get("PRIMER_LEFT_EXPLAIN", ""),
            "right": res.get("PRIMER_RIGHT_EXPLAIN", ""),
            "pair": res.get("PRIMER_PAIR_EXPLAIN", ""),
        },
    }


SKIP_MAX_RANGE = 10_000     # "1-99999999" gibi aralik yazimi bellegi sisirmesin


def parse_exon_list(exons):
    """Ekson secimi -> siralanmis, tekrarsiz tam sayi listesi. Tek yerde ayristirilir.
    Kabul: 5 | [4, 6] | "4-6" | "4,6" | "45–47" | "4-6, 9" (tire/en tire, virgul/bosluk/noktalivirgul)."""
    ham = []
    if isinstance(exons, bool):
        raise PrimerError(t("Ekson numarası geçersiz.", "The exon number is not valid."))
    if isinstance(exons, int):
        ham = [exons]
    elif isinstance(exons, (list, tuple)):
        for x in exons:
            if isinstance(x, bool) or not isinstance(x, (int, str)):
                raise PrimerError(t("Ekson listesinde yalnız tam sayılar olabilir.",
                                    "The exon list may contain whole numbers only."))
            ham.extend(parse_exon_list(x))
    elif isinstance(exons, str):
        s = exons.strip().replace("–", "-").replace("—", "-").replace("−", "-")
        if not s:
            raise PrimerError(t("Ekson numarası gerekli.", "An exon number is required."))
        for parca in re.split(r"[,;\s]+", s):
            if not parca:
                continue
            m = re.fullmatch(r"(\d{1,6})(?:-(\d{1,6}))?", parca)
            if not m:
                raise PrimerError(t(
                    f"'{parca}' ekson biçimi anlaşılmadı. Örnek: 5, 4-6 ya da 4,6.",
                    f"The exon format '{parca}' was not understood. Examples: 5, 4-6 or 4,6."))
            a = int(m.group(1))
            b = int(m.group(2)) if m.group(2) else a
            if b < a:
                raise PrimerError(t(
                    f"'{parca}' aralığı ters: küçük numara önce yazılmalı (örn. {b}-{a}).",
                    f"The range '{parca}' is reversed: write the smaller number first "
                    f"(e.g. {b}-{a})."))
            if b - a + 1 > SKIP_MAX_RANGE:
                raise PrimerError(t(f"'{parca}' aralığı çok geniş.", f"The range '{parca}' is too wide."))
            ham.extend(range(a, b + 1))
    else:
        raise PrimerError(t("Ekson numarası geçersiz.", "The exon number is not valid."))
    if not ham:
        raise PrimerError(t("Ekson numarası gerekli.", "An exon number is required."))
    return sorted(set(ham))


def exon_coding_lengths(tx):
    """Her eksonun CDS ile ortusen baz sayisi (kodlamayan transkriptte hepsi 0).
    cds_offset / cds_end_offset: transcripts.py, c.1 ve stop kodonun son bazinin cDNA indeksi."""
    c0, c1 = tx.get("cds_offset"), tx.get("cds_end_offset")
    out = []
    for s, e in tx["exon_cdna_spans"]:
        out.append(max(0, min(e, c1) - max(s, c0) + 1) if c0 is not None and c1 is not None else 0)
    return out


def transcript_exons(assembly, acc):
    """GET /transcript_exons: genom okumadan ekson uzunluklari (cDNA) ve kodlayan baz sayilari."""
    if assembly not in ("GRCh37", "GRCh38"):
        raise PrimerError(t("assembly 'GRCh37' veya 'GRCh38' olmalı.",
                            "assembly must be 'GRCh37' or 'GRCh38'."))
    secilen = assembly
    assembly = rna_derleme(secilen)       # RNA yolu: her zaman GRCh38 (K1)
    tx = _resolve_transcript(acc, assembly)
    kod = exon_coding_lengths(tx)
    den = kod_denetimi(tx, assembly)       # yerel genom varsa; yoksa None (internete cikmaz)
    return {"acc": tx["acc"], "gene": tx.get("gene"), "exon_count": tx["exon_count"],
            "exons": [{"no": i, "len": e - s + 1, "coding": kod[i - 1]}
                      for i, (s, e) in enumerate(tx["exon_cdna_spans"], 1)],
            "assembly": assembly, "assembly_note": rna_derleme_notu(secilen),
            "kod_denetimi": den,
            "kod_uyari": kod_uyari_metni(tx, den, tasarim=False, onek=False) if den and den["isaretli"] else None}


def _etiket(sel):
    """[4, 5, 6] -> '4-6'; [4, 6] -> '4,6'; [5] -> '5'; karisik: '2-3,6'."""
    parcalar, i = [], 0
    while i < len(sel):
        j = i
        while j + 1 < len(sel) and sel[j + 1] == sel[j] + 1:
            j += 1
        parcalar.append(str(sel[i]) if i == j else f"{sel[i]}-{sel[j]}")
        i = j + 1
    return ",".join(parcalar)


def design_exon_skipping(assembly, acc, exon_no, params=None):
    """
    Ekson atlama (exon skipping) testi:
    Secilen ekson(lar)in ONCESINDEKI ve SONRASINDAKI eksonlara primer koyar.
      - normal transkript -> uzun urun
      - ekson atlanmis transkript -> kisa urun (fark = atlanan uzunluk)
    exon_no: tek sayi, liste ya da "4-6" / "4,6" metni (parse_exon_list). Bitisik olmayan
    secimde hedef blok en kucuk eksonun basindan en buyugunun sonuna kadardir; aradaki
    eksonlar da blokta kalir (primerler blogun disindaki komsu eksonlara oturur).
    Primerler hedef eksona komsu SINIRLARIN uzerine oturamaz; otursaydi atlanmis
    transkripte baglanamaz ve testin kanitlamak istedigi bant hic gorunmezdi.
    params["junction_overlap"] (varsayilan kapali): primerlerden biri hedef blogun
    DISINDAKI bir ekson sinirinin uzerine oturur (gDNA'ya baglanmaz); normal ve atlanmis
    transkriptin ikisi de o siniri tasidigi icin iki bant yine birlikte gorulur.
    """
    if assembly not in ("GRCh37", "GRCh38"):
        raise PrimerError(t("assembly 'GRCh37' veya 'GRCh38' olmalı.",
                            "assembly must be 'GRCh37' or 'GRCh38'."))
    p = _cdna_params(params)
    sel = parse_exon_list(exon_no)

    secilen = assembly
    assembly = rna_derleme(secilen)       # RNA yolu: her zaman GRCh38 (K1)
    tx = _resolve_transcript(acc, assembly)
    n_ex = tx["exon_count"]
    yok = [x for x in sel if x < 1 or x > n_ex]
    if yok:
        yok_s = ", ".join(map(str, yok))
        raise PrimerError(t(f"{tx['acc']} {n_ex} eksonlu; ekson {yok_s} yok.",
                            f"{tx['acc']} has {n_ex} exons; there is no exon {yok_s}."))
    if n_ex < 3:
        raise PrimerError(t(
            f"{tx['acc']} sadece {n_ex} eksonlu; atlama testi için en az 3 ekson gerekir.",
            f"{tx['acc']} has only {n_ex} exons; a skipping assay needs at least 3."))
    for x in sel:
        if x == 1 or x == n_ex:
            raise PrimerError(t(
                f"Ekson {x} transkriptin {'ilk' if x == 1 else 'son'} eksonu; "
                "bir tarafında çapa eksonu olmadığı için atlama testi tasarlanamaz.",
                f"Exon {x} is the {'first' if x == 1 else 'last'} exon of the "
                "transcript; with no anchor exon on one side, a skipping assay cannot be "
                "designed."))
    blk_a, blk_b = sel[0], sel[-1]
    bitisik = len(sel) == blk_b - blk_a + 1
    exon_no = blk_a                      # eski alan: tek eksonda aynen o ekson
    etiket = _etiket(sel)
    blok_ad = f"{blk_a}" if blk_a == blk_b else f"{blk_a}–{blk_b}"

    cdna, source = build_cdna(tx, assembly)
    tx["kod_denetimi"] = kod_denetimi(tx, assembly, cdna)
    spans = tx["exon_cdna_spans"]
    ex_start, ex_end = spans[blk_a - 1][0], spans[blk_b - 1][1]
    exon_len = ex_end - ex_start + 1     # hedef BLOK uzunlugu
    sec_len = sum(spans[x - 1][1] - spans[x - 1][0] + 1 for x in sel)
    atlanan_len = exon_len if bitisik else sec_len   # atlanan toplam bp
    kod = exon_coding_lengths(tx)
    coding_tx = tx.get("cds_offset") is not None

    def _cerceve(grup):
        return (sum(kod[x - 1] for x in grup) % 3 == 0) if coding_tx else None

    margin = int(p["skip_margin"])
    # Hedef ekson + guvenlik payi: primer buraya HIC giremez (sinir ustune oturmasin)
    excl_start = max(0, ex_start - margin)
    excl_end = min(len(cdna) - 1, ex_end + margin)

    # Hedef ekson kisiti testin kendisi icin ZORUNLU; SNP kisiti ise iyilestirme.
    # Ikisi ayri tutulur ki daralma halinde sadece SNP kismindan vazgecilsin.
    exon_excl = [[excl_start, excl_end - excl_start + 1]]
    snps = _cdna_snps(tx, assembly, p)
    snp_excl = (_excluded_from_snps(snps, len(cdna), limit=PRIMER3_BOLGE_MAKS - 1)
                if p.get("avoid_common_snps", True) else [])

    # Urun hedef eksonu kapsamak ZORUNDA
    seq_args = {
        "SEQUENCE_ID": f"{tx['acc']}_skip_exon{etiket.replace(',', '_')}",
        "SEQUENCE_TEMPLATE": cdna,
        "SEQUENCE_TARGET": [ex_start, exon_len],
        "SEQUENCE_EXCLUDED_REGION": exon_excl + snp_excl,
    }

    # Amplikon araligi eksona gore otomatik ayarlanir: kucuk eksonda urunu kisa tut ki
    # iki bant (normal / atlanmis) jelde ayirt edilebilsin.
    p = dict(p)
    p["product_size_min"] = exon_len + 2 * int(p["skip_min_flank"])
    p["product_size_max"] = exon_len + 2 * int(p["skip_max_flank"])
    # Normal transkript urunu eksonun tamamini kapsamak zorunda: ekson uzunsa urun
    # laboratuvarin cogaltabildigi boyu asar. Genel "alt sinir > en uzun urun"
    # hatasi burada anlasilmaz olurdu (kullanici urun boyu girmedi).
    if p["product_size_min"] > int(p["pcr_max"]):
        raise PrimerError(t(
            f"Ekson {blok_ad} {'' if blk_a == blk_b else 'toplam '}{tr_sayi(exon_len)} bp: atlama testinde normal transkriptin ürünü en az "
            f"{tr_sayi(p['product_size_min'])} bp olur, çoğaltılabilen en uzun ürün ise "
            f"{tr_sayi(int(p['pcr_max']))} bp. Gelişmiş parametrelerden bu sınırı yükseltmeden bu "
            "eksonun atlanması bu yöntemle gösterilemez.",
            f"Exon {blok_ad} is {'' if blk_a == blk_b else 'in total '}{exon_len:,} bp: in the skipping test the normal transcript's "
            f"product is at least {p['product_size_min']:,} bp, while the longest amplifiable "
            f"product is {int(p['pcr_max']):,} bp. Without raising this limit under advanced "
            "parameters, skipping of this exon cannot be shown with this method."))
    dahil = _dahil_bolge(len(cdna), [ex_start, exon_len], p)
    if dahil:
        seq_args["SEQUENCE_INCLUDED_REGION"] = dahil
    global_args = _build_global_args(p)
    # Iki bandin AYRILABILIRLIGI urun uzunluguna baglidir: fark sabit (= ekson boyu),
    # dolayisiyla urun ne kadar kisaysa oransal fark o kadar buyuk. Bu yuzden bu modda
    # kisa amplikon aktif olarak odullendirilir (DNA modundaki hafif tercihten farkli).
    global_args["PRIMER_PRODUCT_OPT_SIZE"] = int(p["product_size_min"])
    global_args["PRIMER_PAIR_WT_PRODUCT_SIZE_GT"] = float(p["skip_wt_long_product"])

    # Sinir ustu primer (Varyant modundaki ayarin aynisi, ayni primer3 mekanizmasi):
    # primerlerden biri bir ekson sinirinin UZERINE oturur, gDNA'ya baglanmaz. Atlama
    # testinde yalnizca hedef blogun DISINDAKI sinirlar kullanilabilir: bloga komsu iki
    # sinir ve blogun icindekiler atlanmis transkriptte yoktur; primer oraya otursa iki
    # banttan biri hic gorunmez. Komsu sinirlar zaten dislanan bolgeye duser (exon_excl);
    # liste yine de acikca daraltilir. Sinir ofseti j = sonraki eksonun ilk bazinin indeksi.
    junction_overlap = bool(p.get("junction_overlap"))
    if junction_overlap:
        dis_sinirlar = [j for j in tx["junctions"] if j < ex_start or j > ex_end + 1]
        if not dis_sinirlar:
            raise PrimerError(t(
                f"{tx['acc']}: seçilen eksonların dışında ekson sınırı yok (primerlerin "
                f"oturduğu ekson {blk_a - 1} ve {blk_b + 1} transkriptin ilk ve son eksonu). "
                "Bu testte primer ekson sınırının üzerine oturtulamaz; seçeneği kapatıp "
                "yeniden deneyin.",
                f"{tx['acc']}: there is no exon junction outside the selected exons (the "
                f"anchor exons {blk_a - 1} and {blk_b + 1} are the first and last exons of "
                "the transcript). No primer can be placed across an exon junction in this "
                "assay; turn the option off and try again."))
        seq_args["SEQUENCE_OVERLAP_JUNCTION_LIST"] = [j - 1 for j in dis_sinirlar]
        global_args["PRIMER_MIN_3_PRIME_OVERLAP_OF_JUNCTION"] = \
            int(p["min_3p_overlap_junction"])
        global_args["PRIMER_MIN_5_PRIME_OVERLAP_OF_JUNCTION"] = \
            int(p["min_5p_overlap_junction"])

    res = primer3.bindings.design_primers(seq_args, global_args)

    snp_notes = []
    if snp_excl and int(res.get("PRIMER_PAIR_NUM_RETURNED", 0)) == 0:
        # Hedef ekson kisiti korunur, sadece SNP kisiti geri alinir
        seq_args["SEQUENCE_EXCLUDED_REGION"] = exon_excl
        res = primer3.bindings.design_primers(seq_args, global_args)
        # Kisit kaldirildiginda da cift cikmadiysa "varyantlar isaretlendi" demek yanlis
        if int(res.get("PRIMER_PAIR_NUM_RETURNED", 0)):
            snp_notes.append(t(
                f"UYARI: Çapa eksonları yaygın varyant açısından yoğun ({len(snp_excl)} "
                "varyant); hepsinden kaçınılınca uygun primer kalmadı. SNP kısıtı "
                "kaldırıldı - primer üzerindeki varyantlar işaretlendi.",
                f"WARNING: The anchor exons are dense in common variants ({len(snp_excl)}); "
                "avoiding all of them left no usable primer. The SNP constraint was lifted - "
                "variants falling on the primers are flagged."))

    sira = _rank_order(res, p, template=cdna)
    order = sira[:int(p["num_return"])]
    pairs = _collect_pairs_cdna(tx, res, order, p, template=cdna)
    _annotate_pair_snps(pairs, res, order, snps)

    warn_bp = float(p["skip_resolution_warn"])
    ratio_warn = float(p["skip_ratio_warn"])
    # Bitisik olmayan secimde beklenen bantlar: her tekli secim + hepsi birden (fark, okuma cercevesi)
    skip_bands = []
    if not bitisik:
        for grup in [[x] for x in sel] + [sel]:
            skip_bands.append({"exons": grup,
                               "diff": sum(spans[x - 1][1] - spans[x - 1][0] + 1 for x in grup),
                               "frame": _cerceve(grup)})
    # BANT UYARISI ESIGI (tasarim secimi, olculmus bir sinir degil): iki beklenen bant (normal
    # dahil) arasindaki fark max(20 bp, buyuk bandin %5'i)'nden kucukse jelde ayrimi zor olabilir.
    BAND_YAKIN_BP, BAND_YAKIN_ORAN = 20, 0.05
    band_close_any = False
    for pr in pairs:
        normal = pr["product_size"]
        skipped = normal - atlanan_len
        pr["product_size_normal"] = normal
        pr["product_size_skipped"] = skipped
        pr["band_difference"] = atlanan_len
        pr["band_ratio"] = round(skipped / normal, 3) if normal else None
        # Ayrilabilirlik: hem mutlak fark hem de bantlarin birbirine oranı onemli
        pr["low_resolution"] = (atlanan_len < warn_bp) or (skipped / normal > ratio_warn
                                                           if normal else False)
        if skip_bands:
            pr["bands"] = [{"exons": b["exons"], "size": normal - b["diff"], "diff": b["diff"],
                            "frame": b["frame"]} for b in skip_bands]
            boylar = sorted([normal] + [b["size"] for b in pr["bands"]], reverse=True)
            yakin = [(boylar[i], boylar[i + 1]) for i in range(len(boylar) - 1)
                     if boylar[i] - boylar[i + 1] < max(BAND_YAKIN_BP, BAND_YAKIN_ORAN * boylar[i])]
            pr["band_close"] = [list(c) for c in yakin]
            if yakin:
                pr["low_resolution"] = True
                band_close_any = True

    notes = (_rna_basi_notlari(tx, secilen) + _surum_tx_notu(tx) + list(snp_notes)
             + _par_tx_notu(assembly, tx) + _paralog_tx_notu(tx))
    notes.extend(_suzgec_notlari(sira, p, pairs))
    if atlanan_len < warn_bp:
        if len(sel) == 1:
            notes.append(t(
                f"Ekson {exon_no} sadece {exon_len} bp. İki bant arasındaki fark da {exon_len} bp "
                "olacağı için standart agaroz jelde ayırt etmek zor olabilir; "
                "kapiler elektroforez veya yüksek yüzdeli jel düşünün.",
                f"Exon {exon_no} is only {exon_len} bp, so the two bands will differ by just "
                f"{exon_len} bp - hard to resolve on a standard agarose gel. Consider "
                "capillary electrophoresis or a higher-percentage gel."))
        else:
            notes.append(t(
                f"Seçilen eksonlar toplam {atlanan_len} bp. Normal ve tümü atlanmış bant arasındaki "
                f"fark da {atlanan_len} bp olacağı için standart agaroz jelde ayırt etmek zor "
                "olabilir; kapiler elektroforez veya yüksek yüzdeli jel düşünün.",
                f"The selected exons total {atlanan_len} bp, so the normal and fully skipped "
                f"bands differ by just {atlanan_len} bp - hard to resolve on a standard agarose "
                "gel. Consider capillary electrophoresis or a higher-percentage gel."))
    if band_close_any:
        notes.append(t(
            "Bazı beklenen bantlar birbirine çok yakın (fark, 20 bp'nin ya da büyük bandın "
            "%5'inin altında); jelde ayırt etmek zor olabilir. Ayrıntı: ürün satırlarında "
            "işaretli bant çiftleri.",
            "Some expected bands are very close (differ by less than 20 bp or 5% of the larger "
            "band); they may be hard to tell apart on a gel. Details: the flagged band pairs "
            "in each product row."))
    if junction_overlap:
        # Gercekten sinir uzerine oturmus mu? (sessiz basarisizlik olmasin; design_cdna ile ayni)
        for pr in pairs:
            if not (pr["forward"]["spans_junction"] or pr["reverse"]["spans_junction"]):
                notes.append(t(
                    f"Çift {pr['rank']}: primer3 sınır üstü primer döndürmedi; "
                    "bu çift gDNA'ya da bağlanabilir.",
                    f"Pair {pr['rank']}: primer3 did not return a junction-spanning "
                    "primer; this pair can also bind gDNA."))
    if not pairs and junction_overlap:
        notes.append(t(
            "Ekson sınırının üzerine oturan primerle uygun çift bulunamadı: seçilen "
            "eksonların dışındaki sınırlar ürün boyu sınırının dışında kalıyor ya da oraya "
            "uygun primer sığmıyor. 'Primer ekson sınırının üzerine otursun' seçeneğini "
            "kapatıp yeniden deneyin; o durumda kartta gDNA ürününün boyu gösterilir.",
            "No suitable pair was found with a primer placed across an exon junction: the "
            "junctions outside the selected exons lie beyond the product size limit, or no "
            "acceptable primer fits there. Turn off 'Place one primer across an exon "
            "junction' and try again; the card then shows the size of the gDNA product."))
    elif not pairs:
        notes.append(t(
            "Uygun çift bulunamadı. Komşu eksonlar primer sığdırmak için çok kısa olabilir; "
            "'skip_max_flank' değerini artırarak daha uzak eksonlara çapa atmayı deneyin.",
            "No suitable pair was found. The neighbouring exons may be too short to hold a "
            "primer; try raising 'skip_max_flank' to anchor in exons further out."))

    return {
        "mode": "exon_skipping",
        "input": {"assembly": assembly, "assembly_requested": secilen, "acc": acc,
                  "exon": exon_no, "exons": etiket},
        "transcript": tr.transcript_summary(tx),
        "sequence_source": source,
        "target_exon": {
            "number": exon_no,
            "length": exon_len,
            "cdna_start": ex_start + 1,
            "cdna_end": ex_end + 1,
            "genomic_start": min(e[0] for e in tx["exons_tx"][blk_a - 1:blk_b]),
            "genomic_end": max(e[1] for e in tx["exons_tx"][blk_a - 1:blk_b]),
        },
        "skip_exons": sel,
        "skip_block": [blk_a, blk_b],
        "skip_len": atlanan_len,
        "skip_frame": _cerceve(sel),
        "skip_utr": (any(kod[x - 1] < spans[x - 1][1] - spans[x - 1][0] + 1 for x in sel)
                     if coding_tx else None),
        "skip_bands": skip_bands,
        "anchor_exons": [blk_a - 1, blk_b + 1],
        # "overlap": primerlerden biri blogun disindaki bir ekson sinirinin uzerinde;
        # "flanking": primerler blogun iki yanindaki eksonlarda (bu modda urun her zaman sinir kapsar)
        "junction_mode": "overlap" if junction_overlap else "flanking",
        "params_used": p,
        "num_returned": len(pairs),
        "pairs": pairs,
        "notes": notes,
        "dbsnp": {
            "available": dbsnp.get_index(assembly) is not None,
            "in_template": len(snps),
            "excluded": len(snp_excl),
            "applied": bool(snp_excl) and len(seq_args["SEQUENCE_EXCLUDED_REGION"]) > 1,
        },
        "explain": {
            "left": res.get("PRIMER_LEFT_EXPLAIN", ""),
            "right": res.get("PRIMER_RIGHT_EXPLAIN", ""),
            "pair": res.get("PRIMER_PAIR_EXPLAIN", ""),
        },
    }


# ------------------------------------------------------------------
# Serbest dizi modu (genom/transkript gerektirmez)
# ------------------------------------------------------------------
SEQ_DEFAULTS = {
    # Iki dizi arasindaki BILINEN mesafe (bp). 0 = diziler bitisik kabul edilir
    # (fuzyon transkripti, delesyon kirilma noktasi). Bosluk N ile doldurulur,
    # primer3 N'li bolgeye primer koymaz (PRIMER_MAX_NS_ACCEPTED=0).
    "gap": 0,
    "max_gap": 20000,
    # Iki dizi arasindaki mesafe bilinmiyorsa urun boyu kisitinin anlami kalmaz.
    # Acikken kisit acilir: primerler dizilerin HER YERINDEN, yalnizca kaliteye
    # gore secilir. (Kapaliyken 180-650 varsayilani F'yi 1. dizinin sonuna,
    # R'yi 2. dizinin basina dogru cekiyor ve uclari kullanilamaz kiliyor.)
    "ignore_product_size": False,
}

# IUPAC belirsizlik kodlari: N'e cevrilir, primer oraya oturmaz
_IUPAC = "RYKMSWBDHV"
_BRACKET = re.compile(r"\[([^\]]*)\]")


def _apply_brackets(seq):
    """'ACGT[A/G]TTT' -> ('ACGTATTT', (4, 1)). Hedef, kose parantezle isaretlenir;
    ilk allel diziye yazilir, parantez araligi hedef bolge olur."""
    m = _BRACKET.search(seq)
    if not m:
        return seq, None, 0
    alleles = [a.strip() for a in m.group(1).split("/") if a.strip()]
    first = alleles[0] if alleles else ""
    if first == "-":                       # delesyon gosterimi
        first = ""
    new = seq[:m.start()] + first + seq[m.end():]
    target = (m.start(), max(1, len(first)))
    extra = len(_BRACKET.findall(new))     # kalan parantez sayisi
    return new, target, extra


def parse_sequence_input(text, allow_brackets=True, kutu=None):
    """Yapistirilan diziyi temizle. FASTA basligi, bosluk, konum numaralari atilir.
    Dizi icerigi olan BIRDEN COK FASTA kaydi varsa reddedilir: kayitlar eskiden sessizce
    tek diziye birlestiriliyor, birlesme noktasini kapsayan gercekte olmayan urunler
    cikiyordu. Icerigi olmayan baslik kayit sayilmaz. kutu: (tr, en) kutu adi (iki dizi modu).
    Doner: (dizi, hedef|None, notlar)."""
    if text:
        # Dosyadan kopyalanan metnin basindaki BOM (U+FEFF) bosluk sayilmaz: ">" satirinin
        # onune gecip basligi "gecersiz karakter" yapiyordu (D3-05)
        text = str(text).lstrip("﻿")
    if not text or not str(text).strip():
        raise PrimerError(t("Dizi boş.", "The sequence is empty."))
    notes = []
    kept = []
    kayit, kayit_dolu = 0, False
    for line in str(text).splitlines():
        if line.strip().startswith(">"):
            notes.append(t(f"FASTA başlığı yok sayıldı: {line.strip()[:60]}",
                           f"FASTA header ignored: {line.strip()[:60]}"))
            kayit += kayit_dolu
            kayit_dolu = False
            continue
        if re.sub(r"[\s0-9]", "", line):
            kayit_dolu = True
        kept.append(line)
    kayit += kayit_dolu
    if kayit > 1:
        tr_kutu = f"{kutu[0]} kutusunda " if kutu else "Dizi kutusunda "
        en_kutu = f"The {kutu[1]} box contains " if kutu else "The sequence box contains "
        raise PrimerError(t(
            f"{tr_kutu}{kayit} FASTA kaydı var. Kayıtlar tek diziye birleştirilirse birleşme "
            "noktasında gerçekte olmayan ürünler görünür; tasarım yapılmadı. Tek bir kayıt "
            "yapıştırın.",
            f"{en_kutu}{kayit} FASTA records. Joined into one sequence, they would show "
            "products across the junction that do not exist; no design was made. Paste a "
            "single record."))
    s = re.sub(r"[\s0-9]", "", "".join(kept)).upper()

    target, extra = None, 0
    if allow_brackets:
        s, target, extra = _apply_brackets(s)
        if extra:
            s = _BRACKET.sub("", s)
            notes.append(t(
                f"Birden fazla köşeli parantez var; yalnızca ilki hedef olarak "
                f"kullanıldı, diğer {extra} tanesi yok sayıldı.",
                f"More than one square-bracket marker found; only the first was used as "
                f"the target, the other {extra} were ignored."))
    elif "[" in s or "]" in s:
        s = _BRACKET.sub("", s)
        notes.append(t("Bu modda köşeli parantez hedef işareti kullanılmaz; yok sayıldı.",
                       "Square-bracket target markers are not used in this mode; ignored."))

    if "U" in s and "T" not in s:
        s = s.replace("U", "T")
        notes.append(t("RNA dizisi algılandı (U); tasarım için T'ye çevrildi.",
                       "RNA sequence detected (U); converted to T for design."))

    amb = sorted(set(s) & set(_IUPAC))
    if amb:
        s = re.sub(f"[{_IUPAC}]", "N", s)
        notes.append(t(
            f"Belirsiz baz kodu ({', '.join(amb)}) N'e çevrildi; "
            "primer bu konumlara oturmayacak.",
            f"Ambiguous base codes ({', '.join(amb)}) were converted to N; "
            "no primer will be placed there."))

    bad = sorted(set(s) - set("ACGTN"))
    if bad:
        # U hem T ile birlikte geciyorsa RNA cevirisi devreye girmez; kullaniciya
        # "gecersiz karakter U" demek yaniltici olur, asil sorun karisik dizidir.
        if "U" in bad and "T" in s:
            raise PrimerError(t(
                "Dizide hem T hem U var; RNA mı DNA mı olduğu anlaşılamadı. "
                "Tek bir gösterim kullanın.",
                "The sequence contains both T and U, so it is unclear whether it is DNA "
                "or RNA. Use one notation only."))
        raise PrimerError(t(f"Dizide geçersiz karakter: {', '.join(bad[:8])}",
                            f"Invalid character in the sequence: {', '.join(bad[:8])}"))
    if not s:
        raise PrimerError(t("Temizlendikten sonra dizi boş kaldı.",
                            "The sequence was empty after cleaning."))
    return s, target, notes


def _seq_target_region(target, seq_len, p):
    """Hedefi min_dist_from_variant kadar genislet: urun hedefi kapsamak zorunda
    kalir, dolayisiyla primerler hedeften o kadar uzakta durur."""
    if not target:
        return None
    a, n = target
    excl = int(p["min_dist_from_variant"])
    start = max(0, a - excl)
    end = min(seq_len - 1, a + n - 1 + excl)
    return [start, max(1, end - start + 1)]


def _collect_pairs_seq(res, order, p, split=None, template=None, gap_span=None, hedef=None):
    """Serbest dizi modu icin ciftleri topla.
    split=None  -> tek dizi; konumlar dizinin basindan itibaren
    split=(lenA, gap) -> iki dizi; reverse konumlari B dizisine gore verilir."""
    pairs = []
    for rank, (i, ds, total) in enumerate(order, start=1):
        f_s, f_e, r_s, r_e = _primer_spans(res, i)
        d = _amplikon_ekle(_pair_core(res, i, ds, total, rank, p), res, i,
                           template, gap_span=gap_span, hedef=hedef)
        d["forward"]["seq_start"] = f_s + 1
        d["forward"]["seq_end"] = f_e + 1
        if split:
            off = split[0] + split[1]
            d["forward"]["region"] = "F"
            d["reverse"]["region"] = "R"
            d["reverse"]["seq_start"] = r_s + 1 - off
            d["reverse"]["seq_end"] = r_e + 1 - off
        else:
            d["forward"]["region"] = None
            d["reverse"]["region"] = None
            d["reverse"]["seq_start"] = r_s + 1
            d["reverse"]["seq_end"] = r_e + 1
        d["amplicon_start"] = f_s + 1
        d["amplicon_end"] = r_e + 1
        pairs.append(d)
    return pairs


def _seq_params(params):
    return _ayar_birlestir([DEFAULTS, SEQ_DEFAULTS], params)


# Hedef verilmeyen tek dizide primer3 dizinin TAMAMINDA aday arar ve sure dizi boyunun
# karesiyle buyur: 50 kb 1,6 sn, 100 kb 5,7 sn, 1 Mb 10 dakikadan uzun (2026-10-31 hata
# taramasi; sunucuda zaman siniri yok, arayuzde iptal edilse de hesap surer). Hedef
# verilince arama hedef cevresiyle sinirli (_dahil_bolge): 1 Mb 4 sn. Iki dizi modu
# etkilenmiyor (100 + 100 kb 1-3 sn).
DIZI_HEDEFSIZ_MAKS = 50_000


def design_from_sequence(sequence, target=None, params=None):
    """Tek dizi: kullanicinin verdigi dizi uzerinde primer cifti tasarla.
    Hedef, dizideki kose parantezle (ornek: ACGT[A/G]TTT) veya `target`
    parametresiyle (1-tabanli konum ya da 'baslangic-bitis') belirtilir."""
    p = _seq_params(params)
    seq, bracket_target, notes = parse_sequence_input(sequence)

    tgt = bracket_target
    if target not in (None, ""):
        if bracket_target:
            notes.append(t(
                "Hem köşeli parantez hem hedef konumu verildi; konum bilgisi kullanıldı.",
                "Both a bracket marker and a target position were given; the position "
                "was used."))
        tgt = _parse_target_arg(target, len(seq))

    if not tgt and len(seq) > DIZI_HEDEFSIZ_MAKS:
        raise PrimerError(t(
            f"Hedef belirtilmeden en fazla {tr_sayi(DIZI_HEDEFSIZ_MAKS)} bp'lik dizide tasarım "
            f"yapılır (girilen dizi {tr_sayi(len(seq))} bp). Hedefi köşeli parantezle (ör. "
            "ACGT[A/G]TTT) ya da 'Hedef konum' alanıyla belirtin ya da diziyi kısaltın; "
            "hedef verildiğinde uzunluk sınırı yoktur.",
            f"Without a target, design is limited to sequences of up to "
            f"{DIZI_HEDEFSIZ_MAKS:,} bp (this sequence is {len(seq):,} bp). Mark the target "
            "with brackets (e.g. ACGT[A/G]TTT) or the 'Target position' field, or shorten "
            "the sequence; with a target there is no length limit."))

    if len(seq) < int(p["product_size_min"]):
        raise PrimerError(t(
            f"Dizi çok kısa ({len(seq)} bp); en küçük amplikon "
            f"{int(p['product_size_min'])} bp olarak ayarlı.",
            f"Sequence too short ({len(seq)} bp); the minimum amplicon is set to "
            f"{int(p['product_size_min'])} bp."))

    seq_args = {"SEQUENCE_ID": "custom", "SEQUENCE_TEMPLATE": seq}
    region = _seq_target_region(tgt, len(seq), p)
    if region:
        seq_args["SEQUENCE_TARGET"] = region
        dahil = _dahil_bolge(len(seq), region, p)
        if dahil:
            seq_args["SEQUENCE_INCLUDED_REGION"] = dahil

    global_args = _build_global_args(p)
    global_args["PRIMER_MAX_NS_ACCEPTED"] = 0
    res = primer3.bindings.design_primers(seq_args, global_args)
    sira = _rank_order(res, p, template=seq)
    order = sira[:int(p["num_return"])]
    pairs = _collect_pairs_seq(res, order, p, template=seq,
                               hedef=(tgt[0], tgt[0] + tgt[1] - 1) if tgt else None)
    _annotate_pair_snps(pairs, res, order, [])     # bu modda genomik SNP bilgisi yok
    notes.extend(_suzgec_notlari(sira, p, pairs))
    sinir_notu = _pcr_sinir_notu(p)
    if sinir_notu:
        notes.append(sinir_notu)

    return {
        "mode": "sequence",
        "input": {"length": len(seq), "target": tgt},
        "sequence": seq,
        "num_returned": len(pairs),
        "pairs": pairs,
        "notes": notes,
        "params_used": p,
        "dbsnp": {"available": False, "in_template": 0, "excluded": 0,
                  "applied": False, "not_applicable": True},
        "explain": {
            "left": res.get("PRIMER_LEFT_EXPLAIN", ""),
            "right": res.get("PRIMER_RIGHT_EXPLAIN", ""),
            "pair": res.get("PRIMER_PAIR_EXPLAIN", ""),
        },
    }


def _parse_target_arg(target, seq_len):
    """'1234' veya '1200-1260' -> (0-tabanli baslangic, uzunluk)."""
    raw = str(target).strip().replace(" ", "")
    # En cok 12 basamak: 4.300+ basamakli girdi int()'te 500 veriyordu (bkz. _sayi)
    m = re.fullmatch(r"([0-9]{1,12})(?:([-_.]{1,2})([0-9]{1,12}))?", raw)
    if m and m.group(2) == ".":
        # Tek nokta aralik ayraci degil, ondalik ayracidir ("600.5"); aralik ".." ile yazilir.
        goster = raw if len(raw) <= 40 else raw[:40] + "…"
        raise PrimerError(t(
            f"Hedef konum tam sayı olmalı, ondalık olmaz: {goster} (örn. 1234 veya 1200-1260)",
            f"The target position must be a whole number, not a decimal: {goster} "
            "(e.g. 1234 or 1200-1260)"))
    if not m:
        goster = raw if len(raw) <= 40 else raw[:40] + "…"
        raise PrimerError(t(
            f"Hedef konum anlaşılamadı: {goster} (örn. 1234 veya 1200-1260)",
            f"Could not parse the target position: {goster} (e.g. 1234 or 1200-1260)"))
    a = int(m.group(1))
    b = int(m.group(3)) if m.group(3) else a
    if m.group(3) and b < a and a >= 1 and a <= seq_len:
        raise PrimerError(t(
            f"Hedef aralığın sonu ({b}) başlangıcından ({a}) küçük olamaz; "
            f"küçük sayıyı başa yazın (örn. {b}-{a}).",
            f"The end of the target range ({b}) cannot be smaller than its start ({a}); "
            f"put the smaller number first (e.g. {b}-{a})."))
    if a < 1 or b < a or b > seq_len:
        raise PrimerError(t(
            f"Hedef konum dizi sınırları dışında (dizi {seq_len} bp).",
            f"The target position is outside the sequence ({seq_len} bp)."))
    return (a - 1, b - a + 1)


def design_from_two_sequences(fwd_seq, rev_seq, params=None):
    """Iki dizi: forward primer BIRINCI dizinin, reverse primer IKINCI dizinin
    icinden secilir. Fuzyon transkripti (forward A geninde, reverse B geninde) ve
    delesyon kirilma noktasi tasarimlarinin dogru modeli budur.

    Diziler varsayilan olarak BITISIK kabul edilir; aralarinda bilinen bir mesafe
    varsa 'gap' ile verilir ve o kadar N eklenir (primer N'ye oturamaz)."""
    p = _seq_params(params)
    a_seq, _t1, n1 = parse_sequence_input(fwd_seq, allow_brackets=False,
                                          kutu=("Forward", "Forward"))
    b_seq, _t2, n2 = parse_sequence_input(rev_seq, allow_brackets=False,
                                          kutu=("Reverse", "Reverse"))
    notes = ([t(f"Forward bölgesi: {n}", f"Forward region: {n}") for n in n1]
             + [t(f"Reverse bölgesi: {n}", f"Reverse region: {n}") for n in n2])
    # Primer tumuyle kendi dizisinin icinde kalmali; dizi primerden kisaysa primer3
    # hic aday bulamaz. Eskiden bu "amplikon araligi bu iki diziye uymuyor" diye
    # YANLIS sebeple aciklaniyordu (2026-10-29 hata taramasi).
    en_kisa = int(p["primer_min_size"])
    for ad, s in (("Forward", a_seq), ("Reverse", b_seq)):
        if len(s) < en_kisa:
            raise PrimerError(t(
                f"{ad} dizisi çok kısa ({len(s)} bp): primer en az {en_kisa} baz olmalı "
                "ve tamamı bu dizinin içinde kalmalı.",
                f"The {ad.lower()} sequence is too short ({len(s)} bp): a primer needs at "
                f"least {en_kisa} bases and must lie entirely within it."))

    gap = int(p.get("gap") or 0)
    if gap < 0:
        raise PrimerError(t("Aradaki mesafe negatif olamaz.",
                            "The distance between the sequences cannot be negative."))
    if gap > int(p["max_gap"]):
        raise PrimerError(t(
            f"Aradaki mesafe çok büyük ({tr_sayi(gap)} bp). Bu kadar uzun bir ürün PCR ile "
            f"çoğaltılamaz; sınır {tr_sayi(int(p['max_gap']))} bp.",
            f"The distance is too large ({gap:,} bp). A product that long cannot be "
            f"amplified by PCR; the limit is {int(p['max_gap']):,} bp."))

    lenA, lenB = len(a_seq), len(b_seq)
    template = a_seq + ("N" * gap) + b_seq
    total = lenA + gap + lenB

    free = bool(p.get("ignore_product_size"))
    if free:
        # Mesafe bilinmiyor: urun boyu kisiti kaldirilir, primerler dizilerin her
        # yerinden secilebilir. Kisa amplikon tercihi de kapatilir - yoksa siralama
        # yine primerleri birlesme noktasina dogru ceker.
        p = dict(p)
        p["product_size_min"] = 2 * int(p["primer_min_size"]) + gap
        p["product_size_max"] = total
        p["prefer_short_product"] = 0.0
    elif int(p["product_size_min"]) > total:
        # Kullanicinin amplikon araligi iki bolgeye sigmiyorsa erkenden ve anlasilir soyle
        raise PrimerError(t(
            f"Amplikon alt sınırı ({int(p['product_size_min'])} bp) iki dizinin "
            f"toplamından ({total} bp) büyük. Aradaki mesafe önemli değilse "
            "'mesafe bilinmiyor' seçeneğini kullanın.",
            f"The minimum amplicon size ({int(p['product_size_min'])} bp) exceeds the "
            f"combined length of the two sequences ({total} bp). If the distance does "
            "not matter, use the 'distance unknown' option."))

    # forward SADECE A icinde, reverse SADECE B icinde kalsin
    seq_args = {
        "SEQUENCE_ID": "custom_pair",
        "SEQUENCE_TEMPLATE": template,
        "SEQUENCE_PRIMER_PAIR_OK_REGION_LIST": [[0, lenA, lenA + gap, lenB]],
    }
    global_args = _build_global_args(p)
    global_args["PRIMER_MAX_NS_ACCEPTED"] = 0

    res = primer3.bindings.design_primers(seq_args, global_args)
    if int(res.get("PRIMER_PAIR_NUM_RETURNED", 0)) == 0:
        notes.append(t(
            "Uygun çift bulunamadı. En sık nedeni amplikon aralığının bu iki diziye "
            f"uymaması: en kısa olası ürün yaklaşık {gap + 2 * int(p['primer_min_size'])} bp, "
            f"en uzunu {lenA + gap + lenB} bp.",
            "No suitable pair was found. The usual cause is an amplicon range that does "
            f"not fit these two sequences: the shortest possible product is about "
            f"{gap + 2 * int(p['primer_min_size'])} bp and the longest "
            f"{lenA + gap + lenB} bp."))

    sira = _rank_order(res, p, template=template)
    order = sira[:int(p["num_return"])]
    notes.extend(_suzgec_notlari(sira, p, order))
    pairs = _collect_pairs_seq(res, order, p, split=(lenA, gap),
                               template=template,
                               gap_span=((lenA, lenA + gap - 1) if gap else None))
    _annotate_pair_snps(pairs, res, order, [])

    sinir_notu = _pcr_sinir_notu(p)
    if sinir_notu:
        notes.append(sinir_notu)

    if free:
        notes.append(t(
            "Ürün boyu kısıtı uygulanmadı; primerler her iki dizinin tamamından, "
            "yalnızca kaliteye göre seçildi. Gösterilen amplikon boyu ancak diziler "
            "gerçekten bitişikse geçerlidir.",
            "No product size limit was applied; primers were chosen from the whole of "
            "both sequences on quality alone. The amplicon size shown only holds if the "
            "sequences really are contiguous."))

    return {
        "mode": "sequence_pair",
        "input": {"forward_length": lenA, "reverse_length": lenB, "gap": gap,
                  "free_product_size": free},
        "num_returned": len(pairs),
        "pairs": pairs,
        "notes": notes,
        "params_used": p,
        "dbsnp": {"available": False, "in_template": 0, "excluded": 0,
                  "applied": False, "not_applicable": True},
        "explain": {
            "left": res.get("PRIMER_LEFT_EXPLAIN", ""),
            "right": res.get("PRIMER_RIGHT_EXPLAIN", ""),
            "pair": res.get("PRIMER_PAIR_EXPLAIN", ""),
        },
    }


# ------------------------------------------------------------------
# Kirilma noktasi modu: delesyon / tandem duplikasyon
# ------------------------------------------------------------------
# DELESYON (gap-PCR): primerler silinen bolgenin IKI YANINA konur. Delesyonlu
#   alelde yan yana gelip kisa bir "kirilma noktasi" urunu verirler; normal
#   alelde aralarinda delesyonun tamami durur (birkac kb'tan buyukse urun
#   cikmaz). Tasarim, delesyonlu alelin KENDISI uzerinde yapilir: sol kanat +
#   sag kanat birlestirilir, primer3 kirilma noktasini kapsayan cifti secer.
# TANDEM DUPLIKASYON: ilk kopyanin sonu ikinci kopyanin basina baglanir.
#   Primerler duplike bolgenin ICINE, uclara yakin ve DISA bakacak sekilde
#   konur (F sona yakin saga, R basa yakin sola). Normal genomda birbirinden
#   uzaga baktiklari icin urun yok; duplikasyonda baglantida yuz yuze gelirler.
#   Urun boyu dup buyuklugunden BAGIMSIZ. Kucuk dup'ta dis primerler + boy farki.
# BELIRSIZLIK (bp_margin): kirilma noktalari ±m bp bilinmiyorsa primerler olasi
#   tum kirilma noktalarinin disina (DEL) / icine (DUP) konur; urun boyu araliga
#   doner. Gosterilen dizi en genis delesyon / en dar dup varsayimiyla.
BP_DEFAULTS = {
    "bp_margin": 0,
    "control_primer": False,   # 3. primer: DEL'de normal alel bandi, DUP'ta PCR kontrolu
    "dup_small_max": 1500,     # bu boya kadar dup: dis primerler + boy farki (bant sigarsa)
    # Normal alel bandinin kullanicinin kendi sinirina gore nerede durdugu: bu boya
    # kadar sinir icinde, 2 katina kadar sinirin ustunde, otesi cok ustunde. Bunlar
    # PCR hakkinda mutlak bir hukum DEGIL - baska bir laboratuvar sinirini yukseltince
    # ayni bant "sinir icinde" olur; metinler de oyle yazilmistir (2026-10-25).
    # Verilmezse pcr_max'tan turetilir (bkz. _kirilma_parametreleri); eskiden sabit
    # 3 / 6 kb'ti ve en fazla ~700 bp cogaltan laboratuvarda 900 bp'lik normal alel
    # bandina "cogalir" deniyordu.
    "wt_amp_max": 3000,
    "wt_weak_max": 6000,
    "control_min_diff": 100,   # kontrol bandi ile kirilma bandi arasi en az fark (bp)
    # Primerin 3' ucu kirilma noktasina en az bu kadar uzak (gelismis ayardaki
    # "varyanta uzaklik" daha buyukse o). 50 bp'de kirilma noktasi Sanger
    # okumasinin ilk, kalitesiz ~40 bazina dusebiliyordu.
    "bp_min_dist": 100,
}
KIRILMA_TIPLERI = {"del": "del", "delesyon": "del", "deletion": "del",
                   "dup": "dup", "duplikasyon": "dup", "duplication": "dup"}


def _legacy_cift(a, b):
    """Iki primer arasi legacy tamamlayicilik (Primer-BLAST birimi). 3 primerli
    tasarimda kontrol primerinin DIGER reverse primerle dimerine bakmak icin."""
    if max(len(a), len(b)) > 36:
        return None
    try:
        r = primer3.bindings.design_primers(
            {"SEQUENCE_ID": "dimer", "SEQUENCE_PRIMER": a, "SEQUENCE_PRIMER_REVCOMP": b},
            {"PRIMER_TASK": "check_primers", "PRIMER_PICK_ANYWAY": 1,
             "PRIMER_THERMODYNAMIC_OLIGO_ALIGNMENT": 0,
             "PRIMER_THERMODYNAMIC_TEMPLATE_ALIGNMENT": 0,
             "PRIMER_MIN_SIZE": 5, "PRIMER_OPT_SIZE": 20, "PRIMER_MAX_SIZE": 36,
             "PRIMER_MIN_TM": 0, "PRIMER_MAX_TM": 100, "PRIMER_MIN_GC": 0, "PRIMER_MAX_GC": 100,
             "PRIMER_MAX_POLY_X": 100, "PRIMER_MAX_SELF_ANY": 100, "PRIMER_MAX_SELF_END": 100,
             "PRIMER_PAIR_MAX_COMPL_ANY": 100, "PRIMER_PAIR_MAX_COMPL_END": 100,
             "PRIMER_PAIR_MAX_DIFF_TM": 100, "PRIMER_MAX_END_STABILITY": 100,
             "PRIMER_PRODUCT_SIZE_RANGE": [[36, 1000]]})
    except Exception:
        return None
    if not r.get("PRIMER_PAIR_NUM_RETURNED"):
        return None
    return {"compl_any": r.get("PRIMER_PAIR_0_COMPL_ANY"),
            "compl_end": r.get("PRIMER_PAIR_0_COMPL_END")}


def _snp_notu_gevsetildi(n):
    return t(
        f"UYARI: Bölge yaygın varyant açısından yoğun ({n} varyant); hepsinden "
        "kaçınılınca uygun primer kalmadı. Kısıt kaldırıldı — primerlerin üzerindeki "
        "varyantlar işaretlendi, özellikle 3' uca yakın olanlara dikkat edin.",
        f"WARNING: The region is dense in common variants ({n} variants); avoiding all "
        "of them left no suitable primer. The restriction was lifted — variants on the "
        "primers are marked; watch those near the 3' end.")


def _tekrar_notu(n):
    return t(
        f"{n} aday çift elendi: primerlerden birinin 3' ucu şablonda birden fazla yere "
        "oturuyor (tekrar dizisi) ve birden çok bant verirdi.",
        f"{n} candidate pairs were dropped: the 3' end of one of the primers fits more than "
        "one place in the template (a repeat) and would give several bands.")


def _bp_baglanti_tasarimi(assembly, chrom, parcalar, p, dist, etiket):
    """Iki genomik parcanin birlesiminden olusan (referansta OLMAYAN) dizi uzerinde
    cift tasarla: F 1. parcadan, R 2. parcadan; ikisi de birlesim noktasina en az
    'dist' bp uzak. parcalar = [(genomik_bas1, dizi1), (genomik_bas2, dizi2)].
    Doner: (ciftler, primer3 sonucu, snp listesi, snp kacinmasi uygulandi mi, notlar)."""
    (g1, s1), (g2, s2) = parcalar
    J = len(s1)
    sablon = s1 + s2
    en_az = dist + int(p["primer_min_size"])
    if J < en_az or len(s2) < en_az:
        raise PrimerError(t(
            "Kırılma noktasının bir yanında primer koymaya yetecek dizi yok "
            f"(her yanda en az {en_az} bp gerekli). Kromozom ucuna çok yakın ya da "
            "bölge çok kısa olabilir.",
            "There is not enough sequence on one side of the breakpoint to place a "
            f"primer (at least {en_az} bp per side is needed). It may be too close to "
            "the chromosome end, or the region may be too short."))

    snps = _snp_template_offsets(
        _collect_snps(assembly, normalize_chrom(chrom), g1, g1 + J - 1, p), g1)
    for s in _collect_snps(assembly, normalize_chrom(chrom), g2, g2 + len(s2) - 1, p):
        s = dict(s)
        s["template_offset"] = s["position"] - g2 + J
        snps.append(s)
    haric = (_excluded_from_snps(snps, len(sablon))
             if p.get("avoid_common_snps", True) else [])

    seq_args = {
        "SEQUENCE_ID": etiket,
        "SEQUENCE_TEMPLATE": sablon,
        "SEQUENCE_PRIMER_PAIR_OK_REGION_LIST": [[0, J - dist, J + dist, len(s2) - dist]],
    }
    if haric:
        seq_args["SEQUENCE_EXCLUDED_REGION"] = haric
    global_args = _build_global_args(p)
    global_args["PRIMER_MAX_NS_ACCEPTED"] = 0
    res = primer3.bindings.design_primers(seq_args, global_args)
    notlar = []
    uygulandi = bool(haric)
    if haric and int(res.get("PRIMER_PAIR_NUM_RETURNED", 0)) == 0:
        seq_args.pop("SEQUENCE_EXCLUDED_REGION")
        res = primer3.bindings.design_primers(seq_args, global_args)
        uygulandi = False
        # Kisit kaldirildiginda da cift cikmadiysa "varyantlar isaretlendi" demek yanlis
        if int(res.get("PRIMER_PAIR_NUM_RETURNED", 0)):
            notlar.append(_snp_notu_gevsetildi(len(haric)))

    def genomik(idx):
        return g1 + idx if idx < J else g2 + (idx - J)

    sira = _rank_order(res, p, template=sablon)
    order = sira[:int(p["num_return"])]
    notlar.extend(_suzgec_notlari(sira, p, order))
    ciftler = []
    for rank, (i, ds, total) in enumerate(order, start=1):
        f_s, f_e, r_s, r_e = _primer_spans(res, i)
        d = _amplikon_ekle(_pair_core(res, i, ds, total, rank, p), res, i, sablon)
        d["amplicon"]["junction_offsets"] = [J - f_s]      # arayuz '|' ile isaretler
        # Girilen konumun karsiligi: kirilma noktasinin iki yanindaki bazlar. Delesyonda silinen
        # bazlar urunde yoktur; yan yana gelen iki baz gorulur. Tandem duplikasyonda bunlar
        # bolgenin son ve ilk bazidir.
        d["amplicon"]["variant_span"] = [J - f_s - 1, J - f_s]
        d["forward"]["genomic_start"] = genomik(f_s)
        d["forward"]["genomic_end"] = genomik(f_e)
        d["reverse"]["genomic_start"] = genomik(r_s)
        d["reverse"]["genomic_end"] = genomik(r_e)
        ciftler.append(d)
    _annotate_pair_snps(ciftler, res, order, snps)
    return ciftler, res, snps, uygulandi, notlar


def _bp_kontrol_primeri(assembly, chrom, cift, bolge_bas, bolge_bit, ana_aralik, p, es="forward"):
    """3. primer: [bolge_bas, bolge_bit] icinde, ciftin bir primeriyle (es) normal referansta
    siradan bir bant veren primer.
      es="forward": ciftin F'i ile; bolgenin BASINA yakin bir reverse primer (F bolgenin solunda).
      es="reverse": ciftin R'si ile; bolgenin SONUNA yakin bir forward primer (R bolgenin saginda).
    Ikinci yol birincinin aynasidir: sablon ters tamamlayicisina cevrilince R sablonun basina
    gelir ve ayni hesap kullanilir (bant boyu, SNP ofseti, 3' uc uzakligi ayni kalir).
    Bant boyu ana bandin OLASI TUM boylarindan (belirsizlik payi varken bir
    aralik) en az control_min_diff uzak secilir ki tek jelde ayrilsin. Eskiden
    yalnizca orta degere bakiliyordu: ±100 bp payla 476-876 bp'lik baglanti bandina
    519 bp'lik kontrol secildi (2026-10-14, arayuz denemesi).
    Doner: (kontrol sozlugu, None) ya da (None, neden)."""
    ana_min, ana_max = ana_aralik
    ayna = es == "reverse"
    ortak = cift[es]["sequence"]                                  # kontrolle bant veren primer
    diger = cift["forward" if ayna else "reverse"]["sequence"]    # ayni tupteki ucuncu primer
    maks_nt = int(p["primer_max_size"])
    if bolge_bit - bolge_bas + 1 < maks_nt + 10:
        return None, t("kontrol primeri için bölge çok kısa",
                       "the region is too short for a control primer")
    # Arama penceresi BOLGENIN ortak primere bakan ucundan baslar. Eskiden F'den baslayip
    # 1500 bp'de kesiliyordu; belirsizlik payi buyukken F bolgeden zaten >2 kb uzakta kaldigi
    # icin 354 kb'lik delesyonda bile "bolge cok kisa" deniyordu (stres testi).
    # o5: ortak primerin 5' ucu; yakin: o5'ten bolgenin yakin ucuna; boy: sablon uzunlugu.
    if ayna:
        o5 = cift["reverse"]["genomic_end"]
        yakin = o5 - bolge_bit
        son = max(bolge_bas, bolge_bit - 1500, 1)
        boy = o5 - son + 1
    else:
        o5 = cift["forward"]["genomic_start"]
        yakin = bolge_bas - o5
        son = min(bolge_bit, bolge_bas + 1500)
        kr_boy = kromozom_uzunlugu(assembly, chrom)
        if kr_boy is not None:
            son = min(son, kr_boy)
        boy = son - o5 + 1
    if boy < yakin + maks_nt:
        return None, t("kontrol primeri için bölge çok kısa",
                       "the region is too short for a control primer")
    sinir = int(p["pcr_max"])
    if yakin + maks_nt > sinir:
        return None, t(
            "belirsizlik payı büyük olduğu için kontrol bandı çoğaltılabilen en uzun ürünü "
            f"({tr_sayi(sinir)} bp) aşardı",
            "because of the large uncertainty margin the control band would exceed the "
            f"longest amplifiable product ({sinir:,} bp)")
    if ayna:
        ham, _ = get_sequence(assembly, chrom, son, o5)
        sablon = revcomp(ham)
    else:
        sablon, _ = get_sequence(assembly, chrom, o5, son)
    alt = yakin + maks_nt                     # kontrol primeri tamamen bolgenin icinde kalsin
    ust = min(boy, sinir)                     # kontrol bandi laboratuvarin cogaltabildigi boyda
    fark = int(p["control_min_diff"])
    araliklar = [[lo, hi] for lo, hi in ((alt, min(ust, ana_min - fark)),
                                         (max(alt, ana_max + fark), min(ust, ana_max + fark + 600)))
                 if hi >= lo]
    if not araliklar:
        if ana_max - ana_min >= 2 * fark:
            # Buyuk payda ana bant 300-4300 bp gibi genis bir araliga yayiliyor; ondan
            # ayrilacak bant ya cok kisa (F bolgeden uzak) ya da pcr_max'i asiyor.
            return None, t(
                f"belirsizlik payı yüzünden ana bant geniş bir aralığa yayılıyor "
                f"({tr_sayi(ana_min)}–{tr_sayi(ana_max)} bp); ondan ayrılacak bir kontrol bandı "
                f"çoğaltılabilen en uzun ürüne ({tr_sayi(sinir)} bp) sığmıyor, payı küçültmek gerekir",
                f"because of the uncertainty margin the main band spans a wide range "
                f"({ana_min:,}–{ana_max:,} bp); no control band distinct from it fits within "
                f"the longest amplifiable product ({sinir:,} bp), the margin would have to be "
                "reduced")
        return None, t("ana banttan ayrılacak ve çoğaltılabilen en uzun ürüne "
                       f"({tr_sayi(sinir)} bp) sığan bir kontrol bandı bulunamadı",
                       "no control band size distinct from the main band fits within the "
                       f"longest amplifiable product ({sinir:,} bp)")
    if ayna:
        # Ters cevrilmis sablonda genomik [pos, pos+span-1] -> [o5-pos-span+1, o5-pos]
        snps = []
        for s in _collect_snps(assembly, normalize_chrom(chrom), son, o5, p):
            s = dict(s)
            s["template_offset"] = o5 - s["position"] - s["span"] + 1
            snps.append(s)
    else:
        snps = _snp_template_offsets(
            _collect_snps(assembly, normalize_chrom(chrom), o5, son, p), o5)
    haric = (_excluded_from_snps(snps, len(sablon))
             if p.get("avoid_common_snps", True) else [])
    seq_args = {"SEQUENCE_ID": "kontrol", "SEQUENCE_TEMPLATE": sablon, "SEQUENCE_PRIMER": ortak}
    if haric:
        seq_args["SEQUENCE_EXCLUDED_REGION"] = [r for r in haric if r[0] >= len(ortak)]
    pk = dict(p)
    pk["product_size_min"], pk["product_size_max"] = araliklar[0][0], araliklar[-1][1]
    g = _build_global_args(pk)
    g["PRIMER_PRODUCT_SIZE_RANGE"] = araliklar
    g["PRIMER_NUM_RETURN"] = 5
    g["PRIMER_MAX_NS_ACCEPTED"] = 0
    try:
        res = primer3.bindings.design_primers(seq_args, g)
    except OSError as e:
        return None, str(e)
    n = int(res.get("PRIMER_PAIR_NUM_RETURNED", 0))
    if not n:
        return None, t("uygun kontrol primeri bulunamadı", "no suitable control primer was found")
    # Ortak ya da kontrol primeri bu bolgede birden fazla kez geciyorsa her kopyadan
    # ayri bant cikar. primer3 SEQUENCE_PRIMER'i sablonun BASKA bir kopyasina oturtup
    # bant boyunu ona gore bildirebiliyordu (stres testi 2026-10-17: 278 / 280 bp).
    # Tasarim suzgeciyle ayni olcut: 3' uc, iki iplik. Ortak primer tekrarliysa hicbir aday
    # tek bant vermez; aday tekrarliysa yalniz o aday elenir.
    tekrar = t("primer bu bölgede birden fazla kez geçiyor (tekrar dizisi); kontrol "
               "bandı tek olmazdı",
               "a primer occurs more than once in this region (a repeat); the control "
               "band would not be single")
    if _tekrar_sayisi(sablon.upper(), ortak) > 1:
        return None, tekrar
    gecerli = [i for i in range(n)
               if _tekrar_sayisi(sablon.upper(), res[f"PRIMER_RIGHT_{i}_SEQUENCE"]) <= 1]
    if not gecerli:
        return None, tekrar
    # Hairpin (kullanici karari 2026-11-14, F-05 esigiyle ayni: ciftin Ta onerisi - 5 °C): legacy
    # hizalamada primer3 hairpin'e bakmiyor, ilk aday oldugu gibi aliniyordu. Bir vakada obur uctan
    # gelen uc kontrolun ucu de esigi geciyordu (49,4 °C, Ta 50,3). Esigi gecmeyen ilk aday
    # secilir; hepsi geciyorsa en iyisi kalir ve uyari tasir (_bp_kontrol_ara karta yazar).
    esik = round(float(cift["ta_suggested"]) - HAIRPIN_UYARI_PAYI, 1)
    hp = {i: _hairpin_tm(res[f"PRIMER_RIGHT_{i}_SEQUENCE"]) for i in gecerli}
    temiz = [i for i in gecerli if not (hp[i] > 0 and hp[i] >= esik)]
    i = temiz[0] if temiz else gecerli[0]
    _f_s, _f_e, r_s, r_e = _primer_spans(res, i)
    # Aynada primer3'un "right" primeri ters cevrilmis sablonda: dizisi genomun arti ipligi,
    # yani kontrol primeri bir forward primer olur.
    seq = res[f"PRIMER_RIGHT_{i}_SEQUENCE"]
    es_dimer = round(_val(res, f"PRIMER_PAIR_{i}_COMPL_END"), 1)
    diger_dimer = (_legacy_cift(diger, seq) or {}).get("compl_end")
    kontrol = {
        "sequence": seq,
        "length": len(seq),
        "tm": round(float(res[f"PRIMER_RIGHT_{i}_TM"]), 1),
        "gc": round(float(res[f"PRIMER_RIGHT_{i}_GC_PERCENT"]), 1),
        "hairpin_tm": hp[i],
        "self_dimer_tm": round(_val(res, f"PRIMER_RIGHT_{i}_SELF_ANY"), 1),
        "self_dimer_3p_tm": round(_val(res, f"PRIMER_RIGHT_{i}_SELF_END"), 1),
        "genomic_start": (o5 - r_e) if ayna else (o5 + r_s),
        "genomic_end": (o5 - r_s) if ayna else (o5 + r_e),
        # primer3'un PRODUCT_SIZE'i degil: ortak primerin 5' ucundan (sablonun basi)
        # kontrol primerinin 5' ucuna. Ikisi ayniysa sorun yok; degilse dogrusu bu.
        "band": r_e + 1,
        # Kontrol bandini hangi primerle verir: arayuz adlari ve dimer uyarisini buna gore
        # yazar. Dimer: ortak primerle primer3'un cift skoru, ucuncu primerle legacy skor.
        "pairs_with": es,
        "dimer_with_f": diger_dimer if ayna else es_dimer,
        "dimer_with_r": es_dimer if ayna else diger_dimer,
    }
    kontrol["snps"] = []
    for s in snps:
        if s["template_offset"] + s["span"] - 1 < r_s or s["template_offset"] > r_e:
            continue
        kontrol["snps"].append({"rsid": s["rsid"], "maf": s["maf"], "indel": s["indel"],
                                "distance_from_3p": uc3_uzakligi(r_s, s["template_offset"],
                                                                 s["span"])})
    # Yalniz _bp_kontrol_ara icin (sozlukten cikarilir): esigi gecen kontrolun uyari kaydi
    kontrol["_hairpin_uyari"] = (None if temiz else
                                 {"primer": "control", "hairpin_tm": hp[i],
                                  "ta": float(cift["ta_suggested"]), "esik": esik})
    return kontrol, None


def _bp_kontrol_ara(assembly, chrom, cift, yollar, ana_aralik, p, iki_uc_notu):
    """Kontrol primerini yollarda sirayla arar: [(es, bolge_bas, bolge_bit), ...]. Ilk yol
    (F ile) eskiden tek yoldu; orada bulunan kontroller degismesin diye once o denenir.
    Hicbirinde bulunamazsa ilk yolun nedeni ve iki ucun da denendigi notu doner.
    Obur uc (R ile) 2026-11-14'te eklendi: bir delesyonda
    en iyi iki ciftte kontrol bandina kalan iki dar pencereden biri AT'den zengindi
    (GC %27), otekindeki tek aday yaygin varyantin ustundeydi ve "uygun kontrol
    primeri bulunamadi" deniyordu; obur ucta 184-232 bp'lik kontroller bulunuyor.
    Hairpin (ayni gun): bir uctaki kontrol hairpin esigini geciyorsa obur uctaki esigi
    gecmeyen kontrol yegdir. Oncelik: ilk uc temiz > obur uc temiz > ilk uc esik ustu > obur
    uc esik ustu. Esik ustu kontrol secilirse uyarisi ciftin hairpin_warn listesine eklenir;
    kart bunu forward / reverse uyarisiyla ayni satirda gosterir (siralama degismez)."""
    ilk = None
    yedek = None
    for es, bas, bit in yollar:
        k, neden = _bp_kontrol_primeri(assembly, chrom, cift, bas, bit, ana_aralik, p, es)
        if k is None:
            ilk = ilk or neden
            continue
        if k.get("_hairpin_uyari") is None:
            k.pop("_hairpin_uyari", None)
            return k, None
        yedek = yedek or k
    if yedek is not None:
        cift.setdefault("hairpin_warn", []).append(yedek.pop("_hairpin_uyari"))
        return yedek, None
    return None, ilk + iki_uc_notu


def _kirilma_parametreleri(params):
    p = _ayar_birlestir([DEFAULTS, BP_DEFAULTS], params)
    verilen = params if isinstance(params, dict) else {}
    if verilen.get("wt_amp_max") is None:
        p["wt_amp_max"] = int(p["pcr_max"])
    if verilen.get("wt_weak_max") is None:
        p["wt_weak_max"] = 2 * int(p["wt_amp_max"])
    return p


def _bp_sinira_sigdir(p, buyume, geo_min):
    """Kirilma bandi belirsizlik payi yuzunden primer3 urununden (P3) 'buyume' bp'ye
    kadar uzayabilir (DEL / tandem: 4m). En uzun olasi bant laboratuvar sinirini
    (pcr_max) asmasin diye primer3'un urun ust siniri daraltilir. Sigmiyorsa (P3,
    primerlerin geometrisinin izin verdigi en kisa boydan bile kisa olmali) ayar
    degistirilmez; uyariyi design_breakpoint sonda verir."""
    if not buyume:
        return p
    ust = min(int(p["product_size_max"]), int(p["pcr_max"]) - buyume)
    if ust < geo_min:
        return p
    pd = dict(p)
    pd["product_size_max"] = ust
    pd["product_size_min"] = min(int(p["product_size_min"]), ust)
    return pd


def _bp_baglanti_sinirli(assembly, chrom, parcalar, p, dist, etiket, buyume, geo_min):
    """Birlesim tasarimi, once en uzun olasi bant laboratuvar sinirina sigacak sekilde.
    Daralan pencerede primer cikmazsa (±100 payla 700 bp sinirinda urun 236-300 bp'ye
    sikisir) sinirsiz tasarima donulur; bandin sinirlari asabilecegini design_breakpoint
    sondaki uyariyla soyler. Bos sonuc vermekten iyidir: kullanici payi kucultebilir."""
    pd = _bp_sinira_sigdir(p, buyume, geo_min)
    sonuc = _bp_baglanti_tasarimi(assembly, chrom, parcalar, pd, dist, etiket)
    if not sonuc[0] and pd is not p:
        sonuc = _bp_baglanti_tasarimi(assembly, chrom, parcalar, p, dist, etiket)
    return sonuc


def _bp_en_uzun(sonuc):
    """design_breakpoint sonucundaki en uzun olasi bant (uyari karari bununla verilir)."""
    ciftler = sonuc.get("pairs") or []
    if not ciftler:
        return 0
    inp = sonuc.get("input") or {}
    anahtar = ("mut_max" if inp.get("type") == "del" else
               "junction_max" if inp.get("approach") == "tandem_junction" else "dup_max")
    return max(c["bp"][anahtar] for c in ciftler)


def _bp_pay_ara(assembly, chrom, start, end, sv_type, params, ust, sinir, butce=10.0):
    """Belirsizlik payi icin, motorla DENENMIS (en az bir cift, en uzun bant sinir icinde)
    bir deger bulur; yoksa None. Kuramsal formul (sinir - geo_min) // 4 yalniz ust sinirdir:
    primer3 o daracik pencerede cift bulamayabilir (A4-01). Once ust, sonra 0, sonra
    ikili arama (4 bp adim); sure butcesi asilirsa o ana kadar dogrulanan deger doner."""
    verilen = dict(params) if isinstance(params, dict) else {}
    bitis = time.monotonic() + butce

    def calisir(x):
        pr = dict(verilen)
        pr["bp_margin"] = int(x)
        pr["control_primer"] = False
        try:
            s = design_breakpoint(assembly, chrom, start, end, sv_type, pr, _oneri_ara=True)
        except PrimerError:
            return False
        return bool(s.get("pairs")) and _bp_en_uzun(s) <= sinir

    # Kisa duplikasyonda kuramsal ust sinir NEGATIF cikabilir (formul pay 0'da bile sigmayacagini
    # soyler), ama primer3 pay 0 iken cift bulabiliyor: o durumda da 0 denenir (D3-01).
    if ust >= 0 and calisir(ust):
        return ust
    if ust == 0 or not calisir(0):
        return None
    if ust < 0:
        return 0
    alt, ust_kotu = 0, ust
    while ust_kotu - alt > 4 and time.monotonic() < bitis:
        orta = (alt + ust_kotu) // 2
        if calisir(orta):
            alt = orta
        else:
            ust_kotu = orta
    return alt


def design_breakpoint(assembly, chrom, start, end, sv_type="del", params=None, _oneri_ara=False):
    """Delesyon ya da tandem duplikasyon sinirlarindan kirilma noktasi PCR'i.
    start/end: silinen / duplike edilen bolgenin ilk ve son bazi (1-tabanli,
    kapsayici). Bkz. modul ustu aciklama. _oneri_ara: pay onerisi aramasinin ic
    cagrisi (oneri aramaz, ozyineleme olmaz)."""
    p = _kirilma_parametreleri(params)
    if assembly not in ("GRCh37", "GRCh38"):
        raise PrimerError(t("assembly 'GRCh37' veya 'GRCh38' olmalı.",
                            "assembly must be 'GRCh37' or 'GRCh38'."))
    tip = KIRILMA_TIPLERI.get(str(sv_type or "").strip().lower())
    if not tip:
        raise PrimerError(t("Tip 'delesyon' ya da 'duplikasyon' olmalı.",
                            "The type must be 'deletion' or 'duplication'."))
    chrom = normalize_chrom(chrom or "")
    if not chrom:
        raise PrimerError(t("Kromozom belirtilmeli.", "A chromosome must be given."))
    try:
        start, end = int(start), int(end)
    except (TypeError, ValueError):
        raise PrimerError(t("Başlangıç ve bitiş sadece rakam olmalı.",
                            "Start and end must contain digits only."))
    if start < 1:
        raise PrimerError(t("Koordinat 1'den küçük olamaz.",
                            "The coordinate cannot be smaller than 1."))
    if end < start:
        raise PrimerError(t("Bitiş başlangıçtan küçük olamaz.",
                            "The end cannot be smaller than the start."))
    uzunluk = kromozom_uzunlugu(assembly, chrom)
    if uzunluk is not None and end > uzunluk:
        raise _kromozom_disi(assembly, chrom, end, uzunluk)
    m = int(p["bp_margin"])
    if m < 0:
        raise PrimerError(t("Belirsizlik payı negatif olamaz.",
                            "The uncertainty margin cannot be negative."))
    D = end - start + 1
    dist = max(int(p["min_dist_from_variant"]), int(p["bp_min_dist"]))
    flank = max(int(p["product_size_max"]), 700)
    kontrol_istendi = bool(p.get("control_primer"))
    sinir = int(p["pcr_max"])
    # Birlesim urununun primer geometrisine gore en kisa boyu: iki yanda 'dist' + primer
    geo_min = 2 * (dist + int(p["primer_min_size"]))
    notes = []
    pb = par.bolge(assembly, chrom, start, end)
    if pb:
        notes.append(par.not_metni(pb["ad"]))
    # Kirilma noktasi kanatlarinda yakin-ozdes kopyasi olan bir gen var mi?
    paralog_notu = paralog.notu(assembly, None, chrom, start, end, mod="dna")
    if paralog_notu:
        notes.append(paralog_notu)

    def kes(a, b):
        a = max(1, a)
        if uzunluk is not None:
            b = min(uzunluk, b)
        if b < a:
            return a, "", "local"
        s, kaynak = get_sequence(assembly, chrom, a, b)
        return a, s, kaynak

    kaynak = "local"
    yaklasim = None
    sablon_boyu = None
    snps_toplam, uygulandi, res = [], False, {}

    if tip == "del":
        yaklasim = "gap_pcr"
        sol_bit = start - m - 1
        sag_bas = end + m + 1
        if sol_bit < dist + int(p["primer_min_size"]) or (
                uzunluk is not None and uzunluk - sag_bas + 1 < dist + int(p["primer_min_size"])):
            raise PrimerError(t(
                "Delesyon kromozom ucuna çok yakın; dış tarafta primer için yer yok.",
                "The deletion is too close to the chromosome end; there is no room for a "
                "primer on the outer side."))
        g1, s1, kaynak = kes(sol_bit - flank + 1, sol_bit)
        g2, s2, _ = kes(sag_bas, sag_bas + flank - 1)
        sablon_boyu = len(s1) + len(s2)
        ciftler, res, snps_toplam, uygulandi, ek = _bp_baglanti_sinirli(
            assembly, chrom, [(g1, s1), (g2, s2)], p, dist, f"{chrom}_{start}_{end}_del",
            4 * m, geo_min)
        notes += ek
        for c in ciftler:
            p3 = c["product_size"]
            wt = c["reverse"]["genomic_end"] - c["forward"]["genomic_start"] + 1
            c["bp"] = {"mut": p3 + 2 * m, "mut_min": p3, "mut_max": p3 + 4 * m, "wt": wt,
                       "wt_status": ("var" if wt <= int(p["wt_amp_max"]) else
                                     "zayif" if wt <= int(p["wt_weak_max"]) else "yok")}
        if ciftler:
            durum = {c["bp"]["wt_status"] for c in ciftler}
            if durum == {"var"}:
                notes.append(t(
                    f"Delesyon küçük ({tr_sayi(D)} bp): normal alel de ürün verir. Normal alel uzun, "
                    f"delesyonlu alel {tr_sayi(D)} bp daha kısa bant verir; heterozigotta ikisi "
                    "birlikte görülür.",
                    f"The deletion is small ({D:,} bp): the normal allele also amplifies. "
                    f"The normal allele gives the longer band, the deleted allele a band "
                    f"{D:,} bp shorter; a heterozygote shows both."))
                if D < 20 or D < 0.08 * ciftler[0]["bp"]["wt"]:
                    notes.append(t(
                        "UYARI: İki bant arasındaki fark küçük; standart agaroz jelde zor "
                        "ayrılır. %3-4 agaroz, poliakrilamid ya da kapiller elektroforez kullanın.",
                        "WARNING: The difference between the two bands is small; it is hard "
                        "to resolve on a standard agarose gel. Use 3-4% agarose, "
                        "polyacrylamide or capillary electrophoresis."))
            else:
                ek_tr = ("" if kontrol_istendi else
                         " Heterozigot ile homozigot delesyonu ayırmak için kontrol primerini açın.")
                ek_en = ("" if kontrol_istendi else
                         " To tell heterozygous from homozygous deletions, turn on the control primer.")
                # Ciftlerin normal alel bandi farkli boylarda olabilir: bir kismi
                # sinirin altinda ("var"), bir kismi ustunde kalabilir. Metin hepsini
                # "sinirin ustunde" sayiyordu; 150 bp'lik delesyonda 673 bp'lik banda
                # (sinirin ALTINDA) da oyle deniyordu (2026-10-25).
                wt_boylar = [c["bp"]["wt"] for c in ciftler]
                wt_min, wt_max = min(wt_boylar), max(wt_boylar)
                aralik = (f"{wt_min:,}" if wt_min == wt_max else f"{wt_min:,}–{wt_max:,}")
                aralik_tr = (tr_sayi(wt_min) if wt_min == wt_max
                             else f"{tr_sayi(wt_min)}–{tr_sayi(wt_max)}")
                if "var" in durum:
                    notes.append(t(
                        f"Normal alel ürünü delesyon bölgesini de kapsadığı için uzun "
                        f"({aralik_tr} bp): bir kısmı ayarladığınız sınırın ({tr_sayi(sinir)} bp) "
                        "altında, bir kısmı üstünde kalıyor. Hangisi olduğu her çiftin "
                        "kartında yazıyor. Normal alel bandı çıkmadı diye örneği homozigot "
                        "saymayın." + ek_tr,
                        f"The normal-allele product also spans the deleted region, so it is "
                        f"long ({aralik} bp): some pairs fall below the limit you set "
                        f"({sinir:,} bp) and some above it. Each pair's card says which. Do "
                        "not call a sample homozygous just because the normal-allele band is "
                        "missing." + ek_en))
                elif "zayif" in durum:
                    notes.append(t(
                        f"Normal alel ürünü uzun ({aralik_tr} bp; iki primer arası {tr_sayi(D)} bp'lik "
                        "delesyon bölgesini de kapsıyor) ve ayarladığınız sınırın "
                        f"({tr_sayi(sinir)} bp) üstünde. Kısa kırılma noktası ürünü her hâlükârda "
                        "tercihli çoğalır; bu boyu çoğaltan bir protokolde normal alel bandı "
                        "da görülebilir. Normal alel bandı çıkmadı diye örneği homozigot "
                        "saymayın." + ek_tr,
                        f"The normal-allele product is long ({aralik} bp; the primers also span "
                        f"the {D:,} bp deleted region) and above the limit you set "
                        f"({sinir:,} bp). The short breakpoint product amplifies preferentially "
                        "in any case; with a protocol that covers this length the normal-allele "
                        "band may also be seen. Do not call a sample homozygous just because "
                        "the normal-allele band is missing." + ek_en))
                else:
                    notes.append(t(
                        f"Normal alelde iki primer arası {tr_sayi(D)} bp'lik delesyon bölgesini de "
                        f"kapsıyor; ürün ({aralik_tr} bp) ayarladığınız sınırın ({tr_sayi(sinir)} bp) "
                        "çok üstünde. Bu ayarla jelde yalnızca delesyonlu alelin kırılma "
                        "noktası bandını görmeyi bekleyin — bu boyu çoğaltan bir protokolde "
                        "normal alel de bant verir." + ek_tr,
                        f"On the normal allele the two primers also span the {D:,} bp deleted "
                        f"region; the product ({aralik} bp) is far above the limit you set "
                        f"({sinir:,} bp). With this setting expect to see only the deleted "
                        "allele's breakpoint band on the gel — with a protocol that covers "
                        "this length the normal allele gives a band too." + ek_en))
            if kontrol_istendi:
                if durum == {"var"}:
                    notes.append(t("Normal alel zaten bant verdiği için kontrol primeri gerekmedi.",
                                   "The normal allele already gives a band, so no control primer was needed."))
                else:
                    for c in ciftler:
                        # Silinen bolgenin basinda F ile; olmazsa sonunda R ile
                        k, neden = _bp_kontrol_ara(
                            assembly, chrom, c,
                            [("forward", start + m, end - m), ("reverse", start + m, end - m)],
                            (c["bp"]["mut_min"], c["bp"]["mut_max"]), p,
                            t("; silinen bölgenin iki ucu da denendi",
                              "; both ends of the deleted region were tried"))
                        c["control"] = k
                        c["control_reason"] = neden

    else:   # duplikasyon
        ic_bas, ic_bit = start + m, end - m      # kesin duplike bolge
        kucuk = D <= int(p["dup_small_max"])
        tandem_olur = ic_bit - ic_bas + 1 >= 2 * (dist + int(p["primer_max_size"]))
        # Dis primerlerle en kisa olasi duplike alel bandi: normal alel urunu en az
        # D + 2m + 2*dist + 2 primer, duplike alel bunun D + 2m fazlasi. ~700 bp
        # cogaltan laboratuvarda 600 bp'lik dup icin 1,7 kb'lik bant oneriliyordu;
        # dup dışa bakan primerlere yetecek kadar uzunsa birlesim bandi kisa kalir.
        kaydirma_bandi = (D + 2 * m + 2 * dist + 2 * int(p["primer_min_size"])) + D + 2 * m
        if kucuk and (kaydirma_bandi <= sinir or not tandem_olur):
            yaklasim = "size_shift"
            ga, sablon, kaynak = kes(start - m - flank, end + m + flank)
            if not sablon:
                raise PrimerError(t("Dizi çekilemedi.", "The sequence could not be retrieved."))
            sablon_boyu = len(sablon)
            hedef_bas = (start - m - dist) - ga
            hedef_bit = (end + m + dist) - ga
            if hedef_bas < int(p["primer_min_size"]) or hedef_bit > len(sablon) - int(p["primer_min_size"]):
                raise PrimerError(t("Duplikasyon kromozom ucuna çok yakın.",
                                    "The duplication is too close to the chromosome end."))
            taban = (hedef_bit - hedef_bas + 1) + 2 * int(p["primer_min_size"])
            # Dar tutulur: normal alel kisa kalirsa iki bant jelde daha net ayrilir
            # (+600'de primer3 kaliteye gore 1,1-1,3 kb'lik urunler seciyordu).
            # Duplike alel bandi (P3 + D + 2m) laboratuvar sinirini asmasin. Daralan
            # pencerede (100-220 bp dup, varsayilan 700 bp sinirda urun 436-500 bp'ye
            # sikisir) cift cikmazsa ya da pencere hic sigmiyorsa sinirsiz pencereyle
            # yeniden denenir (birlesim yolundaki _bp_baglanti_sinirli ile ayni mantik);
            # bandin siniri asabilecegini design_breakpoint sondaki uyari soyler.
            ust = min(taban + 350, sinir - D - 2 * m)
            pd_serbest = dict(p)
            pd_serbest["product_size_min"], pd_serbest["product_size_max"] = taban, taban + 350
            pd_serbest["pcr_max"] = max(sinir, taban + 350)
            if ust >= taban:
                pd_dar = dict(p)
                pd_dar["product_size_min"], pd_dar["product_size_max"] = taban, ust
                denemeler = [pd_dar, pd_serbest]
            else:
                denemeler = [pd_serbest]
            snps_toplam = _snp_template_offsets(
                _collect_snps(assembly, chrom, ga, ga + len(sablon) - 1, p), ga)
            haric = (_excluded_from_snps(snps_toplam, len(sablon))
                     if p.get("avoid_common_snps", True) else [])
            seq_args = {"SEQUENCE_ID": f"{chrom}_{start}_{end}_dup",
                        "SEQUENCE_TEMPLATE": sablon,
                        "SEQUENCE_TARGET": [hedef_bas, hedef_bit - hedef_bas + 1]}
            if haric:
                seq_args["SEQUENCE_EXCLUDED_REGION"] = haric
            for pd in denemeler:
                if haric:
                    seq_args["SEQUENCE_EXCLUDED_REGION"] = haric
                g = _build_global_args(pd)
                res = primer3.bindings.design_primers(seq_args, g)
                uygulandi = bool(haric)
                gevsetildi = False
                if haric and int(res.get("PRIMER_PAIR_NUM_RETURNED", 0)) == 0:
                    seq_args.pop("SEQUENCE_EXCLUDED_REGION")
                    res = primer3.bindings.design_primers(seq_args, g)
                    uygulandi = False
                    gevsetildi = bool(int(res.get("PRIMER_PAIR_NUM_RETURNED", 0)))
                sira = _rank_order(res, pd, template=sablon)
                if sira:
                    break
            if gevsetildi:
                notes.append(_snp_notu_gevsetildi(len(haric)))
            order = sira[:int(p["num_return"])]
            notes.extend(_suzgec_notlari(sira, pd, order))
            # Normal alelin urunu duplike bolgeyi icerir: girilen bolgenin kendisi isaretlenir
            ciftler = _collect_pairs(res, ga, order, pd, template=sablon, hedef=(start - ga, end - ga))
            _annotate_pair_snps(ciftler, res, order, snps_toplam)
            for c in ciftler:
                wt = c["product_size"]
                c["bp"] = {"wt": wt, "dup": wt + D, "dup_min": wt + D - 2 * m,
                           "dup_max": wt + D + 2 * m}
            notes.append(t(
                f"Duplikasyon küçük ({tr_sayi(D)} bp): dış primerler kullanıldı. Normal alel kısa, "
                f"duplike alel {tr_sayi(D)} bp daha uzun bant verir; heterozigotta ikisi birlikte "
                "görülür. İkinci bant yalnızca kopya yerinde (tandem) ise çıkar.",
                f"The duplication is small ({D:,} bp): outer primers were used. The normal "
                f"allele gives the shorter band, the duplicated allele a band {D:,} bp longer; "
                "a heterozygote shows both. The second band appears only if the copy is in "
                "place (tandem)."))
            if kontrol_istendi:
                notes.append(t("Normal alel bandı her örnekte çıktığı için kontrol primeri gerekmedi.",
                               "The normal-allele band appears in every sample, so no control "
                               "primer was needed."))
        else:
            yaklasim = "tandem_junction"
            if kucuk:
                notes.append(t(
                    f"Duplikasyon küçük ({tr_sayi(D)} bp) ama dış primerlerle duplike alel bandı en az "
                    f"{tr_sayi(kaydirma_bandi)} bp olurdu; çoğaltılabilen en uzun ürün {tr_sayi(sinir)} bp. "
                    "Bu yüzden dışa bakan primerlerle birleşim noktası çoğaltıldı (aşağıdaki "
                    "tandem notuna bakın).",
                    f"The duplication is small ({D:,} bp), but with outer primers the "
                    f"duplicated-allele band would be at least {kaydirma_bandi:,} bp; the longest "
                    f"amplifiable product is {sinir:,} bp. So the junction was amplified with "
                    "outward-facing primers (see the tandem note below)."))
            if not tandem_olur:
                raise PrimerError(t(
                    "Belirsizlik payı düşüldükten sonra kesin duplike bölge dışa bakan "
                    "primerler için çok kısa kalıyor. Payı küçültün.",
                    "After subtracting the uncertainty margin, the surely duplicated region "
                    "is too short for outward-facing primers. Reduce the margin."))
            yarim = min(flank, (ic_bit - ic_bas + 1) // 2)
            g1, s1, kaynak = kes(ic_bit - yarim + 1, ic_bit)       # F: bolgenin sonu
            g2, s2, _ = kes(ic_bas, ic_bas + yarim - 1)            # R: bolgenin basi
            sablon_boyu = len(s1) + len(s2)
            ciftler, res, snps_toplam, uygulandi, ek = _bp_baglanti_sinirli(
                assembly, chrom, [(g1, s1), (g2, s2)], p, dist, f"{chrom}_{start}_{end}_dup",
                4 * m, geo_min)
            notes += ek
            for c in ciftler:
                p3 = c["product_size"]
                c["bp"] = {"junction": p3 + 2 * m, "junction_min": p3, "junction_max": p3 + 4 * m}
            notes.append(t(
                "Tandem (ardışık, aynı yönlü) duplikasyon varsayıldı: primerler duplike "
                "bölgenin içinde, uçlara yakın ve DIŞA bakıyor. Normal genomda birbirinden "
                "uzağa baktıkları için ürün vermezler; duplikasyonda iki kopyanın birleşim "
                "yerinde yüz yüze gelip kısa bir ürün verirler. Ters yönlü ya da genomun "
                "başka bir yerine eklenmiş (insersiyonel) kopyayı YAKALAMAZ: negatif sonuç "
                "duplikasyonu dışlamaz. Heterozigot/homozigot ayrımı yapmaz.",
                "A tandem (adjacent, same-orientation) duplication was assumed: the primers "
                "sit inside the duplicated region, near its ends, facing OUTWARD. On a normal "
                "genome they face away from each other and give no product; in the "
                "duplication they meet at the junction of the two copies and give a short "
                "product. It does NOT detect inverted or insertional copies: a negative "
                "result does not exclude the duplication. It does not distinguish "
                "heterozygous from homozygous."))
            if kontrol_istendi:
                for c in ciftler:
                    # F (bolgenin sonunda, saga bakar) ile duplike bolgenin sagina; olmazsa R
                    # (bolgenin basinda, sola bakar) ile soluna. Iki yolda da kontrol primeri
                    # belirsizlik payinin disinda kalir.
                    k, neden = _bp_kontrol_ara(
                        assembly, chrom, c,
                        [("forward", end + m + 1, end + m + 1500),
                         ("reverse", max(1, start - m - 1500), start - m - 1)],
                        (c["bp"]["junction_min"], c["bp"]["junction_max"]), p,
                        t("; duplike bölgenin iki yanı da denendi",
                          "; both sides of the duplicated region were tried"))
                    c["control"] = k
                    c["control_reason"] = neden
            else:
                notes.append(t(
                    "Normal örnekte hiç bant çıkmayacağı için PCR'ın çalıştığını gösterecek "
                    "bir kontrol önerilir (kontrol primeri düğmesi).",
                    "Since a normal sample gives no band at all, a control showing that the "
                    "PCR worked is recommended (control primer option)."))

    if not ciftler:
        def n_baskin(metin):
            d = _explain_coz(metin)
            return d.get("considered", 0) and d.get("too many ns", 0) >= d["considered"] / 2
        if n_baskin(res.get("PRIMER_LEFT_EXPLAIN")) or n_baskin(res.get("PRIMER_RIGHT_EXPLAIN")):
            notes.append(t(
                "Kırılma noktasının yanı referans genomda boşluk (N) — sentromer, telomer ya da "
                "dizilenmemiş bir bölge. Burada primer tasarlanamaz; koordinatları kontrol edin.",
                "The sequence beside the breakpoint is a gap (N) in the reference genome — a "
                "centromere, telomere or unsequenced region. No primer can be designed here; "
                "check the coordinates."))
        elif yaklasim == "size_shift":
            # Boy farki yolunda urun penceresi dup boyuna gore motorca kurulur; kullanicinin
            # urun boyu araligi ya da payi pencereyi degistirmez (A4-02). Pencere sinirin
            # ustune cikarilarak da denendi; olculen: bu durumda primer kosullari (GC
            # araligi) belirleyici.
            notes.append(t(
                "Bu duplikasyon için dış primerlerle uygun çift bulunamadı. Ürün boyu penceresi "
                "çoğaltılabilen en uzun ürün sınırını aşacak kadar genişletilerek de denendi; bu "
                "yüzden payı küçültmek ya da ürün boyu aralığını genişletmek sonucu değiştirmez. "
                "Olası neden: bölgede primer koşullarına uyan aday az; primer GC aralığını "
                "(GC min / GC max) gevşetmeyi deneyin.",
                "No suitable pair was found with outer primers for this duplication. The product "
                "size window was also tried widened beyond the longest amplifiable product, so "
                "reducing the margin or widening the product size range does not change the "
                "result. Likely cause: few candidates in this region meet the primer conditions; "
                "try relaxing the primer GC range (GC min / GC max)."))
        else:
            notes.append(t(
                "Kırılma noktasının yakınında uygun primer bulunamadı. Belirsizlik payını "
                "küçültmek ya da gelişmiş ayarlardan ürün boyu aralığını genişletmek primerlerin "
                "aranabileceği bölgeyi büyütür.",
                "No suitable primer was found near the breakpoint. Reducing the uncertainty "
                "margin or widening the product size range under advanced settings enlarges the "
                "region where primers can be placed."))

    if ciftler:
        anahtar = "mut_max" if tip == "del" else ("junction_max" if yaklasim == "tandem_junction"
                                                    else "dup_max")
        en_uzun = max(c["bp"][anahtar] for c in ciftler)
        if m:
            notes.append(t(
                f"Kırılma noktaları ±{tr_sayi(m)} bp belirsiz kabul edildi: primerler olası tüm kırılma "
                "noktalarının güvenli tarafına kondu, bant boyları aralık olarak verildi. "
                "Gösterilen ürün dizisi en uç varsayıma göredir; gerçek kırılma noktası Sanger "
                "ile okunur.",
                f"The breakpoints were taken as uncertain by ±{m:,} bp: the primers were placed "
                "on the safe side of every possible breakpoint and band sizes are given as "
                "ranges. The product sequence shown follows the extreme assumption; the real "
                "breakpoint is read by Sanger."))
        if en_uzun > sinir:
            # Kuramsal ust sinir (primerler tam asgari boyda ve tam 'dist' uzakta olsa):
            # gercekte primer3 daha genis pencere ister, formul 20-40 bp fazla veriyordu
            # (116 onerilip 76-112 calisiyor; 200 bp dup'ta 16 onerilip hic cift yoktu).
            # Bu yuzden oneri motorun kendisiyle denenir (A4-01).
            if yaklasim == "size_shift":
                kuram = (sinir - 2 * D - 2 * dist - 2 * int(p["primer_min_size"])) // 4
            else:
                kuram = (sinir - geo_min) // 4
            pay_ok = None
            if m and not _oneri_ara:
                pay_ok = _bp_pay_ara(assembly, chrom, start, end, tip, params,
                                     min(kuram, m - 1), sinir)
            yuksek = f"{en_uzun:,}"
            if pay_ok:
                oneri_tr = (f" Belirsizlik payını ±{tr_sayi(pay_ok)} bp'ye indirince bu bölgede "
                            "sınırınıza sığan bir tasarım bulunuyor (motorla denendi); ya da "
                            "çoğaltılabilen en uzun ürün sınırını gelişmiş parametrelerden en az "
                            f"{tr_sayi(en_uzun)} bp'ye yükseltin.")
                oneri_en = (f" With the margin reduced to ±{pay_ok:,} bp a design that fits "
                            "your limit is found for this region (checked with the engine); or "
                            "raise the longest amplifiable product under advanced parameters "
                            f"to at least {yuksek} bp.")
            elif pay_ok == 0:
                oneri_tr = (" Yalnızca kırılma noktaları tam biliniyorsa (belirsizlik payı 0) bu "
                            "bölgede sınırınıza sığan bir tasarım bulunuyor (motorla denendi); "
                            "kırılma noktaları belirsizse çoğaltılabilen en uzun ürün sınırını "
                            f"gelişmiş parametrelerden en az {tr_sayi(en_uzun)} bp'ye yükseltin.")
                oneri_en = (" Only if the breakpoints are known exactly (margin 0) a design that "
                            "fits your limit is found for this region (checked with the "
                            "engine); if the breakpoints are uncertain, raise the longest "
                            f"amplifiable product under advanced parameters to at least {yuksek} bp.")
            elif m:
                oneri_tr = (" Payı küçültmek de bu bölgede sınırınıza sığan bir tasarım vermedi "
                            "(motorla denendi); çoğaltılabilen en uzun ürün sınırını gelişmiş "
                            f"parametrelerden en az {tr_sayi(en_uzun)} bp'ye yükseltin.")
                oneri_en = (" Reducing the margin did not give a design that fits your limit "
                            "for this region either (checked with the engine); raise the longest "
                            f"amplifiable product under advanced parameters to at least {yuksek} bp.")
            else:
                oneri_tr = (" Bu bölgede sınırınıza sığan bir tasarım bulunamadı; çoğaltılabilen "
                            "en uzun ürün sınırını gelişmiş parametrelerden en az "
                            f"{tr_sayi(en_uzun)} bp'ye yükseltin.")
                oneri_en = (" No design within your limit was found for this region; raise the "
                            "longest amplifiable product under advanced parameters to at least "
                            f"{yuksek} bp.")
            notes.append(t(
                f"UYARI: Bant {tr_sayi(en_uzun)} bp'ye kadar uzayabilir; çoğaltılabilen en uzun ürün "
                f"{tr_sayi(sinir)} bp." + oneri_tr,
                f"WARNING: The band may be up to {en_uzun:,} bp; the longest amplifiable "
                f"product is {sinir:,} bp." + oneri_en))

    _bolge_ekle(ciftler, assembly, chrom)
    return {
        "mode": "breakpoint",
        "input": {"assembly": assembly, "chrom": chrom, "start": start, "end": end,
                  "type": tip, "length": D, "margin": m, "control": kontrol_istendi,
                  "approach": yaklasim},
        "sequence_source": kaynak,
        "params_used": p,
        "template_length": sablon_boyu,
        "num_returned": len(ciftler),
        "pairs": ciftler,
        "notes": notes,
        "dbsnp": {
            "available": dbsnp.get_index(assembly) is not None,
            "in_template": len(snps_toplam),
            "excluded": len(snps_toplam) if uygulandi else 0,
            "applied": uygulandi,
        },
        "explain": {
            "left": res.get("PRIMER_LEFT_EXPLAIN", ""),
            "right": res.get("PRIMER_RIGHT_EXPLAIN", ""),
            "pair": res.get("PRIMER_PAIR_EXPLAIN", ""),
        },
    }


if __name__ == "__main__":
    import json
    # Hizli test: TP53 civarinda bir GRCh38 koordinati (chr17)
    out = design_primers("GRCh38", "17", 7676154, gene="TP53")
    print(json.dumps({k: v for k, v in out.items() if k != "pairs"},
                     indent=2, ensure_ascii=False))
    print(f"\n{out['num_returned']} cift bulundu (kaynak: {out['sequence_source']}).")
    for pr in out["pairs"][:3]:
        f, r = pr["forward"], pr["reverse"]
        print(f"\n--- Cift {pr['rank']} | ceza {pr['pair_penalty']} | "
              f"amplikon {pr['product_size']} bp "
              f"({pr['amplicon_genomic_start']}-{pr['amplicon_genomic_end']}) ---")
        print(f"  FWD 5'-{f['sequence']}-3'  Tm {f['tm']}  GC {f['gc']}%  "
              f"@{f['genomic_start']}-{f['genomic_end']}")
        print(f"  REV 5'-{r['sequence']}-3'  Tm {r['tm']}  GC {r['gc']}%  "
              f"@{r['genomic_start']}-{r['genomic_end']}")
