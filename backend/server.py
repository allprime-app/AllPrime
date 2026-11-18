# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""
AllPrime - Yerel Flask Sunucu (Electron sidecar)
Electron uygulamasi bu sunucuyu yerel bir portta baslatip motora HTTP ile baglanir.
"""
import os
import sys
import hmac
import json
import argparse

# Bellek (v0.8.44): OpenBLAS her numpy yuklemesinde cekirdek sayisi kadar is parcacigi tamponu ayirir ve ozgulluk
# taramasinin her havuz iscisi numpy'yi ayri yukler. Tarama BLAS kullanmaz (yalniz eleman bazli islemler); ayar
# sonucu ve sureyi degistirmez, 24 cekirdekli makinede en iyi Ozgul cift aramasinda toplam ayrilan (commit) bellek
# 11,6 GB -> 2,0 GB. numpy'yi ilk ceken modulden (engine, specificity) ONCE kurulmali; isciler ortami miras alir.
# Kullanici ortamda baska bir deger verdiyse o gecerli kalir.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from flask import Flask, request, jsonify
from flask_cors import CORS

import engine
import transcripts
import specificity
import dbsnp
import downloads
import evaluate
import kopya
from lang import set_lang, t

app = Flask(__name__)

# ERISIM DENETIMI (inceleme bulgusu 6, 2026-10-28)
# Motor 127.0.0.1'de dinliyor ama tarayicida acik HER site o porta istek
# atabiliyordu: CORS(app) herkese acikti ve her uc get_json(force=True) ile
# text/plain govdeyi de okudugu icin tarayici izin bile sormuyordu (preflight
# yok). Bir site /set_genome'a bos yol gonderip genom kaydini kalici silebilir,
# /downloads/start ile indirme baslatabilir, /health'ten kullanici yollarini
# okuyabilirdi. Uc katman:
#   1. Anahtar: Electron her acilista rastgele bir anahtar uretip ALLPRIME_TOKEN ile
#      motora, preload ile arayuze verir; anahtarsiz istek 401. Asil koruma bu.
#   2. Host: DNS rebinding'e karsi yalnizca yerel ad kabul edilir.
#   3. CORS yalnizca arayuzun kokenine. Tamamen kaldirilamaz: arayuz file://
#      sayfasi, motor http - tarayici icin farkli koken. Electron bu sayfadan
#      "Origin: file://" gonderir (olculdu); "null" bilerek YOK, o koken her
#      sitenin sandbox iframe'ine de aittir.
# ALLPRIME_TOKEN yoksa (elle 'python server.py', test_smoke) anahtar denetimi kapali;
# Electron her zaman verir.
ANAHTAR_BASLIGI = "X-AllPrime-Token"
TOKEN = os.environ.get("ALLPRIME_TOKEN", "")
YEREL_ADLAR = {"127.0.0.1", "localhost", "[::1]"}
CORS(app, origins=["file://"], allow_headers=["Content-Type", ANAHTAR_BASLIGI])

# Motor surumu. electron/package.json ile AYNI tutulmali; arayuz acilista
# karsilastirip uyusmazlikta uyarir. Asil kontrol ise /health'teki uc listesi:
# arayuz ihtiyac duydugu her ucun motorda var olup olmadigina bakar.
SURUM = "1.0.0"


@app.before_request
def _apply_language():
    """Mesaj dilini istekten al. Arayuz her cagriya 'lang' ekler; yoksa Turkce."""
    lang = request.args.get("lang")
    if not lang and request.is_json:
        try:
            lang = (request.get_json(silent=True) or {}).get("lang")
        except Exception:
            lang = None
    set_lang(lang or "tr")


@app.before_request
def _erisim_denetimi():
    """Yerel ad + anahtar. Dil secimi (_apply_language) bundan ONCE calisir:
    ret mesaji da istenen dilde olur."""
    host = (request.host or "").lower()
    ad = host if host.endswith("]") else host.rsplit(":", 1)[0]
    if ad not in YEREL_ADLAR:
        return jsonify({"error": t("Yalnızca yerel bağlantı kabul edilir.",
                                   "Only local connections are accepted.")}), 403
    # Tarayicinin CORS on istegi (OPTIONS) baslik DEGERINI tasimaz; cevabi
    # flask_cors verir, asil istek yine anahtarla gelmek zorunda.
    if TOKEN and request.method != "OPTIONS":
        gelen = request.headers.get(ANAHTAR_BASLIGI, "")
        if not hmac.compare_digest(gelen.encode(), TOKEN.encode()):
            return jsonify({"error": t("Yetkisiz istek: motor yalnızca AllPrime arayüzünden "
                                       "kullanılabilir.",
                                       "Unauthorized request: the engine can only be used "
                                       "from the AllPrime interface.")}), 401


# primer3 isteyen uclar. Ozgulluk taramasi saf Python oldugu icin listede YOK:
# primer3 yuklenemese de calisir.
PRIMER3_UCLARI = {"/design", "/design_cdna", "/design_skipping", "/design_sequence",
                  "/design_sequence_pair", "/design_breakpoint", "/evaluate", "/evaluate_cdna"}


@app.before_request
def _primer3_kapisi():
    """primer3 yuklenemediyse istek primer3'e ulasmadan anlasilir bir mesajla
    kesilir. Eskiden "module 'primer3' has no attribute 'calc_tm'" gibi bir 500
    donuyordu. Dil secimi (_apply_language) bundan ONCE calisir - kayit sirasi."""
    if request.path in PRIMER3_UCLARI and not engine.PRIMER3_DURUM["ok"]:
        return jsonify({"error": engine.primer3_mesaji(), "primer3": False}), 503


# Govde ve alan tipleri (2026-10-29 hata taramasi): 844 bozuk istekten 55'i 500
# veriyordu - govde nesne degil ("5"), acc / item / path metin degil, assembly
# liste ya da nesne. Arayuz hep dogru tipi gonderir; bu denetim motoru dogrudan
# cagiran (betik, eski arayuz) icin. Bos ya da bozuk JSON'u uclar kendisi soyler.
METIN_ALANLAR = {"assembly", "gene", "acc", "sequence", "forward", "reverse", "target",
                 "type", "item", "path", "lang"}
METIN_YA_DA_SAYI = {"chrom", "c_position", "start", "end", "exon"}
DERLEMELER = ("GRCh37", "GRCh38")


def _derleme_hatasi(assembly):
    """Bilinmeyen derleme -> 400 (tasarim uclarindaki engine denetimiyle ayni). Eskiden
    'abc' yanlis sebeple reddediliyordu: "abc tanitilmamis", "abc icin transkript
    tablosu bulunamadi" - sanki dosya eksikmis gibi (2026-10-29 hata taramasi)."""
    if assembly in DERLEMELER:
        return None
    return jsonify({"error": t(
        f"assembly 'GRCh37' veya 'GRCh38' olmalı (girilen: '{assembly}').",
        f"assembly must be 'GRCh37' or 'GRCh38' (given: '{assembly}').")}), 400


