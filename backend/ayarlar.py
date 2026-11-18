# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""
AllPrime - Ayar Dogrulama
==========================
Tasarim, ozgulluk ve Degerlendir ayni kurali kullanir: varsayilanlarin ustune
kullanici ayarlari konur, sayilar varsayilanin tipine cevrilir ve her sayi kendi
ALT/UST sinirina karsi denetlenir.

Neden sinir tablosu (olculdu 2026-10-28, TP53):
  - 'Primer (nM)' kutusuna 0, Na+'ya -10, primer boyuna 100 yazinca primer3'un
    ham Ingilizce mesajiyla 500 "Beklenmeyen hata" donuyordu (9 ayar).
  - Sessiz yanlislar: num_return=-5 -> 995 cift (Python'un negatif dilimi);
    negatif 'varyanta min uzaklik' koruma bolgesini 1 baza indiriyordu;
    ozgullukte max_mismatch=-1 hicbir yer bulmayip "ozgul" hukmu veriyordu.
  - Degerlendir'de metin olarak gelen sayi ("5000") tip donusumu olmadan
    karsilastirmada 500 veriyordu.

Ayri modul: engine, specificity ve evaluate'in ucu de kullaniyor; specificity
engine'i import etmez (bagimlilik yonu tek).
"""

import re

from lang import t

# Binlik ayiricili tam sayi: "1.500", "100,000", "1.500.000" (nokta ya da virgul, ardindan
# tam 3 rakamlik gruplar). Konum alanlariyla (engine._BINLIKLI) ayni kural; yalniz TAM SAYI
# varsayilanli ayarlara uygulanir: Na+ "1.5" gibi ondalik ayarlar etkilenmez.
_BINLIKLI_AYAR = re.compile(r"[0-9]{1,3}(?:([.,])[0-9]{3})(?:\1[0-9]{3})*")


class AyarHatasi(ValueError):
    """Kullaniciya gosterilebilir ayar hatasi (cagiran kendi hata sinifini verebilir)."""
    pass


# Arayuzde gorunen adlar (i18n.js 'adv.*' ile ayni). Tabloda olmayan ayar kendi
# adiyla anilir - API'den gelen ayarlar icin yeterli.
ETIKETLER = {
    "pcr_max": ("Çoğaltılabilen en uzun ürün (bp)", "Longest amplifiable product (bp)"),
    "product_min_gc": ("Ürün GC min (%)", "Product GC min (%)"),
    "product_max_gc": ("Ürün GC max (%)", "Product GC max (%)"),
    "product_size_min": ("Amplikon min (bp)", "Amplicon min (bp)"),
    "product_size_max": ("Amplikon max (bp)", "Amplicon max (bp)"),
    "min_dist_from_variant": ("Varyanta min uzaklık (bp)", "Min distance to variant (bp)"),
    "primer_min_size": ("Primer uzunluk min", "Primer length min"),
    "primer_opt_size": ("Primer uzunluk opt", "Primer length opt"),
    "primer_max_size": ("Primer uzunluk max", "Primer length max"),
    "primer_min_tm": ("Tm min (°C)", "Tm min (°C)"),
    "primer_max_tm": ("Tm max (°C)", "Tm max (°C)"),
    "primer_max_tm_diff": ("Tm farkı max (°C)", "Max Tm difference (°C)"),
    "primer_min_gc": ("GC min (%)", "GC min (%)"),
    "primer_max_gc": ("GC max (%)", "GC max (%)"),
    "primer_gc_clamp": ("GC clamp", "GC clamp"),
    "primer_max_end_gc": ("3' uçta en fazla G/C", "Max 3' G/C"),
    "primer_max_poly_x": ("Max homopolimer", "Max homopolymer"),
    "salt_monovalent": ("Na⁺ (mM)", "Na⁺ (mM)"),
    "salt_divalent": ("Mg²⁺ (mM)", "Mg²⁺ (mM)"),
    "dntp_conc": ("dNTP (mM)", "dNTP (mM)"),
    "dna_conc": ("Primer (nM)", "Primer (nM)"),
    "dmso_conc": ("DMSO (%)", "DMSO (%)"),
    "num_return": ("Sonuç sayısı", "Number of results"),
    "gap": ("Aradaki mesafe (bp)", "Distance between the sequences (bp)"),
    "bp_margin": ("Belirsizlik payı (bp)", "Uncertainty margin (bp)"),
}

# primer3'un derlenmis ust siniri (PRIMER_MAX_SIZE "exceeds built-in maximum of 36")
PRIMER3_MAKS_NT = 36

# --- Tasarim (engine) ---------------------------------------------------------
# Sinirlar KAPSAYICI. Tuz/primer konsantrasyonu primer3'te sifir olamaz (ham hata:
# "Illegal value for primer salt or dna concentration"); Mg2+ ve dNTP 0 olabilir.
# 'flank' bilerek yok: kendi kontrolu (design_primers) daha aciklayici mesaj veriyor.
TASARIM_SINIRLARI = {
    "product_size_min": (1, 100_000),
    "product_size_max": (1, 100_000),
    "pcr_max": (100, 100_000),                  # arayuzun set-pcr-max araligiyla ayni
    "product_min_gc": (0, 100),
    "product_max_gc": (0, 100),
    "primer_min_size": (1, PRIMER3_MAKS_NT),
    "primer_opt_size": (1, PRIMER3_MAKS_NT),
    "primer_max_size": (1, PRIMER3_MAKS_NT),
    "primer_min_tm": (0, 100),
    "primer_max_tm": (0, 100),
    "primer_max_tm_diff": (0, 100),
    "wt_tm_lt": (0, 100),
    "wt_tm_gt": (0, 100),
    "primer_min_gc": (0, 100),
    "primer_max_gc": (0, 100),
    "primer_gc_clamp": (0, 5),
    "primer_max_end_gc": (0, 5),
    "primer_max_poly_x": (0, PRIMER3_MAKS_NT),
    "salt_monovalent": (0.01, 10_000),
    "salt_divalent": (0, 1_000),
    "dntp_conc": (0, 1_000),
    "dna_conc": (0.01, 1_000_000),
    "dmso_conc": (0, 20),
    "min_dist_from_variant": (0, 10_000),
    "num_return": (1, 1_000),
    "dimer_pool": (1, 10_000),
    "w_self_end": (0, 100),
    "w_self_any": (0, 100),
    "w_compl_end": (0, 100),
    "w_compl_any": (0, 100),
    "dimer_scale": (0, 100),
    "prefer_short_product": (0, 10),
    "self3p_warn": (0, 100),
    "max_self_any": (0, 100),
    "max_self_end": (0, 100),
    "max_pair_compl_any": (0, 100),
    "max_pair_compl_end": (0, 100),
    "snp_min_maf": (0, 0.5),
    # RNA / ekson atlama
    "min_3p_overlap_junction": (1, PRIMER3_MAKS_NT),
    "min_5p_overlap_junction": (1, PRIMER3_MAKS_NT),
    "skip_margin": (0, 10_000),
    "skip_min_flank": (0, 50_000),
    "skip_max_flank": (0, 50_000),
    "skip_resolution_warn": (0, 100_000),
    "skip_ratio_warn": (0, 1),
    "skip_wt_long_product": (0, 100),
    # Serbest dizi ('gap' ust siniri tasarimda max_gap ile denetlenir; max_gap'in
    # kendisi yukseltilerek o sinir asilamasin)
    "gap": (0, 1_000_000),
    "max_gap": (0, 20_000),
    # Kirilma noktasi
    "bp_margin": (0, 1_000_000),
    "dup_small_max": (0, 1_000_000),
    "wt_amp_max": (1, 10_000_000),
    "wt_weak_max": (1, 10_000_000),
    "control_min_diff": (0, 100_000),
    "bp_min_dist": (0, 10_000),
}

# --- Ozgulluk (specificity) ----------------------------------------------------
OZGULLUK_SINIRLARI = {
    "seed_len": (4, PRIMER3_MAKS_NT),
    "max_mismatch": (0, 10),
    "max_offtarget_product": (1, 1_000_000),
    "max_sites_per_primer": (1, 10_000_000),
    "max_sites_per_task": (1, 10_000_000),
    "max_products": (1, 10_000_000),
    "workers": (0, 64),
    "chunk_bases": (100_000, 300_000_000),
    "report_limit": (1, 1_000),
    "risk_high_max": (0, 20),
    "risk_medium_max": (0, 20),
}

# --- Degerlendir (evaluate) ----------------------------------------------------
DEGERLENDIR_SINIRLARI = {
    "max_product": (1, 1_000_000),
    "pcr_max": (100, 100_000),                  # tasarimdaki sinirla ayni
    "wide_product": (1, 10_000_000),
    "perfect_mismatch": (0, 10),
    "repeat_perfect_sites": (1, 10_000_000),
    "tm_min": (0, 100),
    "tm_max": (0, 100),
    "tm_diff_max": (0, 100),
    "gc_min": (0, 100),
    "gc_max": (0, 100),
    "hairpin_warn": (0, 100),
    "end_info": (0, 100),
    "end_warn": (0, 100),
    "poly_x_warn": (1, 100),
    "junction_min_side": (0, PRIMER3_MAKS_NT),
    "salt_monovalent": (0.01, 10_000),
    "salt_divalent": (0, 1_000),
    "dntp_conc": (0, 1_000),
    "dna_conc": (0.01, 1_000_000),
    "dmso_conc": (0, 20),
}


def _ad(k):
    e = ETIKETLER.get(k)
    return t(e[0], e[1]) if e else k


def _yaz(x):
    """Sinirlari okunur yaz: 100000 -> 100.000 / 100,000; 0.01 -> 0,01 / 0.01."""
    if float(x).is_integer():
        return t(f"{int(x):,}".replace(",", "."), f"{int(x):,}")
    return t(f"{x:g}".replace(".", ","), f"{x:g}")


def birlestir(tabanlar, params, sinirlar=None, hata=AyarHatasi):
    """Varsayilanlarin ustune kullanici ayarlarini koy; TIPLERINI ve SINIRLARINI
    dogrula. Yalnizca kullanicinin verdigi ayarlar denetlenir (varsayilanlar
    zaten sinir icinde). Hata durumunda 'hata' sinifi firlatilir.

    Tipler: varsayilan bool ise "1/true/on/yes/evet" kabul edilir; sayi ise
    float'a cevrilip (NaN / sonsuz reddedilir) varsayilanin tipine getirilir
    ("12" -> 12). Varsayilani olmayan anahtarlar oldugu gibi gecer."""
    sinirlar = sinirlar or {}
    p = {}
    for tb in tabanlar:
        p.update(tb)
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise hata(t("Ayarlar (params) anahtar-değer biçiminde olmalı.",
                     "Settings (params) must be a key-value object."))
    for k, v in params.items():
        if v is None:
            continue
        varsayilan = p.get(k)
        if isinstance(varsayilan, bool):
            p[k] = v if isinstance(v, bool) else str(v).strip().lower() in (
                "1", "true", "on", "yes", "evet")
        elif isinstance(varsayilan, (int, float)):
            try:
                if (isinstance(varsayilan, int) and isinstance(v, str)
                        and _BINLIKLI_AYAR.fullmatch(v.strip())):
                    sayi = float(re.sub(r"[.,]", "", v.strip()))
                else:
                    sayi = float(v)
            except (TypeError, ValueError):
                sayi = None
            if sayi is None or sayi != sayi or sayi in (float("inf"), float("-inf")):
                raise hata(t(f"Geçersiz ayar: '{_ad(k)}' bir sayı olmalı (girilen: {v!r}).",
                             f"Invalid setting: '{_ad(k)}' must be a number (got {v!r})."))
            if k in sinirlar:
                alt, ust = sinirlar[k]
                if not alt <= sayi <= ust:
                    # Kullanicinin yazdigi metin aynen: "1.500" yazan "girilen: 1.5" gormesin
                    girilen = v.strip() if isinstance(v, str) else f"{sayi:g}"
                    raise hata(t(
                        f"Geçersiz ayar: '{_ad(k)}' {_yaz(alt)} ile {_yaz(ust)} arasında "
                        f"olmalı (girilen: {girilen}).",
                        f"Invalid setting: '{_ad(k)}' must be between {_yaz(alt)} and "
                        f"{_yaz(ust)} (got {girilen})."))
            p[k] = int(round(sayi)) if isinstance(varsayilan, int) else sayi
        else:
            p[k] = v
    return p
