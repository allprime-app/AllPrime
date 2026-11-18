# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda.
"""
AllPrime - duman testi (smoke test)
=====================================
Calistirma:

    backend\\.venv\\Scripts\\python.exe backend\\test_smoke.py

Genom/annotasyon dosyalari yoksa onlara bagli testler ATLANIR, gerisi kosar;
boylece veri indirilmemis bir makinede de anlamli bir kontrol yapilabilir.

Buradaki testlerin cogu GERCEKTEN YASANMIS hatalarin nobetcisi:
her biri bir kez sessizce yanlis cevap uretmis ya da kullaniciyi
saatlerce yaniltmis bir durumu tekrar etmemek icin var. Silmeden once
ilgili yorumu oku.

WINDOWS UYARISI: ozgulluk taramasi multiprocessing kullanir; spawn ile bu
dosya yeniden import edilir. Alttaki `if __name__ == "__main__"` korumasi
OLMADAN her isci tum testleri bastan calistirir (14 surec acilir). Silme.
"""
import os
import re
import sys
import json
import shutil
import tempfile
import time

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(BURASI)                       # depo koku (AllPrime-kaynak)
# Calisan uygulama deponun YANINDA durur: Desktop\AllPrime. Eskiden deponun
# icindeydi - ic ice ayni ad kullanicida karisiklik yaratiyordu, kopyalarken
# kaynak kodu da tasiyordu.
os.environ.setdefault("ALLPRIME_APP_ROOT",
                      os.path.join(os.path.dirname(KOK), "AllPrime"))
sys.path.insert(0, BURASI)

gecti = basarisiz = atlandi = 0
_hatalar = []


def ok(ad, kosul, ek=""):
    global gecti, basarisiz
    if kosul:
        gecti += 1
        print(f"  [OK]      {ad} {ek}", flush=True)
    else:
        basarisiz += 1
        _hatalar.append(ad)
        print(f"  [BASARISIZ] {ad} {ek}", flush=True)


def atla(ad, sebep):
    global atlandi
    atlandi += 1
    print(f"  [ATLANDI] {ad} — {sebep}", flush=True)


def baslik(s):
    print(f"\n=== {s} ===", flush=True)


# ------------------------------------------------------------------
# HTTP hedefi (paketli motor). Varsayilan: Flask test_client, motor bu surecte.
#   --exe <allprime-server.exe>          motoru Electron gibi baslatir (rastgele port
#                                        + ALLPRIME_TOKEN), testleri ona kosar, kapatir
#   --url http://127.0.0.1:N --token X   zaten calisan bir motora baglanir
# Neden (inceleme bulgusu 13): dagitilan exe hic test edilmiyordu; PyInstaller'in
# atladigi bir modul ya da veri dosyasi ancak kullanicinin makinesinde ortaya cikardi.
# Bu modda motorun ICINI degistiren (engine.X = ... ile) testler anlamsizdir; onlar
# SUREC_ICI kumesinde ve atlanir.
# ------------------------------------------------------------------
HTTP = None          # {"url": ..., "token": ...} ya da None (test_client)
EXE_YOLU = None      # --exe ile verilen paketli motor (kapanis testi kendi kopyasini baslatir)


class _HttpYanit:
    def __init__(self, r):
        self.status_code = r.status_code
        self.headers = r.headers
        self.data = r.content
        self._r = r

    def get_json(self, silent=False):
        try:
            return self._r.json()
        except ValueError:
            return None


class _HttpIstemci:
    """Flask test_client'in testlerde kullanilan kismi (get/post/options), gercek
    HTTP ile. Anahtar basligini, test kendisi vermediyse ekler."""

    def __init__(self, url, token):
        import requests
        self._s = requests.Session()
        self._s.trust_env = False          # sistem vekil sunucusu yerel istege karismasin
        self.url, self.token = url.rstrip("/"), token

    def _istek(self, yontem, yol, json=None, data=None, content_type=None, headers=None):
        h = {"X-AllPrime-Token": self.token} if self.token else {}
        h.update(headers or {})
        if content_type:
            h["Content-Type"] = content_type
        return _HttpYanit(self._s.request(yontem, self.url + yol, json=json, data=data,
                                          headers=h, timeout=900))

    def get(self, yol, **k):
        return self._istek("GET", yol, **k)

    def post(self, yol, **k):
        return self._istek("POST", yol, **k)

    def options(self, yol, **k):
        return self._istek("OPTIONS", yol, **k)


def _exe_baslat(exe):
    """Paketli motoru Electron'un yaptigi gibi baslat. Doner: (surec, url, token)."""
    return _motor_baslat([exe], os.path.dirname(exe))


def _motor_baslat(komut, cwd, ek_env=None):
    """Motoru ayri bir surec olarak baslat (komut + --port), /health cevap verene
    kadar bekle. Doner: (surec, url, token)."""
    import secrets
    import socket
    import subprocess
    import requests
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    token = secrets.token_hex(32)
    surec = subprocess.Popen(list(komut) + ["--port", str(port)], cwd=cwd,
                             env=dict(os.environ, ALLPRIME_TOKEN=token, **(ek_env or {})),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    t0 = time.time()
    while time.time() - t0 < 180:            # main.js BEKLEME_MS ile ayni
        if surec.poll() is not None:
            raise SystemExit(f"motor acilmadan kapandi (kod {surec.returncode})")
        try:
            requests.get(url + "/health", timeout=1, headers={"X-AllPrime-Token": token})
            print(f"motor hazir: {url} ({time.time() - t0:.1f} sn)", flush=True)
            return surec, url, token
        except requests.RequestException:
            time.sleep(0.5)
    surec.kill()
    raise SystemExit("motor 180 sn icinde acilmadi")


# ------------------------------------------------------------------
# 1) Genom dogrulamasi  (veri dosyasi GEREKMEZ)
# ------------------------------------------------------------------
def test_genom_dogrulama(engine):
    baslik("Genom dogrulamasi")

    k = engine.genome_check("")
    ok("bos yol reddedilir", not k["ok"])

    k = engine.genome_check(os.path.join(BURASI, "boyle_bir_dosya_yok.fa"))
    ok("olmayan dosya reddedilir", not k["ok"])
    ok("  ...sebebi soylenir", bool(k["reason"]))

    # ASIL NOBETCI: sahte/yarim bir .fa dosyasi bir kez config'e yazilmis ve
    # uygulama "genom var" sanip hicbir sey bulamamisti. Sessiz yanlis cevap.
    gecici = tempfile.mkdtemp(prefix="allprime_test_")
    try:
        kucuk = os.path.join(gecici, "Homo_sapiens.GRCh38.dna.fa")
        with open(kucuk, "w", encoding="utf-8") as f:
            f.write(">1\nACGTACGTACGT\n")
        k = engine.genome_check(kucuk)
        ok("kucuk dosya (yarim indirme) reddedilir", not k["ok"])
        ok("  ...sebep boyutu soyler", "MB" in (k["reason"] or ""),
           f"-> {(k['reason'] or '')[:60]}")

        # autodetect ILK eslesmeyi degil ilk GECERLI eslesmeyi almali
        gen_dizin = os.path.join(gecici, "genomes")
        os.makedirs(gen_dizin, exist_ok=True)
        shutil.move(kucuk, os.path.join(gen_dizin, "Homo_sapiens.GRCh38.dna.fa"))

        eski_yollar = dict(engine.GENOME_PATHS)
        eski_kok = os.environ.get("ALLPRIME_APP_ROOT", "")
        eski_red = dict(engine.GENOME_REJECTED)
        try:
            engine.GENOME_PATHS["GRCh38"] = ""
            engine.GENOME_PATHS["GRCh37"] = ""
            engine.GENOME_REJECTED.clear()
            os.environ["ALLPRIME_APP_ROOT"] = gecici
            engine.autodetect_genomes()
            ok("otomatik bulma sahte genomu kaydetmez",
               not engine.GENOME_PATHS.get("GRCh38"))
            ok("  ...reddi sebebiyle kaydeder",
               any("MB" in (v or "") for v in engine.GENOME_REJECTED.values()))
        finally:
            engine.GENOME_PATHS.update(eski_yollar)
            engine.GENOME_REJECTED.clear()
            engine.GENOME_REJECTED.update(eski_red)
            if eski_kok:
                os.environ["ALLPRIME_APP_ROOT"] = eski_kok
    finally:
        shutil.rmtree(gecici, ignore_errors=True)


def test_set_genome_ucu(c, engine):
    baslik("/set_genome dogrulamasi")
    gecici = tempfile.mkdtemp(prefix="allprime_test_")
    try:
        sahte = os.path.join(gecici, "sahte.fa")
        with open(sahte, "w", encoding="utf-8") as f:
            f.write(">1\nACGT\n")
        r = c.post("/set_genome", json={"assembly": "GRCh38", "path": sahte})
        ok("sahte genom 400 ile reddedilir", r.status_code == 400,
           f"-> {(r.get_json().get('error') or '')[:60]}")
        ok("  ...gercek genom yolu bozulmadi",
           engine.GENOME_PATHS.get("GRCh38", "") != sahte)

        r = c.post("/set_genome", json={"assembly": "MARS", "path": sahte})
        ok("gecersiz assembly reddedilir", r.status_code == 400)
    finally:
        shutil.rmtree(gecici, ignore_errors=True)


def test_gz_genom_reddi(c, engine):
    baslik("Sikistirilmis (.gz) FASTA tanitilirken reddedilir (G-02, v0.8.61)")
    # NOBETCI (2026-11-11, kullanici karari G-02): gzip / bgzip FASTA /set_genome'da, config.json'da
    # ve ortam degiskeninde acik mesajla reddedilir; eskiden 161 MB'lik .gz 200 ile kabul edilip
    # /design 500 "BioPython >= 1.73 must be installed" veriyordu. Denetim uzantiya degil ilk iki bayta (1f 8b) bakar.
    import gzip
    gecici = tempfile.mkdtemp(prefix="allprime_gz_")
    eski_yollar = dict(engine.GENOME_PATHS)
    eski_red = dict(engine.GENOME_REJECTED)
    eski_cfg = engine.CONFIG_PATH
    eski_min = engine.MIN_GENOME_BYTES
    try:
        engine.CONFIG_PATH = os.path.join(gecici, "config.json")
        icerik = b">1\n" + b"ACGT" * 50 + b"\n"
        gz = os.path.join(gecici, "g.fa.gz")
        with open(gz, "wb") as f:
            f.write(gzip.compress(icerik))
        # uzantisi .fa ama icerigi gzip: uzantiya degil baytlara bakilir
        gizli = os.path.join(gecici, "gizli.fa")
        with open(gizli, "wb") as f:
            f.write(gzip.compress(icerik))
        duz = os.path.join(gecici, "duz.fa")
        with open(duz, "wb") as f:
            f.write(icerik)
        for dil, parca in (("tr", "Sıkıştırılmış FASTA (.gz) desteklenmiyor"),
                           ("en", "Compressed FASTA (.gz) is not supported")):
            for yol, ad in ((gz, ".fa.gz"), (gizli, "icerigi gzip .fa")):
                r = c.post("/set_genome", json={"assembly": "GRCh38", "path": yol, "lang": dil})
                j = r.get_json() or {}
                ok(f"[{dil}] {ad}: 400 ve acik mesaj", r.status_code == 400 and parca in (j.get("error") or ""),
                   f"-> {r.status_code} {(j.get('error') or '')[:70]}")
        ok("  ...kayit degismedi, config.json'a yazilmadi",
           engine.GENOME_PATHS == eski_yollar and not os.path.exists(engine.CONFIG_PATH))
        # genome_check dogrudan: reddedilir, sebep yazilir
        k = engine.genome_check(gz, "GRCh38")
        ok("genome_check .gz: ok=False, sebep .gz diyor", not k["ok"] and ".gz" in (k["reason"] or ""))
        # config.json'daki .gz yol acilista reddedilir ve GENOME_REJECTED'a sebep yazilir
        engine.GENOME_PATHS["GRCh38"] = ""
        engine.GENOME_REJECTED.pop(gz, None)
        with open(engine.CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"genomes": {"GRCh38": gz}}, f)
        engine.load_config()
        ok("config'teki .gz yol acilista kullanilmaz", not engine.GENOME_PATHS.get("GRCh38"))
        ok("  ...GENOME_REJECTED'da sebep var", ".gz" in (engine.GENOME_REJECTED.get(gz) or ""))
        # ortam degiskeni yolu
        engine.GENOME_PATHS["GRCh38"] = gz
        engine.GENOME_REJECTED.pop(gz, None)
        engine.ortam_genomlarini_denetle()
        ok("ortam degiskeni .gz yolu reddedilir",
           not engine.GENOME_PATHS.get("GRCh38") and ".gz" in (engine.GENOME_REJECTED.get(gz) or ""))
        # gerileme: sikistirilmamis FASTA bu denetimde takilmaz (boyut esigi testte 0)
        engine.MIN_GENOME_BYTES = 0
        k = engine.genome_check(duz, "GRCh38")
        ok("gerileme: duz .fa gz denetiminde reddedilmez", ".gz" not in (k.get("reason") or ""),
           f"-> {k.get('reason')}")
        # G-01 tek kopya kilidi (gercek deneme ayri bir betikle yapildi)
        with open(os.path.join(BURASI, "..", "electron", "main.js"), encoding="utf-8") as f:
            mj = f.read()
        ok("main.js: tek kopya kilidi + second-instance (one getir, kucultulmusse geri ac)",
           "app.requestSingleInstanceLock()" in mj and 'app.on("second-instance"' in mj
           and "mainWindow.restore()" in mj and "if (!TEK_KOPYA) return;" in mj)
    finally:
        engine.MIN_GENOME_BYTES = eski_min
        engine.CONFIG_PATH = eski_cfg
        engine.GENOME_PATHS.clear()
        engine.GENOME_PATHS.update(eski_yollar)
        engine.GENOME_REJECTED.clear()
        engine.GENOME_REJECTED.update(eski_red)
        shutil.rmtree(gecici, ignore_errors=True)


# ------------------------------------------------------------------
# 2) Parametre tutarliligi  (veri dosyasi GEREKMEZ)
# ------------------------------------------------------------------
def test_parametre_dogrulama(c):
    baslik("Tutarsiz ayarlar")
    # Bu kombinasyon eskiden HTTP 500 "beklenmeyen hata" veriyordu; kullanicinin
    # kendi girdigi deger yuzunden "beklenmeyen hata" gormesi yanlis.
    durumlar = [
        ("hedef uzunluk aralik disi", {"primer_min_size": 25, "primer_max_size": 30}),
        ("ters Tm araligi", {"primer_min_tm": 70.0, "primer_max_tm": 50.0}),
        ("ters urun araligi", {"product_size_min": 900, "product_size_max": 300}),
    ]
    for ad, prm in durumlar:
        r = c.post("/design", json={"assembly": "GRCh38", "chrom": "17",
                                    "position": 43093000, "params": prm})
        d = r.get_json() or {}
        ok(f"{ad} -> 400 (500 degil)", r.status_code == 400,
           f"-> {(d.get('error') or '')[:55]}")


# ------------------------------------------------------------------
# 3) "Primer bulunamadi" aciklamasi  (veri dosyasi GEREKMEZ)
# ------------------------------------------------------------------
def test_bos_sonuc_aciklamasi(c, engine):
    baslik("Sonuc bosken sebep aciklaniyor mu")

    coz = engine._explain_coz(
        "considered 330, GC content failed 3, long poly-x seq 12, ok 0")
    ok("primer3 aciklamasi ayristirilir",
       coz.get("gc content failed") == 3 and coz.get("ok") == 0)

    # Kisa dizi + varsayilan urun boyu -> primer3 hic cift bulamaz
    dizi = ("GCTAGCTAGCTAGCATCGATCGATCGTAGCTAGCTAGCTAGCATCGATCGGATCGATCGATTAGC"
            "GGCATCGATCGTAGCTAGCTTAGCATCGATCGATCGATCGTAGCTAGCTAGCATCGATCGATCGA"
            "TCGGCTAGCTAGCTAGCATCGATCGATCGTAGCTAGCTAGCATCGATCGGATCGATCGATTAGCG"
            "GCATCGATCGTAGCTAGCTTAGCATCGATCGATCGATCGTAGCTAGCTAGCATCGATCGATCGAT")
    d = c.post("/design_sequence", json={"sequence": dizi, "params": {}}).get_json()
    ok("kisa dizide sonuc yok", d.get("num_returned") == 0)
    notlar = " ".join(d.get("notes") or [])
    ok("  ...sebep insan diliyle yazilir", "ürün boyu" in notlar,
       f"-> {notlar[:70]}")
    ok("  ...eleme dokumu verilir", "Eleme dökümü" in notlar)

    d = c.post("/design_sequence",
               json={"sequence": dizi, "params": {}, "lang": "en"}).get_json()
    notlar = " ".join(d.get("notes") or [])
    ok("  ...Ingilizcesi de var", "product-size" in notlar, f"-> {notlar[:60]}")


# ------------------------------------------------------------------
# 3b) "Tm opt" alani kaldirildi (K5, F-04)  (veri dosyasi GEREKMEZ)
# ------------------------------------------------------------------
def test_tm_opt_kaldirildi(c, engine):
    baslik("Tm opt alani yok; eski istemcinin primer_opt_tm'i yok sayilir")
    import random
    rng = random.Random(5)
    dizi = "".join(rng.choice("ACGT") for _ in range(1200))
    govde = {"sequence": dizi, "target": "600"}

    def tasarla(prm):
        g = dict(govde)
        g["params"] = prm
        r = c.post("/design_sequence", json=g)
        return r.status_code, r.get_json() or {}

    def ozet(d):
        return [(p["forward"]["sequence"], p["reverse"]["sequence"], p["total_score"])
                for p in d.get("pairs", [])]
    ok("varsayilan ayarlarda primer_opt_tm yok", "primer_opt_tm" not in engine.DEFAULTS)
    k0, d0 = tasarla({})
    ok("tasarim calisir (10 cift) ve params_used'da primer_opt_tm yok",
       k0 == 200 and len(ozet(d0)) == 10 and "primer_opt_tm" not in (d0.get("params_used") or {}),
       f"-> {k0} {len(ozet(d0))}")
    for deger in (56, 64, "abc", None):
        k1, d1 = tasarla({"primer_opt_tm": deger})
        ok(f"eski primer_opt_tm={deger!r} yok sayilir: cift listesi birebir ayni",
           k1 == 200 and ozet(d1) == ozet(d0), f"-> {k1}")
    # primer3'un istedigi optimum, araligin ortasindan turetilir: varsayilan disi aralik hata vermez
    kd, dd = tasarla({"primer_min_tm": 50.0, "primer_max_tm": 54.0})
    tmler = [x["tm"] for p in dd.get("pairs", []) for x in (p["forward"], p["reverse"])]
    ok("Tm araligi 50-54: eskiden 'hedef Tm aralik disi' hatasiydi; simdi tasarim calisir, Tm aralikta",
       kd == 200 and bool(tmler) and all(50 <= x <= 54 for x in tmler), f"-> {kd} {len(tmler)}")
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    with open(os.path.join(kok, "index.html"), encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(kok, "i18n.js"), encoding="utf-8") as f:
        i18n = f.read()
    with open(os.path.join(kok, "..", "main.js"), encoding="utf-8") as f:
        main_js = f.read()
    ok("arayuzde Tm opt alani, etiketi (TR + EN) ve laboratuvar kaydi yok",
       "primer_opt_tm" not in html and "primer_opt_tm" not in i18n and "primer_opt_tm" not in main_js
       and "Tm opt" not in i18n and "Tm opt" not in html)


# ------------------------------------------------------------------
# 4) Tasarim modlari  (GENOM GEREKIR)
# ------------------------------------------------------------------
def test_tasarim(c):
    baslik("Tasarim modlari")

    t0 = time.time()
    r = c.post("/design", json={"assembly": "GRCh38", "chrom": "17",
                                "position": 43093000, "params": {}})
    d = r.get_json()
    ok("DNA modu", r.status_code == 200 and len(d.get("pairs") or []) > 0,
       f"{len(d.get('pairs') or [])} cift, {time.time() - t0:.1f} sn")

    r = c.post("/design_cdna", json={"assembly": "GRCh38", "acc": "NM_007294",
                                     "c_position": "c.1000", "params": {}})
    d = r.get_json()
    ok("RNA/cDNA modu", r.status_code == 200 and len(d.get("pairs") or []) > 0,
       f"{len(d.get('pairs') or [])} cift")

    r = c.post("/design_skipping", json={"assembly": "GRCh38", "acc": "NM_007294",
                                         "exon": 12, "params": {}})
    ok("ekson atlama modu", r.status_code == 200)
    # NOBETCI (2026-10-25): BRCA1 ekson 10 (eski adlandirmada 11) ~3,4 kb; normal transkript urunu
    # cogaltilabilen en uzun urunu (varsayilan 700 bp) asar -> anlasilir 400.
    r = c.post("/design_skipping", json={"assembly": "GRCh38", "acc": "NM_007294",
                                         "exon": 10, "params": {}})
    hata = (r.get_json() or {}).get("error", "")
    ok("  ...uzun ekson (3,4 kb) 700 bp sinirinda: 400 + 'Ekson 10' aciklamasi",
       r.status_code == 400 and "Ekson 10" in hata, f"-> {hata[:70]}")
    r = c.post("/design_skipping", json={"assembly": "GRCh38", "acc": "NM_007294",
                                         "exon": 10, "params": {"pcr_max": 5000}})
    ok("  ...sinir 5 kb'a cikinca ayni ekson tasarlanir", r.status_code == 200)


def test_ekson_secimi(c):
    """Ekson atlama: birden cok ekson secimi (/transcript_exons, 'exons' alani, bant bilgisi).
    Referans uzunluklar motorun kendi transkript cozumlemesinden (engine._resolve_transcript,
    GRCh38, NM_000546 / NM_004006) alindi; baska kaynak yok."""
    baslik("Ekson atlama: birden cok ekson secimi")
    TP_LEN = [114, 102, 22, 279, 184, 113, 110, 137, 74, 107, 1270]
    TP_KOD = [0, 74, 22, 279, 184, 113, 110, 137, 74, 107, 82]
    r = c.get("/transcript_exons?acc=NM_000546&assembly=GRCh38")
    d = r.get_json() or {}
    ex = d.get("exons") or []
    ok("TP53 /transcript_exons: 11 ekson, uzunluk ve kodlayan baz referansla ayni",
       r.status_code == 200 and d.get("exon_count") == 11 and d.get("gene") == "TP53"
       and [x["len"] for x in ex] == TP_LEN and [x["coding"] for x in ex] == TP_KOD,
       f"-> {r.status_code}")
    r = c.get("/transcript_exons?acc=NM_004006&assembly=GRCh38")
    d = r.get_json() or {}
    e79 = {x["no"]: (x["len"], x["coding"]) for x in d.get("exons") or []}
    ok("DMD /transcript_exons: 79 ekson (1: 268/31, 45-47: 176+148+150, 79: 2705/12)",
       r.status_code == 200 and d.get("exon_count") == 79 and len(e79) == 79
       and e79[1] == (268, 31) and (e79[45][0], e79[46][0], e79[47][0]) == (176, 148, 150)
       and e79[79] == (2705, 12), f"-> {r.status_code}")
    for uc, ad in (("/transcript_exons?acc=NM_YOK1&assembly=GRCh38", "olmayan transkript"),
                   ("/transcript_exons?acc=&assembly=GRCh38", "bos kod"),
                   ("/transcript_exons?acc=NM_000546&assembly=abc", "gecersiz derleme")):
        r = c.get(uc)
        ok(f"/transcript_exons {ad}: 400 + mesaj", r.status_code == 400 and (r.get_json() or {}).get("error"),
           f"-> {r.status_code}")
    r = c.get("/transcript_exons?acc=NM_YOK1&assembly=GRCh38&lang=en")
    ok("  ...Ingilizce mesaj", r.status_code == 400 and "not" in (r.get_json() or {}).get("error", "").lower()
       or "exist" in (r.get_json() or {}).get("error", "").lower(), f"-> {(r.get_json() or {}).get('error', '')[:50]}")

    def sk(g, lang="tr"):
        r = c.post("/design_skipping", json={"assembly": "GRCh38", "acc": "NM_000546", "lang": lang, **g})
        return r.status_code, (r.get_json() or {})

    def anahtar(p):
        return (p["forward"]["sequence"], p["reverse"]["sequence"], p["product_size_skipped"])

    k1, a = sk({"exon": 5})
    k2, b = sk({"exons": [5]})
    ok("tek ekson geriye uyum: exon=5 ile exons=[5] ayni ciftler",
       k1 == 200 and k2 == 200 and a.get("pairs") and [anahtar(p) for p in a["pairs"]] == [anahtar(p) for p in b["pairs"]])
    ok("  ...tek ekson yanitinda eski alanlar duruyor (input.exon, target_exon, band_difference)",
       a["input"]["exon"] == 5 and a["target_exon"]["number"] == 5 and a["target_exon"]["length"] == 184
       and a["pairs"][0]["band_difference"] == 184 and a["skip_len"] == 184 and a["skip_block"] == [5, 5]
       and a["skip_bands"] == [])
    for g in ("5-6", [5, 6], "5–6", "5,6"):
        k, j = sk({"exons": g})
        ok(f"bitisik blok TP53 5-6 ({g!r}): skip_len 297, cerceve korunur, blok [5, 6], bant listesi yok",
           k == 200 and j.get("skip_len") == 297 and j.get("skip_frame") is True
           and j.get("skip_block") == [5, 6] and j.get("skip_exons") == [5, 6] and j.get("skip_bands") == []
           and j.get("anchor_exons") == [4, 7], f"-> {k}")
    ok("  ...her ciftte normal - 297 = atlanmis", all(
        p["product_size_normal"] - 297 == p["product_size_skipped"] for p in j["pairs"]) and j["pairs"])
    k, j = sk({"exons": "4,6", "params": {"pcr_max": 1200}})
    bd = {tuple(x["exons"]): x for x in j.get("skip_bands") or []}
    ok("bitisik olmayan 4 ve 6: bantlar -279 / -113 / -392; cerceve korunur / kayar / kayar",
       k == 200 and (bd[(4,)]["diff"], bd[(6,)]["diff"], bd[(4, 6)]["diff"]) == (279, 113, 392)
       and (bd[(4,)]["frame"], bd[(6,)]["frame"], bd[(4, 6)]["frame"]) == (True, False, False), f"-> {k}")
    ok("  ...blok [4, 6], primerler 3 ve 7. eksonda, skip_len 392 (secilenlerin toplami), frame kayar",
       j["skip_block"] == [4, 6] and j["anchor_exons"] == [3, 7] and j["skip_len"] == 392
       and j["skip_frame"] is False and j["skip_utr"] is False)
    p0 = j["pairs"][0]
    ok("  ...ciftte bant boyu = normal - fark",
       {tuple(x["exons"]): x["size"] for x in p0["bands"]}
       == {k_: p0["product_size_normal"] - v["diff"] for k_, v in bd.items()})
    k, j2 = sk({"exons": "1,2"})
    ok("ilk ekson secimi 400", k == 400 and "Ekson 1" in j2.get("error", ""), f"-> {k}")
    k, j2 = sk({"exons": [10, 11]})
    ok("son ekson secimi 400", k == 400 and "Ekson 11" in j2.get("error", ""), f"-> {k}")
    k, j2 = sk({"exons": [4, 12]})
    ok("aralik disi ekson 400 (ekson 12 yok)", k == 400 and "ekson 12 yok" in j2.get("error", ""), f"-> {k}")
    k, j2 = sk({"exons": 1}, lang="en")
    ok("  ...Ingilizce: first exon", k == 400 and "first exon" in j2.get("error", ""))
    for ad, g in (("harfli metin", "abc"), ("ters aralik", "6-4"), ("bos aralik ucu", "4-"), ("bos metin", " "),
                  ("listede metin", [4, "x"]), ("mantiksiz sayi", True)):
        k, j2 = sk({"exons": g})
        ok(f"hatali biciim 400: {ad}", k == 400 and bool(j2.get("error")), f"-> {k} {j2.get('error', '')[:40]}")
    k, j2 = sk({"exons": "abc"}, lang="en")
    ok("  ...Ingilizce bicim hatasi", k == 400 and "not understood" in j2.get("error", ""))
    k, j2 = sk({"exons": "9999999-99999999"})
    ok("devasa aralik bellegi sisirmez: 400", k == 400, f"-> {k}")
    k, j2 = sk({"exons": "5, 5,5"})
    ok("yinelenenler atilir ve siralanir ('6,5,5' -> [5, 6])",
       sk({"exons": "6,5,5"})[1].get("skip_exons") == [5, 6] and k == 200 and j2.get("skip_exons") == [5])
    r = c.post("/design_skipping", json={"assembly": "GRCh38", "acc": "NM_000546"})
    ok("exon/exons ikisi de yok: 400", r.status_code == 400)
    # DMD 45-47: 474 bp, cerceve korunur; varsayilan pcr_max'te acik mesaj
    t0 = time.time()
    r = c.post("/design_skipping", json={"assembly": "GRCh38", "acc": "NM_004006", "exons": "45-47",
                                         "params": {"pcr_max": 1000}})
    d = r.get_json() or {}
    ok("DMD 45-47: 474 bp, cerceve korunur, blok [45, 47]",
       r.status_code == 200 and d.get("skip_len") == 474 and d.get("skip_frame") is True
       and d.get("skip_block") == [45, 47] and d.get("pairs"), f"-> {r.status_code} {time.time() - t0:.1f} sn")
    for lang, parca in (("tr", "Ekson 45–47 toplam 474 bp"), ("en", "Exon 45–47 is in total 474 bp")):
        r = c.post("/design_skipping", json={"assembly": "GRCh38", "acc": "NM_004006", "exons": "45-47",
                                             "lang": lang})
        ok(f"DMD 45-47 pcr_max asimi ({lang}): 400 + blok mesaji", r.status_code == 400
           and parca in (r.get_json() or {}).get("error", ""), f"-> {(r.get_json() or {}).get('error', '')[:60]}")
    # bant uyarisi: iki beklenen bant (normal dahil) max(20 bp, %5) icinde ise isaretlenir
    k, j3 = sk({"exons": "7,9"})
    p3 = (j3.get("pairs") or [{}])[0]
    boylar = sorted([p3.get("product_size_normal", 0)] + [x["size"] for x in p3.get("bands", [])], reverse=True)
    beklenen = [[boylar[i], boylar[i + 1]] for i in range(len(boylar) - 1)
                if boylar[i] - boylar[i + 1] < max(20, 0.05 * boylar[i])]
    ok("bant yakinlik uyarisi esige gore (7,9: bantlar, band_close alani)",
       k == 200 and p3.get("band_close") == beklenen, f"-> {boylar} {p3.get('band_close')}")


def test_girdi_reddi(c):
    baslik("Hatali girdi reddi")
    r = c.post("/design", json={"assembly": "GRCh38", "chrom": "17",
                                "position": "abc"})
    ok("harfli koordinat reddedilir", r.status_code == 400)

    r = c.post("/design_cdna", json={"assembly": "GRCh38", "acc": "NM_YOK",
                                     "c_position": "c.1"})
    ok("olmayan transkript reddedilir", r.status_code == 400,
       f"-> {(r.get_json().get('error') or '')[:50]}")

    r = c.post("/evaluate", json={"forward": "AGAAGCCXXXTGAGAAGTGA",
                                  "assembly": "GRCh38"})
    ok("gecersiz baz reddedilir", r.status_code == 400)

    r = c.post("/evaluate", json={"forward": "AGAAGCCXXXTGAGAAGTGA",
                                  "assembly": "GRCh38", "lang": "en"})
    ok("hata mesaji Ingilizce donebilir",
       "may only contain" in (r.get_json().get("error") or ""))


# ------------------------------------------------------------------
# 5) Degerlendirme  (GENOM GEREKIR)
# ------------------------------------------------------------------
def test_degerlendirme(c):
    baslik("Degerlendirme sekmesi")

    # GERCEK VAKA: kullanicinin LAMA2 cifti. Iki primer de genoma tam oturuyor
    # ama BIRBIRINDEN UZAGA bakiyor - normal kromozomdan urun cikmaz. Klasik
    # araclar bunu soylemez; bu teshis uygulamanin en degerli ciktisi.
    t0 = time.time()
    r = c.post("/evaluate", json={"forward": "AGAAGCCGTGAGAAGTGA",
                                  "reverse": "ATGATCTAGGTTGTGGTCCT",
                                  "assembly": "GRCh38"})
    d = r.get_json()
    ok("istek basarili", r.status_code == 200, f"({time.time() - t0:.1f} sn)")
    if r.status_code != 200:
        return
    ok("genom kullanildi", d.get("genome_used") is True)
    g = d.get("geometry") or {}
    ok("geometri teshisi verilir", g.get("kind") == "birbirinden_uzaga",
       f"-> {g.get('kind')}")
    ok("karar 'sorun'", d.get("verdict") == "sorun")

    # NOBETCI: sayilar KESILMIS listeden hesaplaniyordu; "6 ayri yere oturuyor"
    # diyordu cunku liste 6'da kesiliyordu. Sayilar TAM listeden gelmeli.
    say = (d.get("counts") or {}).get("forward") or {}
    ok("sayimlar tam listeden gelir (>6)", say.get("total", 0) > 6,
       f"toplam={say.get('total')}, gosterilen={len(d['sites']['forward'])}")

    # Tek primer: cift metrigi ve geometri olmamali
    d = c.post("/evaluate", json={"forward": "AGAAGCCGTGAGAAGTGA",
                                  "assembly": "GRCh38"}).get_json()
    ok("tek primerde cift metrigi yok", d.get("pair") is None)
    ok("tek primerde geometri yok", d.get("geometry") is None)


def test_ters_takilmis_cift(c):
    baslik("F/R yer degistirmis cift")
    # NOBETCI: bir cift urun verebilmek icin birinin '+' digerinin '-' yonde
    # baglanmasi yeter; hangisine "forward" dendigi PCR icin onemsizdir.
    # Kod yalnizca "F+R" kombinasyonunu gecerli sayiyordu, bu yuzden etiketleri
    # ters girilmis CALISAN bir cift icin "hicbir urun vermiyor" (sorun) diyor,
    # ustelik gercek urunu "F+F / R+R yan urunu" diye de sayiyordu.
    # Cift BRCA1'in icinde; BRCA1 EKSI iplikte. F/R genin okuma yonune gore
    # adlandirilir: BRCA1'in forward'i genomda R+F gorunur (2026-10-28'e kadar
    # bu test yonu + iplige gore tanimliyordu - bkz. test_iplik_yonu).
    A = "AGTTAGCACTCTAGGGAAGG"      # BRCA1'e gore forward (genomda - yonde)
    B = "TCTGACCAACCACAGGAAAG"      # BRCA1'e gore reverse (urun 443 bp)

    d = c.post("/evaluate", json={"forward": A, "reverse": B,
                                  "assembly": "GRCh38"}).get_json()
    urun = [o for o in d.get("products") or [] if o["combination"] == "R+F"]
    ok("genin yonunde: genomda R+F urunu bulunur", bool(urun),
       f"{urun[0]['size']} bp" if urun else "")
    ok("  ...karar 'iyi'", d.get("verdict") == "iyi", f"-> {d.get('verdict')}")
    metin = " ".join(f["text"] for f in (d.get("findings") or []))
    ok("  ...gercek urun yan urun sayilmaz", "yan ürünü" not in metin,
       "R+F yan urun diye sayiliyordu")

    d = c.post("/evaluate", json={"forward": B, "reverse": A,
                                  "assembly": "GRCh38"}).get_json()
    ok("ters sirada 'sorun' DEMEZ", d.get("verdict") != "sorun", f"-> {d.get('verdict')}")
    metin = " ".join(f["text"] for f in (d.get("findings") or []))
    ok("  ...rollerin yer degistigi (BRCA1'e gore) soylenir",
       "yer değişmiş" in metin and "BRCA1" in metin)


def test_rna_degerlendirme(c):
    baslik("RNA / cDNA degerlendirmesi")
    # ASIL GEREKCE: ekson SINIRINA oturan primer genomda butun halde bulunmaz.
    # DNA modu boyle bir cifte "hicbir urun vermiyor" der - yanlis alarm.
    d = c.post("/design_cdna", json={
        "assembly": "GRCh38", "acc": "NM_007294", "c_position": "c.1000",
        "params": {"junction_overlap": True}}).get_json()
    if not (d.get("pairs") or []):
        atla("RNA degerlendirmesi", "sinir ustu primer tasarlanamadi")
        return
    pr = d["pairs"][0]
    F, R = pr["forward"]["sequence"], pr["reverse"]["sequence"]

    dna = c.post("/evaluate", json={"forward": F, "reverse": R,
                                    "assembly": "GRCh38"}).get_json()
    ok("DNA modu sinir ustu primere yanlis alarm veriyor (beklenen)",
       dna.get("verdict") == "sorun", "-> bu yuzden RNA modu var")

    r = c.post("/evaluate_cdna", json={"forward": F, "reverse": R,
                                       "acc": "NM_007294", "assembly": "GRCh38"})
    j = r.get_json()
    ok("RNA modu istegi basarili", r.status_code == 200,
       f"-> {(j.get('error') or '')[:50]}")
    if r.status_code != 200:
        return
    ok("  ...'sorun' demiyor", j.get("verdict") != "sorun", f"-> {j.get('verdict')}")
    ok("  ...her iki primer de transkriptte bulundu",
       all(j["placement"].get(a) for a in j["primers"]))
    ok("  ...sinir ustu primer tespit edildi",
       any((j["placement"].get(a) or {}).get("spans_junction") for a in j["primers"]))
    u = j.get("product") or {}
    ok("  ...cDNA urun boyu hesaplandi", u.get("cdna_size", 0) > 0,
       f"{u.get('cdna_size')} bp")
    ok("  ...gDNA urun boyu da hesaplandi", (u.get("gdna_size") or 0) > 0,
       f"{u.get('gdna_size')} bp")
    ok("  ...gDNA bandi cDNA'dan buyuk (intron kapsiyor)",
       (u.get("gdna_size") or 0) > u.get("cdna_size", 0))

    # Tek ekzon icinde kalan urun: gDNA kontaminasyonu AYNI bandi verir
    d2 = c.post("/design_cdna", json={
        "assembly": "GRCh38", "acc": "NM_007294", "c_position": "c.2000",
        "params": {"junction_flanking": False}}).get_json()
    if d2.get("pairs"):
        F2, R2 = d2["pairs"][0]["forward"]["sequence"], d2["pairs"][0]["reverse"]["sequence"]
        j2 = c.post("/evaluate_cdna", json={"forward": F2, "reverse": R2,
                                            "acc": "NM_007294",
                                            "assembly": "GRCh38"}).get_json()
        u2 = j2.get("product") or {}
        ok("tek ekzon icindeki urun: gDNA bandi ayni",
           u2.get("gdna_size") == u2.get("cdna_size"), f"{u2.get('cdna_size')} bp")
        metin = " ".join(f["text"] for f in (j2.get("findings") or []))
        ok("  ...kontaminasyon ayirt edilemez uyarisi var",
           "ayırt edilemez" in metin)

        # Roller ters
        j3 = c.post("/evaluate_cdna", json={"forward": R2, "reverse": F2,
                                            "acc": "NM_007294",
                                            "assembly": "GRCh38"}).get_json()
        ok("roller ters takilinca tespit edilir", j3.get("roles_swapped") is True)

        # Yanlis transkript
        j4 = c.post("/evaluate_cdna", json={"forward": F2, "reverse": R2,
                                            "acc": "NM_000546",
                                            "assembly": "GRCh38"}).get_json()
        ok("yanlis transkriptte 'sorun' der", j4.get("verdict") == "sorun")

    r = c.post("/evaluate_cdna", json={"forward": F, "reverse": R,
                                       "assembly": "GRCh38"})
    ok("NM_ verilmezse reddedilir", r.status_code == 400)


def test_amplikon(c):
    baslik("Amplikon (cogaltilan dizi)")
    import random

    def rc(s):
        return s[::-1].translate(str.maketrans("ACGT", "TGCA"))

    def dogrula(ad, d, yer="pairs"):
        o = (d.get(yer) or [None])[0]
        a = (o or {}).get("amplicon")
        if not a:
            ok(f"{ad}: amplikon var", False, "-> yok")
            return None
        F = o["forward"]["sequence"]
        R = o["reverse"]["sequence"]
        boy_ok = a["length"] == len(a["sequence"]) == o["product_size"]
        # ASIL KONTROL: amplikon gercekten forward primerle baslayip reverse'un
        # ters tumleyeniyle bitmeli. Yanlis dilimleme burada yakalanir.
        bas = a["sequence"][:len(F)] == F
        son = a["sequence"][-len(R):] == rc(R)
        ok(f"{ad}: boy tutarli", boy_ok, f"{a['length']} bp")
        ok(f"{ad}: forward ile basliyor", bas)
        ok(f"{ad}: reverse'un ters tumleyeniyle bitiyor", son)
        ok(f"{ad}: primer ofsetleri dogru",
           a["forward_span"] == [0, len(F) - 1] and
           a["reverse_span"] == [a["length"] - len(R), a["length"] - 1])
        return a

    dogrula("DNA", c.post("/design", json={
        "assembly": "GRCh38", "chrom": "17", "position": 43093000,
        "params": {}}).get_json())
    dogrula("cDNA", c.post("/design_cdna", json={
        "assembly": "GRCh38", "acc": "NM_007294", "c_position": "c.1000",
        "params": {}}).get_json())

    random.seed(7)
    dizi = "".join(random.choice("ACGT") for _ in range(900))
    dogrula("tek dizi", c.post("/design_sequence", json={
        "sequence": dizi, "target": "450", "params": {}}).get_json())

    # Iki dizi modu: aradaki BILINMEYEN bolge N ile doldurulur ve isaretlenir
    d = c.post("/design_sequence_pair", json={
        "forward": dizi[:400], "reverse": dizi[500:],
        "params": {"gap": 120}}).get_json()
    a = dogrula("iki dizi", d)
    if a:
        ok("iki dizi: bilinmeyen bolge isaretli", a.get("unknown_length") == 120,
           f"-> {a.get('unknown_span')}")
        ok("  ...dizide o kadar N var", a["sequence"].count("N") == 120)

    # Degerlendir / RNA: urun dizisi + ekson siniri ofsetleri
    j = c.post("/evaluate_cdna", json={
        "forward": "AACTTATTGCAGTGTGGGAG", "reverse": "TCACTTCTGGAAAACCACTC",
        "acc": "NM_007294", "assembly": "GRCh38"}).get_json()
    u = j.get("product") or {}
    ok("Degerlendir/RNA: urun dizisi var", bool(u.get("sequence")),
       f"{len(u.get('sequence') or '')} bp")
    ok("  ...boyu ilan edilen boyla ayni", len(u.get("sequence") or "") == u.get("cdna_size"))
    # NOBETCI: arayuzun amplikon gostericisi 'length' alanini bekliyor; RNA
    # urununde yalnizca 'cdna_size' vardi ve dugmeye basinca hata veriyordu.
    ok("  ...'length' alani var (arayuz bunu kullaniyor)",
       u.get("length") == u.get("cdna_size"), f"-> {u.get('length')}")
    ok("  ...ekson siniri ofsetleri verildi", bool(u.get("junction_offsets")),
       f"-> {u.get('junction_offsets')}")

    # Degerlendir / DNA: ongorulen urunlerin gercek genomik dizisi
    j = c.post("/evaluate", json={"forward": "TCTGACCAACCACAGGAAAG",
                                  "reverse": "AGTTAGCACTCTAGGGAAGG",
                                  "assembly": "GRCh38"}).get_json()
    ilk = (j.get("products") or [None])[0]
    a = (ilk or {}).get("amplicon")
    ok("Degerlendir/DNA: urun dizisi cekildi", bool(a), f"{(a or {}).get('length')} bp")
    if a:
        ok("  ...boyu urun boyuyla ayni", a["length"] == ilk["size"])


def test_hedef_urun(c):
    baslik("Hedef urun isaretlemesi")
    # NOBETCI: hedef urun "yuksek risk" diye kirmiziya boyaniyordu. Kullanici
    # cifti zaten o bolgeyi cogaltmak icin tasarlamis; risk kavrami ISTENMEYEN
    # urunler icindir. Ayrica hedef risk listesinden cikinca "bu cift hicbir
    # urun vermiyor" yanlis alarmi olusmustu - o da burada bekleniyor.
    d = c.post("/evaluate", json={"forward": "GGCTCCATGAGGGTGTTT",
                                  "reverse": "TCCAGGGTCCTCAGTTTCT",
                                  "assembly": "GRCh38"}).get_json()
    hedef = [o for o in (d.get("products") or []) if o.get("intended")]
    ok("hedef urun isaretlendi", len(hedef) == 1,
       f"{hedef[0]['size']} bp chr{hedef[0]['chrom']}" if hedef else "yok")
    if hedef:
        ok("  ...riski 'hedef', 'yuksek' degil", hedef[0]["risk"] == "hedef",
           f"-> {hedef[0]['risk']}")
        ok("  ...tam eslesme", hedef[0]["mismatch_total"] == 0)
        ok("  ...listenin basinda", d["products"][0].get("intended") is True)
    metin = " ".join(f["text"] for f in (d.get("findings") or []))
    ok("  ...'hicbir urun vermiyor' YANLIS alarmi yok",
       "hiçbir ürün vermiyor" not in metin)
    ok("  ...karar 'sorun' degil", d.get("verdict") != "sorun", f"-> {d.get('verdict')}")

    # Kesilme/eleme sessiz kalmamali
    ok("urun sayisi bildiriliyor", isinstance(d.get("product_count"), int),
       f"toplam {d.get('product_count')}, gosterilen {len(d.get('products') or [])}")
    # NOBETCI: 3' uc sarti gevseyince arama penceresi genisledi; suzgec olmadan
    # yuzlerce satir cikip asil onemli olani gizliyordu. Baglanma olasiligi
    # dusuk urunler listelenmez ama SAYISI soylenir - sessizce yutulmaz.
    ok("dusuk olasilikli urunler elendi", (d.get("products_low") or 0) > 0,
       f"{d.get('products_low')} elendi")
    ok("  ...elendigi bulgularda soyleniyor", "olasılığı düşük" in metin)
    ok("  ...listelenenlerin hicbiri 'dusuk' degil",
       all(o["risk"] != "dusuk" for o in (d.get("products") or [])))
    # NOBETCI: "gostermemek" ile "yok saymak" ayni sey degil - dusuk olasilikli
    # urunler arayuzde dugmeyle acilabilsin diye AYRI listede donulmeli.
    dusuk = d.get("products_low_items") or []
    ok("  ...dusuk urunler istege bagli acilabilsin diye donuluyor",
       len(dusuk) > 0, f"{len(dusuk)} kayit")
    ok("  ...hepsi gercekten 'dusuk'", all(o["risk"] == "dusuk" for o in dusuk))
    ok("  ...onlarin da urun dizisi var", any(o.get("amplicon") for o in dusuk))

    # Ozgulluk ucu de ayni sozlesmeyi vermeli
    s = c.post("/specificity", json={
        "assembly": "GRCh38", "forward": "GGCTCCATGAGGGTGTTT",
        "reverse": "TCCAGGGTCCTCAGTTTCT",
        "expected": {"chrom": "19", "start": 39502694, "end": 39503300}}).get_json()
    ok("ozgullukte hedef ayirt edildi", s.get("intended_found") is True)
    ok("  ...dusuk olasiliklilar ayri listede", len(s.get("offtargets_low") or []) > 0,
       f"{s.get('low_hidden')} kayit")
    ok("  ...listelenenlerin hicbiri 'dusuk' degil",
       all(o["risk"] != "dusuk" for o in (s.get("offtargets") or [])))


def test_seed_kor_noktasi(c, engine):
    baslik("3' uc (seed) siniri")
    import specificity as S
    # NOBETCI: seed 8 iken, kendi uyumsuzluk butcemize (<=4) uyan urunlerin
    # ucte ikisi sirf 3' uc sarti yuzunden hic gorulmuyordu. Olculdu:
    # seed 8 -> 15 urun, seed 6 -> 49 urun (ayni cift, ayni butce).
    ok("varsayilan seed 6", S.SPEC_DEFAULTS["seed_len"] == 6,
       f"-> {S.SPEC_DEFAULTS['seed_len']}")
    yol = engine.GENOME_PATHS.get("GRCh38")
    if not yol:
        return
    F, R = "GGCTCCATGAGGGTGTTT", "TCCAGGGTCCTCAGTTTCT"
    sayilar = {}
    for seed in (8, 6):
        p = {**S.SPEC_DEFAULTS, "seed_len": seed, "max_offtarget_product": 5000}
        sayilar[seed] = len(S.pair_products(S.scan_genome(yol, F, R, p), 5000))
    ok("seed 6, seed 8'den daha fazla urun buluyor",
       sayilar[6] > sayilar[8], f"seed8={sayilar[8]}  seed6={sayilar[6]}")


def test_kirpilmis_liste_bulgulari(c, engine):
    baslik("Tekrar dizisindeki primer - bulgular tam listeden")
    # NOBETCI (2026-10-01, rastgele testte bulundu): forward bir Alu dizisinde
    # (genomda 1022 tam yer). Yuzlerce F+F/R+R yan urunu 20 satirlik tabloyu
    # dolduruyordu; bulgular o tablodan sayildigi icin GERCEK F+R urunu
    # (chr11, 493 bp, reverse'te 2 uyumsuzluk) varken "beklenen yonde hicbir
    # urun vermiyor" (sorun) deniyor, yan urun sayisi "20" yaziliyordu.
    if not engine.GENOME_PATHS.get("GRCh37"):
        atla("Tekrar dizisindeki primer", "GRCh37 genomu yok")
        return
    F, R = "GAATCACTTGAGGCCAGGAG", "CCACTACTTACAGGTTATTC"
    t0 = time.time()
    d = c.post("/evaluate", json={"forward": F, "reverse": R,
                                  "assembly": "GRCh37"}).get_json()
    ok("istek basarili", "error" not in d,
       f"({time.time() - t0:.1f} sn) {d.get('error', '')}")
    metin = " ".join(f["text"] for f in (d.get("findings") or []))
    ok("'beklenen yonde urun yok' YANLIS alarmi yok", "hiçbir ürün vermiyor" not in metin)
    urunler = d.get("products") or []
    gercek = [o for o in urunler if o["combination"] in ("F+R", "R+F")
              and str(o["chrom"]) == "11" and o["start"] == 58223311 and o["size"] == 493]
    ok("  ...gercek F+R urunu tabloda", bool(gercek),
       f"F{gercek[0]['mismatch_forward']}/R{gercek[0]['mismatch_reverse']}" if gercek else "")
    cift_mi = [o["combination"] in ("F+R", "R+F") for o in urunler]
    ok("  ...ciftin urunleri yan urunlerden once", cift_mi == sorted(cift_mi, reverse=True))
    n_yan = d.get("side_product_count") or 0
    ok("yan urun sayisi gosterim sinirina takilmiyor", n_yan > len(urunler),
       f"{n_yan:,} yan urun, tabloda {len(urunler)} satir")
    # Turkce bulguda binlik ayirici nokta (v0.8.66)
    ok("  ...bulguda tam sayi yaziyor", f"{n_yan:,}".replace(",", ".") in metin)
    # NOBETCI (2026-10-07): 1022 yere tam oturan primer en fazla "uyari" aliyordu.
    tekrar = [f for f in (d.get("findings") or []) if "tekrar dizisinde" in f["text"]]
    ok("tekrar dizisindeki primer 'sorun' sayilir",
       bool(tekrar) and tekrar[0]["level"] == "sorun" and d.get("verdict") == "sorun",
       f"-> {d.get('verdict')}")


def test_kromozom_disi_koordinat(c, engine):
    baslik("Kromozom disi koordinat - internete sessizce gidilmez")
    # NOBETCI (2026-10-01, rastgele testte bulundu): kromozom sonunu asan bir
    # koordinatta yerel okuma bos donuyor, kod SESSIZCE Ensembl'e (internete)
    # gidiyordu; cevrimdisiyken "Beklenmeyen hata" cikiyordu. Negatif/sifir
    # koordinat da primer3'e kadar gidip 500 veriyordu.
    import requests as _rq
    asm = "GRCh38" if engine.GENOME_PATHS.get("GRCh38") else "GRCh37"
    fa = engine._open_fasta(engine.GENOME_PATHS[asm])
    L = len(fa[engine._fasta_key(fa, "1")])
    istekler = []
    eski_get = engine.requests.get

    def _kaydet(url, *a, **k):
        istekler.append(url)
        raise _rq.ConnectionError("test: internet yok")

    engine.requests.get = _kaydet
    try:
        r = c.post("/design", json={"assembly": asm, "chrom": "1", "position": L + 5000})
        hata = (r.get_json() or {}).get("error", "")
        ok("kromozom sonunu asan koordinat 400 ile reddedilir", r.status_code == 400,
           f"-> {r.status_code}")
        ok("  ...sebep ve kromozom boyu soylenir",
           "kromozomun dışında" in hata and f"{L:,}".replace(",", ".") in hata, hata[:70])
        ok("  ...internete cikilmaz", not istekler, str(istekler[:1]))
        for poz in (0, -5):
            r = c.post("/design", json={"assembly": asm, "chrom": "1", "position": poz})
            ok(f"koordinat {poz} 400 ile reddedilir", r.status_code == 400
               and "1'den küçük" in (r.get_json() or {}).get("error", ""),
               f"-> {r.status_code}")
        dizi, kaynak = engine.get_sequence(asm, "1", L - 99, L + 600)
        ok("kromozom sonuna tasan aralik sonda kirpilir",
           len(dizi) == 100 and kaynak == "local", f"{len(dizi)} bp, {kaynak}")
        try:
            engine.get_sequence(asm, "1", L + 10, L + 500)
            ok("tamamen disaridaki aralik hata verir", False, "hata vermedi")
        except engine.PrimerError:
            ok("tamamen disaridaki aralik hata verir", True)
        except Exception as e:
            ok("tamamen disaridaki aralik hata verir", False, repr(e)[:70])
        ok("  ...hicbir adimda internete cikilmadi", not istekler, str(istekler[:1]))
    finally:
        engine.requests.get = eski_get


def test_gen_adi_yerelden(c, engine):
    baslik("Gen adindan kromozom - yerel tablodan")
    # NOBETCI (2026-10-07): gen adi her seferinde Ensembl'e soruluyordu; yerel
    # genomla calisirken bile istek internete cikiyor, cevrimdisiyken "Beklenmeyen
    # hata" veriyordu. Artik yerel transkript tablosundan (refGene) cozuluyor;
    # Ensembl yalnizca tablo indirilmemisse (bilincli yedek).
    import requests as _rq
    import transcripts as T
    asm = "GRCh38"
    if not T.ANNOT_PATHS.get(asm):
        atla("Gen adindan kromozom", "GRCh38 transkript tablosu yok")
        return
    istekler = []
    eski_get = engine.requests.get

    def _kaydet(url, *a, **k):
        istekler.append(url)
        raise _rq.ConnectionError("test: internet yok")

    engine.requests.get = _kaydet
    if hasattr(engine.lookup_gene, "cache_clear"):
        engine.lookup_gene.cache_clear()
    try:
        c.post("/design", json={"assembly": asm, "chrom": "", "gene": "TP53",
                                "position": 7675000})
        ok("/design gen adiyla: internete cikilmaz", not istekler, str(istekler[:1]))
        r = c.post("/design", json={"assembly": asm, "chrom": "", "gene": "MLL",
                                    "position": 7675000})
        ok("  ...bilinmeyen gen 400 + aciklama", r.status_code == 400
           and "bulunamadı" in (r.get_json() or {}).get("error", ""), f"-> {r.status_code}")

        g = engine.gen_konumu("tp53", asm)
        ok("TP53 yerelden chr17'ye cozulur", g["chrom"] == "17" and g["source"] == "local",
           f"-> chr{g['chrom']} ({g['source']})")
        ok("PAR geni (SHOX) X'e cozulur", engine.gen_konumu("SHOX", asm)["chrom"] == "X")
        try:
            engine.gen_konumu("MIR6859-1", asm)
            ok("birden fazla kromozomdaki ad kromozom ister", False, "hata vermedi")
        except engine.PrimerError as e:
            ok("birden fazla kromozomdaki ad kromozom ister",
               "birden fazla kromozom" in str(e), str(e)[:60])

        n = engine.gen_uzaklik_notu("TP53", g, "17", 7_577_120, asm)   # hg19 ekson 8
        ok("hg19 koordinati GRCh38'de genin disinda -> uyari",
           bool(n) and "dışında" in n, (n or "")[:60])
        ok("  ...gen icindeki koordinatta uyari yok",
           engine.gen_uzaklik_notu("TP53", g, "17", 7_675_000, asm) is None)
        ok("  ...yanlis kromozom uyarilir",
           "chr17" in (engine.gen_uzaklik_notu("TP53", g, "5", 7_675_000, asm) or ""))
        ok("hicbir adimda internete cikilmadi", not istekler, str(istekler[:1]))

        # Tablo yoksa Ensembl'e duser (bilincli yedek); cevrimdisiysa anlasilir hata
        eski_yol, eski_idx = T.ANNOT_PATHS[asm], T._INDEX_CACHE.pop(asm, None)
        T.ANNOT_PATHS[asm] = ""
        try:
            engine.gen_konumu("TP53", asm)
            ok("tablo yoksa Ensembl'e duser", False, "hata vermedi")
        except engine.PrimerError as e:
            ok("tablo yoksa Ensembl'e duser, cevrimdisiysa anlasilir hata",
               bool(istekler) and "internete ulaşılamadı" in str(e), str(e)[:60])
        finally:
            T.ANNOT_PATHS[asm] = eski_yol
            if eski_idx is not None:
                T._INDEX_CACHE[asm] = eski_idx
    finally:
        engine.requests.get = eski_get
        if hasattr(engine.lookup_gene, "cache_clear"):
            engine.lookup_gene.cache_clear()


def test_primer3_saglik(c, engine):
    baslik("primer3 yuklenemezse anlasilir uyari")
    # NOBETCI (2026-10-10): Windows Akilli Uygulama Denetimi primer3'un dosyasini
    # engelledi; motor normal acildi, gosterge yesildi, kullanici tasarim/
    # Degerlendir'e basinca "module 'primer3' has no attribute 'calc_tm'" gordu.
    d = c.get("/health").get_json()
    ok("/health primer3 durumunu bildirir", "primer3" in d, f"-> {d.get('primer3')}")
    tur = engine.primer3_hata_turu
    ok("sebep: Akilli Uygulama Denetimi (TR Windows)", tur(
        "ImportError: DLL load failed while importing thermoanalysis: Uygulama Denetimi "
        "ilkesi bu dosyayı engelledi.") == "sac")
    ok("  ...(EN Windows)", tur("ImportError: DLL load failed while importing "
                               "thermoanalysis: An Application Control policy has blocked "
                               "this file.") == "sac")
    ok("sebep: eksik parametre dosyalari", tur(
        "OSError: Could not load thermodynamic config file C:/x/primer3_config/") == "eksik")
    ok("sebep: diger", tur("ImportError: No module named primer3") == "diger")

    # Paketli exe'de asil soru bu: PyInstaller primer3'u ve parametre dosyalarini aldi mi
    ok("primer3 bu motorda yuklu", (d.get("primer3") or {}).get("ok") is True,
       f"-> {(d.get('primer3') or {}).get('message')}")

    # Hata durumunu taklit et (bu makinede primer3 artik calisiyor)
    if HTTP:
        atla("primer3 hata taklidi", "HTTP modu: motorun ici degistirilemez")
        return
    eski = dict(engine.PRIMER3_DURUM)
    engine.PRIMER3_DURUM.update({"ok": False, "tur": "sac", "ham": "ImportError: ..."})
    try:
        h = c.get("/health").get_json()["primer3"]
        ok("taklit: /health ok=false + Turkce aciklama", h["ok"] is False
           and "Akıllı Uygulama Denetimi" in (h["message"] or ""), (h["message"] or "")[:60])
        h = c.get("/health?lang=en").get_json()["primer3"]
        ok("  ...Ingilizce aciklama", "Smart App Control" in (h["message"] or ""))
        for uc, govde in (("/design", {"assembly": "GRCh38", "chrom": "17", "position": 7675000}),
                          ("/evaluate", {"forward": "GCTGAGGAAGTTGGTGACCA"})):
            r = c.post(uc, json=govde)
            ok(f"  ...{uc} 503 + aciklama (primer3'e ulasmadan)", r.status_code == 503
               and "Akıllı Uygulama Denetimi" in (r.get_json() or {}).get("error", ""),
               f"-> {r.status_code}")
        if engine.GENOME_PATHS.get("GRCh38"):
            r = c.post("/specificity", json={"assembly": "GRCh38",
                                             "forward": "GGCTCCATGAGGGTGTTT",
                                             "reverse": "TCCAGGGTCCTCAGTTTCT"})
            ok("  ...ozgulluk taramasi yine calisir (primer3 kullanmaz)",
               r.status_code == 200, f"-> {r.status_code}")
    finally:
        engine.PRIMER3_DURUM.clear()
        engine.PRIMER3_DURUM.update(eski)


def test_uc_durumlar(c, engine):
    baslik("Kromozom ucu ve uzun dizi - anlasilir hata")
    # NOBETCI (2026-10-08, gercek primer3 ile rastgele testte bulundu): kromozom
    # sonuna cok yakin varyantta hedef bolge sablonun disina tasiyor, primer3
    # "TARGET beyond end of sequence" deyip 500 veriyordu. Degerlendir'e 60
    # bazdan uzun dizi yapistirilinca da primer3'un termodinamik hesabi 500
    # veriyordu. Ikisi de kullaniciya "Beklenmeyen hata" olarak gorunuyordu.
    asm = "GRCh37" if engine.GENOME_PATHS.get("GRCh37") else "GRCh38"
    fa = engine._open_fasta(engine.GENOME_PATHS[asm])
    L = len(fa[engine._fasta_key(fa, "1")])
    for poz, yer in ((L - 20, "sonuna"), (30, "başına")):
        r = c.post("/design", json={"assembly": asm, "chrom": "1", "position": poz})
        hata = (r.get_json() or {}).get("error", "")
        ok(f"kromozom {yer} yakin varyant 400 + aciklama",
           r.status_code == 400 and f"{yer} çok yakın" in hata,
           f"-> {r.status_code} {hata[:60]}")
    r = c.post("/evaluate", json={"forward": "ACGT" * 15 + "A", "assembly": asm})
    ok("61 nt'lik dizi 400 + 'cok uzun'", r.status_code == 400
       and "çok uzun" in (r.get_json() or {}).get("error", ""), f"-> {r.status_code}")
    r = c.post("/evaluate", json={"forward": "GCTGAGGAAGTTGGTGACCATCAGGCTGCTGTTCTCCATC"
                                             "AAGGGTGAAGAGGAATCCCA", "assembly": "yok"})
    ok("  ...60 nt kabul edilir", r.status_code == 200, f"-> {r.status_code}")


def test_tekrar_dizisi_siniri(c, engine):
    baslik("Poli-A / tekrar dizisi - bellek siniri")
    # NOBETCI (2026-10-01): poli-A ciftiyle ozgulluk taramasi 23,8 GB bellege
    # cikti ve bitmedi (makinede 15,6 GB) - kullanicinin bilgisayarini
    # kilitleyebiliyordu. Sinir parca basinaydi; artik genel ve asilinca
    # "tekrar dizisi, tahmin yapilmadi" deniyor. Duzeltmeden sonra ~5 sn, ~0,6 GB.
    if not engine.GENOME_PATHS.get("GRCh37"):
        atla("Tekrar dizisi siniri", "GRCh37 genomu yok")
        return
    F, R = "A" * 20, "T" * 20
    t0 = time.time()
    d = c.post("/evaluate", json={"forward": F, "reverse": R,
                                  "assembly": "GRCh37"}).get_json()
    sure = time.time() - t0
    ok("poli-A degerlendirmesi makul surede biter (<60 sn)", sure < 60, f"{sure:.1f} sn")
    ov = d.get("overflow") or {}
    ok("  ...tasma bildirilir", ov.get("forward") and ov.get("reverse"), f"-> {ov}")
    metin = " ".join(f["text"] for f in (d.get("findings") or []))
    ok("  ...sebebi soylenir", "tekrar dizisine" in metin and "en az" in metin)
    ok("  ...'urun yok' denmez, tahmin yapilmadi", not d.get("products")
       and "hiçbir ürün vermiyor" not in metin)
    ok("  ...karar 'sorun'", d.get("verdict") == "sorun", f"-> {d.get('verdict')}")
    try:
        import ctypes
        from ctypes import wintypes

        class _PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (ad, ctypes.c_size_t) for ad in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        k = ctypes.WinDLL("kernel32")
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC),
                                              wintypes.DWORD]
        m = _PMC()
        m.cb = ctypes.sizeof(_PMC)
        k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(m), m.cb)
        mb = m.PeakPagefileUsage / 1e6
        ok("  ...bellek sinirli kaldi (<3 GB)", mb < 3000, f"tepe {mb:,.0f} MB")
    except Exception as e:      # Windows disi ortam
        atla("bellek olcumu", str(e)[:60])
    s = c.post("/specificity", json={"assembly": "GRCh37", "forward": F, "reverse": R})
    ok("ozgulluk ucu de anlasilir hatayla doner", s.status_code == 400
       and "tekrar dizisine" in (s.get_json() or {}).get("error", ""),
       f"-> {s.status_code}")


def test_havuz_olagan_kapanir(c, engine):
    baslik("Erken biten / durdurulan tarama havuzu olagan yoldan kapanir")
    # NOBETCI (2026-11-09): poli-A ciftinde (A x20 / T x20) iki primer de ilk parcada tasinca tarama
    # erken bitiyordu ve `with mp.Pool` cikisi terminate() ile iscileri ~10 MB'lik sonuclarini
    # gonderirken olduruyordu. Windows'ta sonuc is parcacigi yarim mesaji sonsuza dek bekledi: exe
    # testinde /specificity 900 sn cevapsiz kaldi; kaynakta 41 erken bitiste 1 takilma (yigin:
    # _terminate_pool -> result_handler.join). Tarama kilidi (_TARAMA) birakilmadigi icin sonraki
    # butun taramalar da bekliyordu. Ayni yol en iyi Ozgul cift aramasinin durdurulmasinda da vardi.
    # Takilma aralikli; burada sebebi denetlenir: terminate() aninda canli isci kalmamali.
    if HTTP:
        return atla("Havuz kapanisi", "HTTP modu: motorun ici izlenemez")
    if not (engine.GENOME_PATHS.get("GRCh37") and engine.GENOME_PATHS.get("GRCh38")):
        return atla("Havuz kapanisi", "GRCh37 / GRCh38 genomu yok")
    import multiprocessing.pool as mpp
    import specificity as S
    import cok_tarama as CT
    kayit = []
    eski = mpp.Pool.terminate

    def izle(self):
        kayit.append((self._state, sum(1 for p in self._pool if p.is_alive())))
        return eski(self)

    class Dur(Exception):
        pass

    def iptal():
        raise Dur()

    mpp.Pool.terminate = izle
    try:
        t0 = time.time()
        isabet = S.scan_genome(engine.GENOME_PATHS["GRCh37"], "A" * 20, "T" * 20, dict(S.SPEC_DEFAULTS))
        sure = time.time() - t0
        poli, kayit[:] = list(kayit), []
        durdu = False
        try:
            CT.Tarama(engine.GENOME_PATHS["GRCh38"], ["AGGCTGAGGCAGGAGAATGG", "ACTCACGGGTAGGAGGAGAG"],
                      iptal=iptal)
        except Dur:
            durdu = True
        kopya = list(kayit)
    finally:
        mpp.Pool.terminate = eski
    temiz = lambda k: bool(k) and all(st != "RUN" and canli == 0 for st, canli in k)
    ok("poli-A taramasi erken biter (iki primer de tasar)", set(isabet.tasan) == {"F", "R"},
       f"{sorted(isabet.tasan)} {sure:.1f} sn")
    ok("  ...havuz sonuclar okunduktan sonra kapanir (terminate aninda canli isci yok)", temiz(poli), str(poli))
    ok("Durdurulan cok primerli tarama (en iyi Ozgul cift) da olagan yoldan kapanir",
       durdu and temiz(kopya), f"durdu={durdu} {kopya}")
    serbest = S._TARAMA.acquire(timeout=5)
    if serbest:
        S._TARAMA.release()
    ok("  ...tarama kilidi birakilir", serbest)


def test_es_kopya_hedef(c, engine):
    baslik("Es kopyalar (segmental duplikasyon)")
    # NOBETCI (2026-10-07): cift chr20'de birebir ayni iki kopyaya tam oturuyor.
    # Kopyalardan biri keyfi olarak "hedef", digeri "yuksek risk" yaziliyor,
    # karar yalnizca "uyari" oluyordu. Hangisinin kastedildigi bilinemez;
    # ikisi de hedef adayi gosterilmeli ve durum "sorun" olarak soylenmeli.
    if not engine.GENOME_PATHS.get("GRCh37"):
        atla("Es kopyalar", "GRCh37 genomu yok")
        return
    d = c.post("/evaluate", json={"forward": "GATCTGCCTTTGAGGTCTGG",
                                  "reverse": "CCACCATTGTCCAGTCTGTC",
                                  "assembly": "GRCh37"}).get_json()
    hedef = [o for o in (d.get("products") or []) if o.get("intended")]
    ok("iki kopya da hedef adayi", len(hedef) == 2 and d.get("target_count") == 2,
       ", ".join(f"chr{o['chrom']}:{o['start']}" for o in hedef))
    ok("  ...hicbiri 'yuksek risk' yazilmaz", all(o["risk"] == "hedef" for o in hedef))
    metin = " ".join(f["text"] for f in (d.get("findings") or []) if f["level"] == "sorun")
    ok("  ...kopyalarin ayirt edilemedigi 'sorun' olarak soylenir",
       "ayrı yerde TAM eşleşen" in metin)
    ok("  ...karar 'sorun'", d.get("verdict") == "sorun", f"-> {d.get('verdict')}")


def test_yuksek_riskli_yan_urun_karari(c):
    baslik("Hedef + yuksek riskli yan urun -> 'sorun'")
    import evaluate as E
    # NOBETCI (2026-10-07): hedefin yaninda toplam <=2 uyumsuzlukla oturan ek
    # bir urun jelde fazladan bant demek; karar en fazla "uyari" oluyordu.
    # Hedef YOKKEN sertlestirilmez: o zaman en iyi urun muhtemelen yazim hatali
    # hedefin kendisidir. Genom gerektirmez; bulgu mantigi dogrudan sinanir.
    m = {"tm": 60.0, "gc": 50.0, "hairpin_tm": 0.0, "poly_x": 2, "gc_clamp": True,
         "gc_last5": 2}
    yer = {"chrom": "1", "five_prime": 1000, "three_prime": 1019, "orientation": "+",
           "mismatch": 0, "snps": []}
    hedef = {"chrom": "1", "start": 1000, "end": 1300, "size": 301, "combination": "F+R",
             "risk": "hedef", "intended": True, "mismatch_total": 0}
    yan = {"chrom": "5", "start": 5000, "end": 5400, "size": 401, "combination": "F+R",
           "risk": "yuksek", "mismatch_total": 1}

    def karar(urunler, n_hedef, n_yuksek):
        r = {"genome_used": True, "primers": {"forward": m, "reverse": m},
             "pair": {"delta_tm": 0.3, "hetero_dimer_tm": 0.0},
             "sites": {"forward": [yer], "reverse": [yer]},
             "counts": {"forward": {"perfect": 1, "good": 1},
                        "reverse": {"perfect": 1, "good": 1}},
             "products": urunler, "geometry": None, "overflow": {},
             "target_count": n_hedef, "pair_product_count": len(urunler),
             "side_product_count": 0, "high_risk_count": n_yuksek,
             "pair_roles_swapped": False, "pair_first_size": 301, "products_low": 0}
        return E._findings(r, dict(E.EVAL_DEFAULTS))

    b = karar([hedef, yan], 1, 1)
    ok("hedef + yuksek riskli yan urun -> 'sorun'",
       any(f["level"] == "sorun" and "yüksek riskli" in f["text"] for f in b))
    b = karar([dict(yan)], 0, 1)
    ok("  ...hedef yokken sertlestirilmez",
       not any("yüksek riskli" in f["text"] for f in b))
    b = karar([hedef], 1, 0)
    ok("  ...tek temiz hedefte 'sorun' yok", not any(f["level"] == "sorun" for f in b))


def test_v051_genomsuz(c):
    baslik("v0.5.1 - dimer, yazim bicimi, bicimsiz ayar (genom gerekmez)")
    import engine as EN
    # NOBETCI (2026-10-10 bozuk primer paneli): 3' uclari 8 baz tamamlayici iki
    # primer 0/20 yakalaniyordu - termodinamik dimer Tm'i (14-26 °C) 45 °C
    # esiginin altinda kaliyordu. Artik Primer-BLAST birimindeki legacy skor.
    F = "TTGACCTGAAGTCCAGTGCG"
    R = "AGCTATGGCATC" + "CGCACTGG"              # 3' ucu F'nin son 8 bazinin tumleyeni
    d = c.post("/evaluate", json={"forward": F, "reverse": R, "assembly": "yok"}).get_json()
    ok("3' primer-dimer skoru hesaplanir", (d.get("pair") or {}).get("compl_end", 0) > 3,
       f"-> {(d.get('pair') or {}).get('compl_end')}")
    metin = " ".join(f["text"] for f in d.get("findings") or [])
    ok("  ...ve uyarilir", "3' uçları birbirine tamamlayıcı" in metin)
    F2 = "TTCAGTCAGTTACA" + "GCATATGC"             # 3' ucu 8 bazlik palindrom
    d = c.post("/evaluate", json={"forward": F2, "assembly": "yok"}).get_json()
    m = (d.get("primers") or {}).get("forward") or {}
    ok("kendi 3' ucuna tamamlayici primer uyarilir", (m.get("self_end") or 0) > 3 and
       any("3' ucu kendine tamamlayıcı" in f["text"] for f in d.get("findings") or []),
       f"-> self_end {m.get('self_end')}")
    temiz = c.post("/evaluate", json={"forward": "TCAGGCTGCTGTTCTCCATC", "assembly": "yok"})
    ok("  ...temiz primerde (3' self 0) bu uyari yok", not any(
        "tamamlayıcı" in f["text"] for f in (temiz.get_json() or {}).get("findings") or []))
    # Orta deger (tasarim siniri 3 ile uyari esigi 6 arasi) yalnizca "bilgi":
    # siradan primerlerin ~%30'u bu aralikta, uyari yapmak alarm yorgunlugu olur.
    orta = c.post("/evaluate", json={"forward": "TGCGAGTTGGGCGTACATAC", "assembly": "yok"}).get_json()
    se = orta["primers"]["forward"]["self_end"]
    seviye = {f["level"] for f in orta["findings"] if "3' self" in f["text"]}
    ok("  ...3' self 4 -> yalnizca 'bilgi'", se == 4 and seviye == {"bilgi"},
       f"-> skor {se} {seviye}")
    # NOBETCI: laboratuvar yazimi "5'-...-3'" reddediliyordu
    for yazim in ("5'-GCTGAGGAAGTTGGTGACCA-3'", "5' GCTGAGGAAGTTGGTGACCA 3'",
                  "5′-GCTGAGGAAGTTGGTGACCA-3′"):
        r = c.post("/evaluate", json={"forward": yazim, "assembly": "yok"})
        ok(f"'{yazim[:8]}...' yazimi kabul edilir", r.status_code == 200 and
           r.get_json()["primers"]["forward"]["sequence"] == "GCTGAGGAAGTTGGTGACCA",
           f"-> {r.status_code}")
    # NOBETCI: bicimsiz ayar / govde 500 donuyordu
    for uc, govde, aranan in (
            ("/design", {"assembly": "GRCh38", "chrom": "1", "position": 1000000,
                         "params": {"primer_min_tm": "abc"}}, "Geçersiz ayar"),
            ("/design", {"assembly": "GRCh38", "chrom": "1", "position": 1000000,
                         "params": {"flank": 5000000}}, "flank"),
            ("/design", {"assembly": "GRCh38", "chrom": "1", "position": 1000000,
                         "params": ["x"]}, "anahtar-değer"),
            ("/design_sequence_pair", {"forward": "ACGT" * 50, "reverse": "TGCA" * 50,
                                       "params": {"gap": "x"}}, "Geçersiz ayar"),
            ("/specificity", {"assembly": "GRCh38", "forward": "ACGTACGTACGTACGTAC",
                              "reverse": "ACGTACGTACGTACGTAC", "expected": "x"}, "expected")):
        r = c.post(uc, json=govde)
        hata = (r.get_json() or {}).get("error", "")
        ok(f"{uc} {str(govde.get('params') or govde.get('expected'))[:22]} -> 400 + aciklama",
           r.status_code == 400 and aranan in hata, f"-> {r.status_code} {hata[:60]}")
    r = c.post("/set_genome", data="bozuk{json", content_type="application/json")
    ok("/set_genome bozuk JSON -> JSON 400 (HTML degil)",
       r.status_code == 400 and (r.get_json(silent=True) or {}).get("error"),
       f"-> {r.status_code}")
    # primer3 en fazla 200 haric bolge kabul ediyor; yogun SNP'de 500 veriyordu
    bolgeler = [[i * 10, 2] for i in range(300)]
    b = EN._bolge_sinirla(bolgeler)
    kapsar = all(any(a <= x[0] and x[0] + x[1] <= a + n for a, n in b) for x in bolgeler)
    ok("haric bolge sayisi primer3 sinirina indirilir, hicbir SNP serbest kalmaz",
       len(b) <= EN.PRIMER3_BOLGE_MAKS and kapsar, f"-> {len(b)} bolge")


def test_v051_genomlu(c, engine):
    baslik("v0.5.1 - yon hatasi, hedefsiz cift, roller, SNP kopyasi (GRCh37)")
    # Hepsi 2026-10-10 bozuk primer panelinde kacan GERCEK vakalar.
    if not engine.GENOME_PATHS.get("GRCh37"):
        atla("v0.5.1 genomlu", "GRCh37 genomu yok")
        return

    def ev(F, R):
        return c.post("/evaluate", json={"forward": F, "reverse": R,
                                         "assembly": "GRCh37"}).get_json()
    # Birbirinden uzaga bakan cift; chr10'da 1+4 uyumsuzluklu zayif bir urun
    # teshisi bastiriyordu ve karar "iyi" cikiyordu.
    d = ev("CCAAAGAGGTTGTACCGTTT", "CATCCAGAATAGGCAAAGCT")
    ok("birbirinden uzaga bakan cift: geometri teshisi + 'sorun'",
       (d.get("geometry") or {}).get("kind") == "birbirinden_uzaga" and d["verdict"] == "sorun",
       f"-> {(d.get('geometry') or {}).get('kind')} {d.get('verdict')}")
    d = ev("AGAGGCAACCTTAAAAGCTC", "GAGTAAAGAAGAAGGAGCCAG")
    ok("R'nin ters tumleyeni alinmamis: 'ayni yon' + 'sorun'",
       (d.get("geometry") or {}).get("kind") == "ayni_yon" and d["verdict"] == "sorun",
       f"-> {(d.get('geometry') or {}).get('kind')} {d.get('verdict')}")
    d = ev("AAACAAAAGGATAGCTCAGG", "CTGTACGAGACATTGGAGAG")   # F'de 2 yazim hatasi
    ok("tam eslesen urun yoksa soylenir", any(
        "tam oturduğu bir ürün yok" in f["text"] for f in d.get("findings") or []))
    # ZNF564 (eksi iplik): genin yonune gore TERS girilmis cift -> hedef genomda F+R,
    # uyumsuzluklu yan urunler R+F. Karar HEDEF urunden verilmeli, yan urunlerden degil.
    d = ev("GGCTCTCCCACATACTTTAC", "ATCTCACCTTGGACACAAAC")   # F/R yer degistirmis
    ok("hedefe gore 'roller yer degismis' (zit yonlu yan urunlere ragmen)",
       d.get("pair_roles_swapped") is True and d.get("pair_gene") == "ZNF564")
    d = ev("CCACTAATTTTAGAATATTT", "AAACGGTACAACCTCTTTGG")   # F iki yere tam oturuyor
    ok("hedefteki SNP, primerin diger kopyasina bakilarak kacirilmaz",
       any("rs11712079" in f["text"] for f in d.get("findings") or []))
    d = ev("AATTTCTGTGGGTACATAGT", "AGGGAATCAGTGTGTCAAAG")   # F 40 yere tam oturuyor
    ok("  ...hedefin yeri 6'lik yer listesine girmese de SNP gorulur",
       any("rs3059065" in f["text"] for f in d.get("findings") or []))
    d = ev("TGTTGACAAGAGGAGAGAGG", "CAGTGAATGGAGAAGCGAAG")   # hedef yok; F chr5'te ilgisiz tam yer
    ok("  ...urunle ilgisiz bir tam eslesme yerinin SNP'si 'sorun' diye cikmaz",
       not any("rs10055905" in f["text"] for f in d.get("findings") or []))


def test_par_sinirlari(c):
    baslik("Psodootozomal bolge (PAR) - sinirlar ve es konum")
    import par
    # GRC koordinatlari; Ensembl GRCh37'de Y maskesinin sinirlariyla ve GRCh38'de
    # X/Y dizilerinin birebir esitligiyle dogrulandi (2026-10-11).
    ok("GRCh38 PAR1 sinirlari", par.bolge("GRCh38", "X", 10001) and par.bolge("GRCh38", "X", 2781479)
       and not par.bolge("GRCh38", "X", 2781480) and not par.bolge("GRCh38", "X", 10000))
    ok("GRCh37 PAR2 X ve Y'de", par.bolge("GRCh37", "chrX", 155000000)["ad"] == "PAR2"
       and par.bolge("GRCh37", "Y", 59100000)["kromozom"] == "Y")
    ok("otozom ve X'in PAR disi PAR sayilmaz", not par.bolge("GRCh38", "7", 50000)
       and not par.bolge("GRCh38", "X", 31000000))
    ok("es konum: GRCh37 PAR1 Y->X +50 kb, GRCh38 PAR2 X<->Y gidip donus",
       par.es_konum("GRCh37", "Y", 541733) == ("X", 591733) and
       par.es_konum("GRCh38", "Y", par.es_konum("GRCh38", "X", 155800000)[1]) == ("X", 155800000))


def test_par_degerlendirme(c, engine):
    baslik("PAR - GRCh38'de Y esi 'kopya' / 'yan urun' sayilmaz")
    # NOBETCI (2026-10-11): GRCh38 Ensembl dosyasinda Y'nin PAR'i maskeli degil,
    # X ile birebir ayni. SHOX ciftine Degerlendir "bolge kopyalanmis, kopyalar
    # ayirt edilemez" (sorun), ozgulluk "Y'de yuksek riskli yan urun, ozgul degil"
    # diyordu. Ayni dizinin ikinci temsili; PAR notu yazilmali.
    if not engine.GENOME_PATHS.get("GRCh38"):
        atla("PAR degerlendirme", "GRCh38 genomu yok")
        return
    d = c.post("/design", json={"assembly": "GRCh38", "chrom": "X", "position": 630998}).get_json()
    pr = (d.get("pairs") or [None])[0]
    ok("SHOX (PAR1) tasariminda PAR notu", pr is not None and
       any("Psödootozomal" in n for n in d.get("notes") or []))
    if not pr:
        return
    F, R = pr["forward"]["sequence"], pr["reverse"]["sequence"]
    e = c.post("/evaluate", json={"forward": F, "reverse": R, "assembly": "GRCh38"}).get_json()
    metin = " ".join(f["text"] for f in e.get("findings") or [])
    ok("  ...Degerlendir: hedef 1 lokus, 'kopyalanmis' sorunu yok",
       e.get("target_count") == 1 and "ayrı yerde TAM eşleşen" not in metin,
       f"-> hedef {e.get('target_count')} karar {e.get('verdict')}")
    ok("  ...'2 ayri yere TAM oturuyor' denmez, PAR notu var",
       "ayrı yere TAM" not in metin and "Psödootozomal" in metin)
    s = c.post("/specificity", json={"assembly": "GRCh38", "forward": F, "reverse": R,
                                     "expected": {"chrom": "X", "start": pr["amplicon_genomic_start"],
                                                  "end": pr["amplicon_genomic_end"]}}).get_json()
    ok("  ...Ozgulluk: Y esi yan urun sayilmaz, PAR bildirilir",
       s.get("specific") is True and (s.get("par") or {}).get("ad") == "PAR1"
       and s.get("par_twins", 0) >= 1, f"-> ozgul {s.get('specific')} {s.get('risk_counts')}")
    y = c.post("/design", json={"assembly": "GRCh38", "chrom": "Y", "position": 630998}).get_json()
    ok("Y'nin PAR koordinati X esine cevrilip tasarlanir",
       (y.get("pairs") or []) and any("chrY:630.998" in n for n in y.get("notes") or []),
       f"-> {len(y.get('pairs') or [])} cift")


def test_kontrol_obur_uc(c, engine):
    baslik("Kirilma noktasi kontrol primeri: bolgenin obur ucu (v0.8.62)")
    # NOBETCI (2026-11-14): kontrol primeri yalnizca silinen bolgenin BASINDA, F ile araniyordu;
    # o uctaki dar pencerelerde uygun aday yoksa "uygun kontrol primeri bulunamadi" deniyordu.
    # Artik bulunamazsa obur uc (bolgenin sonu, R ile) denenir; dup'ta ayna yol bolge basinin
    # disi. Dizi, yon, bant ve konum genomdan ELLE dogrulanir. Ornek delesyon rastgele secildi
    # (ANAPC5 icinde, GRCh37 chr12): ilk iki ciftte kontrol obur uctan, 3. ciftte bastan gelir.
    if not engine.GENOME_PATHS.get("GRCh37"):
        return atla("Kontrol primeri obur uc", "GRCh37 genomu yok")
    fa = engine._open_fasta(engine.GENOME_PATHS["GRCh37"])
    tum = str.maketrans("ACGT", "TGCA")

    def G(kr, a, b):
        return str(fa[engine._fasta_key(fa, kr)][a - 1:b]).upper()

    def dogru(kr, x, bolge, ana):
        """Kontrol primeri genomda iddia edilen yerde ve yonde mi; bant ortak primerin 5'
        ucundan kontrolun 5' ucuna mi; bolgenin icinde, sinirda ve ana banttan >=100 bp uzak mi."""
        k = x["control"]
        g = G(kr, k["genomic_start"], k["genomic_end"])
        if k.get("pairs_with") == "reverse":
            dizi_ok, bant = k["sequence"].upper() == g, x["reverse"]["genomic_end"] - k["genomic_start"] + 1
        else:
            dizi_ok = k["sequence"].upper() == g.translate(tum)[::-1]
            bant = k["genomic_end"] - x["forward"]["genomic_start"] + 1
        return (dizi_ok and bant == k["band"] and bolge[0] <= k["genomic_start"]
                and k["genomic_end"] <= bolge[1] and k["band"] <= 700
                and (k["band"] <= ana[0] - 100 or k["band"] >= ana[1] + 100))

    S, E = 121_763_332, 121_766_536
    d = c.post("/design_breakpoint", json={"assembly": "GRCh37", "chrom": "12", "start": S, "end": E,
                                           "type": "del", "params": {"control_primer": True}}).get_json()
    ps = d.get("pairs") or []
    p1 = ps[0] if ps else {}
    k1 = p1.get("control")
    ok("Delesyon (GRCh37 chr12, pay 0): 1. ciftte kontrol primeri var", bool(k1),
       f"-> {p1.get('control_reason')}")
    if k1:
        ok("  ...silinen bolgenin SONUNDA, R ile bant verir; dizi + iplik, bant R'nin 5' ucuna",
           k1.get("pairs_with") == "reverse"
           and dogru("12", p1, (S, E), (p1["bp"]["mut_min"], p1["bp"]["mut_max"])),
           f"-> {k1.get('pairs_with')} {k1['genomic_start']:,}-{k1['genomic_end']:,} {k1['band']} bp")
        ok("  ...kontrol primerinin uzerinde yaygin varyant yok", k1.get("snps") == [],
           f"-> {k1.get('snps')}")
    sol = [x for x in ps if x.get("control") and x["control"].get("pairs_with") == "forward"]
    ok("  ...bolgenin basinda bulunan kontroller degismez (3. cift: F ile 674 bp)",
       any(x["rank"] == 3 and x["control"]["band"] == 674 for x in sol),
       f"-> {[(x['rank'], x['control']['band']) for x in sol][:4]}")
    hatali = [x["rank"] for x in ps if x.get("control")
              and not dogru("12", x, (S, E), (x["bp"]["mut_min"], x["bp"]["mut_max"]))]
    ok("  ...her ciftte kontrol var; hepsi genom, bant, bolge ve 100 bp ayrimla uyusur",
       ps and all(x.get("control") for x in ps) and not hatali,
       f"-> kontrolsuz {[x['rank'] for x in ps if not x.get('control')]}, hatali {hatali}")
    # Duplikasyonda ayna: sag uc uygun degilse (aday yok ya da hairpin) R ile duplike bolgenin SOLUNA
    # (bolge basinin disi). v0.8.64: tekrarli aday tek tek elendigi icin chr16:66,709,809 vakasinin sag
    # ucu artik kontrol buluyor; vaka chr3'e tasindi, orada 5 cift obur ucu kullaniyor.
    S2, E2 = 103_478_237, 103_492_145
    d = c.post("/design_breakpoint", json={"assembly": "GRCh37", "chrom": "3", "start": S2, "end": E2,
                                           "type": "dup", "params": {"control_primer": True}}).get_json()
    ps = d.get("pairs") or []
    ayna = [x for x in ps if x.get("control") and x["control"].get("pairs_with") == "reverse"]
    ok("tandem dup (GRCh37 chr3): sag uc uygun degilse R ile bolgenin soluna konur",
       (d.get("input") or {}).get("approach") == "tandem_junction" and bool(ayna)
       and all(dogru("3", x, (S2 - 1500, S2 - 1), (x["bp"]["junction_min"], x["bp"]["junction_max"]))
               for x in ayna),
       f"-> {[(x['rank'], x['control']['band']) for x in ayna][:4]}")


def test_kontrol_hairpin(c, engine):
    baslik("Kirilma noktasi kontrol primeri: hairpin esigi (v0.8.64)")
    # NOBETCI (2026-11-14, kullanici karari "1 numarayi yapalim"): legacy hizalamada primer3 hairpin'e
    # bakmiyor, kontrol primeri ilk aday olarak aliniyordu; F-05 uyarisi yalniz forward / reverse'teydi.
    # Artik ilk 5 adaydan esigi gecmeyen ilki (iki ucta); yoksa en iyisi kalir ve kartta
    # "Kontrol primerin hairpin Tm'i ..." uyarisi cikar. Siralama degismez.
    import subprocess

    def esik_durumu(x):
        esik = round(x["ta_suggested"] - engine.HAIRPIN_UYARI_PAYI, 1)
        k = x["control"]
        uy = [w for w in x.get("hairpin_warn") or [] if w.get("primer") == "control"]
        return k["hairpin_tm"] > 0 and k["hairpin_tm"] >= esik, uy, esik

    if engine.GENOME_PATHS.get("GRCh38"):
        # Sinir 500 bp: pencereler dar, bazi ciftlerde iki uctaki adaylarin hepsi esigi geciyor (61 °C)
        d = c.post("/design_breakpoint", json={"assembly": "GRCh38", "chrom": "20", "start": 44_511_557,
                                               "end": 44_553_369, "type": "dup",
                                               "params": {"control_primer": True, "pcr_max": 500}}).get_json()
        ps = [x for x in d.get("pairs") or [] if x.get("control")]
        uyarili = [x for x in ps if esik_durumu(x)[1]]
        dogru = all(len(esik_durumu(x)[1]) == 1 and esik_durumu(x)[1][0]["hairpin_tm"] == x["control"]["hairpin_tm"]
                    and esik_durumu(x)[1][0]["esik"] == esik_durumu(x)[2]
                    and esik_durumu(x)[1][0]["ta"] == x["ta_suggested"] for x in uyarili)
        ok("chr20 dup (GRCh38, sinir 500): temiz aday yoksa kontrol kalir ve uyari tasir",
           bool(uyarili) and dogru, f"-> {[(x['rank'], x['control']['hairpin_tm']) for x in uyarili][:4]}")
        ok("  ...her ciftte: kontrol esigi gecerse tam bir uyari, gecmezse hic",
           bool(ps) and all(esik_durumu(x)[0] == bool(esik_durumu(x)[1]) for x in ps))
    else:
        atla("Kontrol hairpin (uyari)", "GRCh38 genomu yok")
    # Arayuz: kontrol uyarisi "Kontrol" adiyla; eksi iplikte F/R gibi cevrilmez (node)
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    app = open(os.path.join(kok, "app.js"), encoding="utf-8").read()
    i18n = open(os.path.join(kok, "i18n.js"), encoding="utf-8").read()
    node = shutil.which("node")
    if not node:
        return atla("Kontrol hairpin satiri", "node yok")
    kod = "\n".join(x for x in app.splitlines() if not x.lstrip().startswith("//"))
    i = kod.find("function hairpinSatiri(")
    fn = kod[i:kod.find("\n}", i)] + "\n}\n"
    yardim = (re.search(r"^const yerel = .*$", app, re.M).group(0) + "\n"
              + re.search(r"^const esc = .*\n.*$", app, re.M).group(0) + "\n")
    p = {"hairpin_warn": [{"primer": "control", "hairpin_tm": 61.0, "ta": 55.0, "esik": 50.0}]}
    betik = (i18n + "\n" + yardim + fn + "const p = " + json.dumps(p) + ";\nconst r = {};\n"
             "for (const L of ['tr', 'en']) { LANG = L; r[L] = [hairpinSatiri(p, false), hairpinSatiri(p, true)]; }\n"
             "console.log(JSON.stringify(r));\n")
    dosya = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    try:
        dosya.write(betik)
        dosya.close()
        r = subprocess.run([node, dosya.name], capture_output=True, text=True, encoding="utf-8", timeout=60)
    finally:
        os.unlink(dosya.name)
    if r.returncode != 0:
        return ok("Kontrol hairpin satiri node ile kurulur", False, r.stderr.strip()[:200])
    s = json.loads(r.stdout)
    ok("kartta 'Kontrol primerin hairpin Tm'i 61,0 °C' (TR) / 'Control primer' (EN); eksi iplikte de ayni",
       all("Kontrol primerin hairpin Tm'i 61,0" in x for x in s["tr"])
       and all("the Control primer is 61.0" in x for x in s["en"]), s["tr"][0][:120])


def test_kirilma_noktasi(c, engine):
    baslik("Kirilma noktasi - delesyon / tandem duplikasyon")
    # Motorun ciktisina guvenmeden: mutant / duplike alel genomdan ELLE kurulur,
    # primerlerin onun iki ucuna oturdugu ve bant boylarinin tuttugu kontrol edilir.
    if not engine.GENOME_PATHS.get("GRCh38"):
        atla("Kirilma noktasi", "GRCh38 genomu yok")
        return
    fa = engine._open_fasta(engine.GENOME_PATHS["GRCh38"])
    kr = fa[engine._fasta_key(fa, "2")]
    tum = str.maketrans("ACGT", "TGCA")

    def G(a, b):
        return str(kr[a - 1:b]).upper()

    def tasarla(s, e, tip, **prm):
        # Bu bolumdeki ilk testler kirilma mantigini sinar ve 3 kb cogaltabilen bir
        # laboratuvari varsayar (pcr_max'in eski fiili degeri). 700 bp varsayilaninin
        # davranisi asagida ayri sinanir (pcr_max=None -> varsayilan).
        prm.setdefault("pcr_max", 3000)
        return c.post("/design_breakpoint", json={"assembly": "GRCh38", "chrom": "2", "start": s,
                                                  "end": e, "type": tip, "params": prm}).get_json()

    d = tasarla(50_000_001, 50_012_000, "del")
    p = (d.get("pairs") or [None])[0]
    ok("12 kb delesyon: cift bulunur (gap-PCR)", p and d["input"]["approach"] == "gap_pcr")
    if p:
        F, R = p["forward"]["sequence"], p["reverse"]["sequence"]
        f5, r5 = p["forward"]["genomic_start"], p["reverse"]["genomic_end"]
        alel = G(f5, 50_000_000) + G(50_012_001, r5)
        ok("  ...mutant alel F ile baslar, R ile biter; kirilma bandi = alel boyu",
           alel.startswith(F) and alel.endswith(R.translate(tum)[::-1]) and len(alel) == p["bp"]["mut"],
           f"-> {len(alel)} / {p['bp']['mut']}")
        ok("  ...primerler kirilma noktasina >=100 bp uzak",
           p["forward"]["genomic_end"] <= 50_000_000 - 100 and p["reverse"]["genomic_start"] >= 50_012_001 + 100)
        ok("  ...normal alel (12,6 kb) 'cogalmaz'", p["bp"]["wt_status"] == "yok")
    d = tasarla(60_000_001, 60_000_300, "del")
    p = (d.get("pairs") or [None])[0]
    ok("300 bp delesyon: normal alel de cogalir, fark = 300",
       p and p["bp"]["wt_status"] == "var" and p["bp"]["wt"] - p["bp"]["mut"] == 300)
    d = tasarla(50_000_001, 50_012_000, "del", control_primer=True, bp_margin=100)
    p = (d.get("pairs") or [None])[0]
    k = (p or {}).get("control")
    # NOBETCI (2026-10-14): kontrol bandi ana bandin orta degerine gore seciliyordu;
    # belirsizlik payi varken ana bant bir ARALIK ve kontrol onun icine dusebiliyordu.
    ok("kontrol primeri silinen bolgenin icinde, bandi ana bant araliginin >=100 bp disinda",
       k and 50_000_101 <= k["genomic_start"] and k["genomic_end"] <= 50_011_900
       and (k["band"] <= p["bp"]["mut_min"] - 100 or k["band"] >= p["bp"]["mut_max"] + 100),
       f"-> {(p or {}).get('control_reason')}")
    ok("  ...±100 belirsizlikte bant araligi 400 bp genis",
       p and p["bp"]["mut_max"] - p["bp"]["mut_min"] == 400)
    d = tasarla(80_000_001, 80_020_000, "dup")
    p = (d.get("pairs") or [None])[0]
    ok("20 kb duplikasyon: disa bakan tandem cift", p and d["input"]["approach"] == "tandem_junction")
    if p:
        F, R = p["forward"]["sequence"], p["reverse"]["sequence"]
        f5, r5 = p["forward"]["genomic_start"], p["reverse"]["genomic_end"]
        baglanti = G(f5, 80_020_000) + G(80_000_001, r5)
        ok("  ...referansta birbirinden uzaga bakar; baglanti dizisi F..R ve boyu tutar",
           r5 < f5 and baglanti.startswith(F) and baglanti.endswith(R.translate(tum)[::-1])
           and len(baglanti) == p["bp"]["junction"])
    d = tasarla(80_000_001, 80_020_000, "dup", control_primer=True, bp_margin=100)
    gecersiz = [c for c in d.get("pairs") or [] if c.get("control") and not (
        c["control"]["band"] <= c["bp"]["junction_min"] - 100
        or c["control"]["band"] >= c["bp"]["junction_max"] + 100)]
    ok("  ...±100 + kontrol: hicbir kontrol bandi baglanti araligina 100 bp'den yakin degil",
       d.get("pairs") and any(c.get("control") for c in d["pairs"]) and not gecersiz,
       f"-> {len(gecersiz)} cakisan")
    # NOBETCI (2026-10-17): bant primer3'un PRODUCT_SIZE'indan aliniyordu; F sablonda
    # tekrarliysa primer3 onu baska kopyaya oturtup yanlis boy bildiriyordu.
    # (2026-11-14: kontrol obur uctan R ile de gelebilir; bant o zaman R'nin 5' ucuna)
    uymayan = [c for c in d.get("pairs") or [] if c.get("control") and c["control"]["band"]
               != (c["reverse"]["genomic_end"] - c["control"]["genomic_start"] + 1
                   if c["control"].get("pairs_with") == "reverse"
                   else c["control"]["genomic_end"] - c["forward"]["genomic_start"] + 1)]
    ok("  ...kontrol bandi = ortak primerin 5' ucundan kontrol primerinin 5' ucuna (genomik)",
       d.get("pairs") and not uymayan, f"-> {len(uymayan)} uymayan")
    # NOBETCI (2026-10-17): arama penceresi F'den 1500 bp'de kesiliyordu; pay buyukken
    # F bolgeden >800 bp uzakta kaldigi icin buyuk delesyonda bile "bolge cok kisa".
    d = tasarla(50_000_001, 50_012_000, "del", control_primer=True, bp_margin=400)
    ok("±400 belirsizlikte de kontrol primeri bulunur",
       any(c.get("control") for c in d.get("pairs") or []),
       f"-> {[c.get('control_reason') for c in (d.get('pairs') or [])[:1]]}")
    d = tasarla(50_000_001, 50_012_000, "del", control_primer=True, bp_margin=1000)
    nedenler = [c.get("control_reason") or "" for c in d.get("pairs") or []]
    ok("  ...±1000'de kontrol yok ve nedeni 'payı küçültmek gerekir'",
       nedenler and not any(c.get("control") for c in d["pairs"])
       and all("payı küçültmek" in n for n in nedenler), f"-> {nedenler[:1]}")
    ok("  ...neden, silinen bolgenin iki ucunun da denendigini soyler (v0.8.62)",
       nedenler and all("iki ucu da denendi" in n for n in nedenler), f"-> {nedenler[:1]}")
    # NOBETCI (2026-10-17): (CA)10 mikrosatellit primeri seciliyordu; kanatta birden
    # fazla kez gecen primer her kopyadan uzayip birden cok bant verir.
    sab = "ACGTTGCA" * 3 + "CA" * 10 + "GATTACAGGT" * 5
    res = {"PRIMER_LEFT_0_SEQUENCE": "CA" * 9, "PRIMER_RIGHT_0_SEQUENCE": "ACCTGTAATC",
           "PRIMER_LEFT_1_SEQUENCE": "TTGCACACAC", "PRIMER_RIGHT_1_SEQUENCE": "GTAATCTGTG"}
    # (2026-10-28: suzgec _rank_order'a tasindi, olcut _tekrar_sayisi)
    kalan = [i for i in (0, 1)
             if all(engine._tekrar_sayisi(sab, res[f"PRIMER_{y}_{i}_SEQUENCE"]) == 1
                    for y in ("LEFT", "RIGHT"))]
    ok("tekrar suzgeci: (CA)n ve tekrar eden reverse elenir, tekil cift kalir",
       kalan == [1], f"-> {kalan}")
    d = tasarla(90_000_001, 90_000_500, "dup")
    p = (d.get("pairs") or [None])[0]
    ok("500 bp duplikasyon: dis primerler, duplike bant = normal + 500",
       p and d["input"]["approach"] == "size_shift" and p["bp"]["dup"] == p["bp"]["wt"] + 500
       and p["forward"]["genomic_end"] < 90_000_001 and p["reverse"]["genomic_start"] > 90_000_500)

    # --- Cogaltilabilen en uzun urun (pcr_max, varsayilan 700 bp) --------------
    # NOBETCI (2026-10-25): en fazla ~700 bp cogaltan laboratuvarda 900 bp'lik normal
    # alele "cogalir", 600 bp'lik dup icin 1,7 kb'lik bant, 1,9 kb'lik kontrol bandi
    # oneriliyordu (wt_amp_max sabit 3 kb'ti).
    h = c.get("/health").get_json() or {}
    ok("varsayilan cogaltilabilen en uzun urun 700 bp", (h.get("defaults") or {}).get("pcr_max") == 700)
    d = tasarla(60_000_001, 60_000_300, "del", pcr_max=None)
    p = (d.get("pairs") or [None])[0]
    ok("700 bp: 300 bp delesyonda ~900 bp'lik normal alel 'cogalir' denmez",
       p and p["bp"]["wt"] > 700 and p["bp"]["wt_status"] != "var"
       and any("700 bp" in n for n in d.get("notes", [])), f"-> {p and p['bp']}")
    d = tasarla(90_000_001, 90_000_600, "dup", pcr_max=None)
    p = (d.get("pairs") or [None])[0]
    ok("700 bp: 600 bp dup dis primerlerle sigmaz -> disa bakan primerler, bant <=700",
       p and d["input"]["approach"] == "tandem_junction" and p["bp"]["junction_max"] <= 700,
       f"-> {d.get('input', {}).get('approach')} {p and p['bp']}")
    if p:
        F, R = p["forward"]["sequence"], p["reverse"]["sequence"]
        f5, r5 = p["forward"]["genomic_start"], p["reverse"]["genomic_end"]
        baglanti = G(f5, 90_000_600) + G(90_000_001, r5)
        ok("  ...baglanti dizisi F..R ve boyu tutar (kucuk dup'ta da)",
           r5 < f5 and baglanti.startswith(F) and baglanti.endswith(R.translate(tum)[::-1])
           and len(baglanti) == p["bp"]["junction"])
    d = tasarla(50_000_001, 50_012_000, "del", pcr_max=None, bp_margin=50)
    ok("700 bp: ±50 belirsizlikte en uzun olasi bant bile <=700",
       d.get("pairs") and all(c_["bp"]["mut_max"] <= 700 for c_ in d["pairs"]),
       f"-> en uzun {max((c_['bp']['mut_max'] for c_ in d.get('pairs') or []), default=None)}")
    # ±100'de urun 236-300 bp'ye sikisir; bu bolgede o pencerede primer yok. Bos sonuc
    # yerine sinirsiz tasarim + "sinira sigan tasarim bulunamadi" uyarisi beklenir.
    d = tasarla(50_000_001, 50_012_000, "del", pcr_max=None, bp_margin=100)
    sigar = d.get("pairs") and all(c_["bp"]["mut_max"] <= 700 for c_ in d["pairs"])
    uyari = any("UYARI: Bant" in n for n in d.get("notes", []))
    ok("  ...±100: cift yine bulunur; sinira sigmiyorsa uyari verilir",
       d.get("pairs") and (sigar or uyari), f"-> cift {len(d.get('pairs') or [])}, uyari {uyari}")
    # NOBETCI (2026-11-10, A4-01): uyari "en fazla ±116 bp payla calisilabilir" diyordu
    # (kuramsal formul); o payda ya uyari suruyor ya da cift cikmiyordu (54/54 vaka).
    # Oneri artik motorla denenir: onerilen pay gercekten uyarisiz ve ciftli sonuc verir;
    # hicbir pay calismiyorsa sayi verilmez, sinirin kac bp'ye cikarilacagi soylenir.
    d = tasarla(50_000_001, 50_012_000, "del", pcr_max=None, bp_margin=200)
    uy = [n for n in d.get("notes", []) if n.startswith("UYARI: Bant")]
    ok("  ...±200 sigmaz: uyari var", len(uy) == 1, f"-> {[n[:60] for n in uy]}")
    mm = re.search(r"±([\d.,]+) bp'ye indirince", uy[0]) if uy else None
    if mm:
        X = int(mm.group(1).replace(".", "").replace(",", ""))
        d2 = tasarla(50_000_001, 50_012_000, "del", pcr_max=None, bp_margin=X)
        ok(f"  ...onerilen ±{X} payla tasarim uyarisiz ve ciftli (motorla denendi)",
           d2.get("pairs") and not any(n.startswith("UYARI: Bant") for n in d2.get("notes", [])),
           f"-> cift {len(d2.get('pairs') or [])}")
    else:
        mu = re.search(r"en az ([\d.,]+) bp'ye yükseltin", uy[0]) if uy else None
        ok("  ...sayi onerilmediyse sinir yukseltme sayisi yazilir", bool(mu), f"-> {uy[0][-90:] if uy else ''}")
        if mu:
            U = int(mu.group(1).replace(".", "").replace(",", ""))
            d2 = tasarla(50_000_001, 50_012_000, "del", pcr_max=U, bp_margin=200)
            ok(f"  ...sinir {U} bp'ye cikinca uyarisiz ve ciftli",
               d2.get("pairs") and not any(n.startswith("UYARI: Bant") for n in d2.get("notes", [])))
    ok("  ...'en fazla ±' kuramsal iddiasi yok", not any("en fazla ±" in n for n in d.get("notes", [])))
    d = tasarla(80_000_001, 80_020_000, "dup", pcr_max=None, control_primer=True)
    kontroller = [c_["control"]["band"] for c_ in d.get("pairs") or [] if c_.get("control")]
    ok("700 bp: kontrol bantlari da <=700", kontroller and max(kontroller) <= 700,
       f"-> {kontroller[:5]}")
    # NOBETCI (2026-10-25): ciftlerin normal alel bandi farkli boylarda; bir kismi
    # sinirin ALTINDA kalabilir. Not hepsini "sinirin ustunde" sayiyordu (150 bp'lik
    # delesyonda 673 bp'lik banda da oyle deniyordu).
    d = tasarla(60_000_001, 60_000_150, "del", pcr_max=None)
    durumlar = {x["bp"]["wt_status"] for x in d.get("pairs") or []}
    notlar = " ".join(d.get("notes", []))
    if durumlar == {"var", "zayif"} or durumlar == {"var", "yok"}:
        ok("karisik normal alel: 'bir kısmı altında, bir kısmı üstünde' der",
           "bir kısmı" in notlar and "altında" in notlar, f"-> {durumlar}")
    else:
        ok("karisik normal alel notu (bu bolgede durum tek tip)", True, f"-> {durumlar}")
    # 2 kb delesyon: normal alel hicbir ciftte cikmaz; het/hom ayrimi kontrol primeriyle
    d = tasarla(50_000_001, 50_002_000, "del", pcr_max=None)
    ok("2 kb delesyonda normal alel hicbir ciftte sinir icinde degil",
       d.get("pairs") and all(x["bp"]["wt_status"] == "yok" for x in d["pairs"]))
    ok("  ...kontrol primerini acmasi soylenir",
       "kontrol primerini açın" in " ".join(d.get("notes", [])))
    # NOBETCI (2026-10-25): sinir kullanicinin KENDI protokolu; "700 bp ustu cogalmaz"
    # gibi mutlak bir hukum verilmemeli (araci baska laboratuvarlar da kullaniyor).
    metin = " ".join(d.get("notes", []))
    ok("  ...sinir mutlak degil, ayara bagli anlatilir",
       "ayarladığınız sınırın" in metin and "protokolde" in metin,
       f"-> {metin[:90]}")
    ok("  ...'ürün beklenmez' gibi mutlak ifade kullanilmaz",
       "ürün beklenmez" not in metin and "çoğalmaz" not in metin)
    d = tasarla(50_000_001, 50_002_000, "del", pcr_max=None, control_primer=True)
    bantlar = [x["control"]["band"] for x in d.get("pairs") or [] if x.get("control")]
    ok("  ...kontrol acikken bandi sinira sigar (het/hom ayrimi mumkun)",
       bantlar and max(bantlar) <= 700, f"-> {bantlar[:4]}")

    r = c.post("/design", json={"assembly": "GRCh38", "chrom": "17", "position": 43093000,
                                "params": {"pcr_max": 400}})
    boylar = [x["product_size"] for x in (r.get_json() or {}).get("pairs") or []]
    ok("DNA modu: sinir 400 bp ise hicbir urun 400'u asmaz (amplikon max 650 olsa da)",
       boylar and max(boylar) <= 400, f"-> en uzun {max(boylar, default=None)}")
    r = c.post("/design", json={"assembly": "GRCh38", "chrom": "17", "position": 43093000,
                                "params": {"pcr_max": 400, "product_size_min": 500}})
    hata = (r.get_json() or {}).get("error", "")
    ok("  ...amplikon alt siniri sinirdan buyukse anlasilir 400",
       r.status_code == 400 and "çoğaltılabilen" in hata, f"-> {hata[:70]}")

    # NOBETCI (2026-10-25): amplikon max sinirin ustundeyse sessizce kirpiliyordu;
    # kullanici "2000 yazdim, 583 bp geldi" diye sormustu. Artik soyleniyor.
    d = c.post("/design", json={"assembly": "GRCh38", "chrom": "17", "position": 43093000,
                                "params": {"product_size_max": 2000}}).get_json() or {}
    boylar = [x["product_size"] for x in d.get("pairs") or []]
    ok("amplikon max sinirin ustunde: kirpildigi soylenir",
       boylar and max(boylar) <= 700
       and any("geçerli üst sınır" in n for n in d.get("notes", [])),
       f"-> en uzun {max(boylar, default=None)}")
    d = c.post("/design", json={"assembly": "GRCh38", "chrom": "17", "position": 43093000,
                                "params": {}}).get_json() or {}
    ok("  ...amplikon max sinirin altindayken bu not CIKMAZ",
       not any("geçerli üst sınır" in n for n in d.get("notes", [])))
    for govde, aranan in (({"assembly": "GRCh38", "chrom": "2", "start": 500, "end": 100, "type": "del"}, "Bitiş"),
                          ({"assembly": "GRCh38", "chrom": "2", "start": 100, "end": 500, "type": "inv"}, "Tip"),
                          ({"assembly": "GRCh38", "chrom": "2", "start": "", "end": 500}, "gerekli")):
        r = c.post("/design_breakpoint", json=govde)
        hata = (r.get_json() or {}).get("error", "")
        ok(f"hatali girdi -> 400 ({aranan})", r.status_code == 400 and aranan in hata, f"-> {hata[:60]}")


def test_rna_tohum_uzunlugu(c, engine):
    baslik("RNA modu 3' uc sarti genomla ayni")
    import evaluate as E
    import specificity as S
    # NOBETCI (2026-10-01): RNA modu sabit 8 bazlik 3' uc sarti kullaniyordu,
    # genom taramasi 6'ya inmisti. 3' ucundan 7. bazdaki tek uyumsuzluk DNA
    # modunda gorunurken RNA modunda primer "transkriptte yok" sayiliyordu
    # (12 rastgele transkriptte 0/12).
    n = S.SPEC_DEFAULTS["seed_len"]

    def boz(s, i):
        """3' uctan i. bazi (1 = son baz) degistir."""
        k = len(s) - i
        return s[:k] + {"A": "C", "C": "G", "G": "T", "T": "A"}[s[k]] + s[k + 1:]

    cdna = ("ATGGCTTCAGGACTCAAGGTACCGTTAGCAGGTCATCGATGCTTAGGACCTGAACTGGTCAGC"
            "TTGACCAGTCGATCCGATTAGGCATCAGGCTTACCGAGT")
    ileri = cdna[20:40]
    h = E._cdna_yerlesim(cdna, boz(ileri, n + 1), "+")
    ok(f"3' uctan {n + 1}. baz uyumsuz -> yine bulunur",
       any(x["start"] == 20 and x["mismatch"] == 1 for x in h))
    h = E._cdna_yerlesim(cdna, boz(ileri, 3), "+")
    ok("3' uctan 3. baz uyumsuz -> bulunmaz (uzama olmaz)",
       not any(x["start"] == 20 for x in h))
    geri = engine.revcomp(cdna[60:80])
    h = E._cdna_yerlesim(cdna, boz(geri, n + 1), "-")
    ok("  ...reverse yonde de ayni kural",
       any(x["start"] == 60 and x["mismatch"] == 1 for x in h))

    if not engine.GENOME_PATHS.get("GRCh38"):
        return
    import transcripts as T
    try:
        tx = T.get_transcript("NM_000546", "GRCh38")
        cd, _ = engine.build_cdna(tx, "GRCh38")
    except Exception as e:
        atla("RNA tohum - gercek transkript", str(e)[:80])
        return
    F = boz(cd[400:420], n + 1)
    R = engine.revcomp(cd[700:720])
    d = c.post("/evaluate_cdna", json={"forward": F, "reverse": R, "acc": "NM_000546",
                                       "assembly": "GRCh38"}).get_json()
    urun = d.get("product") or {}
    ok("gercek transkriptte (TP53) urun bulunur", urun.get("length") == 320,
       f"-> {urun.get('length')} {d.get('error', '')}")
    yer = (d.get("placement") or {}).get("forward") or {}
    ok("  ...forward 1 uyumsuzlukla yerlestirildi", yer.get("mismatch") == 1,
       f"-> {yer.get('mismatch')}")


def test_3uc_gc_siniri(c):
    baslik("3' uc GC siniri (son 5 bazda en fazla 3 G/C)")
    # Clamp "en az 1" derken ters yonu sinirlamamak tutarsizdi: Degerlendir
    # 4+ icin uyariyor, Tasarim rahatca uretebiliyordu.
    d = c.post("/design", json={"assembly": "GRCh38", "chrom": "17",
                                "position": 43093000, "params": {}}).get_json()
    pairs = d.get("pairs") or []
    ok("tasarim basarili", len(pairs) > 0, f"{len(pairs)} cift")
    gc5 = lambda s: sum(1 for ch in s[-5:] if ch in "GC")
    ihlal = [(p["rank"], p["forward"]["sequence"][-5:], p["reverse"]["sequence"][-5:])
             for p in pairs
             if gc5(p["forward"]["sequence"]) > 3 or gc5(p["reverse"]["sequence"]) > 3]
    ok("hicbir primerin son 5 bazinda 4+ G/C yok", not ihlal, f"ihlal: {ihlal}" if ihlal else "")
    ok("hepsi hala G/C ile bitiyor (clamp)",
       all(p["forward"]["sequence"][-1] in "GC" and p["reverse"]["sequence"][-1] in "GC"
           for p in pairs))

    # Tutarsiz ayar: clamp 4 > max_end_gc 3 -> anlasilir hata, 500 degil
    r = c.post("/design", json={"assembly": "GRCh38", "chrom": "17", "position": 43093000,
                                "params": {"primer_gc_clamp": 4, "primer_max_end_gc": 3}})
    ok("clamp > 3'uc siniri -> 400 ile aciklanir", r.status_code == 400,
       f"-> {(r.get_json().get('error') or '')[:60]}")

    # primer3 bu elemeyi ETIKETLEMIYOR (olculdu: sinir 5'te fark 0, 3'te 21,
    # 0'da 312). Ayristirici kalani hesaplayip kendisi etiketlemeli.
    import engine
    coz = engine._explain_coz("considered 2576, overlap excluded region 48, "
                              "GC content failed 2201, low tm 3, high end compl 3, ok 9")
    ok("etiketsiz kalan '3' uc GC' olarak cikarilir", coz.get("high end gc") == 312,
       f"-> {coz.get('high end gc')}")
    coz2 = engine._explain_coz("considered 100, GC content failed 60, ok 40")
    ok("kalan yoksa sahte kalem uydurulmaz", "high end gc" not in coz2)
    from lang import set_lang; set_lang("tr")
    dokum = engine._explain_dokum(coz)
    ok("dokumde Turkce etiketle gorunur", "3' uçta fazla G/C 312" in dokum, f"-> {dokum[:80]}")


def test_amplikon_gc(c):
    baslik("Amplikon GC icerigi ve katki uyarisi")
    import random
    random.seed(3)
    rnd = lambda n, gc: "".join(random.choice("GC") if random.random() < gc
                                else random.choice("AT") for _ in range(n))
    # Uclari normal (primer oturabilsin), ortasi GC'ce cok zengin
    dizi = rnd(120, 0.50) + rnd(300, 0.88) + rnd(120, 0.50)
    d = c.post("/design_sequence", json={"sequence": dizi, "params": {
        "product_size_min": 300, "product_size_max": 540}}).get_json()
    a = ((d.get("pairs") or [{}])[0]).get("amplicon") or {}
    ok("GC yuzdesi hesaplandi", a.get("gc_percent") is not None, f"%{a.get('gc_percent')}")
    ok("  ...'cok_yuksek' bayragi (>=75)", a.get("gc_flag") == "cok_yuksek")
    ok("  ...DMSO/betain onerisi var", "DMSO" in (a.get("gc_note") or ""))

    # Normal bolge: bayrak yok
    d = c.post("/design", json={"assembly": "GRCh38", "chrom": "17",
                                "position": 43093000, "params": {}}).get_json()
    a = d["pairs"][0]["amplicon"]
    ok("normal bolgede bayrak yok", a.get("gc_flag") is None, f"%{a.get('gc_percent')}")

    # Iki dizi modunda N'ler sayilmamali (bilinmeyen bolge GC'yi bozmasin)
    random.seed(7)
    dz = "".join(random.choice("ACGT") for _ in range(900))
    d = c.post("/design_sequence_pair", json={"forward": dz[:400], "reverse": dz[500:],
                                              "params": {"gap": 120}}).get_json()
    a = d["pairs"][0]["amplicon"]
    bilinen = [ch for ch in a["sequence"] if ch in "ACGT"]
    beklenen = round(100.0 * sum(1 for ch in bilinen if ch in "GC") / len(bilinen), 1)
    ok("iki dizi modunda N'ler GC'ye dahil degil", a["gc_percent"] == beklenen,
       f"{a['gc_percent']} == {beklenen}")

    # Degerlendir/RNA urununde de var
    e = c.post("/evaluate_cdna", json={"forward": "AACTTATTGCAGTGTGGGAG",
                                       "reverse": "TCACTTCTGGAAAACCACTC",
                                       "acc": "NM_007294", "assembly": "GRCh38"}).get_json()
    ok("Degerlendir/RNA urununde GC var", (e.get("product") or {}).get("gc_percent") is not None)


def test_genomsuz_degerlendirme(c, engine):
    baslik("Genom yokken degerlendirme")
    if HTTP:
        return atla("Genom yokken degerlendirme", "HTTP modu: motorun ici degistirilemez")
    # NOBETCI: genoma hic bakilmadigi halde "Sorun gorunmuyor" deniyordu.
    # Bir tani aracinda "kontrol etmedim" ile "temiz" ayni sey degildir.
    eski = dict(engine.GENOME_PATHS)
    try:
        engine.GENOME_PATHS["GRCh38"] = ""
        d = c.post("/evaluate", json={"forward": "AGAAGCCGTGAGAAGTGA",
                                      "reverse": "ATGATCTAGGTTGTGGTCCT",
                                      "assembly": "GRCh38"}).get_json()
        ok("genom kullanilmadi olarak isaretlenir", d.get("genome_used") is False)
        ok("karar 'iyi' DEGIL", d.get("verdict") != "iyi", f"-> {d.get('verdict')}")
        metin = " ".join(f["text"] for f in (d.get("findings") or []))
        ok("  ...genom analizi yapilmadigi soylenir", "genom analizi" in metin.lower())
    finally:
        engine.GENOME_PATHS.update(eski)


def test_urun_gc_araligi(c):
    baslik("Urun GC araligi (product_min_gc / product_max_gc)")

    def tasarla(prm):
        r = c.post("/design", json={"assembly": "GRCh38", "chrom": "17",
                                    "position": 43093000, "params": prm})
        return r, (r.get_json() or {})

    r, d = tasarla({})
    serbest = [p["amplicon"]["gc_percent"] for p in d.get("pairs") or []]
    ok("kisit yokken (varsayilan 0-100) tasarim calisir", r.status_code == 200 and serbest,
       f"-> GC {serbest[:3]}")
    ok("  ...varsayilan aralikta hicbir cift elenmez",
       not any("GC içeriği" in n for n in d.get("notes", [])))

    r, d = tasarla({"product_min_gc": 40, "product_max_gc": 50})
    gc = [p["amplicon"]["gc_percent"] for p in d.get("pairs") or []]
    ok("GC %40-50 istenince her urun bu aralikta", gc and all(40 <= g <= 50 for g in gc),
       f"-> {gc[:4]}")
    ok("  ...elenen aday sayisi soylenir",
       any("GC içeriği" in n and "elendi" in n for n in d.get("notes", [])))
    ok("  ...kisitsiz halde aralik disi cift VARDI (suzgec gercekten is yapti)",
       any(not (40 <= g <= 50) for g in serbest), f"-> {serbest[:4]}")

    # NOBETCI (2026-10-25): suzgec listeyi bosalttiginda primer3'un dokumune bakilip
    # "adaylarin cogu urun boyu kisitina takildi, araligi genisletin" deniyordu.
    # primer3 1269 uygun cift bulmustu; sucu urun boyuna atmak yanlis yone gonderiyordu.
    r, d = tasarla({"product_min_gc": 0, "product_max_gc": 35})
    notlar = d.get("notes", [])
    ok("ulasilamaz GC araligi: cift yok ve sebebi GC olarak yazilir",
       d.get("num_returned") == 0 and any("GC içeriği" in n for n in notlar), f"-> {notlar[:1]}")
    ok("  ...yaniltici 'urun boyu kisiti' notu EKLENMEZ",
       not any("ürün boyu kısıtına" in n for n in notlar),
       f"-> {[n[:60] for n in notlar if 'ürün boyu' in n]}")

    for prm, ad in (({"product_min_gc": 70, "product_max_gc": 30}, "min>max"),
                    ({"product_min_gc": 10, "product_max_gc": 140}, "100 ustu")):
        r, d = tasarla(prm)
        ok(f"gecersiz GC araligi ({ad}) -> 400",
           r.status_code == 400 and "GC" in d.get("error", ""), f"-> {d.get('error', '')[:60]}")


def test_varyant_araligi(c, engine):
    baslik("DNA sekmesinde varyant araligi (cok bazli varyant)")
    BAS = 50_000_001

    def tasarla(konum, **prm):
        r = c.post("/design", json={"assembly": "GRCh38", "chrom": "2",
                                    "position": konum, "params": prm})
        return r, (r.get_json() or {})

    def icerde(d, boy):
        bit = BAS + boy - 1
        return sum(1 for p in d.get("pairs") or [] for u in ("forward", "reverse")
                   if not (p[u]["genomic_end"] < bas_veya(p) or p[u]["genomic_start"] > bit)
                   and not (p[u]["genomic_end"] < BAS))

    def bas_veya(_p):
        return BAS

    r, tek = tasarla(BAS)
    ok("tek koordinat eskisi gibi calisir", r.status_code == 200 and len(tek.get("pairs") or []) == 10)
    ok("  ...cikti tek koordinat olarak bildirilir",
       tek["input"]["position"] == BAS and tek["input"]["variant_length"] == 1)

    # NOBETCI (2026-10-25): tek koordinat verilince arac varyantin kac baz uzandigini
    # bilmiyordu; 120 bp'lik delesyonun basi girilince 20 primerin 5'i varyantin
    # ICINE dusuyordu (o primer varyantli alele baglanmaz -> het, hom gorunur).
    for boy in (55, 120, 300):
        r, d = tasarla(f"{BAS}-{BAS + boy - 1}")
        n = icerde(d, boy)
        ok(f"{boy} bp aralik: hicbir primer varyantin icine dusmez",
           r.status_code == 200 and (d.get("pairs") or []) and n == 0, f"-> icerde {n}")
        ok(f"  ...varyant uzunlugu {boy} olarak bildirilir",
           d.get("input", {}).get("variant_length") == boy)
    r, d = tasarla(f"{BAS}-{BAS + 119}")
    ok("  ...aralik verildigi ve neden onemli oldugu not olarak yazilir",
       any("aralığın tamamının" in x for x in d.get("notes", [])))

    # Simetrik "varyanta min uzaklik" ile ayni koruma saglanamiyordu: 300 bp'lik
    # varyant icin 400 bp uzaklik gerekiyor, o da urunu PCR sinirinin ustune cikariyor.
    _r, d_eski = tasarla(BAS, min_dist_from_variant=200)
    eski_icerde = sum(1 for p in d_eski.get("pairs") or [] for u in ("forward", "reverse")
                      if not (p[u]["genomic_end"] < BAS or p[u]["genomic_start"] > BAS + 299))
    r, d_yeni = tasarla(f"{BAS}-{BAS + 299}")
    boylar = [x["product_size"] for x in d_yeni.get("pairs") or []]
    ok("300 bp: aralik korur, simetrik uzaklik (200) koruyamaz",
       eski_icerde > 0 and (d_yeni.get("pairs") or []) and max(boylar) <= 700,
       f"-> eski icerde {eski_icerde}, yeni urun en fazla {max(boylar, default=None)}")

    # Cok uzun varyant tek amplikona sigmaz: sessiz "cift yok" yerine yol gosteren hata
    r, d = tasarla(f"{BAS}-{BAS + 599}")
    hata = d.get("error", "")
    ok("600 bp aralik tek urune sigmaz -> 400 + Kirilma noktasi sekmesi onerisi",
       r.status_code == 400 and "Kırılma noktası" in hata, f"-> {hata[:80]}")

    # NOBETCI (2026-10-25): ilk regex'te kromozom oneki ":"siz de eslesiyordu ve
    # "50000001-50000120" -> kromozom 50000000, baslangic 1 olarak coozuluyordu.
    for konum, et in ((f"{BAS}-{BAS + 119}", "duz"),
                      (f"chr2:{BAS}-{BAS + 119}", "chr onekli"),
                      ("50,000,001-50,000,120", "virgullu"),
                      (f"{BAS}–{BAS + 119}", "uzun tire")):
        _r, d = tasarla(konum)
        ok(f"  bicim '{et}' dogru coozulur",
           d.get("input", {}).get("position") == BAS
           and d.get("input", {}).get("variant_length") == 120,
           f"-> {d.get('input', {}).get('position')} / {d.get('input', {}).get('variant_length')}")
    r, d = tasarla(f"{BAS + 100}-{BAS}")
    ok("ters aralik -> anlasilir 400",
       r.status_code == 400 and "küçük olamaz" in d.get("error", ""), f"-> {d.get('error','')[:60]}")


def test_gen_bolgesi(c, engine):
    baslik("Primer genin neresinde (ekzon / intron)")
    import transcripts as T
    if not engine.GENOME_PATHS.get("GRCh37"):
        atla("Gen bolgesi", "GRCh37 genomu yok")
        return
    try:
        T.autodetect_annotations()
        tx53 = T.get_transcript("NM_000546", "GRCh37")      # TP53, eksi iplik
        txcf = T.get_transcript("NM_000492", "GRCh37")      # CFTR, arti iplik
    except Exception as e:
        atla("Gen bolgesi", f"transkript tablosu yok ({str(e)[:40]})")
        return

    # Her ekzonun ve her intronun ORTASI dogru numarayi vermeli (iki iplikte de)
    for tx, ch, ad in ((tx53, "17", "TP53 (-)"), (txcf, "7", "CFTR (+)")):
        ekz = tx["exons_tx"]
        hata = []
        for n, (a, b) in enumerate(ekz, start=1):
            r = T.konum_bolgesi("GRCh37", ch, (a + b) // 2)
            if not r or r["kind"] != "ekzon" or r["exon"] != n:
                hata.append(f"ekzon {n}")
        for n in range(len(ekz) - 1):
            a = min(ekz[n][1], ekz[n + 1][1]) + 1
            b = max(ekz[n][0], ekz[n + 1][0]) - 1
            if b <= a:
                continue
            r = T.konum_bolgesi("GRCh37", ch, (a + b) // 2)
            if not r or r["kind"] != "intron" or r["intron"] != n + 1:
                hata.append(f"intron {n + 1}")
        ok(f"{ad}: {len(ekz)} ekzon + {len(ekz) - 1} intron ortasi dogru",
           not hata, f"-> {hata[:4]}")

    # NOBETCI: eksi iplikte ekzonun iki ucu FARKLI intronlara komsudur; "ekzon 8
    # siniri" demek belirsizdi. Genomik yon ile transkript yonu ters oldugu icin
    # alt uc intron 8'e, ust uc intron 7'ye bakar.
    alt = T.konum_bolgesi("GRCh37", "17", 7_577_017, 7_577_036)
    ust = T.konum_bolgesi("GRCh37", "17", 7_577_150, 7_577_169)
    ok("eksi iplikte ekzonun iki ucu farkli intronu gosterir",
       alt and ust and alt["kind"] == "sinir" and ust["kind"] == "sinir"
       and alt["intron"] == 8 and ust["intron"] == 7,
       f"-> alt {alt and alt['intron']}, ust {ust and ust['intron']}")
    ok("  ...numaralandirma MANE Select transkripte gore",
       alt and alt["acc"] == "NM_000546" and alt["mane"] == "MANE Select",
       f"-> {alt and (alt['acc'], alt['mane'])}")

    # Tasarim ciktilarina gercekten ekleniyor mu?
    d = c.post("/design", json={"assembly": "GRCh37", "chrom": "17",
                                "position": 7_577_120, "params": {}}).get_json() or {}
    ps = d.get("pairs") or []
    ok("DNA modu: her primerde gen bolgesi var",
       ps and all(x.get("gene_region") for p in ps for x in (p["forward"], p["reverse"])),
       f"-> {ps and ps[0]['forward'].get('gene_region', {}).get('label')}")
    ok("  ...gen ve transkript de bildirilir",
       ps and ps[0]["forward"]["gene_region"]["gene"] == "TP53"
       and ps[0]["forward"]["gene_region"]["acc"].startswith("NM_"))
    d = c.post("/design_breakpoint", json={"assembly": "GRCh37", "chrom": "17",
               "start": 7_577_100, "end": 7_578_000, "type": "del",
               "params": {"control_primer": True}}).get_json() or {}
    ps = d.get("pairs") or []
    ok("Kirilma noktasi: kontrol primerinde de var",
       ps and any(p.get("control", {}).get("gene_region") for p in ps),
       f"-> {[p.get('control', {}).get('gene_region', {}).get('label') for p in ps[:1]]}")

    # Gen disi koordinat: alan hic eklenmemeli (uydurma bolge yazilmamali)
    bos = T.konum_bolgesi("GRCh37", "17", 100, 119)
    ok("gen disinda bolge uydurulmaz", bos is None, f"-> {bos}")


def test_aday_havuzu(c, engine):
    baslik("Aday havuzu cesitliligi (dimer_pool)")
    if not engine.GENOME_PATHS.get("GRCh37"):
        atla("Aday havuzu", "GRCh37 genomu yok")
        return
    ok("varsayilan havuz 1000", int(engine.DEFAULTS["dimer_pool"]) == 1000,
       f"-> {engine.DEFAULTS['dimer_pool']}")

    # NOBETCI (2026-10-27, kullanici bildirdi): havuz 300'ken primer3'un donduru
    # adaylar birbirinin 1-2 baz kaymis kopyasiydi (300 cift = 42 farkli F,
    # 29 farkli R) ve GERCEKTEN daha iyi olan cift havuza hic girmiyordu. TP53'te
    # arac 532 bp'lik cifti oneriyordu; kullanici urun sinirini dusurunce ortaya
    # cikan 360 bp'lik cift hem daha kisa hem self-komplementaritesi dusuktu.
    KISA_R = "TCTCCTTACTGCTCCCACTC"

    def ilk(pool):
        prm = {} if pool is None else {"dimer_pool": pool}
        d = c.post("/design", json={"assembly": "GRCh37", "chrom": "17",
                                    "position": 7_577_180, "params": prm}).get_json() or {}
        ps = d.get("pairs") or []
        return (ps[0] if ps else None), ps

    p_yeni, _ = ilk(None)
    ok("TP53: varsayilan havuzda kisa/temiz cift 1. sirada",
       p_yeni and p_yeni["reverse"]["sequence"] == KISA_R and p_yeni["product_size"] == 360,
       f"-> {p_yeni and p_yeni['product_size']} bp")
    p_eski, _ = ilk(300)
    ok("  ...eski havuzda (300) o cift hic gorulmuyordu",
       p_eski and p_eski["reverse"]["sequence"] != KISA_R,
       f"-> {p_eski and p_eski['product_size']} bp")
    def en_yuksek_self(p):
        return max(p["forward"]["self_dimer_tm"], p["reverse"]["self_dimer_tm"])

    ok("  ...yeni secim hem daha kisa hem self-komplementaritesi dusuk",
       p_yeni and p_eski and p_yeni["product_size"] < p_eski["product_size"]
       and en_yuksek_self(p_yeni) < en_yuksek_self(p_eski)
       and p_yeni["dimer_score"] < p_eski["dimer_score"],
       f"-> self {en_yuksek_self(p_yeni)} < {en_yuksek_self(p_eski)}, "
       f"dimer {p_yeni['dimer_score']} < {p_eski['dimer_score']}")


def test_paralog_uyarisi(c, engine):
    baslik("Psodogen / yakin-ozdes kopya uyarisi")
    import paralog
    ok("tablo yuklu", len(paralog.PARALOGLAR) > 50, f"-> {len(paralog.PARALOGLAR)} gen")
    # Olcum GERCEK DIZIYLE yapildi; bilinen vakalar tabloda olmali.
    for gen, kopya in (("PMS2", "PMS2CL"), ("CYP21A2", "CYP21A1P"), ("NCF1", "NCF1B"),
                       ("HBA1", "HBA2"), ("SMN1", "SMN2"), ("STRC", "STRCP1")):
        adlar = [k["ad"] for k in paralog.gen_paraloglari(gen)]
        ok(f"  {gen} -> {kopya} tabloda", kopya in adlar, f"-> {adlar}")
    # NOBETCI (2026-10-25): ilk olcum tek tek 20-mer sayiyordu ve intronlardaki Alu
    # tekrarlari yuzunden BRCA1'e "paralogu BRCA2" diyordu. 500 bp / %90 sartiyla gitti.
    for gen in ("BRCA1", "LAMA2", "CFTR", "COL6A1", "DMD"):
        ok(f"  {gen} tek kopya: uyari YOK", not paralog.gen_paraloglari(gen),
           f"-> {[k['ad'] for k in paralog.gen_paraloglari(gen)]}")

    # Kopya psodogen mi, ayri bir gen mi? Tablodaki ciftlerin cogu gen ailesi
    # (ADH1A/B/C, MYH6/MYH7); hepsine "psodogen" demek yanlis olurdu.
    n = paralog.not_metni("SMN1", paralog.gen_paraloglari("SMN1"), "cdna")
    ok("kopya ayri bir gense 'paralog gen' denir (SMN2)", n and "paralog gen" in n)
    n = paralog.not_metni("PMS2", paralog.gen_paraloglari("PMS2"), "dna")
    ok("kopya NR_ ise 'psödogen' denir (PMS2CL)", n and "psödogen" in n)

    # Mod esikleri: govde benzerligi dusuk, benzerlik ekzonlarda yogun (MYH6/MYH7).
    n = paralog.not_metni("MYH7", paralog.gen_paraloglari("MYH7"), "dna")
    ok("ekzonlarda yogun benzerlikte intronlarin etkilenmedigi soylenir",
       n and "ekzonlarda yoğun" in n and "intron içindekiler etkilenmez" in n)
    # Zayif aile benzerligi genomik tasarimda gurultu yapmasin (ADH1B: govde %0,8)
    ok("zayif govde benzerligi DNA modunda uyari vermez",
       paralog.not_metni("ADH1B", paralog.gen_paraloglari("ADH1B"), "dna") is None)
    ok("  ...ama cDNA modunda verir (ekzon %11,7)",
       paralog.not_metni("ADH1B", paralog.gen_paraloglari("ADH1B"), "cdna") is not None)

    # Gen adi verilmeden, yalnizca koordinattan da bulunmali (WES'te olagan durum)
    tx = engine.tr.get_transcript("NM_000535", "GRCh37")      # PMS2
    orta = (tx["tx_start"] + tx["tx_end"]) // 2
    d = c.post("/design", json={"assembly": "GRCh37", "chrom": tx["chrom"],
                                "position": orta, "params": {}}).get_json() or {}
    uyari = [n for n in d.get("notes", []) if "PMS2CL" in n]
    ok("DNA modu: koordinattan PMS2 bulunup uyari verilir", bool(uyari), f"-> {uyari[:1]}")
    ok("  ...uyari ozgulluk dugmesine yonlendirir",
       uyari and "Özgüllüğü kontrol et" in uyari[0])

    d = c.post("/design", json={"assembly": "GRCh37", "chrom": "6",
                                "position": 129748948, "params": {}}).get_json() or {}
    ok("tek kopya gende (LAMA2) uyari cikmaz",
       not any("yakın-özdeş" in n for n in d.get("notes", [])))

    # RNA modunda ekzon benzerligi esas alinir (cDNA'da intron yok)
    d = c.post("/design_cdna", json={"assembly": "GRCh37", "acc": "NM_000344",
                                     "c_position": "c.400", "params": {}}).get_json() or {}
    ok("RNA modu: SMN1 icin SMN2 uyarisi",
       any("SMN2" in n for n in d.get("notes", [])),
       f"-> {[n[:70] for n in d.get('notes', []) if 'yakın-özdeş' in n]}")


def test_snp_3uc_uzakligi(engine):
    baslik("Yaygin varyantin 3' uca uzakligi (indel)")
    # NOBETCI (2026-10-28): forward'da varyantin BASLANGICI esas aliniyordu; 3' ucu
    # ortan 20 bp'lik indel "3' uctan 14 bp" gorunup 3' uyarisi vermiyordu.
    res = {"PRIMER_LEFT_0": (100, 20), "PRIMER_RIGHT_0": (400, 20)}   # F 100-119, R 381-400
    pairs = [{"forward": {}, "reverse": {}}]
    snps = [{"rsid": "rs1", "maf": 0.1, "indel": True, "template_offset": 105, "span": 20},
            {"rsid": "rs2", "maf": 0.1, "indel": True, "template_offset": 375, "span": 10},
            {"rsid": "rs3", "maf": 0.1, "indel": False, "template_offset": 395, "span": 1}]
    engine._annotate_pair_snps(pairs, res, [(0, 0, 0)], snps)
    f, r = pairs[0]["forward"]["snps"], pairs[0]["reverse"]["snps"]
    ok("forward: 3' ucu orten indel -> uzaklik 0", f and f[0]["distance_from_3p"] == 0, f"-> {f}")
    ok("  ...3' uyarisi verilir", pairs[0]["snp_at_3p"] is True)
    ok("reverse: 3' ucu orten indel -> 0 (negatif degil)",
       r and r[0]["distance_from_3p"] == 0, f"-> {[h['distance_from_3p'] for h in r]}")
    ok("reverse: 5' uctaki SNP dogru uzaklikta", r and r[-1]["distance_from_3p"] == 14)
    ok("yardimci: 3' ucun otesindeki varyant", engine.uc3_uzakligi(119, 90, 5) == 25
       and engine.uc3_uzakligi(381, 390, 3) == 9)


def test_atomik_veri_dosyalari(engine):
    baslik("Yarim kalan veri dosyalari (dbSNP indeksi, .fai)")
    import gzip as _gz
    import dbsnp
    d = tempfile.mkdtemp(prefix="allprime_atomik_")
    try:
        # snp151Common satiri: 25+ sutun, c[1] krom, c[2] bas0, c[3] bit, c[4] rs, c[11] tur, c[24] frekans
        def satir(rs, poz):
            c = ["0", "chr1", str(poz), str(poz + 1), f"rs{rs}"] + ["x"] * 6 + ["single"] + \
                ["x"] * 12 + ["0.7,0.3,"]
            return "\t".join(c) + "\n"
        kaynak = os.path.join(d, "snp.txt.gz")
        with _gz.open(kaynak, "wt") as f:
            for i in range(2000):
                f.write(satir(i + 1, 1000 + 10 * i))
        hedef = os.path.join(d, "dbsnp_common_hg38.apidx")
        dbsnp.build_index(kaynak, hedef, "GRCh38")
        ix = dbsnp.SnpIndex(hedef)
        bulunan = ix.overlaps("1", 1000, 1100)       # 1-tabanli 1001, 1011, ... 1091
        ok("dbSNP indeksi kurulur ve okunur", len(bulunan) == 10, f"-> {len(bulunan)}")
        ix.close()
        ok("  ...gecici .part dosyasi kalmaz", not os.path.exists(hedef + ".part"))

        # NOBETCI (2026-10-28): yazim yarida kesilince yarim indeks kaliyordu ve panel
        # onu "kurulu" gosteriyordu. Bozuk kaynakla kurulum hedefe hic dokunmamali.
        bozuk = os.path.join(d, "bozuk.txt.gz")
        with open(kaynak, "rb") as f:
            veri = f.read()
        with open(bozuk, "wb") as f:
            f.write(veri[:len(veri) // 2])
        hedef2 = os.path.join(d, "dbsnp_common_hg19.apidx")
        try:
            dbsnp.build_index(bozuk, hedef2, "GRCh37")
            hata = False
        except Exception:
            hata = True
        ok("bozuk kaynak -> hata, yarim indeks birakilmaz",
           hata and not os.path.exists(hedef2) and not os.path.exists(hedef2 + ".part"))

        # .fai: tam / yarim / yok
        fa = os.path.join(d, "kucuk.fa")
        with open(fa, "w", newline="\n") as f:
            f.write(">1\n" + "ACGT" * 15 + "\n" + "ACGTAC\n" + ">2\n" + "GGCC" * 15 + "\nGG\n")
        with open(fa + ".fai", "w", newline="\n") as f:
            f.write("1\t66\t3\t60\t61\n2\t62\t74\t60\t61\n")
        ok(".fai tam -> tutarli", engine.fai_tutarli(fa))
        with open(fa + ".fai", "w", newline="\n") as f:
            f.write("1\t66\t3\t60\t61\n")
        ok(".fai yarim (son kromozom eksik) -> tutarsiz", not engine.fai_tutarli(fa))
        with open(fa + ".fai", "w", newline="\n") as f:
            f.write("1\t66\t3\t60\t61\n2\t6")
        ok(".fai son satiri kesik -> tutarsiz", not engine.fai_tutarli(fa))
        os.remove(fa + ".fai")
        ok(".fai yok -> tutarsiz", not engine.fai_tutarli(fa))
        for asm, yol in engine.GENOME_PATHS.items():
            if yol:
                ok(f"  gercek {asm} indeksi tutarli (yanlis alarm yok)", engine.fai_tutarli(yol))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_indirme_devami(engine):
    baslik("Kaldigi yerden indirme (surum degisirse karismaz)")
    import gzip as _gz
    import downloads

    class Yanit:
        def __init__(self, kod, govde, basliklar=None):
            self.status_code, self._g = kod, govde
            self.headers = dict(basliklar or {})
            self.headers.setdefault("Content-Length", str(len(govde)))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_content(self, n):
            for i in range(0, len(self._g), n):
                yield self._g[i:i + n]

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(self.status_code)

        def close(self):
            pass

    istekler = []
    davranis = {}

    def sahte_get(url, headers=None, stream=False, timeout=None):
        istekler.append(dict(headers or {}))
        return davranis["f"](dict(headers or {}))

    import transcripts as T
    YENI = b"YENI-SURUM-" * 50
    d = tempfile.mkdtemp(prefix="allprime_indir_")
    eski_get = downloads.requests.get
    eski_kok = os.environ.get("ALLPRIME_DATA_ROOT")
    # Basarili _calistir rescan() ile transkript yolunu test dosyasina cevirir; geri alinir
    eski_annot = dict(T.ANNOT_PATHS)
    eski_idx = dict(T._INDEX_CACHE)
    downloads.requests.get = sahte_get
    try:
        gecici = os.path.join(d, "dosya.gz.indiriliyor")
        url = "https://ornek/dosya.gz"

        # 1) Dogrulayicisi olmayan eski parca: uzerine EKLENMEZ, bastan inilir
        with open(gecici, "wb") as f:
            f.write(b"ESKI-SURUM-PARCA")
        istekler.clear()
        davranis["f"] = lambda h: Yanit(200, YENI, {"ETag": '"v2"'})
        downloads._indir("t", url, gecici)
        with open(gecici, "rb") as f:
            icerik = f.read()
        ok("dogrulayicisiz parca bastan inilir (eklenmez)",
           icerik == YENI and "Range" not in istekler[0], f"-> {istekler[:1]}")
        ok("  ...ETag kaydedilir", downloads._dogrulayici_oku(gecici, url) == '"v2"')

        # 2) NOBETCI (2026-10-28): yarim parca var ama sunucudaki dosya DEGISMIS.
        # If-Range tutmaz, sunucu tamamini (200) gonderir: eklenmemeli.
        with open(gecici, "wb") as f:
            f.write(YENI[:100])
        istekler.clear()
        YENI2 = b"UCUNCU-SURUM-" * 40
        davranis["f"] = lambda h: (Yanit(200, YENI2, {"ETag": '"v3"'}))
        downloads._indir("t", url, gecici)
        with open(gecici, "rb") as f:
            icerik = f.read()
        ok("dosya degismisse (200) parca atilip yeni surum inilir",
           icerik == YENI2 and istekler[0].get("If-Range") == '"v2"',
           f"-> If-Range {istekler[0].get('If-Range')}, boy {len(icerik)}")

        # 3) Ayni surum: 206 ile kaldigi yerden devam
        with open(gecici, "wb") as f:
            f.write(YENI2[:100])
        istekler.clear()
        davranis["f"] = lambda h: Yanit(206, YENI2[100:], {"ETag": '"v3"'})
        downloads._indir("t", url, gecici)
        with open(gecici, "rb") as f:
            icerik = f.read()
        ok("ayni surumde kaldigi yerden devam eder (206)",
           icerik == YENI2 and istekler[0].get("Range") == "bytes=100-")

        # 4) Indirilen dosya bozuksa (acilamiyor) silinir: eskiden kaliyordu ve her
        # yeni deneme ayni bozuk dosyadan "devam" ediyordu - hata hic gecmiyordu.
        os.environ["ALLPRIME_DATA_ROOT"] = d
        it = downloads.catalog()["refgene_GRCh37"]
        tam = _gz.compress(b"chr1\t" * 5000)
        davranis["f"] = lambda h: Yanit(200, tam[:len(tam) // 2], {"ETag": '"x"'})
        downloads._calistir("refgene_GRCh37")
        st = downloads._STATE.get("refgene_GRCh37", {})
        ok("bozuk gzip -> hata durumu, anlasilir mesaj",
           st.get("durum") == "hata" and "bozuk" in st.get("hata", "").lower(),
           f"-> {st.get('durum')}: {st.get('hata', '')[:60]}")
        ok("  ...bozuk parca ve dogrulayici silinir, hedef olusmaz",
           not os.path.exists(it["hedef"] + ".indiriliyor") and not os.path.exists(it["hedef"])
           and downloads._dogrulayici_oku(it["hedef"] + ".indiriliyor", it["url"]) is None)
        davranis["f"] = lambda h: Yanit(200, tam, {"ETag": '"x"'})
        downloads._calistir("refgene_GRCh37")
        ok("  ...sonraki deneme bastan iner ve tamamlanir",
           downloads._STATE.get("refgene_GRCh37", {}).get("durum") == "tamam"
           and os.path.exists(it["hedef"]))
    finally:
        downloads.requests.get = eski_get
        if eski_kok is None:
            os.environ.pop("ALLPRIME_DATA_ROOT", None)
        else:
            os.environ["ALLPRIME_DATA_ROOT"] = eski_kok
        downloads._STATE.pop("refgene_GRCh37", None)
        T.ANNOT_PATHS.clear()
        T.ANNOT_PATHS.update(eski_annot)
        T._INDEX_CACHE.clear()
        T._INDEX_CACHE.update(eski_idx)
        shutil.rmtree(d, ignore_errors=True)


def test_degerlendir_fai_yok(c, engine):
    baslik("Degerlendir: genom var ama .fai yok")
    if HTTP:
        return atla(".fai yok", "HTTP modu: motorun ici degistirilemez")
    # NOBETCI (2026-10-28): SpecificityError yakalanmiyordu -> 500 "Beklenmeyen hata"
    d = tempfile.mkdtemp(prefix="allprime_fai_")
    eski = engine.GENOME_PATHS.get("GRCh38", "")
    try:
        fa = os.path.join(d, "g.fa")
        with open(fa, "w") as f:
            f.write(">1\n" + "ACGT" * 100 + "\n")
        engine.GENOME_PATHS["GRCh38"] = fa
        r = c.post("/evaluate", json={"assembly": "GRCh38",
                                      "forward": "GCTGAGGAAGTTGGTGACCA",
                                      "reverse": "ATGATCTAGGTTGTGGTCCT"})
        j = r.get_json() or {}
        ok("400 + anlasilir mesaj (500 degil)",
           r.status_code == 400 and ".fai" in j.get("error", ""),
           f"-> {r.status_code}: {j.get('error', '')[:60]}")
    finally:
        engine.GENOME_PATHS["GRCh38"] = eski
        shutil.rmtree(d, ignore_errors=True)


def test_ayar_sinirlari(c):
    baslik("Ayar sinirlari (tasarim, ozgulluk, Degerlendir)")
    import ayarlar
    import evaluate
    import specificity as S

    def tasarla(**prm):
        r = c.post("/design", json={"assembly": "GRCh37", "chrom": "17",
                                    "position": 7_577_120, "params": prm})
        return r, (r.get_json() or {})

    # NOBETCI (2026-10-28): bunlarin hepsi primer3'un ham Ingilizce mesajiyla 500
    # "Beklenmeyen hata" donuyordu. Ayar tasarimdan ONCE denetlendigi icin genom gerekmez.
    for prm, ad in (({"dna_conc": 0}, "Primer (nM)"),
                    ({"salt_monovalent": -10}, "Na⁺ (mM)"),
                    ({"primer_max_size": 100}, "Primer uzunluk max"),
                    ({"primer_min_size": 0}, "Primer uzunluk min"),
                    ({"product_size_min": -100}, "Amplikon min (bp)"),
                    ({"max_self_end": -1}, "max_self_end"),
                    ({"dimer_pool": 0}, "dimer_pool")):
        r, d = tasarla(**prm)
        ok(f"{prm} -> 400, ayar adiyla", r.status_code == 400 and ad in d.get("error", "")
           and "arasında" in d.get("error", ""), f"-> {r.status_code}: {d.get('error', '')[:70]}")

    # Sessiz yanlislar: hata vermeden yanlis sonuc uretiyorlardi
    r, d = tasarla(num_return=-5)
    ok("num_return=-5 -> 400 (eskiden 995 cift donuyordu)", r.status_code == 400,
       f"-> {r.status_code}")
    r, d = tasarla(min_dist_from_variant=-50)
    ok("negatif varyanta uzaklik -> 400 (koruma bolgesi 1 baza iniyordu)",
       r.status_code == 400, f"-> {r.status_code}")
    r = c.post("/design", json={"assembly": "GRCh37", "chrom": "17", "position": 7_577_120,
                                "params": {"dna_conc": 0}, "lang": "en"})
    ok("  ...Ingilizce mesaj", r.status_code == 400
       and "must be between" in (r.get_json() or {}).get("error", ""))
    ok("sinir ici deger ve metin olarak sayi kabul edilir",
       engine_birlestir_ok(ayarlar))

    # Ozgulluk: dogrudan check_pair (genom taramasina gelmeden reddedilmeli)
    for prm in ({"max_mismatch": -1}, {"seed_len": "abc"}, {"max_offtarget_product": -5},
                {"risk_high_max": 5, "risk_medium_max": 2}):
        try:
            S.check_pair("YOK.fa", "AGAAGCCGTGAGAAGTGA", "ATGATCTAGGTTGTGGTCCT", params=prm)
            sonuc = "kabul"
        except S.SpecificityError as e:
            sonuc = "red: " + str(e)[:50]
        except Exception as e:
            sonuc = f"{type(e).__name__}"
        ok(f"ozgulluk {prm} -> anlasilir red (eskiden 'ozgul' ya da 500)",
           sonuc.startswith("red"), f"-> {sonuc}")

    # Degerlendir: metin olarak gelen sayi cevrilir, sinir disi reddedilir
    ok("Degerlendir: \"5000\" -> 5000", evaluate._ayarlar({"max_product": "5000"})["max_product"] == 5000)
    for prm in ({"tm_min": "abc"}, {"max_product": -1}, {"dna_conc": 0}):
        try:
            evaluate._ayarlar(prm)
            sonuc = "kabul"
        except evaluate.EvaluateError:
            sonuc = "red"
        ok(f"Degerlendir {prm} reddedilir", sonuc == "red")
    r = c.post("/evaluate", json={"assembly": "GRCh38", "forward": "AGAAGCCGTGAGAAGTGA",
                                  "params": {"tm_min": "abc"}})
    ok("  .../evaluate 400 doner (500 degil)", r.status_code == 400, f"-> {r.status_code}")


def engine_birlestir_ok(ayarlar):
    p = ayarlar.birlestir([{"num_return": 10, "dna_conc": 50.0}],
                          {"num_return": "12", "dna_conc": "0.5"}, ayarlar.TASARIM_SINIRLARI)
    return p["num_return"] == 12 and p["dna_conc"] == 0.5


def test_rna_varyant_araligi(c, engine):
    baslik("RNA sekmesinde varyant araligi (c.76_78del)")

    def tasarla(cpos, **prm):
        r = c.post("/design_cdna", json={"assembly": "GRCh37", "acc": "NM_000546",
                                         "c_position": cpos, "params": prm})
        return r, (r.get_json() or {})

    # NOBETCI (2026-10-28): araligin yalnizca ilk konumu aliniyordu - DNA sekmesinde
    # 2026-10-25'te duzeltilen hatanin aynisi. Primer varyantin icine dusebiliyordu.
    def icerde(d, a, b):
        return sum(1 for p in d.get("pairs") or [] for u in ("forward", "reverse")
                   if not (p[u]["cdna_end"] < a or p[u]["cdna_start"] > b))

    r, d = tasarla("c.700_760del")
    a, b = d.get("variant_cdna_index"), d.get("variant_cdna_end")
    ok("aralik okunur (61 nt)", r.status_code == 200 and d.get("variant_length") == 61
       and b - a == 60, f"-> {r.status_code} {a}-{b}")
    ok("  ...hicbir primer varyantin icine dusmez",
       (d.get("pairs") or []) and icerde(d, a, b) == 0, f"-> icerde {icerde(d, a, b)}")
    ok("  ...not yazilir", any("aralığın tamamının" in n for n in d.get("notes", [])))
    _r, eski = tasarla("c.700", min_dist_from_variant=10)
    print(f"  (bilgi) yalniz ilk konum + 10 nt payla varyant icine dusen primer: "
          f"{icerde(eski, a, b)}", flush=True)

    _r, d2 = tasarla("c.672+5_675del")
    _r, d3 = tasarla("c.673_675")
    ok("intronik uclu aralik -> yalniz ekzonik kismi",
       d2.get("variant_cdna_index") == d3.get("variant_cdna_index")
       and d2.get("variant_cdna_end") == d3.get("variant_cdna_end"))
    r, d = tasarla("c.672+5_672+20del")
    ok("tamamen intronik aralik -> 400", r.status_code == 400 and "intronik" in d.get("error", ""))
    r, d = tasarla("c.760_700del")
    ok("ters aralik -> 400", r.status_code == 400 and "önce" in d.get("error", ""))
    r, d = tasarla("c.100_900del")
    ok("urune sigmayan aralik -> yol gosteren 400",
       r.status_code == 400 and "Varyant aralığı" in d.get("error", ""), f"-> {d.get('error', '')[:60]}")
    r, d = tasarla("c.700")
    ok("tek konum eskisi gibi", r.status_code == 200 and d.get("variant_length") == 1
       and d.get("input", {}).get("c_label") == "c.700")


def test_rna_transkript_ucu(c, engine):
    baslik("RNA sekmesinde transkript ucuna yakin varyant")
    # NOBETCI (2026-10-28): DNA modundaki "kromozom ucu" on kontrolu RNA'da yoktu.
    # NM_000546 c.-100 (cDNA'nin 43. bazi) ve c.*1150 (2474 / 2512): primer3 bos
    # donuyor, sebep "urun boyu" ve "kisit kaldirildi - varyantlar isaretlendi" /
    # "hicbir cift ekson sinirini kapsamiyor" gibi YANLIS uyarilar gorunuyordu.
    for cpos, uc in (("c.-100", "5' ucuna"), ("c.*1150", "3' ucuna")):
        r = c.post("/design_cdna", json={"assembly": "GRCh38", "acc": "NM_000546",
                                         "c_position": cpos})
        d = r.get_json() or {}
        ok(f"{cpos} -> yol gosteren 400 ({uc})", r.status_code == 400
           and uc in d.get("error", "") and "DNA modunda" in d.get("error", ""),
           f"-> {r.status_code} {d.get('error', '')[:70]}")
    r = c.post("/design_cdna", json={"assembly": "GRCh38", "acc": "NM_000546",
                                     "c_position": "c.-100", "lang": "en"})
    ok("  ...EN modda Ingilizce", "5' end" in (r.get_json() or {}).get("error", ""))
    r = c.post("/design_cdna", json={"assembly": "GRCh38", "acc": "NM_000546",
                                     "c_position": "c.-100",
                                     "params": {"min_dist_from_variant": 10}})
    d = r.get_json() or {}
    ok("  ...pay kuculunce tasarlanir", r.status_code == 200 and d.get("pairs"),
       f"-> {r.status_code} {len(d.get('pairs') or [])} cift")


def test_erisim_denetimi(c):
    baslik("Motor erisim denetimi (anahtar, Host, CORS)")
    # NOBETCI (2026-10-28, inceleme bulgusu 6): CORS herkese acikti, kimlik yoktu;
    # tarayicidaki herhangi bir site text/plain govdeyle /set_genome'u cagirip
    # genom kaydini silebiliyordu (get_json(force=True) preflight'i atlatiyor).
    # HTTP modunda motorun GERCEK anahtari (ALLPRIME_TOKEN exe'ye ulasti mi - asil soru bu)
    if HTTP:
        anahtar = HTTP["token"]
    else:
        import server
        eski = server.TOKEN
        anahtar = server.TOKEN = "deneme-anahtari"
    bos = {"X-AllPrime-Token": ""}
    try:
        r = c.get("/health", headers=bos)
        ok("anahtarsiz istek -> 401", r.status_code == 401, f"-> {r.status_code}")
        r = c.post("/set_genome", data='{"assembly": "GRCh38", "path": ""}',
                   content_type="text/plain", headers=bos)
        ok("  ...text/plain /set_genome da -> 401 (kayit silinmez)", r.status_code == 401)
        r = c.get("/health", headers={"X-AllPrime-Token": "yanlis"})
        ok("yanlis anahtar -> 401", r.status_code == 401)
        r = c.get("/health?lang=en", headers={"X-AllPrime-Token": "yanlis"})
        ok("  ...mesaj EN modda Ingilizce", "Unauthorized" in (r.get_json() or {}).get("error", ""))
        r = c.get("/health", headers={"X-AllPrime-Token": anahtar})
        ok("dogru anahtar -> 200", r.status_code == 200)
        r = c.get("/health", headers={"X-AllPrime-Token": anahtar,
                                      "Host": "kotu.example:5077"})
        ok("yabanci Host (DNS rebinding) -> 403", r.status_code == 403, f"-> {r.status_code}")
        r = c.get("/health", headers={"X-AllPrime-Token": anahtar,
                                      "Host": "127.0.0.1:5077"})
        ok("  ...127.0.0.1:port kabul", r.status_code == 200)
        on = {"Access-Control-Request-Method": "POST",
              "Access-Control-Request-Headers": "content-type,x-allprime-token"}
        r = c.options("/set_genome", headers={"Origin": "file://", **on})
        ok("CORS on istegi: arayuz (file://) izinli",
           r.headers.get("Access-Control-Allow-Origin") == "file://"
           and "x-allprime-token" in r.headers.get("Access-Control-Allow-Headers", "").lower())
        for koken in ("https://kotu.example", "null"):
            r = c.options("/set_genome", headers={"Origin": koken, **on})
            ok(f"  ...{koken} izinsiz", not r.headers.get("Access-Control-Allow-Origin"))
    finally:
        if not HTTP:
            server.TOKEN = eski
    if not HTTP:
        ok("ALLPRIME_TOKEN yoksa (gelistirme) denetim kapali", c.get("/health").status_code == 200)


def test_turkce_harfler_ve_ensembl_hatasi(engine):
    baslik("Turkce harfli motor mesajlari ve Ensembl HTTP hatasi (K9, K-01)")
    # NOBETCI (K9): Turkce harf gerektiren sozcuklerin harfsiz yazildigi t() metni 0 olmali;
    # 'gerekli' ve 'olamaz' harfsiz de dogru oldugu icin listede yok. Ensembl 503 gelince ham
    # 'cekme hatasi: 503' yerine ne yapilacagini soyleyen aciklama (ham kod parantezde) beklenir.
    import ast
    from lang import set_lang
    ipucu = re.compile(r"\b(icin|degil|olmali|gecersiz|cift|urun|ozgul|bulunamadi|siniri?|kisa|uzun|"
                       r"govdesi|yuklen|kutuphane|ucuncu|dosyasi|tanitilmamis|hatasi|eslesen|baslangic|"
                       r"bitis|buyuk|kucuk|uzerine|icinde|disinda|sayisi|yogun|kaldirildi|anlasilamadi)\b", re.I)
    tr_harf = set("çğıöşüÇĞİÖŞÜ")
    bul = []
    for ad in sorted(os.listdir(BURASI)):
        if not ad.endswith(".py") or ad.startswith("test_") or ad in ("lisans_bildirimi.py", "paralog_olc.py"):
            continue
        with open(os.path.join(BURASI, ad), encoding="utf-8") as f:
            agac = ast.parse(f.read())
        for n in ast.walk(agac):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "t" and len(n.args) == 2:
                a = n.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    p = [a.value]
                elif isinstance(a, ast.JoinedStr):
                    p = [v.value for v in a.values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
                else:
                    p = []
                m = "".join(p)
                if m.strip() and not (set(m) & tr_harf) and ipucu.search(m):
                    bul.append(f"{ad}:{n.lineno}")
    ok("harfsiz Turkce motor mesaji yok", not bul, f"-> {len(bul)} {bul[:4]}")

    import requests as _rq

    class _Yanit:
        status_code, ok, text = 503, False, ""
    eski_get = engine.requests.get
    engine.requests.get = lambda *a, **k: _Yanit()
    try:
        for dil, beklenen in (("tr", ("alınamadı", "HTTP 503", "yeniden deneyin", "indirin")),
                              ("en", ("Could not get the sequence", "503", "try again", "download"))):
            set_lang(dil)
            try:
                engine.fetch_sequence_ensembl("GRCh38", "1", 1000, 1100)
                m = "(hata yok)"
            except Exception as e:
                m = str(e)
            ok(f"Ensembl 503 [{dil}]: aciklama ve ham kod", all(b in m for b in beklenen), f"-> {m[:90]}")
    finally:
        engine.requests.get = eski_get
        set_lang("tr")


def test_ceviri_ve_mane(c, engine):
    baslik("Ceviri eksikleri ve MANE surum secimi")
    # NOBETCI (2026-10-28, inceleme bulgusu 8): bu metinler EN modda Turkce geliyordu.
    import transcripts
    import downloads
    from lang import set_lang
    d = c.post("/design_sequence_pair", json={
        "forward": ">baslik\n" + "ATGGCTAGCTTGACGGTACCAGTTCGAACGTAGGCTAACTGGCTAGTTGACTTGGCAC" * 3,
        "reverse": "GTACCGTAGCTGATCGATCGGATCCTAGGCTTAACGGTCAGCTAGCTTAGGCCTAGGCAA" * 3,
        "lang": "en"}).get_json() or {}
    notlar = " ".join(d.get("notes") or [])
    ok("iki dizi modu notu EN: 'Forward region'", "Forward region:" in notlar
       and "bölgesi" not in notlar, f"-> {notlar[:80]}")
    if transcripts.ANNOT_PATHS.get("GRCh38"):
        set_lang("en")
        try:
            tx = transcripts.get_transcript("NM_000546.6", "GRCh38")
        finally:
            set_lang("tr")
        ok("refGene surum notu EN", "does not keep version" in (tx.get("version_note") or ""),
           f"-> {(tx.get('version_note') or '')[:60]}")
    else:
        atla("refGene surum notu EN", "transkript tablosu yok")

    # NOBETCI (inceleme bulgusu 11): metin siralamasinda v1.10 < v1.9 sayiliyordu
    class _Yanit:
        text = ('<a href="MANE.GRCh38.v1.9.summary.txt.gz">x</a>'
                '<a href="MANE.GRCh38.v1.10.summary.txt.gz">x</a>'
                '<a href="MANE.GRCh38.v1.2.summary.txt.gz">x</a>')

        def raise_for_status(self):
            pass
    asil = downloads.requests.get
    downloads.requests.get = lambda *a, **k: _Yanit()
    try:
        url = downloads._mane_url()
    finally:
        downloads.requests.get = asil
    ok("MANE: v1.10 > v1.9 (sayisal)", url.endswith("MANE.GRCh38.v1.10.summary.txt.gz"),
       f"-> {url.rsplit('/', 1)[-1]}")


def test_iplik_yonu(c):
    baslik("F/R adlandirmasi genin okuma yonune gore (eksi iplik)")
    # NOBETCI (2026-10-28): yayinlanmis 22 TP53 ciftinin 21'ine "F ve R rolleri yer
    # degismis" deniyordu. TP53 eksi iplikte; laboratuvar F/R'yi genin yonune gore
    # adlandirir, AllPrime genomun + ipligine gore bakiyordu. Ciftler acik erisimli
    # makalelerden (test-verileri/dogrulanmis_primerler.xlsx).
    yayinlanmis = [
        ("TP53", "CCATGGGACTGACTTTCTGC", "GAGGAATCCCAAAGTTCCAA"),    # Wooler 2016, ekzon 4
        ("TP53", "TGTTCACTTGTGCCCTGACT", "TTAACCCCTCCTCCCAGAGA"),    # Akouchekian 2016, 5-6
        ("TP53", "GACCTGATTTCCTTACTGCCTCTTG", "AATCTGAGGCATAACTGCACCCTT"),  # Krypuy 2007, 8
        ("MLH1", "TTCAGATAACCTTTCCCTTTGG", "AGCAATACCCCAACTGAAGG"),  # Mirabdolhosseini 2023, 4
        ("PTEN", "CTCTGGAATCCAGTGTTTCTTT", "CCAATAAATTCTCAGATCCAGG"),  # Akouchekian 2016, 5
    ]
    for gen, F, R in yayinlanmis:
        d = c.post("/evaluate", json={"forward": F, "reverse": R,
                                      "assembly": "GRCh38"}).get_json() or {}
        ok(f"{gen} (yayinlanmis, {d.get('pair_gene_strand')} iplik): roller yer degismis DENMEZ",
           d.get("pair_gene") == gen and d.get("pair_roles_swapped") is False,
           f"-> {d.get('pair_gene')} {d.get('pair_roles_swapped')}")
    for gen, F, R in (yayinlanmis[0], yayinlanmis[3]):
        d = c.post("/evaluate", json={"forward": R, "reverse": F,
                                      "assembly": "GRCh38"}).get_json() or {}
        ok(f"  ...{gen} ters girilince uyari (gen adiyla)", any(
            "yer değişmiş" in f["text"] and gen in f["text"] for f in d.get("findings") or []))


def test_govde_tipleri(c):
    baslik("Govde ve alan tipleri - 500 yerine anlasilir 400")
    # NOBETCI (2026-10-29 hata taramasi): 844 bozuk istekten 55'i 500 veriyordu.
    for uc in ("/design", "/design_cdna", "/design_skipping", "/design_sequence",
               "/design_sequence_pair", "/evaluate", "/evaluate_cdna", "/downloads/cancel"):
        r = c.post(uc, data="5", content_type="application/json")
        ok(f"{uc}: govde nesne degil -> 400", r.status_code == 400, f"-> {r.status_code}")
    for uc, g in (("/design_cdna", {"assembly": "GRCh38", "acc": 5, "c_position": "c.1"}),
                  ("/design_skipping", {"assembly": "GRCh38", "acc": ["NM_1"], "exon": 2}),
                  ("/specificity", {"assembly": [], "forward": "ACGTACGTACGTACGTAC",
                                    "reverse": "ACGTACGTACGTACGTAC"}),
                  ("/evaluate", {"forward": "AGAAGCCGTGAGAAGTGA", "assembly": {"a": 1}}),
                  ("/downloads/cancel", {"item": 5}),
                  ("/set_genome", {"assembly": "GRCh38", "path": ["a"]})):
        r = c.post(uc, json=g)
        ok(f"{uc}: yanlis tipte alan -> 400", r.status_code == 400 and
           (r.get_json() or {}).get("error"), f"-> {r.status_code}")


def test_konum_ayristirma(c, engine):
    baslik("Konum ayristirma - sessiz yanlis konum yok")
    # NOBETCI (2026-10-29): "7676154.5" sessizce 76.761.545, "c.1.234" sessizce c.1 oluyordu.
    for girdi in ("7676154.5", "7676154.0", "76.76.154"):
        try:
            engine.varyant_araligi(girdi)
            ok(f"DNA {girdi!r} reddedilir", False, "-> kabul edildi")
        except engine.PrimerError:
            ok(f"DNA {girdi!r} reddedilir", True)
    ok("DNA binlik yazimlar kabul",
       engine.varyant_araligi("7.676.154") == (7676154, 7676154)
       and engine.varyant_araligi("chr2:50,000,001-50,000,300") == (50000001, 50000300)
       and engine.varyant_araligi("7 676 154") == (7676154, 7676154))
    for cp, kod in (("c.1.234", 400), ("c.1 234", 400), ("400.9", 400), ("c.1-", 400),
                    ("c.76A>T", 200), ("c.76_78del", 200), ("c.123_124insAT", 200)):
        r = c.post("/design_cdna", json={"assembly": "GRCh38", "acc": "NM_000546", "c_position": cp})
        ok(f"c. {cp!r} -> {kod}", r.status_code == kod, f"-> {r.status_code}")
    # Eski kod "5000000.1"i 50.000.001 okuyup GECERLI bir silinme gibi tasarliyordu.
    r = c.post("/design_breakpoint", json={"assembly": "GRCh38", "chrom": "2",
                                           "start": "5000000.1", "end": "50012000"})
    ok("kirilma noktasi '5000000.1' -> 400 (50000001 degil)", r.status_code == 400,
       f"-> {r.status_code}")


def test_uzun_transkript_suresi(c):
    baslik("Uzun transkriptte RNA tasarimi makul surede")
    # NOBETCI (2026-10-29): primer3'e transkriptin tamami veriliyordu; sure karesel
    # buyuyordu (DMD 16,5 sn, NEB 80 sn, TTN 10 dk+). Artik hedef cevresi (dahil bolge).
    t0 = time.time()
    r = c.post("/design_cdna", json={"assembly": "GRCh38", "acc": "NM_004006", "c_position": "c.6000"})
    sure = time.time() - t0
    ok("DMD c.6000 < 5 sn", r.status_code == 200 and sure < 5, f"{sure:.1f} sn")
    t0 = time.time()
    r = c.post("/design_skipping", json={"assembly": "GRCh38", "acc": "NM_004006", "exon": 45})
    sure = time.time() - t0
    ok("DMD ekzon 45 atlama < 5 sn", r.status_code == 200 and (r.get_json() or {}).get("pairs")
       and sure < 5, f"{sure:.1f} sn")


def test_bozuk_veri_dosyalari(c):
    baslik("Yarim/bozuk veri dosyalari - sessiz kalmaz, 500 vermez")
    if HTTP:
        return atla("Bozuk veri dosyalari", "HTTP modu: motorun ici degistirilemez")
    import dbsnp
    import transcripts as T
    tmp = tempfile.mkdtemp(prefix="allprime_bozuk_")
    asil_annot, asil_mane = dict(T.ANNOT_PATHS), T.MANE_PATH
    asil_db = dict(dbsnp.DBSNP_PATHS)
    try:
        # NOBETCI (2026-10-29): yarim refGene / MANE 500 + ham "Compressed file ended..."
        if T.ANNOT_PATHS.get("GRCh38"):
            y = os.path.join(tmp, "refGene_hg38.txt.gz")
            v = open(T.ANNOT_PATHS["GRCh38"], "rb").read()
            open(y, "wb").write(v[:len(v) // 3])
            T.ANNOT_PATHS["GRCh38"] = y
            T._INDEX_CACHE.pop("GRCh38", None); T._BOLGE_CACHE.pop("GRCh38", None)
            r = c.get("/transcripts?gene=TP53&assembly=GRCh38")
            ok("yarim refGene -> 400 + dosya adi", r.status_code == 400 and
               "refGene_hg38" in (r.get_json() or {}).get("error", ""), f"-> {r.status_code}")
            T.ANNOT_PATHS.update(asil_annot)
            T._INDEX_CACHE.pop("GRCh38", None); T._BOLGE_CACHE.pop("GRCh38", None)
        if T.MANE_PATH and os.path.exists(T.MANE_PATH):
            y = os.path.join(tmp, "MANE.summary.txt.gz")
            v = open(T.MANE_PATH, "rb").read()
            open(y, "wb").write(v[:len(v) // 2])
            T.MANE_PATH = y; T._MANE_CACHE = None
            r = c.get("/transcripts?gene=TP53&assembly=GRCh38")
            ok("yarim MANE -> 400 (eksik listeyle sessizce devam etmez)", r.status_code == 400,
               f"-> {r.status_code}")
            T.MANE_PATH = asil_mane; T._MANE_CACHE = None
        # NOBETCI (2026-10-29): yarim dbSNP indeksiyle SNP kacinmasi SESSIZCE kapaniyordu
        # (TP53'te 7 yerine 0 varyant, 'available: True').
        kaynak = dbsnp.DBSNP_PATHS.get("GRCh38")
        if kaynak and os.path.exists(kaynak):
            y = os.path.join(tmp, "dbsnp_yarim.apidx")
            with open(kaynak, "rb") as f:
                open(y, "wb").write(f.read(40_000_000))
            eski = dbsnp._INDEX_CACHE.pop("GRCh38", None)
            dbsnp.DBSNP_PATHS["GRCh38"] = y
            d = c.post("/design", json={"assembly": "GRCh38", "chrom": "17",
                                        "position": 7675000}).get_json() or {}
            ok("yarim dbSNP: tasarimda UYARI notu", any("dbSNP" in n and ("UYARI" in n or "WARNING" in n)
               for n in d.get("notes") or []), f"-> {d.get('dbsnp')}")
            ok("  ...dbsnp 'available' degil", (d.get("dbsnp") or {}).get("available") is False)
            h = c.get("/health").get_json() or {}
            ok("  .../health dbSNP GRCh38 yok gorunur", h.get("dbsnp", {}).get("GRCh38") is False)
            ix = dbsnp._INDEX_CACHE.pop("GRCh38", None)
            if ix:
                ix.close()
            dbsnp.DBSNP_PATHS.update(asil_db)
            getattr(dbsnp, "_BOZUK", {}).pop("GRCh38", None)
            if eski:
                dbsnp._INDEX_CACHE["GRCh38"] = eski
    finally:
        T.ANNOT_PATHS.update(asil_annot); T.MANE_PATH = asil_mane
        dbsnp.DBSNP_PATHS.update(asil_db)
        getattr(dbsnp, "_BOZUK", {}).pop("GRCh38", None)
        shutil.rmtree(tmp, ignore_errors=True)


def test_psodogen_ekzon_uyarisi(c):
    baslik("Psodogen uyarisi - kismi / adsiz kopyalar")
    # NOBETCI (2026-10-29): bu 6 gende uyari yoktu ama tasarimin ilk 3 ciftinin 3'u de
    # kopyadan 0-2 uyumsuzlukla urun veriyordu (PTENP1, IKBKGP1, VWFP1, HYDIN2...).
    import paralog
    for gen in ("PTEN", "IKBKG", "CHEK2", "NF1", "VWF", "HYDIN"):
        n = paralog.notu("GRCh38", gen)
        ok(f"{gen}: uyari cikar", bool(n), (n or "")[:70])
    d = c.post("/design", json={"assembly": "GRCh38", "chrom": "10", "position": 87933132}).get_json() or {}
    ok("PTEN ekzon 5 (gen adi verilmeden, koordinattan): tasarim notunda uyari",
       any("PTEN" in n and ("kopya" in n or "copy" in n) for n in d.get("notes") or []))
    # NOBETCI (2026-10-29): DNA modunda uyari "Tasarim bunu kendiliginden kontrol etmez"
    # diyordu; v0.8.9'dan beri arayuz DNA ciftlerini otomatik tarayip rozet ekliyor.
    n = next((n for n in d.get("notes") or [] if "PTEN" in n), "")
    ok("  ...DNA modunda otomatik rozetlere yonlendirir",
       "rozet" in n and "kendiliğinden" not in n, n[-80:])
    n = paralog.not_metni("PTEN", paralog.gen_paraloglari("PTEN"), "cdna") or ""
    ok("  ...RNA modunda dugmeye yonlendirir (rozet yok)",
       "rozet" not in n and "düğmesine basın" in n, n[-80:])


def test_yanlis_sebep(c):
    baslik("Dogru sebep - kisa dizi, bilinmeyen derleme")
    # NOBETCI (2026-10-29 hata taramasi): iki dizi modunda primerden kisa bir dizi
    # "amplikon araligi bu iki diziye uymuyor" diye aciklaniyordu.
    uzun = "GCTGAGGAAGTTGGTGACCATCAGGCTGCTGTTCTCCATCAAGGGTGAAGAGGAATCCCA" * 5
    for ad, govde in (("forward", {"forward": "ACGTACGT", "reverse": uzun}),
                      ("reverse", {"forward": uzun, "reverse": "ACGTACGTAC"})):
        r = c.post("/design_sequence_pair", json=govde)
        hata = (r.get_json() or {}).get("error", "")
        ok(f"iki dizi: kisa {ad} -> 400 'cok kisa'", r.status_code == 400 and "çok kısa" in hata,
           f"-> {r.status_code} {hata[:60]}")
    # NOBETCI: 'abc' derlemesi "abc tanitilmamis" / "transkript tablosu bulunamadi" gibi
    # dosya eksikmis izlenimi veren yanlis sebeple reddediliyordu.
    for ad, r in (("/specificity", c.post("/specificity", json={
                      "assembly": "abc", "forward": "AGAAGCCGTGAGAAGTGA",
                      "reverse": "ATGATCTAGGTTGTGGTCCT"})),
                  ("/evaluate_cdna", c.post("/evaluate_cdna", json={
                      "assembly": "abc", "forward": "GCTGAGGAAGTTGGTGACCA", "acc": "NM_000546"})),
                  ("/transcripts", c.get("/transcripts?gene=TP53&assembly=abc"))):
        hata = (r.get_json() or {}).get("error", "")
        ok(f"{ad} 'abc' -> 400 'GRCh37 veya GRCh38'", r.status_code == 400 and "GRCh38" in hata
           and "abc" in hata and "tanıtılmamış" not in hata and "bulunamadı" not in hata,
           f"-> {r.status_code} {hata[:60]}")
    # /evaluate bilerek genomsuz calismaya devam eder, ama sebebi dogru soyler
    d = c.post("/evaluate", json={"forward": "AGAAGCCGTGAGAAGTGA", "assembly": "abc"}).get_json() or {}
    metin = " ".join(f["text"] for f in d.get("findings") or [])
    ok("/evaluate 'abc': 'tanınmıyor' der, 'tanıtılmadığı için' demez",
       "tanınmıyor" in metin and "tanıtılmadığı" not in metin, metin[:80])


def test_csv_bicimi(c):
    baslik("CSV - Turkce Excel'de sayilar tarihe / metne donmez")
    # NOBETCI (2026-10-31 hata taramasi): ';' ayiricili CSV'de sayilar "30.3" yaziliyordu;
    # Turkce Excel (ondalik ',', tarih g.AA.yyyy) TP53 CSV'sinde 16 hucreyi tarihe
    # ("30.Mar", "3.Ağu") cevirdi, ondaliklilari metin birakti.
    import subprocess
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    with open(os.path.join(kok, "app.js"), encoding="utf-8") as f:
        app_js = f.read()
    ok("app.js CSV satirlarini ';' ile elle birlestirmez (csv.js kullanir)",
       '.join(";")' not in app_js and "CSV.satir(" in app_js)
    with open(os.path.join(kok, "index.html"), encoding="utf-8") as f:
        html = f.read()
    ok("  ...csv.js app.js'ten once yuklenir",
       0 <= html.find('<script src="csv.js">') < html.find('<script src="app.js">'))
    node = shutil.which("node")
    if not node:
        return atla("csv.js bicim testi", "node yok")
    betik = ("const m = require(" + json.dumps(os.path.abspath(os.path.join(kok, "csv.js"))) + ");"
             "const s = [1, 'Forward', 30.3, 3.8, 0.523, 250, '57.5', \"rs1(MAF 0.35, 3' -4)\", 'a\"b'];"
             "console.log(JSON.stringify([m.csvBicimi(',').satir(s), m.csvBicimi('.').satir(s)]));")
    r = subprocess.run([node, "-e", betik], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return ok("csv.js node ile yuklenir", False, r.stderr.strip()[:120])
    tr_s, en_s = json.loads(r.stdout)
    ok("Turkce Excel bicimi: ';' ayirici + ondalik virgul",
       tr_s == "1;Forward;30,3;3,8;0,523;250;57,5;rs1(MAF 0.35, 3' -4);\"a\"\"b\"", tr_s)
    ok("Ingilizce Excel bicimi: ',' ayirici + ondalik nokta, virgullu alan tirnakli",
       en_s == "1,Forward,30.3,3.8,0.523,250,57.5,\"rs1(MAF 0.35, 3' -4)\",\"a\"\"b\"", en_s)


def test_eski_fai(c, engine):
    baslik("Eski / baska .fai - diziler sessizce yanlis okunmaz")
    if HTTP:
        return atla("Eski .fai", "HTTP modu: motorun ici degistirilemez")
    # NOBETCI (2026-10-31 hata taramasi): FASTA yeniden yazilip eski .fai kalinca (satir
    # uzunlugu farkli) /design 200 + 10 cift donuyordu ve primerler gercek dizide YOKTU;
    # pyfaidx yalnizca RuntimeWarning basiyordu. Ozgulluk taramasi da ayni .fai'yi okur.
    import random
    import warnings
    import pyfaidx
    import specificity as S
    tmp = tempfile.mkdtemp(prefix="allprime_fai_")
    asil = dict(engine.GENOME_PATHS)
    rnd = random.Random(5)
    diziler = [("2", "".join(rnd.choice("ACGT") for _ in range(100_000))),
               ("17", "".join(rnd.choice("ACGT") for _ in range(400_000)))]
    s17 = diziler[1][1]
    fa = os.path.join(tmp, "yapay.fa")

    def yaz(genislik):
        with open(fa, "w", newline="\n") as f:
            for ad, d in diziler:
                f.write(f">{ad}\n")
                for i in range(0, len(d), genislik):
                    f.write(d[i:i + genislik] + "\n")

    def tasarla():
        r = c.post("/design", json={"assembly": "GRCh38", "chrom": "17", "position": 200000})
        j = r.get_json() or {}
        p = (j.get("pairs") or [None])[0]
        dogru = p is not None and s17[p["amplicon_genomic_start"] - 1:].startswith(
            p["forward"]["sequence"])
        return r.status_code, dogru, j.get("error") or ""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            yaz(60)
            pyfaidx.Faidx(fa).close()
            engine.GENOME_PATHS["GRCh38"] = fa
            kod, dogru, _h = tasarla()
            ok("saglam yapay genom: primer gercek dizide", kod == 200 and dogru, f"-> {kod}")
            yaz(80)                      # ayni dizi, farkli satir uzunlugu; eski .fai yerinde
            kod, dogru, hata = tasarla()
            ok("eski .fai (uygulama acikken dosya degisti): tasarim 400 + sebep",
               kod == 400 and ".fai" in hata, f"-> {kod} dogru={dogru} {hata[:60]}")
            engine._FASTA_CACHE.pop(fa, None)   # uygulama yeniden acildi: FASTA eski .fai ile acilir
            getattr(engine, "_FASTA_IMZA", {}).pop(fa, None)
            kod, dogru, hata = tasarla()
            ok("  ...yeniden acilista da 400 (yanlis diziyle cift donmez)",
               kod == 400 and ".fai" in hata, f"-> {kod} dogru={dogru} {hata[:60]}")
            r = c.post("/specificity", json={"assembly": "GRCh38", "forward": s17[1000:1020],
                                             "reverse": "ACGTACGTACGTACGTACGA"})
            hata = (r.get_json() or {}).get("error", "")
            ok("  ...ozgulluk taramasi da 400 + sebep", r.status_code == 400 and ".fai" in hata,
               f"-> {r.status_code} {hata[:60]}")
            ok("  ...fai_denetle 'uyusmuyor' der",
               getattr(S, "fai_denetle", lambda _p: None)(fa) == "uyusmuyor")
            os.remove(fa + ".fai")       # oneri: .fai'yi sil -> ilk kullanimda yeniden kurulur
            kod, dogru, hata = tasarla()
            ok("  ....fai silinince yeniden kurulur, primer dogru", kod == 200 and dogru,
               f"-> {kod} {hata[:60]}")
    finally:
        engine.GENOME_PATHS.clear()
        engine.GENOME_PATHS.update(asil)
        engine._FASTA_CACHE.pop(fa, None)
        getattr(engine, "_FASTA_IMZA", {}).pop(fa, None)
        shutil.rmtree(tmp, ignore_errors=True)


def test_tablo_bozuk_dna(c):
    baslik("Bozuk refGene / MANE - DNA tasariminda guvenlik uyarisi sessizce kaybolmaz")
    if HTTP:
        return atla("Bozuk tablo", "HTTP modu: motorun ici degistirilemez")
    import transcripts as T
    import paralog
    # NOBETCI (2026-10-31 hata taramasi): yarim refGene'de PTEN tasarimi (gen adi
    # verilmeden) PTENP1 uyarisi ve ekzon etiketleri OLMADAN, hicbir not dusulmeden
    # donuyordu; /health tabloyu "var" gosteriyordu. MANE yarimken etiketler sessizce yoktu.
    if not T.ANNOT_PATHS.get("GRCh38") or not T.MANE_PATH:
        return atla("Bozuk tablo", "transkript tablosu ya da MANE yok")
    tmp = tempfile.mkdtemp(prefix="allprime_tablo_")
    asil_a, asil_m = dict(T.ANNOT_PATHS), T.MANE_PATH
    PTEN = {"assembly": "GRCh38", "chrom": "10", "position": 87933132}

    def temizle():
        T._INDEX_CACHE.pop("GRCh38", None)
        T._BOLGE_CACHE.pop("GRCh38", None)
        T._MANE_CACHE = None
        paralog._ARALIK_ONBELLEK.pop("GRCh38", None)

    def uyarili(notlar, *aranan):
        return any(n.startswith(("UYARI", "WARNING")) and all(a in n for a in aranan)
                   for n in notlar)
    try:
        y = os.path.join(tmp, "refGene_hg38.txt.gz")
        with open(T.ANNOT_PATHS["GRCh38"], "rb") as f:
            v = f.read()
        with open(y, "wb") as f:
            f.write(v[:len(v) // 3])
        T.ANNOT_PATHS["GRCh38"] = y
        temizle()
        d = c.post("/design", json=PTEN).get_json() or {}
        ok("yarim refGene: DNA tasariminda UYARI (psodogen uyarisi yok denir)",
           uyarili(d.get("notes") or [], "refGene", "psödogen"), f"-> {(d.get('notes') or [''])[0][:70]}")
        h = c.get("/health").get_json() or {}
        ok("  .../health refGene GRCh38 'var' demez", (h.get("annotations") or {}).get("GRCh38") is False)
        e = c.post("/evaluate", json={"assembly": "GRCh38", "forward": "CCATGGGACTGACTTTCTGC",
                                      "reverse": "GAGGAATCCCAAAGTTCCAA"}).get_json() or {}
        ok("  ...Degerlendir'de de uyari (gen / F-R yonu denetlenemedi)",
           any("F/R" in f["text"] and "refGene" in f["text"] for f in e.get("findings") or []))
        T.ANNOT_PATHS.update(asil_a)
        y = os.path.join(tmp, "MANE.summary.txt.gz")
        with open(T.MANE_PATH, "rb") as f:
            v = f.read()
        with open(y, "wb") as f:
            f.write(v[:len(v) // 2])
        T.MANE_PATH = y
        temizle()
        d = c.post("/design", json=PTEN).get_json() or {}
        ok("yarim MANE: DNA tasariminda UYARI (etiket yok denir)",
           uyarili(d.get("notes") or [], "MANE", "etiket"))
        h = c.get("/health").get_json() or {}
        ok("  .../health MANE 'var' demez", (h.get("annotations") or {}).get("mane") is False)
    finally:
        T.ANNOT_PATHS.update(asil_a)
        T.MANE_PATH = asil_m
        temizle()
        shutil.rmtree(tmp, ignore_errors=True)
    d = c.post("/design", json=PTEN).get_json() or {}
    ok("  ...saglam tablolarda bu uyari CIKMAZ",
       not any("okunamadı" in n or "bulunamadı" in n for n in d.get("notes") or []))


def test_hedefsiz_uzun_dizi(c):
    baslik("Dizi modu - hedefsiz uzun dizi takilmaz")
    # NOBETCI (2026-10-31 hata taramasi): hedef verilmeden 1 Mb'lik dizi 10 dakikayi
    # astigi icin durduruldu (100 kb 5,7 sn); sure dizi boyunun karesiyle buyur.
    import random
    rnd = random.Random(11)
    d60 = "".join(rnd.choice("ACGT") for _ in range(60_000))
    t0 = time.time()
    r = c.post("/design_sequence", json={"sequence": d60})
    sure = time.time() - t0
    hata = (r.get_json() or {}).get("error", "")
    ok("60 kb hedefsiz dizi -> hizli 400 + hedef onerisi",
       r.status_code == 400 and "hedef" in hata.lower() and sure < 5,
       f"-> {r.status_code} {sure:.1f} sn {hata[:60]}")
    r = c.post("/design_sequence", json={"sequence": d60, "target": "30000-30020"})
    ok("  ...ayni dizi hedefle tasarlanir", r.status_code == 200 and
       (r.get_json() or {}).get("pairs"), f"-> {r.status_code}")
    r = c.post("/design_sequence", json={"sequence": d60[:20_000]})
    ok("  ...sinirin altindaki hedefsiz dizi calisir", r.status_code == 200 and
       (r.get_json() or {}).get("pairs"), f"-> {r.status_code}")


def test_arayuz_bicimi(c):
    baslik("Arayuz ve CSV bicimi - dil, gen adi, CSV sutunlari (kod denetimi)")
    # NOBETCI (2026-10-31 hata taramasi, Dusuk bulgular). Bunlar arayuz kodunun gerileme
    # denetimidir; davranis gercek arayuzde CDP ile ayrica denendi.
    import re
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    with open(os.path.join(kok, "app.js"), encoding="utf-8") as f:
        app_js = f.read()
    with open(os.path.join(kok, "i18n.js"), encoding="utf-8") as f:
        i18n = f.read()
    kod = "\n".join(x for x in app_js.splitlines() if not x.lstrip().startswith("//"))
    # D-3: Ingilizce arayuzde "Position: 7.676.059" (Windows ayari) ve "GC: %62.1"
    ok("sayilar arayuz diline gore bicimlenir (bos toLocaleString() yok)",
       ".toLocaleString()" not in kod and "toLocaleString(yerel())" in kod)
    ok("  ...yuzde isareti cevirden (TR '%62.1', EN '62.1%')",
       "%${" not in kod and '"fmt.pct": (v) => `%${v}`' in i18n and '"fmt.pct": (v) => `${v}%`' in i18n)
    # D-2: bas basa genlerde F "ekzon 1" (TIGD7) / R "intron 1" (ZNF75A) ayni gen saniliyordu
    ok("tabloda gen adi her zaman yazilir (farkli genlerdeki primerler dahil)",
       'const etiket = (r.gene ? r.gene + "\\u00a0· " : "") + bolgeEtiket(r);' in kod
       and kod.count("bolgeCell(x)") == 2)
    # D-4: CSV'de eksi iplikte Genomik_Baslangic > Genomik_Bitis; bant "612 bp" metin
    ok("CSV: cDNA modunda genomik uclar kucukten buyuge",
       "Math.min(x.genomic_start, x.genomic_end), Math.max(x.genomic_start, x.genomic_end)" in kod)
    bp_csv = kod[kod.find("function exportBpCsv"):]
    bp_csv = bp_csv[:bp_csv.find(chr(10) + "function ", 10)]
    ok("  ...kirilma noktasi CSV'sinde bant boylari birimsiz sayi",
       "bpCsv(" in bp_csv and " bp`" not in bp_csv and "bpBoy(" not in bp_csv)
    ok("  ...basliklar tutarli (Gen_bolgesi, AnaBant_bp)",
       all(x in i18n for x in ('"Gen_bolgesi"', '"Gene_region"', '"AnaBant_bp"', '"MainBand_bp"'))
       and not re.search(r'"csv\.geneRegion": "Gen(e)? (bolgesi|region)"', i18n))
    # D-5: bildirim dosyasi veri kaynaklarini anmiyordu
    with open(os.path.join(BURASI, "..", "THIRD-PARTY-NOTICES.txt"), encoding="utf-8") as f:
        bildirim = f.read()
    ok("THIRD-PARTY-NOTICES veri kaynaklarini ve kosullarini anar",
       "Veri dosyalari / Data files" in bildirim and all(
           x in bildirim for x in ("ftp.ensembl.org", "genome.ucsc.edu/conditions.html",
                                   "ftp.ncbi.nlm.nih.gov/refseq/MANE")))
    # NOBETCI (2026-11-11, K7/F-07): pakette olan ama bildirimde anilmayan bilesenler ve
    # motorun kullanmadigi primer3 exe'leri
    ok("THIRD-PARTY-NOTICES paketteki ek bilesenleri anar (expat, libmpdec, liblzma, khash, msvcp140)",
       all(x in bildirim for x in ("expat 2.", "Thai Open Source Software Center",
                                   "libmpdec  (BSD-2-Clause)", "Stefan Krah",
                                   "liblzma (xz)", "klib/khash.h  (MIT)", "Attractive Chaos",
                                   "msvcp140-*.dll")))
    with open(os.path.join(BURASI, "allprime-server.spec"), encoding="utf-8") as f:
        spec = f.read()
    ok("allprime-server.spec primer3'un 5 komut satiri exe'sini pakete almaz",
       all(x in spec for x in ("primer3_core.exe", "ntthal.exe", "ntdpal.exe", "oligotm.exe",
                               "amplicon3_core.exe", "datas = [d for d in datas if _exe_degil(d)]",
                               "binaries = [b for b in binaries if _exe_degil(b)]")))
    ok("bildirim 'amplicon3_core' exe'sinin pakete konmadigini soyler",
       "amplicon3_core) pakete konmaz" in bildirim)


def test_c_konum_uclari(c):
    baslik("c. konumu - gecersiz c.-0 / c.*0, HGVS 'c.76='")
    # NOBETCI (2026-10-31 hata taramasi): c.-0 sessizce c.1'e, c.*0 son kodlayan baza
    # cevriliyordu; 'c.76=' (degisiklik yok) reddediliyor ve ipucu ilgisizdi.
    tp53 = {"assembly": "GRCh38", "acc": "NM_000546"}
    for cp in ("c.-0", "c.*0"):
        r = c.post("/design_cdna", json=dict(tp53, c_position=cp))
        hata = (r.get_json() or {}).get("error", "")
        ok(f"{cp} -> 400 'gecerli bir konum degil'", r.status_code == 400 and "geçerli bir konum değil" in hata,
           f"-> {r.status_code} {hata[:50]}")
    a = c.post("/design_cdna", json=dict(tp53, c_position="c.76")).get_json() or {}
    b = c.post("/design_cdna", json=dict(tp53, c_position="c.76="))
    ok("c.76= kabul edilir (c.76 ile ayni konum)", b.status_code == 200 and
       (b.get_json() or {}).get("variant_cdna_index") == a.get("variant_cdna_index"), f"-> {b.status_code}")
    h1 = (c.post("/design_cdna", json=dict(tp53, c_position="c.76$")).get_json() or {}).get("error", "")
    h2 = (c.post("/design_cdna", json=dict(tp53, c_position="c.1.234")).get_json() or {}).get("error", "")
    ok("  ...binlik ayirici ipucu yalnizca binlik yazimina", "Binlik" not in h1 and "Binlik" in h2,
       f"-> {h1[-40:]} | {h2[-40:]}")


def test_c_referans_baz(c):
    baslik("c.NNNX>Y referans bazi transkriptle karsilastirilir (A2-01)")
    # NOBETCI (2026-11-10, K5): TP53 c.524A>G ve c.524T>C (gercek baz G) uyarisiz kabul
    # ediliyordu; yanlis transkript surumu/numaralamayla gelen kullanici fark etmiyordu.
    # Reddedilmez, yalnizca uyarilir; del/dup/ins ve aralik bicimi eskisi gibi.
    tp53 = {"assembly": "GRCh38", "acc": "NM_000546"}
    uyari = lambda j: [n for n in (j.get("notes") or []) if "referans baz" in n or "reference base" in n]
    for dil in ("tr", "en"):
        g = lambda cp, acc="NM_000546", asm="GRCh38": c.post("/design_cdna", json={
            "assembly": asm, "acc": acc, "c_position": cp, "lang": dil}).get_json() or {}
        ok(f"[{dil}] dogru baz (c.524G>A) uyarisiz", not uyari(g("c.524G>A")))
        for yanlis in ("c.524A>G", "c.524T>C"):
            j = g(yanlis)
            u = uyari(j)
            ok(f"[{dil}] {yanlis}: uyari, gercek baz (G) ve transkript adi", len(u) == 1 and "(G)" in u[0]
               and "NM_000546" in u[0] and bool(j.get("pairs")), f"-> {u[:1]}")
        ok(f"[{dil}] GRCh37'de de denetlenir", len(uyari(g("c.524A>G", asm="GRCh37"))) == 1)
        ok(f"[{dil}] arti iplik: BRCA2 c.1A>G uyarisiz, c.1G>A uyarili",
           not uyari(g("c.1A>G", "NM_000059")) and len(uyari(g("c.1G>A", "NM_000059"))) == 1)
        ok(f"[{dil}] del/dup/aralik bicimlerinde uyari yok",
           all(not uyari(g(x)) for x in ("c.524del", "c.524dup", "c.524_526del", "c.524")))


def test_k8_kucuk_duzeltmeler(c):
    baslik("K8: Dizi hedef sebebi (F-10), bildirim metni, telif basliklari, belge sayilari (F-09, H-04)")
    # NOBETCI (2026-11-11, F-10): "600-500" (ters aralik) ve "600.5" (ondalik) "dizi sinirlari disinda"
    # diye reddediliyordu (yanlis sebep). Dogru sebep: aralik ters / sayi tam olmali.
    import random
    rng = random.Random(5)
    dizi = "".join(rng.choice("ACGT") for _ in range(1201))
    for dil, ters_k, ond_k, disi_k in (("tr", "küçük olamaz", "tam sayı olmalı", "sınırları dışında"),
                                       ("en", "cannot be smaller", "whole number", "outside the sequence")):
        for hedef, anahtar in (("600-500", ters_k), ("600.5", ond_k), ("5000", disi_k), ("0", disi_k)):
            r = c.post("/design_sequence", json={"sequence": dizi, "target": hedef, "lang": dil})
            m = (r.get_json() or {}).get("error", "")
            ok(f"[{dil}] hedef {hedef!r}: 400 ve dogru sebep", r.status_code == 400 and anahtar in m, f"-> {r.status_code} {m[:90]}")
            if hedef in ("600-500", "600.5"):
                ok("  ...'dizi sinirlari disinda' sebebi yok", disi_k not in m)
    for hedef in ("600", "590-610", "590..610", "590_610"):
        r = c.post("/design_sequence", json={"sequence": dizi, "target": hedef})
        ok(f"gecerli hedef {hedef!r} reddedilmez", r.status_code == 200, f"-> {r.status_code}")

    # Bildirim (kullanici karari 2026-11-11): transkript tablosu da yoksa gen sembolu de Ensembl'e gider
    # (ayri bir betikle olculdu). Metin olguya uymali; surum artmali.
    kok = os.path.join(BURASI, "..", "electron")
    oku = lambda ad: " ".join(open(os.path.join(kok, ad), encoding="utf-8").read().split())
    tr_b, en_b = oku("renderer/terms.html"), oku("renderer/terms_en.html")
    ok("bildirim 5. madde (TR): gen sembolu de sorgulanir, 'yalnizca koordinat' iddiasi yok",
       "<b>gen sembolü</b>" in tr_b and "yalnızca <b>koordinat</b>" not in tr_b)
    ok("bildirim 5. madde (EN): gene symbol queried too, no 'only a coordinate' claim",
       "<b>gene symbol</b>" in en_b and "only a <b>coordinate</b>" not in en_b)
    kurulum = open(os.path.join(KOK, "KURULUM.txt"), encoding="utf-8").read()
    ok("KURULUM: Ensembl yedeginde gen sembolu de soylenir; 'sadece koordinat' yok",
       "gen sembolü de sorgulanır" in kurulum and "sadece koordinat sorgulanır" not in kurulum)
    ok("KURULUM: MANE sürümü uydurulmaz (v1.5 yok; yerel dosya sürüm taşımaz)", "MANE v1.5" not in kurulum)

    # F-09 belge sayilari: README i18n anahtar sayisini gercek sayiyla soyler
    i18n = open(os.path.join(kok, "renderer", "i18n.js"), encoding="utf-8").read()
    tr_blok, en_blok = i18n.split(chr(10) + "  en: {", 1)
    sayi_tr = len(re.findall(r'^    "[\w.\-]+":', tr_blok, flags=re.M))
    sayi_en = len(re.findall(r'^    "[\w.\-]+":', en_blok, flags=re.M))
    readme = open(os.path.join(KOK, "GELISTIRME.md"), encoding="utf-8").read()
    ok("README: i18n anahtar sayisi gercek sayiyla ayni (TR = EN)",
       sayi_tr == sayi_en and f"{sayi_tr}'er anahtar" in readme.replace("\n", " "), f"-> TR {sayi_tr} EN {sayi_en}")
    ok("README: duman testi suresi ~9 dk, normal alel bandi pcr_max'a gore (3 / 6 kb sabit esigi yok)",
       "(~9 dk" in readme and "≤3 kb" not in readme)
    ok("alt bilgi: lisans metinlerinin yeri dosyalar; 'Hakkinda'da lisans metni' iddiasi yok",
       "(GPL v3) dosyalarındadır; " in i18n and "(GPL v3) files in the " in i18n
       and "Lisans metinleri: " not in i18n and "Licence texts: " not in i18n)

    # H-04: telif basligi olmayan 8 dosya
    for ad in ("backend/allprime-server.spec", "build.ps1", "kurulu-temizle.ps1", "electron/tools/ico-uret.ps1",
               "electron/tools/ikon-uret.js", "electron/renderer/style.css", "electron/renderer/terms.html",
               "electron/renderer/terms_en.html"):
        bas = open(os.path.join(KOK, ad.replace("/", os.sep)), encoding="utf-8").read(900)
        ok(f"telif basligi (tekil 'eser sahibi' + AUTHORS + GPL): {ad}",
           "Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS" in bas and "GPL-2.0-or-later" in bas)


def test_k8_tek_primer(c):
    baslik("K8: Degerlendir DNA kipinde tek primer bilgi notu (F-08)")
    # NOBETCI (2026-11-11, F-08): yalniz Forward verilince bulgu listesi bos, "Sorun gorunmuyor" tek basina
    # kaliyordu; RNA kipinde "yalnizca tek primer" bilgi notu vardi. Simdi DNA kipinde de var (TR/EN).
    for dil, anahtar in (("tr", "Yalnızca tek primer"), ("en", "Only one primer")):
        d = c.post("/evaluate", json={"forward": "AGAAGCCGTGAGAAGTGA", "assembly": "GRCh38", "lang": dil}).get_json()
        notlar = [f for f in d.get("findings", []) if anahtar in f["text"]]
        ok(f"[{dil}] DNA tek primer: bilgi notu var", len(notlar) == 1 and notlar[0]["level"] == "bilgi",
           "-> " + " | ".join(f"[{f['level']}] {f['text'][:60]}" for f in d.get("findings", [])[:4]))
    d = c.post("/evaluate", json={"forward": "AGAAGCCGTGAGAAGTGA", "reverse": "ATGATCTAGGTTGTGGTCCT",
                                  "assembly": "GRCh38"}).get_json()
    ok("iki primerde tek primer notu yok", not any("Yalnızca tek primer" in f["text"] for f in d.get("findings", [])))


def test_dizi_ucu_sebebi(c, engine):
    baslik("Dizi modu: hedef ucuna yakinsa dogru sebep (A3-02)")
    # NOBETCI (2026-11-10, K5): hedef dizinin basindan/sonundan <= ~85 baz uzaktaysa cift
    # cikmiyor, ama sebep ya yoktu ya da yanlis ("Adaylarin cogu GC orani ...") yaziliyordu.
    import random
    rng = random.Random(11)
    dizi = "".join(rng.choice("ACGT") for _ in range(900))
    p = engine._seq_params({})
    gerek = int(p["min_dist_from_variant"]) + int(p["primer_min_size"])      # koddan: 50 + 18
    for dil in ("tr", "en"):
        anahtar = "çok yakın" if dil == "tr" else "too close"
        for ad, hedef in (("basta", "1"), ("basta (sert sinirin altinda)", str(gerek - 1)),
                          ("sonda", "900"), ("sonda 40", "860")):
            j = c.post("/design_sequence", json={"sequence": dizi, "target": hedef, "lang": dil}).get_json()
            n = " ".join(j.get("notes") or [])
            ok(f"[{dil}] hedef {ad}: 0 cift, sebep uca yakinlik ve esik {gerek}",
               not j["pairs"] and anahtar in n and str(gerek) in n, f"-> {n[:90]}")
            ok(f"  ...yanlis 'GC' aciklamasi yok", "GC" not in n)
        j = c.post("/design_sequence", json={"sequence": dizi, "target": "450", "lang": dil}).get_json()
        ok(f"[{dil}] ortadaki hedefte cift var, uc notu yok", bool(j["pairs"]) and not any(
            anahtar in x for x in j["notes"]))
    # esik ayardan turetilir: min uzaklik 10 -> 28
    j = c.post("/design_sequence", json={"sequence": dizi, "target": "20",
                                         "params": {"min_dist_from_variant": 10}}).get_json()
    n = " ".join(j.get("notes") or [])
    ok("esik min_dist_from_variant ayarindan hesaplanir (10 + 18 = 28)",
       not j["pairs"] and "28" in n, f"-> {n[:90]}")


def test_indirme_dili(engine):
    baslik("Indirme durum ve hata metinleri arayuz dilinde (A7-01)")
    # NOBETCI (2026-11-10, K5): indirme is parcacigi ContextVar'i miras almadigi icin EN arayuzde
    # de Turkce metin geliyordu. Simdi durum kaydi iki dili de tasir; /downloads istegin diliyle verir.
    import gzip as _gz
    import threading
    import downloads
    import lang

    kapi = threading.Event()
    govde = _gz.compress(b"chr1\t" * 5000)

    class Yanit:
        status_code = 200

        def __init__(self):
            self.headers = {"Content-Length": str(len(govde)), "ETag": '"dil"'}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_content(self, n):
            yield govde[:len(govde) // 2]
            kapi.wait(15)
            yield govde[len(govde) // 2:len(govde) // 2 + 5]      # kesik: bozuk gzip

        def raise_for_status(self):
            pass

        def close(self):
            pass

    d = tempfile.mkdtemp(prefix="allprime_dil_")
    eski_get = downloads.requests.get
    eski_kok = os.environ.get("ALLPRIME_DATA_ROOT")
    eski_dil = lang.get_lang()
    os.environ["ALLPRIME_DATA_ROOT"] = d
    downloads.requests.get = lambda *a, **k: Yanit()

    def durum(dil):
        lang.set_lang(dil)
        return downloads.status()["ogeler"]["refgene_GRCh38"]

    def bekle(sart, sn=20):
        t0 = time.time()
        while time.time() - t0 < sn:
            if sart(durum("tr")):
                return True
            time.sleep(0.05)
        return False

    try:
        for baslat in ("en", "tr"):
            kapi.clear()
            downloads._STATE.pop("refgene_GRCh38", None)
            lang.set_lang(baslat)
            downloads.start("refgene_GRCh38")
            ok(f"[baslat={baslat}] indirme basladi", bekle(lambda o: o["durum"] == "indiriliyor"))
            ok("  ...sirasinda EN istekte 'Downloading', TR istekte 'İndiriliyor' (dil degisebilir)",
               "Downloading" in durum("en")["mesaj"] and "İndiriliyor" in durum("tr")["mesaj"])
            kapi.set()
            ok("  ...bitti (hata)", bekle(lambda o: o["durum"] == "hata" and not downloads.status()["aktif"]))
            en, tr = durum("en")["hata"], durum("tr")["hata"]
            ok("  ...hata EN istekte Ingilizce, TR istekte Turkce",
               "corrupt" in en and "bozuk" in tr and not any(ch in "çğıöşüİ" for ch in en), f"-> {en[:50]} | {tr[:50]}")
        lang.set_lang("en")
        try:
            downloads.start("yok_boyle_oge")
            ok("bilinmeyen oge hata atar", False)
        except downloads.DownloadError as e:
            ok("bilinmeyen oge hatasi istek dilinde (EN)", "Unknown item" in str(e), f"-> {e}")
    finally:
        downloads.requests.get = eski_get
        if eski_kok is None:
            os.environ.pop("ALLPRIME_DATA_ROOT", None)
        else:
            os.environ["ALLPRIME_DATA_ROOT"] = eski_kok
        lang.set_lang(eski_dil)
        downloads._STATE.pop("refgene_GRCh38", None)
        shutil.rmtree(d, ignore_errors=True)


def test_telif_gorunur(c):
    baslik("Telif bildirimi uygulama ekraninda gorunur (GPL v2 md. 2c)")
    # NOBETCI (2026-10-31): eser sahibinin adi yalnizca AUTHORS ve bildirim dosyasindaydi;
    # ekranda hic yoktu. Program acilista duyuru gosterirse GPL v2 md. 2(c) geregi
    # degistirilmis surumler de gostermek zorunda.
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    oku = lambda ad: open(os.path.join(kok, ad), encoding="utf-8").read()
    html, i18n, onay = oku("index.html"), oku("i18n.js"), oku("consent.html")
    ok("ana ekranda telif satiri ve tam duyuru alani var",
       'data-i18n="app.copyright"' in html and 'data-i18n="app.notice"' in html)
    def deger(metin, anahtar):
        i = metin.find(f'"{anahtar}":')
        return metin[i:metin.find('",', i)] if i >= 0 else ""
    tr, en = i18n.split(chr(10) + "  en: {", 1)
    for dil, metin, kelimeler in (("TR", tr, ("garanti", "dağıtıl")), ("EN", en, ("warranty", "redistribute"))):
        telif, duyuru = deger(metin, "app.copyright"), deger(metin, "app.notice")
        ok(f"  ...{dil}: ust satirda ad + GPL", "Eren Kılınç" in telif and "GPL" in telif)
        ok(f"  ...{dil}: duyuruda ad, GPL, garanti yok, dagitim kosulu, LICENSE",
           all(k in duyuru for k in ("Eren Kılınç", "GPL", "LICENSE") + kelimeler))
    ok("onay ekraninda telif satiri var", "2026 Eren Kılınç" in onay)


def test_kaynak_zip(c):
    baslik("AllPrime'in kaynak kodu uygulama klasorunde (GPL v2 Bolum 3a)")
    # NOBETCI (2026-10-31, tarama bulgusu L-A): klasorde motorun .py dosyalari da,
    # GPL v2 Bolum 3 yazili teklifi de yoktu; klasor kurum disina verilse primer3'un
    # lisansi karsilanmazdi. kurulu-guncelle.ps1 artik kaynak-zip.ps1 ile koyuyor.
    import re
    import subprocess
    import zipfile
    oku = lambda ad: open(os.path.join(KOK, ad), encoding="utf-8").read()
    betik = os.path.join(KOK, "kaynak-zip.ps1")
    ok("kurulu-guncelle.ps1 kaynak zip'ini uretiyor",
       os.path.exists(betik) and "kaynak-zip.ps1" in oku("kurulu-guncelle.ps1"))
    for ad in ("KURULUM.txt", "THIRD-PARTY-NOTICES.txt"):
        ok(f"  ...{ad} kaynagin yerini soyluyor", "AllPrime-kaynak-" in oku(ad))
    surum = json.loads(oku(os.path.join("electron", "package.json")))["version"]
    on = f"AllPrime-kaynak-{surum}/"
    gecici = tempfile.mkdtemp(prefix="allprime-kaynak-")
    try:
        with open(os.path.join(gecici, "AllPrime-kaynak-0.0.1.zip"), "wb") as f:
            f.write(b"eski surum")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", betik,
                            "-Hedef", gecici], capture_output=True, text=True, errors="replace",
                           timeout=120) if os.path.exists(betik) else None
        zipler = sorted(f for f in os.listdir(gecici) if f.endswith(".zip"))
        ok("betik calisir; klasorde yalnizca bu surumun zip'i kalir",
           r is not None and r.returncode == 0 and zipler == [f"AllPrime-kaynak-{surum}.zip"],
           f"{zipler} {(r.stdout + r.stderr).strip()[-200:] if r else 'betik yok'}")
        if zipler == [f"AllPrime-kaynak-{surum}.zip"]:
            with zipfile.ZipFile(os.path.join(gecici, zipler[0])) as z:
                adlar = set(z.namelist())
                gerekli = ["backend/engine.py", "backend/server.py", "backend/specificity.py",
                           "backend/transcripts.py", "backend/allprime-server.spec",
                           "backend/requirements.txt", "electron/main.js", "electron/package.json",
                           "electron/renderer/app.js", "kurulu-guncelle.ps1", "kurulu-temizle.ps1",
                           "LICENSE", "AUTHORS"]
                eksik = [g for g in gerekli if on + g not in adlar]
                ok("zip motoru, arayuzu, derleme betiklerini ve lisansi icerir", not eksik,
                   f"eksik: {eksik}")
                fazla = [a for a in adlar
                         if re.search(r"(^|/)(\.venv|node_modules|genomes|__pycache__)/", a)]
                ok("zip'e sanal ortam / node_modules / genom girmemis", not fazla, str(fazla[:3]))
                # Commit edilmemis degisiklik de girmeli: zip, derlenen kaynagin AYNISI olmali
                bu = oku(os.path.join("backend", "test_smoke.py")).replace("\r\n", "\n")
                zipteki = z.read(on + "backend/test_smoke.py").decode("utf-8").replace("\r\n", "\n")
                ok("zip calisma agacindaki kaynakla ayni (commit edilmemis degisiklik dahil)",
                   bu == zipteki)
    finally:
        shutil.rmtree(gecici, ignore_errors=True)
    # Paketli motor modunda kurulu klasorun kendisi de denetlenir (kurulu-guncelle.ps1
    # calistiktan sonra kosulur); kaynak modunda kurulu klasor kaynaktan geride olabilir.
    if HTTP:
        surum_motor = c.get("/health").get_json().get("version")
        kdir = os.path.join(os.environ["ALLPRIME_APP_ROOT"], "kaynak")
        kurulu = sorted(f for f in os.listdir(kdir) if f.endswith(".zip")) if os.path.isdir(kdir) else []
        ok("kurulu klasorde motorun surumundeki kaynak zip'i var (tek)",
           kurulu == [f"AllPrime-kaynak-{surum_motor}.zip"], str(kurulu))


def test_lisans_surumu(c):
    baslik("Lisans: GPL-2.0-or-later; kurum disina GPL v3 ile (Apache-2.0 bilesenler)")
    # NOBETCI (2026-10-31): package.json "GPL-2.0-only" diyordu, bildirimler "GNU GPL v2".
    # Motordaki requests ve OpenSSL Apache-2.0; FSF'ye gore Apache-2.0 GPL v2 ile uyumsuz,
    # GPL v3 ile uyumlu. Cozum: AllPrime "v2 veya sonrasi" + GPL v3 metni klasorde.
    import glob
    oku = lambda yol: open(yol, encoding="utf-8", errors="replace").read()
    ok("package.json lisansi GPL-2.0-or-later",
       json.loads(oku(os.path.join(KOK, "electron", "package.json"))).get("license")
       == "GPL-2.0-or-later")
    gpl3 = os.path.join(KOK, "LICENSE-GPL-3.0.txt")
    metin3 = oku(gpl3) if os.path.exists(gpl3) else ""
    ok("GPL v3 tam metni depoda (LICENSE-GPL-3.0.txt)",
       "Version 3, 29 June 2007" in metin3 and "END OF TERMS AND CONDITIONS" in metin3)
    betik = oku(os.path.join(KOK, "kurulu-guncelle.ps1"))
    ok("kurulu-guncelle.ps1 GPL v3 metnini kopyaliyor, exe kimligi GPL-2.0-or-later",
       '"LICENSE-GPL-3.0.txt"' in betik and "GPL-2.0-or-later" in betik)
    for ad in ("THIRD-PARTY-NOTICES.txt", "KURULUM.txt", "AUTHORS",
               os.path.join("electron", "renderer", "terms.html"),
               os.path.join("electron", "renderer", "terms_en.html")):
        ok(f"  ...{ad}: GPL v3 metnine isaret ediyor",
           "LICENSE-GPL-3.0.txt" in oku(os.path.join(KOK, ad)))
    # "yalnizca GPL v2" diye okunabilecek eski ifadeler kalmasin (bu dosya haric:
    # aranan ifadeler burada yaziyor)
    yasak = ("bu yazilim da GNU GPL v2", "GPL-2.0-only", "primer3 GPL v2 dahil",
             "including primer3 GPL v2", "butunu GNU GPL v2", "subject to the GNU GPL v2",
             "GPL v2 ile lisanslıdır", "primer3 is licensed under GPL v2",
             "GNU GPL v2 (primer3 ile", "GNU GPL v2 koşullarına", "GNU GPL v2 koşullarında",
             "under the GNU GPL v2 are", 'GNU GPL v2"', "GNU GPL v2</p>")
    dosyalar = ([y for y in glob.glob(os.path.join(KOK, "backend", "*.py"))
                 if not y.endswith("test_smoke.py")]
                + glob.glob(os.path.join(KOK, "electron", "*.js"))
                + [os.path.join(KOK, "electron", "package.json")]
                + glob.glob(os.path.join(KOK, "electron", "renderer", "*.js"))
                + glob.glob(os.path.join(KOK, "electron", "renderer", "*.html"))
                + [os.path.join(KOK, a) for a in ("AUTHORS", "KURULUM.txt", "README.md", "GELISTIRME.md",
                                                  "THIRD-PARTY-NOTICES.txt")])
    kalan = [f"{os.path.relpath(y, KOK)}: {s}" for y in dosyalar for s in yasak if s in oku(y)]
    ok("'yalnizca GPL v2' diye okunabilecek ifade kalmadi", not kalan, "; ".join(kalan[:4]))
    # Paketli motor modunda kurulu klasor de (kurulu-guncelle.ps1 calistiktan sonra kosulur)
    if HTTP:
        kurulu = os.path.join(os.environ["ALLPRIME_APP_ROOT"], "LICENSE-GPL-3.0.txt")
        ok("kurulu klasorde GPL v3 metni var ve depodakiyle ayni",
           os.path.exists(kurulu) and oku(kurulu) == metin3)


def test_lisans_paragrafi(c):
    baslik("Onay metninde lisans paragrafi kisa: yalnizca lisans ve metinlerinin yeri")
    # NOBETCI (2026-11-01, kullanici: "su ile lisanslidir desek yeter"). 4. maddedeki uyari
    # kutusu GPL v2/v3, Apache-2.0 ve kurum disina dagitim yukumluluklerini anlatiyordu; bu
    # ayrinti README, KURULUM.txt ve THIRD-PARTY-NOTICES.txt'de. Yukumlulukler metinden
    # bagimsiz olarak gecerli; lisans metinleri ve kaynak zip'i klasorde (test_lisans_surumu,
    # test_kaynak_zip). Metin degistigi icin onay surumu artar, herkes bir kez yeniden onaylar.
    kok = os.path.join(BURASI, "..", "electron")
    oku = lambda ad: " ".join(open(os.path.join(kok, ad), encoding="utf-8").read().split())
    for ad, cumle, eski in (
            ("terms.html", "AllPrime, GNU GPL sürüm 2 ya da (isteğinize göre) daha sonraki bir sürümü "
                           "ile lisanslıdır. Lisans metinleri uygulama klasöründedir",
             ("dağıtım gerçekleşmiş", "Apache-2.0 lisanslı bileşenler", "yükümlülükleri doğar")),
            ("terms_en.html", "AllPrime is licensed under the GNU GPL version 2 or (at your option) any "
                              "later version. The licence texts are in the application folder",
             ("distribution has occurred", "Apache-2.0 components", "obligations apply"))):
        metin = oku(os.path.join("renderer", ad))
        dort = metin[metin.find("<h3>4."):metin.find("<h3>5.")]
        ok(f"{ad}: 4. maddede lisans tek cumle + lisans metinlerinin yeri",
           cumle in dort and "LICENSE-GPL-3.0.txt" in dort and 'class="uyari"' not in dort
           and not any(e in dort for e in eski))
    onay_js, onay_html, main_js = oku("renderer/consent.js"), oku("renderer/consent.html"), oku("main.js")
    ok("3. uyari maddesi artik anlatilmayan dagitim kosullarindan soz etmiyor (TR / EN)",
       "kurum dışına" not in onay_js and "kurum dışına" not in onay_html
       and "outside my institution" not in onay_js
       and "GNU GPL (v2 veya sonrası) ile lisanslıdır" in onay_js
       and "GNU GPL (v2 or later)" in onay_js)
    ok("bildirim metni degisti -> bildirim surumu artti (2.1)", 'const NOTICE_VERSION = "2.1";' in main_js)


def _yorumsuz_js(m):
    return "\n".join(x for x in m.splitlines() if not x.lstrip().startswith("//"))


def test_bilgilendirme_ekrani(c):
    baslik("Acilis ekrani bilgilendirme ekrani: onay kutusu, kaydirma sarti ve Reddet yok (v0.8.43)")
    # NOBETCI (2026-11-10, kullanici karari H-03): zorunlu kutular, "metni sonuna kadar kaydir"
    # sarti ve "Reddet ve cik" kalkti; ustte "Onemli uyarilar" kutusu ve tek "Anladim, devam et"
    # dugmesi var. Metin TR + EN. Kabul / onay dili bilgilendirme diline cevrildi.
    kok = os.path.join(BURASI, "..", "electron")
    oku = lambda ad: open(os.path.join(kok, ad), encoding="utf-8").read()
    html, js = oku("renderer/consent.html"), oku("renderer/consent.js")
    main_js, preload, css = oku("main.js"), oku("preload.js"), oku("renderer/style.css")
    tr_terms, en_terms = oku("renderer/terms.html"), oku("renderer/terms_en.html")
    html_k = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    js_k, main_k = _yorumsuz_js(js), _yorumsuz_js(main_js)
    ok("consent.html: onay kutusu, Reddet dugmesi ve kaydirma ipucu yok",
       'type="checkbox"' not in html_k and "declineBtn" not in html_k and "c-req" not in html_k
       and "consent-checks" not in html_k and "scrollHint" not in js_k and "checkScrolled" not in js_k
       and "declineConsent" not in js_k and "disabled" not in html_k)
    ok("  ...tek dugme (acilis eylemleri alaninda) ve ust bardaki iki dil dugmesi",
       html_k.count("<button") == 3 and html_k.count('id="acceptBtn"') == 1)
    ok("  ...dugme etiketleri TR / EN: Anladim, devam et / Got it, continue",
       "Anladım, devam et" in js_k and "Got it, continue" in js_k
       and "Anladım, devam et" in html_k)
    ok("  ...'Onemli uyarilar' kutusu 3 madde, TR + EN",
       all(f'id="c_n{i}"' in html_k and f"n{i}:" in js_k for i in (1, 2, 3))
       and "Önemli uyarılar" in js_k and "Important notices" in js_k)
    # kabul / onay / ret dili kalmadi (izin verilen: "onay istemez", "does not ask for acceptance",
    # "kullanim sarti degildir", "not a condition of use")
    def dil(m):
        for s in ("acceptBtn", "accept:", "t.accept", "onay istemez", "does not ask for acceptance", "kullanım şartı değildir",
                  "not a condition of use"):
            m = m.replace(s, "")
        return re.findall(r"(?i)kabul|onay|reddet|accept|decline|agree|consent", re.sub(r"<[^>]+>", " ", m))
    kalan = dil(html_k) + dil(js_k) + dil(re.sub(r"<!--.*?-->", "", tr_terms, flags=re.S)) \
        + dil(re.sub(r"<!--.*?-->", "", en_terms, flags=re.S))
    ok("ekran ve bildirim metinlerinde kabul / onay / ret dili yok", not kalan, ", ".join(kalan[:6]))
    ok("terms: §2 uyari dili ve §7 'bildirimin kaydi' (TR + EN), kullanici / bilgisayar adi anilmiyor",
       "doğrulanması gerekir" in " ".join(tr_terms.split()) and "kullanım şartı değildir" in " ".join(tr_terms.split())
       and "7. Bu bildirimin kaydı" in tr_terms and "7. Record of this notice" in en_terms
       and "should be <b>experimentally validated</b>" in " ".join(en_terms.split())
       and "not a condition of use" in " ".join(en_terms.split())
       and "Windows kullanıcı adı" not in tr_terms and "Windows user name" not in en_terms)
    ok("main.js: NOTICE_VERSION 2.1, TERMS_VERSION kalmadi, bildirim IPC'si notice-ack, consent-decline yok",
       'const NOTICE_VERSION = "2.1";' in main_k and "TERMS_VERSION" not in main_k
       and 'ipcMain.handle("notice-ack"' in main_k and "consent-decline" not in main_k
       and "consent-accept" not in main_k and 'ipcRenderer.invoke("notice-ack"' in preload
       and "declineConsent" not in preload and "acceptConsent" not in preload)
    hazir = main_k.find("app.whenReady()")
    ok("motor bildirimden bagimsiz baslar (startBackend, pencere / bildirim sayfasindan once)",
       hazir >= 0 and 0 <= main_k.find("startBackend();", hazir) < main_k.find("createWindow();", hazir)
       and 'noticeSeen() ? "index.html" : "consent.html"' in main_k)
    ok("Ayarlar > Lisans ve sorumluluk ayni kaynaktan (getTerms) okunur",
       'getTerms(LANG)' in oku("renderer/app.js") and 'readFileSync(path.join(__dirname, "renderer", file)' in main_k)
    ok("1024x640 icin metin kutusu yuksekligi ayarli (clamp) ve onay kutusu stilleri kalkti",
       ".consent-main .terms-box { height: clamp(" in css and "consent-checks" not in css
       and "meta-hint" not in css and ".notice-box" in css)


def test_bilgilendirme_kaydi(c):
    baslik("Bildirim kaydi: yalniz surum + tarih; BOM'lu / yarim consent.json; eski kayit bir kez gosterir")
    # NOBETCI (2026-11-10, H-03 + A6-05): kayit yalniz noticeVersion + noticeShownAt (kullanici adi ve
    # bilgisayar adi YOK); eski accepted / acceptedAt / user / host / termsVersion alanlari ilk
    # yazimda silinir; eski kayit (termsVersion 1.4) bildirimi bir kez gosterir. BOM'lu dosya yok
    # sayiliyor ve bir sonraki yazimda tercihler siliniyordu (A6-05).
    import subprocess
    node = shutil.which("node")
    if not node:
        return atla("bildirim kaydi", "node yok")
    main_js = open(os.path.join(BURASI, "..", "electron", "main.js"), encoding="utf-8").read()
    def blok(ad):
        i = main_js.find(f"function {ad}(")
        return main_js[i:main_js.find("\n}\n", i) + 2] if i >= 0 else ""
    sabit = re.search(r"const NOTICE_VERSION = [^;]+;", main_js)
    eski = re.search(r"const ESKI_ONAY_ALANLARI = \[[^\]]*\];", main_js)
    govdeler = [blok(a) for a in ("parseSettings", "readSettings", "writeSettings", "noticeSeen", "noticeKaydi")]
    if not sabit or not eski or not all(govdeler):
        return ok("main.js bildirim islevleri bulundu", False)
    with tempfile.TemporaryDirectory() as tmp:
        yol = os.path.join(tmp, "AllPrime", "consent.json")
        betik = ("const fs = require('fs'); const path = require('path'); const os = require('os');"
                 f"const settingsPath = () => {json.dumps(yol)};"
                 + sabit.group(0) + eski.group(0) + "".join(govdeler) + r"""
const sonuc = {};
sonuc.parse = ["", "abc", '{"a":1', "\uFEFF{\"a\":1}", "[1,2]", "null", '"x"', "{}"].map(parseSettings);
sonuc.seen = [{}, {accepted: true, termsVersion: "1.4"}, {noticeVersion: "2.1", noticeShownAt: "2026-11-10T08:00:00.000Z"},
              {noticeVersion: "2.0", noticeShownAt: "2026-11-10T08:00:00.000Z"}, {noticeVersion: "2.1"}].map((s) => noticeSeen(s));
const eskiKayit = {accepted: true, termsVersion: "1.4", acceptedAt: "x", user: "KULLANICI_ADI", host: "BILGISAYAR_ADI",
                   appVersion: "0.8.39", lang: "tr", pcr_max: 2000, theme: "light", zoom: 1.1, lab: {primer_min_tm: 55}};
const kopya = JSON.stringify(eskiKayit);
const y = noticeKaydi(eskiKayit, "en", "2026-11-10T09:00:00.000Z");
sonuc.yeni = y; sonuc.degismedi = JSON.stringify(eskiKayit) === kopya;
sonuc.dil = noticeKaydi({}, "fr", "T").lang;
// diskte: BOM'lu kayit okunur, yarim kayit {} sayilir, yazim gecerli JSON uretir ve .tmp birakmaz
const bomluGecerli = JSON.stringify({noticeVersion: "2.1", noticeShownAt: "2026-11-10T08:00:00.000Z", pcr_max: 2000});
fs.mkdirSync(path.dirname(settingsPath()), {recursive: true});
fs.writeFileSync(settingsPath(), "\uFEFF" + bomluGecerli, "utf8");
sonuc.bom = {seen: noticeSeen(), pcr_max: readSettings().pcr_max};
fs.writeFileSync(settingsPath(), '{"noticeVersion": "2.1", "noticeShownAt": "2026-11-', "utf8");
sonuc.yarim = {seen: noticeSeen(), anahtar: Object.keys(readSettings()).length};
const w1 = writeSettings(noticeKaydi(readSettings(), "tr", "2026-11-10T10:00:00.000Z"));
const w2 = writeSettings(noticeKaydi(readSettings(), "en", "2026-11-10T10:05:00.000Z"));
const hamYazim = fs.readFileSync(settingsPath());
sonuc.yazim = {w1, w2, bom: hamYazim[0] === 0xef, gecerli: !!JSON.parse(hamYazim.toString("utf8")), seen: noticeSeen(),
               tmp: fs.existsSync(settingsPath() + ".tmp"), dosyalar: fs.readdirSync(path.dirname(settingsPath()))};
sonuc.kullanici = [os.userInfo().username, os.hostname()].some((a) => hamYazim.toString("utf8").toLowerCase().includes(a.toLowerCase()));
console.log(JSON.stringify(sonuc));
""")
        r = subprocess.run([node, "-e", betik], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return ok("bildirim kaydi node ile calisir", False, r.stderr.strip()[:200])
        d = json.loads(r.stdout)
    ok("parseSettings: BOM'lu JSON okunur; bos, bozuk, yarim, dizi, null ve metin {} sayilir",
       d["parse"] == [{}, {}, {}, {"a": 1}, {}, {}, {}, {}], json.dumps(d["parse"]))
    ok("noticeSeen: kayit yok / eski kayit (termsVersion 1.4) / eski bildirim surumu / tarihsiz -> False; guncel -> True",
       d["seen"] == [False, False, True, False, False], json.dumps(d["seen"]))
    y = d["yeni"]
    ok("noticeKaydi: noticeVersion 2.1 + noticeShownAt, dil; eski onay alanlari ve appVersion silinir",
       y.get("noticeVersion") == "2.1" and y.get("noticeShownAt") == "2026-11-10T09:00:00.000Z" and y.get("lang") == "en"
       and not any(a in y for a in ("accepted", "acceptedAt", "user", "host", "termsVersion", "appVersion")), json.dumps(y))
    ok("  ...tercihler korunur (pcr_max, tema, boyut, laboratuvar); kullanici / bilgisayar adi dosyada yok; girdi degismez",
       y.get("pcr_max") == 2000 and y.get("theme") == "light" and y.get("zoom") == 1.1
       and y.get("lab") == {"primer_min_tm": 55} and "KULLANICI_ADI" not in json.dumps(y)
       and "BILGISAYAR_ADI" not in json.dumps(y) and d["degismedi"] and d["dil"] == "tr")
    ok("A6-05: BOM'lu consent.json yok sayilmaz (bildirim gorulmus, tercih okunur)",
       d["bom"] == {"seen": True, "pcr_max": 2000}, json.dumps(d["bom"]))
    ok("  ...yarim consent.json cokertmez: bildirim yeniden gosterilir, sonraki yazim gecerli JSON",
       d["yarim"] == {"seen": False, "anahtar": 0} and d["yazim"]["w1"] and d["yazim"]["w2"]
       and d["yazim"]["gecerli"] and d["yazim"]["seen"] and not d["yazim"]["bom"], json.dumps(d["yazim"]))
    ok("  ...yazim gecici dosya birakmaz; kayitta Windows kullanici adi / bilgisayar adi yok",
       not d["yazim"]["tmp"] and d["yazim"]["dosyalar"] == ["consent.json"] and d["kullanici"] is False)
    ack = main_js[main_js.find('ipcMain.handle("notice-ack"'):]
    ack = ack[:ack.find("\n});", 10)]
    ok("notice-ack: kullanici adi / bilgisayar adi okumaz (os.userInfo / os.hostname yok)",
       ack != "" and "userInfo" not in ack and "hostname" not in ack and "noticeKaydi(readSettings()" in ack)


def test_veri_kaynaklari_belgesi(c):
    baslik("README veri kaynaklari paketin gercek icerigiyle tutarli (H-01, H-08)")
    # NOBETCI (2026-11-10): README "genom, transkript tablosu ve dbSNP indeksi dagitilmaz" diyordu;
    # paket refGene, MANE ve dbSNP indekslerini tasiyor (package.json extraResources). Yalniz olgu:
    # hukuki yorum yok; adresler kodda zaten gecen adreslerdir (yeni adres uydurulmaz).
    import glob
    oku = lambda *p: open(os.path.join(KOK, *p), encoding="utf-8").read()
    readme = oku("GELISTIRME.md")
    paket = json.loads(oku("electron", "package.json"))
    kaynaklar = [r["from"] for r in paket["build"]["extraResources"]]
    ok("paket annotations/ klasorunu tasir (extraResources), genomes/ tasimaz",
       "../annotations" in kaynaklar and not any("genomes" in k for k in kaynaklar), str(kaynaklar))
    ok("README: 'uygulamayla dagitilmaz' / 'yeniden dagitmamis oluruz' beyani kalmadi",
       "yeniden dağıtmamış" not in readme and "uygulamayla **dağıtılmaz**" not in readme)
    bas = readme.find("## Veri dosyalarının indirilmesi")
    giris = readme[bas:readme.find("| Öğe |", bas)]
    ok("  ...giris paketin icerigini soyler: refGene, MANE, dbSNP indeksi dahil; genom FASTA dahil degil",
       "refGene tabloları (UCSC), MANE listesi (NCBI) ve dbSNP indeksleri" in giris
       and "pakete dahildir" in giris and "pakete dahil değildir" in giris)
    i = readme.find("## Veri kaynakları")
    bolum = readme[i:readme.find("\n## ", i + 10)] if i >= 0 else ""
    ok("README: 'Veri kaynaklari' bolumu var; her veri seti icin kaynak, pakette olup olmadigi, surum / tarih, atif",
       bolum != "" and all(x in bolum for x in ("Ensembl", "refGene", "MANE", "dbSNP", "Ensembl REST", "**hayır**", "**evet**",
                                                  "Sürüm / tarih", "Atıf satırı", "erişim tarihi")))
    # bolumdeki her tam adres kodda gecmeli (indirme: downloads.py; sorgu: engine.py; kosul sayfalari: lisans_bildirimi.py)
    kod = oku("backend", "downloads.py") + oku("backend", "engine.py") + oku("backend", "lisans_bildirimi.py")
    kod = re.sub(r'"\s*\n\s*"', "", kod)         # bolunmus metin parcalarini birlestir
    adresler = sorted(set(re.findall(r"https://[A-Za-z0-9./_<>-]+", bolum)))
    def kodda(a):
        a = a.rstrip(".,")
        if a.startswith("https://hgdownload.soe.ucsc.edu/goldenPath/"):          # hg19 / hg38 + tablo adi koddan turetilir
            return "hgdownload.soe.ucsc.edu/goldenPath/" in kod and a.split("/database/")[-1] in kod
        return a.split("<")[0] in kod
    yok = [a for a in adresler if not kodda(a)]
    ok("  ...bolumdeki adreslerin hepsi kodda zaten var (yeni adres uydurulmamis)", bool(adresler) and not yok, ", ".join(yok[:4]))
    ok("  ...paket dosyalari ve tarihleri olculen degerlerle yaziliyor; surum uydurulmuyor",
       "annotations/refGene_hg19.txt.gz" in bolum and "annotations/MANE.summary.txt.gz" in bolum
       and "dbsnp_common_hg38.apidx" in bolum and "ürüm numarası dosyada yazılı değil" in bolum
       and "build 151" in bolum)
    ok("  ...hukuki yorum yok (lisans / izin / serbest ifadeleri kullanilmiyor)",
       not re.search(r"(?i)serbestçe|izin verilir|hukuken|yasal olarak|telif hakkı serbest", bolum))
    tpn = oku("THIRD-PARTY-NOTICES.txt")
    j = tpn.find("Veri dosyalari / Data files")
    tb = tpn[j:tpn.find("\n=====", j + 100)]
    ok("THIRD-PARTY-NOTICES: veri notu pakette olan / olmayan / calisma aninda ve atif oneri satirini soyler",
       all(x in tb for x in ("Pakette / In the package", "Pakette yok / Not in the package", "Calisma aninda / At run time",
                             "Atif (oneri) / Citation (suggested)", "rest.ensembl.org", "snp151Common")))
    uretici = open(os.path.join(BURASI, "lisans_bildirimi.py"), encoding="utf-8").read()
    ok("  ...ayni not uretici betikte (lisans_bildirimi.py) de var: dosya elle duzenlenmemis",
       "Pakette / In the package" in uretici and "Atif (oneri) / Citation (suggested)" in uretici)
    authors = oku("AUTHORS")
    ok("AUTHORS: kurum yer tutucu notu yok, yazar e-postasi duruyor; kaynak basliklari tekil (eser sahibi)",
       "Kurum adını da eklemek isterseniz" not in authors and "eren.501kilinc@gmail.com" in authors
       and "eser sahipleri" not in "".join(
           open(p, encoding="utf-8", errors="replace").read()
           for p in glob.glob(os.path.join(KOK, "backend", "*.py")) + glob.glob(os.path.join(KOK, "electron", "*.js"))
           + glob.glob(os.path.join(KOK, "electron", "renderer", "*.*"))
           if not p.endswith("test_smoke.py")))


def test_claude_dagitima_girmez(c):
    baslik("Dagitim paketine ve kurulu klasore .claude girmez (T-01)")
    # NOBETCI (2026-11-10): kurulu klasorde .claude\settings.local.json bulundu (kurulu klasorde
    # calisan bir gelistirme araci oturumunun yerel izin / komut gecmisi dosyasi; hicbir betik kopyalamadi).
    # Kopyalama yapan her yer .claude'u acikca disarida birakir; kaynak zip'i uretildikten sonra denetlenir.
    import subprocess
    oku = lambda *p: open(os.path.join(KOK, *p), encoding="utf-8").read()
    paket = json.loads(oku("electron", "package.json"))["build"]
    filtre = ["!**/.claude", "!**/.claude/**/*"]
    ok("package.json: build.files ve her extraResources girdisi .claude'u disarida birakir",
       all(f in paket["files"] for f in filtre)
       and all(all(f in (r.get("filter") or []) for f in filtre) for r in paket["extraResources"]))
    ok("build.ps1: sidecar'dan .claude temizlenir ve paket klasoru denetlenir",
       'Filter ".claude"' in oku("build.ps1") and "Paketin icinde .claude var" in oku("build.ps1"))
    ok("kurulu-guncelle.ps1: kopyalama listesi ve Electron / motor kopyasi .claude'u atlar, kurulu klasorde varsa uyarir",
       "'(^|\\\\)\\.claude(\\\\|$)'" in oku("kurulu-guncelle.ps1") and '$f.Name -eq ".claude"' in oku("kurulu-guncelle.ps1")
       and "kurulu klasorde .claude var" in oku("kurulu-guncelle.ps1"))
    ok(".gitignore .claude/ icerir", ".claude/" in oku(".gitignore").splitlines())
    zip_ps = oku("kaynak-zip.ps1")
    m = re.search(r'archive [^\n]*?-- \. "([^"]+)"', zip_ps)
    ok("kaynak-zip.ps1: git archive pathspec'i .claude'u dislar ve zip girdileri denetlenir",
       bool(m) and "zip icinde .claude girdisi var" in zip_ps, m.group(1) if m else "pathspec yok")
    git = shutil.which("git")
    if not (git and m):
        return atla("kaynak zip dislamasi (gecici depo)", "git ya da pathspec yok")
    import io
    import tarfile
    with tempfile.TemporaryDirectory() as tmp:
        def g(*a):
            return subprocess.run([git, "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.safecrlf=false", *a],
                                  capture_output=True, timeout=60)
        g("init", "-q")
        for yol in (".claude/settings.local.json", "electron/renderer/.claude/yapay.txt", "electron/renderer/app.js", "AUTHORS"):
            os.makedirs(os.path.dirname(os.path.join(tmp, yol)), exist_ok=True)
            open(os.path.join(tmp, yol), "w").write("x")
        g("add", "-f", ".")
        g("commit", "-q", "-m", "t")
        izlenen = g("ls-files").stdout.decode().split()
        cikti = g("archive", "--format=tar", "HEAD", "--", ".", m.group(1)).stdout
        girdiler = [x.name for x in tarfile.open(fileobj=io.BytesIO(cikti)).getmembers() if x.isfile()]
    ok("yapay .claude klasorleri git'e eklenmis olsa bile (ust duzey + alt klasor) zip listesine girmez",
       sum(".claude" in x for x in izlenen) == 2 and sorted(girdiler) == ["AUTHORS", "electron/renderer/app.js"],
       f"izlenen={izlenen} zip={girdiler}")


def test_tm_kosul_notu(c):
    baslik("Tm'in yontemi ve kosullari ekranda yaziyor")
    # NOBETCI (2026-10-31): sentez firmasinin "Basic" Tm'i (yalnizca uzunluk + G+C)
    # programinkinden 4-7 derece dusuk cikinca programin degeri yanlis sanildi; Tm'in
    # hangi yontem ve kosullarla hesaplandigi ekranda hic yazmiyordu.
    F, R = "GGCCTGAAGATTTCCTGAAG", "AGGTTGTGGTCCTTTGTTTG"
    anahtar = ("salt_monovalent", "salt_divalent", "dntp_conc", "dna_conc", "dmso_conc")
    r = c.post("/evaluate", json={"forward": F, "reverse": R, "assembly": "yok"})
    j = r.get_json() or {}
    k = j.get("params_used") or {}
    tm_f = ((j.get("primers") or {}).get("forward") or {}).get("tm")
    ok("Degerlendir yaniti Tm kosullarini veriyor (varsayilan 50 / 1,5 / 0,6 / 50 / 0)",
       r.status_code == 200 and [k.get(a) for a in anahtar] == [50.0, 1.5, 0.6, 50.0, 0.0],
       f"-> {r.status_code} {k}")
    ok("  ...F primerin Tm'i tasarimdakiyle ayni (56,1)",
       tm_f is not None and abs(tm_f - 56.1) < 0.05, f"-> {tm_f}")
    r2 = c.post("/evaluate", json={"forward": F, "reverse": R, "assembly": "yok",
                                   "params": {"salt_divalent": "2.5"}})
    j2 = r2.get_json() or {}
    tm_f2 = ((j2.get("primers") or {}).get("forward") or {}).get("tm")
    ok("  ...kullanicinin Mg2+ degeri yanitta ve Tm'i yukseltiyor",
       (j2.get("params_used") or {}).get("salt_divalent") == 2.5
       and tm_f2 is not None and tm_f is not None and tm_f2 > tm_f, f"-> {tm_f} -> {tm_f2}")
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    app = open(os.path.join(kok, "app.js"), encoding="utf-8").read()
    i18n = open(os.path.join(kok, "i18n.js"), encoding="utf-8").read()
    tr, en = i18n.split(chr(10) + "  en: {", 1)
    for dil, metin in (("TR", tr), ("EN", en)):
        ok(f"  ...{dil}: not yontemi, Mg2+ ve 'Basic' Tm farkini acikliyor",
           all(s in metin for s in ('"tm.note"', '"tm.cond"', "SantaLucia 1998", "Mg²⁺", "Basic")))
    # 2026-11-01: not belirli bir sentez firmasini genellemesin (kullanici: "herkes ayni
    # firmaya yaptirmiyor"); fark yontem / kosul farki olarak anlatilsin.
    for dil, metin, yasak in (("TR", tr, "firma"), ("EN", en, "supplier")):
        i = metin.find('"tm.why"')
        parca = metin[i:metin.find('"chip.ta"', i)] if i >= 0 else ""
        ok(f"  ...{dil}: Tm farki belirli bir firmaya baglanmiyor (yontem / kosul farki)",
           bool(parca) and yasak not in parca.lower() and ("yöntem" in parca or "method" in parca))
    ok("not tasarim ve Degerlendir sonuclarinda, motorun kullandigi degerlerle",
       app.count("tmNotu(j)") >= 3 and "j.params_used" in app)


def _eski_ad_deseni():
    import re
    return re.compile(r"(?i:\bek-primer|\bekprimer|ekidx)|\bEK Primer\b|\bEK_[A-Z]|\[EK\]|EKSNP"  # onceki-ad-uyumu
                      r"|\bwindow\.ek\b|exposeInMainWorld\(\"ek\"")                          # onceki-ad-uyumu


def _eski_ad_ara(kok, atlanan=()):
    """kok altindaki metin dosyalarinda ve dosya adlarinda uygulamanin eski adini arar.
    'onceki-ad-uyumu' isaretli satirlar (eski ayar / indeks dosyalarini taniyanlar)
    bulunan sayilmaz; ayrica dondurulur."""
    desen = _eski_ad_deseni()
    uzantilar = {".py", ".js", ".html", ".css", ".json", ".md", ".txt", ".ps1", ".svg",
                 ".spec", ".bat", ".cmd", ""}
    bulunan, isaretli = [], set()
    for k, dd, ff in os.walk(kok):
        dd[:] = [a for a in dd if a not in atlanan]
        bulunan += [os.path.relpath(os.path.join(k, a), kok) for a in dd + ff if desen.search(a)]
        for a in ff:
            if os.path.splitext(a)[1].lower() not in uzantilar:
                continue
            yol = os.path.join(k, a)
            try:
                with open(yol, encoding="utf-8", errors="replace") as f:
                    for no, satir in enumerate(f, 1):
                        if not desen.search(satir):
                            continue
                        if "onceki-ad-uyumu" in satir:
                            isaretli.add(os.path.relpath(yol, kok))
                        else:
                            bulunan.append(f"{os.path.relpath(yol, kok)}:{no}")
            except OSError:
                pass
    return bulunan, isaretli


def test_eski_ad_yok(c):
    baslik("Uygulamanin eski adi kalmadi")
    # NOBETCI (2026-11-01, kullanici: "eski adi da kalmasin bir yerde, AllPrime adi"):
    # eski ad ayar klasorunde, motorun ortam degiskenlerinde, gunluk onekinde, dbSNP
    # indeksinin uzantisi ve basliginda, belgelerde ve kaynak klasorunun adinda
    # kalmisti. Eski adi yalnizca eski surumden kalan ayar / indeks dosyalarini
    # taniyan, isaretli satirlar anabilir.
    import re
    atlanan = {".git", "node_modules", ".venv", "__pycache__", "annotations", "genomes",
               ".cache", "sidecar", "dist", "build"}
    bulunan, isaretli = _eski_ad_ara(KOK, atlanan)
    ok("kaynakta (kod, belge, betik, dosya adi) eski ad gecmiyor", not bulunan, str(bulunan[:6]))
    ok("  ...eski adi yalnizca eski ayar / indeks dosyalarini taniyan satirlar aniyor",
       isaretli <= {os.path.join("backend", a) for a in ("engine.py", "dbsnp.py", "test_smoke.py")},
       str(sorted(isaretli)))
    ok("  ...kaynak klasorunun adinda da yok", not _eski_ad_deseni().search(os.path.basename(KOK)),
       os.path.basename(KOK))
    # Ortam degiskenlerinin adi degisti. main.js'in verdigini motor okumazsa anahtar
    # denetimi SESSIZCE kapanir (server.py: anahtar yoksa gelistirme modu sayilir).
    with open(os.path.join(KOK, "electron", "main.js"), encoding="utf-8") as f:
        m = re.search(r"Object\.assign\(\{\}, process\.env, \{([^}]*)\}\)", f.read())
    verilen = re.findall(r"([A-Z][A-Z0-9_]+)\s*:", m.group(1)) if m else []
    motor = ""
    for a in sorted(os.listdir(BURASI)):
        if a.endswith(".py") and a != "test_smoke.py":
            with open(os.path.join(BURASI, a), encoding="utf-8") as f:
                motor += f.read()
    okunan = set(re.findall(r"os\.environ(?:\.get\(|\[)\"([A-Z][A-Z0-9_]+)\"", motor))
    ok("main.js'in motora verdigi ortam degiskenlerini motor okuyor (anahtar dahil)",
       "ALLPRIME_TOKEN" in verilen and "ALLPRIME_APP_ROOT" in verilen and set(verilen) <= okunan,
       f"verilen={verilen}")


def test_ayar_klasoru_tasinir(engine):
    baslik("Ayar klasoru AllPrime adinda; eskisi bir kez tasinir")
    # NOBETCI (2026-11-01): ayar klasoru (%APPDATA%) uygulamanin eski adini tasiyordu;
    # elle secilmis genom yollari kaybolmasin diye bilerek oyle birakilmisti. Artik
    # AllPrime; eski klasordeki config.json ve data\ acilista bir kez tasinir.
    def oku(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    ok("ayar klasoru %APPDATA%\\AllPrime", os.path.basename(engine.CONFIG_DIR) == "AllPrime",
       engine.CONFIG_DIR)
    tasi = getattr(engine, "eski_ayarlari_tasi", None)
    g = tempfile.mkdtemp(prefix="allprime_ayar_")
    try:
        eski, yeni = os.path.join(g, "eski"), os.path.join(g, "yeni")
        ayar = os.path.join(yeni, "config.json")
        os.makedirs(os.path.join(eski, "data", "genomes"))
        with open(os.path.join(eski, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"genomes": {"GRCh38": "D:\\genom.fa"}}, f)
        with open(os.path.join(eski, "data", "genomes", "x.fa"), "w") as f:
            f.write(">x\nACGT\n")
        os.makedirs(yeni)                       # Electron'un profil klasoru zaten var
        open(os.path.join(yeni, "Preferences"), "w").close()
        tasinan = tasi(eski, yeni) if tasi else None
        ok("config.json ve data\\ yeni klasore tasinir, bosalan eski klasor silinir",
           sorted(tasinan or []) == ["config.json", "data"] and not os.path.exists(eski)
           and os.path.exists(os.path.join(yeni, "data", "genomes", "x.fa"))
           and os.path.exists(os.path.join(yeni, "Preferences")), str(tasinan))
        ok("  ...tasinan ayar okunur", os.path.exists(ayar)
           and oku(ayar)["genomes"]["GRCh38"] == "D:\\genom.fa")
        os.makedirs(eski, exist_ok=True)       # eski kodda tasinmamis olur
        with open(os.path.join(eski, "config.json"), "w", encoding="utf-8") as f:
            f.write('{"genomes": {}}')
        tasinan = tasi(eski, yeni) if tasi else None
        ok("  ...yenide ayni ad varsa ikisi de ezilmez, eski klasor yerinde kalir",
           tasinan == [] and os.path.exists(os.path.join(eski, "config.json"))
           and oku(ayar)["genomes"].get("GRCh38") == "D:\\genom.fa", str(tasinan))
        ok("  ...eski klasor yoksa hicbir sey yapmaz",
           tasi is not None and tasi(os.path.join(g, "yok"), yeni) == [])
    finally:
        shutil.rmtree(g, ignore_errors=True)


def test_eski_dbsnp_indeksi(engine):
    baslik("dbSNP indeksi yeni adla; onceki adla uretilmis indeks okunur ve cevrilir")
    # NOBETCI (2026-11-01): indeksin uzantisi ve sihirli sayisi uygulamanin eski adini
    # tasiyordu. Yeni indeks yeni adla yazilir; eski klasorden kopyalanan indeks okunur
    # ve bulundugu yerde yeni ada cevrilir (760 MB'lik kaynak yeniden indirilmez).
    import gzip as _gz
    import dbsnp
    import downloads
    ok("indeks uzantisi .apidx; indirme paneli de ayni adi bekliyor",
       getattr(dbsnp, "UZANTI", None) == ".apidx"
       and downloads.catalog()["dbsnp_GRCh38"]["hedef"].endswith(".apidx"))
    d = tempfile.mkdtemp(prefix="allprime_snp_")
    try:
        def satir(rs, poz):
            c = ["0", "chr1", str(poz), str(poz + 1), f"rs{rs}"] + ["x"] * 6 + ["single"] + \
                ["x"] * 12 + ["0.7,0.3,"]
            return "\t".join(c) + "\n"
        kaynak = os.path.join(d, "snp.txt.gz")
        with _gz.open(kaynak, "wt") as f:
            for i in range(500):
                f.write(satir(i + 1, 1000 + 10 * i))
        yeni = os.path.join(d, "dbsnp_common_hg38.apidx")
        dbsnp.build_index(kaynak, yeni, "GRCh38")
        with open(yeni, "rb") as f:
            veri = bytearray(f.read())
        ix = dbsnp.SnpIndex(yeni)
        beklenen = ix.overlaps("1", 1000, 1100)
        ix.close()
        ok("  ...yeni indeksin basligi APSNP1", bytes(veri[:6]) == b"APSNP1" and len(beklenen) == 10,
           repr(bytes(veri[:8])))
        # Onceki surumun indeksi: ayni bicim, eski uzanti ve sihirli sayi
        veri[:8] = b"EKSNP1\x00\x00"                                          # onceki-ad-uyumu
        os.remove(yeni)
        eski = os.path.join(d, "dbsnp_common_hg38.ekidx")                     # onceki-ad-uyumu
        with open(eski, "wb") as f:
            f.write(veri)
        cevir = getattr(dbsnp, "eski_indeksi_cevir", None)
        yol = cevir(eski) if cevir else None
        ok("onceki adla uretilmis indeks yeni ada cevrilir",
           yol == yeni and os.path.exists(yeni) and not os.path.exists(eski), str(yol))
        if yol == yeni:
            with open(yeni, "rb") as f:
                bas = f.read(8)
            ix = dbsnp.SnpIndex(yeni)
            ayni = ix.overlaps("1", 1000, 1100) == beklenen
            ix.close()
            ok("  ...basligi da yenilenir, sorgu sonucu degismez", bas[:6] == b"APSNP1" and ayni,
               repr(bas))
        # Cevrilemeyen eski indeks (salt okunur klasor, baska surecte acik) oldugu gibi okunur
        kopya = os.path.join(d, "kopya.ekidx")                                # onceki-ad-uyumu
        with open(kopya, "wb") as f:
            f.write(veri)
        try:
            ix = dbsnp.SnpIndex(kopya)
            ayni = ix.overlaps("1", 1000, 1100) == beklenen
            ix.close()
        except Exception:
            ayni = False
        ok("  ...eski basligi tasiyan indeks de okunur", ayni)
        # Acilista: uygulama klasorundeki eski adli indeks bulunur ve cevrilir
        app = os.path.join(d, "app")
        os.makedirs(os.path.join(app, "annotations"))
        eski = os.path.join(app, "annotations", "dbsnp_common_hg19.ekidx")    # onceki-ad-uyumu
        with open(eski, "wb") as f:
            f.write(veri)
        kayitli = dict(dbsnp.DBSNP_PATHS)
        eski_kok = os.environ.get("ALLPRIME_APP_ROOT")
        try:
            os.environ["ALLPRIME_APP_ROOT"] = app
            dbsnp.DBSNP_PATHS["GRCh37"] = ""
            dbsnp.autodetect_dbsnp()
            bulunan = dbsnp.DBSNP_PATHS.get("GRCh37") or ""
        finally:
            dbsnp.DBSNP_PATHS.update(kayitli)
            if eski_kok is None:
                os.environ.pop("ALLPRIME_APP_ROOT", None)
            else:
                os.environ["ALLPRIME_APP_ROOT"] = eski_kok
        hedef = os.path.join(app, "annotations", "dbsnp_common_hg19.apidx")
        ok("  ...uygulama klasorundeki eski adli indeks acilista bulunur ve cevrilir",
           os.path.normcase(bulunan) == os.path.normcase(hedef) and not os.path.exists(eski),
           bulunan)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_openblas_ortami():
    """v0.8.44: motor acilisinda (numpy yuklenmeden once) OPENBLAS_NUM_THREADS=1 kurulur; havuz iscileri ortami
    miras alir. Olcum: en iyi Ozgul cift aramasinda 24 cekirdekte toplam commit 11,6 GB -> 2,0 GB, sonuc ve sure
    ayni. Kullanicinin verdigi baska deger ezilmez."""
    baslik("OpenBLAS is parcacigi: motor ortami")
    import subprocess
    kaynak = open(os.path.join(BURASI, "server.py"), encoding="utf-8").read()
    i_ayar = kaynak.find('os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")')
    i_ilk = kaynak.find("\nimport engine")
    ok("server.py: ayar ilk motor modulunden (numpy'yi ceken) once", 0 < i_ayar < i_ilk, f"{i_ayar} {i_ilk}")
    kod = ("import os, sys; sys.path.insert(0, sys.argv[1]); import server; "
           "print('DEGER=' + str(os.environ.get('OPENBLAS_NUM_THREADS')))")

    def deger(**ek):
        e = {k: v for k, v in os.environ.items() if k != "OPENBLAS_NUM_THREADS"}
        e.update(ek)
        r = subprocess.run([sys.executable, "-B", "-c", kod, BURASI], env=e, capture_output=True, text=True,
                           timeout=300)
        s = [x for x in r.stdout.splitlines() if x.startswith("DEGER=")]
        return s[-1][6:] if s else (r.stdout + r.stderr)[-200:]
    ok("Temiz ortamda `import server` sonrasi OPENBLAS_NUM_THREADS=1", deger() == "1", deger())
    ok("Kullanicinin verdigi deger (4) ezilmez", deger(OPENBLAS_NUM_THREADS="4") == "4")


def test_kurulu_temizlik(c):
    baslik("Kurulu klasor: Electron artiklari, dil paketleri, eski yedekler")
    # NOBETCI (2026-11-01): Electron yukseltmesi yeni surumde OLMAYAN dosyalari
    # birakiyordu (33.x'ten libEGL.dll ve libGLESv2.dll; 44.10.0'da hicbir surec
    # yuklemiyordu), 55 dil paketinin 53'u kullanilmiyordu ve kurulu-guncelle.ps1'in
    # her calistirmada biraktigi yedekler hic silinmiyordu (TEMP'te 6,6 GB).
    import subprocess
    betik = os.path.join(KOK, "kurulu-temizle.ps1")
    with open(os.path.join(KOK, "kurulu-guncelle.ps1"), encoding="utf-8") as f:
        kg = f.read()
    ok("kurulu-guncelle.ps1 temizlik betigini cagiriyor",
       os.path.exists(betik) and "kurulu-temizle.ps1" in kg)
    g = tempfile.mkdtemp(prefix="allprime_temizlik_")
    try:
        uyg, dist, gec = (os.path.join(g, a) for a in ("AllPrime", "dist", "TEMP"))

        def dosya(*p):
            yol = os.path.join(*p)
            os.makedirs(os.path.dirname(yol), exist_ok=True)
            with open(yol, "wb") as f:
                f.write(b"x" * 10)

        def loc(a):
            return os.path.join("locales", a)
        for a in ("version", "ffmpeg.dll", "resources.pak", "icudtl.dat", "snapshot_blob.bin",
                  loc("tr.pak"), loc("en-US.pak"), loc("de.pak")):
            dosya(dist, a)
        kalacak = ["AllPrime.exe", "ffmpeg.dll", "resources.pak", "icudtl.dat",
                   "snapshot_blob.bin", "LICENSE", "notlar.txt", loc("tr.pak"), loc("en-US.pak"),
                   os.path.join("annotations", "refGene_hg38.txt.gz"),
                   os.path.join("resources", "backend", "_internal", "python313.dll")]
        gidecek = ["libEGL.dll", "libGLESv2.dll", loc("de.pak"), loc("fr.pak")]
        for a in kalacak + gidecek:
            dosya(uyg, a)
        for a in ("AllPrime-exe-yedek-20261001-000000.exe", "AllPrime-exe-yedek-20261002-000000.exe",
                  os.path.join("AllPrime-electron-yedek-20261001-000000", "eski.dll"),
                  os.path.join("allprime-derleme", "backend-yedek-20261001-000000", "a.exe"),
                  os.path.join("allprime-derleme", "backend-yedek-20261002-000000", "a.exe"),
                  "baska-programin-dosyasi.tmp"):
            dosya(gec, a)

        def calistir():
            if not os.path.exists(betik):
                return None
            return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                   "-File", betik, "-Uygulama", uyg, "-Dist", dist, "-Gecici", gec],
                                  capture_output=True, text=True, errors="replace", timeout=120)
        r = calistir()
        cikti = (r.stdout + r.stderr).strip()[-300:] if r else "betik yok"
        ok("betik calisir", r is not None and r.returncode == 0, cikti)
        ok("  ...Electron'un dagitmadigi dll'ler ve fazla dil paketleri kalkar",
           not any(os.path.exists(os.path.join(uyg, a)) for a in gidecek))
        ok("  ...uygulamanin dosyalari, kullanicinin dosyasi, tr ve en-US kalir",
           all(os.path.exists(os.path.join(uyg, a)) for a in kalacak))
        gecici = sorted(os.listdir(gec))
        el = [a for a in gecici if a.startswith("AllPrime-electron-yedek-")]
        yedek = os.path.join(gec, el[-1]) if el else g
        ok("  ...kaldirilanlar silinmez, yedege tasinir",
           os.path.exists(os.path.join(yedek, "libEGL.dll"))
           and os.path.exists(os.path.join(yedek, "locales-fazla", "de.pak")), str(el))
        derleme = os.path.join(gec, "allprime-derleme")
        ok("  ...her turden yalnizca en yeni yedek kalir, baska dosyaya dokunulmaz",
           [a for a in gecici if a.startswith("AllPrime-exe-yedek-")]
           == ["AllPrime-exe-yedek-20261002-000000.exe"] and len(el) == 1
           and os.listdir(derleme) == ["backend-yedek-20261002-000000"]
           and "baska-programin-dosyasi.tmp" in gecici, str(gecici))
        r = calistir()
        ok("  ...ikinci calistirma bir sey degistirmez",
           r is not None and r.returncode == 0 and sorted(os.listdir(gec)) == gecici
           and all(os.path.exists(os.path.join(uyg, a)) for a in kalacak))
    finally:
        shutil.rmtree(g, ignore_errors=True)
    # Paketli motor modunda kurulu klasorun kendisi (kurulu-guncelle.ps1'den sonra kosulur;
    # kaynak modunda kurulu klasor kaynaktan geride olabilir)
    if not HTTP:
        return
    uyg = os.environ.get("ALLPRIME_APP_ROOT", "")
    if not os.path.exists(os.path.join(uyg, "AllPrime.exe")):
        atla("Kurulu klasorun kendisi", "kurulu uygulama yok")
        return
    el_dist = os.path.join(KOK, "electron", "node_modules", "electron", "dist")
    artik = [a for a in os.listdir(uyg)
             if os.path.splitext(a)[1].lower() in (".dll", ".pak", ".bin", ".dat")
             and os.path.isdir(el_dist) and not os.path.exists(os.path.join(el_dist, a))]
    diller = sorted(os.listdir(os.path.join(uyg, "locales")))
    ok("kurulu klasorde Electron artigi yok; dil paketleri tr ve en-US",
       not artik and diller == ["en-US.pak", "tr.pak"], f"artik={artik} dil={len(diller)}")
    desen = _eski_ad_deseni()
    adlar = []
    for k, dd, ff in os.walk(uyg):
        dd[:] = [a for a in dd if a != "genomes"]
        adlar += [os.path.relpath(os.path.join(k, a), uyg) for a in dd + ff if desen.search(a)]
    metin, _ = _eski_ad_ara(os.path.join(uyg, "resources", "app"))
    for a in ("KURULUM.txt", "THIRD-PARTY-NOTICES.txt", "AUTHORS"):
        with open(os.path.join(uyg, a), encoding="utf-8", errors="replace") as f:
            metin += [f"{a}:{no}" for no, satir in enumerate(f, 1) if desen.search(satir)]
    ok("kurulu klasorde (dosya adlari, arayuz, belgeler) eski ad gecmiyor",
       not adlar and not metin, str((adlar + metin)[:5]))


_TIKALI_HAVUZ = r"""
import multiprocessing as mp, sys, time
if __name__ == "__main__":
    sys.path.insert(0, sys.argv[1])
    import specificity as S
    havuz = mp.Pool(3, initializer=S._worker_init, initargs=("yok.fa", [], 6, 4, 10, 30))
    havuz.map_async(time.sleep, [600] * 3)
    time.sleep(1.5)
    print("HAZIR", flush=True)
    time.sleep(600)
"""


def test_kapanista_isci_kalmaz(c):
    baslik("Motor sonlandirilinca tarama iscileri de kapanir")
    # NOBETCI (2026-10-31): paketli motor testinden sonra 2 tarama iscisi ebeveynsiz,
    # bos (CPU sabit) ve ~58 MB'ar bellekle dakikalarca acik kaldi. Isci, borudan okurken
    # ebeveyn olurse kapanir; ama o an kilit beklerken (havuz kapanisi sirasinda motor
    # kapatilirsa) ya da uzun bir hesaptaysa boruya hic dokunmadigi icin kapanmaz.
    # Windows'ta motoru sonlandirmak (main.js pyProc.kill(), Gorev Yoneticisi) alt
    # surecleri kapatmaz. Duzeltme: isci ebeveynini izler (specificity._ebeveyn_bekcisi)
    # ve main.js motoru alt surecleriyle kapatir (taskkill /T).
    main_js = open(os.path.join(BURASI, "..", "electron", "main.js"), encoding="utf-8").read()
    ok("uygulama motoru alt surecleriyle kapatiyor (taskkill /T)",
       "taskkill" in main_js and '"/T"' in main_js and main_js.count("motoruKapat()") >= 2)
    if os.name != "nt":
        return atla("tarama iscileri", "yalnizca Windows")
    import subprocess
    import threading
    import requests

    def isciler(pid):
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"(Get-CimInstance Win32_Process -Filter 'ParentProcessId={pid}').ProcessId"],
                           capture_output=True, text=True, timeout=60)
        return [int(x) for x in r.stdout.split() if x.strip().isdigit()]

    def sonlandir_ve_say(surec, goruldu):
        surec.terminate()             # Electron'un pyProc.kill()'i ile ayni: TerminateProcess
        surec.wait(30)
        kalan, t0 = goruldu, time.time()
        while kalan and time.time() - t0 < 15:
            time.sleep(1)
            kalan = isciler(surec.pid)
        return kalan, time.time() - t0

    def temizle(surec, kalan):
        if surec.poll() is None:
            surec.kill()
        for p in kalan or isciler(surec.pid):      # eski kodda kalanlari temizle
            subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True)

    # Venv baslaticisi alt surecleri kendi is nesnesiyle oldurur; sorunu gizlememesi
    # icin kaynaktaki surecler TABAN yorumlayiciyla baslatilir.
    taban = getattr(sys, "_base_executable", sys.executable)
    ek = {"PYTHONPATH": os.pathsep.join(y for y in sys.path if y.endswith("site-packages"))}

    # 1) Belirlenimci: iscileri boruya dokunmayan bir iste (uyku) tutarken ebeveyni oldur
    betik = os.path.join(tempfile.mkdtemp(prefix="allprime-havuz-"), "tikali_havuz.py")
    with open(betik, "w", encoding="utf-8") as f:
        f.write(_TIKALI_HAVUZ)
    surec = subprocess.Popen([taban, betik, BURASI], env=dict(os.environ, **ek),
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    kalan = []
    try:
        hazir = surec.stdout.readline().strip() == "HAZIR"
        goruldu = isciler(surec.pid)
        ok("tikali isciler kuruldu", hazir and len(goruldu) == 3, f"{len(goruldu)} isci")
        kalan, sure = sonlandir_ve_say(surec, goruldu)
        ok("ebeveyn olunce tikali isciler de kapanir", not kalan,
           f"{len(kalan)} isci acik kaldi" if kalan else f"{sure:.1f} sn icinde")
    finally:
        temizle(surec, kalan)
        shutil.rmtree(os.path.dirname(betik), ignore_errors=True)

    # 2) Uctan uca: gercek motor + gercek tarama; tarama surerken motoru sonlandir
    if EXE_YOLU:
        komut, cwd, ek2 = [EXE_YOLU], os.path.dirname(EXE_YOLU), None
    else:
        komut, cwd, ek2 = [taban, os.path.join(BURASI, "server.py")], BURASI, ek
    surec, url, token = _motor_baslat(komut, cwd, ek2)
    sonuc, kalan = {}, []

    def tara():
        try:
            sonuc["r"] = requests.post(url + "/specificity", timeout=180,
                                       headers={"X-AllPrime-Token": token},
                                       json={"assembly": "GRCh38", "forward": "GGCTCCATGAGGGTGTTT",
                                             "reverse": "TCCAGGGTCCTCAGTTTCT"})
        except requests.RequestException as e:
            sonuc["hata"] = str(e)[:80]

    try:
        threading.Thread(target=tara, daemon=True).start()
        goruldu, t0 = [], time.time()
        while not goruldu and time.time() - t0 < 60 and "r" not in sonuc:
            goruldu = isciler(surec.pid)
        ok("tarama sirasinda isci surecler calisiyor", len(goruldu) > 0,
           f"{len(goruldu)} isci" + (" (tarama isciler gorulmeden bitti)" if "r" in sonuc else ""))
        kalan, sure = sonlandir_ve_say(surec, goruldu)
        ok("motor tarama sirasinda sonlandirilinca isci kalmaz", not kalan,
           f"{len(kalan)} isci acik kaldi" if kalan else f"{sure:.1f} sn icinde")
    finally:
        temizle(surec, kalan)


def test_gorsel_duzen(c):
    baslik("Gorsel duzen (2026-11-01 inceleme onerileri)")
    # NOBETCI: olculen sorunlar - giris kutusu kenarligi zemine 1,19:1 (gerekli 3:1), urun
    # dizisi satir numarasi 2,66:1, marka turkuazi ile 'iyi' yesili 14 derece; ozgulluk
    # rozeti "3' self-komp." cipiyle ayni gorunuyor, 9 cip iki satira tasiyordu; Kontrol
    # primeri Reverse ile ayni renkti; ipucu satirlari ~176 karakter; 169 oge 11 px idi.
    import colorsys
    import re
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    oku = lambda ad: open(os.path.join(kok, ad), encoding="utf-8").read()
    css, app, html, i18n = oku("style.css"), oku("app.js"), oku("index.html"), oku("i18n.js")
    # Koyu temanin degerleri (ilk :root blogu); acik tema test_ayarlar_ekrani'nda
    koyu_blok = css[css.find(":root {"):css.find("}", css.find(":root {"))]
    tok = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", koyu_blok))

    def lum(h):
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        f = lambda x: x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

    def oran(a, b):
        x, y = sorted((lum(a), lum(b)), reverse=True)
        return (x + 0.05) / (y + 0.05)

    def ton(h):
        return colorsys.rgb_to_hls(*(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)))[0] * 360

    kenar = tok.get("input-border")
    ok("giris kutusu kenarligi panele ve kutu zeminine en az 3:1",
       bool(kenar) and oran(kenar, tok["panel"]) >= 3 and oran(kenar, tok["panel-2"]) >= 3
       and "border: 1px solid var(--input-border)" in css,
       f"{oran(kenar, tok['panel']):.2f} / {oran(kenar, tok['panel-2']):.2f}" if kenar else "token yok")
    fark = abs(ton(tok["accent"]) - ton(tok["good"]))
    ok("marka turkuazi ile 'iyi' yesili en az 25 derece ayri", fark >= 25, f"{fark:.0f} derece")
    ok("Kontrol primeri kendi renginde ve okunur (en az 4,5:1)",
       'row("bp.dir.control", "dir-k", k)' in app and "kontrol" in tok
       and oran(tok["kontrol"], tok["panel-2"]) >= 4.5 and ".dir-k {" in css)
    ok("Forward etiketi urun dizisindeki rengiyle ayni (marka rengi)",
       re.search(r"\.dir-f \{[^}]*var\(--accent\)", css) is not None)
    ok("urun dizisi satir numaralari okunur (soluk metin rengi)",
       re.search(r"\.amp-no \{[^}]*color: var\(--muted\)", css) is not None)
    ok("ozgulluk rozeti sira numarasinin yaninda, kendi stilinde",
       'bas.querySelector(".rank-badge")' in app and "sira.after(r)" in app
       and ".pair-head .spec-rozet.chip-ok" in css)
    ok("kart basliginda ikincil degerler ayri satirda (butun kart turleri)",
       '<div class="cip-ikincil">' in app and app.count("qualityChips(p, ") >= 4
       and ".pair-head .cip-ikincil" in css)
    ok("tablolarda sayisal sutunlar saga yasli, rakamlar esit genislikte",
       app.count('class="sayi"') >= 20 and "tabular-nums" in css
       and re.search(r"td\.sayi \{ text-align: right", css) is not None)
    ok("  ...genis pencerede hucreler tek satir, dar pencerede (1100 px alti) kirilabilir",
       "table.primer-table th, table.primer-table td { white-space: nowrap; }" in css
       and "@media (max-width: 1100px) { table.primer-table th, table.primer-table td { white-space: normal; } }" in css)
    ok("panelin ilk kutusunda bos serit yok",
       re.search(r"\.panel > \.opt-box:first-child \{ margin-top: 0", css) is not None)
    ok("duzyazi satirlari en fazla ~84 karakter",
       re.search(r"\.hint, \.note \{ max-width: 84ch", css) is not None)
    kucuk = [sec.strip() for sec, gov in re.findall(r"([^{}]+)\{([^}]*)\}", css)
             if re.search(r"\b(th|label)\b", sec) and re.search(r"font-size:\s*1[01](\.\d+)?px", gov)]
    ok("tablo basliklari ve alan etiketleri en az 12 px", not kucuk, "; ".join(kucuk[:3]))
    # 2026-11-01: tek alt panel de kalkti, uc bolum Ayarlar ekraninda (test_ayarlar_ekrani)
    ok("veri / genom / lisans ana ekranda ayri panel olarak yok",
       'id="ayarPanel"' not in html and 'class="panel genome-panel"' not in html)
    ok("tasarim ve Degerlendir bitince sonuclara kaydirir (hareket azaltma tercihine uyar)",
       app.count("sonucaKaydir(") >= 3 and "prefers-reduced-motion" in app)
    tm = app[app.find("function tmNotu"):app.find("function sonucaKaydir")]
    tr, en = i18n.split(chr(10) + "  en: {", 1)
    ok("Tm notu kisa; 'Basic' Tm aciklamasi acilir ayrintida (TR/EN)",
       "<details" in tm and all('"tm.why"' in m and '"tm.whyText"' in m for m in (tr, en)))


def test_ayarlar_ekrani(c):
    baslik("Ayarlar ekrani - tema, arayuz boyutu, laboratuvar varsayilanlari")
    # NOBETCI (2026-11-01). Olculenler: koyu temanin renkleri beyaz zeminde okunmuyordu
    # (turkuaz 1,86:1, amber 1,67:1; gereken 4,5:1), stil kurallarinda ~30 sabit renk temaya
    # bagli degildi; genom her degistiginde gelismis parametreler fabrika degerine donuyordu
    # (GRCh37'ye gecince Mg 2 -> 1,5, DMSO 5 -> 0); veri / genom / lisans ana ekranin
    # altindaydi. Davranis gercek arayuzde CDP ile ayrica denendi (kontrast, tasma, kalicilik).
    import colorsys
    import re
    kok = os.path.join(BURASI, "..", "electron")
    oku = lambda ad: open(os.path.join(kok, ad), encoding="utf-8").read()
    css, app, html, i18n = (oku("renderer/style.css"), oku("renderer/app.js"),
                            oku("renderer/index.html"), oku("renderer/i18n.js"))
    main_js, preload = oku("main.js"), oku("preload.js")
    govde = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    i = govde.find(":root {")
    koyu_blok = govde[i:govde.find("}", i) + 1]
    j = govde.find("@media (prefers-color-scheme: light)")
    acik_blok = govde[j:govde.find("}", govde.find(":root {", j)) + 1] if j >= 0 else ""
    blok = lambda b: {k: v.strip() for k, v in re.findall(r"--([\w-]+):\s*([^;]+);", b)}
    koyu, acik = blok(koyu_blok), blok(acik_blok)
    renkli = {k for k, v in koyu.items() if re.match(r"#|rgba?\(|\d+,\s*\d+,\s*\d+$", v)}
    ok("acik tema var: koyu temadaki her renk degiskeni acik temada da tanimli",
       bool(acik) and renkli <= set(acik) and "color-scheme: light" in acik_blok
       and "color-scheme: dark" in koyu_blok, ", ".join(sorted(renkli - set(acik))[:5]) or "acik blok yok")

    def rgb(v):
        return (tuple(int(v[k:k + 2], 16) for k in (1, 3, 5)) if v.startswith("#")
                else tuple(int(float(x)) for x in v.split(",")[:3]))

    def lum(cc):
        f = lambda x: x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
        r, g, b = (f(x / 255) for x in cc)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def oran(a, b):
        x, y = sorted((lum(a), lum(b)), reverse=True)
        return (x + 0.05) / (y + 0.05)

    karistir = lambda ust, alfa, alt: tuple(alfa * u + (1 - alfa) * a for u, a in zip(ust, alt))
    # Renkli ton kurallari: ayni kuralda yazi rengi var(--X), zemin rgba(var(--Y-rgb), a).
    # app.js'in satir ici stilleri de (j-flag) ayni sekilde.
    kurallar = re.findall(r"\{([^{}]*)\}", govde.replace(koyu_blok, "").replace(acik_blok, ""))
    kurallar += re.findall(r'style="([^"]+)"', app)
    tonlar = []
    for g in kurallar:
        yazi = re.search(r"(?:^|[;\s])color:\s*var\(--([\w-]+)\)", g)
        zemin = re.search(r"background(?:-color)?:\s*rgba\(var\(--([\w-]+)-rgb\),\s*([\d.]+)\)", g)
        if yazi and zemin:
            tonlar.append((yazi.group(1), zemin.group(1), float(zemin.group(2))))
    ok("  ...renkli ton kurallari bulundu (cip, rozet, karar cubugu, amplikon)", len(tonlar) >= 12, f"{len(tonlar)} kural")
    for ad, tok in (("koyu", koyu), ("acik", {**koyu, **acik})):
        zeminler = {z: rgb(tok[z]) for z in ("bg", "panel", "panel-2")}
        dusuk = [f"{y}/{z} {oran(rgb(tok[y]), zz):.2f}" for y in ("text", "muted", "accent", "good", "warn", "danger", "kontrol")
                 for z, zz in zeminler.items() if oran(rgb(tok[y]), zz) < 4.5]
        ok(f"  ...{ad}: yazi renkleri bg / panel / panel-2 uzerinde en az 4,5:1", not dusuk, "; ".join(dusuk[:3]))
        dolgu = [oran(rgb(tok["on-accent"]), rgb(tok[z])) for z in ("accent", "accent-2")] if "on-accent" in tok else [0]
        ok(f"  ...{ad}: vurgu dolgusundaki yazi (secili dugme, Primer Tasarla) en az 4,5:1",
           min(dolgu) >= 4.5, f"{min(dolgu):.2f}")
        kenar = min(oran(rgb(tok["input-border"]), zeminler[z]) for z in ("panel", "panel-2"))
        ok(f"  ...{ad}: giris kutusu kenarligi en az 3:1", kenar >= 3, f"{kenar:.2f}")
        ton_dusuk = []
        for y, z, a in tonlar:
            if f"{z}-rgb" not in tok or y not in tok:
                ton_dusuk.append(f"{y}/{z}-rgb tanimsiz")
                continue
            for zz in ("panel", "panel-2"):
                o = oran(rgb(tok[y]), karistir(rgb(tok[f"{z}-rgb"]), a, zeminler[zz]))
                if o < 4.5:
                    ton_dusuk.append(f"{y} / {z} %{a * 100:.0f} ({zz}) {o:.2f}")
        ok(f"  ...{ad}: renkli tonlarin uzerindeki yazi en az 4,5:1", not ton_dusuk, "; ".join(ton_dusuk[:3]))
        ton = lambda h: colorsys.rgb_to_hls(*(x / 255 for x in rgb(h)))[0] * 360
        fark = abs(ton(tok["accent"]) - ton(tok["good"]))
        ok(f"  ...{ad}: marka rengi ile 'iyi' yesili en az 25 derece ayri", fark >= 25, f"{fark:.0f} derece")
    kalan = govde.replace(koyu_blok, "").replace(acik_blok, "")
    sabit = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d[^)]*\)", kalan)
    ok("stil kurallarinda sabit renk yok (hepsi tema degiskeninden)", not sabit, " ".join(sabit[:4]))
    kod = "\n".join(x for x in app.splitlines() if not x.lstrip().startswith("//"))
    satir_ici = re.findall(r"rgba?\(\s*\d[^)]*\)|#[0-9a-fA-F]{6}\b", kod)
    ok("  ...app.js satir ici stillerinde de sabit renk yok", not satir_ici, " ".join(satir_ici[:3]))

    # Tema ve boyut main.js'te: nativeTheme (CSS sorgusu ve onay ekrani buna uyar), sayfa zoom'u
    liste = lambda ad, metin: re.findall(r'"([^"]+)"|([\d.]+)', (re.search(ad + r"\s*=\s*\[([^\]]*)\]", metin) or [None, ""])[1])
    duz = lambda l: [a or b for a, b in l]
    temalar, boyutlar = duz(liste("TEMALAR", main_js)), duz(liste("BOYUTLAR", main_js))
    seg = lambda ad: re.findall(r'data-deger="([^"]+)"', html[html.find(f'data-ayar="{ad}"'):html.find("</div>", html.find(f'data-ayar="{ad}"'))])
    ok("tema secenekleri main.js ile ayni (koyu / acik / Windows'a uy)",
       temalar == ["dark", "light", "system"] and seg("tema") == temalar, f"{temalar} / {seg('tema')}")
    ok("arayuz boyutlari main.js ile ayni (%90-%150)",
       [float(x) for x in boyutlar] == [0.9, 1, 1.1, 1.25, 1.5] and [float(x) for x in seg("boyut")] == [float(x) for x in boyutlar],
       f"{boyutlar} / {seg('boyut')}")
    ok("tema acilista pencereden once uygulanir, pencere zemini temaya uyar",
       "nativeTheme.themeSource = kayitliTema()" in main_js
       and main_js.find("nativeTheme.themeSource = kayitliTema()") < main_js.find("createWindow();", main_js.find("app.whenReady()"))
       and "backgroundColor: pencereZemini()" in main_js
       and f'"{koyu.get("bg")}" : "{acik.get("bg")}"' in main_js, "pencereZemini koyu/acik bg ile ayni olmali")
    ok("arayuz boyutu her sayfada (bildirim ekrani dahil) ve degisince uygulanir",
       "zoomFactor: kayitliBoyut()" in main_js and main_js.count("setZoomFactor(") >= 2)
    kopru = ("setTheme", "set-theme"), ("setZoom", "set-zoom"), ("setDefaultAssembly", "set-default-assembly"), \
        ("setLabDefaults", "set-lab-defaults")
    ok("tercih kopruleri (preload) ve isleyicileri (main.js) eslesir",
       all(f"{a}:" in preload and f'"{b}"' in preload and f'ipcMain.handle("{b}"' in main_js for a, b in kopru))
    ok("tercihler bildirim kaydinda: bildirim yeniden gosterilince silinmez",
       "const y = { ...s };" in main_js and "noticeKaydi(readSettings()" in main_js
       and all(f"{k}:" in main_js for k in ("theme", "zoom", "assembly", "lab")))

    # Laboratuvar varsayilanlari
    param = re.findall(r'"(\w+)"', (re.search(r"const PARAM_IDS = \[([^\]]*)\]", app) or [None, ""])[1])
    lab = re.findall(r'"(\w+)"', (re.search(r"const LAB_PARAMETRELERI = \[([^\]]*)\]", main_js) or [None, ""])[1])
    ok("main.js'in sakladigi parametreler = app.js PARAM_IDS (pcr_max haric)",
       bool(lab) and sorted(lab) == sorted(p for p in param if p != "pcr_max"), f"{len(lab)} / {len(param)}")
    saglik = app[app.find("async function loadHealth"):app.find("function updateGenomeStatus")]
    dolgu_yeri = saglik.find("for (const id of PARAM_IDS)")
    ok("genom degisince gelismis parametreler sifirlanmaz (yalnizca ilk yanitta doldurulur)",
       0 <= saglik.find("if (!PARAMS_DOLDU)") < dolgu_yeri and "PARAMS_DOLDU = true" in saglik
       and "LAB_KAYIT[id]" in saglik)
    ok("  ...kayit yalnizca fabrika degerinden farkli olanlari tutar, sifirlama alanlari da dondurur",
       "Number(v) !== Number(HEALTH.defaults[id])" in app and "setLabDefaults({})" in app)

    # Ekran: tasinan bolumler, alt bilgi, mesajlar, dar alan, ceviriler
    bas, son = html.find('<section id="ayarlarEkrani"'), html.find('<div class="tabs">')
    ok("veri / genom / lisans Ayarlar ekraninda, ana ekranda degil",
       0 <= bas < son and all(bas < html.find(x) < son for x in ('id="dlPanel"', 'data-i18n="gp.summary"', 'id="licensePanel"'))
       and 'id="ayarPanel"' not in html and 'id="ayarAc"' in html)
    tr, en = i18n.split(chr(10) + "  en: {", 1)
    deger = lambda metin, k: metin[metin.find(f'"{k}":'):metin.find('",', metin.find(f'"{k}":'))]
    ok("alt bilgi lisansin yerini dogru soyler ve oraya goturur (TR / EN)",
       "ayar-git" in deger(tr, "app.notice") and "Ayarlar" in deger(tr, "app.notice")
       and "yukarıdaki" not in deger(tr, "app.notice") and "Settings" in deger(en, "app.notice")
       and "panel above" not in deger(en, "app.notice") and 'closest("a.ayar-git")' in app)
    ok("Ayarlar acikken mesajlar (genom secimi, indirme) Ayarlar'da gorunur",
       '$("ayarMsg") : $("msg")' in app and 'id="ayarMsg"' in html)
    ok("Esc Ayarlar'i kapatir", '"Escape"' in app and "ayarlariKapat()" in app)
    ok("dar alanda (900 px alti) ust cubuk sarar, tablolar kartin icinde kayar",
       re.search(r"@media \(max-width: 900px\) \{[^@]*\.topbar \{ flex-wrap: wrap;[^@]*table\.primer-table, table\.spec-table "
                 r"\{ display: block; max-width: 100%; overflow-x: auto; \}", govde) is not None)
    anahtar = set(re.findall(r'data-i18n(?:-ph|-title)?="([^"]+)"', html)) | set(re.findall(r't\("((?:set|about)\.[\w.]+)"', app))
    eksik = [k for k in sorted(anahtar) if f'"{k}":' not in tr or f'"{k}":' not in en]
    ok("Ayarlar metinleri iki dilde de var", not eksik and any(k.startswith("set.") for k in anahtar), ", ".join(eksik[:5]))


def test_oto_rozet_durumu(c):
    baslik("Otomatik ozgulluk rozeti - durdurulan tarama 'sirada' birakmaz")
    # NOBETCI (2026-11-01, kurulu 0.8.24 / 0.8.25'te olculdu): DNA taramasi surerken kirilma
    # noktasi tasarimi yapilinca 10 kartin hepsinde, tarama sirasinda "Ozgullugu otomatik
    # kontrol et" kapatilinca taranmamis 8 kartta hic bitmeyen "Ozgulluk: sirada" rozeti
    # kaliyordu (dil degisince ve 15 sn sonra da). Sebep: durdurulan taramanin denetcisi
    # OTO_IPTAL'de kaliyor, yeniden cizim "sirada"yi lastResult'a gore koyuyordu. Davranis
    # gercek arayuzde CDP ile ayrica denendi (tarama/betikler/rozet_sirada.mjs, rozet_kapat.mjs).
    app = open(os.path.join(BURASI, "..", "electron", "renderer", "app.js"), encoding="utf-8").read()
    kod = "\n".join(x for x in app.splitlines() if not x.lstrip().startswith("//"))
    i = kod.find("function otoDurdur")
    durdur = kod[i:kod.find("async function otoOzgulluk")] if i >= 0 else ""
    ok("durdurma denetciyi ve taramanin sonucunu temizler, bekleme rozetini kaldirir",
       bool(durdur) and "OTO_IPTAL = null" in durdur and "OTO_SONUC = null" in durdur
       and "SPEC_RESULTS[p.rank]" in durdur and ".remove()" in durdur)
    ok("taramayi durduran her yer otoDurdur'u kullanir (dogrudan abort kalmadi)",
       bool(durdur) and "OTO_IPTAL.abort()" not in kod.replace(durdur, "") and kod.count("otoDurdur();") >= 3)
    ok("yeniden cizim 'sirada'yi yalnizca taramanin kendi sonucuna koyar",
       "OTO_IPTAL && OTO_SONUC === j" in kod and "OTO_IPTAL && lastResult === j" not in kod)
    oto = kod[kod.find("async function otoOzgulluk"):kod.find("function rozetYaz")]
    ok("  ...tarama baslarken sonuc baglanir, bitince temizlenir",
       "OTO_SONUC = j" in oto and "OTO_SONUC = null" in oto)


def test_gen_yonu_gorunum(c):
    baslik("F/R adlari genin yonunde - gorunum (yon.js) ve metinler")
    # NOBETCI (2026-11-01, kullanici sorusu: eksi iplikteki genlerde "forward" Sanger'da
    # uyumsuzluk yaratir mi?). DNA / kirilma noktasi ciftleri genomun + ipligine gore
    # adlandiriliyordu: TP53'te forward primerle yapilan okuma c. dizisinin ters
    # tumleyeniydi (c.215C, chr17:7676154'te + iplikte G) ve tasarlanan cift Degerlendir'e
    # verilince "roller yer degismis" deniyordu. Gorunum yon.js'te cevrilir.
    import subprocess
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    oku = lambda ad: open(os.path.join(kok, ad), encoding="utf-8").read()
    html, app, i18n = oku("index.html"), oku("app.js"), oku("i18n.js")
    ok("yon.js app.js'ten once yuklenir",
       0 <= html.find('<script src="yon.js">') < html.find('<script src="app.js">'))
    kod = "\n".join(x for x in app.splitlines() if not x.lstrip().startswith("//"))
    yerler = {ad: kod[kod.find(f"function {ad}"):kod.find("\n}", kod.find(f"function {ad}"))]
              for ad in ("renderPair", "renderBpPair", "toggleAmplicon", "pairToEvaluate",
                         "specGovdesi", "exportCsv", "exportBpCsv")}
    eksik = [ad for ad, govde in yerler.items() if "genYonunde(" not in govde]
    ok("kart, urun dizisi, Degerlendir dugmesi, ozgulluk, CSV ayni gorunumu kullanir", not eksik, ", ".join(eksik))
    ok("  ...sonuclarin ustunde yon notu, ozette genin ipligi",
       "yonNotu(j)" in kod and 'p0.gene_strand === "-"' in kod)
    tr, en = i18n.split(chr(10) + "  en: {", 1)
    ok("yon notu ve kontrol primeri metinleri iki dilde (kontrol metni gosterilen adi alir)",
       all(f'"{k}"' in m for k in ("yon.eksi", "yon.belirsiz", "amp.geneDir") for m in (tr, en))
       and all(f'"{k}": (' in m for k in ("bp.chip.control.title", "bp.controlSpecHint") for m in (tr, en))
       and all('"bp.controlDimer": (s, ad)' in m for m in (tr, en)))
    # NOBETCI (2026-11-14, v0.8.62): kontrol primeri obur uctan R ile de bant verebilir.
    # Kart eskiden esi her zaman F, dimer uyarisinin ucuncu primerini her zaman R sayiyordu.
    bp_kart = yerler["renderBpPair"]
    ok("  ...kartta kontrolun esi pairs_with'ten; dimer uyarisi tupteki ucuncu primere bakar",
       'k.pairs_with === "reverse"' in bp_kart and 't("bp.chip.control.title", esAd)' in bp_kart
       and 't("bp.controlSpecHint", esAd)' in bp_kart
       and 't("bp.controlDimer", digerDimer, digerAd)' in bp_kart
       and "kR ? k.dimer_with_f : k.dimer_with_r" in bp_kart)
    # Kullanici (2026-11-01): "onceki surumlerde boyleydi gibi bir nota gerek yok, henuz
    # kimseyle paylasmadim" - not ve KURULUM.txt surum gecmisinden soz etmez
    deger = lambda metin, k: metin[metin.find(f'"{k}":'):metin.find('",', metin.find(f'"{k}":'))]
    kurulum = open(os.path.join(BURASI, "..", "KURULUM.txt"), encoding="utf-8").read()
    ok("  ...yon notu ve KURULUM.txt surum gecmisinden soz etmez",
       not any(s in deger(tr, "yon.eksi") for s in ("sürüm", "0.8."))
       and not any(s in deger(en, "yon.eksi") for s in ("Versions before", "0.8."))
       and "önceki sürümler" not in kurulum)
    # Bos sonuc aciklamasi: DNA / kirilma noktasinda koordinat tarafi, digerlerinde F/R
    import engine as engine_mod

    def aciklama(mod):
        s = {"num_returned": 0, "mode": mod, "params_used": {},
             "explain": {"left": "considered 300, GC content failed 300, ok 0",
                         "right": "considered 300, ok 50", "pair": "considered 0, ok 0"}}
        return " ".join(engine_mod.explain_notu(s).get("notes") or [])
    ok("bos sonuc aciklamasi DNA / kirilma noktasinda koordinat tarafini soyler",
       "Küçük koordinat tarafında" in aciklama(None) and "Küçük koordinat tarafında" in aciklama("breakpoint")
       and "Forward tarafında" in aciklama("cdna"), aciklama(None)[:60])
    node = shutil.which("node")
    if not node:
        return atla("yon.js davranisi", "node yok")
    betik = ("const y = require(" + json.dumps(os.path.abspath(os.path.join(kok, "yon.js"))) + ");"
             "const a = {sequence: 'AAAACCCCGGn', forward_span: [0, 3], reverse_span: [8, 10],"
             " junction_offsets: [5], unknown_span: null, gc_percent: 50};"
             "const p = {forward: {sequence: 'F'}, reverse: {sequence: 'R'}, amplicon: a};"
             "const e = y.genYonunde(Object.assign({}, p, {gene_strand: '-'}));"
             "console.log(JSON.stringify({tt: y.tersTumleyen('ACGTNacgt'), a: y.amplikonTers(a),"
             " f: e.forward.sequence, r: e.reverse.sequence, ea: e.amplicon.sequence,"
             " arti: ['+', '?', undefined].map((g) => y.genYonunde(Object.assign({}, p, {gene_strand: g})).forward.sequence)}));")
    r = subprocess.run([node, "-e", betik], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return ok("yon.js node ile yuklenir", False, r.stderr.strip()[:120])
    d = json.loads(r.stdout)
    ok("ters tumleyen (N ve kucuk harf korunur)", d["tt"] == "acgtNACGT", d["tt"])
    ok("urun dizisi aynalanir: F/R araliklari yer degistirir, kirilma isareti n-k",
       d["a"]["sequence"] == "nCCGGGGTTTT" and d["a"]["forward_span"] == [0, 2]
       and d["a"]["reverse_span"] == [7, 10] and d["a"]["junction_offsets"] == [6]
       and d["a"]["unknown_span"] is None and d["a"]["gc_percent"] == 50, json.dumps(d["a"]))
    ok("eksi iplikte F/R yer degistirir, urun dizisi cevrilir; +, ? ve gen yoksa ayni kalir",
       d["f"] == "R" and d["r"] == "F" and d["ea"] == "nCCGGGGTTTT" and d["arti"] == ["F", "F", "F"], json.dumps(d))


def test_favoriler(c):
    baslik("Favoriler: yerel liste (electron/favoriler.js), kart dugmesi, Favoriler ekrani (v0.8.63)")
    # NOBETCI (2026-11-14, kullanici istegi "Favorilere ekle gibi bi sey"; prototip onayi "Uygula").
    # Liste YALNIZ bu bilgisayarda (userData\favoriler.json). Dosya islevleri node ile gercek diskte
    # sinanir; arayuz baglantilari kaynak metinden. Bozuk dosyanin ustune YAZILMAZ (yedeklenir).
    import subprocess
    kok = os.path.join(BURASI, "..")
    oku = lambda *ad: open(os.path.join(kok, *ad), encoding="utf-8").read()
    main_js, preload, app, i18n = (oku("electron", "main.js"), oku("electron", "preload.js"),
                                   oku("electron", "renderer", "app.js"), oku("electron", "renderer", "i18n.js"))
    html, paket, kurulum = (oku("electron", "renderer", "index.html"), oku("electron", "package.json"),
                            oku("kurulu-guncelle.ps1"))
    ok("main.js favoriler.js'i yukler ve 4 ucu baglar (listele, ekle, sil, not)",
       'require("./favoriler")' in main_js
       and all(f'ipcMain.handle("fav-{u}"' in main_js for u in ("list", "add", "remove", "note"))
       and 'path.join(app.getPath("userData"), "favoriler.json")' in main_js)
    ok("  ...preload dort islevi verir", all(f"{a}: " in preload for a in ("favList", "favAdd", "favRemove", "favNote")))
    ok("  ...favoriler.js kurulu-guncelle listesinde ve paket dosyalarinda (yoksa kurulu uygulama acilmaz)",
       'k = "electron\\favoriler.js"' in kurulum and '"favoriler.js"' in paket)
    ok("  ...ust cubukta dugme + sayac, Favoriler ekrani (arama, CSV, liste)",
       all(f'id="{i}"' in html for i in ("favAc", "favSayac", "favEkrani", "favAra", "favCsv", "favListe", "favGeri")))
    kod = "\n".join(x for x in app.splitlines() if not x.lstrip().startswith("//"))
    spec = kod[kod.find("const specFooter"):kod.find("</div>`;", kod.find("const specFooter"))]
    ok("  ...dugme butun tasarim kartlarinin ortak altliginda ve iki Degerlendir sonucunda",
       "favDugmesi(" in spec and kod.count("favDugmesi('data-ev=\"1\"', \"fav-ev\")") == 2)
    ok("  ...kirilma noktasi kaydi Degerlendir'e gonderilmez; genomik kayit kendi derlemesiyle acilir",
       'k.tur === "kirilma" ? ""' in kod and 'if (!k || k.tur === "kirilma") return;' in kod
       and "k.derleme !== ASSEMBLY" in kod)
    # "fav.err." + hata ve "fav.kind." + tur birlesik yazilir: onekler degil, uretilen anahtarlar sayilir
    kullanilan = {k for k in re.findall(r'"(fav\.[\w.]+)"', kod) if not k.endswith(".")} | {
        "fav.kind." + x for x in ("dna", "cdna", "atlama", "dizi", "dizi_cift", "degerlendir_dna",
                                  "degerlendir_cdna")} | {
        "fav.err." + x for x in ("gecersiz", "yazilamadi", "okunamadi", "bozuk", "sinir", "yok")}
    tr, en = i18n.split(chr(10) + "  en: {", 1)
    eksik = sorted(k for k in kullanilan if f'"{k}":' not in tr or f'"{k}":' not in en)
    ok("  ...kullanilan her fav.* metni iki dilde", not eksik, ", ".join(eksik))
    ok("  ...not alaninda hasta adi uyarisi iki dilde",
       "Hasta adı ya da kimliği yazmayın" in tr and "Do not write patient names or IDs" in en)
    node = shutil.which("node")
    if not node:
        return atla("favoriler.js davranisi", "node yok")
    mod = os.path.abspath(os.path.join(kok, "electron", "favoriler.js"))
    anahtar_app = re.search(r"const favAnahtar = \(k\) => ([^;]+);", app)
    with tempfile.TemporaryDirectory() as tmp:
        dosya = os.path.join(tmp, "AllPrime", "favoriler.json")
        betik = (f"const F = require({json.dumps(mod)}); const fs = require('fs'); const path = require('path');"
                 f"const dosya = {json.dumps(dosya)}; const appAnahtar = (k) => "
                 + (anahtar_app.group(1) if anahtar_app else "null") + r""";
const o = {};
const kayit = (ek) => Object.assign({tur: "dna", derleme: "GRCh38", gen: "TP53", girdi: {chrom: "17", position: 7676154, zararli: "x"},
  urun: {boy: 330, ta: 52.5, bilinmeyen: 1}, surum: "0.8.63", not: "  Sanger\ndogrulamasi\t ",
  primerler: [{rol: "reverse", dizi: "GGTAGGTTTTCTGGGAAGGG", uzunluk: 20, tm: 57.5, gc: 55, konum: {tur: "genomik", bas: 7676059, bit: 7676078}},
              {rol: "forward", dizi: "cgttctggtaaggacaaggg", uzunluk: 20, tm: 57.9, gc: 55, konum: {tur: "genomik", bas: 7676369, bit: 7676388}}],
  fazla: "<script>"}, ek);
o.bos = F.liste(dosya);
const e1 = F.ekle(dosya, kayit());
const k1 = e1.kayit;
o.e1 = {ok: e1.ok, n: e1.kayitlar.length, roller: k1.primerler.map((p) => p.rol), girdi: k1.girdi, urun: k1.urun,
        not: k1.not, fazla: "fazla" in k1, id: /^[A-Za-z0-9-]{6,40}$/.test(k1.id), tarih: !isNaN(Date.parse(k1.tarih))};
const e2 = F.ekle(dosya, kayit({not: "baska not"}));
o.e2 = {ok: e2.ok, zatenVar: !!e2.zatenVar, n: e2.kayitlar.length};
o.gecersiz = [kayit({tur: "xyz"}), kayit({primerler: [{rol: "reverse", dizi: "ACGTACGTAC"}]}),
              kayit({primerler: [{rol: "forward", dizi: "ACGT1ACGT"}]}), null, "metin"].map((k) => F.ekle(dosya, k).hata);
const e3 = F.ekle(dosya, kayit({tur: "kirilma", derleme: "GRCh37", primerler: [
  {rol: "forward", dizi: "AATAGGAGTGGTGAGAGAGG"}, {rol: "reverse", dizi: "AGACAAGCACATTCCAAGTC"},
  {rol: "control", dizi: "TCAGGCCAATATCCCTGATG", es: "forward"}]}));
o.e3 = {ok: e3.ok, n: e3.kayitlar.length, ilk: e3.kayitlar[0].tur, kontrolEs: e3.kayit.primerler[2].es};
o.anahtar = {ayni: appAnahtar ? F.anahtar(e3.kayit) === appAnahtar(e3.kayit) : null, deger: F.anahtar(k1)};
const n1 = F.notYaz(dosya, k1.id, "yeni not ".repeat(100));
o.not = {ok: n1.ok, uzunluk: n1.kayit.not.length, diskte: F.liste(dosya).kayitlar.find((k) => k.id === k1.id).not.length};
o.notYok = F.notYaz(dosya, "yok-yok-yok", "x").hata;
const s1 = F.sil(dosya, k1.id);
o.sil = {ok: s1.ok, n: s1.kayitlar.length, diskte: F.liste(dosya).kayitlar.length};
o.tmp = fs.readdirSync(path.dirname(dosya)).filter((a) => a.endsWith(".tmp")).length;
// BOM'lu dosya okunur
fs.writeFileSync(dosya, "﻿" + fs.readFileSync(dosya, "utf8"), "utf8");
o.bom = F.liste(dosya).kayitlar.length;
// bozuk dosya: liste hata verir, ekleme once yedekler (icerik aynen), sonra yeni dosya
fs.writeFileSync(dosya, '{"bicim": 1, "kayitlar": [ {"tur": "dna"', "utf8");
o.bozukListe = F.liste(dosya).hata;
o.bozukSil = F.sil(dosya, "abcdef").hata;
const e4 = F.ekle(dosya, kayit());
const yedekler = fs.readdirSync(path.dirname(dosya)).filter((a) => a.startsWith("favoriler.bozuk-"));
o.bozuk = {ok: e4.ok, yedek: !!e4.yedek, yedekSayisi: yedekler.length,
           yedekIcerik: yedekler.length ? fs.readFileSync(path.join(path.dirname(dosya), yedekler[0]), "utf8") : null,
           yeniGecerli: F.liste(dosya).kayitlar.length};
// sinir: EN_COK kayitta yeni kayit reddedilir, dosya degismez
const dolu = Array.from({length: F.EN_COK}, () => ({tur: "dizi", primerler: [{rol: "forward", dizi: "ACGTACGTACGTACGTACGT"}]}));
fs.writeFileSync(dosya, JSON.stringify({bicim: 1, kayitlar: dolu}), "utf8");
const once = fs.readFileSync(dosya, "utf8");
o.sinir = {hata: F.ekle(dosya, kayit()).hata, degismedi: fs.readFileSync(dosya, "utf8") === once, n: F.liste(dosya).kayitlar.length};
console.log(JSON.stringify(o));
""")
        r = subprocess.run([node, "-e", betik], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return ok("favoriler.js node ile calisir", False, r.stderr.strip()[-300:])
        d = json.loads(r.stdout)
    ok("bos klasorde liste bos, hata yok", d["bos"] == {"ok": True, "kayitlar": [], "hata": None}, json.dumps(d["bos"]))
    e1 = d["e1"]
    ok("ekleme: primerler forward/reverse sirasinda, bilinmeyen alan atilir, not tek satir ve kirpilmis",
       e1["ok"] and e1["n"] == 1 and e1["roller"] == ["forward", "reverse"] and not e1["fazla"]
       and e1["girdi"] == {"chrom": "17", "position": 7676154} and e1["urun"] == {"boy": 330, "ta": 52.5}
       and e1["not"] == "Sanger dogrulamasi" and e1["id"] and e1["tarih"], json.dumps(e1))
    ok("  ...ayni cift ikinci kez eklenmez (not farkli olsa da)",
       d["e2"] == {"ok": True, "zatenVar": True, "n": 1}, json.dumps(d["e2"]))
    ok("  ...gecersiz kayit reddedilir (tur, forward yok, dizide rakam, bos, metin)",
       d["gecersiz"] == ["gecersiz"] * 5, json.dumps(d["gecersiz"]))
    ok("  ...kontrol primerli kirilma kaydi en uste, esi korunur",
       d["e3"] == {"ok": True, "n": 2, "ilk": "kirilma", "kontrolEs": "forward"}, json.dumps(d["e3"]))
    ok("  ...app.js'teki favAnahtar favoriler.js anahtar() ile ayni sonucu verir (kart durumu)",
       d["anahtar"]["ayni"] is True and d["anahtar"]["deger"].startswith("dna|GRCh38|forward:CGTTCTGG"),
       json.dumps(d["anahtar"]))
    # Kesim bosluga denk gelirse kirpilir; kayit ile diskten okunan AYNI olmali (eskiden 500 / 499)
    ok("  ...not 500 karakterle sinirli, diskten okunanla ayni; olmayan kayit 'yok'",
       d["not"]["ok"] and d["not"]["uzunluk"] == d["not"]["diskte"] and 490 <= d["not"]["uzunluk"] <= 500
       and d["notYok"] == "yok", json.dumps(d["not"]))
    ok("  ...silme diske yazilir; .tmp kalmaz; BOM'lu dosya okunur",
       d["sil"] == {"ok": True, "n": 1, "diskte": 1} and d["tmp"] == 0 and d["bom"] == 1,
       f"{d['sil']} tmp {d['tmp']} bom {d['bom']}")
    bz = d["bozuk"]
    ok("bozuk dosya: liste hata verir, silme yazmaz; yeni kayit once bozugu AYNEN yedekler",
       d["bozukListe"] == "bozuk" and d["bozukSil"] == "bozuk" and bz["ok"] and bz["yedek"]
       and bz["yedekSayisi"] == 1 and bz["yedekIcerik"] == '{"bicim": 1, "kayitlar": [ {"tur": "dna"'
       and bz["yeniGecerli"] == 1, json.dumps(bz)[:200])
    ok("  ...sinirda yeni kayit reddedilir, eski kayitlar silinmez",
       d["sinir"]["hata"] == "sinir" and d["sinir"]["degismedi"] and d["sinir"]["n"] == 2000, json.dumps(d["sinir"]))


def _node_calistir(betik):
    """Gecici .js dosyasini node ile calistirir: (json sonuc, hata metni)."""
    import subprocess
    dosya = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    try:
        dosya.write(betik)
        dosya.close()
        r = subprocess.run([shutil.which("node"), dosya.name], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
    finally:
        os.unlink(dosya.name)
    if r.returncode != 0:
        return None, r.stderr.strip()[:300]
    return json.loads(r.stdout), ""


def test_v100_sayfa_sureci_cokerse():
    """NOBETCI (v1.0.0): acilislarin bir bolumunde sayfa sureci (renderer) cokuyor, pencere bos
    kaliyordu (olcum: 80 acilista 9; render-process-gone reason=crashed, cikis kodu 0x80000003).
    main.js sayfayi yeniden yukler. Gercek deneme ayri bir betikle yapildi (paketli uygulama,
    yeni ve kalici profil); burada kodun yerinde durdugu denetlenir."""
    baslik("Sayfa sureci cokerse sayfa yeniden yuklenir (v1.0.0)")
    mj = open(os.path.join(BURASI, "..", "electron", "main.js"), encoding="utf-8").read()
    i = mj.find("function createWindow(")
    govde = _yorumsuz_js(mj[i:mj.find("\n}", i)]) if i >= 0 else ""
    j = govde.find('.on("render-process-gone"')
    isleyici = govde[j:govde.find("});", govde.find("setTimeout", j)) if j >= 0 else 0] if j >= 0 else ""
    ok("main.js: pencere render-process-gone olayini dinliyor", bool(isleyici))
    ok("cokuste sayfa adiyla yukleniyor (loadFile(acilisSayfasi())); reload() degil",
       "loadFile(acilisSayfasi())" in isleyici and ".reload(" not in isleyici)
    ok("yeniden yukleme sinirli (en cok 3) ve olagan kapanista (clean-exit) yok",
       ">= 3" in isleyici and '"clean-exit"' in isleyici and "isDestroyed()" in isleyici)
    ok("acilis sayfasi tek yerde: bildirim gorulduyse index.html, yoksa consent.html",
       mj.count("function acilisSayfasi()") == 1 and govde.count("acilisSayfasi()") == 2
       and 'noticeSeen() ? "index.html" : "consent.html"' in mj)


def test_v0866_favori_csv_ve_degerlendir(c):
    baslik("Favoriler CSV'sinde konum iki sutun; Degerlendir'de ayni cift 'Favorilerde' (v0.8.66)")
    # NOBETCI (2026-11-17, denetim 2 madde 2 ve 4).
    # (2) Favoriler CSV'si konumu tek hucrede "bas-bit" yaziyordu; dizi / cDNA kayitlarinda "5-24" Excel'de
    #     tarihe donuyordu. Artik oteki CSV'ler gibi iki sayi sutunu (csv.posStart / csv.posEnd).
    # (4) Favorilerden "Degerlendir'de ac" ile acilan cift Degerlendir'de "Favorilere ekle" gosteriyor ve
    #     ikinci kez ("Degerlendir - DNA") eklenebiliyordu: kayit turu farkli, anahtar tutmuyordu. Degerlendir
    #     kaydi icin ayni derlemede ayni Forward + Reverse dizisini tasiyan kayit (turu ne olursa olsun)
    #     bulunur; anahtar (favAnahtar = favoriler.js anahtar()) degismez, tasarim kartlari etkilenmez.
    kok = os.path.join(BURASI, "..")
    oku = lambda *ad: open(os.path.join(kok, *ad), encoding="utf-8").read()
    app, i18n, readme = oku("electron", "renderer", "app.js"), oku("electron", "renderer", "i18n.js"), oku("GELISTIRME.md")
    tr, en = i18n.split(chr(10) + "  en: {", 1)
    say = lambda m: len(re.findall(r'^    "([^"]+)":', m, re.M))
    ok("konum sutun adlari iki dilde var, kullanilmayan csv.favPos kalkti",
       all(f'"csv.{k}":' in m for k in ("posStart", "posEnd") for m in (tr, en))
       and '"csv.favPos"' not in i18n and '"favPos"' not in app)
    m = re.search(r"(\d+)'er anahtar", readme)
    ok("  ...README'deki anahtar sayisi iki dildeki sayiyla ayni", bool(m) and int(m.group(1)) == say(tr) == say(en),
       f"-> README {m and m.group(1)}, TR {say(tr)}, EN {say(en)}")
    if not shutil.which("node"):
        return atla("Favoriler CSV / Degerlendir davranisi", "node yok")
    i = app.find("function favCsvIndir(")
    csv_fn = app[i:app.find("\n}", i) + 2] if i >= 0 else ""
    bul = app[app.find("const favAnahtar"):app.find("const favSayi")]
    d, hata = _node_calistir((r"""
var FAVORILER = [];
const t = (k) => k;
const H = (...keys) => keys.map((k) => t("csv." + k));
const CSV = { satir: (a) => a };
let cikti = null;
const downloadCsv = (rows) => { cikti = rows; };
const favTurAdi = (k) => k.tur, favGirdiMetni = () => "", favUrunMetni = () => "";
""" + bul + "\n" + csv_fn + r"""
const r = {};
const F = "CGTTCTGGTAAGGACAAGGG", R = "GGTAGGTTTTCTGGGAAGGG";
const pr = (rol, dizi, konum) => ({ rol, dizi, uzunluk: 20, tm: 58, gc: 55, konum });
const dna = { id: "a1", tur: "dna", derleme: "GRCh38", tarih: "2026-11-17T10:00:00Z", primerler: [
  pr("forward", F, { tur: "genomik", bas: 7676369, bit: 7676388 }), pr("reverse", R, { tur: "genomik", bas: 7676078, bit: 7676059 })] };
const dizi = { id: "d1", tur: "dizi", derleme: "", tarih: "2026-11-17T10:00:00Z", primerler: [
  pr("forward", F, { tur: "dizi", bas: 5, bit: 24 }), pr("reverse", R, { tur: "dizi", bas: 330, bit: 311 })] };
const ev = (ek) => Object.assign({ tur: "degerlendir_dna", derleme: "GRCh38",
  primerler: [{ rol: "forward", dizi: F.toLowerCase() }, { rol: "reverse", dizi: R }] }, ek);
const degr = Object.assign(ev({ id: "e1", tarih: "2026-11-17T10:00:00Z" }), { primerler: [pr("forward", F), pr("reverse", R)] });
FAVORILER = [dizi, dna, degr];
favCsvIndir();
const bas = cikti[0];
const s = (n, ad) => cikti[n][bas.indexOf(ad)];
r.csv = { bas, uzunluklar: cikti.map((x) => x.length),
  dizi: [s(1, "csv.posStart"), s(1, "csv.posEnd")], genomik: [s(3, "csv.posStart"), s(3, "csv.posEnd")],
  konumsuz: [s(5, "csv.posStart"), s(5, "csv.posEnd")] };
FAVORILER = [dizi, dna];
const id = (k) => (favBul(k) || {}).id || null;
r.bul = { ev: id(ev()), ev37: id(ev({ derleme: "GRCh37" })), evR: id(ev({ primerler: [{ rol: "forward", dizi: F }, { rol: "reverse", dizi: F }] })),
  evTek: id(ev({ primerler: [{ rol: "forward", dizi: F }] })), evTers: id(ev({ primerler: [{ rol: "forward", dizi: R }, { rol: "reverse", dizi: F }] })),
  cdna: id(ev({ tur: "degerlendir_cdna" })), tasarimKarti: id(ev({ tur: "cdna" })), dnaKendisi: id(dna) };
FAVORILER = [dna, degr];
r.bul.tam = id(ev());
console.log(JSON.stringify(r));
""") if bul and csv_fn else "process.exit(3)")
    if d is None:
        return ok("favCsvIndir / favBul node ile calisir", False, hata or "islev bulunamadi")
    b = d["csv"]["bas"]
    ok("CSV basliginda Konum_Baslangic / Konum_Bitis yan yana; tek 'Konum' sutunu yok",
       "csv.posStart" in b and "csv.posEnd" in b and b.index("csv.posEnd") == b.index("csv.posStart") + 1
       and "csv.favPos" not in b and set(d["csv"]["uzunluklar"]) == {len(b)}, json.dumps(b))
    ok("  ...dizi kaydinda kucuk sayilar ayri sayi hucresi (5 / 24; eskiden '5-24' -> Excel'de tarih)",
       d["csv"]["dizi"] == [5, 24], json.dumps(d["csv"]["dizi"]))
    ok("  ...genomik kayitta koordinatlar ayni; konumsuz Degerlendir kaydinda iki bos hucre",
       d["csv"]["genomik"] == [7676369, 7676388] and d["csv"]["konumsuz"] == ["", ""],
       json.dumps([d["csv"]["genomik"], d["csv"]["konumsuz"]]))
    x = d["bul"]
    ok("Degerlendir: ayni derlemede ayni F + R (buyuk/kucuk harf farksiz) tasarim kaydi bulunur",
       x["ev"] == "a1" and x["cdna"] == "a1", json.dumps(x))
    ok("  ...baska derleme, baska R, tek primer ya da F/R yer degismisse bulunmaz",
       x["ev37"] is None and x["evR"] is None and x["evTek"] is None and x["evTers"] is None, json.dumps(x))
    ok("  ...tasarim kartlari eskisi gibi yalniz anahtarla; tam eslesen kayit once gelir",
       x["tasarimKarti"] is None and x["dnaKendisi"] == "a1" and x["tam"] == "e1", json.dumps(x))


def test_v0866_binlik(c, engine, genom_var, annot_var):
    baslik("Turkce motor mesajlarinda binlik ayirici nokta, Ingilizcede virgul (v0.8.66)")
    # NOBETCI (2026-11-17, denetim 2 madde 3). Turkce notlar
    # "1,671 bp'lik", "(1,992–2,113 bp)", "11,344 bp" yaziyordu; ayni ekrandaki kartlar "2.101 bp".
    # Turkce yarilar lang.tr_sayi ile noktali; Ingilizce yarilar aynen (v0866_binlik.py: 61 x 2 cagri,
    # EN birebir ayni, TR binlik normalize edilince ayni).
    import random
    binlik = re.compile(r"\d,\d{3}(?!\d)")
    nokta = re.compile(r"\d\.\d{3}(?!\d)")

    def iki(yol, govde):
        return {d: c.post(yol, json=dict(govde, lang=d)).get_json() or {} for d in ("tr", "en")}
    rr = random.Random(3)
    dizi = "".join(rr.choice("ACGT") for _ in range(52_000))
    y = iki("/design_sequence", {"sequence": dizi})
    a, b = y["tr"].get("error", ""), y["en"].get("error", "")
    ok("hedefsiz uzun dizi: TR '50.000 bp'lik ... 52.000 bp', EN '50,000 ... 52,000 bp'",
       "50.000 bp'lik" in a and "52.000 bp" in a and not binlik.search(a) and "50,000 bp" in b and "52,000 bp" in b,
       f"-> {a[:80]!r} / {b[:70]!r}")
    y = iki("/design_sequence_pair", {"forward": dizi[:220], "reverse": dizi[380:600], "params": {"gap": 25000}})
    a, b = y["tr"].get("error", ""), y["en"].get("error", "")
    ok("  ...iki dizi arasi mesafe hatasi: TR (25.000 bp) sinir 20.000, EN (25,000 bp) 20,000",
       "(25.000 bp)" in a and "20.000 bp" in a and "(25,000 bp)" in b and "20,000 bp" in b, f"-> {a[:70]!r}")
    if not HTTP:
        from lang import set_lang
        import transcripts as trx
        rows = [{"acc": "NM_000001.1", "chrom": "1", "tx_start": 1234567, "tx_end": 1240000},
                {"acc": "NM_000001.1", "chrom": "5", "tx_start": 7654321, "tx_end": 7660000}]
        try:
            set_lang("tr")
            a = trx._lokus_notu(rows, rows[0], "uzun", "GRCh38") or ""
            set_lang("en")
            b = trx._lokus_notu(rows, rows[0], "uzun", "GRCh38") or ""
        finally:
            set_lang("tr")
        ok("  ...transkript lokus notu: TR 1:1.234.567-1.240.000 / 5:7.654.321, EN virgullu",
           "1:1.234.567-1.240.000" in a and "5:7.654.321-7.660.000" in a and not binlik.search(a)
           and "1:1,234,567-1,240,000" in b and "5:7,654,321-7,660,000" in b, f"-> {a[:90]!r}")
    if not (genom_var and engine.GENOME_PATHS.get("GRCh38")):
        return atla("Binlik ayirici (genomlu)", "GRCh38 genomu yok")
    y = iki("/design_breakpoint", {"assembly": "GRCh38", "chrom": "1", "start": 109_609_703, "end": 109_611_373,
                                   "type": "del", "params": {"bp_margin": 200, "control_primer": True}})
    a = " ".join(y["tr"].get("notes") or []) + " " + " ".join(
        p.get("control_reason") or "" for p in y["tr"].get("pairs") or [])
    b = " ".join(y["en"].get("notes") or [])
    ayni = [p["forward"]["sequence"] for p in y["tr"].get("pairs") or []] == \
        [p["forward"]["sequence"] for p in y["en"].get("pairs") or []]
    ok("Kirilma noktasi (GNAT2 del, pay 200, kontrol): TR '1.671 bp'lik', virgullu binlik yok; EN '1,671 bp'",
       "1.671 bp'lik" in a and not binlik.search(a) and "1,671 bp" in b and ayni and bool(y["tr"].get("pairs")),
       f"-> {binlik.findall(a)[:3]} {a[:100]!r}")
    if not annot_var:
        return atla("Binlik ayirici (Degerlendir cDNA)", "transkript tablosu yok")
    d = c.post("/design_cdna", json={"assembly": "GRCh38", "acc": "NM_000546", "c_position": "c.215"}).get_json() or {}
    p = (d.get("pairs") or [None])[0]
    if not p:
        return ok("Degerlendir cDNA: TP53 c.215 cifti", False, str(d.get("error"))[:120])
    y = iki("/evaluate_cdna", {"forward": p["forward"]["sequence"], "reverse": p["reverse"]["sequence"],
                               "acc": "NM_000546", "assembly": "GRCh38"})
    a = " ".join(f.get("text", "") for f in y["tr"].get("findings") or [])
    b = " ".join(f.get("text", "") for f in y["en"].get("findings") or [])
    ok("Degerlendir cDNA (TP53 c.215): TR genomik bant noktali (11.3xx bp), EN virgullu",
       bool(nokta.search(a)) and not binlik.search(a) and bool(binlik.search(b)),
       f"-> TR {nokta.findall(a)} {binlik.findall(a)} EN {binlik.findall(b)}")


def test_igv_konum(c):
    baslik("Kartlarda IGV konumu: primerlerin araligi + 'IGV icin kopyala' (v0.8.65)")
    # NOBETCI (2026-11-14, kullanici istegi: "primerlerin bulundugu koordinatlarin araligi da yazsin, IGV'den
    # bulmak kolay olsun"). Kartin Pozisyon sutunu Turkce bicimde (117.559.410–117.559.715); IGV noktali
    # ve uzun tireli bicimi okumuyor. Kirilma noktasi ve RNA kartlarinda konum hic yoktu.
    import subprocess
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    app = open(os.path.join(kok, "app.js"), encoding="utf-8").read()
    i18n = open(os.path.join(kok, "i18n.js"), encoding="utf-8").read()
    kod = "\n".join(x for x in app.splitlines() if not x.lstrip().startswith("//"))

    def govde(ad):
        i = kod.find(f"function {ad}(")
        return kod[i:kod.find("\n}", i)] if i >= 0 else ""
    ok("DNA, RNA (varyant, ekson atlama), Kirilma noktasi kartlarinda ve Favoriler kaydinda konum cipi",
       "konumCipi(i.chrom, p.amplicon_genomic_start" in govde("renderPair")
       and "rnaKonumCipi(p, j)" in govde("renderCdnaPair") and govde("renderSkipPair").count("rnaKonumCipi(p, j)") == 2
       and "primerAraligi(p.forward, p.reverse, k)" in govde("renderBpPair") and "konumCipi(" in govde("favKayitHtml"))
    ok("  ...kartlar j ile cizilir (kromozom ve derleme sonuctan)",
       "((p) => renderPair(p, j))" in kod and "((p) => renderCdnaPair(p, j))" in kod and "((p) => renderSkipPair(p, j))" in kod)
    tr, en = i18n.split(chr(10) + "  en: {", 1)
    ok("  ...metinler iki dilde", all(f'"{k}":' in m for k in ("igv.copy", "igv.copy.title") for m in (tr, en)))
    node = shutil.which("node")
    if not node:
        return atla("IGV konumu davranisi", "node yok")
    fn = "".join(govde(a) + "\n}\n" for a in ("igvKonum", "konumCipi", "primerAraligi"))
    yardim = (re.search(r"^const yerel = .*$", app, re.M).group(0) + "\n"
              + re.search(r"^const esc = .*\n.*$", app, re.M).group(0) + "\n")
    betik = (i18n + "\n" + yardim + fn + r"""
const r = {};
LANG = "tr";
r.igv = [igvKonum("7", 117559410, 117559715), igvKonum("chr7", 1, 5), igvKonum("MT", 10, 20), igvKonum("X", 5, 9)];
r.tr = konumCipi("7", 117559715, 117559410, "GRCh38");
r.tr37 = konumCipi("12", 121763332, 121766536, "GRCh37");
r.bos = [konumCipi(null, 1, 2, "GRCh38"), konumCipi("7", null, 2, "GRCh38"), konumCipi("", 1, 2, "GRCh38")];
r.aralik = [primerAraligi({genomic_start: 100, genomic_end: 119}, {genomic_start: 400, genomic_end: 381}, {genomic_start: 250, genomic_end: 269}),
            primerAraligi({genomic_start: null, genomic_end: null}), primerAraligi(null, undefined)];
LANG = "en";
r.en = konumCipi("7", 117559410, 117559715, "GRCh38");
console.log(JSON.stringify(r));
""")
    dosya = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    try:
        dosya.write(betik)
        dosya.close()
        r = subprocess.run([node, dosya.name], capture_output=True, text=True, encoding="utf-8", timeout=60)
    finally:
        os.unlink(dosya.name)
    if r.returncode != 0:
        return ok("IGV konumu islevleri node ile calisir", False, r.stderr.strip()[:200])
    d = json.loads(r.stdout)
    ok("IGV bicimi: chr ekli, ayiricisiz, duz tire; 'chr' tekrarlanmaz; MT -> chrM",
       d["igv"] == ["chr7:117559410-117559715", "chr7:1-5", "chrM:10-20", "chrX:5-9"], json.dumps(d["igv"]))
    ok("  ...kartta okunur bicim (chr7:117.559.410–117.559.715), kopyada IGV bicimi; ters sira duzelir",
       'data-seq="chr7:117559410-117559715"' in d["tr"] and "chr7:117.559.410–117.559.715" in d["tr"]
       and "IGV için kopyala" in d["tr"], d["tr"][:200])
    ok("  ...ipucu dogru genomu soyler (GRCh38 -> hg38, GRCh37 -> hg19)",
       "GRCh38 (hg38)" in d["tr"] and "GRCh37 (hg19)" in d["tr37"])
    ok("  ...kromozom ya da koordinat yoksa cip cizilmez", d["bos"] == ["", "", ""])
    ok("  ...aralik F, R ve kontrolu kapsar (ters iplik dahil); konum yoksa null",
       d["aralik"] == [[100, 400], None, None], json.dumps(d["aralik"]))
    ok("  ...Ingilizce: 'Copy for IGV', binlik virgul",
       "Copy for IGV" in d["en"] and "chr7:117,559,410–117,559,715" in d["en"], d["en"][:160])


def test_degerlendir_urun_yonu(c):
    baslik("Degerlendir urun dizisi F'den baslar, lejant uclardaki primeri adlandirir")
    # NOBETCI (2026-11-03 tarama, kurulu 0.8.29'da olculdu). Degerlendir urun dizisini genomun
    # + ipliginde (cDNA'da transkriptin yonunde) gosteriyor, lejant her zaman "Forward primer /
    # Reverse primer" diyordu. TP53 kartinin cifti (R+F urun): kullanicinin R'si GGTAGGTTTT...
    # "Forward primer" diye isaretliydi, ayni ekrandaki tablo "R 0 / F 0" diyordu, kart urunu
    # F'den (CGTTCT...) baslatiyordu. F/R'si ters girilmis cDNA ciftinde ve F+F / R+R yan
    # urunlerinde de lejant yanlisti.
    import subprocess
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    oku = lambda ad: open(os.path.join(kok, ad), encoding="utf-8").read()
    app, i18n = oku("app.js"), oku("i18n.js")
    kod = "\n".join(x for x in app.splitlines() if not x.lstrip().startswith("//"))
    bas = kod.find("function toggleEvalAmplicon")
    govde = kod[bas:kod.find("\n}", bas)] if bas >= 0 else ""
    ok("urun gorunumu uclardaki primere gore cizilir (DNA: urunun kaydi, cDNA: roller yer degismis mi)",
       "degerlendirmeUrunu(" in govde and "kaynak.forward_primer" in govde
       and "kaynak.reverse_primer" in govde and 'j.roles_swapped ? "R" : "F"' in govde)
    ok("  ...lejant uctaki primerin adini alir, cevrilen urunde not ve FASTA basligi",
       'u.sol === "F" ? "amp.fwd" : "amp.rev.self"' in govde and 'u.sag === "R" ? "amp.rev" : "amp.fwd.rc"' in govde
       and 'note: u.ters ? t("amp.fromF")' in govde and 'u.ters ? `>${ad} ${t("amp.fromF")}' in govde)
    ok("  ...renderAmplicon lejanti ve notu secenekten alir (vermeyen yerler eskisi gibi)",
       "opts.fwdLabel || t(\"amp.fwd\")" in kod and "opts.revLabel || t(\"amp.rev\")" in kod and "opts.note ?" in kod)
    tr, en = i18n.split(chr(10) + "  en: {", 1)
    ok("yeni lejant ve not metinleri iki dilde",
       all(f'"{k}"' in m for k in ("amp.fwd.rc", "amp.rev.self", "amp.fromF") for m in (tr, en)))
    node = shutil.which("node")
    if not node:
        return atla("degerlendirmeUrunu davranisi", "node yok")
    betik = ("const y = require(" + json.dumps(os.path.abspath(os.path.join(kok, "yon.js"))) + ");"
             "const a = {sequence: 'AAAACCCCGG', forward_span: [0, 3], reverse_span: [7, 9], gc_percent: 50};"
             "const o = {};"
             "for (const [s, g] of [['F', 'R'], ['R', 'F'], ['F', 'F'], ['R', 'R']]) {"
             " const u = y.degerlendirmeUrunu(a, s, g);"
             " o[s + '+' + g] = {d: u.amplicon.sequence, f: u.amplicon.forward_span, r: u.amplicon.reverse_span,"
             " sol: u.sol, sag: u.sag, ters: u.ters, ayni: u.amplicon === a}; }"
             "console.log(JSON.stringify(o));")
    r = subprocess.run([node, "-e", betik], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return ok("degerlendirmeUrunu yon.js'te", False, next((x for x in r.stderr.splitlines() if "Error" in x), "")[:120])
    d = json.loads(r.stdout)
    ok("R+F urun ters cevrilir: F'den baslar, isaretler aynalanir, uclar F / R",
       d["R+F"] == {"d": "CCGGGGTTTT", "f": [0, 2], "r": [6, 9], "sol": "F", "sag": "R", "ters": True, "ayni": False},
       json.dumps(d["R+F"]))
    ok("  ...F+R aynen kalir; F+F ve R+R cevrilmez, uclar kendi adini korur",
       d["F+R"]["ayni"] and not d["F+R"]["ters"] and (d["F+R"]["sol"], d["F+R"]["sag"]) == ("F", "R")
       and d["F+F"]["ayni"] and (d["F+F"]["sol"], d["F+F"]["sag"]) == ("F", "F")
       and d["R+R"]["ayni"] and (d["R+R"]["sol"], d["R+R"]["sag"]) == ("R", "R"), json.dumps(d))


def test_menu_kisayollari(c):
    baslik("Varsayilan menu yok; Ctrl + / - / 0 Ayarlar'daki boyut adimlarini kullanir")
    # NOBETCI (2026-11-03 tarama, kurulu 0.8.29'da olculdu). Electron'un varsayilan menusu gizliyken
    # de kisayollari calisiyordu: Ctrl+R sayfayi yenileyip sonuclari siliyordu; Ctrl + / -
    # yakinlastirmasi Ayarlar'a yansimiyor, kaydedilmiyor ve Ayarlar'in %90 alt sinirini
    # asiyordu (uc basista %83); Ctrl+Shift+I gelistirici araclarini, F11 tam ekrani aciyordu.
    import re
    import subprocess
    kok = os.path.join(BURASI, "..", "electron")
    oku = lambda ad: open(os.path.join(kok, ad), encoding="utf-8").read()
    main_js, preload, app = oku("main.js"), oku("preload.js"), oku("renderer/app.js")
    yorumsuz = lambda m: "\n".join(x for x in m.splitlines() if not x.lstrip().startswith("//"))
    kod, kapp = yorumsuz(main_js), yorumsuz(app)
    hazir = kod.find("app.whenReady()")
    ok("varsayilan menu acilista, pencereden once kaldirilir",
       hazir >= 0 and 0 <= kod.find("Menu.setApplicationMenu(null)", hazir) < kod.find("createWindow();", hazir))
    ok("  ...kisayol pencerenin klavye olayindan Ayarlar'in kayit yoluna gider",
       'webContents.on("before-input-event"' in kod and "kisayolBoyutu(input)" in kod
       and "e.preventDefault();" in kod and "return boyutUygula(v);" in kod)
    bas = kod.find("function boyutUygula")
    govde = kod[bas:kod.find("\n}", bas)] if bas >= 0 else ""
    ok("  ...boyut kaydedilir, uygulanir ve sayfaya bildirilir",
       all(k in govde for k in ("writeSettings(s)", "setZoomFactor(v)", 'send("zoom-changed", v)')))
    ok("  ...sayfa bildirimi dinler: secili boyut ve Ayarlar cizimi guncellenir",
       'onZoomChanged: (cb) => ipcRenderer.on("zoom-changed"' in preload
       and re.search(r"onZoomChanged\(\(v\) => \{ BOYUT = v; ayarlariCiz\(\); \}\)", kapp) is not None)
    node = shutil.which("node")
    if not node:
        return atla("kisayol adimlari", "node yok")
    # kisayolBoyutu main.js'ten cikarilip electron'suz calistirilir (BOYUTLAR ve kayit taklidiyle)
    fbas = main_js.find("function kisayolBoyutu")
    liste = re.search(r"const BOYUTLAR = \[[^\]]*\];", main_js)
    if fbas < 0 or not liste:
        return ok("kisayolBoyutu main.js'te", False)
    betik = (liste.group(0) + "let kayit = 1; const kayitliBoyut = () => kayit;"
             + main_js[fbas:main_js.find("\n}\n", fbas) + 2]
             + "const t = (key, o = {}) => kisayolBoyutu(Object.assign({type: 'keyDown', key, control: true,"
               " alt: false, meta: false, shift: false}, o));"
               "const s = [];"
               "for (const [k, b] of [['+', 1], ['=', 1], ['-', 1], ['0', 1.25], ['+', 1.5], ['-', 0.9]]) { kayit = b; s.push(t(k)); }"
               "kayit = 1;"
               "s.push(t('+', {control: false}), t('+', {alt: true}), t('+', {meta: true}), t('+', {type: 'keyUp'}),"
               " t('r'), t('I', {shift: true}));"
               "console.log(JSON.stringify(s));")
    r = subprocess.run([node, "-e", betik], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return ok("kisayolBoyutu node ile calisir", False, r.stderr.strip()[:120])
    d = json.loads(r.stdout)
    ok("kisayol adimlari: + ve = buyutur, - kucultur, 0 -> %100, uclarda (%90 / %150) durur",
       d[:6] == [1.1, 1.1, 0.9, 1, 1.5, 0.9], json.dumps(d[:6]))
    ok("  ...Ctrl'siz, AltGr (Ctrl+Alt), Windows tusu, tus birakma, Ctrl+R ve Ctrl+Shift+I boyut degistirmez",
       d[6:] == [None] * 6, json.dumps(d[6:]))


def test_cok_tarama(c):
    baslik("Tek gecis cok primer taramasi = check_pair (v0.8.36)")
    # NOBETCI (2026-11-09): kurallara uyan butun adaylar tek geciste taranir (cok_tarama.py). Sonuc
    # specificity.check_pair ile BIREBIR ayni olmali: olculdu 204/204 + 16.659 cift (esdeger_kanit.py,
    # rapor-en-iyi-cift.md). PAR ikizi (SHOX), tekrar dizisi siniri ((CA)n, poli-A) ve urun siniri
    # (Alu+Alu) dahil. Tek gecis isabetleri check_pair'e isabet= ile verilir; geri kalan ayni koddur.
    if isinstance(c, _HttpIstemci):
        atla("Tek gecis = check_pair", "motor ayri surecte (uc noktasi test_kopya_ciftleri'nde)")
        return
    import engine
    import specificity as S
    try:
        import cok_tarama
    except ImportError as e:
        ok("cok_tarama modulu yuklenir", False, str(e))
        return
    yol = engine.GENOME_PATHS.get("GRCh38", "")
    ciftler = []
    for kr, konum in (("17", 7676154), ("X", 640000), ("6", 32040495)):
        d = engine.design_primers("GRCh38", kr, konum, params={})
        for p in d["pairs"][:4]:
            ciftler.append((p["forward"]["sequence"], p["reverse"]["sequence"],
                            {"chrom": engine.normalize_chrom(kr), "start": p["amplicon_genomic_start"],
                             "end": p["amplicon_genomic_end"]}))
    ciftler += [("CACACACACACACACACACA", "CCTCCCAGAGACCCCAGTTG", None),
                ("GGCTCACGCCTGTAATCCCA", "TGGGATTACAGGCGTGAGCC", None),
                ("AAAAAAAAAAAAAAAAAAAA", "TGAGGTGCGTGTTTGTGCCT", None)]
    T = cok_tarama.Tarama(yol, {x[0] for x in ciftler} | {x[1] for x in ciftler})

    def cagir(f, r, e, isabet):
        try:
            return S.check_pair(yol, f, r, expected=e, params={}, assembly="GRCh38", isabet=isabet)
        except S.SpecificityError as x:
            return ("hata", str(x))
    ayni = karar = ikiz = hata = 0
    for f, r, e in ciftler:
        g = cagir(f, r, e, None)
        ayni += g == cagir(f, r, e, T.isabetler)
        h = T.risk(f, r, e, "GRCh38")
        if isinstance(g, tuple):
            hata += 1
            karar += bool(h.get("hata"))
        else:
            ikiz += g["par_twins"] > 0
            rc = g["risk_counts"]
            karar += (not h.get("hata") and h["specific"] == g["specific"] and h["yuksek"] == rc["yuksek"]
                      and h["orta"] == rc["orta"] and h["dusuk"] == rc["dusuk"])
            karar += -1 if T.risk(f, r, e, "GRCh38", sadece_karar=True)["specific"] != g["specific"] else 0
    n = len(ciftler)
    ok(f"Tek gecis isabetleriyle check_pair birebir ayni ({n} cift: TP53, SHOX/PAR1, CYP21A2, tekrar)",
       ayni == n, f"{ayni}/{n}")
    ok("  ...hizli risk sayimi ve erken durma karari da ayni", karar == n, f"{karar}/{n}")
    ok("  ...PAR ikizi ve tekrar hatasi vakalari icinde", ikiz >= 1 and hata >= 2, f"ikiz {ikiz}, hata {hata}")


def test_kopya_ciftleri(c):
    baslik("En iyi Ozgul cift / kopyadan ayrisan ciftler (v0.8.36: butun adaylar)")
    # NOBETCI (2026-11-06, kullanici istegi): "psodogeni olan genlere primer tasarlarken ozdeslige dikkat
    # etsin; normal primer tasarimini etkilememeli". v0.8.36 (kullanici karari 2026-11-09, rapor-en-iyi-cift):
    # kurallara uyan BUTUN adaylar taranir, deneme siniri yok; "en iyi" = once Ozgul, sonra bugunku skor;
    # liste ve sirasi degismez. Asagidaki degerler olcumden (en_iyi_olcum.py, e1_veri.py), GRCh38 (SORD GRCh37).
    import re
    import threading
    import time
    js = lambda r: r.get_json(silent=True) or {}
    cift = lambda p: (p["forward"]["sequence"], p["reverse"]["sequence"])
    liste = lambda d: [cift(p) for p in d.get("pairs") or []]

    normal = {"assembly": "GRCh38", "chrom": "17", "position": 7676154, "gene": "TP53"}
    d = js(c.post("/design", json=normal))
    ok("Normal gende kopya isareti yok (TP53)", len(liste(d)) == 10 and "paralog_var" not in d)
    if isinstance(c, _HttpIstemci):
        atla("Havuz istegi tasarim sonucunu degistirmez", "motor ayri surecte")
    else:
        import engine
        havuz = {}
        try:
            ayni = (engine.design_primers("GRCh38", "17", 7676154, gene="TP53", params={}, havuz=havuz)
                    == engine.design_primers("GRCh38", "17", 7676154, gene="TP53", params={}))
        except TypeError:
            ayni = False
        ok("Havuz istegi tasarim sonucunu degistirmez", ayni and len(havuz.get("sira") or []) > 10
           and "seq_args" in havuz and "global_args" in havuz)
    s = js(c.post("/kopya_ciftleri", json=normal))
    ok("TP53: 1. cift en iyisi; kutu acilmaz (sessiz)", s.get("durum") == "bir" and s.get("pairs") == []
       and (s.get("taranan") or 0) > 10000 and s.get("tam") is True, f"{s.get('durum')} {s.get('taranan')}")
    ok("  ...normal liste degismedi", liste(js(c.post("/design", json=normal))) == liste(d))

    hedef = {"assembly": "GRCh38", "chrom": "6", "position": 32040495}
    ilk = js(c.post("/design", json=hedef))
    ok("Kopyali gende isaret var (CYP21A2)", ilk.get("paralog_var") is True)
    r = c.post("/kopya_ciftleri", json=hedef)
    s = js(r)
    ps = s.get("pairs") or []
    ok("CYP21A2: ilk 8 Ozgul cift, durum 'disari'", r.status_code == 200 and len(ps) == 8
       and s.get("durum") == "disari" and s.get("taranan") == 5217, f"{s.get('durum')} {len(ps)} cift")
    ok("  ...ilki olcumdeki en iyi cift: sira 17, 434 bp", bool(ps) and ps[0].get("havuz_sira") == 17
       and ps[0]["product_size"] == 434 and cift(ps[0]) == ("GACTCCACCCGATCATTCCC", "AGCCTCCACCACATTTTCAC"))
    ok("  ...hicbiri normal listede degil, sirasi listeden sonra",
       all((p.get("havuz_sira") or 99) > 10 and cift(p) not in liste(ilk) for p in ps))
    ok("  ...hedef konum her urunun icinde, urun 700 bp sinirinda", all(
        p["forward"]["genomic_end"] < 32040495 < p["reverse"]["genomic_start"] and p["product_size"] <= 700
        for p in ps))
    for p in ps[:3]:
        v = js(c.post("/specificity", json={
            "assembly": "GRCh38", "forward": p["forward"]["sequence"], "reverse": p["reverse"]["sequence"],
            "expected": {"chrom": "6", "start": p["forward"]["genomic_start"], "end": p["reverse"]["genomic_end"]}}))
        ok(f"  ...sira {p.get('havuz_sira')} ayri taramada Ozgul, hedef urun bulundu",
           v.get("specific") is True and v.get("intended_found") is True)
    # Kopyadan fark (v0.8.35): olcumle ayni (kopya_fark.py, 2026-11-08). 8 ciftin hepsinde Forward
    # CYP21A1P'ye de tam oturur; ayrismayi Reverse'un 3' son ya da sondan ikinci bazi saglar.
    fark = [[(f["primer"], f["uctan"]) for f in (x.get("kopya") or {}).get("fark", [])] for x in ps]
    ok("  ...kopyadan fark: Reverse'un 3' son (6 cift) ve sondan ikinci (2 cift) bazi",
       fark == [[("reverse", 1)]] * 6 + [[("reverse", 2)]] * 2, str(fark))
    ok("  ...fark CYP21A1P'de (chr6:32.007.6xx)", bool(ps) and all(
        (x.get("kopya") or {}).get("chrom") == "6" and 32007600 < x["kopya"]["start"] < 32007700 for x in ps))
    ok("  ...1. cifte gore fark: dimer +1,4, urun 29 bp kisa", bool(ps) and ps[0].get("fark") ==
       {"ceza": 0.0, "dimer": 1.4, "boy": -29, "skor": 0.251}, str(ps and ps[0].get("fark")))
    ok("Arama normal listeyi degistirmez", liste(js(c.post("/design", json=hedef))) == liste(ilk) != [])

    s = js(c.post("/kopya_ciftleri", json={"assembly": "GRCh37", "chrom": "15", "position": 45361216}))
    ps = s.get("pairs") or []
    ok("SORD (GRCh37): eski 12 denemenin bulamadigi en iyi cift, sira 105", s.get("durum") == "disari"
       and bool(ps) and ps[0].get("havuz_sira") == 105 and ps[0]["product_size"] == 612
       and cift(ps[0]) == ("CTACCCGATTGTCCAAAGCC", "GAGATAGCGCCTGTAATCCC") and len(ps) == 8
       and s.get("taranan") == 19084, f"{s.get('durum')} {ps and ps[0].get('havuz_sira')}")
    ok("  ...1. cift Ozgul degil (1 yuksek riskli yan urun)", s.get("bir") == {"ozgul": False, "yuksek": 1,
       "orta": 0, "hata": None}, str(s.get("bir")))
    s = js(c.post("/kopya_ciftleri", json={"assembly": "GRCh38", "chrom": "17", "position": 7240904}))
    ps = s.get("pairs") or []
    ok("GABARAP: 1. cift Ozgul ama havuz disinda daha iyi Ozgul cift ('k2'), urun 271 bp kisa",
       s.get("durum") == "k2" and bool(ps) and ps[0].get("havuz_sira") is None and ps[0]["product_size"] == 242
       and (ps[0].get("fark") or {}).get("boy") == -271 and ((ps[0].get("fark") or {}).get("skor") or 0) < 0, f"{s.get('durum')}")
    s = js(c.post("/kopya_ciftleri", json={"assembly": "GRCh38", "chrom": "11", "position": 57560432}))
    ps = s.get("pairs") or []
    ok("UBE2L6: en iyi Ozgul cift listede 3. sirada ('ilk10')", s.get("durum") == "ilk10" and bool(ps)
       and ps[0].get("havuz_sira") == 3 and (s.get("bir") or {}).get("yuksek") == 5622, f"{s.get('durum')}")

    s = js(c.post("/kopya_ciftleri", json={"assembly": "GRCh38", "chrom": "5", "position": 70941448}))
    ad = s.get("aday") if isinstance(s.get("aday"), list) else []
    ok("SMN1'de cift uydurulmaz: Ozgul yok, en az riskli 3 aday (1 yuksek, 0 orta)", s.get("durum") == "yok"
       and s.get("pairs") == [] and len(ad) == 3 and all(x.get("yuksek") == 1 and x.get("orta") == 0 for x in ad)
       and s.get("taranan") == 4533, f"{s.get('durum')} {len(ad)}")
    s = js(c.post("/kopya_ciftleri", json={"assembly": "GRCh38", "chrom": "16", "position": 2103580}))
    ps = s.get("pairs") or []
    ok("Eksi iplikteki genin ciftleri gen yonunu tasir (PKD1)",
       bool(ps) and all(p.get("gene_strand") == "-" for p in ps), f"{len(ps)} cift")
    s = js(c.post("/kopya_ciftleri", json={"assembly": "GRCh38", "chrom": "10", "position": 87965379}))
    ps = s.get("pairs") or []
    ok("Kopyada en cok 5 uyumsuzla urun vermeyen ciftler 'cok farkli' (PTEN, olculen 8 cift)",
       len(ps) == 8 and all("kopya" in x and x["kopya"] is None for x in ps), f"{len(ps)} cift")
    s = js(c.post("/kopya_ciftleri", json={"assembly": "GRCh38", "chrom": "16", "position": 177347}))
    ok("Listede 1. cift en iyiyse kutu acilmaz (HBA1)", s.get("durum") == "bir" and s.get("pairs") == [],
       str(s.get("durum")))

    sonuc = []
    is_ = threading.Thread(target=lambda: sonuc.append(js(c.post("/kopya_ciftleri", json=hedef))))
    is_.start()
    time.sleep(5)
    c.post("/kopya_durdur")
    is_.join(60)
    ok("Durdurulan arama yarida birakilir", bool(sonuc) and sonuc[0].get("iptal") is True)
    ok("Konumsuz istek reddedilir", c.post("/kopya_ciftleri", json={"assembly": "GRCh38"}).status_code == 400)
    ok("Bilinmeyen derleme reddedilir",
       c.post("/kopya_ciftleri", json={"assembly": "abc", "position": 1}).status_code == 400)

    kok = os.path.join(BURASI, "..", "electron", "renderer")
    oku = lambda ad: open(os.path.join(kok, ad), encoding="utf-8").read()
    app, i18n, css = oku("app.js"), oku("i18n.js"), oku("style.css")
    kod = "\n".join(x for x in app.splitlines() if not x.lstrip().startswith("//"))
    govde = lambda ad: kod[kod.find(f"function {ad}"):kod.find("\n}", kod.find(f"function {ad}"))]
    ok("Bolum yalnizca DNA sonucunda cizilir", '(j.mode ? "" : `<div id="kopyaBolum"></div>`)' in kod)
    ok("  ...arama DNA sonucunda baslar", "if (!j.mode) { kopyaHazirla(j); kopyaCiz(j); }"
       in govde("otoOzgulluk") and kod.count("kopyaHazirla(") == 2)
    ok("  ...rozetlerden sonra her zaman taranir (1. cift Ozgul olsa da)",
       'if (!j.mode && KOPYA && KOPYA.j === j && KOPYA.durum === "sirada") kopyaAra(j);' in govde("otoOzgulluk"))
    ok("  ...1. cift en iyiyse sessiz", 's.durum === "bir") return gizle();' in govde("kopyaCiz"))
    ok("  ...bolum kart sayilmaz", "pair-card" not in govde("kopyaCiz"))
    ok("  ...kopyadan fark sutunu, adi genin yonunde", "kopyaFarkHucre)" in govde("kopyaCiz")
       and 'p.gene_strand === "-"' in govde("kopyaFarkHucre"))
    ok("  ...motor ucu arayuzun bekledigi listede",
       '"/kopya_ciftleri"' in kod[kod.find("const GEREKLI_UCLAR"):kod.find("function motorUyumu")])
    ok("  ...yeni tasarim ya da kontrolu kapatmak aramayi durdurur", "kopyaDurdur();" in govde("otoDurdur"))
    ok("  ...dil degisince bolum yeniden cizilir", "kopyaCiz(j)" in govde("renderResults"))
    anahtar = set(re.findall(r't\("((?:kopya|eniyi)\.[\w.]+)"', kod)) | {"eniyi.sirada", "eniyi.araniyor"}
    ok("  ...metinler iki dilde", len(anahtar) > 20 and all(i18n.count(f'"{k}":') == 2 for k in anahtar),
       str(sorted(k for k in anahtar if i18n.count(f'"{k}":') != 2)))
    stil = css[css.find(".kopya-bolum"):css.find(".tablo-kaydir")]
    ok("  ...stil yalnizca tema renkleriyle", bool(stil) and not re.search(r"#[0-9a-fA-F]{3,6}\b", stil))


def test_oto_kontrol_sonradan(c):
    baslik("En iyi Ozgul cift: otomatik kontrol sonradan acilinca / arama surerken kapatilinca")
    # NOBETCI (2026-11-09, v0.8.36 hatasi): kontrol kapaliyken tasarlanan psodogensiz gende kutu
    # "gizli" kaliyordu; kontrol sonradan acilinca rozetler geliyor ama en iyi Ozgul cift aramasi
    # hic baslamiyordu (sessiz kutu "1. cift en iyisi" diye okunur). Arama surerken kontrol
    # kapatilinca da psodogensiz gende "Bu gende yakin kopya var" dugmesi cikiyordu.
    # Durum gecisleri app.js'teki fonksiyonlarin kendisiyle node'da denenir.
    import subprocess
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    with open(os.path.join(kok, "app.js"), encoding="utf-8") as f:
        kod = "\n".join(x for x in f.read().splitlines() if not x.lstrip().startswith("//"))

    def fonk(ad):
        i = kod.find(f"function {ad}(")
        return kod[i:kod.find("\n}", i)] + "\n}\n" if i >= 0 else ""

    ok("Yapilmayan / durdurulan arama tek kurala bagli (dogrudan \"dugme\" atamasi yok)",
       'durum = "dugme"' not in kod)
    node = shutil.which("node")
    if not node:
        return atla("Kopya durum gecisleri", "node yok")
    betik = ("let KOPYA = null, OTO = false;\n"
             "const HEALTH = { genomes: { GRCh38: 1 } }, ASSEMBLY = 'GRCh38';\n"
             "const $ = () => ({ checked: OTO }), kopyaCiz = () => {}, motor = () => Promise.resolve(), api = (x) => x;\n"
             + fonk("kopyaBeklet") + fonk("kopyaHazirla") + fonk("kopyaDurdur") +
             "const r = {};\n"
             "for (const [ad, p] of [['normal', false], ['psodogen', true]]) {\n"
             "  const j = { input: { assembly: 'GRCh38' }, pairs: [1], paralog_var: p };\n"
             "  OTO = false; kopyaHazirla(j); const kapali = KOPYA.durum;\n"
             "  OTO = true; kopyaHazirla(j); const acildi = KOPYA.durum;\n"
             "  KOPYA.durum = 'araniyor'; OTO = false; kopyaDurdur(); const durdu = KOPYA.durum;\n"
             "  OTO = true; kopyaHazirla(j); r[ad] = [kapali, acildi, durdu, KOPYA.durum];\n"
             "}\n"
             "console.log(JSON.stringify(r));\n")
    r = subprocess.run([node, "-e", betik], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return ok("Kopya durum gecisleri node ile calisir", False, r.stderr.strip()[:160])
    d = json.loads(r.stdout)
    ok("Psodogensiz gen: kontrol kapaliyken kutu gizli, sonradan acilinca arama siraya girer",
       d["normal"][:2] == ["gizli", "sirada"], str(d["normal"]))
    ok("  ...arama surerken kontrol kapatilinca kutu gizlenir (kopya dugmesi cikmaz), yeniden acilinca siraya girer",
       d["normal"][2:] == ["gizli", "sirada"], str(d["normal"]))
    ok("Psodogenli gen: kapaliyken dugme, acilinca sirada, durdurulunca yine dugme",
       d["psodogen"] == ["dugme", "sirada", "dugme", "sirada"], str(d["psodogen"]))


def test_yakin_not_metni(c):
    baslik("Degerlendir: 'kopyadan yalnizca 1-2 baz farki' notunun metni")
    # NOBETCI (2026-11-09, kullanici "Uygula, guzel olmus"; prototip cikti/ekran/kopya_not_proto): not urun
    # tablosunun altinda; metin motorun near_copy alanindan kurulur. evYakinNot app.js'ten alinip gercek
    # i18n.js ile node'da iki dilde denenir (CYP21A2 olculen veri, iki fark, F+F ve birden cok yer).
    import re
    import subprocess
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    app = open(os.path.join(kok, "app.js"), encoding="utf-8").read()
    i18n = open(os.path.join(kok, "i18n.js"), encoding="utf-8").read()
    kod = "\n".join(x for x in app.splitlines() if not x.lstrip().startswith("//"))
    i = kod.find("function evYakinNot(")
    ok("Not cizici var (evYakinNot)", i >= 0)
    if i < 0:
        return
    govde = kod[i:kod.find("\n}", i)] + "\n}\n"
    ok("  ...urun tablosunun hemen altinda; urun yoksa da cizilir",
       "</tbody></table>\n        ${evYakinNot(j)}" in app and '${t("ev.noProduct")}</p>${evYakinNot(j)}' in app)
    anahtar = set(re.findall(r't\("(ev\.yakin\.[\w.]+)"', govde))
    ok("  ...metinler iki dilde", len(anahtar) == 5 and all(i18n.count(f'"{k}":') == 2 for k in anahtar),
       str(sorted(anahtar)))
    node = shutil.which("node")
    if not node:
        return atla("Not metni", "node yok")
    yardim = (re.search(r"^const yerel = .*$", app, re.M).group(0) + "\n" +
              re.search(r"^const esc = [\s\S]*?\);$", app, re.M).group(0) + "\n")
    cyp = {"chrom": "6", "start": 31974969, "end": 31975482, "size": 514, "combination": "F+R",
           "genes": ["CYP21A1P"], "total": 1, "count": 1,
           "sites": [{"primer": "forward", "orientation": "+", "mismatches": []},
                     {"primer": "reverse", "orientation": "-",
                      "mismatches": [{"from_3p": 1, "primer_base": "G", "template_base": "T"}]}]}
    iki = dict(cyp, genes=[], total=2, sites=[cyp["sites"][0], {"primer": "reverse", "orientation": "-", "mismatches": [
        {"from_3p": 1, "primer_base": "G", "template_base": "T"}, {"from_3p": 4, "primer_base": "A", "template_base": "C"}]}])
    ff = dict(cyp, chrom="2", start=5000, end=5811, size=812, combination="F+F", genes=["ABC1"], count=3,
              sites=[cyp["sites"][0], {"primer": "forward", "orientation": "-", "mismatches": [
                  {"from_3p": 2, "primer_base": "C", "template_base": "A"}]}])
    betik = (i18n + "\n" + yardim + govde + "const v = " + json.dumps([cyp, iki, ff]) + ";\nconst r = {};\n"
             "for (const L of ['tr', 'en']) { LANG = L; r[L] = v.map((n) => evYakinNot({ near_copy: n })"
             ".replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim()); }\n"
             "r.yok = evYakinNot({ near_copy: null });\nconsole.log(JSON.stringify(r));\n")
    dosya = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    try:
        dosya.write(betik)
        dosya.close()
        r = subprocess.run([node, dosya.name], capture_output=True, text=True, encoding="utf-8", timeout=60)
    finally:
        os.unlink(dosya.name)
    if r.returncode != 0:
        return ok("Not metni node ile kurulur", False, r.stderr.strip()[:160])
    d = json.loads(r.stdout)
    tr_cyp, tr_iki, tr_ff = d["tr"]
    ok("CYP21A2 (olculen veri): onaylanan metin",
       tr_cyp.startswith("Kopyadan yalnızca tek baz farkı var — temkinli olun")
       and "CYP21A1P bölgesinde (chr6:31.974.969–31.975.482, 514 bp) bu çiftten ürün oluşabilir: F kopyaya "
           "birebir oturuyor, R yalnız 3' son bazında farklı (primerin G'si karşısında T)." in tr_cyp
       and "Tek bazlık fark zayıf bir ayrımdır; kopya da çoğalabilir. Düzeltme yapmayan Taq kullanın" in tr_cyp
       and "Bu türden" not in tr_cyp, tr_cyp[:200])
    ok("  ...iki fark: baslik ve iki baz birlikte yazilir; gen adi yoksa konum bir kez",
       tr_iki.startswith("Kopyadan yalnızca 2 baz farkı var") and "R 3' son bazında (primerin G'si karşısında T) ve "
       "3' uçtan 4. bazında (primerin A'sı karşısında C) farklı" in tr_iki
       and "chr6:31.974.969–31.975.482 bölgesinde (514 bp)" in tr_iki
       and "Bu kadar az fark zayıf bir ayrım olabilir" in tr_iki, tr_iki[:200])
    ok("  ...F+F urunu ve birden cok yer belirtilir",
       "(chr2:5.000–5.811, 812 bp, F+F)" in tr_ff and "F yalnız 3' uçtan 2. bazında farklı (primerin C'si karşısında A)"
       in tr_ff and "Bu türden 3 yer var; en az farklı olanı yazıldı." in tr_ff, tr_ff[:200])
    ok("  ...Ingilizce", d["en"][0].startswith("Differs from a copy by a single base only — be cautious")
       and "in CYP21A1P (chr6:31,974,969–31,975,482, 514 bp): F matches the copy exactly, R differs only at its "
           "last 3' base (primer G opposite T)." in d["en"][0], d["en"][0][:200])
    ok("  ...near_copy yoksa not yok", d["yok"] == "")


def test_yakin_kopya_notu(c, engine):
    baslik("Degerlendir: 3' kurali disinda kalan ama yalnizca 1-2 baz farkla urun veren yer (near_copy)")
    # NOBETCI (2026-11-09): CYP21A2 cifti (GRCh37) R'nin CYP21A1P'deki yeri yalniz 3' son bazda farkli (G
    # karsisinda T). Tarama son 6 bazi tam istedigi icin bu yer ve 514 bp'lik kopya urunu Degerlendir'in iki
    # tablosunda da yoktu, cift temiz gorunuyordu. Kullanici: "reverse'un 1 baz farkla tam oturmasi lazim, neden
    # yok". Not yalnizca bilgi: liste ve karar degismez. Kontrol TP53 cifti olculdu (not yok).
    if not engine.GENOME_PATHS.get("GRCh37"):
        return atla("Yakin kopya notu", "GRCh37 genomu yok")
    js = lambda r: r.get_json(silent=True) or {}
    d = js(c.post("/evaluate", json={"forward": "CCAGTTATGGGCCTGTTGCC", "reverse": "TCGTGGTCTAGCTCCTCCTG",
                                     "assembly": "GRCh37", "target": "chr6:32007959"}))
    n = d.get("near_copy") or {}
    ok("CYP21A2 cifti: CYP21A1P'deki kopya urunu bulunur",
       (n.get("chrom"), n.get("start"), n.get("end"), n.get("size")) == ("6", 31974969, 31975482, 514),
       str({k: n.get(k) for k in ("chrom", "start", "end", "size")}))
    ok("  ...yer CYP21A1P, F+R, toplam 1 fark, tek yer",
       "CYP21A1P" in (n.get("genes") or []) and n.get("combination") == "F+R" and n.get("total") == 1
       and n.get("count") == 1, str({k: n.get(k) for k in ("genes", "combination", "total", "count")}))
    ok("  ...F kopyaya birebir, R yalniz 3' son bazda (primerin G'si karsisinda T)",
       n.get("sites") == [{"primer": "forward", "orientation": "+", "mismatches": []},
                          {"primer": "reverse", "orientation": "-",
                           "mismatches": [{"from_3p": 1, "primer_base": "G", "template_base": "T"}]}],
       str(n.get("sites")))
    ok("  ...urun listesi degismez (yalniz hedef)",
       [(o.get("start"), o.get("end")) for o in d.get("products") or []] == [(32007705, 32008217)],
       str([(o.get("start"), o.get("end")) for o in d.get("products") or []]))
    if engine.GENOME_PATHS.get("GRCh38"):
        d2 = js(c.post("/evaluate", json={"forward": "GGTAGGTTTTCTGGGAAGGG", "reverse": "CGTTCTGGTAAGGACAAGGG",
                                          "assembly": "GRCh38"}))
        ok("Kontrol (TP53 cifti): not yok", "near_copy" in d2 and d2["near_copy"] is None, str(d2.get("near_copy")))


def test_yakin_rozet_notu(c, engine):
    baslik("Ozgul rozetli ciftte 3' kurali disinda kalan yakin kopya notu (/specificity near_copy; F-03)")
    # NOBETCI (2026-11-11, kullanici karari: kartta rozetin altinda tek satir): BRCA1 c.68_69 birinci cifti
    # 'Ozgul' rozeti aliyordu ama chr17:43.167.979-43.168.799 (821 bp) bir yerde genomik reverse primerin 3'
    # ucundan 2. bazinda tek uyumsuzlukla urun verir (taramanin 3' kurali bunu saymaz). Not rozetin
    # isabetlerinden hesaplanir (ayri tarama yok); rozet karari, sira ve 'En iyi Ozgul cift' degismez.
    # BRCA1 eksi iplikte: kartin Forward'i genomik reverse'tur, arayuz adlari kartla ayni gonderir.
    import re
    import subprocess
    import specificity
    js = lambda r: r.get_json(silent=True) or {}
    if engine.GENOME_PATHS.get("GRCh38"):
        brca_f, brca_r = "AGAAAGGAAAAGACCCAAGG", "AGAGTGGATGGAGAACAAGG"      # kartta Forward, Reverse
        ex = {"chrom": "chr17", "start": 43123828, "end": 43124361}
        d = js(c.post("/specificity", json={"assembly": "GRCh38", "forward": brca_f, "reverse": brca_r,
                                            "expected": ex}))
        n = d.get("near_copy") or {}
        ok("BRCA1 c.68_69 birinci cifti: 'Ozgul' rozeti ve yakin kopya notu var",
           d.get("specific") is True and bool(n), str(d.get("near_copy"))[:120])
        ok("  ...konum ve boy: chr17:43.167.979-43.168.799, 821 bp",
           (n.get("chrom"), n.get("start"), n.get("end"), n.get("size")) == ("17", 43167979, 43168799, 821),
           str({k: n.get(k) for k in ("chrom", "start", "end", "size")}))
        var = [s for s in n.get("sites") or [] if s["mismatches"]]
        ok("  ...uyumsuzluk kartin Forward'inde (3' uctan 2. baz, tek)",
           len(var) == 1 and var[0]["primer"] == "forward"
           and [m["from_3p"] for m in var[0]["mismatches"]] == [2], str(n.get("sites")))
        d2 = js(c.post("/specificity", json={"assembly": "GRCh38", "forward": brca_r, "reverse": brca_f,
                                             "expected": ex}))
        v2 = [s for s in (d2.get("near_copy") or {}).get("sites", []) if s["mismatches"]]
        ok("  ...ad istekteki adi izler (adlar degisince ayni primer 'reverse')",
           len(v2) == 1 and v2[0]["primer"] == "reverse", str(d2.get("near_copy"))[:120])
        sade = {k: v for k, v in d.items() if k != "near_copy"}
        e = dict(ex, chrom="17")
        ref = specificity.check_pair(
            engine.GENOME_PATHS["GRCh38"], brca_f, brca_r, expected=e, params={}, assembly="GRCh38")
        ref["assembly"] = "GRCh38"
        ok("  ...rozet karari ve yan urunler not olmadan birebir ayni (check_pair)",
           json.dumps(sade, sort_keys=True, default=str) == json.dumps(ref, sort_keys=True, default=str))
        d3 = js(c.post("/specificity", json={"assembly": "GRCh38", "forward": "GGTAGGTTTTCTGGGAAGGG",
                                             "reverse": "CGTTCTGGTAAGGACAAGGG",
                                             "expected": {"chrom": "chr17", "start": 7676059, "end": 7676388}}))
        ok("Kontrol (TP53 c.215 birinci cifti): 'Ozgul', not yok",
           d3.get("specific") is True and "near_copy" in d3 and d3["near_copy"] is None, str(d3.get("near_copy")))
        d4 = js(c.post("/specificity", json={"assembly": "GRCh38", "forward": brca_f, "reverse": brca_r}))
        ok("Hedef bolge bilinmiyorsa (serbest dizi) not yok", "near_copy" in d4 and d4["near_copy"] is None,
           str(d4.get("near_copy"))[:100])
    else:
        atla("Yakin kopya rozet notu (motor)", "GRCh38 genomu yok")
    # Arayuz: not yalniz DNA modunda ve 'Ozgul' rozetinde, rozetin altinda; metin iki dilde (node)
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    app = open(os.path.join(kok, "app.js"), encoding="utf-8").read()
    i18n = open(os.path.join(kok, "i18n.js"), encoding="utf-8").read()
    kod = "\n".join(x for x in app.splitlines() if not x.lstrip().startswith("//"))
    rz = kod[kod.find("function rozetYaz("):kod.find("function yakinSatiriYaz(")]
    ok("rozetYaz notu yalniz Ozgul rozetinde, DNA modunda ve hatasiz sonucta cizer",
       "yakinSatiriYaz(bas, !durum && s && !s.error && s.specific && lastResult && !lastResult.mode" in rz, rz[-300:])
    i = kod.find("function yakinSatiriYaz(")
    govde = kod[i:kod.find("\n}", i)] + "\n}\n"
    anahtar = set(re.findall(r't\("(auto\.yakin[\w.]*)"', govde))
    ok("  ...metinler iki dilde", anahtar == {"auto.yakin", "auto.yakin.primer"}
       and all(i18n.count(f'"{k}":') == 2 for k in anahtar), str(sorted(anahtar)))
    node = shutil.which("node")
    if not node:
        return atla("Yakin kopya satiri metni", "node yok")
    yardim = (re.search(r"^const yerel = .*$", app, re.M).group(0) + "\n")
    brca = {"chrom": "17", "start": 43167979, "end": 43168799, "size": 821, "combination": "F+R", "total": 1,
            "count": 1, "sites": [{"primer": "forward", "orientation": "+", "mismatches": [
                {"from_3p": 2, "primer_base": "G", "template_base": "T"}]},
                {"primer": "reverse", "orientation": "-", "mismatches": []}]}
    iki = dict(brca, total=3, sites=[brca["sites"][0], {"primer": "reverse", "orientation": "-", "mismatches": [
        {"from_3p": 1, "primer_base": "A", "template_base": "C"}, {"from_3p": 4, "primer_base": "A", "template_base": "C"}]}])
    betik = (i18n + "\n" + yardim + govde + "const v = " + json.dumps([brca, iki, dict(brca, sites=[])]) + ";\n"
             "const r = {};\nfor (const L of ['tr', 'en']) { LANG = L; r[L] = v.map((n) => { const bas = { nextElementSibling: null,"
             " after(e) { this.s = e; } }; global.document = { createElement: () => ({ className: '', textContent: '',"
             " classList: { contains: () => false } }) }; yakinSatiriYaz(bas, n); return bas.s ? bas.s.className + '|' + bas.s.textContent : ''; }); }\n"
             "console.log(JSON.stringify(r));\n")
    dosya = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    try:
        dosya.write(betik)
        dosya.close()
        r = subprocess.run([node, dosya.name], capture_output=True, text=True, encoding="utf-8", timeout=60)
    finally:
        os.unlink(dosya.name)
    if r.returncode != 0:
        return ok("Yakin kopya satiri node ile kurulur", False, r.stderr.strip()[:200])
    d = json.loads(r.stdout)
    ok("Satir metni (TR): onaylanan metin",
       d["tr"][0] == "spec-yakin|Yakın kopya: chr17:43.167.979–43.168.799 (821 bp); Forward primerin 3' ucundan 2. "
                     "bazda 1 uyumsuzluk. Ayrıntı Değerlendir'de.", d["tr"][0])
    ok("  ...Ingilizce", d["en"][0] == "spec-yakin|Near copy: chr17:43,167,979–43,168,799 (821 bp); 1 mismatch at "
                                      "base 2 from the 3' end of the Forward primer. Details in Evaluate.", d["en"][0])
    ok("  ...iki uyumsuzluk: Reverse adi, 3' son baz ve 4. baz",
       "Reverse primerin 3' son bazında ve 3' ucundan 4. bazda 2 uyumsuzluk" in d["tr"][1]
       and "2 mismatches at the last 3' base and base 4 from the 3' end of the Reverse primer" in d["en"][1],
       d["tr"][1] + " / " + d["en"][1])
    ok("  ...uyumsuzluklu primer yoksa satir yok", d["tr"][2] == "" and d["en"][2] == "")


def test_hairpin_uyarisi(c, engine):
    baslik("Hairpin uyarisi: hairpin Tm >= Ta - 5 C ise kartta uyari; siralama degismez (F-05)")
    # NOBETCI (2026-11-11, kullanici karari: "sadece yuksek degerlere cikarsa uyari koyalim, hesaplamaya katma"):
    # 298 hedefte birinci ciftin 29'unda bir primerin hairpin Tm'i Ta - 5 C'yi geciyordu ama kartta isaret yoktu.
    # Kural motorda tek yerde (hairpin_uyarisi); _pair_core DNA, RNA, Dizi ve Kirilma noktasi icin ortak.
    import re
    import subprocess
    # Kural ve sinirlar (Ta 55,0 -> esik 50,0)
    u = engine.hairpin_uyarisi(52.1, 40.0, 55.0)
    ok("Esigi gecen primer uyarilir: yalniz Forward, alanlar dogru",
       u == [{"primer": "forward", "hairpin_tm": 52.1, "ta": 55.0, "esik": 50.0}], str(u))
    ok("  ...esige esit uyarilir, esigin hemen altinda uyarilmaz",
       [x["primer"] for x in engine.hairpin_uyarisi(50.0, 49.9, 55.0)] == ["forward"])
    ok("  ...yapi yoksa (0,0) hic uyarilmaz; iki primer de gecerse ikisi", engine.hairpin_uyarisi(0.0, 0.0, 5.0) == []
       and [x["primer"] for x in engine.hairpin_uyarisi(60.0, 51.0, 55.0)] == ["forward", "reverse"])
    ok("Esik sabiti 5 C", engine.HAIRPIN_UYARI_PAYI == 5.0)
    # Siralama: _rank_order hairpin'e bakmaz
    kaynak = open(os.path.join(BURASI, "engine.py"), encoding="utf-8").read()
    i = kaynak.find("def _rank_order(")
    govde = kaynak[i:kaynak.find("\ndef ", i + 10)]
    ok("_rank_order hairpin kullanmaz (sira degismez)", "hairpin" not in govde.lower(), "")
    if engine.GENOME_PATHS.get("GRCh38"):
        # 11:60429745: birinci ciftte Reverse hairpin 52,7 >= Ta (52,3) - 5; 17:7242000 (GABARAP) temiz ornek aranir
        d = c.post("/design", json={"assembly": "GRCh38", "chrom": "11", "position": "60429745", "lang": "tr"}).get_json(silent=True) or {}
        p = (d.get("pairs") or [{}])[0]
        w = p.get("hairpin_warn") or []
        ok("Gercek tasarim (GRCh38 11:60429745) birinci cift: Reverse uyarisi",
           [(x["primer"], x["hairpin_tm"]) for x in w] == [("reverse", p.get("reverse", {}).get("hairpin_tm"))]
           and p.get("reverse", {}).get("hairpin_tm", 0) >= p.get("ta_suggested", 99) - 5, str(w))
        kural = True
        for q in d.get("pairs") or []:
            bek = [(a, q[a]["hairpin_tm"]) for a in ("forward", "reverse")
                   if q[a]["hairpin_tm"] > 0 and q[a]["hairpin_tm"] >= round(q["ta_suggested"] - 5, 1)]
            kural = kural and [(x["primer"], x["hairpin_tm"]) for x in q.get("hairpin_warn", [None])] == bek
        ok("  ...her ciftte uyari tam olarak esigi gecen primerde", kural and bool(d.get("pairs")))
        sirali = [q["rank"] for q in d.get("pairs") or []]
        ok("  ...sira 1..n kalir", sirali == list(range(1, len(sirali) + 1)), str(sirali))
    else:
        atla("Hairpin uyarisi (gercek tasarim)", "GRCh38 genomu yok")
    # Arayuz: satir metni TR/EN, eksi iplikte kartin gosterdigi ad (node)
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    app = open(os.path.join(kok, "app.js"), encoding="utf-8").read()
    i18n = open(os.path.join(kok, "i18n.js"), encoding="utf-8").read()
    kod = "\n".join(x for x in app.splitlines() if not x.lstrip().startswith("//"))
    ok("Uyari 6 kartta cizilir (DNA, 3 x RNA, Dizi, Kirilma noktasi)", kod.count("${hairpinSatiri(p") == 6, str(kod.count("${hairpinSatiri(p")))
    ok("  ...DNA ve Kirilma noktasi kartlari eksi iplikte adi cevirir",
       "${hairpinSatiri(p, v !== p)}" in kod and "${hairpinSatiri(p, cevrik)}" in kod)
    ok("  ...metin iki dilde", i18n.count('"hairpin.uyari":') == 2)
    node = shutil.which("node")
    if not node:
        return atla("Hairpin uyari satiri metni", "node yok")
    i = kod.find("function hairpinSatiri(")
    fn = kod[i:kod.find("\n}", i)] + "\n}\n"
    yardim = re.search(r"^const yerel = .*$", app, re.M).group(0) + "\n" + re.search(r"^const esc = .*\n.*$", app, re.M).group(0) + "\n"
    p = {"hairpin_warn": [{"primer": "forward", "hairpin_tm": 52.1, "ta": 55.0, "esik": 50.0}]}
    iki = {"hairpin_warn": [{"primer": "forward", "hairpin_tm": 57.3, "ta": 53.8, "esik": 48.8},
                            {"primer": "reverse", "hairpin_tm": 49.2, "ta": 53.8, "esik": 48.8}]}
    betik = (i18n + "\n" + yardim + fn + "const v = " + json.dumps([[p, False], [p, True], [iki, False], [{}, False]]) + ";\n"
             "const r = {};\nfor (const L of ['tr', 'en']) { LANG = L; r[L] = v.map(([x, c]) => hairpinSatiri(x, c)); }\n"
             "console.log(JSON.stringify(r));\n")
    dosya = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    try:
        dosya.write(betik)
        dosya.close()
        r = subprocess.run([node, dosya.name], capture_output=True, text=True, encoding="utf-8", timeout=60)
    finally:
        os.unlink(dosya.name)
    if r.returncode != 0:
        return ok("Hairpin uyari satiri node ile kurulur", False, r.stderr.strip()[:200])
    d = json.loads(r.stdout)
    ok("Satir metni (TR): onaylanan metin",
       d["tr"][0] == '<div class="hairpin-uyari">Hairpin: Forward primerin hairpin Tm\'i 52,1 °C; önerilen Ta 55,0 °C\'nin '
                     '5 °C altını geçiyor. Primer kendi üzerine katlanıp verimi düşürebilir.</div>', d["tr"][0])
    ok("  ...Ingilizce", d["en"][0] == '<div class="hairpin-uyari">Hairpin: the hairpin Tm of the Forward primer is 52.1 °C; '
                                         'it exceeds the suggested Ta of 55.0 °C minus 5 °C. The primer may fold onto itself '
                                         'and lower the yield.</div>', d["en"][0])
    ok("  ...eksi iplikte motorun forward'u kartta Reverse gorunur", "Reverse primerin hairpin Tm'i 52,1" in d["tr"][1]
       and "the Reverse primer is 52.1" in d["en"][1], d["tr"][1])
    ok("  ...iki primer iki satir; uyari yoksa bos",
       d["tr"][2].count('class="hairpin-uyari"') == 2 and "Reverse primerin hairpin Tm'i 49,2" in d["tr"][2]
       and d["tr"][3] == "" and d["en"][3] == "", d["tr"][2][:200])


def test_degerlendir_k3(c, engine, annot_var):
    baslik("Degerlendir (duzeltme 2, K3): D1-04 rol karari, D1-02 hedef konum, A5-02 RNA tek primer, A5-04 hedef kopya degil")
    # NOBETCI (2026-11-10): D1-04 PMS2/NCF1 cifti ters girilince psodogen kopyasi (ters yonlu) beklenen yonde
    # urun verip F/R uyarisini susturuyordu; D1-02 hedef konum urun disinda ya da kromozom gecersizse sessizdi;
    # A5-02 RNA modunda tek primer "sirtlari donuk" teshisi aliyordu; A5-04 hedefin kendisi "kopya" sayiliyordu.
    js = lambda r: r.get_json(silent=True) or {}
    var = lambda j, anahtar: [f["text"] for f in j.get("findings") or [] if anahtar in f["text"]]
    F, R = "CCATGGGACTGACTTTCTGC", "GAGGAATCCCAAAGTTCCAA"      # TP53, GRCh38 chr17:7675903-7676436
    if annot_var and engine.GENOME_PATHS.get("GRCh38"):
        cift = {"PMS2": ("ATTTCATTTCTGCTGTAAAG", "CTCCCAGAGTGCTGGGATTA"), "NCF1": ("GATCCTGGGTGCACACAGCA", "GGCTAAGGTCCTTCCCAAAG"),
                "STRC": ("GTCTGGTATTCTGAGTCAGA", "CCACTGATGATGGTGGCTGA"), "TP53": ("CTTCCAGTTGCTTTATCTGT", "CAGTGAGGAATCAGAGGCCT"),
                "UBE2L6": ("CTCGGATTGGGGCAGGAAGG", "AGCTGTGAACCCCCTCTCCA")}
        for gen, (f, r) in cift.items():
            d = js(c.post("/evaluate", json={"forward": f, "reverse": r, "assembly": "GRCh38"}))
            t_ = js(c.post("/evaluate", json={"forward": r, "reverse": f, "assembly": "GRCh38"}))
            ok(f"D1-04 {gen}: dogru yonde girisinde rol uyarisi yok", d.get("pair_roles_swapped") is False
               and not var(d, "rolleri yer değişmiş"), str(d.get("pair_roles_swapped")))
            ok(f"  ...ters girisinde uyari var (genin kendi lokusuna gore)",
               t_.get("pair_roles_swapped") is True and bool(var(t_, "rolleri yer değişmiş")),
               f"{t_.get('pair_gene')} {t_.get('pair_roles_swapped')}")
        t_ = js(c.post("/evaluate", json={"forward": cift["PMS2"][1], "reverse": cift["PMS2"][0], "assembly": "GRCh38", "lang": "en"}))
        ok("D1-04 PMS2 ters: kopya lokus yonu notu (bilgi) var, EN", bool(t_.get("pair_roles_copies"))
           and any(f["level"] == "bilgi" for f in t_.get("findings") or [] if "copy loci" in f["text"]), str(t_.get("pair_roles_copies")))
        t_ = js(c.post("/evaluate", json={"forward": cift["PMS2"][1], "reverse": cift["PMS2"][0], "assembly": "GRCh38"}))
        ok("  ...TR", bool(var(t_, "kopya lokus")))
    else:
        atla("D1-04 rol karari", "GRCh38 genomu ya da transkript tablosu yok")

    if engine.GENOME_PATHS.get("GRCh38"):
        temel = {"forward": F, "reverse": R, "assembly": "GRCh38"}
        for lang, anahtar in (("tr", "hedef konum"), ("en", "target position you gave")):
            for hedef, bilgi in (("chr17:1000", True), ("chr5:7676000", True), ("7676000", False), ("chr17:7676000", False),
                                 ("NC_000017.11:7676000", False)):
                k = c.post("/evaluate", json=dict(temel, target=hedef, lang=lang))
                d = js(k)
                isaret = any((p.get("amplicon") or {}).get("variant_span") for p in d.get("products") or [])
                ok(f"D1-02 {lang} hedef {hedef}: bilgi bulgusu {'var' if bilgi else 'yok'}",
                   k.status_code == 200 and bool(var(d, anahtar)) == bilgi and isaret == (not bilgi), f"{k.status_code} {isaret}")
            for hedef in ("chrZZ:7676000", "NC_000099.1:5", "NC_000017.10:7676000"):
                k = c.post("/evaluate", json=dict(temel, target=hedef, lang=lang))
                ok(f"  ...{lang} {hedef}: 400 ve hata iletisi 'tasarim' demez", k.status_code == 400
                   and "asarım" not in str(js(k).get("error")) and "esign" not in str(js(k).get("error")),
                   f"{k.status_code} {str(js(k).get('error'))[:70]}")
        k = c.post("/evaluate", json={"forward": F, "assembly": "GRCh38", "target": "chrZZ:5"})
        ok("D1-02 tek primer + tanimsiz kromozom: 400", k.status_code == 400)
        # A5-04: hedefin 3' ucunda yazim hatali primer: hedefin kendisi kopya sayilmaz
        R1 = R[:-1] + {"A": "C", "C": "A", "G": "T", "T": "G"}[R[-1]]
        d = js(c.post("/evaluate", json=dict(temel, reverse=R1)))
        ok("A5-04 TP53, R'nin 3' son bazi degisik: hedefin kendisi 'kopya' degil", d.get("near_copy") is None, str(d.get("near_copy"))[:80])
    else:
        atla("D1-02 / A5-04", "GRCh38 genomu yok")

    if annot_var and engine.GENOME_PATHS.get("GRCh38"):
        import transcripts as T
        tx = T.get_transcript("NM_000546", "GRCh38")
        cdna, _k = engine.build_cdna(tx, "GRCh38")
        ex = tx["exons"] if tx["strand"] == "+" else tx["exons"][::-1]
        x = sum(b - a + 1 for a, b in ex[:4])
        Fc = cdna[x - 10:x + 10]
        d = js(c.post("/evaluate_cdna", json={"forward": Fc, "acc": "NM_000546", "assembly": "GRCh38"}))
        ok("A5-02 RNA modunda tek primer: 'sirtlari donuk' teshisi yok, karar 'sorun' degil",
           not var(d, "sırtları dönük") and d.get("verdict") != "sorun" and bool((d.get("placement") or {}).get("forward")),
           str(d.get("verdict")))
        ok("  ...ikinci primer gerekir bilgisi TR/EN", bool(var(d, "reverse primeri de girin")) and bool(var(
            js(c.post("/evaluate_cdna", json={"forward": Fc, "acc": "NM_000546", "assembly": "GRCh38", "lang": "en"})), "second primer")))
        Rr = cdna[40:60].translate(str.maketrans("ACGT", "TGCA"))[::-1]
        d = js(c.post("/evaluate_cdna", json={"forward": Fc, "reverse": Rr, "acc": "NM_000546", "assembly": "GRCh38"}))
        ok("  ...iki primerli sirtlari donuk cift: teshis korunur", d.get("verdict") == "sorun" and bool(var(d, "sırtları dönük")))
    else:
        atla("A5-02 RNA tek primer", "GRCh38 genomu ya da transkript tablosu yok")


def test_urun_hedef_isareti(c):
    baslik("Urun dizisinde girilen konum isaretlenir (tum sekmeler)")
    # NOBETCI (2026-11-06, kullanici istegi): "19. kromozom 11537002 dedigimde urun dizisinde bu
    # koordinattaki nukleotit farkli renkle belirgin gorunsun, tum sekmeler icin". Eksi iplikteki
    # gende urun ters cevrildigi icin isaret de aynalanmali: yanlis baz isaretlemek hic
    # isaretlememekten kotudur. TP53 c.215 = chr17:7676154: + iplikte G, cDNA'da C.
    import re
    import subprocess
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    oku = lambda ad: open(os.path.join(kok, ad), encoding="utf-8").read()
    app, i18n, css, html = oku("app.js"), oku("i18n.js"), oku("style.css"), oku("index.html")
    kod = "\n".join(x for x in app.splitlines() if not x.lstrip().startswith("//"))
    govde = lambda ad: kod[kod.find(f"function {ad}"):kod.find("\n}", kod.find(f"function {ad}"))]
    ok("konum en son isaretlenir (primerin ustune dusse de gorunur), lejantta adi ve sirasi yazar",
       0 < kod.find('isaretle(a.unknown_span, "amp-n")') < kod.find('isaretle(a.variant_span, "amp-v")')
       and 'class="amp-sw amp-v"' in kod and 'title="${hedefAdi}"' in kod)
    ok("  ...kart ve Degerlendir urun gorunumu konumun adini verir",
       "targetLabel:" in govde("toggleAmplicon") and "targetLabel:" in govde("toggleEvalAmplicon"))
    ok("Degerlendir'de alan var, kartin dugmesi doldurur, istek motora gider",
       'id="ev_hedef"' in html and '$("ev_hedef").value =' in govde("pairToEvaluate") and "govde.target = hedefKonum" in kod)
    tr, en = i18n.split(chr(10) + "  en: {", 1)
    ok("metinler iki dilde", all(f'"{k}"' in m for k in ("amp.target", "amp.target.bp", "amp.target.region", "amp.target.seq",
                                                        "ev.target", "ev.target.ph", "ev.target.help") for m in (tr, en)))

    def isik(h):
        f = lambda x: x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
        r, g, b = (f(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    dolgu, yazi = re.findall(r"--hedef:\s*(#[0-9a-f]{6})", css), re.findall(r"--on-hedef:\s*(#[0-9a-f]{6})", css)
    oran = [(max(isik(a), isik(b)) + 0.05) / (min(isik(a), isik(b)) + 0.05) for a, b in zip(dolgu, yazi)]
    ok("isaret iki temada tanimli, yazi dolgu uzerinde en az 4,5:1", len(oran) == 2 and min(oran) >= 4.5, str([round(x, 1) for x in oran]))

    d = c.post("/design", json={"assembly": "GRCh38", "chrom": "17", "position": "7676154", "params": {}}).get_json()
    cift = d.get("pairs") or []
    ok("DNA: her ciftte tek baz isaretli, koordinata denk ve genomdaki baz (+ iplikte G)", bool(cift) and all(
        p["amplicon"].get("variant_span") == [7676154 - p["amplicon_genomic_start"]] * 2
        and p["amplicon"]["sequence"][7676154 - p["amplicon_genomic_start"]] == "G" for p in cift), str(len(cift)))
    if not cift:
        return
    a = c.post("/design", json={"assembly": "GRCh38", "chrom": "17", "position": "7676154-7676158", "params": {}}).get_json()
    v = a["pairs"][0]["amplicon"].get("variant_span") if a.get("pairs") else None
    ok("  ...aralik girilince aralik isaretlenir (5 baz)", bool(v) and v[1] - v[0] == 4, str(v))
    r = c.post("/design_cdna", json={"assembly": "GRCh38", "acc": "NM_000546", "c_position": "c.215", "params": {}}).get_json()
    bol = lambda a: a["sequence"][a["variant_span"][0]:a["variant_span"][1] + 1] if a.get("variant_span") else None
    ok("RNA: c.215 isaretli, cDNA'daki baz C", bool(r.get("pairs")) and all(bol(p["amplicon"]) == "C" for p in r["pairs"]))
    dizi = max((p["amplicon"]["sequence"] for p in cift), key=len)
    t1 = c.post("/design_sequence", json={"sequence": dizi, "target": "201-205", "params": {}}).get_json()
    t2 = c.post("/design_sequence", json={"sequence": dizi[:200] + "[" + dizi[200] + "/T]" + dizi[201:], "params": {}}).get_json()
    ok("Dizi: hedef konum ve kose parantez isaretlenir", bool(t1.get("pairs")) and bol(t1["pairs"][0]["amplicon"]) == dizi[200:205]
       and bool(t2.get("pairs")) and bol(t2["pairs"][0]["amplicon"]) == dizi[200])
    b = c.post("/design_sequence", json={"sequence": dizi, "params": {}}).get_json()
    s2 = c.post("/design_sequence_pair", json={"forward": dizi[:220], "reverse": dizi[220:], "params": {}}).get_json()
    e = c.post("/design_skipping", json={"assembly": "GRCh38", "acc": "NM_007294", "exon": 12, "params": {}}).get_json()
    ok("  ...hedefi olmayan modlarda isaret yok (hedefsiz dizi, iki dizi, ekson atlama)",
       all("variant_span" not in p["amplicon"] for x in (b, s2, e) for p in x.get("pairs", [])))
    k = c.post("/design_breakpoint", json={"assembly": "GRCh38", "chrom": "17", "start": 7670000, "end": 7672000,
                                           "type": "del", "params": {}}).get_json()
    ok("Kirilma noktasi: birlesim isaretinin iki yanindaki bazlar", bool(k.get("pairs")) and all(
        p["amplicon"].get("variant_span") == [p["amplicon"]["junction_offsets"][0] - 1, p["amplicon"]["junction_offsets"][0]] for p in k["pairs"]))
    u = c.post("/design_breakpoint", json={"assembly": "GRCh38", "chrom": "2", "start": 90000001, "end": 90000500,
                                           "type": "dup", "params": {"pcr_max": 3000}}).get_json()
    dis = [p for p in u.get("pairs", []) if not p["amplicon"].get("junction_offsets")]
    ok("  ...kucuk duplikasyonda dis primer urununde bolgenin kendisi", (u.get("input") or {}).get("approach") == "size_shift"
       and bool(dis) and all(p["amplicon"].get("variant_span") == [90000001 - p["amplicon_genomic_start"], 90000500 - p["amplicon_genomic_start"]]
                             for p in dis), f'{(u.get("input") or {}).get("approach")} {len(dis)}')
    ev = lambda h: c.post("/evaluate", json={"forward": cift[0]["forward"]["sequence"], "reverse": cift[0]["reverse"]["sequence"],
                                             "assembly": "GRCh38", "lang": "tr", "params": {}, **({"target": h} if h else {})})
    j = ev("chr17:7676154").get_json()
    am = j["products"][0].get("amplicon", {})
    ok("Degerlendir: verilen konum urunde isaretli", bol(am) == "G", str(am.get("variant_span")))
    ok("  ...baska kromozomdaki ya da urun disi konum isaretlenmez, alan bos da olur",
       "variant_span" not in ev("chr3:7676154").get_json()["products"][0].get("amplicon", {})
       and "variant_span" not in ev("chr17:7000000").get_json()["products"][0].get("amplicon", {})
       and "variant_span" not in ev("").get_json()["products"][0].get("amplicon", {}))
    ok("  ...anlasilmayan konum anlasilir hatayla reddedilir", ev("abc").status_code == 400 and "Varyant konumu" in ev("abc").get_json().get("error", ""))
    cd = c.post("/evaluate_cdna", json={"forward": "GACACGCTTCCCTGGATTGG", "reverse": "TGCCCTGGTAGGTTTTCTGG", "acc": "NM_000546",
                                        "assembly": "GRCh38", "lang": "tr", "params": {}, "target": "c.215"}).get_json()
    pr = cd.get("product") or {}
    ok("Degerlendir cDNA: c.215 isaretli, baz C", bol(pr) == "C", str(pr.get("variant_span")))
    node = shutil.which("node")
    if not node:
        return atla("isaretin aynalanmasi", "node yok")
    betik = ("const y = require(" + json.dumps(os.path.abspath(os.path.join(kok, "yon.js"))) + ");"
             "const a = {sequence: 'AAAACCCCGG', forward_span: [0, 3], reverse_span: [7, 9], variant_span: [5, 6]};"
             "console.log(JSON.stringify({k: y.genYonunde({gene_strand: '-', forward: 1, reverse: 2, amplicon: a}).amplicon.variant_span,"
             " a: y.genYonunde({gene_strand: '+', amplicon: a}).amplicon.variant_span,"
             " d: y.degerlendirmeUrunu(a, 'R', 'F').amplicon.variant_span}));")
    r = subprocess.run([node, "-e", betik], capture_output=True, text=True, timeout=60)
    z = json.loads(r.stdout) if r.returncode == 0 else {}
    ok("eksi iplikte ve R+F urunde isaret aynalanir, arti iplikte degismez",
       z == {"k": [3, 4], "a": [5, 6], "d": [3, 4]}, json.dumps(z))


def test_degerlendir_pcr_siniri(c):
    baslik("Degerlendir laboratuvarin urun sinirini (pcr_max) bilir")
    # NOBETCI (2026-11-06, 647 yayinlanmis ciftle deneme): arayuz sinirdan soz etmiyor, motorda
    # ust sinir sabit 5000 bp idi. 700 bp ustu 46 ciftin 8'ine "Sorun gorunmuyor" deniyordu
    # (Nie 2018, ASXL1 ekzon 12, 772 bp); KURULUM ise sinirin her sekmede gecerli oldugunu soyluyor.
    import re
    F, R = "ATGCCTCTTCCTGCTGAGAT", "GTGCTCCTGCCTAAAGAGTA"
    app = open(os.path.join(BURASI, "..", "electron", "renderer", "app.js"), encoding="utf-8").read()
    m = re.search(r"const KOSUL_IDS = \[([^\]]*)\]", app)
    ok("arayuz siniri Degerlendir istegine ekler", bool(m) and '"pcr_max"' in m.group(1))
    sor = lambda prm: c.post("/evaluate", json={"forward": F, "reverse": R, "assembly": "GRCh38", "lang": "tr", "params": prm})
    uyari = lambda d: [b for b in d.get("findings", []) if "sınırınızın üstünde" in b["text"]]
    r = sor({})
    d = r.get_json()
    ok("varsayilan sinirda (700 bp) 772 bp'lik urun uyarilir, karar 'iyi' kalmaz",
       r.status_code == 200 and [b["level"] for b in uyari(d)] == ["uyari"] and d.get("verdict") == "uyari",
       f'{d.get("verdict")} {[b["text"][:50] for b in uyari(d)]}')
    ok("  ...metin sinirin laboratuvara ait oldugunu soyler, 'cogalmaz' demez",
       bool(uyari(d)) and "772" in uyari(d)[0]["text"] and "protokolde" in uyari(d)[0]["text"]
       and "çoğalmaz" not in uyari(d)[0]["text"])
    r = sor({"pcr_max": "1000"})
    d = r.get_json()
    ok("  ...sinir yukseltilince uyari kalkar (arayuz metin gonderir)",
       r.status_code == 200 and not uyari(d) and d.get("verdict") == "iyi", str(d.get("verdict")))
    ok("gecersiz sinir anlasilir hatayla reddedilir", sor({"pcr_max": 50}).status_code == 400)
    r = c.post("/evaluate", json={"forward": F, "reverse": R, "assembly": "GRCh38", "lang": "en", "params": {}})
    ok("Ingilizce metin", "above your limit" in " ".join(b["text"] for b in r.get_json().get("findings", [])))
    cdna = lambda s: c.post("/evaluate_cdna", json={"forward": "GACACGCTTCCCTGGATTGG", "reverse": "TGCCCTGGTAGGTTTTCTGG",
                                                    "acc": "NM_000546", "assembly": "GRCh38", "lang": "tr",
                                                    "params": {"pcr_max": s}}).get_json()
    ok("cDNA urunu de sinira bakar (364 bp: 300'de uyari, 700'de yok)", bool(uyari(cdna(300))) and not uyari(cdna(700)))


def test_kurulum_degerlendir(c):
    baslik("KURULUM.txt Degerlendir sekmesini anlatir")
    # NOBETCI (2026-11-03 tarama): kullanim kilavuzunda DNA, RNA, Dizi ve Kirilma noktasi
    # sekmeleri anlatiliyordu, Degerlendir sekmesinin bolumu yoktu. Bolumdeki her cumle
    # kurulu uygulamada olculdu (betikler/degerlendir_metin.mjs, degerlendir_snp.mjs).
    import re
    metin = open(os.path.join(BURASI, "..", "KURULUM.txt"), encoding="utf-8").read()
    kullanim = metin[metin.find("\nKULLANIM\n"):metin.find("\nÇOĞALTILABİLEN EN UZUN ÜRÜN\n")]
    bas = kullanim.find("\nDeğerlendir sekmesi\n")
    bolum = kullanim[bas:] if bas >= 0 else ""
    ok("KULLANIM'da Kirilma noktasindan sonra Degerlendir sekmesi bolumu var",
       bas > kullanim.find("\nKırılma noktası sekmesi\n") >= 0)
    # Ekrandaki adlar bolumde aynen yazilir: kullanici ekranda gordugunu metinde bulsun
    i18n = open(os.path.join(BURASI, "..", "electron", "renderer", "i18n.js"), encoding="utf-8").read()
    tr = i18n.split(chr(10) + "  en: {", 1)[0]
    deger = lambda k: (re.search(r'"%s": "([^"]*)"' % re.escape(k), tr) or [None, f"<{k} yok>"])[1]
    adlar = [deger(k) for k in ("ev.verdict.iyi", "ev.verdict.uyari", "ev.verdict.sorun", "ev.acc.find", "amp.btn")]
    eksik = [a for a in adlar if a not in bolum]
    ok("  ...karar duzeyleri, 'Gen ile bul' ve 'Urun dizisi' ekrandaki adlarla", not eksik, ", ".join(eksik))
    ok("  ...iki mod, hedef / risk duzeyleri, kombinasyonlar, urun yonu, roller ve kart dugmesi",
       all(s in bolum for s in ("DNA (genomik)", "RNA / cDNA", '"hedef"', "Bağlanma olasılığı düşük", "F+F",
                                "R+R", "Forward'dan başlar", "rolleri yer değişmiş", "Tasarım kartlarındaki")))
    ok("  ...surum gecmisinden soz etmez", not any(s in bolum for s in ("sürüm", "0.8.", "önceki")))


def test_kurulu_arayuz_dosyalari(c):
    baslik("Kurulu klasore kopyalanan arayuz dosyalari sayfalarin yukledigi her dosyayi kapsar")
    # NOBETCI (2026-11-01): yon.js eklenince kurulu-guncelle.ps1'in sabit dosya listesinde
    # yoktu; kurulu uygulama sonuc cizerken "genYonunde is not defined" ile bozulacakti
    # (kaynakta calisiyordu). Sayfalarin yukledigi script / stil / resim dosyalari listede olmali.
    import re
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    betik = open(os.path.join(BURASI, "..", "kurulu-guncelle.ps1"), encoding="utf-8").read()
    liste = set(re.findall(r'k = "electron\\renderer\\([^"]+)"', betik))
    yuklenen = set()
    for sayfa in ("index.html", "consent.html"):
        html = open(os.path.join(kok, sayfa), encoding="utf-8").read()
        yuklenen |= {sayfa} | set(re.findall(r'(?:src|href)="([\w.-]+\.(?:js|css|svg|png))"', html))
    eksik = sorted(yuklenen - liste)
    ok("sayfalarin yukledigi her dosya kurulu-guncelle.ps1 listesinde", bool(liste) and not eksik,
       ", ".join(eksik) or f"{len(yuklenen)} dosya")


def test_gen_yonu_adlari(c):
    baslik("F/R adlari genin yonunde - tasarim ve Degerlendir tutarli")
    # NOBETCI (2026-11-01): TP53 (eksi iplik) DNA sekmesinin 1. cifti Degerlendir'e
    # verilince "F ve R rolleri yer degismis" deniyordu (Degerlendir v0.8.8'den beri genin
    # yonune bakiyor, tasarim genoma). Sunucu her cifte genin ipligini ekler; arayuz eksi
    # iplikte F/R'yi cevirir. Ayni fonksiyon (evaluate._urun_geni) iki yerde.
    for gen, krom, konum, iplik in (("TP53", "17", "7676154", "-"), ("MLH1", "3", "37017000", "+")):
        d = c.post("/design", json={"assembly": "GRCh38", "chrom": krom, "position": konum,
                                    "gene": gen}).get_json() or {}
        ps = d.get("pairs") or []
        etiket = {(p.get("strand_gene"), p.get("gene_strand")) for p in ps}
        ok(f"{gen}: her cifte gen ve iplik eklenir ({iplik})", bool(ps) and etiket == {(gen, iplik)}, str(etiket))
        if not ps:
            continue
        p = ps[0]
        gF, gR = (p["reverse"], p["forward"]) if iplik == "-" else (p["forward"], p["reverse"])
        e = c.post("/evaluate", json={"assembly": "GRCh38", "forward": gF["sequence"],
                                      "reverse": gR["sequence"]}).get_json() or {}
        ok(f"  ...{gen}: ekranda gosterilen F/R Degerlendir'de 'yer degismis' DENMEZ",
           e.get("pair_gene") == gen and e.get("pair_roles_swapped") is False,
           f"{e.get('pair_gene')} {e.get('pair_roles_swapped')}")
        if iplik == "-":
            e2 = c.post("/evaluate", json={"assembly": "GRCh38", "forward": p["forward"]["sequence"],
                                           "reverse": p["reverse"]["sequence"]}).get_json() or {}
            ok("  ...TP53: genomik adlarla (eski gosterim) Degerlendir uyariyordu",
               e2.get("pair_roles_swapped") is True)
    b = c.post("/design_breakpoint", json={"assembly": "GRCh38", "chrom": "17", "start": 7670000,
                                           "end": 7672000, "type": "del"}).get_json() or {}
    bp = b.get("pairs") or []
    ok("kirilma noktasi (TP53 icinde delesyon): ciftler eksi iplik olarak isaretli",
       bool(bp) and {(p.get("strand_gene"), p.get("gene_strand")) for p in bp} == {("TP53", "-")})


def test_bolge_etiketleri(c):
    baslik("Primerin hangi genin hangi ekzon / intronunda oldugu yaziyor")
    # NOBETCI (2026-11-01): kullanici bu bilgiyi goremedi. Tasarim tablosunda gen adi
    # yalnizca F ve R farkli genlerdeyse yaziyordu; Degerlendir'in baglanma tablosu intronu
    # numarasiz "intron" diye veriyordu. Beklenenler olculdu: kullanicinin LAMA2 cifti
    # F intron 45, R intron 40 (NM_000426, MANE Select; GRCh37 ve GRCh38'de ayni).
    r = c.post("/evaluate", json={"forward": "GGCCTGAAGATTTCCTGAAG",
                                  "reverse": "AGGTTGTGGTCCTTTGTTTG", "assembly": "GRCh38"})
    d = r.get_json() or {}

    def ilk(ad):
        return (((d.get("sites") or {}).get(ad) or [{}])[0].get("gene_region") or {})

    f, rv = ilk("forward"), ilk("reverse")
    ok("Degerlendir: F baglanma bolgesi gen ve intron numarasiyla (LAMA2 intron 45)",
       r.status_code == 200 and (f.get("gene"), f.get("kind"), f.get("intron")) == ("LAMA2", "intron", 45),
       f"-> {f.get('gene')} {f.get('kind')} {f.get('intron')}")
    ok("  ...R (LAMA2 intron 40), numaralandirma MANE Select transkriptine gore",
       (rv.get("gene"), rv.get("kind"), rv.get("intron")) == ("LAMA2", "intron", 40)
       and rv.get("mane") == "MANE Select",
       f"-> {rv.get('gene')} {rv.get('kind')} {rv.get('intron')} {rv.get('mane')}")
    kok = os.path.join(BURASI, "..", "electron", "renderer")
    app = open(os.path.join(kok, "app.js"), encoding="utf-8").read()
    i18n = open(os.path.join(kok, "i18n.js"), encoding="utf-8").read()
    ok("arayuz: tasarim tablosunda gen adi her zaman, Degerlendir'de ayni etiket",
       'const etiket = (r.gene ? r.gene + "\\u00a0· " : "") + bolgeEtiket(r);' in app
       and "s.gene_region" in app and "bolgeEtiket(gb)" in app)
    tr, en = i18n.split(chr(10) + "  en: {", 1)
    ok("  ...'—' icin aciklama (genler arasi ya da tablo yok), TR/EN",
       all('"th.region.none"' in m for m in (tr, en)))


def test_paket_e_kucuk(c):
    baslik("DMSO, Ta onerisi, MAF gosterimi (Paket E)")
    # NOBETCI (bulgu 22): program GC'ce zengin urunde DMSO onerip Tm'i DMSO'suz hesapliyordu
    F, R = "AGAAGCCGTGAGAAGTGA", "ATGATCTAGGTTGTGGTCCT"
    d0 = c.post("/evaluate", json={"forward": F, "reverse": R, "assembly": "GRCh38",
                                   "params": {}}).get_json() or {}
    d5 = c.post("/evaluate", json={"forward": F, "reverse": R, "assembly": "GRCh38",
                                   "params": {"dmso_conc": "5"}}).get_json() or {}
    tm0 = (d0.get("primers") or {}).get("forward", {}).get("tm")
    tm5 = (d5.get("primers") or {}).get("forward", {}).get("tm")
    ok("Degerlendir: %5 DMSO Tm'i ~3 °C dusurur (0,6 x %)", tm0 and tm5
       and 2.5 <= tm0 - tm5 <= 3.5, f"-> {tm0} -> {tm5}")
    pr = d5.get("pair") or {}
    tmlar = [d5["primers"][k]["tm"] for k in ("forward", "reverse")] if pr else []
    ok("Ta onerisi = dusuk Tm - 5", pr and pr.get("ta_suggested") == round(min(tmlar) - 5, 1),
       f"-> {pr.get('ta_suggested')} / {tmlar}")
    r = c.post("/evaluate", json={"forward": F, "params": {"dmso_conc": 25}})
    ok("DMSO %25 -> 400 (sinir 0-20)", r.status_code == 400 and "DMSO" in
       (r.get_json() or {}).get("error", ""), f"-> {r.status_code}")
    import random
    rnd = random.Random(3)                 # tekrarsiz dizi (tekrar suzgeci elemesin)
    d = c.post("/design_sequence", json={"sequence": "".join(rnd.choice("ACGT") for _ in range(400)),
                                         "params": {"dmso_conc": 3}}).get_json() or {}
    cift = (d.get("pairs") or [{}])[0]
    ok("tasarim ciftinde ta_suggested", cift.get("ta_suggested") == round(
       min(cift["forward"]["tm"], cift["reverse"]["tm"]) - 5, 1) if cift else False,
       f"-> {cift.get('ta_suggested')}")
    # NOBETCI (bulgu 20): %0,25 alti MAF indekste 0 duruyor; "0" yazilmamali
    import dbsnp
    ok("MAF 0 -> '<0.0025' gosterilir", dbsnp.maf_yaz(0) == "<0.0025"
       and dbsnp.maf_yaz(0.015) == "0.015")


def test_nm_surum_uyarisi(c):
    baslik("NM surumu MANE ile uyusmuyor -> uyari")
    # NOBETCI (bulgu 21): refGene surum tutmaz; eski surumle bildirilen varyantin
    # c. numarasi guncel kayitta farkli olabilir. MANE dosyasi surumu bilir.
    def notlar(acc):
        d = c.post("/design_cdna", json={"assembly": "GRCh38", "acc": acc,
                                         "c_position": "c.400"}).get_json() or {}
        return " ".join(d.get("notes") or [])
    ok("NM_000546.5 (MANE .6) -> UYARI", "UYARI: NM_000546.5" in notlar("NM_000546.5"))
    ok("  ...guncel surum (.6) -> uyari yok", "UYARI: NM_000546" not in notlar("NM_000546.6"))
    ok("  ...surumsuz -> uyari yok", "UYARI: NM_000546" not in notlar("NM_000546"))
    d = c.post("/evaluate_cdna", json={"forward": "GCTGAGGAAGTTGGTGACCA", "acc": "NM_000546.4",
                                       "assembly": "GRCh38"}).get_json() or {}
    ok("Degerlendir (RNA) bulgularinda da uyari",
       any("NM_000546.4" in f["text"] and f["level"] == "uyari" for f in d.get("findings") or []))


def test_rna_grch38_hizalama(c, engine):
    baslik("RNA yollari her zaman GRCh38; kodlayan dizisi tutarsiz transkriptte hizalama uyarisi (F-01)")
    # NOBETCI (2026-11-11 degerlendirme F-01): cDNA genom + refGene hizalamasindan kurulur; hizalama
    # boslukluysa c. ve ekson numaralari kayar (TNNI3 c.433C>T "referans baz uyusmuyor", GRCh37'de SRD5A2
    # 6 ekson, C1R 9 ekson). Olcum (MANE Select, kodlayan): isaretli GRCh38 64/18.761, GRCh37 185/18.751.
    def uy(j):
        return [n for n in j.get("notes") or [] if n.startswith(("UYARI", "WARNING"))]

    # birim: uc olcut; ATG disi baslangic ve saglam dizi isaretlenmez
    h = engine._kod_hesapla
    ok("olcut: saglam ATG..TGA isaretsiz", not h("ATGAAATGA")["isaretli"])
    ok("  ...ATG disi baslangic (CTG) isaretsiz", not h("CTGAAATGA")["isaretli"])
    ok("  ...uzunluk 3'un kati degil -> mod3", h("ATGAAATGAC")["nedenler"][0] == "mod3")
    ok("  ...son kodon durdurma degil -> son_kodon", h("ATGAAACCC")["nedenler"] == ["son_kodon"])
    ok("  ...erken durdurma -> erken_durdurma, kodon 2", h("ATGTAAAAATGA")["nedenler"] == ["erken_durdurma"]
       and h("ATGTAAAAATGA")["ilk_durdurma_kodon_no"] == 2)

    for asm in ("GRCh38", "GRCh37"):
        j = c.post("/design_cdna", json={"assembly": asm, "acc": "NM_000363", "c_position": "c.433C>T"}).get_json() or {}
        nt = " | ".join(j.get("notes") or [])
        ok(f"TNNI3 c.433C>T ({asm} secili): hizalama uyarisi", "UYARI: NM_000363" in nt and "erken durdurma" in nt, nt[:200])
        ok("  ...referans baz uyarisi suclamaz, kaymayi soyler", "genom dizisinden kurulan NM_000363" in nt
           and "sizin varyantınızda olmayabilir" in nt)
        ok("  ...girdi derlemesi GRCh38", (j.get("input") or {}).get("assembly") == "GRCh38")
    j = c.post("/design_cdna", json={"assembly": "GRCh37", "acc": "NM_000363", "c_position": "c.433C>T", "lang": "en"}).get_json() or {}
    nt = " | ".join(j.get("notes") or [])
    ok("  ...EN: WARNING + GRCh38 notu", "WARNING: when NM_000363" in nt and "always builds the transcript from the GRCh38" in nt)

    # SRD5A2: GRCh37 secili iken GRCh38 kurulumu (5 ekson, uyari yok, not var)
    j = c.get("/transcript_exons?acc=NM_000348&assembly=GRCh37").get_json() or {}
    ok("SRD5A2 ekson dugmeleri GRCh37 secili: 5 ekson, isaretsiz, GRCh38 notu",
       j.get("exon_count") == 5 and (j.get("kod_denetimi") or {}).get("isaretli") is False and "GRCh38" in (j.get("assembly_note") or ""))
    j = c.post("/design_cdna", json={"assembly": "GRCh37", "acc": "NM_000348", "c_position": "c.680G>A"}).get_json() or {}
    ok("SRD5A2 c.680G>A GRCh37 secili: uyari yok, GRCh38 notu var", not uy(j) and any(n.startswith("Not: RNA sekmesi") for n in j.get("notes") or []))
    j = c.get("/transcript_exons?acc=NM_001733&assembly=GRCh37").get_json() or {}
    ok("C1R ekson dugmeleri GRCh37 secili: 11 ekson", j.get("exon_count") == 11)

    # denetim genleri: uyari yok
    for acc, cp in (("NM_000546", "c.524G>A"), ("NM_000492", "c.1624G>T"), ("NM_007294", "c.181T>G")):
        for asm in ("GRCh38", "GRCh37"):
            j = c.post("/design_cdna", json={"assembly": asm, "acc": acc, "c_position": cp}).get_json() or {}
            ok(f"{acc} {asm} secili: uyari yok", bool(j.get("pairs")) and not uy(j), str(uy(j))[:160])

    # liste ve Degerlendir
    j = c.get("/transcripts?gene=TNNI3&assembly=GRCh37").get_json() or {}
    ok("TNNI3 listesi: GRCh38, NM_000363 isaretli", j.get("assembly") == "GRCh38" and any(
        x["acc"] == "NM_000363" and (x.get("kod_denetimi") or {}).get("isaretli") for x in j.get("transcripts") or []))
    j = c.post("/evaluate_cdna", json={"assembly": "GRCh37", "acc": "NM_000363", "forward": "GCTGAGGAAGTTGGTGACCA"}).get_json() or {}
    ok("Degerlendir RNA TNNI3: hizalama uyarisi (uyari) + GRCh38 notu (bilgi)", j.get("assembly") == "GRCh38" and any(
        f["level"] == "uyari" and "kodlayan bölge tutarsız" in f["text"] for f in j.get("findings") or []) and any(
        f["level"] == "bilgi" and f["text"].startswith("Not: RNA sekmesi") for f in j.get("findings") or []))

    if HTTP:
        return
    # DNA sekmesi: ekzon etiketinde not (GRCh37 + SRD5A2: (a)(c) ve (d); GRCh38 SRD5A2 ve TP53 isaretsiz)
    import transcripts as T

    def etiket(asm, acc):
        tx = T.get_transcript(acc, asm)
        e = tx["exons_tx"][1]
        j = c.post("/design", json={"assembly": asm, "chrom": tx["chrom"], "position": (e[0] + e[1]) // 2, "params": {}}).get_json() or {}
        return [p[a]["gene_region"] for p in j.get("pairs") or [] for a in ("forward", "reverse")
                if (p[a].get("gene_region") or {}).get("acc") == acc]
    g = etiket("GRCh37", "NM_000348")
    ok("DNA GRCh37 SRD5A2: ekzon etiketinde kod_isareti", bool(g) and all(x["kod_isareti"] for x in g))
    g = etiket("GRCh38", "NM_000348")
    ok("DNA GRCh38 SRD5A2: kod_isareti yok", bool(g) and not any(x["kod_isareti"] for x in g))
    g = etiket("GRCh37", "NM_000546")
    ok("DNA GRCh37 TP53: kod_isareti yok", bool(g) and not any(x["kod_isareti"] for x in g))

    # sayim: bütün MANE Select'te isaretlenen GRCh38 sayisi = olculen sayi (olcut_say.py, 2026-11-11: 64 / 18.761)
    mane = T._load_mane()
    n = say = 0
    for acc, (durum, _s) in mane.items():
        if durum != "MANE Select":
            continue
        try:
            tx = T.get_transcript(acc, "GRCh38")
        except T.TranscriptError:
            continue
        if not tx["coding"]:
            continue
        den = engine.kod_denetimi(tx, "GRCh38")
        n += 1
        say += bool(den and den["isaretli"])
    ok("MANE Select GRCh38: isaretlenen = 64 (olculen)", say == 64 and n == 18761, f"{say} / {n}")


def test_coklu_lokus_secimi(c):
    baslik("Birden cok yere hizalanan transkript: GRCh38'de MANE konumuyla lokus (F-02)")
    # NOBETCI (2026-11-11 degerlendirme F-02): _pick_mapping "en uzun yayilim"i seciyordu;
    # GRCh38'de cok satirli 274 MANE transkriptin 168'inde secilen satir MANE konumuyla
    # ortusmuyordu (SMN2 -> SMN1 lokusu ve c.840 = C, U2AF1/CRYAA -> chr21:6 Mb, C4B -> C4A).
    # Beklenti degismedi: yalniz eski yanlis lokusu bekleyen bir test yoktu.
    def cdna(asm, acc, cp, lang="tr"):
        r = c.post("/design_cdna", json={"assembly": asm, "acc": acc, "c_position": cp, "lang": lang})
        return r.get_json() or {}

    def baz(j):
        p = j["pairs"][0]
        return p["amplicon"]["sequence"][p["amplicon"]["variant_span"][0]]

    j = cdna("GRCh38", "NM_017411", "c.840")
    t = j.get("transcript") or {}
    ok("SMN2 GRCh38: chr5 70,0 Mb lokusu", t.get("chrom") == "chr5" and 70_000_000 <= t.get("tx_start", 0) < 70_100_000,
       f"{t.get('chrom')}:{t.get('tx_start')}")
    ok("  ...c.840 bazi T (SMN1'de C)", bool(j.get("pairs")) and baz(j) == "T")
    ok("  ...MANE konumuyla secildi: lokus notu yok", not any("hizalan" in n for n in j.get("notes", [])))
    j = cdna("GRCh38", "NM_000344", "c.840")
    t = j.get("transcript") or {}
    ok("SMN1 GRCh38 degismedi (chr5:70.925.087-70.953.015, c.840 = C)",
       (t.get("chrom"), t.get("tx_start"), t.get("tx_end")) == ("chr5", 70925087, 70953015) and baz(j) == "C")
    for acc, cp, bas, son in (("NM_006758", "c.101C>T", 43_000_000, 43_200_000),
                              ("NM_000394", "c.346C>T", 43_000_000, 43_200_000),
                              ("NM_001002029", "c.100", 32014795, 32035418)):
        t = cdna("GRCh38", acc, cp).get("transcript") or {}
        ok(f"{acc} GRCh38 MANE lokusunda", bas <= t.get("tx_start", 0) and t.get("tx_end", 1 << 60) <= son,
           f"{t.get('chrom')}:{t.get('tx_start')}-{t.get('tx_end')}")
    # GRCh37 secili iken RNA yollari GRCh38 kullanir (K1): SMN2 MANE lokusunda, lokus notu yok, "GRCh38" notu var.
    # (Eskiden bu satirlar GRCh37 icin "en uzun hizalama" lokus notunu bekliyordu; RNA sekmesi artik GRCh37
    # satirlarina hic ulasmadigi icin beklenti degisti. GRCh37 satirinin notu asagida dogrudan sinanir.)
    j37 = cdna("GRCh37", "NM_017411", "c.840")
    t37 = j37.get("transcript") or {}
    ok("SMN2 GRCh37 secili: RNA GRCh38 MANE lokusunu kullanir", (j37.get("input") or {}).get("assembly") == "GRCh38"
       and t37.get("chrom") == "chr5" and 70_000_000 <= t37.get("tx_start", 0) < 70_100_000, str(t37)[:160])
    ok("  ...lokus notu yok, GRCh38 notu var", not any("hizalan" in n for n in j37.get("notes", []))
       and any(n.startswith("Not: RNA sekmesi") for n in j37.get("notes", [])))
    r = c.post("/evaluate_cdna", json={"assembly": "GRCh37", "acc": "NM_017411", "forward": "GCTGAGGAAGTTGGTGACCA"})
    ok("  ...Degerlendir (RNA): GRCh38 notu (bilgi), lokus notu yok",
       any(f["level"] == "bilgi" and f["text"].startswith("Not: RNA sekmesi") for f in (r.get_json() or {}).get("findings", []))
       and not any("hizalan" in f["text"] for f in (r.get_json() or {}).get("findings", [])))
    if not HTTP:
        import transcripts as T37
        tx37 = T37.get_transcript("NM_017411", "GRCh37")
        ok("GRCh37 satiri (get_transcript): lokus notu hala uretilir", bool(tx37.get("locus_note")) and "chr5:" in tx37["locus_note"],
           str(tx37.get("locus_note"))[:160])
    # tek satirli transkriptte not yok
    ok("TP53 (tek satir) GRCh38/GRCh37: lokus notu yok",
       not any("hizalan" in n for a in ("GRCh38", "GRCh37") for n in cdna(a, "NM_000546", "c.215").get("notes", [])))
    if HTTP:
        return
    import transcripts as T
    kon = T._load_mane_konum()
    idx = T._load_index("GRCh38")
    cok = yanlis = yama = 0
    for acc, rows in idx["by_acc"].items():
        if len(rows) < 2:
            continue
        if acc not in kon:
            yama += 1
            ok_ = T._pick_mapping(rows, "GRCh38") is T._en_uzun(rows)       # MANE konumu yok: eski kural
            yanlis += 0 if ok_ else 1
            continue
        cok += 1
        krom, bas, son = kon[acc]
        s = T._pick_mapping(rows, "GRCh38")
        if not (s["chrom"] == krom and s["tx_start"] <= son and s["tx_end"] >= bas):
            yanlis += 1
    ok("GRCh38: cok satirli MANE transkriptlerin hepsi MANE konumuyla ortusen satirda (274)", cok == 274 and yanlis == 0,
       f"cok={cok} yanlis={yanlis}")
    ok("  ...MANE konumu yok/yama iskelesinde olanlar eski kuralla kalir", yama > 0 and yanlis == 0, f"yama={yama}")


def test_performans_saglamlik(engine):
    baslik("Performans ve saglamlik (Paket C)")
    if HTTP:
        return atla("Paket C", "HTTP modu: motorun ici degistirilemez")
    import threading
    import specificity as S
    import downloads
    import transcripts as T

    # NOBETCI (bulgu 14): ayni anda iki tarama 25 surec aciyordu -> tek tarama
    ayni_anda = [0, 0]
    asil = S._scan_genome

    def sahte(*a):
        ayni_anda[0] += 1
        ayni_anda[1] = max(ayni_anda[1], ayni_anda[0])
        time.sleep(0.3)
        ayni_anda[0] -= 1
    S._scan_genome = sahte
    try:
        th = [threading.Thread(target=S.scan_genome, args=(None, "", "", {})) for _ in range(3)]
        [x.start() for x in th]
        [x.join() for x in th]
    finally:
        S._scan_genome = asil
    ok("ozgulluk: ayni anda en fazla 1 genom taramasi", ayni_anda[1] == 1, f"-> {ayni_anda[1]}")

    # NOBETCI (bulgu 16): data_root() her durum sorgusunda diske test dosyasi yaziyordu
    downloads.data_root()
    yazma = []
    gercek_open = open

    def sayan_open(yol, *a, **k):
        if str(yol).endswith(".allprime_yazma_testi"):
            yazma.append(yol)
        return gercek_open(yol, *a, **k)
    downloads.open = sayan_open
    try:
        for _ in range(5):
            downloads.data_root()
    finally:
        del downloads.open
    ok("data_root: tekrar cagrilarda diske test dosyasi yazilmaz", not yazma, f"-> {len(yazma)}")

    if not T.ANNOT_PATHS.get("GRCh38"):
        return atla("Bolge arama / kilit", "GRCh38 transkript tablosu yok")
    # NOBETCI (bulgu 17): ikili arama, kaba taramayla AYNI sonucu vermeli
    import random
    b = T._bolge_indeksi("GRCh38")
    rnd = random.Random(5)
    farkli = 0
    for _ in range(500):
        kr = rnd.choice(list(b.keys()))
        lst = b[kr][1]
        a = rnd.randint(1, lst[-1][1] + 1000)
        e = a + rnd.randint(0, 300)
        kaba = [r for s0, e0, r in lst if s0 <= e and a <= e0]
        farkli += [id(r) for r in T._kesisen_transkriptler(b, kr, a, e)] != [id(r) for r in kaba]
    ok("bolge arama: ikili arama = kaba tarama (500 rastgele sorgu)", farkli == 0, f"-> {farkli}")
    s0, e0, _r = b["M"][1][0]
    ok("mitokondri: 'MT' (motor) refGene'in 'chrM' kaydini bulur",
       (T.konum_bolgesi("GRCh38", "MT", (s0 + e0) // 2) or {}).get("kind") == "ekzon")

    # NOBETCI (bulgu 18): eszamanli ilk istekler refGene'i iki kez okuyordu
    eski = T._INDEX_CACHE.pop("GRCh38")
    eski_bolge = T._BOLGE_CACHE.pop("GRCh38", None)
    okuma = []
    gercek = T._open_maybe_gz

    def sayan(yol, *a, **k):
        okuma.append(yol)
        return gercek(yol, *a, **k)
    T._open_maybe_gz = sayan
    try:
        th = [threading.Thread(target=T._load_index, args=("GRCh38",)) for _ in range(3)]
        [x.start() for x in th]
        [x.join() for x in th]
    finally:
        T._open_maybe_gz = gercek
        T._INDEX_CACHE["GRCh38"] = eski
        if eski_bolge is not None:
            T._BOLGE_CACHE["GRCh38"] = eski_bolge
    ok("refGene: 3 eszamanli ilk istek -> tek okuma", len(okuma) == 1, f"-> {len(okuma)}")


def test_tekrar_suzgeci_her_modda(c, engine):
    baslik("Tekrar dizisi suzgeci butun modlarda")
    # NOBETCI (2026-10-28, inceleme bulgusu 9): suzgec yalnizca Kirilma noktasi
    # sekmesindeydi, tam boy ve tek yon bakiyordu. Artik _rank_order icinde: 3' ucun
    # son 15 bazi, iki iplik.
    s = "ACGTTGCAAGGCTTAACCGGTTACGATCGATGCATGCAAGTC"
    uc = s[-engine.TEKRAR_UC3_NT:]
    ok("tek yer -> 1", engine._tekrar_sayisi(s, s) == 1)
    ok("ters tumleyen kopya da sayilir (F+F riski)",
       engine._tekrar_sayisi(s + "TTTT" + engine.revcomp(uc), s) == 2)
    ok("yalniz 3' ucu ayni kopya da sayilir", engine._tekrar_sayisi(
        s + "GGGG" + "CCCCC" + uc, s) == 2)
    ok("palindrom primer iki kez sayilmaz",     # GAATTCCGGAATTC kendi ters tumleyeni
       engine._tekrar_sayisi("TTGAATTCCGGAATTCAA", "GAATTCCGGAATTC") == 1)

    import random
    rnd = random.Random(11)
    temel = "".join(rnd.choice("ACGT") for _ in range(700))
    # 100-160 arasindaki blogun ters tumleyeni 500'e yerlestirilir: bu bloktaki
    # her primer sablonda iki yere oturur
    sablon = temel[:500] + engine.revcomp(temel[100:160]) + temel[560:]
    d = c.post("/design_sequence", json={"sequence": sablon,
                                         "params": {"product_size_min": 150,
                                                    "product_size_max": 500}}).get_json() or {}
    ciftler = d.get("pairs") or []
    S = sablon.upper()
    ihlal = sum(1 for p in ciftler for u in ("forward", "reverse")
                if engine._tekrar_sayisi(S, p[u]["sequence"]) > 1)
    ok("dizi modu: donen ciftlerde tekrara oturan primer yok", ciftler and ihlal == 0,
       f"-> {len(ciftler)} cift, ihlal {ihlal}")
    ok("  ...elenen aday notu yazilir", any("tekrar dizisi" in n for n in d.get("notes", [])),
       f"-> {d.get('notes')}")


# ------------------------------------------------------------------
# 6) Ozgulluk  (GENOM GEREKIR — en yavas test)
# ------------------------------------------------------------------
def test_ozgulluk(c):
    baslik("Ozgulluk taramasi")
    t0 = time.time()
    r = c.post("/specificity", json={"assembly": "GRCh38",
                                     "forward": "AGAAGCCGTGAGAAGTGA",
                                     "reverse": "ATGATCTAGGTTGTGGTCCT"})
    d = r.get_json()
    sure = time.time() - t0
    ok("istek basarili", r.status_code == 200, f"({sure:.1f} sn)")
    if r.status_code != 200:
        return
    ok("baglanma bolgeleri bulundu", d["binding_sites"]["F"]["toplam"] > 0)
    ok("tarama makul surede biter (<30 sn)", sure < 30, f"{sure:.1f} sn")

# ------------------------------------------------------------------
# Eksik genom kullanilmaz + yanlis derleme reddedilir (v0.8.40; A7-04, A6-02, A6-01)
# ------------------------------------------------------------------
def _yapay_genom(klasor, ad, rnd):
    """1 (2 Mb) ve Y (0,8 Mb) kromozomlu yapay FASTA + .fai; 1'deki 280 bp'lik bolge Y'de de var,
    yani tam genomda bu cift 'Ozgul degil'. Doner: (yol, F, R, hedef, fai_satirlari)."""
    import specificity as S
    r1 = bytearray(rnd.choice(b"ACGT") for _ in range(2_000_000))
    rY = bytearray(rnd.choice(b"ACGT") for _ in range(800_000))
    amp = bytes(r1[500_000:500_280])
    rY[300_000:300_280] = amp
    yol = os.path.join(klasor, ad + ".fa")
    fai = []
    with open(yol, "wb") as f:
        for kr, dz in (("1", bytes(r1)), ("Y", bytes(rY))):
            f.write(b">" + kr.encode() + b"\n")
            ofs = f.tell()
            for i in range(0, len(dz), 70):
                f.write(dz[i:i + 70] + b"\n")
            fai.append(f"{kr}\t{len(dz)}\t{ofs}\t70\t71\n")
    with open(yol + ".fai", "w", newline="\n") as f:
        f.writelines(fai)
    F = amp[:22].decode()
    R = S.revcomp_b(amp[-22:]).decode()
    return yol, F, R, {"chrom": "1", "start": 500_001, "end": 500_280}, fai


def test_genom_eksik_kullanilmaz(c, engine):
    baslik("Kesik / yarim genom kullanilmaz (A7-04, A6-02)")
    if HTTP:
        return atla("Kesik genom", "HTTP modu: motorun ici degistirilemez")
    # NOBETCI (2026-11-09 kapsamli tarama): FASTA kesik ya da .fai yarim olunca acilista uyari
    # uretilip ATILIYORDU; ozgulluk taramasi eksik genomda 'specific: true' diyordu (sessiz yanlis
    # karar). Artik denetimden gecmeyen genom hicbir yolda kullanilmaz ve uyari /health'e gelir.
    import random
    rnd = random.Random(11)
    gecici = tempfile.mkdtemp(prefix="allprime_eksik_")
    eski_yollar = dict(engine.GENOME_PATHS)
    eski_red = dict(engine.GENOME_REJECTED)
    eski_min = engine.MIN_GENOME_BYTES
    eski_cfg = engine.CONFIG_PATH
    eski_kok = os.environ.get("ALLPRIME_APP_ROOT", "")
    try:
        engine.MIN_GENOME_BYTES = 0          # yapay genom 100 MB siniri altinda
        engine.CONFIG_PATH = os.path.join(gecici, "config.json")
        yol0, F, R, hedef, fai = _yapay_genom(gecici, "ham", rnd)
        govde = {"assembly": "GRCh38", "forward": F, "reverse": R, "expected": hedef}
        for ad in ("tam", "kesik", "yarim"):
            kok = os.path.join(gecici, "kok_" + ad)
            gdir = os.path.join(kok, "genomes")
            os.makedirs(gdir, exist_ok=True)
            yol = os.path.join(gdir, "Homo_sapiens.GRCh38.dna.primary_assembly.fa")
            shutil.copy(yol0, yol)
            shutil.copy(yol0 + ".fai", yol + ".fai")
            if ad == "kesik":
                with open(yol, "r+b") as f:
                    f.truncate(int(fai[1].split("\t")[2]) + 50_000)
            if ad == "yarim":
                with open(yol + ".fai", "w", newline="\n") as f:
                    f.write(fai[0])
            # ACILIS yolu: uygulama klasorundeki genomes\ otomatik bulunur
            engine.GENOME_PATHS["GRCh38"] = ""
            engine.GENOME_PATHS["GRCh37"] = ""
            os.environ["ALLPRIME_APP_ROOT"] = kok
            engine.autodetect_genomes()
            r = c.post("/specificity", json=govde)
            j = r.get_json() or {}
            if ad == "tam":
                ok("tam yapay genom: Ozgul degil (Y'de kopya var)",
                   r.status_code == 200 and j.get("specific") is False,
                   f"-> {r.status_code} specific={j.get('specific')}")
                continue
            saglik = c.get("/health?lang=tr").get_json()
            uyari = (saglik.get("genome_warnings") or {}).get("GRCh38")
            ok(f"{ad} genom: uyari /health'e ulasir", bool(uyari), f"-> {(uyari or '')[:50]}")
            ok(f"  ...{ad} genom kullanilabilir sayilmaz",
               saglik["genomes"].get("GRCh38") is False)
            ok(f"  ...{ad} genomla ozgulluk 'Ozgul' demez, anlasilir hata",
               r.status_code == 400 and j.get("specific") is not True and bool(j.get("error")),
               f"-> {r.status_code} {(j.get('error') or '')[:50]} specific={j.get('specific')}")
            r = c.post("/evaluate", json={"forward": F, "reverse": R, "assembly": "GRCh38"})
            j = r.get_json() or {}
            ok(f"  ...{ad} genomla Degerlendir genom taramasi yapmaz",
               r.status_code == 400 and not j.get("genome_used"),
               f"-> {r.status_code} {(j.get('error') or '')[:50]} genome_used={j.get('genome_used')}")
            r = c.post("/kopya_ciftleri", json={"assembly": "GRCh38", "chrom": "1",
                                                "position": 500_100})
            ok(f"  ...{ad} genomla en iyi Ozgul cift aramasi sonuc vermez",
               r.status_code == 400 and bool((r.get_json() or {}).get("error")),
               f"-> {r.status_code}")
            r = c.post("/design", json={"assembly": "GRCh38", "chrom": "1", "position": 500_100})
            ok(f"  ...{ad} genomla tasarim eksik genomdan dizi okumaz",
               r.status_code == 400, f"-> {r.status_code}")
            # elle tanitma (set_genome): ayni kural, uyari yanitta ve 'usable: false'
            engine.GENOME_PATHS["GRCh38"] = ""
            r = c.post("/set_genome", json={"assembly": "GRCh38", "path": yol})
            j = r.get_json() or {}
            ok(f"  ...{ad} genom set_genome: uyari var, kullanilabilir degil",
               r.status_code == 200 and bool(j.get("warning")) and j.get("usable") is False,
               f"-> {r.status_code} usable={j.get('usable')}")
        # .fai/FASTA onarilinca genom yeniden kullanilir
        yol = os.path.join(gecici, "kok_yarim", "genomes",
                           "Homo_sapiens.GRCh38.dna.primary_assembly.fa")
        shutil.copy(yol0 + ".fai", yol + ".fai")
        engine.GENOME_PATHS["GRCh38"] = yol
        r = c.post("/specificity", json=govde)
        ok("onarilan genom yeniden kullanilir", r.status_code == 200 and
           (r.get_json() or {}).get("specific") is False, f"-> {r.status_code}")
    finally:
        engine.MIN_GENOME_BYTES = eski_min
        engine.CONFIG_PATH = eski_cfg
        engine.GENOME_PATHS.clear()
        engine.GENOME_PATHS.update(eski_yollar)
        engine.GENOME_REJECTED.clear()
        engine.GENOME_REJECTED.update(eski_red)
        if eski_kok:
            os.environ["ALLPRIME_APP_ROOT"] = eski_kok
        shutil.rmtree(gecici, ignore_errors=True)


def test_genom_derleme_birim(engine):
    baslik("Genom derlemesi denetimi - .fai uzunluklari (A6-01)")
    f = getattr(engine, "derleme_denetle", None)
    ok("derleme_denetle var", f is not None)
    if f is None:
        return
    gecici = tempfile.mkdtemp(prefix="allprime_derleme_")
    # bilinen uzunluklar (gercek .fai dosyalarindan olculdu, 2026-11-10)
    G37 = {"1": 249250621, "17": 81195210, "X": 155270560}
    G38 = {"1": 248956422, "17": 83257441, "X": 156040895}
    ok("tablo: GRCh37 / GRCh38 uzunluklari", engine.DERLEME_UZUNLUK["GRCh37"] == G37 and
       engine.DERLEME_UZUNLUK["GRCh38"] == G38)

    def fai(ad, uz, onek=""):
        yol = os.path.join(gecici, ad + ".fa")
        with open(yol + ".fai", "w", newline="\n") as o:
            ofs = 56
            for k, n in uz.items():
                o.write(f"{onek}{k}\t{n}\t{ofs}\t60\t61\n")
                ofs += n + n // 60 + 2
        return yol
    try:
        ok("GRCh38 dosyasi GRCh38 yuvasinda: uyumlu",
           f(fai("a", G38), "GRCh38")["durum"] == "uyumlu")
        ok("GRCh37 dosyasi GRCh37 yuvasinda: uyumlu",
           f(fai("b", G37), "GRCh37")["durum"] == "uyumlu")
        d = f(fai("c", G37), "GRCh38")
        ok("GRCh37 dosyasi GRCh38 yuvasinda: karsi derleme", d["durum"] == "karsi" and
           d["karsi"] == "GRCh37", f"-> {d['durum']}")
        d = f(fai("d", G38), "GRCh37")
        ok("GRCh38 dosyasi GRCh37 yuvasinda: karsi derleme", d["durum"] == "karsi" and
           d["karsi"] == "GRCh38")
        ok("chr onekli adlar da taninir",
           f(fai("e", G37, "chr"), "GRCh38")["durum"] == "karsi")
        ok("hicbirine uymayan uzunluk: bilinmiyor (uyariyla kabul)",
           f(fai("g", {"1": 1000, "17": 500, "X": 300}), "GRCh38")["durum"] == "bilinmiyor")
        ok("tanidik kromozom adi yok: bilinmiyor",
           f(fai("h", {"contig_1": 1000}), "GRCh38")["durum"] == "bilinmiyor")
        ok("karisik (biri bu derlemeye, biri oburune uyar): bilinmiyor",
           f(fai("i", {"1": G38["1"], "17": G37["17"]}), "GRCh38")["durum"] == "bilinmiyor")
        ok(".fai yoksa denetlenemez ('yok'), reddedilmez",
           f(os.path.join(gecici, "yok.fa"), "GRCh38")["durum"] == "yok")
        import lang
        try:
            lang.set_lang("en")
            m_en = engine.derleme_karsi_mesaji("GRCh38", f(fai("c", G37), "GRCh38"))
            lang.set_lang("tr")
            m_tr = engine.derleme_karsi_mesaji("GRCh38", f(fai("c", G37), "GRCh38"))
        finally:
            lang.set_lang("tr")
        ok("red mesaji EN: benzedigi derleme + olculen uzunluk",
           "GRCh37" in m_en and "249,250,621" in m_en and "GRCh38" in m_en, f"-> {m_en[:70]}")
        ok("red mesaji TR: benzedigi derleme + olculen uzunluk",
           "GRCh37" in m_tr and "249.250.621" in m_tr and "GRCh38" in m_tr, f"-> {m_tr[:70]}")
    finally:
        shutil.rmtree(gecici, ignore_errors=True)


def test_genom_tamlik(c, engine):
    baslik("Eksik ya da kesik genom 'Ozgul' dedirtmez: ana kromozom tamligi (D3-04)")
    # NOBETCI (2026-11-10 kapsamli tarama D3-04, Kritik): .fai yokken kesik FASTA'nin ilk /design
    # istegi .fai'yi kesik dosyadan kuruyordu; dosya kendi icinde tutarli gorundugu icin 0.8.40
    # engeli devreye girmiyor, /specificity 200 "Ozgul" diyordu. Artik 1-22, X, Y, MT .fai'de
    # bilinen uzunlukta olmali; yoksa ya da farkliysa (obur derleme degilse) genom kullanilmaz.
    # Denetim yalniz .fai'yi okur; yalniz TAMLIK_MIN_BYTES (100 MB) ve ustu dosyalara uygulanir (testlerin
    # kucuk yapay genomlari bu yuzden etkilenmez; kucuk dosya zaten genome_check'te reddedilir).
    import specificity as S
    import lang
    gecici = tempfile.mkdtemp(prefix="allprime_tamlik_")
    eski_min = engine.TAMLIK_MIN_BYTES
    eski_yollar = dict(engine.GENOME_PATHS)
    eski_red = dict(engine.GENOME_REJECTED)
    A = engine.ANA_KROMOZOM_UZUNLUK
    fasta = os.path.join(gecici, "g.fa")
    try:
        # 1) tablolar: DERLEME_UZUNLUK alt kume; gercek .fai'lerle birebir (varsa)
        ok("DERLEME_UZUNLUK, ANA_KROMOZOM_UZUNLUK'un alt kumesi",
           all(A[a][k] == v for a in A for k, v in engine.DERLEME_UZUNLUK[a].items()))
        ok("ana kromozomlar: 1-22, X, Y (24 kayit) iki derlemede",
           all(len(A[a]) == 24 and "Y" in A[a] for a in A))
        for asm in ("GRCh37", "GRCh38"):
            yol = eski_yollar.get(asm) or ""
            if yol and os.path.exists(yol + ".fai"):
                gercek = {}
                with open(yol + ".fai", encoding="utf-8") as o:
                    for sat in o:
                        k = sat.split("\t")
                        gercek[k[0]] = int(k[1])
                ok(f"{asm}: tablo bu makinedeki gercek .fai ile birebir",
                   all(gercek.get(k) == v for k, v in A[asm].items()) and
                   gercek.get("MT") in engine.MT_UZUNLUK[asm])
        with open(fasta, "w") as o:
            o.write(">1\nACGT\n")

        def fai(uz, onek="", mt=16569, mt_ad="MT"):
            with open(fasta + ".fai", "w", newline="\n") as o:
                for k, n in uz.items():
                    o.write(f"{onek}{k}\t{n}\t56\t60\t61\n")
                if mt is not None:
                    o.write(f"{onek if mt_ad == 'MT' else ''}{mt_ad}\t{mt}\t56\t60\t61\n")
            engine._DERLEME_ONBELLEK.pop(fasta, None)

        def msg(asm, dil="tr"):
            lang.set_lang(dil)
            try:
                return engine.tamlik_mesaji(fasta, asm)
            finally:
                lang.set_lang("tr")
        engine.TAMLIK_MIN_BYTES = 0          # kucuk dosya "gercek boyutlu" sayilsin
        # 2) tam genomlar gecer
        for asm in ("GRCh37", "GRCh38"):
            fai(A[asm])
            ok(f"{asm}: tam .fai engellenmez", msg(asm) is None)
            fai(A[asm], onek="chr", mt_ad="M")
            ok(f"{asm}: chr oneki ve chrM adi taninir", msg(asm) is None)
        # Kullanici karari (2026-11-10): mitokondri yalniz rCRS (16.569); hg19'un eski chrM'si (16.571) rCRS degil
        fai(A["GRCh37"], mt=16571)
        m = msg("GRCh37") or ""
        ok("GRCh37: MT 16.571 bp (UCSC hg19 eski chrM) kabul EDILMEZ; mesaj rCRS'yi soyler",
           "rCRS" in m and "16.571" in m and "kullanılmadı" in m and "kesik" not in m, f"-> {m[:140]}")
        m_en = msg("GRCh37", "en") or ""
        ok("  ...EN mesaj", "rCRS" in m_en and "16,571" in m_en and "not used" in m_en, f"-> {m_en[:120]}")
        uz = dict(A["GRCh37"])
        uz.pop("Y")
        fai(uz, mt=16571)
        m = msg("GRCh37") or ""
        ok("GRCh37: Y yok + eski chrM: genel mesaj + rCRS ipucu", "chrY" in m and "rCRS" in m, f"-> {m[:140]}")
        fai(A["GRCh38"], mt=16571)
        ok("GRCh38: MT 16.571 bp kabul EDILMEZ", "chrMT" in (msg("GRCh38") or ""))
        fai({**A["GRCh38"], "KI270728.1": 1872759, "chrUn_xyz": 5}, mt=16569)
        ok("alt/random/Un contig'ler denetime katilmaz (ekstra kayit sorun degil)", msg("GRCh38") is None)
        # 3) eksik / kesik
        uz = dict(A["GRCh38"])
        uz.pop("Y")
        fai(uz)
        m = msg("GRCh38") or ""
        ok("Y yok: engel; mesaj Y'yi ve erkek ornekte yan urun kacmasini soyler",
           "chrY" in m and "yok" in m and "erkek" in m, f"-> {m[:120]}")
        m_en = msg("GRCh38", "en") or ""
        ok("  ...EN mesaj", "chrY" in m_en and "male sample" in m_en and "incomplete or truncated" in m_en)
        uz = dict(A["GRCh38"])
        uz["X"] = 101640
        fai(uz)
        m = msg("GRCh38") or ""
        ok("X kesik: 'chrX bekleniyor 156.040.895 bp, dosyada 101.640 bp'",
           "chrX bekleniyor 156.040.895 bp, dosyada 101.640 bp" in m and "kullanılmadı" in m,
           f"-> {m[:150]}")
        fai(A["GRCh38"], mt=None)
        ok("MT yok: engel", "chrMT" in (msg("GRCh38") or ""))
        fai({k: v for k, v in A["GRCh38"].items() if k in ("1", "17", "X")})
        ok("yalniz 1, 17, X var (eski denetimi gecerdi): engel", msg("GRCh38") is not None)
        fai({"contig_1": 1000})
        ok("tanidik ad yok: engel", msg("GRCh38") is not None)
        # 4) obur derlemenin uzunluklari: yanlis derleme davranisi (bu denetim sorun SAYMAZ)
        fai(A["GRCh37"])
        ok("GRCh37 uzunluklari GRCh38 yuvasinda: tamlik engeli degil, 'karsi' derleme",
           msg("GRCh38") is None and engine.derleme_denetle(fasta, "GRCh38")["durum"] == "karsi")
        # 5) genom_uyarisi / genom_durumu / genome_check
        uz = dict(A["GRCh38"])
        uz["X"] = 101640
        fai(uz)
        eski_denetle = S.fai_denetle
        S.fai_denetle = lambda yol, ornek=25: "tamam"      # .fai bu FASTA'ya ait sayilsin
        try:
            engelli, uyari = engine.genom_uyarisi(fasta, "GRCh38")
            ok("genom_uyarisi: eksik genom engelli", engelli and "bekleniyor" in (uyari or ""))
            engine.GENOME_PATHS["GRCh38"] = fasta
            ok("genom_durumu (kayitli yol: ortam degiskeni / config.json / elle): engelli",
               engine.genom_durumu("GRCh38")["engelli"] is True)
            eski_gmin = engine.MIN_GENOME_BYTES
            engine.MIN_GENOME_BYTES = 0
            try:
                ok("genome_check: kayit ok ama usable=False",
                   engine.genome_check(fasta, "GRCh38").get("usable") is False)
            finally:
                engine.MIN_GENOME_BYTES = eski_gmin
        finally:
            S.fai_denetle = eski_denetle
        # 6) .fai FASTA ile kendi icinde tutarli olsa bile (specificity yolu) fai_engeli engeller
        with open(fasta, "w", newline="\n") as o:
            o.write(">1\n" + "A" * 60 + "\n")
        with open(fasta + ".fai", "w", newline="\n") as o:
            o.write("1\t60\t3\t60\t61\n")
        engine._DERLEME_ONBELLEK.pop(fasta, None)
        ok("kendi icinde tutarli kesik .fai: fai_denetle 'tamam' ama fai_engeli engeller",
           S.fai_denetle(fasta) == "tamam" and "eksik ya da kesik" in (S.fai_engeli(fasta) or ""))
        try:
            S.read_fai(fasta)
            ok("read_fai kesik genomu okumaz (acik mesaj)", False)
        except S.SpecificityError as e:
            ok("read_fai kesik genomu okumaz (acik mesaj)", "kullanılmadı" in str(e))
        engine.TAMLIK_MIN_BYTES = eski_min
        ok("TAMLIK_MIN_BYTES altindaki yapay genom etkilenmez (test genomlari calismaya devam)",
           S.fai_engeli(fasta) is None and bool(S.read_fai(fasta)))
        # 7) .fai yoksa denetlenemez; ilk kullanimda kurulunca hemen denetlenir
        os.remove(fasta + ".fai")
        engine.TAMLIK_MIN_BYTES = 0
        ok(".fai yok: tamlik_mesaji None (denetlenemez)", engine.tamlik_mesaji(fasta, "GRCh38") is None)
        engine.GENOME_PATHS["GRCh38"] = fasta
        engine._FASTA_CACHE.pop(fasta, None)
        try:
            engine.fetch_sequence_local("GRCh38", "1", 1, 4)
            ok(".fai ilk kez kurulunca genom hemen denetlenir (kesik: PrimerError)", False)
        except engine.PrimerError as e:
            ok(".fai ilk kez kurulunca genom hemen denetlenir (kesik: PrimerError)",
               "eksik ya da kesik" in str(e) and os.path.exists(fasta + ".fai"), f"-> {str(e)[:70]}")
        engine._FASTA_CACHE.pop(fasta, None)
        # 8) hiz: .fai imzasiyla onbellek (ikinci cagri dosyayi acmaz)
        engine._DERLEME_ONBELLEK.pop(fasta, None)
        a1 = engine._fai_uzunluklari(fasta)
        a2 = engine._fai_uzunluklari(fasta)
        ok(".fai uzunluklari imzayla onbelleklenir", a1 is a2 and a1 is not None)
        # 9) ortam degiskeni ile gelen kucuk dosya kayda girmez
        engine.TAMLIK_MIN_BYTES = eski_min
        engine.GENOME_PATHS["GRCh38"] = fasta
        engine.ortam_genomlarini_denetle()
        ok("ortam degiskeniyle gelen kucuk dosya kayda girmez; sebep saklanir",
           not engine.GENOME_PATHS.get("GRCh38") and fasta in engine.GENOME_REJECTED)
    finally:
        engine.TAMLIK_MIN_BYTES = eski_min
        lang.set_lang("tr")
        engine.GENOME_PATHS.clear()
        engine.GENOME_PATHS.update(eski_yollar)
        engine.GENOME_REJECTED.clear()
        engine.GENOME_REJECTED.update(eski_red)
        engine._FASTA_CACHE.pop(fasta, None)
        shutil.rmtree(gecici, ignore_errors=True)


def test_genom_derleme_gercek(c, engine):
    baslik("Yanlis derleme FASTA'si reddedilir - gercek genomlar (A6-01)")
    if HTTP:
        return atla("Yanlis derleme", "HTTP modu: motorun ici degistirilemez")
    g37 = engine.GENOME_PATHS.get("GRCh37") or ""
    g38 = engine.GENOME_PATHS.get("GRCh38") or ""
    if not (g37 and g38 and os.path.exists(g37) and os.path.exists(g38)):
        return atla("Yanlis derleme", "iki genom da gerekli")
    gecici = tempfile.mkdtemp(prefix="allprime_derleme_")
    eski_yollar = dict(engine.GENOME_PATHS)
    eski_red = dict(engine.GENOME_REJECTED)
    eski_cfg = engine.CONFIG_PATH
    eski_kok = os.environ.get("ALLPRIME_APP_ROOT", "")
    try:
        engine.CONFIG_PATH = os.path.join(gecici, "config.json")
        # 1) elle tanitma: GRCh37 FASTA'si GRCh38 yuvasina -> 400, kayit ve config degismez
        r = c.post("/set_genome", json={"assembly": "GRCh38", "path": g37, "lang": "en"})
        j = r.get_json() or {}
        ok("GRCh37 FASTA'si GRCh38 yuvasina: 400", r.status_code == 400, f"-> {r.status_code}")
        ok("  ...hata hangi derlemeye benzedigini ve uzunlugu soyler",
           "GRCh37" in (j.get("error") or "") and "249,250,621" in (j.get("error") or ""),
           f"-> {(j.get('error') or '')[:80]}")
        ok("  ...kayit degismedi", engine.GENOME_PATHS.get("GRCh38") == g38)
        ok("  ...config.json'a yazilmadi", not os.path.exists(engine.CONFIG_PATH))
        r = c.post("/set_genome", json={"assembly": "GRCh37", "path": g38})
        ok("GRCh38 FASTA'si GRCh37 yuvasina: 400", r.status_code == 400 and
           engine.GENOME_PATHS.get("GRCh37") == g37, f"-> {r.status_code}")
        # 2) dogru eslesme etkilenmez: uyarisiz, kullanilabilir
        for asm, yol in (("GRCh38", g38), ("GRCh37", g37)):
            r = c.post("/set_genome", json={"assembly": asm, "path": yol})
            j = r.get_json() or {}
            ok(f"dogru {asm} dosyasi kabul: uyarisiz ve kullanilabilir",
               r.status_code == 200 and not j.get("warning") and j.get("usable") is True,
               f"-> {r.status_code} {j.get('warning')} usable={j.get('usable')}")
        # 3) acilista config'den okunan yanlis derleme de reddedilir
        with open(engine.CONFIG_PATH, "w", encoding="utf-8") as o:
            json.dump({"genomes": {"GRCh38": g37, "GRCh37": ""}}, o)
        engine.GENOME_PATHS["GRCh38"] = ""
        engine.load_config()
        ok("config'den okunan yanlis derleme kaydedilmez", not engine.GENOME_PATHS.get("GRCh38"))
        ok("  ...reddi sebebiyle saklanir", "GRCh37" in (engine.GENOME_REJECTED.get(g37) or ""))
        # 4) acilista otomatik bulunan yanlis adli dosya. Derleme yalniz .fai uzunluguna bakar;
        #    3 GB kopyalamamak icin kucuk bir FASTA + GERCEK GRCh37 .fai'si kullanilir.
        kok = os.path.join(gecici, "kok")
        gdir = os.path.join(kok, "genomes")
        os.makedirs(gdir)
        hedef = os.path.join(gdir, "Homo_sapiens.GRCh38.dna.primary_assembly.fa")
        with open(hedef, "w", encoding="utf-8") as o:
            o.write(">1\nACGT\n")
        shutil.copy(g37 + ".fai", hedef + ".fai")
        eski_min = engine.MIN_GENOME_BYTES
        engine.MIN_GENOME_BYTES = 0
        try:
            engine.GENOME_PATHS["GRCh38"] = ""
            engine.GENOME_REJECTED.clear()
            os.environ["ALLPRIME_APP_ROOT"] = kok
            engine.autodetect_genomes()
        finally:
            engine.MIN_GENOME_BYTES = eski_min
        ok("otomatik bulunan yanlis derleme kaydedilmez",
           engine.GENOME_PATHS.get("GRCh38") != hedef)
        ok("  ...reddi sebebiyle saklanir",
           "GRCh37" in (engine.GENOME_REJECTED.get(hedef) or ""))
    finally:
        os.environ["ALLPRIME_APP_ROOT"] = eski_kok
        engine.CONFIG_PATH = eski_cfg
        engine.GENOME_PATHS.clear()
        engine.GENOME_PATHS.update(eski_yollar)
        engine.GENOME_REJECTED.clear()
        engine.GENOME_REJECTED.update(eski_red)
        shutil.rmtree(gecici, ignore_errors=True)



def test_dup_yedegi_ve_mane_yonu(c, engine):
    baslik("Kirilma noktasi: dup boy farki yedegi + onerilen pay (A4-01/02), MANE gen yonu (A5-01)")
    # NOBETCI (2026-11-10 kapsamli tarama): (1) varsayilan ayarla 100-220 bp duplikasyonda
    # (boy farki yolu) urun penceresi 436-500 bp'ye daraldigi icin 6 lokusun 2-3'unde cift
    # cikmiyordu; birlesim yolundaki gibi sinirsiz pencereyle yedek denenir ve bant sinirini
    # asabilecegi UYARI ile soylenir. (2) refGene satirlari mane_status tasimadigi icin
    # "MANE oncelikli" gen yonu kurali hic calismiyordu; zit yonlu genle ortusen urunde
    # (TP53 ekzon 1 + WRAP53, PKD1 3') yon "?" cikip F/R yer degisimi uyarisi susuyordu.
    if not engine.GENOME_PATHS.get("GRCh38"):
        atla("dup yedegi / MANE yonu", "GRCh38 genomu yok")
        return

    def bp(asm, ch, bas, D, tip, lang="tr", **prm):
        r = c.post("/design_breakpoint", json={"assembly": asm, "chrom": ch, "start": bas,
                                               "end": bas + D - 1, "type": tip, "params": prm,
                                               "lang": lang})
        return r.get_json() or {}

    bos, say, fark, yedek = 0, 0, 0, 0
    for D in (120, 160, 200, 220):
        for asm, ch, b in (("GRCh38", "7", 117559000), ("GRCh38", "17", 43070000),
                           ("GRCh38", "2", 100000000), ("GRCh38", "5", 70000000)):
            d = bp(asm, ch, b, D, "dup")
            say += 1
            if not d.get("num_returned"):
                bos += 1
                continue
            yedek += any(n.startswith("UYARI: Bant") for n in d.get("notes", []))
            fark += sum(1 for p in d["pairs"] if p["bp"]["dup"] - p["bp"]["wt"] != D)
    ok(f"100-220 bp dup (boy farki yolu), varsayilan ayar: bos hucre yok ({bos}/{say})", bos == 0)
    ok("  ...yedek tasarimda bant farki duplikasyon boyuna esit", fark == 0 and yedek > 0,
       f"-> sapan {fark}, yedek {yedek}")
    d = bp("GRCh38", "7", 117559000, 200, "dup")
    uy = [n for n in d.get("notes", []) if n.startswith("UYARI: Bant")]
    ok("  ...D=200: yedek 'bant sinirini asabilir' diye uyarir ve sinir yukseltmeyi onerir",
       d.get("input", {}).get("approach") == "size_shift" and len(uy) == 1 and "yükseltin" in uy[0],
       f"-> {uy[0][-90:] if uy else ''}")
    # onerilen pay: EN metinde de sayi motorla denenmis olmali
    d = bp("GRCh38", "7", 117559000, 400, "del", lang="en", bp_margin=200)
    uy = [n for n in d.get("notes", []) if n.startswith("WARNING: The band may be")]
    mm = re.search(r"reduced to ±([\d,]+) bp", uy[0]) if uy else None
    if mm:
        d2 = bp("GRCh38", "7", 117559000, 400, "del", lang="en", bp_margin=int(mm.group(1).replace(",", "")))
        ok("EN: onerilen pay uyarisiz ve ciftli", d2.get("pairs") and
           not any(n.startswith("WARNING: The band may be") for n in d2.get("notes", [])))
    else:
        ok("EN: sayi onerilmediyse sinir yukseltme yazar", bool(uy) and "to at least" in uy[0], f"-> {uy[:1]}")

    import evaluate
    for asm in ("GRCh38", "GRCh37"):
        tx = [t for v in evaluate._gene_index(asm).values() for t in v]
        n = sum(1 for t in tx if t.get("mane_status"))
        ok(f"{asm}: refGene satirlarinda MANE isareti dolu ({n}/{len(tx)})", n > 15000)
    g = evaluate._urun_geni("GRCh38", "17", 7687300, 7687500)
    ok("TP53 ekzon 1 (eksi iplik, WRAP53 ile ortusur): (TP53, -)", g == ("TP53", "-"), f"-> {g}")
    import server
    F, R = "AGGGTGTGTGCTGCCATTAC", "GGGTCTGGCTGGACTAAAGG"        # PKD1 3' (eksi iplik, MANE)
    s = {"input": {"chrom": "16"}, "pairs": [{"forward": {"genomic_start": 2092888, "genomic_end": 2092907},
                                              "reverse": {"genomic_start": 2093241, "genomic_end": 2093260}}]}
    server._gen_yonu_ekle(s, "GRCh38")
    ok("PKD1: sunucu ve Degerlendir ayni (gen, yon) verir ve yon belli",
       (s["pairs"][0]["strand_gene"], s["pairs"][0]["gene_strand"]) == evaluate._urun_geni("GRCh38", "16", 2092888, 2093260)
       and s["pairs"][0]["gene_strand"] == "-", f"-> {s['pairs'][0].get('strand_gene')} {s['pairs'][0].get('gene_strand')}")
    sw = []
    for x, y in ((F, R), (R, F)):
        e = c.post("/evaluate", json={"assembly": "GRCh38", "forward": x, "reverse": y}).get_json() or {}
        sw.append(bool(e.get("pair_roles_swapped")))
    ok("PKD1 cifti iki sirada girilince tam birinde 'roller yer degismis' uyarisi", sw.count(True) == 1, f"-> {sw}")


def test_nc_surumu_ve_pay0(c, engine):
    baslik("RefSeq surum eki secili derlemeyle karsilastirilir (D3-02); kisa dup'ta pay 0 onerilir (D3-01)")
    # NOBETCI (2026-11-10): NC_000017.10 (GRCh37 erisimi) GRCh38 seciliyken, NC_000017.11 GRCh37
    # seciliyken uyarisiz kabul ediliyordu. GRCh38 surumleri yerel MANE dosyasindan; GRCh37 icin
    # yerelde dogrulanabilir liste yok: yalniz GRCh38'in surumu reddedilir, baska surum kabul.
    import transcripts
    ref = transcripts.grch38_kromozom_erisimleri()
    ok("MANE'den GRCh38 erisimleri: 17 -> NC_000017.11, X -> NC_000023.11, 24 kromozom",
       ref.get("17") == ("NC_000017", 11) and ref.get("X") == ("NC_000023", 11) and len(ref) == 24,
       f"-> {ref.get('17')} {ref.get('X')} {len(ref)}")
    G = [("GRCh38", "17", "NC_000017.10:7676154", True), ("GRCh38", "17", "NC_000017.10:g.7676154", True),
         ("GRCh38", "17", "NC_000017.12:7676154", True), ("GRCh37", "17", "NC_000017.11:7579472", True),
         ("GRCh38", "X", "NC_000023.10:100000000", True), ("GRCh37", "X", "NC_000023.11:100000000", True),
         ("GRCh38", "17", "NC_000017.11:7676154", False), ("GRCh37", "17", "NC_000017.10:7579472", False),
         ("GRCh37", "17", "NC_000017.9:7579472", False), ("GRCh38", "17", "NC_000017:7676154", False),
         ("GRCh37", "17", "nc_000017:7579472", False), ("GRCh38", "17", "chr17:7676154", False),
         ("GRCh38", "MT", "NC_012920.1:3000", False), ("GRCh37", "MT", "NC_012920.1:3000", False)]
    for asm, krom, kon, red in G:
        try:
            engine.erisim_surumu_denetimi(kon, asm)
            ok(f"birim: {asm} + {kon!r} {'reddedilir' if red else 'kabul'}", not red, "-> kabul edildi")
        except engine.PrimerError as e:
            ok(f"birim: {asm} + {kon!r} {'reddedilir' if red else 'kabul'}", red, f"-> {str(e)[:80]}")
    # uc nokta: tasarim, kirilma noktasi baslangic ve bitis; iki dil
    for lang, iz in (("tr", "seçili derleme"), ("en", "selected assembly")):
        for asm, kon in (("GRCh38", "NC_000017.10:7676154"), ("GRCh37", "NC_000017.11:7579472")):
            ikinci = {"GRCh38": ("NC_000017.10:7676154", "7677154"), "GRCh37": ("NC_000017.11:7579472", "7580472")}[asm]
            r = c.post("/design", json={"assembly": asm, "chrom": "17", "position": kon, "lang": lang})
            j = r.get_json() or {}
            ok(f"{asm} {lang}: /design '{kon}' -> 400, NC_ numarasi mesajda, cift yok",
               r.status_code == 400 and kon.split(":")[0] in j.get("error", "") and not j.get("pairs"),
               f"-> {r.status_code} {str(j.get('error'))[:80]}")
            if asm == "GRCh38":
                ok(f"{asm} {lang}: mesaj derlemeyi ve GRCh37 olasiligini soyler",
                   iz in j.get("error", "") and "GRCh37" in j.get("error", ""))
            for alan, deger in (("start", ikinci[0]), ("end", ikinci[0])):
                g = {"assembly": asm, "chrom": "17", "type": "del", "lang": lang,
                     "start": "7676154" if asm == "GRCh38" else "7579472", "end": "7677154" if asm == "GRCh38" else "7580472"}
                g[alan] = deger
                r = c.post("/design_breakpoint", json=g)
                j = r.get_json() or {}
                ok(f"{asm} {lang}: /design_breakpoint {alan}={deger!r} -> 400",
                   r.status_code == 400 and deger.split(":")[0] in j.get("error", "") and not j.get("pairs"),
                   f"-> {r.status_code}")
    # sozlesme: bugunku kabuller bozulmadi
    for asm, kon in (("GRCh38", "NC_000017.11:7676154"), ("GRCh37", "NC_000017.10:7579472")):
        r = c.post("/design", json={"assembly": asm, "chrom": "17", "position": kon})
        ok(f"{asm}: '{kon}' -> 200 ve cift var", r.status_code == 200 and (r.get_json() or {}).get("pairs"),
           f"-> {r.status_code}")
    # D3-01: kisa duplikasyonda kuramsal ust sinir negatif; pay 0 iken cift ve sinir ici bant var
    import re
    for asm, krom, bas, D, m in (("GRCh37", "19", 44908000, 250, 139), ("GRCh37", "19", 44908000, 250, 80),
                                 ("GRCh37", "5", 70000000, 500, 139)):
        pr = {"bp_margin": m}
        r = c.post("/design_breakpoint", json={"assembly": asm, "chrom": krom, "start": bas, "end": bas + D - 1,
                                               "type": "dup", "params": pr, "lang": "en"})
        j = r.get_json() or {}
        txt = " ".join(j.get("notes", []))
        ok(f"{asm} chr{krom} dup {D} bp margin {m}: not 'did not give a design' DEMEZ, pay 0 onerir",
           r.status_code == 200 and "did not give a design" not in txt and "margin 0" in txt,
           f"-> {r.status_code} {txt[-160:]}")
        r0 = c.post("/design_breakpoint", json={"assembly": asm, "chrom": krom, "start": bas, "end": bas + D - 1,
                                                "type": "dup", "params": {"bp_margin": 0}, "lang": "en"})
        j0 = r0.get_json() or {}
        ok("  ...onerilen pay (0) uygulaninca cift var ve 'Bant ... uzayabilir' uyarisi yok",
           r0.status_code == 200 and j0.get("pairs") and not any(
               n.startswith("WARNING: The band may be") for n in j0.get("notes", [])), f"-> {r0.status_code}")
    # pay 0 da calismiyorsa eski dogru mesaj korunur (GRCh38 chr1:155000000 dup 300 bp, margin 139)
    r = c.post("/design_breakpoint", json={"assembly": "GRCh38", "chrom": "1", "start": 155000000,
                                           "end": 155000299, "type": "dup", "params": {"bp_margin": 139}, "lang": "en"})
    j = r.get_json() or {}
    txt = " ".join(j.get("notes", []))
    r0 = c.post("/design_breakpoint", json={"assembly": "GRCh38", "chrom": "1", "start": 155000000,
                                            "end": 155000299, "type": "dup", "params": {"bp_margin": 0}, "lang": "en"})
    j0 = r0.get_json() or {}
    u0 = (not j0.get("pairs")) or any(n.startswith("WARNING: The band may be") for n in j0.get("notes", []))
    ok("pay 0'da da uyarili bolgede 'payi kucultmek de vermedi' notu dogru kalir",
       "did not give a design" in txt and u0, f"-> {txt[-120:]} u0={u0}")
    # TR notu da anlamli
    r = c.post("/design_breakpoint", json={"assembly": "GRCh37", "chrom": "19", "start": 44908000,
                                           "end": 44908249, "type": "dup", "params": {"bp_margin": 139}, "lang": "tr"})
    txt = " ".join((r.get_json() or {}).get("notes", []))
    ok("TR: pay 0 notu 'kırılma noktaları tam biliniyorsa' der", "kırılma noktaları tam biliniyorsa" in txt,
       f"-> {txt[-160:]}")


def test_coklu_fasta_reddi(c, engine):
    baslik("Coklu FASTA kaydi reddedilir - sessiz birlestirme yok (A3-01)")
    # NOBETCI (2026-11-10 kapsamli tarama): iki FASTA kaydi sessizce tek diziye birlestiriliyor,
    # birlesme noktasini kapsayan gercekte olmayan urunler cikiyordu (tek uyari "baslik yok
    # sayildi"). Dizi icerigi olan birden cok kayit varsa tasarim yapilmaz; tek kayit ve icerigi
    # olmayan ikinci baslik eskisi gibi calisir. Iki dizi modunda her kutu icin ayni kural.
    import random
    r = random.Random(5)
    s1 = "".join(r.choice("ACGT") for _ in range(300))
    s2 = "".join(r.choice("ACGT") for _ in range(300))
    for lang, kayit_kelimesi in (("tr", "FASTA kaydı"), ("en", "FASTA records")):
        def post(uc, govde):
            x = c.post(uc, json=dict(govde, lang=lang))
            return x.status_code, (x.get_json() or {})
        k, j = post("/design_sequence", {"sequence": f">a\n{s1}\n>b\n{s2}\n"})
        ok(f"{lang}: 2 kayit -> 400, sayi + FASTA yazili, cift yok", k == 400 and "2" in j.get("error", "")
           and kayit_kelimesi in j.get("error", "") and not j.get("pairs"), f"-> {k} {str(j.get('error'))[:60]}")
        k, j = post("/design_sequence", {"sequence": f">a\n{s1}\n>b\n{s2}\n>c\n{s1}"})
        ok(f"{lang}: 3 kayit -> 400 ve '3'", k == 400 and "3" in j.get("error", ""), f"-> {k}")
        k, j = post("/design_sequence", {"sequence": f"{s1}\n>b\n{s2}"})
        ok(f"{lang}: basliksiz ilk parca + baslikli kayit = 2 kayit -> 400", k == 400, f"-> {k}")
        k, j = post("/design_sequence", {"sequence": f">a\n{s1}\n"})
        ok(f"{lang}: tek baslikli tek kayit -> 200 + baslik notu", k == 200 and j.get("pairs")
           and any("FASTA" in n for n in j.get("notes", [])), f"-> {k}")
        k, j = post("/design_sequence", {"sequence": f">a\n{s1}\n>bos\n\n"})
        ok(f"{lang}: ikinci baslik dizisiz -> tek kayit, 200", k == 200, f"-> {k}")
        k, j = post("/design_sequence_pair", {"forward": f">a\n{s1}\n>b\n{s2}", "reverse": s2})
        ok(f"{lang}: iki dizi, forward kutusunda 2 kayit -> 400 + Forward", k == 400 and "Forward" in j.get("error", "")
           and "2" in j.get("error", ""), f"-> {k}")
        k, j = post("/design_sequence_pair", {"forward": s1, "reverse": f">a\n{s1}\n>b\n{s2}"})
        ok(f"{lang}: iki dizi, reverse kutusunda 2 kayit -> 400 + Reverse", k == 400 and "Reverse" in j.get("error", ""),
           f"-> {k}")
        k, j = post("/design_sequence_pair", {"forward": f">f\n{s1}", "reverse": f">r\n{s2}"})
        ok(f"{lang}: iki dizi, her kutuda tek kayit -> 200", k == 200, f"-> {k}")


def test_konum_oneki_celiskisi(c, engine):
    baslik("Konum oneki kromozom alaniyla celisirse tasarim yapilmaz (A1-01)")
    # NOBETCI (2026-11-10 kapsamli tarama): kromozom alaninda 17 varken konuma "chr2:..." yazilinca
    # onek sessizce atiliyor, tasarim chr17'de yapiliyordu. Artik iki kromozomu da adiyla soyleyen
    # hata doner; ayni kromozom ("chr17:" ile 17) sessizce kabul edilir.
    ok("konum_oneki: 'chr2:5-9' -> 2, '5' -> None, '17:5' -> 17",
       engine.konum_oneki("chr2:5-9") == "2" and engine.konum_oneki("5") is None
       and engine.konum_oneki("17:5") == "17" and engine.konum_oneki("chrx : 5") == "X")
    for onek, kutu in (("chr2:", "17"), ("2:", "17"), ("chrX:", "17"), ("chr7:", "chr17"), ("chr17:", "7")):
        try:
            engine.kromozom_celiskisi(engine.konum_oneki(onek + "7676154"), kutu)
            ok(f"birim: {onek!r} + kutu {kutu!r} celisir", False, "-> kabul edildi")
        except engine.PrimerError as e:
            a, b = engine.normalize_chrom(onek.rstrip(":")), engine.normalize_chrom(kutu)
            ok(f"birim: {onek!r} + kutu {kutu!r} celisir", f"chr{a}" in str(e) and f"chr{b}" in str(e))
    engine.kromozom_celiskisi(engine.konum_oneki("chr17:7676154"), "17")
    engine.kromozom_celiskisi(engine.konum_oneki("7676154"), "17")
    ok("birim: ayni kromozom ve onceksiz konum hata vermez", True)
    # RefSeq kromozom erisim numarasi (NC_...) kromozoma eslenir; taninmayan onek ayri mesaj alir
    ok("konum_oneki: NC_000017.11 -> 17, nc_000023.11 -> X, NC_012920.1 -> MT",
       engine.konum_oneki("NC_000017.11:7676154") == "17" and engine.konum_oneki("nc_000023.11:5") == "X"
       and engine.konum_oneki("NC_012920.1:5") == "MT")
    engine.kromozom_celiskisi(engine.konum_oneki("NC_000017.11:7676154"), "17")
    ok("birim: NC_000017.11 + kutu 17 hata vermez", True)
    try:
        engine.kromozom_celiskisi(engine.konum_oneki("NC_000002.12:7676154"), "17")
        ok("birim: NC_000002.12 + kutu 17 celisir", False, "-> kabul edildi")
    except engine.PrimerError as e:
        ok("birim: NC_000002.12 + kutu 17 celisir", "chr2" in str(e) and "chr17" in str(e))
    try:
        engine.kromozom_celiskisi(engine.konum_oneki("abc:123"), "17")
        ok("birim: taninmayan onek 'abc' hata verir", False, "-> kabul edildi")
    except engine.PrimerError as e:
        ok("birim: taninmayan onek 'abc' hata verir, 'chrabc' demez", "abc" in str(e) and "chrabc" not in str(e))
    r1 = c.post("/design", json={"assembly": "GRCh38", "chrom": "17", "position": "7676154"})
    r2 = c.post("/design", json={"assembly": "GRCh38", "chrom": "17", "position": "NC_000017.11:7676154"})
    cift = lambda r: [(p["forward"]["sequence"], p["reverse"]["sequence"]) for p in (r.get_json() or {}).get("pairs", [])]
    ok("GRCh38: 'NC_000017.11:7676154' + kutu 17 -> 200, onceksizle ayni",
       r2.status_code == 200 and cift(r2) and cift(r2) == cift(r1), f"-> {r2.status_code}")
    for asm, kon in (("GRCh38", "7676154"), ("GRCh37", "7579472")):
        k0 = c.post("/design", json={"assembly": asm, "chrom": "17", "position": kon})
        j0 = k0.get_json() or {}
        taban = [(p["forward"]["sequence"], p["reverse"]["sequence"]) for p in j0.get("pairs", [])]
        ok(f"{asm} onceksiz taban 200 ve cift var", k0.status_code == 200 and taban)
        for lang in ("tr", "en"):
            for kutu, onek in (("17", "chr2:"), ("17", "2:"), ("chr17", "chr7:"), ("7", "chr17:")):
                r = c.post("/design", json={"assembly": asm, "chrom": kutu, "position": onek + kon, "lang": lang})
                j = r.get_json() or {}
                a, b = engine.normalize_chrom(onek.rstrip(":")), engine.normalize_chrom(kutu)
                ok(f"{asm} {lang}: kutu {kutu!r} + {onek + kon!r} -> 400, iki kromozom adi, cift yok",
                   r.status_code == 400 and f"chr{a}" in j.get("error", "") and f"chr{b}" in j.get("error", "")
                   and not j.get("pairs"), f"-> {r.status_code}")
            for kutu, onek in (("17", "chr17:"), ("chr17", "17:")):
                r = c.post("/design", json={"assembly": asm, "chrom": kutu, "position": onek + kon, "lang": lang})
                j = r.get_json() or {}
                ok(f"{asm} {lang}: kutu {kutu!r} + {onek + kon!r} -> 200, onceksizle ayni",
                   r.status_code == 200 and [(p["forward"]["sequence"], p["reverse"]["sequence"])
                                              for p in j.get("pairs", [])] == taban, f"-> {r.status_code}")
    r = c.post("/design", json={"assembly": "GRCh38", "chrom": "17", "position": "chr2:7676154-7676200"})
    ok("aralik 'chr2:a-b' + kutu 17 -> 400", r.status_code == 400, f"-> {r.status_code}")
    r = c.post("/design", json={"assembly": "GRCh38", "gene": "TP53", "position": "chr2:7676154"})
    ok("gen=TP53 (kromozom bos, gen chr17) + 'chr2:' -> 400", r.status_code == 400, f"-> {r.status_code}")
    bp = {"assembly": "GRCh38", "chrom": "7", "start": "117559000", "end": "117559399", "type": "del"}
    r0 = c.post("/design_breakpoint", json=bp)
    for alan in ("start", "end"):
        r = c.post("/design_breakpoint", json=dict(bp, **{alan: "chr2:" + bp[alan]}))
        ok(f"kirilma noktasi {alan}='chr2:...' + kromozom 7 -> 400", r.status_code == 400, f"-> {r.status_code}")
    r = c.post("/design_breakpoint", json=dict(bp, start="chr7:117559000", end="7:117559399"))
    ok("kirilma noktasi ayni kromozom oneki kabul, onceksizle ayni cift",
       r.status_code == 200 and r0.status_code == 200 and
       [p["forward"]["sequence"] for p in r.get_json()["pairs"]] == [p["forward"]["sequence"] for p in r0.get_json()["pairs"]],
       f"-> {r.status_code}")


# ------------------------------------------------------------------
def test_k6_kucuk_duzeltmeler(c, engine, annot_var):
    baslik("Duzeltme 3 / K6: sayi okuma, binlik ayraci, BOM, indirme hatasi dili, NC_ g. ve aralik")
    # NOBETCI (2026-11-10, K6): ust simge rakam / 4.300+ basamak 500 "Beklenmeyen hata" veriyordu
    # (A1-02, A4-05, A3-05, A1-03); "1.500" 1,5 okunuyordu (D1-05); BOM'lu FASTA "gecersiz karakter >"
    # (D3-05); requests hata metni Turkce arayuzde Ingilizce kaliyordu (E1-04); NC_...:g.POS ve NC_
    # aralik reddediliyordu (E1-01).
    import ayarlar
    import downloads
    import requests
    # 1) sayi okuma: PrimerError (400), 500 degil
    for dil in ("tr", "en"):
        def hata(uc, govde):
            x = c.post(uc, json=dict(govde, lang=dil))
            return x.status_code, (x.get_json() or {}).get("error", "")
        for ad, uc, g in (
                ("design ust simge", "/design", {"assembly": "GRCh38", "chrom": "17", "position": "7676154²"}),
                ("design 4400 hane", "/design", {"assembly": "GRCh38", "chrom": "17", "position": "7" * 4400}),
                ("kirilma baslangic ust simge", "/design_breakpoint",
                 {"assembly": "GRCh38", "chrom": "7", "start": "117559000²", "end": "117559500", "type": "del"}),
                ("kirilma bitis 4400 hane", "/design_breakpoint",
                 {"assembly": "GRCh38", "chrom": "7", "start": "117559000", "end": "1" * 4400, "type": "del"}),
                ("dizi hedef 4400 hane", "/design_sequence", {"sequence": "ACGT" * 150, "target": "7" * 4400})):
            k, e = hata(uc, g)
            ok(f"[{dil}] {ad}: 400, 'Beklenmeyen hata' yok, mesaj kisa",
               k == 400 and "Beklenmeyen" not in e and "Unexpected" not in e and len(e) < 400, f"-> {k} {e[:70]}")
        # /specificity expected: tarama oncesi 400 (genom olmasa da once okunur ya da genom 400'u gelir)
        k, e = hata("/specificity", {"forward": "AGAAGCCGTGAGAAGTGA", "reverse": "GGTAGGTTTTCTGGGAAGGG",
                                     "assembly": "GRCh38", "expected": {"chrom": "17", "start": "abc", "end": 1}})
        ok(f"[{dil}] specificity bozuk expected.start: 400", k == 400 and "Beklenmeyen" not in e and "Unexpected" not in e,
           f"-> {k} {e[:70]}")
    for deger, beklenen in ((7676154, 7676154), ("7.676.154", 7676154), (" 7 676 154 ", 7676154), ("-5", -5)):
        ok(f"_sayi({deger!r}) = {beklenen}", engine._sayi(deger) == beklenen)
    for kotu in ("7676154²", "٣٤", "7" * 4400, "1e6", ""):
        try:
            engine._sayi(kotu)
            ok(f"_sayi({kotu[:12]!r}) PrimerError", False)
        except engine.PrimerError:
            ok(f"_sayi({kotu[:12]!r}) PrimerError", True)
        except Exception as e:
            ok(f"_sayi({kotu[:12]!r}) PrimerError", False, f"-> {type(e).__name__}")
    # 2) binlik ayraci: tam sayi ayarlarda "1.500" = 1500; ondalik ayar etkilenmez; mesaj yazilani gosterir
    ay = lambda **kw: ayarlar.birlestir([engine.DEFAULTS], kw, ayarlar.TASARIM_SINIRLARI)
    ok("pcr_max '1.500' ve '1,500' = 1500, '100.000' = 100000",
       ay(pcr_max="1.500")["pcr_max"] == 1500 and ay(pcr_max="1,500")["pcr_max"] == 1500
       and ay(pcr_max="100.000")["pcr_max"] == 100000)
    ok("ondalik ayar (Mg 1.500) 1,5 kalir", abs(ay(salt_divalent="1.500")["salt_divalent"] - 1.5) < 1e-9)
    ok("sayi olarak gelen 1500 degismez", ay(pcr_max=1500)["pcr_max"] == 1500)
    for dil in ("tr", "en"):
        import lang as _lang
        _lang.set_lang(dil)
        try:
            ay(pcr_max="0.050")
            ok(f"[{dil}] pcr_max '0.050' reddedilir", False)
        except ayarlar.AyarHatasi as e:
            ok(f"[{dil}] pcr_max '0.050' reddedilir, mesaj yazilani aynen gosterir", "0.050" in str(e), f"-> {e}")
    _lang.set_lang("tr")
    # 3) BOM'lu FASTA
    s, _hedef, _nt = engine.parse_sequence_input("﻿>seq1\nACGTTGCAAGGCTTCAGTCAGGATCCATTGCA\n")
    ok("BOM'lu tek kayitli FASTA ayristirilir", s == "ACGTTGCAAGGCTTCAGTCAGGATCCATTGCA")
    try:
        engine.parse_sequence_input("﻿")
        ok("yalniz BOM bos dizi sayilir", False)
    except engine.PrimerError:
        ok("yalniz BOM bos dizi sayilir", True)
    # 7) indirme hatasi: iki dilli aciklama (gercek aga cikilmaz; istisnalar elle uretilir)
    yanit = requests.Response()
    yanit.status_code = 404
    h404 = requests.HTTPError("404 Client Error: Not Found for url: https://x/y", response=yanit)
    m = downloads._ag_hatasi(h404)
    ok("404: Turkce 'bulunamadı' + kod, Ingilizce 'not found' + kod",
       m is not None and "404" in m.tr and "bulunamadı" in m.tr and "404" in m.en and "not found" in m.en
       and m.tr.startswith("Sunucu") and m.en.startswith("The server"), f"-> {m and m.tr[:60]}")
    ok("yanitsiz HTTPError: kod mesajdan okunur", "503" in downloads._ag_hatasi(
        requests.HTTPError("503 Server Error: Service Unavailable for url: https://x")).tr)
    ok("baglanti hatasi: 'Bağlantı kurulamadı' / 'Could not connect'",
       "Bağlantı kurulamadı" in downloads._ag_hatasi(requests.ConnectionError("x")).tr
       and "Could not connect" in downloads._ag_hatasi(requests.ConnectionError("x")).en)
    ok("zaman asimi (ConnectTimeout dahil): 'zaman aşımı' / 'timed out'",
       all("zaman aşımı" in downloads._ag_hatasi(e).tr and "timed out" in downloads._ag_hatasi(e).en
           for e in (requests.ReadTimeout("x"), requests.ConnectTimeout("x"))))
    ok("ag disi istisna: None (eski davranis)", downloads._ag_hatasi(OSError("disk")) is None)
    # 8) NC_ ...:g.POS ve NC_ aralik = chr17 karsiligi (genom gerekmez: ayristirma)
    ok("NC_000017.11:g.7676154 -> (7676154, 7676154)", engine.varyant_araligi("NC_000017.11:g.7676154") == (7676154, 7676154))
    ok("NC_ aralik, g. aralik ve HGVS alt cizgi = chr17 araligi",
       all(engine.varyant_araligi(x) == (7676154, 7676160) == engine.varyant_araligi("chr17:7676154-7676160")
           for x in ("NC_000017.11:7676154-7676160", "NC_000017.11:g.7676154-7676160", "NC_000017.11:g.7676154_7676160")))
    ok("NC_ onek kromozomu hala NC_'den okunur", engine.konum_oneki("NC_000017.11:g.7676154") == "17")
    for dil in ("tr", "en"):
        if annot_var:          # RefSeq surum denetimi yerel MANE dosyasina dayanir
            x = c.post("/design", json={"assembly": "GRCh38", "chrom": "17", "position": "NC_000017.10:g.7676154", "lang": dil})
            e = (x.get_json() or {}).get("error", "")
            ok(f"[{dil}] g. oneki surum denetimini atlatmaz (GRCh37 erisimi GRCh38'de)",
               x.status_code == 400 and "NC_000017.10" in e, f"-> {x.status_code} {e[:70]}")
        x = c.post("/design", json={"assembly": "GRCh38", "chrom": "18", "position": "NC_000017.11:g.7676154", "lang": dil})
        ok(f"[{dil}] g. onekli konum kromozom celiskisini yine yakalar", x.status_code == 400, f"-> {x.status_code}")


def test_k6_rna_hedef(c, engine):
    baslik("Duzeltme 3 / K6: Degerlendir RNA hedefi - referans baz uyarisi, tek primerde gecersiz hedef")
    # NOBETCI (2026-11-10, K6): c.215 A>G (bosluklu) yazimda referans baz uyarisi yoktu (E1-03);
    # Degerlendir RNA modunda c. hedefinde hic denetim yoktu (A2-01 acigi); tek primer + gecersiz
    # hedef sessizce yok sayiliyordu, cift primerde 400 veriyordu (E1-02).
    import transcripts as T
    asm, acc = "GRCh38", "NM_000546.6"
    tx = T.get_transcript(acc, asm)
    T._annotate_cdna(tx)
    cd = engine.build_cdna(tx, asm)[0]
    co = tx["cds_offset"]
    gercek = cd[co + 214]
    yanlis = "ACGT".replace(gercek, "")[0]
    alt = [x for x in "ACGT" if x not in (gercek, yanlis)][0]
    ok("c_referans_uyarisi: bosluklu yanlis uyarir, bosluklu dogru uyarmaz",
       bool(T.c_referans_uyarisi(tx, f"c.215 {yanlis}>{alt}", cd)) and bool(T.c_referans_uyarisi(tx, f"c.215 {yanlis} > {alt}", cd))
       and not T.c_referans_uyarisi(tx, f"c.215 {gercek}>{alt}", cd))
    comp = str.maketrans("ACGT", "TGCA")
    f_ = cd[co + 150: co + 170]
    r_ = cd[co + 400: co + 420].translate(comp)[::-1]
    uy = lambda j: [x for x in (j.get("findings") or []) if "uyuşmuyor" in x["text"] or "does not match" in x["text"]]
    for dil in ("tr", "en"):
        def ev(forward, reverse, hedef):
            g = {"forward": forward, "acc": acc, "assembly": asm, "target": hedef, "lang": dil}
            if reverse:
                g["reverse"] = reverse
            x = c.post("/evaluate_cdna", json=g)
            return x.status_code, (x.get_json() or {})
        for ad, rev, hedef, bek in (("cift, yanlis baz", r_, f"c.215{yanlis}>{alt}", True),
                                    ("cift, bosluklu yanlis baz", r_, f"c.215 {yanlis}>{alt}", True),
                                    ("tek primer, yanlis baz", None, f"c.215{yanlis}>{alt}", True),
                                    ("cift, dogru baz", r_, f"c.215{gercek}>{alt}", False),
                                    ("cift, yalniz konum", r_, "c.215", False)):
            k, j = ev(f_, rev, hedef)
            u = uy(j)
            ok(f"[{dil}] Degerlendir RNA {ad}: uyari {'var' if bek else 'yok'}",
               k == 200 and bool(u) == bek and (not u or u[0]["level"] == "uyari"), f"-> {k} {[x['text'][:40] for x in u]}")
        for hedef in ("c.9999", "chr17:7676154", "xyz"):
            kt, _ = ev(f_, None, hedef)
            kc, _ = ev(f_, r_, hedef)
            ok(f"[{dil}] tek primer + gecersiz hedef {hedef!r}: cift primerle ayni 400", kt == 400 == kc, f"-> tek {kt} cift {kc}")
        kt, _ = ev(f_, None, "c.215")
        ok(f"[{dil}] tek primer + gecerli hedef: 200", kt == 200)


def main():
    print("AllPrime - duman testi", flush=True)
    print(f"uygulama klasoru: {os.environ['ALLPRIME_APP_ROOT']}", flush=True)

    import engine
    global HTTP, EXE_YOLU
    surec = None
    arg = sys.argv[1:]
    if "--exe" in arg:
        EXE_YOLU = os.path.abspath(arg[arg.index("--exe") + 1])
        surec, url, token = _exe_baslat(EXE_YOLU)
        HTTP = {"url": url, "token": token}
    elif "--url" in arg:
        HTTP = {"url": arg[arg.index("--url") + 1],
                "token": arg[arg.index("--token") + 1] if "--token" in arg else ""}
    if HTTP:
        print(f"HEDEF: {HTTP['url']} (HTTP; surec ici testler atlanir)", flush=True)
        c = _HttpIstemci(HTTP["url"], HTTP["token"])
    else:
        import server
        c = server.app.test_client()
    try:
        return _testler(c, engine)
    finally:
        if surec:
            surec.terminate()
            surec.wait(30)


def _testler(c, engine):

    saglik = c.get("/health").get_json()
    genom_var = bool(saglik["genomes"].get("GRCh38"))
    annot_var = bool(saglik["annotations"].get("GRCh38")) and \
        bool(saglik["annotations"].get("mane"))

    baslik("Saglik")
    ok("motor cevap veriyor", saglik.get("status") == "ok")
    print(f"  genomlar : {saglik['genomes']}", flush=True)
    print(f"  annotasyon: {saglik['annotations']}", flush=True)
    print(f"  dbSNP    : {saglik['dbsnp']}", flush=True)

    # --- veri gerektirmeyenler ---
    test_genom_dogrulama(engine)
    test_genom_derleme_birim(engine)
    test_genom_tamlik(c, engine)
    test_genom_eksik_kullanilmaz(c, engine)
    test_gz_genom_reddi(c, engine)
    test_coklu_fasta_reddi(c, engine)
    test_k6_kucuk_duzeltmeler(c, engine, annot_var)
    test_parametre_dogrulama(c) if genom_var else atla(
        "Tutarsiz ayarlar", "genom yok (istek dizi cekmeye kadar gidiyor)")
    test_bos_sonuc_aciklamasi(c, engine)
    test_tm_opt_kaldirildi(c, engine)
    test_rna_tohum_uzunlugu(c, engine)     # genom varsa gercek transkriptle de
    test_yuksek_riskli_yan_urun_karari(c)
    test_primer3_saglik(c, engine)
    test_v051_genomsuz(c)
    test_par_sinirlari(c)
    test_snp_3uc_uzakligi(engine)
    test_atomik_veri_dosyalari(engine)
    test_indirme_devami(engine)
    test_indirme_dili(engine)
    test_dizi_ucu_sebebi(c, engine)
    test_degerlendir_fai_yok(c, engine)
    test_ayar_sinirlari(c)
    test_erisim_denetimi(c)
    test_ceviri_ve_mane(c, engine)
    test_turkce_harfler_ve_ensembl_hatasi(engine)
    test_tekrar_suzgeci_her_modda(c, engine)
    test_performans_saglamlik(engine)
    test_paket_e_kucuk(c)
    test_govde_tipleri(c)
    test_yanlis_sebep(c)
    test_csv_bicimi(c)
    test_hedefsiz_uzun_dizi(c)
    test_arayuz_bicimi(c)
    test_telif_gorunur(c)
    test_kaynak_zip(c)
    test_lisans_surumu(c)
    test_lisans_paragrafi(c)
    test_bilgilendirme_ekrani(c)
    test_bilgilendirme_kaydi(c)
    test_veri_kaynaklari_belgesi(c)
    test_claude_dagitima_girmez(c)
    test_tm_kosul_notu(c)
    test_gorsel_duzen(c)
    test_ayarlar_ekrani(c)
    test_oto_rozet_durumu(c)
    test_oto_kontrol_sonradan(c)
    test_yakin_not_metni(c)
    test_gen_yonu_gorunum(c)
    test_favoriler(c)
    test_igv_konum(c)
    test_v0866_favori_csv_ve_degerlendir(c)
    test_v0866_binlik(c, engine, genom_var, annot_var)
    test_v100_sayfa_sureci_cokerse()
    test_degerlendir_urun_yonu(c)
    test_menu_kisayollari(c)
    test_kurulum_degerlendir(c)
    test_k8_kucuk_duzeltmeler(c)
    test_kurulu_arayuz_dosyalari(c)
    test_eski_ad_yok(c)
    test_ayar_klasoru_tasinir(engine)
    test_eski_dbsnp_indeksi(engine)
    test_openblas_ortami()
    test_kurulu_temizlik(c)

    # --- veri gerektirenler ---
    if genom_var:
        test_set_genome_ucu(c, engine)
        test_genom_derleme_gercek(c, engine)
        test_konum_oneki_celiskisi(c, engine)
        test_nc_surumu_ve_pay0(c, engine)
        test_girdi_reddi(c)
        test_degerlendirme(c)
        test_k8_tek_primer(c)
        test_degerlendir_pcr_siniri(c)
        test_yakin_kopya_notu(c, engine)
        test_yakin_rozet_notu(c, engine)
        test_hairpin_uyarisi(c, engine)
        test_degerlendir_k3(c, engine, annot_var)
        test_urun_hedef_isareti(c)
        test_cok_tarama(c)
        test_kopya_ciftleri(c)
        test_bolge_etiketleri(c)
        test_ters_takilmis_cift(c)
        test_iplik_yonu(c)
        test_hedef_urun(c)
        test_kirpilmis_liste_bulgulari(c, engine)
        test_es_kopya_hedef(c, engine)
        test_v051_genomlu(c, engine)
        test_par_degerlendirme(c, engine)
        test_kirilma_noktasi(c, engine)
        test_kontrol_obur_uc(c, engine)
        test_kontrol_hairpin(c, engine)
        test_urun_gc_araligi(c)
        test_varyant_araligi(c, engine)
        test_aday_havuzu(c, engine)
        test_gen_bolgesi(c, engine)
        test_paralog_uyarisi(c, engine) if annot_var else atla(
            "Paralog uyarisi", "transkript tablosu yok")
        test_tekrar_dizisi_siniri(c, engine)
        test_havuz_olagan_kapanir(c, engine)
        test_kromozom_disi_koordinat(c, engine)
        test_gen_adi_yerelden(c, engine)
        test_uc_durumlar(c, engine)
        test_seed_kor_noktasi(c, engine)
        test_genomsuz_degerlendirme(c, engine)
        test_ozgulluk(c)
    else:
        for ad in ("/set_genome dogrulamasi", "Hatali girdi reddi",
                   "Degerlendirme sekmesi", "F/R yer degistirmis cift",
                   "Genom yokken degerlendirme", "Ozgulluk taramasi"):
            atla(ad, "yerel genom tanitilmamis")

    if genom_var and annot_var:
        test_tasarim(c)
        test_ekson_secimi(c)
        test_rna_degerlendirme(c)
        test_amplikon(c)
        test_3uc_gc_siniri(c)
        test_amplikon_gc(c)
        test_rna_varyant_araligi(c, engine)
        test_rna_transkript_ucu(c, engine)
        test_nm_surum_uyarisi(c)
        test_konum_ayristirma(c, engine)
        test_uzun_transkript_suresi(c)
        test_bozuk_veri_dosyalari(c)
        test_eski_fai(c, engine)
        test_tablo_bozuk_dna(c)
        test_c_konum_uclari(c)
        test_c_referans_baz(c)
        test_k6_rna_hedef(c, engine)
        test_gen_yonu_adlari(c)
        test_kapanista_isci_kalmaz(c)
        test_psodogen_ekzon_uyarisi(c)
        test_dup_yedegi_ve_mane_yonu(c, engine)
        test_coklu_lokus_secimi(c)
        test_rna_grch38_hizalama(c, engine)
    else:
        atla("Tasarim modlari", "genom veya annotasyon dosyasi yok")
        atla("RNA degerlendirmesi", "genom veya annotasyon dosyasi yok")
        atla("Amplikon dizisi", "genom veya annotasyon dosyasi yok")
        atla("3' uc GC siniri", "genom yok")
        atla("Amplikon GC", "genom yok")
        atla("RNA varyant araligi", "genom veya annotasyon dosyasi yok")
        atla("RNA transkript ucu", "genom veya annotasyon dosyasi yok")

    print(f"\n{'=' * 60}", flush=True)
    print(f"GECTI: {gecti}   BASARISIZ: {basarisiz}   ATLANDI: {atlandi}", flush=True)
    if _hatalar:
        print("Basarisiz olanlar:", flush=True)
        for h in _hatalar:
            print(f"  - {h}", flush=True)
    print(f"{'=' * 60}", flush=True)
    return 1 if basarisiz else 0


if __name__ == "__main__":
    # Windows: ozgulluk taramasi coklu surec kullanir, spawn bu dosyayi yeniden
    # import eder. Bu koruma olmadan her isci butun testleri bastan calistirir.
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