@app.before_request
def _govde_denetimi():
    if request.method != "POST":
        return None
    data = request.get_json(force=True, silent=True)
    if data is None:
        return None
    if not isinstance(data, dict):
        return jsonify({"error": t("İstek gövdesi bir JSON nesnesi olmalı ({...}).",
                                   "The request body must be a JSON object ({...}).")}), 400
    for k, v in data.items():
        if v is None:
            continue
        if k in METIN_ALANLAR and not isinstance(v, str):
            return jsonify({"error": t(f"'{k}' alanı metin olmalı.",
                                       f"The '{k}' field must be text.")}), 400
        if k in METIN_YA_DA_SAYI and (isinstance(v, bool) or not isinstance(v, (str, int, float))):
            return jsonify({"error": t(f"'{k}' alanı metin ya da sayı olmalı.",
                                       f"The '{k}' field must be text or a number.")}), 400
    # assembly'nin DEGERI burada denetlenmez: bilinmeyen deger Degerlendir'i genomsuz
    # calistirir (duman testleri "yok" ile bunu kullanir), tasarim uclari kendisi reddeder.
    return None


def _tasarim_yaniti(sonuc):
    """Tasarim sonuclarinin ortak son islemi: sonuc bossa primer3'un ham
    aciklamasini ("unacceptable product size 10044") okunur, eyleme donuk bir
    nota cevirir. YENI BIR TASARIM UCU EKLERSEN bunu kullan, duz jsonify degil."""
    sonuc = engine.explain_notu(sonuc)
    asm = (sonuc.get("input") or {}).get("assembly")
    # Dizi modlarinda dbSNP hic kullanilmaz (genomik koordinat yok); orada uyari anlamsiz
    uyari = (dbsnp.bozuk_mu(asm) if asm and sonuc.get("dbsnp") is not None
             and sonuc.get("mode") not in ("sequence", "sequence_pair") else None)
    if uyari:
        sonuc["notes"] = [uyari] + list(sonuc.get("notes") or [])
    # DNA ve kirilma noktasinda transkript tablosu yalnizca etiket ve psodogen uyarisi
    # icin kullanilir; okunamazsa o uyarilar SESSIZCE kayboluyordu. RNA modlari tablo
    # olmadan zaten calismaz (anlasilir 400).
    if asm and sonuc.get("mode") in (None, "breakpoint"):
        tablo = transcripts.tablo_uyarisi(asm)
        if tablo:
            sonuc["notes"] = [tablo] + list(sonuc.get("notes") or [])
        _gen_yonu_ekle(sonuc, asm)
    return jsonify(sonuc)


