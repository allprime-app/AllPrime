# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""
AllPrime - Hazir Primer Degerlendirme
=======================================
Elde zaten olan bir primer ciftini inceler: tasarlamaz, DEGERLENDIRIR.

Tasarim modlarindan farki, cevaplamasi gereken sorunun farkli olmasi:
tasarimda "en iyi cifti bul", burada "bu cift ne yapar, nerede oturur,
neden calismiyor" sorulur.

En degerli kismi GEOMETRI TESHISI: iki primer genomda tam eslesse bile
birbirine SIRTINI DONMUSSE hicbir urun cikmaz. Bu durum pratikte sikca
gorulur (dizinin ters tumleyeni alinmis, roller karismis) ve klasik
araclarda acikca soylenmez - kullanici "neden bant yok" diye saatlerce
ugrasir. Burada dogrudan yazilir.
"""

import re

import primer3

import ayarlar
import specificity as S
import transcripts as T
import dbsnp
import engine
import par
from lang import t, tr_sayi

# Degerlendirme esikleri. Tasarim varsayilanlariyla ayni mantik:
# NCBI Primer-BLAST ile karsilastirilabilir legacy skorlar.
EVAL_DEFAULTS = {
    "max_product": 5000,        # bu boyun ustu standart PCR ile cogalmaz
    # Laboratuvarin cogaltabildigi en uzun urun: tasarim sekmeleriyle ayni ayar, arayuz
    # kayitli degeri gonderir. Uyari icindir; tarama penceresi max_product'tir.
    "pcr_max": engine.DEFAULTS["pcr_max"],
    "wide_product": 300000,     # geometri teshisi icin genis pencere
    "perfect_mismatch": 1,      # "tam oturuyor" sayilan ust sinir
    # Bir primer bu kadar yere TAM oturuyorsa bir tekrar dizisindedir (Alu/LINE,
    # uydu) ve karar "sorun" olur. 2-9 tam yer segmental duplikasyon/paralog
    # olabilir - "uyari". Olculen: normal primer 1, chr20 duplikasyonu 2,
    # Alu primeri 1022, chr7 uydu tekrari 8549 (2026-10-07).
    "repeat_perfect_sites": 10,
    "tm_min": 55.0, "tm_max": 65.0, "tm_diff_max": 3.0,
    "gc_min": 40.0, "gc_max": 60.0,
    "hairpin_warn": 45.0,       # °C - baglanma sicakligina yaklasirsa sorun
    # Legacy 3' self / 3' dimer skorlari (Primer-BLAST birimi). Tasarim 3'un
    # ustunu eler (NCBI varsayilani) ama hazir primerde bunu uyari yapmak alarm
    # yorgunlugu: tasarlanmamis siradan 20-merlerin %32'sinde 3' self > 3, ciftlerin
    # %7'sinde 3' dimer > 3 (1500 rastgele cift, 2026-10-10). Bu yuzden iki kademe:
    # tasarim sinirinin ustu "bilgi", 6+ "uyari" (primerlerin ~%4-10'u). Bozuk
    # primer panelindeki 3' palindrom / 3' tamamlayici ciftler 8 veriyordu.
    "end_info": 3.0,
    "end_warn": 6.0,
    "poly_x_warn": 5,
    # Ekson sinirina oturan primerde sinirin HER IKI yaninda en az bu kadar baz
    # olmali; 2-3 bazlik bir uc sarkabilir ve primer gDNA'ya yine baglanir.
    "junction_min_side": 4,
    "salt_monovalent": 50.0, "salt_divalent": 1.5,
    "dntp_conc": 0.6, "dna_conc": 50.0, "dmso_conc": 0.0,
}

# Tm'in hesaplandigi reaksiyon kosullari yanitta da durur: arayuz "Tm su kosullarla
# hesaplandi" notunu motorun KULLANDIGI degerlerle yazar (2026-10-31; sentez
# firmasinin "Basic" Tm'i 4-7 derece dusuk cikinca programin degeri yanlis sanildi).
TM_KOSULLARI = ("salt_monovalent", "salt_divalent", "dntp_conc", "dna_conc", "dmso_conc")

_GENE_IDX = {}      # assembly -> {chrom: [(start, end, gene, acc, strand), ...]}

# Bir cift urun verebilmek icin birinin '+' digerinin '-' yonde baglanmasi
# gerekir; hangisine "forward" dendigi PCR acisindan ONEMSIZDIR. Dolayisiyla
# R+F de tam gecerli bir urundur - yalnizca kullanicinin etiketleri ters.
# Bunu "urun yok" saymak CALISAN bir cifti bozuk gostermek olur.
GECERLI_CIFT = ("F+R", "R+F")


class EvaluateError(Exception):
    """Kullaniciya gosterilebilir degerlendirme hatasi."""
    pass


def _ayarlar(params):
    """EVAL_DEFAULTS + kullanici ayarlari, tip ve sinir denetimiyle. Eskiden oldugu
    gibi aktariliyordu: metin olarak gelen "5000" karsilastirmada 500 veriyordu."""
    return ayarlar.birlestir([EVAL_DEFAULTS], params, ayarlar.DEGERLENDIR_SINIRLARI,
                             EvaluateError)


# ------------------------------------------------------------------
# Gen / ekson baglami
# ------------------------------------------------------------------
def _gene_index(assembly):
    if assembly in _GENE_IDX:
        return _GENE_IDX[assembly]
    idx = T._load_index(assembly)
    mane = T._load_mane()
    per = {}
    for acc, rows in idx["by_acc"].items():
        tx = T._pick_mapping(rows, assembly)
        # refGene satirlari mane_status tasimaz (yalniz get_transcript kopyaya ekler);
        # "MANE oncelikli" gen yonu kurali bu yuzden hic calismiyordu (A5-01). MANE
        # dosyasi surumlu (NM_000546.6), refGene surumsuz: surumsuz akesyonla eslenir.
        # Ortak indeks degistirilmez: yalniz MANE olan satirin kopyasi isaretlenir.
        m = mane.get(acc)
        if m:
            tx = dict(tx)
            tx["mane_status"], tx["mane_acc"] = m
        c = engine.normalize_chrom(tx["chrom"])
        per.setdefault(c, []).append(tx)
    _GENE_IDX[assembly] = per
    return per


_MANE_SIRA = {"MANE Select": 0, "MANE Plus Clinical": 1}


def _mane_sirasi(tx):
    """MANE Select, sonra MANE Plus Clinical, sonra gen adi (deterministik)."""
    return (_MANE_SIRA.get(tx.get("mane_status"), 2), tx.get("gene") or "")


def _urun_geni_mane(assembly, chrom, bas, son):
    """Urunle ortusen genin adi ve okuma yonu ve MANE'li mi: (gen, "+"/"-", mane_var_mi).
    MANE transkripti varsa o esas alinir; ortusen genler farkli ipliklerdeyse yon
    belirsizdir -> (None, "?", mane_var_mi); ortusen gen yoksa (None, None, False)."""
    try:
        per = _gene_index(assembly)
    except Exception:
        return None, None, False
    ortusen = [tx for tx in per.get(engine.normalize_chrom(chrom), [])
               if tx["tx_start"] <= son and bas <= tx["tx_end"]]
    if not ortusen:
        return None, None, False
    mane = sorted((tx for tx in ortusen if tx.get("mane_status")), key=_mane_sirasi)
    if mane:
        # MANE transkriptleri de zit yonlu genlerden ise (PKD1 + TSC2 gibi) yon
        # belirsizdir; eskiden ilki sessizce secilirdi.
        if len({tx["strand"] for tx in mane}) > 1:
            return None, "?", True
        return mane[0]["gene"], mane[0]["strand"], True
    yonler = {tx["strand"] for tx in ortusen}
    if len(yonler) > 1:
        return None, "?", False
    return ortusen[0]["gene"], yonler.pop(), False


def _urun_geni(assembly, chrom, bas, son):
    """Urunle ortusen genin adi ve okuma yonu: (gen, "+"/"-") ya da (None, None).
    Ayrinti ve MANE onceligi icin bkz. _urun_geni_mane."""
    gen, yon, _mane = _urun_geni_mane(assembly, chrom, bas, son)
    return gen, yon


def _context(assembly, chrom, pos):
    """Bu konumda hangi gen var, ekson mu intron mu?"""
    out = {"genes": [], "region": None, "exon": None, "transcript": None}
    try:
        per = _gene_index(assembly)
    except Exception:
        return out
    genler, secili = set(), None
    for tx in per.get(engine.normalize_chrom(chrom), []):
        if tx["tx_start"] <= pos <= tx["tx_end"]:
            genler.add(tx["gene"])
            if secili is None or _mane_sirasi(tx)[0] < _mane_sirasi(secili)[0]:
                secili = tx
    out["genes"] = sorted(g for g in genler if g)
    if secili is not None:
        T._annotate_cdna(secili)
        idx = T.genomic_to_cdna(secili, pos)
        out["transcript"] = secili["acc"]
        if idx is None:
            out["region"] = "intron"
        else:
            out["region"] = "exon"
            out["exon"] = T.exon_number_of(secili, idx)
    return out


# ------------------------------------------------------------------
# Tek primer olcumleri
# ------------------------------------------------------------------
def _poly_run(seq):
    en = 1
    for m in re.finditer(r"(.)\1*", seq):
        en = max(en, len(m.group(0)))
    return en


def _primer_metrics(seq, p):
    s = seq.upper()
    gc = 100.0 * (s.count("G") + s.count("C")) / len(s)
    tm = primer3.calc_tm(s, mv_conc=p["salt_monovalent"], dv_conc=p["salt_divalent"],
                         dntp_conc=p["dntp_conc"], dna_conc=p["dna_conc"],
                         dmso_conc=p["dmso_conc"])
    # Legacy hizalama = NCBI Primer-BLAST ile ayni birim (tasarim tarafiyla tutarli)
    self_any = primer3.calc_homodimer(s).tm
    return {
        "sequence": s,
        "length": len(s),
        "tm": round(tm, 1),
        "gc": round(gc, 1),
        "hairpin_tm": round(primer3.calc_hairpin(s).tm, 1),
        "self_dimer_tm": round(self_any, 1),
        "gc_clamp": s[-1] in "GC",
        "gc_last5": sum(1 for c in s[-5:] if c in "GC"),
        "poly_x": _poly_run(s),
        "three_prime": s[-5:],
    }


LEGACY_MAKS_NT = 36     # primer3 legacy hizalamasinin kabul ettigi en uzun primer


def _legacy_skorlar(diziler):
    """Self / 3' self / primer-dimer skorlari, NCBI Primer-BLAST ile AYNI birimde
    (primer3 LEGACY hizalama; "check_primers" gorevi verilen primerleri oldugu gibi
    puanlar). Tasarim modu primerleri bu olcuyle eliyor; Degerlendir ise yalnizca
    termodinamik dimer Tm'ine bakiyordu ve o 3' uca kor: 3' uclari 8 baz
    tamamlayici iki primer 14-26 °C verip 45 °C esiginin cok altinda kaliyordu
    (2026-10-10 bozuk primer paneli: 3' primer-dimer 0/20 yakalandi). 30 ciftte
    bu fonksiyonun degerleri Primer-BLAST'in gosterdigiyle birebir ayni cikti.
    Doner: {"forward": {...}, "reverse": {...}, "pair": {...}} ya da None."""
    if any(len(s) > LEGACY_MAKS_NT for s in diziler.values()):
        return None
    seq = {"SEQUENCE_ID": "degerlendir", "SEQUENCE_PRIMER": diziler["forward"]}
    if "reverse" in diziler:
        seq["SEQUENCE_PRIMER_REVCOMP"] = diziler["reverse"]
    # Amac yalnizca puanlamak: hicbir primer elenmesin diye sinirlar genis
    g = {"PRIMER_TASK": "check_primers", "PRIMER_PICK_ANYWAY": 1,
         "PRIMER_THERMODYNAMIC_OLIGO_ALIGNMENT": 0,
         "PRIMER_THERMODYNAMIC_TEMPLATE_ALIGNMENT": 0,
         "PRIMER_MIN_SIZE": 5, "PRIMER_OPT_SIZE": 20, "PRIMER_MAX_SIZE": LEGACY_MAKS_NT,
         "PRIMER_MIN_TM": 0, "PRIMER_MAX_TM": 100, "PRIMER_MIN_GC": 0, "PRIMER_MAX_GC": 100,
         "PRIMER_MAX_POLY_X": 100, "PRIMER_MAX_SELF_ANY": 100, "PRIMER_MAX_SELF_END": 100,
         "PRIMER_PAIR_MAX_COMPL_ANY": 100, "PRIMER_PAIR_MAX_COMPL_END": 100,
         "PRIMER_PAIR_MAX_DIFF_TM": 100, "PRIMER_MAX_END_STABILITY": 100,
         # Aralik dar tutulmali: [36, 100000] verince cagri ~0,9 sn suruyordu (0,002 sn)
         "PRIMER_PRODUCT_SIZE_RANGE": [[LEGACY_MAKS_NT, 1000]]}
    try:
        r = primer3.design_primers(seq, g)
    except Exception:
        return None
    if not r.get("PRIMER_LEFT_NUM_RETURNED"):
        return None
    out = {"forward": {"self_any": r.get("PRIMER_LEFT_0_SELF_ANY"),
                       "self_end": r.get("PRIMER_LEFT_0_SELF_END")}}
    if "reverse" in diziler and r.get("PRIMER_RIGHT_NUM_RETURNED"):
        out["reverse"] = {"self_any": r.get("PRIMER_RIGHT_0_SELF_ANY"),
                          "self_end": r.get("PRIMER_RIGHT_0_SELF_END")}
        if r.get("PRIMER_PAIR_NUM_RETURNED"):
            out["pair"] = {"compl_any": r.get("PRIMER_PAIR_0_COMPL_ANY"),
                           "compl_end": r.get("PRIMER_PAIR_0_COMPL_END")}
    return out


def _legacy_ekle(sonuc, diziler):
    """Legacy skorlari primer/cift olcumlerine yaz (DNA ve RNA modu ortak)."""
    ls = _legacy_skorlar(diziler) or {}
    for ad, m in sonuc["primers"].items():
        m.update({"self_any": None, "self_end": None})
        m.update(ls.get(ad) or {})
    if sonuc["pair"] is not None:
        sonuc["pair"].update({"compl_any": None, "compl_end": None})
        sonuc["pair"].update(ls.get("pair") or {})


# ------------------------------------------------------------------
# Genomda yerlesim
# ------------------------------------------------------------------
def _best_sites(hits, label, assembly, p, limit=6, x_anahtar=None):
    """Doner: (en iyi N bolge, sayaclar). Sayaclar TAM listeden hesaplanir -
    kesilmis listeden saymak "6 yere oturuyor" gibi yaniltici sonuc veriyordu.
    Y'nin PAR'indaki, X'teki esiyle ayni isabet ("PAR ikizi") sayilmaz: GRCh38'de
    her PAR primeri boylece "2 ayri yere TAM oturuyor" uyarisi aliyordu."""
    bu = [h for h in hits if h[0] == label]
    bu.sort(key=lambda h: h[5])
    if x_anahtar is None:
        x_anahtar = par.yer_x_anahtari(hits)
    ikiz = [par.yer_ikizi_mi(assembly, h, x_anahtar) for h in bu]
    sayilan = [h for h, i in zip(bu, ikiz) if not i]
    sayac = {
        "total": len(sayilan),
        "perfect": sum(1 for h in sayilan if h[5] == 0),
        "good": sum(1 for h in sayilan if h[5] <= p["perfect_mismatch"]),
    }
    out = []
    for (_l, yon, chrom, bes, uc, mm), i in list(zip(bu, ikiz))[:limit]:
        ctx = _context(assembly, chrom, bes)
        # Tasarim tablosuyla AYNI etiket (ekzon 7 / intron 45 / sinir): eskiden intron
        # numarasiz "intron" donuyordu (kullanici hangi intron oldugunu goremedi, 2026-11-01).
        b = T.konum_bolgesi(assembly, chrom, min(bes, uc), max(bes, uc))
        out.append({
            "chrom": chrom, "five_prime": bes, "three_prime": uc,
            "orientation": yon, "mismatch": mm,
            "genes": ctx["genes"], "region": ctx["region"],
            "exon": ctx["exon"], "transcript": ctx["transcript"],
            "gene_region": engine.bolge_sozlugu(b, assembly) if b else None,
            "par_ikizi": i,
        })
    return out, sayac


def _hedef_coz(metin, assembly=None):
    """Istege bagli varyant konumu: 'chr19:11537002', '19:11537002-11537010',
    'NC_000019.10:11537002' ya da yalnizca koordinat. Doner: (kromozom ya da None, bas, bit);
    bos girdide None. Onek kurallari tasarim ucuyla aynidir (engine.konum_oneki,
    engine.erisim_surumu_denetimi): tanimsiz kromozom onegi ya da secili derlemeye uymayan RefSeq
    surumu acik hata verir (D1-02; eskiden onek sessizce atiliyor, hedef hicbir yerde
    isaretlenmiyordu)."""
    if metin in (None, ""):
        return None
    s = str(metin).strip()
    try:
        bas, bit = engine.varyant_araligi(s)
    except (engine.PrimerError, ValueError, TypeError):
        raise EvaluateError(t(
            f"Varyant konumu anlaşılamadı: {s[:40]} (örn. chr19:11537002; RNA modunda c.215).",
            f"Could not read the variant position: {s[:40]} (e.g. chr19:11537002; c.215 in RNA mode)."))
    krom = engine.konum_oneki(s)
    if krom is not None and krom not in engine._BILINEN_KROMOZOM:
        raise EvaluateError(t(
            f"Hedef konumdaki önek ({krom}) bir kromozom olarak tanınmadı. Değerlendirme yapılmadı; "
            "öneki silin ya da kromozomu \"chr17:\" biçiminde yazın.",
            f"The prefix of the target position ({krom}) was not recognised as a chromosome. No "
            "evaluation was made; remove the prefix or write the chromosome as \"chr17:\"."))
    try:
        engine.erisim_surumu_denetimi(s, assembly)
    except engine.PrimerError as e:
        # motorun mesaji tasarim ucu icin yazildi; burada degerlendirme yapilmiyor
        raise EvaluateError(str(e).replace("Tasarım yapılmadı.", "Değerlendirme yapılmadı.")
                            .replace("No design was made.", "No evaluation was made."))
    return krom, bas, bit


def _urun_dizileri(urunler, assembly, F, R, limit=8, max_bp=5000, hedef=None):
    """Ongorulen urunlerin GERCEK dizisini genomdan cek.

    Sadece kayda deger olanlar icin (ilki limit tanesi) ve makul boyda olanlar
    icin yapilir: 20 urunun hepsini cekmek istegi gereksiz yere yavaslatir.
    Primerlerin urun icindeki ofsetleri de verilir; yan urunlerde primer TAM
    oturmadigi icin dizi primerden farkli olabilir - gorulmesi gereken sey de
    zaten budur."""
    for o in urunler[:limit]:
        if o["size"] > max_bp:
            continue
        try:
            dizi, _kaynak = engine.get_sequence(assembly, o["chrom"],
                                                o["start"], o["end"])
        except Exception:
            continue
        if not dizi or len(dizi) != o["size"]:
            continue
        f_len = len(F if o["forward_primer"] == "F" else R)
        r_len = len(R if o["reverse_primer"] == "R" else F)
        gc = engine.amplikon_gc(dizi)
        o["amplicon"] = {
            "sequence": dizi,
            "length": len(dizi),
            "forward_span": [0, f_len - 1],
            "reverse_span": [len(dizi) - r_len, len(dizi) - 1],
            "gc_percent": gc,
            "gc_flag": engine.amplikon_gc_bayragi(gc),
            "gc_note": engine.amplikon_gc_notu(gc),
        }
        # Girilen konum bu urunun icindeyse arayuz o bazi isaretler (+ iplik ofseti)
        if hedef and hedef[0] in (None, engine.normalize_chrom(o["chrom"])):
            a, b = hedef[1] - o["start"], hedef[2] - o["start"]
            if b >= 0 and a < len(dizi):
                o["amplicon"]["variant_span"] = [max(0, a), min(len(dizi) - 1, b)]


def _geometry(f_sites, r_sites, p):
    """Urun cikmiyorsa NEDEN cikmadigini soyle. Asil deger burada."""
    if not f_sites or not r_sites:
        return None
    fi = f_sites[0]
    ri = r_sites[0]
    if fi["mismatch"] > p["perfect_mismatch"] or ri["mismatch"] > p["perfect_mismatch"]:
        return None
    if fi["chrom"] != ri["chrom"]:
        return {"kind": "farkli_kromozom", "f": fi, "r": ri,
                "mesaj": t(
                    f"Forward chr{fi['chrom']}, reverse chr{ri['chrom']} üzerinde oturuyor. "
                    "Farklı kromozomlarda oldukları için normal genomdan ürün veremezler; "
                    "ancak bir füzyon/translokasyon bağlantısı varsa ürün çıkabilir.",
                    f"Forward binds chr{fi['chrom']}, reverse chr{ri['chrom']}. Being on "
                    "different chromosomes they cannot amplify from a normal genome; a "
                    "product would only appear across a fusion/translocation junction.")}

    mesafe = abs(fi["five_prime"] - ri["five_prime"])
    # Urun icin: '+' yonlu primer DUSUK koordinatta, '-' yonlu YUKSEK koordinatta olmali
    if fi["orientation"] == ri["orientation"]:
        return {"kind": "ayni_yon", "f": fi, "r": ri, "distance": mesafe,
                "mesaj": t(
                    "İki primer de aynı yöne bakıyor (ikisi de aynı iplikten okunuyor). "
                    "Bir çiftin ürün vermesi için birinin ileri, diğerinin geri yönde "
                    "olması gerekir. Büyük olasılıkla birinin ters tümleyeni alınmamış.",
                    "Both primers point the same way (both read from the same strand). "
                    "A pair needs one forward and one reverse; most likely one of them "
                    "was not reverse-complemented.")}

    plus = fi if fi["orientation"] == "+" else ri
    minus = ri if fi["orientation"] == "+" else fi
    if plus["five_prime"] > minus["five_prime"]:
        return {"kind": "birbirinden_uzaga", "f": fi, "r": ri, "distance": mesafe,
                "mesaj": t(
                    f"İki primer birbirinden UZAĞA bakıyor ({tr_sayi(mesafe)} bp arayla). "
                    "Normal bir kromozomdan hiçbir koşulda ürün veremezler — aradaki "
                    "bölge silinse bile yönleri değişmez. Ürün ancak bölgenin yön "
                    "değiştirdiği bir yeniden düzenlenmede (inversiyon vb.) çıkar. "
                    "Delesyon hedefliyorduysanız dizilerin iplik yönünü gözden geçirin.",
                    f"The two primers point AWAY from each other ({mesafe:,} bp apart). "
                    "They cannot amplify from a normal chromosome under any circumstance — "
                    "deleting the region between them does not change their orientation. "
                    "A product appears only across a rearrangement that flips orientation "
                    "(e.g. an inversion). If you targeted a deletion, check the strand of "
                    "your sequences.")}

    urun = minus["five_prime"] - plus["five_prime"] + 1
    if urun > p["max_product"]:
        return {"kind": "cok_uzak", "f": fi, "r": ri, "distance": urun,
                "mesaj": t(
                    f"Primerler doğru yöne bakıyor ama araları {tr_sayi(urun)} bp. Standart PCR "
                    "ile bu uzunlukta ürün alınamaz. Aradaki bölgeyi kısaltan bir "
                    "delesyon varsa ürün çıkabilir (kırılma noktası testi mantığı).",
                    f"The primers face each other but are {urun:,} bp apart. A product "
                    "that long cannot be obtained by standard PCR. If a deletion shortens "
                    "the region a product can appear (breakpoint assay logic).")}
    return None


# ------------------------------------------------------------------
# Ana giris
# ------------------------------------------------------------------
PRIMER_MAKS_NT = 60     # primer3 termodinamik hizalamasinin ust siniri


def _temiz_diziler(forward, reverse=None):
    """Girilen dizileri temizle ve dogrula. Bosluk/rakam atilir (kopyala-yapistir
    dizilerinde konum numarasi sik gelir), U -> T cevrilir (RNA gosterimi).
    Kesme isareti ve tire de atilir: laboratuvarda primerler cogunlukla
    "5'-ACGT...-3'" diye yazilir ve bu yazim eskiden "yalnizca A/C/G/T" hatasiyla
    reddediliyordu (2026-10-10 testi). Rakamlar zaten atildigi icin 5'/3' de gider."""
    diziler = {}
    for ad, s in (("forward", forward), ("reverse", reverse)):
        if s is None or not str(s).strip():
            continue
        temiz = re.sub(r"[\s0-9'’′`\-–]", "", str(s)).upper().replace("U", "T")
        if not re.fullmatch(r"[ACGT]+", temiz):
            raise EvaluateError(t(
                f"{ad} dizisi yalnızca A/C/G/T içerebilir.",
                f"The {ad} sequence may only contain A/C/G/T."))
        if len(temiz) < 10:
            raise EvaluateError(t(f"{ad} dizisi çok kısa ({len(temiz)} nt).",
                                  f"The {ad} sequence is too short ({len(temiz)} nt)."))
        # primer3'un hairpin/dimer hesabi en fazla 60 baz kabul eder; daha uzunu
        # "Beklenmeyen hata" (500) veriyordu. Bu boyda bir dizi zaten primer
        # degildir - buyuk olasilikla yanlislikla uzun bir dizi yapistirilmistir.
        if len(temiz) > PRIMER_MAKS_NT:
            raise EvaluateError(t(
                f"{ad} dizisi çok uzun ({tr_sayi(len(temiz))} nt); primer en fazla "
                f"{PRIMER_MAKS_NT} nt olabilir. Primer yerine uzun bir dizi yapıştırılmış olabilir.",
                f"The {ad} sequence is too long ({len(temiz):,} nt); a primer can be at most "
                f"{PRIMER_MAKS_NT} nt. A long sequence may have been pasted instead of a primer."))
        diziler[ad] = temiz
    if "forward" not in diziler:
        raise EvaluateError(t("En az bir dizi gerekli.", "At least one sequence is required."))
    return diziler


# "Kopyadan yalnizca tek baz farki var - temkinli olun" notu (2026-11-09, kullanici onayi; prototip
# AllPrime-tarama/cikti/ekran/kopya_not_proto). Kullanici: "reverse'un 1 baz farkla tam oturmasi lazim,
# neden yok". Esik rozetin yuksek risk siniri (risk_high_max: toplam 2 fark).
YAKIN_CAPA_SINIR = 100      # 0-1 uyumsuz capa bundan coksa (tekrar dizisi) arama yapilmaz
ROL_URUN_SINIR = 30         # F/R rol karari icin gen aranan en cok urun (hedef + yan cift urunleri)
_TUM = str.maketrans("ACGTN", "TGCAN")


def _yakin_kopya(hits, F, R, assembly, max_product, hedef_yerleri=None):
    """Taramanin 3' kurali (son seed_len baz tam) yuzunden saymadigi ama yalnizca 1-2 baz farkla urun
    verebilecek yer. Ornek: CYP21A2 cifti (GRCh37) - R'nin CYP21A1P'deki yeri yalniz 3' son bazda farkli
    (primerin G'si karsisinda T), F kopyaya birebir; 514 bp'lik kopya urunu iki tabloda da yoktu.
    Capa: taramanin 0-1 uyumsuzla buldugu yerler. Cevrelerinde urun boyu kadar pencerede iki primer 3'
    kurali olmadan aranir (kopya._yakin_yerler, en cok risk_high_max uyumsuz). Urunun en az bir yeri 3'
    kurali yuzunden taramada yoktur (yoksa urun zaten listededir). Iki primerin kopya yeri de 3' kurali
    disinda kalirsa capa olmaz, bulunmaz (iki ayri 3' farki: daha guclu ayrim). Yalnizca bilgi: liste ve
    karar degismez. Doner: None ya da {chrom, start, end, size, combination, genes, total, count,
    sites: [{primer, orientation, mismatches: [{from_3p, primer_base, template_base}]}]}
    (template_base: primerin karsisindaki kalip bazi; from_3p: 1 = 3' son baz).

    hedef_yerleri: [(kromozom ya da None, bas, bit)] - hedef lokus ve cifte ait urunlerin yerleri.
    Bu yerlerle ortusen aday KOPYA degildir (hedefin kendisidir) ve elenir (A5-04: R'nin 3' ucunda yazim
    hatasi olan cifte hedefin kendisi "kopyadan tek baz farki" notu aliyordu). None ya da bos: hedef
    bilinmiyor (ne beklenen urun var ne en olasi cift urunu) - hangi yerin kopya oldugu soylenemez, not yok."""
    if not hedef_yerleri:
        return None
    import kopya            # kopya evaluate'i ice aktarmaz; dongu yok
    esik = int(S.SPEC_DEFAULTS["risk_high_max"])
    seed = int(S.SPEC_DEFAULTS["seed_len"])
    capalar = [h for h in hits if h[5] < esik]
    if not capalar or len(capalar) > YAKIN_CAPA_SINIR:
        return None
    araliklar = {}
    for _e, _y, kr, bes, uc, _mm in capalar:
        araliklar.setdefault(kr, []).append((max(1, min(bes, uc) - max_product), max(bes, uc) + max_product))
    pencereler = []
    try:
        for kr, liste in araliklar.items():
            birlesik = []
            for a, b in sorted(liste):
                if birlesik and a <= birlesik[-1][1] + 1:
                    birlesik[-1][1] = max(birlesik[-1][1], b)
                else:
                    birlesik.append([a, b])
            for a, b in birlesik:
                dizi, _kaynak = engine.get_sequence(assembly, kr, a, b)
                pencereler.append((kr, a, dizi.upper()))
    except Exception:
        return None             # pencere okunamadi (kromozom ucu vb.): not yok, karar degismez
    yerler = []                 # (etiket, primer, iplik, krom, lo, hi, [(uctan, primer_bazi, kalip_bazi)])
    for ad, etiket, s in (("forward", "F", F), ("reverse", "R", R)):
        boy, rc = len(s), s.translate(_TUM)[::-1]
        for (kr, iplik, bes) in kopya._yakin_yerler(s, pencereler, esik):
            lo, hi = (bes, bes + boy - 1) if iplik == "+" else (bes - boy + 1, bes)
            pk = next(((a, d) for k, a, d in pencereler if k == kr and a <= lo and hi < a + len(d)), None)
            if pk is None:
                continue
            d = pk[1][lo - pk[0]:hi - pk[0] + 1]
            if iplik == "+":    # primer + iplikle ayni; karsisindaki kalip - ipliktir
                fark = [(boy - x, s[x], d[x].translate(_TUM)) for x in range(boy) if d[x] != s[x]]
            else:               # primerin ters tumleyeni + iplikte; kalip + iplik
                fark = [(x + 1, rc[x].translate(_TUM), d[x]) for x in range(boy) if d[x] != rc[x]]
            yerler.append((etiket, ad, iplik, kr, lo, hi, sorted(fark)))
    disarida = lambda f: any(u <= seed for u, _p, _k in f)      # 3' kurali yuzunden taramada yok
    adaylar = {}
    for A in (y for y in yerler if y[2] == "+"):
        for B in (y for y in yerler if y[2] == "-" and y[3] == A[3]):
            boy = B[5] - A[4] + 1
            toplam = len(A[6]) + len(B[6])
            if not 0 < boy <= max_product or toplam > esik or not (disarida(A[6]) or disarida(B[6])):
                continue
            if any(k0 in (None, A[3]) and a0 <= B[5] and A[4] <= b0 for k0, a0, b0 in hedef_yerleri):
                continue            # hedefin kendisi: kopya degil
            # en tehlikelisi: en az fark, esitse 3' uca en yakin farki en uzakta olan (kopya_farki gibi)
            anahtar = (toplam, -min(u for u, _p, _k in A[6] + B[6]))
            k = (A[3], A[4], B[5])
            if k not in adaylar or anahtar < adaylar[k][0]:
                adaylar[k] = (anahtar, A, B, boy, toplam)
    if not adaylar:
        return None
    _a, A, B, boy, toplam = min(adaylar.values(), key=lambda v: v[0])

    def yer(Y):
        return {"primer": Y[1], "orientation": Y[2],
                "mismatches": [{"from_3p": u, "primer_base": pb, "template_base": kb} for u, pb, kb in Y[6]]}
    return {"chrom": A[3], "start": A[4], "end": B[5], "size": boy, "combination": f"{A[0]}+{B[0]}",
            "genes": sorted(_context(assembly, A[3], (A[4] + B[5]) // 2)["genes"]),
            "total": toplam, "count": len(adaylar), "sites": [yer(A), yer(B)]}


def evaluate(forward, reverse=None, assembly="GRCh38", params=None, hedef=None):
    p = _ayarlar(params)

    diziler = _temiz_diziler(forward, reverse)
    # Hedef konum en basta cozulur: gecersizse (tek primerde ya da genomsuz da) acik 400
    hedef_k = _hedef_coz(hedef, assembly)

    sonuc = {"assembly": assembly, "primers": {}, "pair": None,
             "sites": {}, "counts": {}, "products": [], "geometry": None,
             "genome_used": False, "findings": [], "near_copy": None,
             "params_used": {k: p[k] for k in TM_KOSULLARI}}

    for ad, s in diziler.items():
        sonuc["primers"][ad] = _primer_metrics(s, p)

    if len(diziler) == 2:
        F, R = diziler["forward"], diziler["reverse"]
        sonuc["pair"] = {
            "delta_tm": round(abs(sonuc["primers"]["forward"]["tm"] -
                                  sonuc["primers"]["reverse"]["tm"]), 1),
            "ta_suggested": engine.ta_onerisi(sonuc["primers"]["forward"]["tm"],
                                              sonuc["primers"]["reverse"]["tm"]),
            "hetero_dimer_tm": round(primer3.calc_heterodimer(F, R).tm, 1),
        }
    _legacy_ekle(sonuc, diziler)

    # --- genom analizi ---
    yol = engine.GENOME_PATHS.get(assembly, "")
    if yol:
        sonuc["genome_used"] = True
        F = diziler["forward"]
        R = diziler.get("reverse", F)
        sp = {"max_offtarget_product": p["max_product"], "report_limit": 30}
        sc = {**S.SPEC_DEFAULTS, **sp}
        try:
            hits = S.scan_genome(yol, F, R, sc)
        except S.SpecificityError as e:
            # Ornegin .fai yok: eskiden yakalanmiyor, 500 "Beklenmeyen hata" donuyordu
            raise EvaluateError(str(e))
        x_anahtar = par.yer_x_anahtari(hits)
        sonuc["sites"]["forward"], sonuc["counts"]["forward"] = \
            _best_sites(hits, "F", assembly, p, x_anahtar=x_anahtar)
        if "reverse" in diziler:
            sonuc["sites"]["reverse"], sonuc["counts"]["reverse"] = \
                _best_sites(hits, "R", assembly, p, x_anahtar=x_anahtar)

        # Kaynak siniri asildi mi? Tekrar dizisindeki bir primerin yer listesi
        # EKSIKTIR (bellek siniri); ondan urun tahmini yapmak yanlis guven verir.
        tasan = getattr(hits, "tasan", frozenset())
        toplam = getattr(hits, "toplam", None) or {}
        sonuc["overflow"] = {
            "forward": "F" in tasan,
            "reverse": "reverse" in diziler and "R" in tasan,
            "products": False,
            "product_limit": int(sc["max_products"]),
        }
        sonuc["site_totals"] = {"forward": toplam.get("F")}
        if "reverse" in diziler:
            sonuc["site_totals"]["reverse"] = toplam.get("R")

        urunler = None
        odak = None     # SNP'ye bakilacak urun: hedef, yoksa en olasi cift urunu
        if "reverse" in diziler and not (sonuc["overflow"]["forward"] or
                                         sonuc["overflow"]["reverse"]):
            limit = int(sc["max_products"])
            urunler = S.pair_products(hits, p["max_product"], limit=limit)
            if len(urunler) > limit:
                sonuc["overflow"]["products"] = True
                urunler = None
        if "reverse" in diziler and urunler is None:
            # Urun tahmini yapilmadi; sebebi bulgularda yazar. Arayuz bu durumda
            # "urun yok" DEMEMELI - yok degil, sayilamayacak kadar cok.
            sonuc.update({"product_count": None, "products": [], "products_low": 0,
                          "products_low_items": [], "products_low_truncated": False,
                          "products_truncated": False, "pair_product_count": None,
                          "side_product_count": None, "target_count": None,
                          "high_risk_count": None})

        if urunler is not None:
            hi, med = S.SPEC_DEFAULTS["risk_high_max"], S.SPEC_DEFAULTS["risk_medium_max"]
            for o in urunler:
                o["risk"] = ("yuksek" if o["mismatch_total"] <= hi else
                             "orta" if o["mismatch_total"] <= med else "dusuk")
            urunler.sort(key=lambda x: (x["mismatch_total"], x["size"]))
            # Y'nin PAR'indaki ikizler ayri lokus degil (bkz. par.py); isaretlenir,
            # listede kalir ama hicbir sayima girmez.
            par.urun_ikizleri(assembly, urunler)

            # HEDEF urunu isaretle. Kullanici bu cifti bir bolgeyi cogaltmak
            # icin tasarlamis; iki primerin de TAM oturdugu cift urunu hedeftir.
            # Onu "yuksek risk" diye kirmiziya boyamak yanlis - risk kavrami
            # ISTENMEYEN urunler icindir. Yalnizca tam eslesme (0 uyumsuzluk)
            # hedef sayilir; primerler hicbir yere tam oturmuyorsa hicbir sey
            # hedef ilan edilmez, o durum zaten ayrica uyari olarak bildiriliyor.
            #
            # Birden fazla tam eslesen urun varsa (segmental duplikasyon,
            # psodogen) HEPSI hedef adayidir. Eskiden ilki (en kisasi) "hedef",
            # birebir ayni kopyasi "yuksek risk" yaziliyordu - hangisinin
            # kastedildigini bilmeden birini secmek keyfiydi (chr20 vakasinda
            # iki es kopya, 2026-10-01). Bulgu, kopyalarin ayirt edilemedigini soyler.
            hedefler = [o for o in urunler
                        if o["combination"] in GECERLI_CIFT and o["mismatch_total"] == 0]
            for o in hedefler:
                o["intended"] = True
                o["risk"] = "hedef"
            hedefler = [o for o in hedefler if not o.get("par_ikizi")]
            sonuc["target_count"] = len(hedefler)
            odak = (hedefler or [o for o in urunler if o["combination"] in GECERLI_CIFT
                                 and not o.get("par_ikizi")] or [None])[0]

            # Yalnizca GERCEKTEN baglanabilecek urunler listelenir.
            # 3' uc sarti 6 baza inince arama penceresi genisledi; suzgec
            # olmadan yuzlerce "urun" cikip asil onemli olani gizler. Suzgec
            # uygulamanin kendi risk siniflandirmasi: dusuk risk = iki primerde
            # toplam 6+ uyumsuzluk, ki bu boyda bir primerde pratikte bant
            # vermez. Sayilari gizlemiyoruz - kac tanesinin elendigi soyleniyor.
            gosterilecek = [o for o in urunler if o["risk"] != "dusuk"]
            dusukler = [o for o in urunler if o["risk"] == "dusuk"]

            # Bulgular TAM listeden sayilir, 20 satirlik tablodan degil.
            # Bir primer tekrar dizisine (Alu vb.) dusunce yuzlerce F+F/R+R yan
            # urunu tabloyu dolduruyordu; bulgular o tablodan sayildigi icin
            # GERCEK F+R urunu varken "beklenen yonde hicbir urun vermiyor"
            # deniyor, "20 ayri urun" yaziyordu - 20 gosterim siniriydi, olculen
            # bir vakada gercek sayi 2 milyonu asiyordu (2026-10-01).
            cift = [o for o in gosterilecek if o["combination"] in GECERLI_CIFT]
            yan = [o for o in gosterilecek if o["combination"] not in GECERLI_CIFT]

            def say(liste):     # PAR ikizleri ayri lokus degil - sayilmaz
                return sum(1 for o in liste if not o.get("par_ikizi"))
            sonuc["pair_product_count"] = say(cift)
            sonuc["side_product_count"] = say(yan)
            # Hedef disindaki yuksek riskli urunler (cift + yan): kararin sertligi buna bagli
            sonuc["high_risk_count"] = say(o for o in gosterilecek if o["risk"] == "yuksek")
            # Roller hedef urunden okunur. Eskiden TUM cift urunlerine bakiliyordu:
            # hedef R+F iken baska bir yerde zayif bir F+R yan urunu varsa "roller
            # yer degismis" uyarisi susuyordu (2026-10-10 paneli, 1/20).
            temel = hedefler or cift
            # Laboratuvarda F/R GENIN okuma yonune gore adlandirilir. Eksi iplikteki
            # bir gende (TP53 gibi) dogru adlandirilmis cift genomda R+F gorunur;
            # eskiden buna "roller yer degismis" deniyordu - yayinlanmis 22 TP53
            # ciftinin 21'ine yanlis alarm (2026-10-28, test-verileri). Urun bir
            # genle ortusuyorsa beklenen yon o genin ipligine gore; gen yoksa
            # + iplik (eski davranis); ortusen genler zit yonluyse uyari yok.
            #
            # Rol karari GENIN KENDI lokusundaki urunden verilir (D1-04, 2026-11-10): psodogen
            # kopyasi ters yonluyse (PMS2/PMS2CL, NCF1/NCF1B-C) ters girilen cift kopyada
            # "beklenen" yonde gorunur ve eskiden TUM urunlere bakan all() uyariyi susturuyordu.
            # Genin kendi lokusu = MANE transkriptiyle ortusen urun (psodogenlerde MANE yok;
            # 0.8.42'deki MANE onceligiyle ayni olcut). Her urun kendi genin ipligine gore
            # degerlendirilir. MANE'li urun yoksa eski davranis (temel[0]'in geni, hepsine bak).
            gen = iplik = None
            kopya_roller = None
            mane_urunler = []
            for o in temel[:ROL_URUN_SINIR]:
                g, y, m = _urun_geni_mane(assembly, o["chrom"], o["start"], o["end"])
                if m and y != "?":
                    mane_urunler.append((o, g, y))
            if mane_urunler:
                o0, gen, iplik = mane_urunler[0]
                sonuc["pair_roles_swapped"] = all(
                    o["combination"] != ("F+R" if y in (None, "+") else "R+F") for o, _g, y in mane_urunler)
                sonuc["pair_first_size"] = o0["size"]
                # Genin kendi lokusu disindaki (kopya) urunler ters yonde oturuyorsa kisa not
                kendi = {id(o) for o, _g, _y in mane_urunler}
                farkli = [o for o in temel if id(o) not in kendi and not o.get("par_ikizi")
                          and o["combination"] != o0["combination"]]
                if farkli:
                    kopya_roller = {"count": len(farkli), "locus": f"chr{o0['chrom']}:{o0['start']:,}",
                                    "examples": [{"chrom": o["chrom"], "start": o["start"], "end": o["end"],
                                                  "combination": o["combination"]} for o in farkli[:3]]}
            else:
                if temel:
                    o0 = temel[0]
                    gen, iplik = _urun_geni(assembly, o0["chrom"], o0["start"], o0["end"])
                beklenen = "F+R" if iplik in (None, "+") else "R+F"
                sonuc["pair_roles_swapped"] = bool(temel) and iplik != "?" and all(
                    o["combination"] != beklenen for o in temel)
                sonuc["pair_first_size"] = temel[0]["size"] if temel else None
            sonuc["pair_gene"], sonuc["pair_gene_strand"] = gen, iplik
            sonuc["pair_roles_copies"] = kopya_roller

            # Tabloda once ciftin KENDI urunleri (hedef en basta, cunku listede
            # ilk tam eslesen F+R odur), sonra F+F/R+R. Kullanicinin ilk sorusu
            # "bu cift ne cogaltir"; yan urunlerin tam sayisi bulgularda yazar.
            gosterilecek = cift + yan
            dusukler = ([o for o in dusukler if o["combination"] in GECERLI_CIFT] +
                        [o for o in dusukler if o["combination"] not in GECERLI_CIFT])

            sonuc["product_count"] = say(urunler)
            sonuc["products"] = gosterilecek[:20]
            # Dusuk olasilikli urunler VARSAYILAN olarak listelenmez ama
            # ATILMAZ: kullanici isterse acabilsin diye ayri listede donulur.
            # "Gostermemek" ile "yok saymak" ayni sey degil.
            sonuc["products_low"] = say(dusukler)
            sonuc["products_low_items"] = dusukler[:100]
            sonuc["products_low_truncated"] = len(dusukler) > 100
            # Liste kesildiyse SOYLE: sessizce kirpmak "hepsi bu" izlenimi verir
            sonuc["products_truncated"] = len(gosterilecek) > len(sonuc["products"])
            _urun_dizileri(sonuc["products"], assembly, F, R, hedef=hedef_k)
            _urun_dizileri(sonuc["products_low_items"], assembly, F, R, hedef=hedef_k)
            if hedef_k:
                # Verilen konum hicbir urunun icinde degilse (baska kromozom, urun disi) sessiz kalinmaz
                # (D1-02): bulgu "target_info" ile soylenir. Dusuk olasilikli urunler sayilmaz.
                sonuc["target_info"] = {
                    "position": str(hedef).strip()[:40],
                    "in_product": any(
                        hedef_k[0] in (None, engine.normalize_chrom(o["chrom"]))
                        and hedef_k[1] <= o["end"] and o["start"] <= hedef_k[2] for o in gosterilecek)}
            # 3' kurali yuzunden listede olmayan ama yalnizca 1-2 baz farkla urun verebilecek yer (not)
            # Hedef lokus: tam eslesen urun(ler), yoksa gercekten baglanabilir (dusuk olmayan) F+R urunleri.
            # Bulunan aday bunlarla ortusuyorsa hedefin kendisidir, kopya degil (A5-04); hedef hic
            # bilinmiyorsa not verilmez. Tesadufi dusuk olasilikli bir F+R urunu hedef sayilmaz.
            bilinen = ([o for o in urunler if o.get("intended")] or
                       [o for o in urunler if o["combination"] in GECERLI_CIFT and o["risk"] != "dusuk"])
            hedef_yerleri = None
            if bilinen:
                hedef_yerleri = [(engine.normalize_chrom(o["chrom"]), o["start"], o["end"])
                                 for o in urunler if o["combination"] in GECERLI_CIFT]
                if hedef_k:
                    hedef_yerleri.append(hedef_k)
            sonuc["near_copy"] = _yakin_kopya(hits, F, R, assembly, int(p["max_product"]),
                                              hedef_yerleri=hedef_yerleri)

            # Urun yoksa NEDEN yok? Sadece gercek cift kombinasyonlarina bakilir:
            # bir F+F yan urunu varken de "cift neden calismiyor" sorusu
            # gecerlidir, teshis bastirilmamali.
            # Esik "guclu" urun (en fazla 2 uyumsuzluk): eskiden 3-5 uyumsuzluklu
            # ZAYIF bir yan urun bile teshisi bastiriyordu. R'nin ters tumleyeni
            # alinmamis ya da birbirinden uzaga bakan bir cift, genomun baska bir
            # yerinde rastlantisal zayif bir urun yuzunden "iyi" aliyordu
            # (2026-10-10 bozuk primer paneli: 2/40 vaka).
            guclu_fr = [o for o in urunler
                        if o["combination"] in GECERLI_CIFT and o["mismatch_total"] <= hi]
            if not guclu_fr:
                sonuc["geometry"] = _geometry(sonuc["sites"]["forward"],
                                              sonuc["sites"]["reverse"], p)

        # Odak urun (yoksa tek primerin en iyi yeri) psodootozomal bolgede mi?
        par_b, ikiz = None, False
        if odak:
            par_b = par.bolge(assembly, odak["chrom"], odak["start"], odak["end"])
            ikiz = any(o.get("par_ikizi") for o in urunler or [])
        elif sonuc["sites"].get("forward"):
            s0 = sonuc["sites"]["forward"][0]
            par_b = par.bolge(assembly, s0["chrom"], s0["five_prime"], s0["three_prime"])
            ikiz = any(x.get("par_ikizi") for x in sonuc["sites"]["forward"])
        if par_b:
            sonuc["par"] = {"ad": par_b["ad"], "ikiz_gorunuyor": ikiz}

        # baglanma bolgelerinde yaygin varyant
        ix = dbsnp.get_index(assembly)
        sonuc["dbsnp_uyari"] = dbsnp.bozuk_mu(assembly)
        sonuc["tablo_uyari"] = T.tablo_uyarisi(assembly, "degerlendir")
        if ix:
            for ad in sonuc["sites"]:
                for site in sonuc["sites"][ad]:
                    a, b = sorted((site["five_prime"], site["three_prime"]))
                    snps = ix.overlaps(site["chrom"], a, b)
                    site["snps"] = [{
                        "rsid": s["rsid"], "maf": s["maf"],
                        "distance_from_3p": engine.uc3_uzakligi(
                            site["three_prime"], s["position"], s["span"]),
                    } for s in snps]
            # Odak urunu olusturan baglanma yerleri: SNP bulgusu BURADAN okunur.
            # Eskiden "sites" listesinin ilk elemanina bakiliyordu; o liste en fazla
            # 6 yer tutuyor ve uyumsuzluga gore sirali. Primer birden cok yere tam
            # oturunca hedefin yeri listede ya hic yoktu ya da rastgele siradaydi;
            # hedef yokken de urunle ilgisiz bir tam eslesme yerinin SNP'si "sorun"
            # diye cikiyordu (2026-10-10 bozuk primer paneli).
            if odak:
                ad_of = {"F": "forward", "R": "reverse"}
                odak_snp = {}
                for etiket, yon in ((odak["forward_primer"], "+"), (odak["reverse_primer"], "-")):
                    ad = ad_of[etiket]
                    L = len(diziler[ad])
                    a, b = ((odak["start"], odak["start"] + L - 1) if yon == "+"
                            else (odak["end"] - L + 1, odak["end"]))
                    uc3 = b if yon == "+" else a
                    odak_snp.setdefault(ad, [])
                    for s in ix.overlaps(odak["chrom"], a, b):
                        if s["rsid"] not in {q["rsid"] for q in odak_snp[ad]}:
                            odak_snp[ad].append({"rsid": s["rsid"], "maf": s["maf"],
                                                 "distance_from_3p": engine.uc3_uzakligi(
                                                     uc3, s["position"], s["span"])})
                sonuc["focus_snps"] = odak_snp

    sonuc["findings"] = _findings(sonuc, p)
    sonuc["verdict"] = ("sorun" if any(f["level"] == "sorun" for f in sonuc["findings"])
                        else "uyari" if any(f["level"] == "uyari" for f in sonuc["findings"])
                        else "iyi")
    return sonuc


def _dizi_bulgulari(r, p, ekle):
    """Yalnizca DIZI ozelliklerine bakan bulgular (Tm, GC, hairpin, dimer...).
    Genomdan/transkriptten bagimsiz oldugu icin hem DNA hem RNA modunda ayni."""
    for ad, m in r["primers"].items():
        etiket = t("Forward", "Forward") if ad == "forward" else t("Reverse", "Reverse")
        if not (p["tm_min"] <= m["tm"] <= p["tm_max"]):
            ekle("uyari", f"{etiket} Tm {m['tm']} °C — önerilen aralık "
                          f"{p['tm_min']:.0f}-{p['tm_max']:.0f} °C dışında.",
                 f"{etiket} Tm {m['tm']} °C — outside the recommended "
                 f"{p['tm_min']:.0f}-{p['tm_max']:.0f} °C range.")
        if not (p["gc_min"] <= m["gc"] <= p["gc_max"]):
            ekle("uyari", f"{etiket} GC %{m['gc']} — önerilen aralık dışında.",
                 f"{etiket} GC {m['gc']}% — outside the recommended range.")
        if m["hairpin_tm"] >= p["hairpin_warn"]:
            ekle("uyari", f"{etiket} hairpin {m['hairpin_tm']} °C — bağlanma sıcaklığına "
                          "yakın, primer kendi üzerine katlanabilir.",
                 f"{etiket} hairpin {m['hairpin_tm']} °C — close to the annealing "
                 "temperature; the primer may fold on itself.")
        if m["poly_x"] >= p["poly_x_warn"]:
            ekle("uyari", f"{etiket} dizisinde {m['poly_x']} baz uzunluğunda homopolimer var.",
                 f"{etiket} contains a homopolymer run of {m['poly_x']} bases.")
        if not m["gc_clamp"]:
            ekle("bilgi", f"{etiket} 3' ucu G/C ile bitmiyor (GC clamp yok).",
                 f"{etiket} does not end in G/C (no GC clamp).")
        if m["gc_last5"] >= 4:
            ekle("uyari", f"{etiket} son 5 bazında {m['gc_last5']} adet G/C var — "
                          "3' uç fazla kararlı, yanlış yere oturma eğilimi artar.",
                 f"{etiket} has {m['gc_last5']} G/C in its last 5 bases — the 3' end is "
                 "too stable, which increases mispriming.")
        se = m.get("self_end")
        if se is not None and se >= p["end_warn"]:
            ekle("uyari", f"{etiket} 3' ucu kendine tamamlayıcı (3' self skoru {se:g}). İki "
                          "kopyası 3' uçlarından birbirine yapışıp uzayabilir — primer-dimer "
                          "bandı verebilir.",
                 f"{etiket} has a self-complementary 3' end (self 3' score {se:g}). Two "
                 "copies can anneal at their 3' ends and extend — this can give a "
                 "primer-dimer band.")
        elif se is not None and se > p["end_info"]:
            ekle("bilgi", f"{etiket} 3' self skoru {se:g} — tasarım sınırının "
                          f"({p['end_info']:g}) üstünde. Tek başına genellikle sorun "
                          "çıkarmaz; primer-dimer bandı görülürse önce buna bakın.",
                 f"{etiket} self 3' score {se:g} — above the design limit "
                 f"({p['end_info']:g}). On its own it rarely causes trouble; if a "
                 "primer-dimer band appears, check this first.")

    if r["pair"]:
        ce = r["pair"].get("compl_end")
        if ce is not None and ce >= p["end_warn"]:
            ekle("uyari", f"İki primerin 3' uçları birbirine tamamlayıcı (3' dimer skoru {ce:g}). "
                          "Birbirleri üzerinde uzayıp primer-dimer oluşturabilirler; jelde "
                          "50 bp'nin altında kısa bir bant görülebilir.",
                 f"The 3' ends of the two primers are complementary (3' dimer score {ce:g}). "
                 "They can extend on each other and form primer-dimers; a short band below "
                 "~50 bp may appear on the gel.")
        elif ce is not None and ce > p["end_info"]:
            ekle("bilgi", f"İki primerin 3' dimer skoru {ce:g} — tasarım sınırının "
                          f"({p['end_info']:g}) üstünde.",
                 f"The pair's 3' dimer score is {ce:g} — above the design limit "
                 f"({p['end_info']:g}).")
        if r["pair"]["delta_tm"] > p["tm_diff_max"]:
            ekle("uyari", f"İki primer arasında {r['pair']['delta_tm']} °C Tm farkı var; "
                          f"{p['tm_diff_max']:.0f} °C altında olması tercih edilir.",
                 f"The two primers differ by {r['pair']['delta_tm']} °C in Tm; "
                 f"below {p['tm_diff_max']:.0f} °C is preferred.")
        if r["pair"]["hetero_dimer_tm"] >= p["hairpin_warn"]:
            ekle("uyari", f"Primer-dimer {r['pair']['hetero_dimer_tm']} °C — iki primer "
                          "birbirine yapışıyor.",
                 f"Primer-dimer {r['pair']['hetero_dimer_tm']} °C — the two primers "
                 "stick to each other.")


# ------------------------------------------------------------------
# RNA / cDNA degerlendirmesi
# ------------------------------------------------------------------
# Neden ayri bir mod: ekson SINIRINA oturan bir primer genomda hicbir yerde
# butun halde bulunmaz (yarisi bir eksonda, yarisi digerinde, arada intron).
# DNA modunun genom taramasi boyle bir primer icin "hicbir yere oturmuyor,
# dizide hata olabilir" der - duapduz yanlis alarm. RNA modunda primerler
# transkriptin cDNA'si uzerinde aranir.
#
# 3' uc sarti ve uyumsuzluk butcesi genom taramasiyla AYNI ayardan okunur.
# Burada eskiden sabit 8 yaziyordu; genom taramasi 6'ya inince RNA modu geride
# kaldi: 3' ucundan 7-8. bazdaki tek uyumsuzluk DNA modunda gorunurken RNA
# modunda primer "bu transkriptte yok" sayiliyordu (2026-10-01 olculdu: 12
# rastgele transkriptte 0/12). Sayiyi kopyalamak yerine kaynagindan okumak,
# seed bir daha degisirse iki modun ayrismasini onler.


def _cdna_yerlesim(cdna, primer, yon, max_mm=None):
    """Primerin cDNA uzerindeki oturma yerleri.

    yon '+' : primerin AYNISI aranir (forward rolu)
    yon '-' : ters tumleyeni aranir (reverse rolu)

    3' uctaki son seed_len baz TAM eslesmek zorunda - polimeraz oradan uzatir,
    orasi tutmuyorsa primer baglansa bile urun cikmaz.
    Doner: [{"start", "end", "mismatch"}, ...] uyumsuzluga gore sirali (0-tabanli).
    """
    seed_len = int(S.SPEC_DEFAULTS["seed_len"])
    if max_mm is None:
        max_mm = int(S.SPEC_DEFAULTS["max_mismatch"])
    p = primer if yon == "+" else engine.revcomp(primer)
    seed = p[-seed_len:] if yon == "+" else p[:seed_len]
    lead = len(p) - seed_len
    out = []
    i = cdna.find(seed)
    while i != -1:
        start = (i - lead) if yon == "+" else i
        if start >= 0 and start + len(p) <= len(cdna):
            mm = sum(1 for a, b in zip(cdna[start:start + len(p)], p) if a != b)
            if mm <= max_mm:
                out.append({"start": start, "end": start + len(p) - 1, "mismatch": mm})
        i = cdna.find(seed, i + 1)
    out.sort(key=lambda h: (h["mismatch"], h["start"]))
    return out


def _sinir_bilgisi(tx, a, b):
    """Primer [a,b] araligi ekson sinirini kapsiyor mu, kapsiyorsa iki yanda
    kac baz kaliyor? Sinira 2-3 baz tasan primer gDNA'ya yine baglanir; ayirt
    edicilik icin iki yanda da yeterli baz olmali."""
    sinirlar = engine._junctions_within(tx, a, b)
    if not sinirlar:
        return {"spans_junction": False, "junctions": [], "five_side": None,
                "three_side": None}
    j = sinirlar[0]
    return {
        "spans_junction": True,
        "junctions": sinirlar,
        "five_side": j - a,          # sinirin solunda kalan baz sayisi
        "three_side": b - j + 1,     # sinirin sagina gecen baz sayisi
    }


def _cdna_konum(tx, a, b):
    """Bir primerin transkript uzerindeki konum ozeti."""
    d = {
        "cdna_start": a + 1, "cdna_end": b + 1,
        "exons": engine._primer_exons(tx, a, b),
        "genomic_start": T.cdna_to_genomic(tx, a),
        "genomic_end": T.cdna_to_genomic(tx, b),
    }
    d.update(_sinir_bilgisi(tx, a, b))
    return d


def evaluate_cdna(forward, reverse=None, acc="", assembly="GRCh38", params=None, hedef=None):
    """Hazir bir primer ciftini BELIRTILEN TRANSKRIPT uzerinde degerlendir.

    DNA modundan farki: aranan yer genom degil, transkriptin cDNA'sidir.
    Cevaplanan asil sorular:
      - primerler bu transkriptte gercekten var mi, hangi eksonlarda?
      - ekson sinirina oturuyorlar mi (gDNA'ya baglanmazlar - RT-PCR'da iyi)?
      - urun intron kapsiyor mu? Kapsamiyorsa gDNA kontaminasyonu AYNI bandi
        verir ve ayirt edilemez; bu RT-PCR'daki en sik gozden kacan hatadir.
    """
    p = _ayarlar(params)

    diziler = _temiz_diziler(forward, reverse)
    if not str(acc).strip():
        raise EvaluateError(t("Transkript kodu (NM_) gerekli.",
                              "A transcript accession (NM_) is required."))

    secilen = assembly
    assembly = engine.rna_derleme(secilen)      # RNA yolu: her zaman GRCh38 (K1)
    try:
        tx = T.get_transcript(str(acc).strip(), assembly)
    except T.TranscriptError as e:
        raise EvaluateError(str(e))
    T._annotate_cdna(tx)
    try:
        cdna, kaynak = engine.build_cdna(tx, assembly)
    except engine.PrimerError as e:
        raise EvaluateError(str(e))
    tx["kod_denetimi"] = engine.kod_denetimi(tx, assembly, cdna)
    tx["secilen_derleme"] = secilen

    # Hedef (c. konumu) EN BASTA cozulur: gecersizse tek primerde de cift primerdeki gibi
    # 400 (E1-02; eskiden yalniz cift urun olusunca cozuluyor, tek primerde sessizce
    # yok sayiliyordu). Yazilan referans baz transkriptle uyusmuyorsa bulgu eklenir (A2-01).
    h1 = h2 = None
    hedef_ref_uyari = None
    if hedef not in (None, ""):
        try:
            h1, h2, _ = T.parse_c_range(tx, str(hedef))
        except T.TranscriptError as e:
            raise EvaluateError(str(e))
        hedef_ref_uyari = T.c_referans_uyarisi(tx, str(hedef), cdna)

    sonuc = {
        "mode": "cdna", "assembly": assembly,
        "params_used": {k: p[k] for k in TM_KOSULLARI},
        "transcript": T.transcript_summary(tx),
        "sequence_source": kaynak,
        "primers": {}, "pair": None, "sites": {}, "placement": {},
        "product": None, "roles_swapped": False, "findings": [],
    }
    for ad, s in diziler.items():
        sonuc["primers"][ad] = _primer_metrics(s, p)
    if len(diziler) == 2:
        F, R = diziler["forward"], diziler["reverse"]
        sonuc["pair"] = {
            "delta_tm": round(abs(sonuc["primers"]["forward"]["tm"] -
                                  sonuc["primers"]["reverse"]["tm"]), 1),
            "ta_suggested": engine.ta_onerisi(sonuc["primers"]["forward"]["tm"],
                                              sonuc["primers"]["reverse"]["tm"]),
            "hetero_dimer_tm": round(primer3.calc_heterodimer(F, R).tm, 1),
        }
    _legacy_ekle(sonuc, diziler)

    # Her primeri IKI yonde de ara: rolleri ters takilmis olabilir (DNA modunda
    # da ayni durum var; orada R+F olarak goruluyor).
    for ad, s in diziler.items():
        sonuc["sites"][ad] = {
            "+": _cdna_yerlesim(cdna, s, "+"),
            "-": _cdna_yerlesim(cdna, s, "-"),
        }

    def _en_iyi(ad, yon):
        lst = (sonuc["sites"].get(ad) or {}).get(yon) or []
        return lst[0] if lst else None

    f_ileri = _en_iyi("forward", "+")
    r_geri = _en_iyi("reverse", "-") if "reverse" in diziler else None
    # Ters takilma: forward aslinda '-', reverse aslinda '+' yonde oturuyor
    f_geri = _en_iyi("forward", "-")
    r_ileri = _en_iyi("reverse", "+") if "reverse" in diziler else None

    ileri_ad, geri_ad = "forward", "reverse"
    if not (f_ileri and r_geri) and (f_geri and r_ileri):
        sonuc["roles_swapped"] = True
        ileri_ad, geri_ad = "reverse", "forward"
        ileri, geri = r_ileri, f_geri
    else:
        ileri, geri = f_ileri, r_geri

    for ad in diziler:
        yon = "+" if ad == ileri_ad else "-"
        h = _en_iyi(ad, yon)
        if h:
            sonuc["placement"][ad] = dict(_cdna_konum(tx, h["start"], h["end"]),
                                          mismatch=h["mismatch"], orientation=yon)
        else:
            sonuc["placement"][ad] = None

    if ileri and geri and geri["end"] >= ileri["start"]:
        a, b = ileri["start"], geri["end"]
        g1, g2 = T.cdna_to_genomic(tx, a), T.cdna_to_genomic(tx, b)
        sinirlar = engine._junctions_within(tx, a, b)
        urun_dizi = cdna[a:b + 1]
        urun_gc = engine.amplikon_gc(urun_dizi)
        sonuc["product"] = {
            "sequence": urun_dizi,
            # "length": amplikon gosterimi tasarim modlarindakiyle AYNI sozlesmeyi
            # bekliyor; cdna_size tek basina yeterli degil.
            "length": b - a + 1,
            "gc_percent": urun_gc,
            "gc_flag": engine.amplikon_gc_bayragi(urun_gc),
            "gc_note": engine.amplikon_gc_notu(urun_gc),
            # amplikon icinde 0-tabanli, kapsayici - arayuz primerleri isaretler
            "forward_span": [0, ileri["end"] - a],
            "reverse_span": [geri["start"] - a, b - a],
            # cDNA uzerindeki ekson sinirlari (amplikon ofsetine cevrilmis)
            "junction_offsets": [j - a for j in sinirlar],
            "cdna_size": b - a + 1,
            "cdna_start": a + 1, "cdna_end": b + 1,
            "exons": sorted(set(engine._primer_exons(tx, a, b))),
            "junctions": len(sinirlar),
            "gdna_size": (abs(g2 - g1) + 1) if (g1 and g2) else None,
            "genomic_start": min(g1, g2) if (g1 and g2) else None,
            "genomic_end": max(g1, g2) if (g1 and g2) else None,
        }
        # Girilen c. konumu urunun icindeyse arayuz o bazi isaretler
        if h1 is not None and h2 >= a and h1 <= b:
            sonuc["product"]["variant_span"] = [max(h1, a) - a, min(h2, b) - a]

    sonuc["findings"] = _findings_cdna(sonuc, p, tx)
    if hedef_ref_uyari:
        sonuc["findings"].insert(0, {"level": "uyari", "text": hedef_ref_uyari})
    sonuc["verdict"] = ("sorun" if any(f["level"] == "sorun" for f in sonuc["findings"])
                        else "uyari" if any(f["level"] == "uyari" for f in sonuc["findings"])
                        else "iyi")
    return sonuc


def _findings_cdna(r, p, tx):
    """RNA modu bulgulari."""
    out = []

    def ekle(level, tr, en):
        out.append({"level": level, "text": t(tr, en)})

    _dizi_bulgulari(r, p, ekle)
    acc = r["transcript"].get("acc", "")
    den = tx.get("kod_denetimi")
    if den and den["isaretli"]:            # kodlayan dizi tutarsiz: c. / ekson numarasi kayabilir (K1)
        out.append({"level": "uyari", "text": engine.kod_uyari_metni(tx, den, tasarim=False, onek=False)})
    dn = engine.rna_derleme_notu(tx.get("secilen_derleme") or r["assembly"])
    if dn:                                 # ustte GRCh37 secili: RNA GRCh38 kullandi
        out.append({"level": "bilgi", "text": dn})
    if tx.get("version_warning"):          # istenen NM surumu MANE'ninkinden farkli
        out.append({"level": "uyari", "text": tx["version_warning"]})
    if tx.get("locus_note"):               # NM_ birden cok yere hizalanmis, MANE konumu yok
        out.append({"level": "bilgi", "text": tx["locus_note"]})
    pb = par.bolge(r["assembly"], tx.get("chrom"), tx.get("tx_start") or 0, tx.get("tx_end") or 0)
    if pb:
        metin = par.not_metni(pb["ad"])
        ekle("bilgi", metin, metin)

    # 1) Primer bu transkriptte var mi?
    eksik = [ad for ad in r["primers"] if not r["placement"].get(ad)]
    for ad in eksik:
        etiket = "Forward" if ad == "forward" else "Reverse"
        ekle("sorun",
             f"{etiket} bu transkriptte ({acc}) hiçbir yere oturmuyor. Primer başka "
             "bir transkripte ait olabilir, dizisi yanlış yazılmış olabilir ya da "
             "ters tümleyeni alınmış olabilir.",
             f"{etiket} does not bind anywhere in this transcript ({acc}). It may "
             "belong to a different transcript, contain a typo, or have been "
             "reverse-complemented.")
    if eksik:
        return out

    if r["roles_swapped"]:
        ekle("uyari",
             "F ve R rolleri yer değişmiş: \"forward\" verdiğiniz primer transkriptin "
             "ters yönünde okunuyor. PCR açısından sorun değil ama kayıtlarınızda "
             "yanıltır; iki diziyi yer değiştirmeniz yeterli.",
             "The F and R roles are swapped: the primer you entered as \"forward\" "
             "reads in the reverse direction on the transcript. This does not affect "
             "the PCR but is misleading in your records; just swap the two sequences.")

    # 2) Uyumsuzluk
    for ad, yer in r["placement"].items():
        etiket = "Forward" if ad == "forward" else "Reverse"
        if yer and yer["mismatch"] > 0:
            ekle("uyari",
                 f"{etiket} bu transkripte {yer['mismatch']} uyumsuzlukla oturuyor "
                 "(tam eşleşmiyor). Dizide hata olabilir ya da primer başka bir "
                 "izoform için tasarlanmış olabilir.",
                 f"{etiket} binds this transcript with {yer['mismatch']} mismatches "
                 "(not a perfect match). There may be a typo, or the primer may have "
                 "been designed for a different isoform.")

    # 3) Ekson siniri uzerindeki primer: gDNA'ya baglanmaz - RT-PCR'da istenen sey
    for ad, yer in r["placement"].items():
        etiket = "Forward" if ad == "forward" else "Reverse"
        if not yer or not yer["spans_junction"]:
            continue
        bes, uc = yer["five_side"], yer["three_side"]
        kisa = min(bes, uc)
        if kisa >= int(p.get("junction_min_side", 4)):
            ekle("bilgi",
                 f"{etiket} ekson sınırının üzerine oturuyor ({bes}+{uc} baz). "
                 "Genomik DNA'ya bağlanamaz — kontaminasyon bu primerden ürün vermez.",
                 f"{etiket} sits across an exon junction ({bes}+{uc} bases). It cannot "
                 "bind genomic DNA, so contamination will not prime from it.")
        else:
            ekle("uyari",
                 f"{etiket} ekson sınırına oturuyor ama sınırın bir yanında yalnızca "
                 f"{kisa} baz var ({bes}+{uc}). Bu kadar kısa bir uç sarkabilir; primer "
                 "genomik DNA'ya yine de bağlanabilir, sınır özgüllüğüne güvenmeyin.",
                 f"{etiket} sits across an exon junction but only {kisa} bases fall on "
                 f"one side ({bes}+{uc}). Such a short overhang can still anneal, so the "
                 "primer may bind genomic DNA anyway — do not rely on junction specificity.")

    # Tek primer: urun, ekson siniri ve gDNA ayrimi sorulamaz; cift teshisi ("sirtlari donuk") konmaz.
    # DNA modu da tek primerde yalnizca primerin kendi ozelliklerini ve yerlesimini degerlendirir (A5-02).
    if len(r["primers"]) < 2:
        ekle("bilgi",
             "Yalnızca tek primer girildi; yalnızca kendi özellikleri ve yerleşimi değerlendirildi. "
             "Ürün, ekson sınırı ve gDNA ayrımı için reverse primeri de girin.",
             "Only one primer was entered, so only its own properties and placement were evaluated. "
             "Enter the second primer for the product, exon-junction and gDNA assessment.")
        return out

    # 4) Urun
    urun = r.get("product")
    if not urun:
        ekle("sorun",
             "Bu çift bu transkriptten ürün vermiyor: reverse primer forward'ın "
             "önünde yer alıyor, yani birbirlerine sırtları dönük. Dizilerin yönünü "
             "gözden geçirin.",
             "This pair gives no product from this transcript: the reverse primer lies "
             "upstream of the forward one, so they face away from each other. Check the "
             "orientation of your sequences.")
        return out

    if urun["cdna_size"] > p["pcr_max"]:
        ekle("uyari",
             f"cDNA ürünü {tr_sayi(urun['cdna_size'])} bp — sınırınızın üstünde (çoğaltılabilen en uzun "
             f"ürün: {tr_sayi(p['pcr_max'])} bp). Daha uzun ürün çoğaltan bir protokolde bu bant görülebilir.",
             f"The cDNA product is {urun['cdna_size']:,} bp — above your limit (longest amplifiable "
             f"product: {p['pcr_max']:,} bp). A protocol that amplifies longer products may show "
             "this band.")
    if urun.get("gc_note"):
        ekle("uyari" if urun.get("gc_flag") in ("yuksek", "cok_yuksek") else "bilgi",
             urun["gc_note"], urun["gc_note"])

    # 5) ASIL SORU: gDNA kontaminasyonu ayirt edilebilir mi?
    sinir = urun["junctions"]
    gd = urun["gdna_size"]
    sinir_ustu = any((r["placement"].get(a) or {}).get("spans_junction")
                     for a in r["placement"])
    en_az = int(p.get("junction_min_side", 4))
    sinir_saglam = any(y and y.get("spans_junction") and min(y["five_side"], y["three_side"]) >= en_az
                       for y in r["placement"].values())
    urun["gdna_none"] = sinir_saglam
    if sinir == 0 and not sinir_ustu:
        ekle("uyari",
             f"Ürün tek ekzonun içinde kalıyor (intron kapsamıyor). Genomik DNA "
             f"kontaminasyonu AYNI {tr_sayi(urun['cdna_size'])} bp'lik bandı verir ve jelde "
             "ayırt edilemez. RT eksi kontrolü şart; mümkünse primerlerden birini "
             "ekson sınırına taşıyın.",
             f"The product lies within a single exon (it spans no intron). Genomic DNA "
             f"contamination gives the SAME {urun['cdna_size']:,} bp band, which cannot "
             "be told apart on a gel. A no-RT control is essential; if possible move one "
             "primer onto an exon junction.")
    elif sinir_saglam:
        # Sinirin iki yaninda da yeterli bazi olan primer genomik DNA'ya baglanmaz (yukaridaki
        # 3. bulgu bunu zaten soyler): gDNA bandi icin boy yazmak onunla celisirdi. Bant yok;
        # arayuz "cogalmaz" yazar (urun["gdna_none"]; kullanici karari 2026-11-22).
        pass
    elif gd:
        if gd > p["max_product"]:
            ekle("bilgi",
                 f"Ürün {sinir} ekson sınırı kapsıyor. Genomik DNA'dan çıkacak bant "
                 f"{tr_sayi(gd)} bp olurdu — standart PCR ile çoğalmaz, yani kontaminasyon "
                 "bant vermez. RT-PCR için istenen durum.",
                 f"The product spans {sinir} exon junction(s). From genomic DNA the band "
                 f"would be {gd:,} bp — too long for a standard PCR, so contamination "
                 "produces no band. This is what you want for RT-PCR.")
        else:
            ekle("uyari",
                 f"Ürün {sinir} ekson sınırı kapsıyor ama aradaki intron(lar) kısa: "
                 f"genomik DNA'dan {tr_sayi(gd)} bp'lik bir bant da çıkar. İki bant jelde "
                 f"{tr_sayi(abs(gd - urun['cdna_size']))} bp farkla ayrılır — ayırt edilebilir "
                 "ama kontaminasyon yine de ürün verir.",
                 f"The product spans {sinir} junction(s) but the intron(s) are short: "
                 f"genomic DNA also gives a {gd:,} bp band. The two differ by "
                 f"{abs(gd - urun['cdna_size']):,} bp on a gel — distinguishable, but "
                 "contamination still amplifies.")
    return out


def _findings(r, p):
    """DNA modu bulgulari: seviye + metin. Sirali degil, arayuz seviyeye gore gosterir."""
    out = []

    def ekle(level, tr, en):
        out.append({"level": level, "text": t(tr, en)})

    _dizi_bulgulari(r, p, ekle)
    if r.get("dbsnp_uyari"):                 # indeks bozuk: SNP kontrolu yapilamadi
        out.append({"level": "uyari", "text": r["dbsnp_uyari"]})
    if r.get("tablo_uyari"):                 # refGene/MANE okunamadi: gen ve F/R yonu yok
        out.append({"level": "uyari", "text": r["tablo_uyari"]})

    if not r["genome_used"]:
        # "bilgi" degil "uyari": genoma bakilmadiysa "sorun yok" demek yaniltici olur,
        # cunku ozgulluk ve yerlesim hic kontrol edilmemistir.
        asm = r.get("assembly")
        if asm not in ("GRCh37", "GRCh38"):
            # Eskiden 'abc' icin de "yerel genom tanitilmadi" deniyordu (yanlis sebep)
            ekle("uyari", f"Genom sürümü tanınmıyor: '{asm}' (GRCh37 ya da GRCh38 olmalı). "
                          "Genom analizi yapılmadı; yalnızca dizi özellikleri değerlendirildi.",
                 f"Unknown genome build: '{asm}' (must be GRCh37 or GRCh38). No genome "
                 "analysis was done; only sequence properties were evaluated.")
        else:
            ekle("uyari", "Yerel genom tanıtılmadığı için genom analizi yapılmadı; "
                          "yalnızca dizi özellikleri değerlendirildi.",
                 "No local genome is configured, so no genome analysis was done; only "
                 "sequence properties were evaluated.")
        return out

    ov = r.get("overflow") or {}
    if r.get("par"):
        metin = par.not_metni(r["par"]["ad"], r["par"].get("ikiz_gorunuyor"))
        ekle("bilgi", metin, metin)
    for ad in ("forward", "reverse"):
        s = r["sites"].get(ad) or []
        etiket = "Forward" if ad == "forward" else "Reverse"
        if ad not in r["primers"]:
            continue
        if ov.get(ad):
            # Yer listesi bellek siniri yuzunden eksik; sayilar alt sinir.
            n = (r.get("site_totals") or {}).get(ad) or 0
            ekle("sorun", f"{etiket} genomda en az {tr_sayi(n)} yere bağlanıyor — poli-A ya da "
                          "Alu/LINE gibi bir tekrar dizisine denk geliyor. Bu primerle özgül "
                          "ürün beklenmez; ürün tahmini yapılmadı.",
                 f"{etiket} binds at least {n:,} places in the genome — it falls in poly-A "
                 "or an Alu/LINE-type repeat. No specific product can be expected; no "
                 "product prediction was made.")
            continue
        if not s:
            ekle("sorun", f"{etiket} bu genomda hiçbir yere oturmuyor. Dizi bu türe ait "
                          "olmayabilir ya da yazımında hata olabilir.",
                 f"{etiket} does not bind anywhere in this genome. The sequence may not "
                 "belong to this species, or it may contain a typo.")
            continue
        tam = [x for x in s if x["mismatch"] == 0]
        if not tam:
            ekle("uyari", f"{etiket} hiçbir yere TAM oturmuyor (en iyisi "
                          f"{s[0]['mismatch']} uyumsuz). Dizide hata olabilir.",
                 f"{etiket} matches nowhere perfectly (best is {s[0]['mismatch']} "
                 "mismatches). The sequence may contain an error.")
        c = r["counts"].get(ad, {})
        if c.get("perfect", 0) >= p["repeat_perfect_sites"]:
            ekle("sorun", f"{etiket} genomda {tr_sayi(c['perfect'])} ayrı yere TAM oturuyor — "
                          "büyük olasılıkla bir tekrar dizisinde (Alu/LINE vb.). Bu primerle "
                          "özgül ürün beklenmez.",
                 f"{etiket} matches perfectly at {c['perfect']:,} separate places — it "
                 "most likely sits in a repeat (Alu/LINE etc.). No specific product can "
                 "be expected with this primer.")
        elif c.get("perfect", 0) > 1:
            ekle("uyari", f"{etiket} genomda {c['perfect']} ayrı yere TAM oturuyor — "
                          "tek bir hedefe özgü değil.",
                 f"{etiket} matches perfectly at {c['perfect']} separate places — "
                 "it is not specific to a single target.")
        elif c.get("good", 0) > 1:
            ekle("bilgi", f"{etiket} en fazla {p['perfect_mismatch']} uyumsuzlukla "
                          f"{c['good']} yere oturuyor.",
                 f"{etiket} binds at {c['good']} places with at most "
                 f"{p['perfect_mismatch']} mismatches.")
        # SNP'ye ODAK urunu (hedef; yoksa en olasi urun) olusturan baglanma yerinde
        # bakilir - bkz. evaluate() "focus_snps". Cift urunu yoksa (tek primer,
        # urunsuz cift) en iyi baglanma yeri kullanilir.
        odak_snp = (r.get("focus_snps") or {}).get(ad)
        for snps in ([odak_snp] if odak_snp is not None else
                     [x.get("snps", []) for x in s[:1]]):
            for snp in snps:
                lv = "sorun" if snp["distance_from_3p"] <= 5 else "uyari"
                ekle(lv, f"{etiket} bağlanma bölgesinde yaygın varyant: {snp['rsid']} "
                         f"(MAF {dbsnp.maf_yaz(snp['maf'])}), 3' ucundan {snp['distance_from_3p']} baz. "
                         "Allel dropout riski.",
                     f"A common variant sits in the {etiket} binding site: {snp['rsid']} "
                     f"(MAF {dbsnp.maf_yaz(snp['maf'])}), {snp['distance_from_3p']} bases from the 3' end. "
                     "Risk of allele dropout.")

    if len(r["primers"]) < 2:
        # Tek primer (RNA kipindeki nota denk, F-08): ikinci primer yoksa urun ve cift
        # ozgullugu degerlendirilemez; "sorun gorunmuyor" tek basina eksik kalir.
        ekle("bilgi",
             "Yalnızca tek primer girildi; yalnızca kendi özellikleri ve genomdaki yerleşimi "
             "değerlendirildi. Ürün ve çift özgüllüğü için ikinci primeri de girin.",
             "Only one primer was entered, so only its own properties and genome placement were "
             "evaluated. Enter the second primer for the product and pair-specificity assessment.")

    if r["pair"]:
        if ov.get("forward") or ov.get("reverse"):
            return out          # urun tahmini yapilmadi; sebebi primer bulgusunda
        if ov.get("products"):
            lim = ov.get("product_limit") or 0
            ekle("sorun", f"Bu çift {tr_sayi(lim)}'den fazla olası ürün veriyor — primerler bir "
                          "tekrar bölgesinde. Özgül ürün beklenmez; ürün listesi çıkarılmadı.",
                 f"This pair gives more than {lim:,} possible products — the primers sit "
                 "in a repeat region. No specific product can be expected; the product "
                 "list was not produced.")
            return out

        # Sayimlar TAM listeden gelir (pair_product_count / side_product_count).
        # r["products"] 20 satira kirpilmis GOSTERIM listesidir; ondan saymak
        # tekrar dizisindeki bir primerde gercek urunu "yok" gosteriyordu.
        hedef = [o for o in r["products"] if o.get("intended")]
        n_hedef = r.get("target_count") or 0
        n_cift = r.get("pair_product_count", 0)
        n_yan = r.get("side_product_count", 0)
        n_yuksek = r.get("high_risk_count") or 0
        if r["geometry"]:
            ekle("sorun", r["geometry"]["mesaj"], r["geometry"]["mesaj"])
        elif not n_cift:
            ekle("sorun", "Bu çift beklenen yönde hiçbir ürün vermiyor.",
                 "This pair does not give any product in the expected orientation.")
        elif not n_hedef:
            # Iki primerin de TAM oturdugu bir urun yok, ama uyumsuzluklu urun(ler)
            # var. Eskiden bu durum sessizdi: liste yalnizca "orta risk" bir urun
            # gosteriyor, karar baska sebeplerden "iyi"/"uyari" olabiliyordu.
            ilk = next(o for o in r["products"] if o["combination"] in GECERLI_CIFT)
            hi = S.SPEC_DEFAULTS["risk_high_max"]
            fp, rp = ilk.get("forward_primer") or "F", ilk.get("reverse_primer") or "R"
            fm = ilk.get("mismatch_forward", "?")
            rm = ilk.get("mismatch_reverse", "?")
            yer = (f"chr{ilk['chrom']}:{ilk['start']:,}-{ilk['end']:,}, {ilk['size']:,} bp; "
                   f"{fp} {fm} + {rp} {rm}")
            yer_tr = (f"chr{ilk['chrom']}:{tr_sayi(ilk['start'])}-{tr_sayi(ilk['end'])}, "
                      f"{tr_sayi(ilk['size'])} bp; {fp} {fm} + {rp} {rm}")
            if ilk["mismatch_total"] <= hi:
                ekle("uyari",
                     f"İki primerin de tam oturduğu bir ürün yok. En olası ürün ({yer_tr} "
                     "uyumsuzluk) uyumsuzluklu bağlanmayla oluşuyor; dizide yazım hatası "
                     "olabilir, PCR verimi düşebilir.",
                     f"No product has both primers matching perfectly. The most likely product "
                     f"({yer} mismatches) forms through mismatched binding; the sequence may "
                     "contain a typo and PCR efficiency may drop.")
            else:
                ekle("sorun",
                     f"Bu çiftin tam ya da güçlü eşleşen bir ürünü yok; öngörülen ürünlerin "
                     f"hepsi zayıf (3-5 uyumsuzluklu) bağlanmalardan (en olası: {yer_tr} "
                     "uyumsuzluk). Bu çiftle ürün beklenmez.",
                     f"This pair has no perfectly or strongly matching product; all predicted "
                     f"products come from weak (3-5 mismatch) binding (most likely: {yer} "
                     "mismatches). No product should be expected from this pair.")
            if n_cift > 1:
                ekle("uyari", f"{tr_sayi(n_cift)} ayrı ürün çıkıyor — çift tek bir bölgeye "
                              "özgü değil.",
                     f"{n_cift:,} separate products are predicted — the pair is not "
                     "specific to a single region.")
        else:
            if n_hedef > 1:
                yerler = ", ".join(f"chr{o['chrom']}:{o['start']:,}" for o in hedef[:3])
                yerler_tr = ", ".join(f"chr{o['chrom']}:{tr_sayi(o['start'])}" for o in hedef[:3])
                ek_tr = f" ve {tr_sayi(n_hedef - 3)} yer daha" if n_hedef > 3 else ""
                ek_en = f" and {n_hedef - 3:,} more" if n_hedef > 3 else ""
                ekle("sorun",
                     f"Çift genomda {tr_sayi(n_hedef)} ayrı yerde TAM eşleşen ürün veriyor "
                     f"({yerler_tr}{ek_tr}). Bölge kopyalanmış (segmental duplikasyon / "
                     "psödogen): hangisinin hedef olduğu ayırt edilemez ve kopyalar "
                     "birlikte çoğalır; dizilemede kopyalar arasındaki farklar karışık "
                     "sinyal verir. Primerleri kopyalar arasında farklı olan bir bölgeye "
                     "kaydırın.",
                     f"The pair gives a perfectly matching product at {n_hedef:,} separate "
                     f"places ({yerler}{ek_en}). The region is duplicated (segmental "
                     "duplication / pseudogene): the intended copy cannot be told apart and "
                     "the copies co-amplify; in sequencing, differences between copies give "
                     "mixed signals. Move the primers to a region that differs between copies.")
            if n_hedef and n_yuksek:
                # Hedef varken ek GUCLU urun: jelde fazladan bant. Hedef yoksa
                # en iyi urun muhtemelen yazim hatali hedefin kendisidir; o durum
                # "tam oturmuyor" uyarisiyla zaten bildiriliyor, sertlestirilmez.
                hi = S.SPEC_DEFAULTS["risk_high_max"]
                ekle("sorun",
                     f"Hedefin yanında {tr_sayi(n_yuksek)} adet yüksek riskli yan ürün öngörülüyor "
                     f"(iki primerde toplam en fazla {hi} uyumsuzluk) — jelde ek bant beklenir.",
                     f"Besides the target, {n_yuksek:,} high-risk side products are predicted "
                     f"(at most {hi} mismatches across both primers) — expect extra bands on "
                     "the gel.")
            if n_cift > max(n_hedef, 1):
                ekle("uyari", f"{tr_sayi(n_cift)} ayrı ürün çıkıyor — çift tek bir bölgeye "
                              "özgü değil.",
                     f"{n_cift:,} separate products are predicted — the pair is not "
                     "specific to a single region.")

        if r.get("products_low"):
            ekle("bilgi",
                 f"{r['products_low']} adet bağlanma olasılığı düşük ürün "
                 "listelenmedi (iki primerde toplam 6 veya daha fazla uyumsuzluk; "
                 "bu boyda bir primerde pratikte bant vermez).",
                 f"{r['products_low']} products with low binding probability are not "
                 "listed (6 or more mismatches across the two primers; at this primer "
                 "length such a site does not give a band in practice).")
        if r.get("products_truncated"):
            ekle("bilgi",
                 f"Listelenecek ürün sayısı fazla; en kayda değer "
                 f"{len(r['products'])} tanesi gösteriliyor.",
                 f"There are more products to list; the {len(r['products'])} most "
                 "notable ones are shown.")

        # Hedef urunun GC icerigi: DMSO/betain karari icin (es kopyalar varsa
        # ayni not tekrarlanmasin diye yalnizca ilki)
        for o in hedef[:1]:
            amp = o.get("amplicon") or {}
            if amp.get("gc_note"):
                ekle("uyari" if amp.get("gc_flag") in ("yuksek", "cok_yuksek") else "bilgi",
                     amp["gc_note"], amp["gc_note"])

        # Butun gercek urunler R+F ise etiketler ters takilmis demektir.
        # PCR calisir (adlarla isi yoktur) ama kayitta ve iplik yonune bagli
        # islerde yanlis isimlendirme sorun cikarir; sessiz gecilmemeli.
        # Hedef urun laboratuvarin sinirini asiyor mu? Tasarim bu boydan uzun urun onermez, hazir
        # cift verilince de soylenmeli: yayinlanmis 647 ciftin 46'si 700 bp ustuydu, 8'ine "Sorun
        # gorunmuyor" deniyordu (2026-11-06). "Cogalmaz" denmez, sinir laboratuvarin protokoludur.
        ana = hedef[0] if hedef else next((o for o in r["products"] if o["combination"] in GECERLI_CIFT), None)
        if ana and ana["size"] > p["pcr_max"]:
            ekle("uyari",
                 f"Ürün {tr_sayi(ana['size'])} bp — sınırınızın üstünde (çoğaltılabilen en uzun ürün: "
                 f"{tr_sayi(p['pcr_max'])} bp). Daha uzun ürün çoğaltan bir protokolde bu bant görülebilir.",
                 f"The product is {ana['size']:,} bp — above your limit (longest amplifiable product: "
                 f"{p['pcr_max']:,} bp). A protocol that amplifies longer products may show this band.")

        if r.get("pair_roles_swapped") and r.get("pair_gene"):
            boy, gen = r["pair_first_size"], r["pair_gene"]
            yon_tr = "+ (düz)" if r["pair_gene_strand"] == "+" else "− (ters)"
            yon_en = "+ (forward)" if r["pair_gene_strand"] == "+" else "− (reverse)"
            ekle("uyari",
                 f"F ve R rolleri yer değişmiş: \"forward\" verdiğiniz primer {gen} geninin "
                 f"okuma yönünün tersine okuyor (gen {yon_tr} iplikte). PCR açısından "
                 f"sorun değil — çift {tr_sayi(boy)} bp'lik ürünü verir — ama kayıtlarınızda ve "
                 "iplik yönüne bağlı işlerde (dizileme primeri seçimi gibi) yanlış "
                 "isimlendirme yanıltır. İki diziyi yer değiştirmeniz yeterli.",
                 f"The F and R roles are swapped: the primer you entered as \"forward\" "
                 f"reads against the direction of {gen} (the gene is on the {yon_en} strand). "
                 f"This does not affect the PCR — the pair still gives a {boy:,} bp product — "
                 "but the mislabelling is misleading in your records and in strand-dependent "
                 "work (choosing a sequencing primer, for instance). Just swap the two "
                 "sequences.")
        elif r.get("pair_roles_swapped"):
            boy = r["pair_first_size"]
            ekle("uyari",
                 f"F ve R rolleri yer değişmiş: \"forward\" verdiğiniz primer ters "
                 f"iplikten, \"reverse\" verdiğiniz düz iplikten okunuyor. PCR açısından "
                 f"sorun değil — çift {tr_sayi(boy)} bp'lik ürünü verir — ama kayıtlarınızda ve "
                 "iplik yönüne bağlı işlerde (dizileme primeri seçimi gibi) yanlış "
                 "isimlendirme yanıltır. İki diziyi yer değiştirmeniz yeterli.",
                 f"The F and R roles are swapped: the primer you entered as \"forward\" "
                 f"reads from the reverse strand and vice versa. This does not affect the "
                 f"PCR — the pair still gives a {boy:,} bp product — but the mislabelling "
                 "is misleading in your records and in strand-dependent work (choosing a "
                 "sequencing primer, for instance). Just swap the two sequences.")

        ti = r.get("target_info")
        if ti and not ti["in_product"]:
            ekle("bilgi",
                 f"Verdiğiniz hedef konum ({ti['position']}) hiçbir üründe değil; işaretlenmedi. "
                 "Konumu ve derlemeyi kontrol edin.",
                 f"The target position you gave ({ti['position']}) is not in any product; it was not "
                 "marked. Check the position and the assembly.")

        kr = r.get("pair_roles_copies")
        if kr and r.get("pair_gene"):
            ekle("bilgi",
                 f"{tr_sayi(kr['count'])} kopya lokusta çift ters yönde oturuyor (örn. "
                 f"chr{kr['examples'][0]['chrom']}:{tr_sayi(kr['examples'][0]['start'])}); bu kopya lokuslarda F ve R "
                 f"rolleri {r['pair_gene']} lokusundakinin tersi görünür. F/R rol kararı {r['pair_gene']} "
                 f"lokusuna ({kr['locus'].replace(',', '.')}) göre verildi.",
                 f"At {kr['count']:,} copy loci the pair binds in the opposite orientation (e.g. "
                 f"chr{kr['examples'][0]['chrom']}:{kr['examples'][0]['start']:,}); at those copy loci the F and "
                 f"R roles look reversed relative to the {r['pair_gene']} locus. The F/R role decision was "
                 f"made from the {r['pair_gene']} locus ({kr['locus']}).")

        if n_yan:
            ekle("uyari", f"{tr_sayi(n_yan)} adet F+F / R+R yan ürünü öngörülüyor.",
                 f"{n_yan:,} F+F / R+R side products are predicted.")
    return out
