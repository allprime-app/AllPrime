# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda.
"""
AllPrime - Yakin-ozdes kopya olcumu (paralog.py tablosuna kayit uretir)

Kullanim (yerel GRCh38 genomu gerekir; GELISTIRME araci, uygulamayla calismaz):

    backend\\.venv\\Scripts\\python.exe backend\\paralog_olc.py PTEN IKBKG VWF

Neden ayri bir arac (2026-10-29 hata taramasi): paralog.py tablosunu ureten betik
depoda yoktu ve aday ciftleri yalnizca GEN ADI benzerliginden seciyordu. refGene'de
hic bulunmayan kopyalar (IKBKGP1, VWFP1, NF1'in chr21 kopyasi) bu yuzden hic
gorulmuyordu; PTENP1 ve HYDIN2 refGene'de oldugu halde tabloda yoktu. Olculdu:
bu 6 gende (PTEN, IKBKG, CHEK2, NF1, VWF, HYDIN) uyari cikmiyor ama tasarimin ilk
3 ciftinin 3'u de kopyadan 0-2 uyumsuzlukla urun veriyordu.

Yontem:
 1. Kopya ARAMA ada bagli degil: genin HER ekzonunun ortasindan 20 bazlik parca
    alinip genom taramasiyla (specificity.scan_genome) aranir. Genin disinda en az
    iki farkli parcanin <=2 uyumsuzlukla dustugu bolge aday kopyadir.
 2. EKZON DUZEYINDE olcum: her ekzonun dizisi (500 bp'den uzunsa 500'luk parcalar)
    kopya bolgesinde aranir (ortadaki 20-mer, iki yon) ve bulundugu yerden boyu
    boyunca kimlik hesaplanir; >= %90 ise o ekzonun kopyasi var. Gen govdesi
    yuzdesi kismi psodogeni gostermez: VWFP1 VWF'nin yalnizca ekzon 23-34'unu
    kopyalar, govdenin ~%3'u - ama o ekzonlardaki primer kopyadan birebir urun verir.
 3. 'dna' = gen govdesi 500 bp pencerelerinin homolog yuzdesi (paralog.py ile ayni).
 4. Kopyanin adi: bolgeyle kesisen refGene geni (yoksa 'kopya (chrN:x Mb)').
Cikti paralog.py PARALOGLAR satiridir; 6. alan etkilenen ekzon numaralari
(transkript sirasinda, MANE transkripti).
"""
import os
import sys

PENCERE = 500
KIMLIK = 0.90
PARCA = 20
PAY = 30_000              # kopya bolgesinin isabetlerin iki yanina genisletilmesi


def _rc(s):
    return s.translate(str.maketrans("ACGTN", "TGCAN"))[::-1]


def _homolog(w, bolge, bolge_rc):
    """w penceresinin kopya bolgesindeki en iyi ungapped kimligi >= KIMLIK mi?"""
    orta = len(w) // 2 - PARCA // 2
    parca = w[orta:orta + PARCA]
    if len(parca) < PARCA or "N" in parca:
        return False
    for hedef in (bolge, bolge_rc):
        i = hedef.find(parca)
        while i != -1:
            bas = i - orta
            if bas >= 0 and bas + len(w) <= len(hedef):
                k = hedef[bas:bas + len(w)]
                if sum(1 for a, b in zip(w, k) if a == b) >= KIMLIK * len(w):
                    return True
            i = hedef.find(parca, i + 1)
    return False