def _gen_yonu_ekle(sonuc, asm):
    """Her cifte urunun ortustugu genin adi ve ipligi (strand_gene, gene_strand).
    Arayuz eksi iplikte F/R adlarini ve urun dizisini genin yonune cevirir (yon.js).
    Degerlendir'in kullandigi fonksiyonun AYNISI: tasarlanan cift Degerlendir'e
    verilince "roller yer degismis" denmemeli; TP53'te deniyordu (2026-11-01)."""
    chrom = (sonuc.get("input") or {}).get("chrom")
    for p in sonuc.get("pairs") or []:
        uclar = [x for x in (p.get("forward"), p.get("reverse")) if x]
        if not chrom or len(uclar) != 2 or any("genomic_start" not in x for x in uclar):
            continue
        bas = min(min(x["genomic_start"], x["genomic_end"]) for x in uclar)
        son = max(max(x["genomic_start"], x["genomic_end"]) for x in uclar)
        p["strand_gene"], p["gene_strand"] = evaluate._urun_geni(asm, chrom, bas, son)


_ASM = ("GRCh38", "GRCh37")


@app.get("/health")
def health():
    _genom = {a: engine.genom_durumu(a) for a in _ASM}
    return jsonify({
        "status": "ok",
        "version": SURUM,
        # Arayuz bu listeye bakip "motor su ozelligi taniyor mu" diye sorar.
        # Eski bir motorda bu alan hic yoktur - o da bir cevaptir.
        "endpoints": sorted({r.rule for r in app.url_map.iter_rules()
                             if not r.rule.startswith("/static")}),
        # Motor acik olsa da hesaplama cekirdegi yuklenememis olabilir
        # (Akilli Uygulama Denetimi, eksik kopyalanmis klasor). Arayuz buna bakar.
        "primer3": {"ok": engine.PRIMER3_DURUM["ok"],
                    "kind": engine.PRIMER3_DURUM["tur"],
                    "message": engine.primer3_mesaji()},
        # genomes: yerel genom VAR ve KULLANILABILIR (kesik / yarim / uyusmayan indeksli genom
        # kayitli kalsa da burada False: ozgulluk ve en iyi cift aramalari baslamaz). Sebep
        # genome_warnings'te (istegin dilinde); arayuz bunu gorunur gosterir (A7-04, v0.8.40).
        "genomes": {a: _genom[a]["var"] and not _genom[a]["engelli"] for a in _ASM},
        "genome_warnings": {a: _genom[a]["uyari"] for a in _ASM},
        "genome_blocked": {a: _genom[a]["engelli"] for a in _ASM},
        "annotations": transcripts.annotation_status(),
        "dbsnp": dbsnp.dbsnp_status(),
        "config_debug": engine.config_diagnostics(),
        "defaults": engine.DEFAULTS,
        "cdna_defaults": engine.CDNA_DEFAULTS,
    })


