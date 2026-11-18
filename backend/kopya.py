# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""En iyi Ozgul cift: kurallara uyan BUTUN adaylarin genom taramasi (v0.8.36; once v0.8.34'te yalniz
psodogenli genlerde "kopyadan ayrisan ciftler").

Liste primer3'un ilk 1.000 adayindan secilir ve ozgulluk siralamaya girmez (kullanici karari: rozetler
yalnizca isaret, liste ve sirasi degismez). Olculdu (2026-11-08, 300 rastgele hedef, rapor-en-iyi-cift):
1. cift 57/298 hedefte Ozgul degildi, bunlarin 52'sinde Ozgul cift vardi; 13/298'de havuz kesimi daha iyi
skorlu cifti disarida birakiyordu. Kullanici karari (2026-11-09): "en iyi" = once Ozgul (3 kb icinde yuksek
ya da orta riskli yan urun yok), sonra bugunku skor; liste aynen kalir, en iyi Ozgul cift ayrica gosterilir.

Yontem (rozetler bittikten sonra, DNA modunda):
 1) tasarim aynen tekrarlanir; ayni girdiyle primer3'ten kurallara uyan butun ciftler istenir, _rank_order
    ile siralanir (havuz 1000 bu listenin primer3 sirasindaki onegidir; olculdu 338/338);
 2) butun farkli primerler tek geciste taranir (cok_tarama; check_pair ile birebir, olculdu);
 3) bugunku sirayla gidilir: ilk Ozgul cift en iyidir (psodogenli gende ilk 8'i, kopyadan farkiyla);
 4) hic Ozgul cift yoksa en az riskli 3 cift: once en az yuksek, sonra en az orta riskli yan urun.
