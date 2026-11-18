# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""
AllPrime - Psodootozomal bolgeler (PAR1 / PAR2)

X ve Y kromozomlarinin uclarindaki bu bolgelerin dizisi iki kromozomda BIREBIR
aynidir; erkekte X ve Y'den, kadinda iki X'ten - yani herkeste iki kopyadan -
cogalir ve otozomal gibi kalitilir (SHOX, CSF2RA, CRLF2, ASMT...).

Neden ayri modul: referans genomlar bu bolgeyi FARKLI temsil ediyor ve bu
uygulamanin kararlarini dogrudan etkiliyor (yerel Ensembl dosyalarinda
olculdu, 2026-10-11):
  - GRCh37: Y'nin PAR'i tamamen N ile maskeli -> urun yalnizca X'te gorunur.
  - GRCh38: Y'nin PAR'i maskeli DEGIL, dizi X ile ayni -> her PAR urunu hem X'te
    hem Y'de "tam eslesen urun" olarak cikiyor. Degerlendir bunu "bolge
    kopyalanmis, kopyalar ayirt edilemez" (sorun), ozgulluk taramasi "Y'de
    yuksek riskli yan urun" diye isaretliyordu - ikisi de yanlis alarm.

Sinirlar GRC'nin yayimladigi koordinatlar (1-tabanli, kapsayici). X ve Y
parcalarinin uzunluklari esit ve ayni yonde; bu yuzden es konum sabit bir
kaydirmayla bulunur (Ensembl GRCh37'de Y maskesinin sinirlari ve GRCh38'de iki
dizinin birebir esitligi ile dogrulandi).
"""

from lang import t

# assembly -> ad -> ((X bas, X son), (Y bas, Y son))
PAR = {
    "GRCh37": {"PAR1": ((60001, 2699520), (10001, 2649520)),
               "PAR2": ((154931044, 155260560), (59034050, 59363566))},
    "GRCh38": {"PAR1": ((10001, 2781479), (10001, 2781479)),
               "PAR2": ((155701383, 156030895), (56887903, 57217415))},
}


def _kr(chrom):
    c = str(chrom or "").strip()
    return c[3:] if c.lower().startswith("chr") else c


def bolge(assembly, chrom, start, end=None):
    """[start, end] bir PAR'a degiyor mu? Doner: {"ad", "kromozom"} ya da None."""
    k = _kr(chrom).upper()
    if k not in ("X", "Y"):
        return None
    end = start if end is None else end
    a, b = min(start, end), max(start, end)
    for ad, (xb, yb) in PAR.get(assembly, {}).items():
        lo, hi = xb if k == "X" else yb
        if a <= hi and b >= lo:
            return {"ad": ad, "kromozom": k}
    return None


def es_konum(assembly, chrom, pos):
    """PAR icindeki bir konumun diger kromozomdaki esi: ("X"|"Y", konum) ya da None."""
    k = _kr(chrom).upper()
    for (xa, xb), (ya, yb) in PAR.get(assembly, {}).values():
        if k == "X" and xa <= pos <= xb:
            return "Y", pos - xa + ya
        if k == "Y" and ya <= pos <= yb:
            return "X", pos - ya + xa
    return None


def urun_ikizleri(assembly, urunler):
    """Y'nin PAR'inda olup X'teki eslenigi AYNI uyumsuzlukla listede bulunan
    urunleri isaretle (o["par_ikizi"] = True). Bunlar ayri bir lokus degil, ayni
    dizinin ikinci temsilidir; sayimlara katilmamalidir. Doner: ikiz sayisi."""
    x_anahtar = {(o["combination"], o["mismatch_forward"], o["mismatch_reverse"],
                  o["start"], o["end"]) for o in urunler if _kr(o["chrom"]).upper() == "X"}
    n = 0
    for o in urunler:
        if _kr(o["chrom"]).upper() != "Y":
            continue
        a, b = es_konum(assembly, "Y", o["start"]), es_konum(assembly, "Y", o["end"])
        if a and b and (o["combination"], o["mismatch_forward"], o["mismatch_reverse"],
                        a[1], b[1]) in x_anahtar:
            o["par_ikizi"] = True
            n += 1
    return n


def yer_ikizi_mi(assembly, hit, x_anahtar):
    """Tarama isabeti (etiket, yon, kromozom, 5', 3', uyumsuzluk) Y'nin PAR'inda
    ve X'teki esi ayni etiket/yon/uyumsuzlukla var mi?"""
    etiket, yon, chrom, bes, _uc, mm = hit
    if _kr(chrom).upper() != "Y":
        return False
    e = es_konum(assembly, "Y", bes)
    return bool(e) and (etiket, yon, e[1], mm) in x_anahtar


def yer_x_anahtari(hits):
    return {(h[0], h[1], h[3], h[5]) for h in hits if _kr(h[2]).upper() == "X"}


def not_metni(ad, ikiz_gorunuyor=None):
    """Kullaniciya gosterilecek aciklama. ikiz_gorunuyor: Y esi referansta
    listelendiyse True, maskeli oldugu icin gorunmuyorsa False, bilinmiyorsa None."""
    tr = (f"Psödootozomal bölge ({ad}): bu bölgenin dizisi X ve Y kromozomlarında birebir "
          "aynıdır. Erkekte X ve Y'den, kadında iki X'ten — yani herkeste iki kopyadan — "
          "çoğalır ve otozomal gibi kalıtılır. Bu bir özgüllük sorunu değildir; sonucu "
          "X'e bağlı (hemizigot) bir gen gibi yorumlamayın.")
    en = (f"Pseudoautosomal region ({ad}): the sequence of this region is identical on the "
          "X and Y chromosomes. It amplifies from X and Y in males and from both X "
          "chromosomes in females — i.e. from two copies in everyone — and is inherited like "
          "an autosome. This is not a specificity problem; do not interpret the result as "
          "an X-linked (hemizygous) gene.")
    if ikiz_gorunuyor is True:
        tr += " Referans genomda Y'deki eşi de görünüyor; aynı lokus olarak sayıldı."
        en += " The Y copy also appears in the reference genome; it is counted as the same locus."
    elif ikiz_gorunuyor is False:
        tr += " Referans genomda Y'nin bu bölgesi maskeli olduğu için yalnızca X görünür."
        en += (" In the reference genome this part of Y is masked, so only the X copy "
               "is shown.")
    return t(tr, en)