@app.post("/design")
def design():
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": t("Geçersiz JSON gövdesi.", "Invalid JSON body.")}), 400

    assembly = data.get("assembly", "GRCh38")
    chrom = data.get("chrom") or ""
    gene = data.get("gene") or None
    position = data.get("position")
    params = data.get("params") or {}

    if position in (None, ""):
        return jsonify({"error": t("Genomik koordinat (position) gerekli.",
                            "A genomic coordinate (position) is required.")}), 400
    # Ayristirma motorda: tek koordinat da ("50000001") varyantin tamamini kapsayan
    # aralik da ("50000001-50000300") kabul edilir; bkz. engine.varyant_araligi.
    try:
        result = engine.design_primers(assembly, chrom, position,
                                       gene=gene, params=params)
        return _tasarim_yaniti(result)
    except engine.PrimerError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover
        return jsonify({"error": t(f"Beklenmeyen hata: {e}", f"Unexpected error: {e}")}), 500


@app.post("/kopya_ciftleri")
def kopya_ciftleri():
    """DNA tasariminda kurallara uyan butun adaylari tarar: en iyi Ozgul cift; psodogenli gende kopyadan
    ayrisan ilk 8 cift; Ozgul cift yoksa en az riskli 3 cift (bkz. kopya.py, v0.8.36)."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": t("Geçersiz JSON gövdesi.", "Invalid JSON body.")}), 400
    assembly = data.get("assembly", "GRCh38")
    hata = _derleme_hatasi(assembly)
    if hata:
        return hata
    if not os.path.exists(engine.GENOME_PATHS.get(assembly, "") or ""):
        return jsonify({"error": t(f"Bu arama yerel genom dosyası gerektirir; {assembly} tanıtılmamış.",
                                   f"This search needs a local genome file; {assembly} is not configured.")}), 400
    if data.get("position") in (None, ""):
        return jsonify({"error": t("Genomik koordinat (position) gerekli.",
                                   "A genomic coordinate (position) is required.")}), 400
    try:
        sonuc = kopya.ara(assembly, data.get("chrom") or "", data.get("position"),
                          gene=data.get("gene") or None, params=data.get("params") or {})
        _gen_yonu_ekle(sonuc, assembly)
        _gen_yonu_ekle({"input": sonuc["input"], "pairs": sonuc.get("aday") or []}, assembly)
        return jsonify(sonuc)
    except kopya.Iptal:
        return jsonify({"iptal": True})
    except (engine.PrimerError, specificity.SpecificityError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover
        return jsonify({"error": t(f"Beklenmeyen hata: {e}", f"Unexpected error: {e}")}), 500


@app.post("/kopya_durdur")
def kopya_durdur():
    kopya.durdur()
    return jsonify({"ok": True})


@app.get("/transcripts")
def transcripts_of_gene():
    """Gen sembolunden NM_ listesi (MANE Select en ustte) - NM arama yardimcisi."""
    gene = (request.args.get("gene") or "").strip()
    assembly = request.args.get("assembly", "GRCh38")
    if not gene:
        return jsonify({"error": t("Gen sembolü gerekli.", "A gene symbol is required.")}), 400
    hata = _derleme_hatasi(assembly)
    if hata:
        return hata
    try:
        # RNA yolu: derleme secimi ne olursa olsun GRCh38 (engine.RNA_DERLEME); kodlayan
        # dizisi tutarsiz transkriptler "kod_denetimi" ile isaretlenir
        return jsonify(engine.transkript_listesi(gene, assembly))
    except (transcripts.TranscriptError, engine.PrimerError) as e:
        return jsonify({"error": str(e)}), 400


@app.get("/transcript_exons")
def transcript_exons():
    """Ekson atlama arayuzu icin: transkriptin ekson uzunluklari (genom okumadan)."""
    acc = (request.args.get("acc") or "").strip()
    assembly = request.args.get("assembly", "GRCh38")
    if not acc:
        return jsonify({"error": t("Transkript kodu (NM_) gerekli.",
                            "Transcript accession (NM_) is required.")}), 400
    hata = _derleme_hatasi(assembly)
    if hata:
        return hata
    try:
        return jsonify(engine.transcript_exons(assembly, acc))
    except engine.PrimerError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover
        return jsonify({"error": t(f"Beklenmeyen hata: {e}", f"Unexpected error: {e}")}), 500


@app.post("/design_cdna")
def design_cdna():
    """RNA modu: NM_ kodu + c. koordinati -> cDNA uzerinde primer."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": t("Geçersiz JSON gövdesi.", "Invalid JSON body.")}), 400

    acc = (data.get("acc") or "").strip()
    c_pos = (str(data.get("c_position") or "")).strip()
    if not acc:
        return jsonify({"error": t("Transkript kodu (NM_) gerekli.",
                            "Transcript accession (NM_) is required.")}), 400
    if not c_pos:
        return jsonify({"error": t("c. koordinatı gerekli (örn. c.1234).",
                            "A c. coordinate is required (e.g. c.1234).")}), 400

    try:
        result = engine.design_primers_cdna(
            data.get("assembly", "GRCh38"), acc, c_pos,
            params=data.get("params") or {})
        return _tasarim_yaniti(result)
    except engine.PrimerError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover
        return jsonify({"error": t(f"Beklenmeyen hata: {e}", f"Unexpected error: {e}")}), 500