Deneme siniri yoktur: aday sayisi ne olursa olsun hepsi taranir; ekranda "taranan N aday" yazar.
"""
import primer3

import engine
import specificity

PENCERE = 6000          # kopya bolgelerini gruplama adimi (bp)
PAY = 3000              # bolgenin iki yanina eklenen, yan urun boyuyla ayni
EN_COK_BOLGE = 40
TAM_LISTE = 500_000     # primer3'ten istenen aday: kurallara uyan butun ciftler (olculdu: en cok 54.365)
EN_COK_CIFT = 8         # psodogenli gende gosterilen Ozgul cift (ilki en iyisi)
ADAY = 3                # Ozgul cift yoksa gosterilen en az riskli cift

_NESIL = [0]            # her yeni arama ya da durdur() artirir; eski arama kendini birakir


class Iptal(Exception):
    """Arayuz aramayi birakti (yeni tasarim, otomatik kontrol kapatildi)."""


def durdur():
    """Yarim kalan arama yeni tasarimin rozetleriyle yarismasin."""
    _NESIL[0] += 1


def _yakin_yerler(primer, pencereler, en_cok):
    """Tohumsuz arama: primer pencerelerde en cok en_cok uyumsuzla nereye oturuyor. Primer
    en_cok + 1 parcaya bolunur; en az biri tam eslesmek zorunda (guvercin yuvasi), o parcalar
    aranir, adaylar tam karsilastirilir.
    Doner: {(krom, iplik, 5' koordinati): uyumsuz bazlarin 3' uctan sirasi (1 = son baz)}"""
    boy, n = len(primer), en_cok + 1
    adim = boy // n
    yerler = {}
    rc = specificity.revcomp_b(primer.encode("ascii")).decode("ascii")
    for iplik, s in (("+", primer), ("-", rc)):
        sb = s.encode("ascii")
        for j in range(n):
            parca = s[j * adim:(j + 1) * adim]
            for kr, bas, dizi in pencereler:
                i = dizi.find(parca)
                while i != -1:
                    a = i - j * adim
                    if a >= 0 and a + boy <= len(dizi):
                        yer = (kr, iplik, bas + a if iplik == "+" else bas + a + boy - 1)
                        if yer not in yerler:
                            d = dizi[a:a + boy].encode("ascii")
                            if specificity._mismatches(d, sb) <= en_cok:
                                yerler[yer] = sorted(boy - x if iplik == "+" else x + 1
                                                     for x in range(boy) if d[x] != sb[x])
                    i = dizi.find(parca, i + 1)
    return yerler


def kopya_farki(cift, pencereler, p, onbellek):
    """Bulunan cift kopyadan neyle ayrisiyor (yalnizca bilgi; sira ve "Ozgul" karari degismez).
    Tarama 3' son 6 bazi tam ister: kopyada o bazlardan birinde tek fark olan primer "isabet yok"
    sayilir. Burada o kural olmadan, taramanin diger olculeriyle (primer basina en cok 4, toplamda
    en cok 5 uyumsuz, 3 kb icinde bakisan) kopya bolgelerindeki en tehlikeli urun aranir: en az
    uyumsuzlu, esitse farki 3' uctan en uzak olan. Olculdu (2026-11-08): uyarili 15 hedefte
    bulunan ciftlerin cogu kopyadan tek primerin 3' bolgesindeki tek bazla ayrisiyor.
    Doner: None -> kopyada boyle urun yok; yoksa {chrom, start, size, fark: [{primer, uctan}]}
    (primer tasarim yonunde: forward = sol primer; uca yakin fark once)."""
    en_cok = int(p["max_mismatch"])
    yerler = []
    for ad in ("forward", "reverse"):
        s = cift[ad]["sequence"]
        if s not in onbellek:
            onbellek[s] = _yakin_yerler(s, pencereler, en_cok)
        yerler += [(ad, y, f) for y, f in onbellek[s].items()]
    beklenen = (cift["forward"]["genomic_start"], cift["reverse"]["genomic_end"])
    en_kotu = None
    for ad_a, (kr, ip, a), fa in yerler:
        if ip != "+":
            continue
        for ad_b, (kr_b, ip_b, b), fb in yerler:
            boy = b - a + 1
            if (ip_b != "-" or kr_b != kr or not 0 < boy <= int(p["max_offtarget_product"])
                    or len(fa) + len(fb) > int(p["risk_medium_max"]) or (a, b) == beklenen):
                continue
            fark = sorted([{"primer": ad_a, "uctan": u} for u in fa] + [{"primer": ad_b, "uctan": u} for u in fb],
                          key=lambda x: x["uctan"])
            anahtar = (len(fark), -(fark[0]["uctan"] if fark else 99))
            if en_kotu is None or anahtar < en_kotu[0]:
                en_kotu = (anahtar, {"chrom": str(kr), "start": a, "size": boy, "fark": fark})
    return en_kotu[1] if en_kotu else None


def _pencereler(T, ilk, assembly):
    """Kopya bolgeleri: ilk 10 ciftin yan urunlerinden (check_pair'in kendisi, isabetler tek gecisten)."""
    sayac = {}
    for x in ilk:
        try:
            d = T.check_pair(x["f"], x["r"], expected=x["e"], assembly=assembly)
        except specificity.SpecificityError:
            continue                    # tekrar dizisi: yan urun listesi yok
        for o in d["offtargets"]:
            y = (str(o["chrom"]), o["start"] // PENCERE)
            sayac[y] = sayac.get(y, 0) + 1
    pencereler = []
    for kr, adim in sorted(sayac, key=sayac.get, reverse=True)[:EN_COK_BOLGE]:
        a = max(1, adim * PENCERE - PAY)
        dizi, _kaynak = engine.get_sequence(assembly, kr, a, a + 2 * PENCERE + PAY - 1)
        pencereler.append((kr, a, dizi.upper()))
    return pencereler


def ara(assembly, chrom, position, gene=None, params=None):
    durdur()
    nesil = _NESIL[0]

    def iptal():
        if nesil != _NESIL[0]:
            raise Iptal()
    import cok_tarama           # numpy yalniz arama yapilinca yuklenir: motorun acilisi hizli kalir
    havuz = {}
    s = engine.design_primers(assembly, chrom, position, gene=gene, params=params, havuz=havuz)
    k = engine.normalize_chrom(s["input"]["chrom"])
    p = s["params_used"]
    sonuc = {"input": {"chrom": k}, "durum": "bos", "paralog": bool(s.get("paralog_var")),
             "taranan": 0, "tam": True, "havuz": int(p.get("dimer_pool", 0)), "bir": None,
             "pairs": [], "aday": []}
    if not s["pairs"]:
        return sonuc
    iptal()
    t0 = s["template_start"]
    rt = primer3.bindings.design_primers(havuz["seq_args"],
                                         dict(havuz["global_args"], PRIMER_NUM_RETURN=TAM_LISTE))
    st = engine._rank_order(rt, p, template=havuz["template"])
    sonuc["tam"] = int(rt.get("PRIMER_PAIR_NUM_RETURNED", 0)) < TAM_LISTE
    sonuc["taranan"] = len(st)

    def anahtar(r, i):
        return tuple(r[f"PRIMER_LEFT_{i}"]), tuple(r[f"PRIMER_RIGHT_{i}"])
    havuz_sira = {anahtar(havuz["res"], i): n for n, (i, _d, _t) in enumerate(havuz["sira"], 1)}
    X = []
    for n, (i, ds, top) in enumerate(st, 1):
        a, b, c, d = engine._primer_spans(rt, i)
        X.append({"sira": n, "havuz_sira": havuz_sira.get(anahtar(rt, i)), "f": rt[f"PRIMER_LEFT_{i}_SEQUENCE"],
                  "r": rt[f"PRIMER_RIGHT_{i}_SEQUENCE"], "e": {"chrom": k, "start": t0 + a, "end": t0 + d},
                  "spans": (t0 + a, t0 + b, t0 + c, t0 + d), "ceza": float(rt[f"PRIMER_PAIR_{i}_PENALTY"]),
                  "dimer": ds, "boy": int(rt[f"PRIMER_PAIR_{i}_PRODUCT_SIZE"]), "top": top})
    # ekrandaki 1. cift (havuzun 1.'si); tam listede bulunmazsa kartin kendisinden
    bir = next((x for x in X if x["havuz_sira"] == 1), None)
    if bir is None:
        q = s["pairs"][0]
        bir = {"f": q["forward"]["sequence"], "r": q["reverse"]["sequence"], "havuz_sira": 1, "sira": None,
               "e": {"chrom": k, "start": q["amplicon_genomic_start"], "end": q["amplicon_genomic_end"]},
               "ceza": q["pair_penalty"], "dimer": q["dimer_score"], "boy": q["product_size"], "top": q["total_score"]}
    primerler = {x["f"] for x in X} | {x["r"] for x in X} | {bir["f"], bir["r"]}
    T = cok_tarama.Tarama(engine.GENOME_PATHS[assembly], primerler, iptal=iptal)
    rb = T.risk(bir["f"], bir["r"], bir["e"], assembly)
    sonuc["bir"] = {"ozgul": bool(rb.get("specific")), "yuksek": rb.get("yuksek"), "orta": rb.get("orta"),
                    "hata": rb.get("hata")}

    def disari(x, risk=None):
        a, b, c, d = x["spans"]
        out = {"sira": x["sira"], "havuz_sira": x["havuz_sira"], "product_size": x["boy"],
               "forward": {"sequence": x["f"], "genomic_start": a, "genomic_end": b},
               "reverse": {"sequence": x["r"], "genomic_start": c, "genomic_end": d},
               "fark": {"ceza": round(x["ceza"] - bir["ceza"], 2), "dimer": round(x["dimer"] - bir["dimer"], 1),
                        "boy": x["boy"] - bir["boy"], "skor": round(x["top"] - bir["top"], 3)}}
        if risk:
            out["yuksek"], out["orta"] = risk["yuksek"], risk["orta"]
        return out

    # bugunku sirayla: ilk Ozgul cift O1'e gore en iyidir (sira toplam skora gore artan)
    istenen = EN_COK_CIFT if sonuc["paralog"] else 1
    bulunan = []
    for n, x in enumerate(X):
        if n % 100 == 0:
            iptal()
        if T.risk(x["f"], x["r"], x["e"], assembly, sadece_karar=True)["specific"]:
            bulunan.append(x)
            if len(bulunan) >= istenen:
                break
    if not bulunan:
        # en az riskli ADAY cift (yuksek, orta, skor); alt sinir (kendi urunleri) daha kotuyse hesaplanmaz
        enler = []
        for n, x in enumerate(X):
            if n % 100 == 0:
                iptal()
            if len(enler) >= ADAY and T.alt_sinir(x["f"], x["r"], x["e"], assembly) + (x["top"],) > enler[-1][0]:
                continue
            r = T.risk(x["f"], x["r"], x["e"], assembly)
            if r.get("hata"):
                continue
            enler.append(((r["yuksek"], r["orta"], x["top"]), x, r))
            enler.sort(key=lambda e: e[0])
            del enler[ADAY:]
        sonuc["durum"] = "yok"
        sonuc["aday"] = [disari(x, r) for _a, x, r in enler]
        return sonuc
    en = bulunan[0]
    if en["havuz_sira"] == 1:
        sonuc["durum"] = "bir"
        return sonuc
    sonuc["durum"] = ("k2" if sonuc["bir"]["ozgul"] else
                      "ilk10" if en["havuz_sira"] and en["havuz_sira"] <= len(s["pairs"]) else "disari")
    sonuc["pairs"] = [disari(x) for x in bulunan]
    if sonuc["paralog"] and sonuc["durum"] != "ilk10":
        ilk = [x for x in X if x["havuz_sira"] and x["havuz_sira"] <= len(s["pairs"])]
        pencereler = _pencereler(T, ilk, assembly)
        if pencereler:          # kopya bolgesi bilinmiyorsa fark da bilinmez (anahtar yok)
            onbellek = {}
            for c in sonuc["pairs"]:
                c["kopya"] = kopya_farki(c, pencereler, specificity.SPEC_DEFAULTS, onbellek)
    return sonuc