def olc(gen, assembly="GRCh38"):
    import engine
    import specificity as S
    import transcripts as T
    fa = engine.GENOME_PATHS[assembly]
    txs = T.find_by_gene(gen, assembly)
    tx = T.get_transcript(txs[0]["acc"], assembly)
    c = engine.normalize_chrom(tx["chrom"])
    govde = engine.get_sequence(assembly, c, tx["tx_start"], tx["tx_end"])[0].upper()
    eks = sorted(tx["exons"])
    sirali = eks if tx["strand"] == "+" else eks[::-1]          # ekzon 1 bastadir
    ekzon_dizi = [(n, govde[s - tx["tx_start"]: e - tx["tx_start"] + 1])
                  for n, (s, e) in enumerate(sirali, start=1)]

    # 1) kopya arama: her ekzonun ortasindan bir parca, ikiser ikiser taranir
    parcalar = []
    for _n, d in ekzon_dizi:
        if len(d) >= 40:
            m = len(d) // 2 - PARCA // 2
            p = d[m:m + PARCA]
            if "N" not in p:
                parcalar.append(p)
    parcalar = parcalar[:120]
    if len(parcalar) % 2:
        parcalar.append(parcalar[0])
    prm = dict(S.SPEC_DEFAULTS, max_mismatch=2)
    vurus = []
    for i in range(0, len(parcalar), 2):
        for h in S.scan_genome(fa, parcalar[i], parcalar[i + 1], prm):
            if h[5] > 2:
                continue
            no = i if h[0] == "F" else i + 1
            hc, hp = str(h[2]), min(h[3], h[4])
            if hc == c and tx["tx_start"] - 5000 <= hp <= tx["tx_end"] + 5000:
                continue                         # genin kendisi
            vurus.append((hc, hp, no))
    kumeler = []
    for hc, hp, no in sorted(vurus):
        if kumeler and kumeler[-1]["c"] == hc and hp - kumeler[-1]["son"] <= 300_000:
            kumeler[-1]["son"] = hp
            kumeler[-1]["parca"].add(no)
        else:
            kumeler.append({"c": hc, "bas": hp, "son": hp, "parca": {no}})
    kumeler = [k for k in kumeler if len(k["parca"]) >= 2]

    sonuc = []
    idx = T._load_index(assembly)
    for k in kumeler:
        a, b = max(1, k["bas"] - PAY), k["son"] + PAY
        bolge = engine.get_sequence(assembly, k["c"], a, b)[0].upper()
        bolge_rc = _rc(bolge)
        etkilenen = []
        for n, d in ekzon_dizi:
            if len(d) < 40:
                continue
            pencereler = [d[i:i + PENCERE] for i in range(0, len(d), PENCERE)]
            pencereler = [w for w in pencereler if len(w) >= 40]
            if pencereler and all(_homolog(w, bolge, bolge_rc) for w in pencereler):
                etkilenen.append(n)
        if not etkilenen:
            continue                              # rastlantisal tekrar isabeti
        gw = [govde[i:i + PENCERE] for i in range(0, len(govde), PENCERE)]
        gw = [w for w in gw if len(w) >= PENCERE // 2]
        dna = round(100.0 * sum(_homolog(w, bolge, bolge_rc) for w in gw) / len(gw), 1)
        ekz = round(100.0 * len(etkilenen) / sum(1 for _n, d in ekzon_dizi if len(d) >= 40), 1)
        adlar = {}
        for rows in idx["by_acc"].values():
            for r in rows:
                if engine.normalize_chrom(r["chrom"]) == k["c"] and r["tx_start"] <= b \
                        and a <= r["tx_end"] and r["gene"] and r["gene"].upper() != gen.upper():
                    adlar[r["gene"]] = adlar.get(r["gene"], False) or r["acc"].startswith("NM_")
        kok = [g for g in adlar if g.upper().startswith(gen.upper()[:3])]
        if kok:
            ad, kodlayan = kok[0], adlar[kok[0]]
        else:
            ad, kodlayan = f"kopya (chr{k['c']}:{k['bas'] / 1e6:.1f} Mb)", False
        sonuc.append((ad, k["c"], dna, ekz, kodlayan, tuple(etkilenen)))
    return sonuc


def main():
    for gen in sys.argv[1:]:
        for kayit in olc(gen):
            print(f'    "{gen}": ({kayit!r},),', flush=True)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("ALLPRIME_APP_ROOT", os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "AllPrime"))
    main()