@app.post("/design_skipping")
def design_skipping():
    """Ekson atlama testi: hedef eksonun iki yanindaki eksonlara primer."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": t("Geçersiz JSON gövdesi.", "Invalid JSON body.")}), 400

    acc = (data.get("acc") or "").strip()
    exon = data.get("exons")
    if exon in (None, "", []):
        exon = data.get("exon")             # tek sayi (eski alan) aynen calisir
    if not acc:
        return jsonify({"error": t("Transkript kodu (NM_) gerekli.",
                            "Transcript accession (NM_) is required.")}), 400
    if exon in (None, "", []):
        return jsonify({"error": t("Ekson numarası gerekli.", "An exon number is required.")}), 400
    try:
        # Tek sayi, liste ya da "4-6" / "4,6" metni: ayristirma engine.parse_exon_list'te
        exon = engine.parse_exon_list(exon)
    except engine.PrimerError as e:
        return jsonify({"error": str(e)}), 400

    try:
        result = engine.design_exon_skipping(
            data.get("assembly", "GRCh38"), acc, exon,
            params=data.get("params") or {})
        return _tasarim_yaniti(result)
    except engine.PrimerError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover
        return jsonify({"error": t(f"Beklenmeyen hata: {e}", f"Unexpected error: {e}")}), 500


@app.post("/design_sequence")
def design_sequence():
    """Serbest dizi modu: kullanicinin yapistirdigi dizi uzerinde primer."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": t("Geçersiz JSON gövdesi.", "Invalid JSON body.")}), 400
    try:
        return _tasarim_yaniti(engine.design_from_sequence(
            data.get("sequence") or "",
            target=data.get("target") or None,
            params=data.get("params") or {}))
    except engine.PrimerError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover
        return jsonify({"error": t(f"Beklenmeyen hata: {e}", f"Unexpected error: {e}")}), 500


@app.post("/design_sequence_pair")
def design_sequence_pair():
    """Iki dizi modu: forward birinci dizinin, reverse ikinci dizinin icinden."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": t("Geçersiz JSON gövdesi.", "Invalid JSON body.")}), 400
    fwd = data.get("forward") or ""
    rev = data.get("reverse") or ""
    if not str(fwd).strip() or not str(rev).strip():
        return jsonify({"error": t("Her iki dizi de gerekli.",
                            "Both sequences are required.")}), 400
    try:
        return _tasarim_yaniti(engine.design_from_two_sequences(
            fwd, rev, params=data.get("params") or {}))
    except engine.PrimerError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover
        return jsonify({"error": t(f"Beklenmeyen hata: {e}", f"Unexpected error: {e}")}), 500


@app.post("/design_breakpoint")
def design_breakpoint():
    """Kirilma noktasi modu: delesyon (gap-PCR) / tandem duplikasyon (disa bakan
    primerler) sinirlarindan primer. Bkz. engine.design_breakpoint."""
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": t("Geçersiz JSON gövdesi.", "Invalid JSON body.")}), 400
    bas, bit = data.get("start"), data.get("end")
    if bas in (None, "") or bit in (None, ""):
        return jsonify({"error": t("Başlangıç ve bitiş koordinatı gerekli.",
                            "Start and end coordinates are required.")}), 400
    try:
        # DNA sekmesiyle ayni kural: "50000001.5" eskiden 500000015 oluyordu
        # Kromozom onekli koordinat ("chr7:117559000"): kromozomla celisirse hata, aynisiysa kabul
        krom = data.get("chrom") or ""
        bas = engine.oneksiz_koordinat(bas, krom, data.get("assembly", "GRCh38"))
        bit = engine.oneksiz_koordinat(bit, krom, data.get("assembly", "GRCh38"))
        bas, bit = engine._sayi(bas), engine._sayi(bit)
    except engine.PrimerError as e:
        return jsonify({"error": str(e)}), 400
    try:
        return _tasarim_yaniti(engine.design_breakpoint(
            data.get("assembly", "GRCh38"), data.get("chrom") or "", bas, bit,
            sv_type=data.get("type") or "del", params=data.get("params") or {}))
    except engine.PrimerError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover
        return jsonify({"error": t(f"Beklenmeyen hata: {e}", f"Unexpected error: {e}")}), 500


def _yakin_not(hits, fwd, rev, assembly, expected, result):
    """Ozgul rozetli ciftte 3' kurali disinda kalan yakin kopya notu (evaluate._yakin_kopya; F-03).
    Yalnizca bilgi: rozet karari, sira ve 'En iyi Ozgul cift' bu alana bagli degildir. Hedef bolge
    bilinmiyorsa (serbest dizi, kirilma noktasi) ya da hesap basarisizsa None. Primer adlari istekteki
    adlardir (arayuz kartta gorunen adi gonderir): 'forward' = kartin Forward'i."""
    if hits is None or not expected or not expected.get("chrom"):
        return None
    try:
        hedef = [(expected["chrom"], int(expected["start"]), int(expected["end"]))]
        pr = result.get("intended")
        if pr:
            hedef.append((engine.normalize_chrom(pr["chrom"]), pr["start"], pr["end"]))
        return evaluate._yakin_kopya(hits, fwd.upper(), rev.upper(), assembly,
                                     int(result["params_used"]["max_offtarget_product"]),
                                     hedef_yerleri=hedef)
    except Exception:       # not eklenemezse rozet yine de gelir
        return None


@app.post("/specificity")
def check_specificity():
    """Bir primer CIFTININ genomda istenmeyen urun verip vermedigini kontrol et.
    Otomatik degil - arayuzde kullanici istedigi cift icin tetikler."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": t("Geçersiz JSON gövdesi.", "Invalid JSON body.")}), 400

    if not isinstance(data, dict):
        return jsonify({"error": t("Geçersiz JSON gövdesi.", "Invalid JSON body.")}), 400
    assembly = data.get("assembly", "GRCh38")
    hata = _derleme_hatasi(assembly)
    if hata:
        return hata
    fwd = str(data.get("forward") or "").strip()
    rev = str(data.get("reverse") or "").strip()
    if not fwd or not rev:
        return jsonify({"error": t("Forward ve reverse dizi gerekli.",
                            "Forward and reverse sequences are required.")}), 400
    # Bicimi bozuk 'expected' / 'params' eskiden AttributeError -> 500 veriyordu
    if not isinstance(data.get("expected") or {}, dict) or \
            not isinstance(data.get("params") or {}, dict):
        return jsonify({"error": t("'expected' ve 'params' anahtar-değer nesnesi olmalı.",
                            "'expected' and 'params' must be key-value objects.")}), 400

    path = engine.GENOME_PATHS.get(assembly, "")
    if not path or not os.path.exists(path):
        return jsonify({"error": t(
            f"Özgüllük kontrolü yerel genom dosyası gerektirir; {assembly} tanıtılmamış. "
            "Ensembl API ile bu kontrol yapılamaz.",
            f"The specificity check needs a local genome file; {assembly} is not "
            "configured. This check cannot be done through the Ensembl API.")}), 400

    # Hedef bolge kromozomu FASTA yazimina cevrilir ('chr17' -> '17'); RNA modunda
    # transkript kaydi 'chr' onekli gelir, tarama ise FASTA adlarini kullanir.
    expected = data.get("expected") or None
    if expected and expected.get("chrom"):
        expected = dict(expected)
        expected["chrom"] = engine.normalize_chrom(expected["chrom"])
    if expected:
        # Bozuk start/end tarama bittikten SONRA int()'te 500 veriyordu (A1-03): once oku
        expected = dict(expected)
        try:
            for k in ("start", "end"):
                if k in expected:
                    v = expected[k]
                    expected[k] = engine._sayi(
                        int(v) if isinstance(v, float) and v.is_integer() else v)
        except engine.PrimerError as e:
            return jsonify({"error": t(f"'expected.{k}' okunamadı: {e}",
                                       f"'expected.{k}' could not be read: {e}")}), 400

    try:
        # Taramanin isabetleri tutulur: yakin kopya notu ayni isabetlerden hesaplanir (ayri genom
        # taramasi yok; olculen ek sure cift basina ~1,5 ms). Karar alanlarina karismaz.
        kutu = {}

        def isabet(*a, **k):
            kutu["h"] = specificity.scan_genome(*a, **k)
            return kutu["h"]
        result = specificity.check_pair(
            path, fwd, rev, expected=expected,
            params=data.get("params") or {}, assembly=assembly, isabet=isabet)
        result["assembly"] = assembly
        result["near_copy"] = _yakin_not(kutu.get("h"), fwd, rev, assembly, expected, result)
        return jsonify(result)
    except specificity.SpecificityError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover
        return jsonify({"error": t(f"Beklenmeyen hata: {e}", f"Unexpected error: {e}")}), 500


@app.post("/evaluate")
def evaluate_pair():
    """Hazir primerleri degerlendir: ozellikler + genomda yerlesim + urun teshisi."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(evaluate.evaluate(
            data.get("forward") or "",
            data.get("reverse") or None,
            data.get("assembly", "GRCh38"),
            params=data.get("params") or {},
            hedef=data.get("target")))
    except evaluate.EvaluateError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover
        return jsonify({"error": t(f"Beklenmeyen hata: {e}",
                                   f"Unexpected error: {e}")}), 500


@app.post("/evaluate_cdna")
def evaluate_pair_cdna():
    """RNA modu: hazir primerleri BELIRTILEN TRANSKRIPT uzerinde degerlendir.
    Genom taramasi degil - ekson sinirina oturan primer genomda butun halde
    bulunmadigi icin DNA modu bu primerlere yanlis alarm veriyor."""
    data = request.get_json(force=True, silent=True) or {}
    hata = _derleme_hatasi(data.get("assembly", "GRCh38"))
    if hata:
        return hata
    try:
        return jsonify(evaluate.evaluate_cdna(
            data.get("forward") or "",
            data.get("reverse") or None,
            acc=data.get("acc") or "",
            assembly=data.get("assembly", "GRCh38"),
            params=data.get("params") or {},
            hedef=data.get("target")))
    except evaluate.EvaluateError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover
        return jsonify({"error": t(f"Beklenmeyen hata: {e}",
                                   f"Unexpected error: {e}")}), 500


@app.get("/downloads")
def downloads_status():
    """Veri dosyalarinin durumu + suren indirmenin ilerlemesi."""
    return jsonify(downloads.status())


@app.post("/downloads/start")
def downloads_start():
    """Bir veri dosyasini indirmeye basla (arka planda, tek is)."""
    data = request.get_json(force=True, silent=True) or {}
    key = (data.get("item") or "").strip()
    try:
        downloads.start(key)
        return jsonify({"ok": True, "item": key})
    except downloads.DownloadError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover
        return jsonify({"error": t(f"Beklenmeyen hata: {e}",
                                   f"Unexpected error: {e}")}), 500


@app.post("/downloads/cancel")
def downloads_cancel():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify({"ok": downloads.cancel((data.get("item") or "").strip() or None)})


@app.post("/set_genome")
def set_genome():
    """Calisma aninda yerel FASTA yolunu tanit (Electron ayarlardan cagirir)."""
    # silent=True: bozuk JSON'da Flask'in HTML 400 sayfasi yerine JSON hata don
    # (arayuz HTML'i cozemeyip "Unexpected token <" gosteriyordu)
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": t("Geçersiz JSON gövdesi.", "Invalid JSON body.")}), 400
    asm = data.get("assembly")
    path = data.get("path")
    if asm not in ("GRCh37", "GRCh38"):
        return jsonify({"error": t("assembly GRCh37/GRCh38 olmalı.",
                            "assembly must be GRCh37 or GRCh38.")}), 400

    uyari = None
    kullanilabilir = False
    if path:
        # Bos yol = tanimi kaldir; dolu yol ise DOGRULANIR. Yanlis dosyayi
        # sessizce kabul etmek "genom var ama hicbir sey bulunamiyor" gibi
        # tesehisi zor bir duruma yol aciyordu.
        # asm verilir: obur derlemeye ait FASTA (GRCh37 -> GRCh38 yuvasi) reddedilir, config'e yazilmaz
        k = engine.genome_check(path, asm)
        if not k["ok"]:
            engine.GENOME_REJECTED[path] = k["reason"]
            return jsonify({"error": k["reason"]}), 400
        uyari = k["warning"]
        kullanilabilir = bool(k.get("usable"))

    engine.GENOME_PATHS[asm] = path or ""
    engine.GENOME_REJECTED.pop(path, None)
    engine.save_config()
    # usable: genom gercekten kullanilabilir mi (False ise uyari 'genom kullanilmadi' der)
    return jsonify({"ok": True, "genomes": engine.GENOME_PATHS, "warning": uyari,
                    "usable": kullanilabilir})


if __name__ == "__main__":
    # ONEMLI: ozgulluk taramasi coklu surec kullanir. PyInstaller ile paketlenmis
    # exe'de Windows her isci icin ayni exe'yi yeniden baslatir; freeze_support()
    # EN BASTA cagrilmazsa uygulama kendini sonsuz kez acar.
    import multiprocessing
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5077)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    # Sadece yerel: disaridan erisilemez (KVKK / yerel-oncelikli)
    print(f"[AllPrime] sunucu baslatiliyor: http://{args.host}:{args.port}", flush=True)
    if not TOKEN:
        print("[AllPrime] UYARI: ALLPRIME_TOKEN yok - anahtar denetimi kapali (gelistirme modu).",
              flush=True)
    app.run(host=args.host, port=args.port, threaded=True)
