# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""
AllPrime - Ozgulluk Kontrolu
==============================
Bir primer CIFTININ genom uzerinde istenmeyen urun verip vermedigini bulur.

Neden BLAST degil:
  - BLAT 18-24 nt primerler icin uygun degil (kisa eslesmeleri kacirir).
  - BLAST dogru arac ama primer BASINA cevap verir; bizim sorumuz CIFT bazinda
    ("kac tane yan urun amplikonu cikar"), yani ciftlestirme mantigini zaten
    kendimiz yazmak zorundayiz. Ustelik genom basina ~5 GB veritabani ve
    20-40 dk kurulum gerektiriyor.

Yaklasim (seed-and-extend):
  1) Uzama SADECE 3' uc oturmussa gerceklesir. Bu yuzden primerin son N bazini
     (seed) genomda TAM eslesme olarak arariz - bu ucuz ve hizli.
  2) Her seed vurusunda primerin tamamini hizalayip uyumsuzluk sayariz; esigi
     asan bolge elenir.
  3) Kalan baglanma bolgelerini YONLERINE gore ciftleriz: '+' yonlu bir bolge ile
     onun sagindaki '-' yonlu bir bolge, aralarindaki mesafe makul ise bir yan urun
     olusturur. F+F ve R+R kombinasyonlari da kontrol edilir (gercek risk).

Olcum (bu makinede, GRCh37): tek desen tam genom taramasi ~6 sn tek islemci ile;
kromozom bazinda paralellestirilince cift basina ~1-2 sn.
"""

import os
import re
import threading
import multiprocessing as mp

import ayarlar
import par
from lang import t, tr_sayi

# Yerel modul; GENOME_PATHS'i engine ile paylasmak icin ge­cikmeli import edilir
# (engine -> specificity yonunde bagimlilik var, tersi yok).

SPEC_DEFAULTS = {
    # 3' uctan kac baz TAM eslesmeli (uzamanin on kosulu).
    #
    # 8 idi, 6'ya indirildi. Sebep olculdu: 8 baz sarti biyolojik olarak fazla
    # katiydi. Uzamayi belirleyen asil sey son 2-3 bazdir; 3' uctan 7-8 baz
    # geride kalan bir uyumsuzluk primerin baglanip uzamasini cogu zaman
    # engellemez. 8 sarti bu bolgeleri HIC gostermiyordu.
    #
    # Gercek bir cift (DLL3) ile olcum - hepsi zaten max_mismatch<=4 bütçesine
    # uyan, yani gostermemiz gereken bolgeler:
    #     seed 8 -> 3.6 sn, 15 urun     (eski)
    #     seed 7 -> 3.6 sn, 30 urun
    #     seed 6 -> 4.1 sn, 49 urun     (secilen)
    #     seed 5 -> 8.8 sn, 99 urun
    # 6'ya inmek yarim saniyeye mal oluyor, bulunan urunu uce katliyor.
    # Daha da dusurmek istenirse 5 de kabul edilebilir (dugmeyle tetikleniyor),
    # ama maliyet iki katina cikiyor.
    "seed_len": 6,
    "max_mismatch": 4,          # primerin tamaminda izin verilen toplam uyumsuzluk
    "max_offtarget_product": 3000,   # bu bp'den uzun "urun" pratikte cogalmaz

    # --- Kaynak sinirlari -----------------------------------------------------
    # Eskiden tek bir sinir vardi ve PARCA basina uygulaniyordu (16 Mbp'lik her
    # dilimde 200 bin). Poli-A gibi bir primer her dilimde siniri doldurdugu
    # icin toplam isabet yuz milyonlara cikti: test sureci 23,8 GB bellege
    # ulasip durduruldu (2026-10-01, makinede 15,6 GB var). Uygulama kullanicinin
    # bilgisayarini kilitleyebiliyordu. Artik sinirlar GENEL ve asildiginda
    # sessizce kirpilmiyor; "tekrar dizisi, tahmin yapilamadi" olarak bildiriliyor.
    #
    # Olculen degerler (ana surec bellegi):
    #     normal cift (DLL3)           ~5 bin yer/primer,   49 urun        ~70 MB
    #     Alu primeri (1022 tam yer)   565 bin yer,         242 bin urun   ~260 MB
    #     chr7 uydu tekrari            195 bin + 142 bin,   2,09 milyon    ~890 MB
    # Sinirlar Alu vakasini bozmayacak, chr7 ve poli-A'yi durduracak sekilde secildi.
    "max_sites_per_primer": 1_000_000,  # primer basina toplam baglanma yeri (~190 MB)
    "max_sites_per_task": 100_000,      # TEK dilimde (16 Mbp) bu kadar yer = kesin tekrar;
                                        # isci basina bellegi de sinirlar
    "max_products": 500_000,            # urun eslestirme siniri (~180 MB)
    "workers": 0,               # 0 = otomatik (cekirdek sayisina gore)
    # Parca boyu: isci basina bellek ~ bunun 3 kati. 16 Mbp -> ~50 MB/isci,
    # 12 isci ile ~600 MB. Kromozomun tamamini almak 12 GB'a cikip takasa sokuyordu.
    "chunk_bases": 16_000_000,
    "report_limit": 25,         # arayuze donen yan urun sayisi siniri

    # --- Risk siniflandirmasi -------------------------------------------------
    # 3' uc zaten TAM eslesiyor (seed kosulu), dolayisiyla ayirt edici olan
    # geri kalan uyumsuzluk sayisidir. Iki baglanma bolgesinin TOPLAMI esas alinir:
    # 20 bazlik bir primerde 3-4 uyumsuzluk pratikte cogalmayi durdurur, ama
    # 0-2 uyumsuzlukla oturan bir cift gercek yan urun verir.
    "risk_high_max": 2,         # toplam uyumsuzluk <= 2  -> yuksek risk
    "risk_medium_max": 5,       # 3..5                    -> orta
}                               # 6+                      -> dusuk

_COMPLEMENT = bytes.maketrans(b"ACGTNacgtnRYKMSWBDHVrykmswbdhv",
                              b"TGCANtgcanYRMKSWVHDByrmkswvhdb")


class SpecificityError(Exception):
    """Kullaniciya gosterilebilir ozgulluk hatasi."""
    pass


def revcomp_b(seq: bytes) -> bytes:
    return seq.translate(_COMPLEMENT)[::-1]


# ------------------------------------------------------------------
# FASTA indeksi (.fai) okuma - pyfaidx'e gerek yok, satirlar bize lazim
# ------------------------------------------------------------------
_FAI_DURUM = {}          # fasta yolu -> (dosya imzalari, durum)


def _dosya_imzasi(yol):
    try:
        st = os.stat(yol)
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def fai_imzasi(fasta_path):
    """FASTA ve .fai'nin (boyut, degisme zamani) ikilisi: dosyalar degisti mi?"""
    return (_dosya_imzasi(fasta_path), _dosya_imzasi(fasta_path + ".fai"))


def fai_denetle(fasta_path, ornek=25):
    """.fai bu FASTA dosyasina gercekten ait mi?
    Doner: "yok" | "uyusmuyor" | "kesik" | "yarim" | "tamam".

    pyfaidx (rebuild=False) ve read_fai indeksi OLDUGU GIBI kullanir. FASTA sonradan
    degismis ama eski .fai kalmissa (satir uzunlugu farkli bir dosya, ayni adla baska
    bir surum) ofsetler kayar ve okunan diziler SESSIZCE yanlis olur: eski .fai'li yapay
    genomda 10 cift tasarlandi, hicbiri gercek diziyle eslesmedi (2026-10-31 hata
    taramasi). Kayitlardan bir ornekte (ilk, son ve aradakiler) ofsetten hemen once
    '>ad' baslik satiri ve ilk satirin indeksteki yerde bitmesi aranir: birkac kucuk okuma.
      uyusmuyor: indeks bu dosyaya ait degil; okunan dizi yanlis olur, kullanilmamali
      kesik:     kayitlar dogru ama FASTA indeksin gosterdiginden kisa (yarim kopya)
      yarim:     kayitlar dogru ama indeks dosyanin sonuna ulasmiyor (son kayitlar eksik)
    Sonuc dosya imzasina gore onbellekte tutulur; dosya degisince yeniden denetlenir."""
    if not os.path.exists(fasta_path + ".fai"):
        return "yok"
    imza = fai_imzasi(fasta_path)
    eski = _FAI_DURUM.get(fasta_path)
    if eski and eski[0] == imza:
        return eski[1]
    durum = _fai_denetle_ham(fasta_path, ornek)
    _FAI_DURUM[fasta_path] = (imza, durum)
    return durum


def _fai_denetle_ham(fasta_path, ornek):
    try:
        boyut = os.path.getsize(fasta_path)
        kayitlar = []
        with open(fasta_path + ".fai", "r", encoding="utf-8", errors="replace") as f:
            for satir in f:
                c = satir.rstrip("\r\n").split("\t")
                if len(c) < 5:
                    return "uyusmuyor"
                kayitlar.append((c[0], int(c[1]), int(c[2]), int(c[3]), int(c[4])))
        if not kayitlar:
            return "uyusmuyor"
        n = len(kayitlar)
        secilen = sorted({0, n - 1} | {round(i * (n - 1) / max(1, ornek - 1)) for i in range(ornek)})
        with open(fasta_path, "rb") as fa:
            for i in secilen:
                ad, uz, ofs, lb, lby = kayitlar[i]
                if lb <= 0 or lby < lb or ofs < 2:
                    return "uyusmuyor"
                if ofs > boyut:
                    return "kesik"
                bas = max(0, ofs - 8192)
                fa.seek(bas)
                onceki = fa.read(ofs - bas)
                if not onceki.endswith(b"\n"):
                    return "uyusmuyor"
                baslik = onceki[:-1].rstrip(b"\r").rsplit(b"\n", 1)[-1]
                if not baslik.startswith(b">") or \
                        baslik[1:].split()[:1] != [ad.encode("utf-8", "replace")]:
                    return "uyusmuyor"
                if uz > lb:
                    # ilk satir indeksin gosterdigi yerde bitmeli (satir sonu bayt(lar)i)
                    fa.seek(ofs + lb)
                    sonu = fa.read(lby - lb)
                    if len(sonu) == lby - lb and sonu.strip(b"\r\n"):
                        return "uyusmuyor"
    except (OSError, ValueError):
        return "uyusmuyor"
    ad, uz, ofs, lb, lby = kayitlar[-1]
    fark = boyut - (ofs + (uz // lb) * lby + (uz % lb))
    if fark < 0:
        return "kesik"
    return "tamam" if fark <= 2 else "yarim"


def fai_uyusmuyor_mesaji(fasta_path):
    ad = os.path.basename(fasta_path)
    return t(
        f"Genom indeksi ({ad}.fai) bu FASTA dosyasına ait değil ya da FASTA sonradan "
        "değişmiş: satır düzeni ve kromozom başlıkları indeksle tutmuyor. Bu hâliyle "
        "okunan diziler YANLIŞ olacağı için genom kullanılmadı. Çözüm: "
        f"{ad}.fai dosyasını silin; ilk kullanımda yeniden oluşturulur (3 GB'lık "
        "dosyada birkaç dakika sürer).",
        f"The genome index ({ad}.fai) does not belong to this FASTA file, or the FASTA "
        "changed afterwards: the line layout and chromosome headers do not match the "
        "index. Sequences read this way would be WRONG, so the genome was not used. Fix: "
        f"delete {ad}.fai; it is rebuilt on first use (takes a few minutes for a 3 GB file).")


# Kullanilmamasi gereken indeks durumlari: bu genomla okunan dizi yanlis (uyusmuyor) ya da
# tarama eksik kalir (kesik, yarim) - ozgulluk 'Ozgul' dedirtemez (A7-04, v0.8.40).
FAI_ENGEL = ("uyusmuyor", "kesik", "yarim")


def fai_sorun_mesaji(fasta_path, durum):
    """Engelli bir indeks durumu icin kullaniciya donen mesaj (genom kullanilmadi der)."""
    ad = os.path.basename(fasta_path)
    if durum == "uyusmuyor":
        return fai_uyusmuyor_mesaji(fasta_path)
    if durum == "kesik":
        return t(
            f"FASTA dosyası ({ad}) indeksin gösterdiğinden kısa: dosya yarım kopyalanmış ya da "
            "inmiş olabilir; son kromozomlar okunamaz. Eksik genomda özgüllük taraması yanlışlıkla "
            "\"özgül\" sonucu verebileceği için genom kullanılmadı. Genomu yeniden indirin.",
            f"The FASTA file ({ad}) is shorter than its index says: it may be a partial copy or "
            "download; the last chromosomes cannot be read. A specificity scan on an incomplete "
            "genome could wrongly report \"specific\", so the genome was not used. Download the "
            "genome again.")
    if durum == "yarim":
        return t(
            f"FASTA indeksi ({ad}.fai) yarım kalmış görünüyor: son kaydı dosyanın sonuna "
            "ulaşmıyor, bazı kromozomlar taranamaz. Eksik genomda özgüllük taraması yanlışlıkla "
            "\"özgül\" sonucu verebileceği için genom kullanılmadı. .fai dosyasını silin; ilk "
            "kullanımda yeniden oluşturulur.",
            f"The FASTA index ({ad}.fai) looks incomplete: its last record does not reach the "
            "end of the file, so some chromosomes cannot be scanned. A specificity scan on an "
            "incomplete genome could wrongly report \"specific\", so the genome was not used. "
            "Delete the .fai file; it is rebuilt on first use.")
    return None


# engine tarafindan kurulur: (fasta_yolu) -> eksik/kesik genom mesaji | None (D3-04, tamlik denetimi)
TAMLIK_KANCASI = None


def fai_engeli(fasta_path):
    """Genom kullanilamiyorsa nedenini anlatan mesaj, kullanilabiliyorsa None.
    Indeks bu dosyaya uygun olsa bile genom eksik/kesikse (kromozom yok ya da uzunluk
    bilinenden farkli) mesaj doner; yalniz .fai okunur."""
    durum = fai_denetle(fasta_path)
    if durum in FAI_ENGEL:
        return fai_sorun_mesaji(fasta_path, durum)
    if durum == "tamam" and TAMLIK_KANCASI is not None:
        return TAMLIK_KANCASI(fasta_path)
    return None


def read_fai(fasta_path):
    """[(ad, uzunluk, offset, satirdaki_baz, satirdaki_bayt), ...]"""
    fai = fasta_path + ".fai"
    if not os.path.exists(fai):
        raise SpecificityError(t(
            f"FASTA indeksi yok: {os.path.basename(fai)}. "
            "Özgüllük kontrolü için .fai dosyası gerekir.",
            f"FASTA index missing: {os.path.basename(fai)}. "
            "The specificity check needs the .fai file."))
    engel = fai_engeli(fasta_path)
    if engel:
        raise SpecificityError(engel)
    out = []
    with open(fai, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            c = line.rstrip("\n").split("\t")
            if len(c) >= 5:
                out.append((c[0], int(c[1]), int(c[2]), int(c[3]), int(c[4])))
    if not out:
        raise SpecificityError(t("FASTA indeksi boş okundu.",
                                 "The FASTA index was read as empty."))
    return out


_FH = {}
_FH_LOCK = threading.Lock()


def _handle(path):
    """Acik dosya tanitici (surec basina). Transkriptom taramasinda 76 bin kucuk
    kayit okunuyor; her biri icin open() cagirmak taramayi 60 saniyeye cikariyordu."""
    fh = _FH.get(path)
    if fh is None:
        fh = open(path, "rb")
        _FH[path] = fh
    return fh


def _read_bases(path, offset, lenc, lenb, base_start, base_count):
    """FASTA'dan [base_start, base_start+base_count) baz araligini satir sonlari
    temizlenmis halde oku. Koordinat 0-tabanli, kromozom icinde.

    Kromozomun TAMAMINI bellege almiyoruz: chr1 250 MB, uzerine replace/upper
    kopyalari eklenince isci basina ~1 GB ediyor ve 12 isci makineyi takasa
    sokuyordu (GRCh38 taramasi 4 sn yerine 47 sn suruyordu)."""
    def byte_at(i):
        return offset + (i // lenc) * lenb + (i % lenc)

    start_byte = byte_at(base_start)
    end_byte = byte_at(base_start + base_count)
    # Kilit: Flask threaded calisiyor, paylasilan tanitici uzerinde seek+read
    # iki istek arasinda birbirine karismasin.
    with _FH_LOCK:
        f = _handle(path)
        f.seek(start_byte)
        raw = f.read(end_byte - start_byte)
    seq = raw.replace(b"\n", b"").replace(b"\r", b"")
    # Ensembl "dna" dosyalari zaten buyuk harf; soft-masked surumler icin guvence
    return seq if seq.isupper() else seq.upper()


def _mismatches(a: bytes, b: bytes) -> int:
    """Esit uzunlukta iki dizide uyumsuz baz sayisi (C hizinda: XOR + sifir sayimi)."""
    n = len(a)
    x = (int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).to_bytes(n, "big")
    return n - x.count(0)


# ------------------------------------------------------------------
# Tarama
# ------------------------------------------------------------------
# Isci surecler icin modul duzeyi durum (spawn'da her iscide bir kez kurulur)
_W = {}


def _worker_init(path, probes, seed_len, max_mm, max_sites_task, pad, dur=None):
    _W["path"] = path
    _W["probes"] = probes          # [(etiket, yon, tam_primer_bytes, seed_bytes), ...]
    _W["seed_len"] = seed_len
    _W["max_mm"] = max_mm
    _W["max_sites_task"] = max_sites_task
    _W["pad"] = pad                # parca sinirlarindaki ortusme payi (baz)
    _W["dur"] = dur                # tarama erken bitti isareti (mp.Event; tek surecte None)
    _ebeveyn_bekcisi()


def _durdu():
    """Ana surec taramayi erken bitirdi mi (bkz. _scan_genome): kalan parcalar taranmaz,
    sonuc gonderilmez."""
    dur = _W.get("dur")
    return dur is not None and dur.is_set()


def _ebeveyn_bekcisi():
    """Havuz iscisi, motor (ebeveyn) olunce kendini kapatsin. Windows'ta motor
    sonlandirilinca (uygulama kapanisi, Gorev Yoneticisi, cokme) isciler kapanmiyor,
    ebeveynsiz bos bekleyip bellek tutuyordu (2026-10-31). Tek surecli taramada
    (serial) ebeveyn yoktur, bekci kurulmaz."""
    ebeveyn = mp.parent_process()
    if ebeveyn is None or _W.get("bekci"):
        return
    _W["bekci"] = True

    def bekle():
        ebeveyn.join()         # ebeveynin surec tutamaci isaretlenene kadar bekler
        os._exit(0)
    threading.Thread(target=bekle, name="ebeveyn-bekcisi", daemon=True).start()


def _scan_chunk(task):
    """Bir is parcasini tara. task: [(ad, offset, lenc, lenb, dizi_uzunlugu,
    baslangic, adet), ...] - birden fazla alt aralik icerebilir.

    Neden liste: genomda is parcasi = kromozomun 16 Mbp'lik dilimi, ama
    transkriptomda 76 bin kucuk dizi var; her birine ayri is parcasi acmak
    surecler arasi iletisimde bogulurdu. Kucuk diziler tek pakette toplanir.

    Doner: (isabetler, sayac, tasanlar)
      isabetler: [(etiket, yon, dizi_adi, 5'_koordinati, 3'_koordinati, uyumsuzluk), ...]
      sayac:     {etiket: bu parcada bulunan yer sayisi}
      tasanlar:  bu parcada max_sites_per_task'i asan etiketler (= tekrar dizisi)"""
    hits, sayac = [], {}
    for sub in task:
        if _durdu():
            break
        hits.extend(_scan_range(sub, sayac))
    if _durdu():
        return [], {}, []        # ana surec bu parcayi kullanmaz; buyuk mesaj gonderilmez
    sinir = _W["max_sites_task"]
    return hits, sayac, [e for e, n in sayac.items() if n > sinir]


def _scan_range(sub, sayac):
    name, offset, lenc, lenb, chrom_len, base_start, base_count = sub
    seed_len = _W["seed_len"]
    max_mm = _W["max_mm"]
    pad = _W["pad"]
    sinir = _W["max_sites_task"]

    # Parca sinirinda kesilen primer ayak izlerini kacirmamak icin iki yana pay
    read_start = max(0, base_start - pad)
    read_end = min(chrom_len, base_start + base_count + pad)
    seq = _read_bases(_W["path"], offset, lenc, lenb, read_start, read_end - read_start)

    hits = []
    for label, orient, primer, seed in _W["probes"]:
        if _durdu():
            break                    # tarama erken bitti; sonuc zaten kullanilmaz
        if sayac.get(label, 0) > sinir:
            continue                 # bu primer bu parcada zaten tasti
        plen = len(primer)
        # '+' yonlu: genomda primerin AYNISI var, uzama saga dogru.
        #     seed (3' uc) eslesmenin SONUNDA -> primer basi = i - (plen - seed_len)
        # '-' yonlu: genomda primerin TERS TUMLEYENI var, uzama sola dogru.
        #     seed'in ters tumleyeni eslesmenin BASINDA -> primer basi = i
        lead = plen - seed_len
        i = seq.find(seed)
        while i != -1:
            # Bu seed vurusu bu parcaya mi ait? (paylar bir sonraki/onceki parcada sayilir)
            g_seed = read_start + i
            if base_start <= g_seed < base_start + base_count:
                start = (i - lead) if orient == "+" else i
                if start >= 0 and start + plen <= len(seq):
                    mm = _mismatches(seq[start:start + plen], primer)
                    if mm <= max_mm:
                        sayac[label] = sayac.get(label, 0) + 1
                        if sayac[label] > sinir:
                            # Tek bir 16 Mbp diliminde bu kadar yer: primer bir
                            # tekrar dizisinde. Geri kalani taramak hem zaman hem
                            # bellek harcar ve sonucu degistirmez; tasma bildirilir.
                            break
                        g_lo = read_start + start + 1      # 1-tabanli
                        g_hi = g_lo + plen - 1
                        # 3' uc: '+' yonlude yuksek koordinat, '-' yonlude dusuk
                        five, three = (g_lo, g_hi) if orient == "+" else (g_hi, g_lo)
                        hits.append((label, orient, name, five, three, mm))
            i = seq.find(seed, i + 1)
    return hits


def _build_tasks(recs, chunk_bases):
    """Dizileri ~chunk_bases boyutunda is parcalarina bol.
    Buyuk diziler (kromozom) bolunur; kucukler (transkript) tek pakette toplanir.
    Boylece hem bellek sinirli kalir hem is parcasi sayisi makul olur."""
    tasks = []
    batch, batch_bases = [], 0
    for name, length, offset, lenc, lenb in recs:
        pos = 0
        while pos < length:
            n = min(chunk_bases, length - pos)
            sub = (name, offset, lenc, lenb, length, pos, n)
            if n >= chunk_bases:                 # tam boy dilim: kendi basina
                tasks.append([sub])
            else:
                batch.append(sub)
                batch_bases += n
                if batch_bases >= chunk_bases:
                    tasks.append(batch)
                    batch, batch_bases = [], 0
            pos += n
    if batch:
        tasks.append(batch)
    return tasks


def _probes_for(fwd, rev, seed_len):
    """Aranacak desenler. Her primer icin iki yon:
    '+' -> primerin kendisi, '-' -> ters tumleyeni. Seed her zaman 3' uctan alinir."""
    probes = []
    for label, seq in (("F", fwd), ("R", rev)):
        p = seq.encode("ascii")
        probes.append((label, "+", p, p[-seed_len:]))
        rc = revcomp_b(p)
        # ters tumleyende primerin 3' ucu, dizinin BASINDA yer alir
        probes.append((label, "-", rc, rc[:seed_len]))
    return probes


class Isabetler(list):
    """scan_genome sonucu. Duz bir isabet listesi gibi davranir (eski cagiranlar
    degismeden calisir); ek olarak primer basina toplam yer sayisini ve siniri
    asan (tekrar dizisindeki) primerleri tasir. Tasma varsa o primerin listesi
    EKSIKTIR - urun tahmini yapilmamali."""
    toplam = None       # {"F": n, "R": n}; tasan primerde alt sinirdir
    tasan = frozenset()


def _birlestir(parcalar, genel_sinir, etiketler, dur=None):
    """Isci sonuclarini sirayla birlestir. Genel sinir burada uygulanir: bir
    primerin toplam yeri siniri asinca listesine eklemeyi birakir, tasmayi
    kaydeder. Butun primerler tasinca tarama erken biter (doner: True).
    dur (havuzla taramada): erken bitince donguden cikilmaz; isaret verilir, kalan
    sonuclar okunur ama KULLANILMAZ (cikti donguyu kirmakla ayni), havuz bosalir."""
    out = Isabetler()
    toplam = {e: 0 for e in etiketler}
    kayit = {e: 0 for e in etiketler}
    tasan = set()
    bitti = False
    for hits, sayac, tasti in parcalar:
        if bitti:
            continue                    # havuz bosaltiliyor (bkz. _scan_genome)
        tasan.update(tasti)
        for e, n in sayac.items():
            toplam[e] = toplam.get(e, 0) + n
        for h in hits:
            e = h[0]
            if kayit[e] < genel_sinir:
                out.append(h)
                kayit[e] += 1
            else:
                tasan.add(e)
        if tasan >= set(etiketler):
            bitti = True
            if dur is None:
                break
            dur.set()                   # iscilere: kalan parcalari tarama, sonuc gonderme
    out.toplam = toplam
    out.tasan = frozenset(tasan)
    return out, bitti


# Ayni anda TEK genom taramasi (inceleme bulgusu 14). Her tarama cekirdek sayisi kadar
# isci acar; ikinci tarama ayni anda baslayinca 25 surec olculdu (2026-10-28, paketli
# exe). Islemci zaten dolu oldugu icin siraya koymak toplam sureyi uzatmaz, bellegi
# ve surec sayisini yariya indirir. Kalici havuz DENENMEDI: havuz kurmak taramanin
# ~0,4 sn'si (3,0 sn'de), karsiliginda 12 surec surekli bellekte kalirdi.
_TARAMA = threading.Semaphore(1)


def scan_genome(fasta_path, fwd, rev, p):
    """Genom boyunca baglanma bolgelerini bul. Doner: Isabetler (liste + toplam/tasan)."""
    with _TARAMA:
        return _scan_genome(fasta_path, fwd, rev, p)


def _scan_genome(fasta_path, fwd, rev, p):
    recs = read_fai(fasta_path)
    seed_len = int(p["seed_len"])
    probes = _probes_for(fwd, rev, seed_len)
    pad = max(len(fwd), len(rev)) + seed_len
    chunk = int(p["chunk_bases"])
    init_args = (fasta_path, probes, seed_len, int(p["max_mismatch"]),
                 int(p["max_sites_per_task"]), pad)
    tasks = _build_tasks(recs, chunk)
    genel = int(p["max_sites_per_primer"])
    etiketler = ("F", "R")

    workers = int(p.get("workers") or 0)
    if workers <= 0:
        workers = min(mp.cpu_count() or 1, 12)
    workers = max(1, min(workers, len(tasks)))

    def serial():
        _worker_init(*init_args)
        return _birlestir((_scan_chunk(t) for t in tasks), genel, etiketler)[0]

    if workers == 1:
        return serial()
    try:
        dur = mp.Event()
        with mp.Pool(workers, initializer=_worker_init, initargs=init_args + (dur,)) as pool:
            # imap: sonuclar geldikce islenir, hepsi bellekte birikmez. Butun primerler
            # tasinca isaret verilir; isciler kalan parcalari taramadan bos doner, havuz
            # bosalir ve olagan yoldan kapanir. Eskiden dongu kirilip with blogu havuzu
            # terminate() ile sonlandiriyordu: isciler ~10 MB'lik sonuc gonderirken
            # olduruluyor, sonuc is parcacigi yarim mesaji sonsuza dek bekliyordu
            # (Windows; poli-A ciftinde 41 erken bitiste 1, yigin result_handler.join'de).
            # Tarama kilidi (_TARAMA) birakilmadigi icin sonraki butun taramalar da
            # bekliyordu (2026-11-09).
            out = _birlestir(pool.imap(_scan_chunk, tasks, chunksize=2),
                             genel, etiketler, dur)[0]
            pool.close()
            pool.join()
            return out
    except Exception:
        # Paketlenmis ortamda coklu surec kurulamazsa tek surece dus
        return serial()


# ------------------------------------------------------------------
# Yan urun (amplikon) tespiti
# ------------------------------------------------------------------
def pair_products(hits, max_product, limit=None):
    """'+' yonlu bir bolge ile sagindaki '-' yonlu bir bolgeyi eslestir.
    Urun = iki primerin 5' uclari arasindaki mesafe.

    limit: verilirse en fazla limit+1 urun uretilir ve durulur; cagiran
    len(sonuc) > limit ise listenin EKSIK oldugunu bilir. Tekrar bolgesindeki
    bir cift milyonlarca urun uretip GB'larca bellek tuketiyordu (chr7 uydu
    tekrarinda 2,09 milyon urun ~890 MB)."""
    by_chrom = {}
    for h in hits:
        by_chrom.setdefault(h[2], []).append(h)

    products = []
    tavan = None if limit is None else int(limit) + 1
    for chrom, lst in by_chrom.items():
        plus = sorted([h for h in lst if h[1] == "+"], key=lambda h: h[3])
        minus = sorted([h for h in lst if h[1] == "-"], key=lambda h: h[3])
        if not plus or not minus:
            continue
        j0 = 0
        for hp in plus:
            p5 = hp[3]
            # ilk kullanilabilir '-' bolgesine kadar ilerle
            while j0 < len(minus) and minus[j0][3] < p5:
                j0 += 1
            j = j0
            while j < len(minus) and minus[j][3] - p5 + 1 <= max_product:
                if tavan is not None and len(products) >= tavan:
                    return products
                hm = minus[j]
                products.append({
                    "chrom": chrom,
                    "start": p5,
                    "end": hm[3],
                    "size": hm[3] - p5 + 1,
                    "combination": hp[0] + "+" + hm[0],   # F+R, F+F, R+R ...
                    "forward_primer": hp[0],
                    "reverse_primer": hm[0],
                    "mismatch_forward": hp[5],
                    "mismatch_reverse": hm[5],
                    "mismatch_total": hp[5] + hm[5],
                })
                j += 1
    return products


def check_pair(fasta_path, fwd, rev, expected=None, params=None, assembly=None, isabet=None):
    """
    Bir primer ciftinin ozgullugunu kontrol et.
    expected: {"chrom":..., "start":..., "end":...} - istenen urun (raporda elenir)
    assembly: verilirse Y'nin psodootozomal bolgesindeki, X'teki esiyle ayni
              urunler ("PAR ikizi") yan urun sayilmaz - bkz. par.py.
    isabet:   verilirse genom yeniden taranmaz; isabetler bu cagridan gelir, imzasi
              scan_genome ile ayni. Tek gecis taramasi (cok_tarama.Tarama.isabetler) bunu
              kullanir: geri kalan her adim burada, ayni kodla yapilir (v0.8.36).
    """
    # Tip ve sinir denetimi: max_mismatch=-1 hicbir yer bulmayip "ozgul" hukmu,
    # seed_len="abc" 500 veriyordu (2026-10-28). Bkz. ayarlar.py.
    p = ayarlar.birlestir([SPEC_DEFAULTS], params, ayarlar.OZGULLUK_SINIRLARI,
                          SpecificityError)
    if int(p["risk_medium_max"]) < int(p["risk_high_max"]):
        raise SpecificityError(t(
            "risk_medium_max, risk_high_max'tan küçük olamaz.",
            "risk_medium_max cannot be smaller than risk_high_max."))

    if not fwd or not rev:
        raise SpecificityError(t("Forward ve reverse dizi gerekli.",
                                 "Both forward and reverse sequences are required."))
    for s in (fwd, rev):
        if not re.fullmatch(r"[ACGTacgt]+", s):
            raise SpecificityError(t(f"Dizi sadece A/C/G/T içermeli: {s}",
                                     f"Sequence may only contain A/C/G/T: {s}"))
    if int(p["seed_len"]) > min(len(fwd), len(rev)):
        raise SpecificityError(t("seed_len primer uzunluğundan büyük olamaz.",
                                 "seed_len cannot exceed the primer length."))

    hits = (isabet or scan_genome)(fasta_path, fwd.upper(), rev.upper(), p)
    # Sinir asildiysa liste EKSIK: yan urun sayimi da "ozgul" hukmu de yanlis
    # olur. Sessizce kirpip sonuc vermek yerine durumu acikca soyle.
    if hits.tasan:
        ad = {"F": "Forward", "R": "Reverse"}
        kim = [f"{ad[e]} (en az {tr_sayi(hits.toplam.get(e, 0))})" for e in ("F", "R") if e in hits.tasan]
        kim_en = [f"{ad[e]} (at least {hits.toplam.get(e, 0):,})" for e in ("F", "R")
                  if e in hits.tasan]
        raise SpecificityError(t(
            f"Primer bir tekrar dizisine denk geliyor: {', '.join(kim)} bağlanma yeri. "
            "Poli-A ya da Alu/LINE gibi tekrarlarda primer genomun her yerine oturur; "
            "özgül ürün beklenmez ve özgüllük taraması anlamlı bir sonuç veremez.",
            f"The primer falls in a repeat: {', '.join(kim_en)} binding sites. In "
            "poly-A or Alu/LINE-type repeats a primer binds all over the genome; no "
            "specific product can be expected and a specificity scan is meaningless."))
    limit = int(p["max_products"])
    products = pair_products(hits, int(p["max_offtarget_product"]), limit=limit)
    if len(products) > limit:
        raise SpecificityError(t(
            f"Bu çift {tr_sayi(limit)}'den fazla olası ürün veriyor — primerler bir tekrar "
            "bölgesinde. Özgül ürün beklenmez; liste çıkarılamadı.",
            f"This pair gives more than {limit:,} possible products — the primers sit "
            "in a repeat region. No specific product can be expected; the list could "
            "not be produced."))

    # Y'nin PAR'indaki ikizler: GRCh38'de her PAR urunu Y'de de birebir cikiyor ve
    # eskiden "yuksek riskli yan urun, ozgul degil" diye raporlaniyordu (SHOX,
    # 2026-10-11). Ayni dizinin ikinci temsili; ayrilir, ayrica bildirilir.
    if assembly:
        par.urun_ikizleri(assembly, products)
    ikizler = [pr for pr in products if pr.get("par_ikizi")]
    products = [pr for pr in products if not pr.get("par_ikizi")]

    # Istenen urunu ele: ayni kromozom + baslangic/bitis yakinsa
    intended = None
    off = []
    for pr in products:
        if expected and _is_intended(pr, expected):
            intended = pr
        else:
            off.append(pr)

    # En tehlikeliden siraya: az uyumsuzluk + kisa urun once
    off.sort(key=lambda x: (x["mismatch_total"], x["size"]))

    hi, med = int(p["risk_high_max"]), int(p["risk_medium_max"])
    tiers = {"yuksek": 0, "orta": 0, "dusuk": 0}
    for o in off:
        o["risk"] = ("yuksek" if o["mismatch_total"] <= hi else
                     "orta" if o["mismatch_total"] <= med else "dusuk")
        tiers[o["risk"]] += 1

    # Baglanma bolgeleri: toplam sayi yaniltici olabilir (tekrar bolgelerinde
    # sisiyor), o yuzden "iyi oturan" bolgeler ayrica sayilir.
    sites = {"F": {"toplam": 0, "iyi": 0}, "R": {"toplam": 0, "iyi": 0}}
    x_anahtar = par.yer_x_anahtari(hits) if assembly else set()
    for h in hits:
        label, mm = h[0], h[5]
        if assembly and par.yer_ikizi_mi(assembly, h, x_anahtar):
            continue
        sites[label]["toplam"] += 1
        if mm <= hi:
            sites[label]["iyi"] += 1

    # Hedef (yoksa en iyi yan urun) psodootozomal bolgede mi? Arayuz not gosterir.
    par_bilgi = None
    if assembly:
        odak = intended or (off[0] if off else None)
        pb = par.bolge(assembly, odak["chrom"], odak["start"], odak["end"]) if odak else None
        if pb:
            par_bilgi = {"ad": pb["ad"], "ikiz_gorunuyor": bool(ikizler),
                         "note": par.not_metni(pb["ad"], bool(ikizler))}

    # Yalnizca GERCEKTEN baglanabilecek yan urunler listelenir. 3' uc sarti
    # 6 baza inince arama penceresi genisledi; suzgec olmadan yuzlerce satir
    # cikip asil onemli olani gizler. Elenen sayisi risk_counts'ta duruyor,
    # yani bilgi kaybolmuyor - yalnizca tablo okunabilir kaliyor.
    kayda_deger = [o for o in off if o["risk"] != "dusuk"]
    dusukler = [o for o in off if o["risk"] == "dusuk"]

    return {
        "forward": fwd.upper(),
        "reverse": rev.upper(),
        "params_used": p,
        "binding_sites": sites,
        "intended_found": intended is not None,
        "intended": intended,
        "offtarget_count": len(off),
        "risk_counts": tiers,
        "offtargets": kayda_deger[:int(p["report_limit"])],
        # Dusuk olasilikliler varsayilan listede yok ama ATILMIYOR: arayuz
        # istege bagli acabilsin diye ayri donuluyor.
        "offtargets_low": dusukler[:100],
        "low_hidden": len(dusukler),
        "low_truncated": len(dusukler) > 100,
        "truncated": len(kayda_deger) > int(p["report_limit"]),
        # "ozgul" = kayda deger (yuksek/orta) yan urun yok
        "specific": tiers["yuksek"] == 0 and tiers["orta"] == 0,
        "par": par_bilgi,
        "par_twins": len(ikizler),
    }


def _is_intended(prod, expected):
    """Tahmin edilen urun, tasarlanan urunle ayni mi? (uc koordinatlarda kucuk
    kayma olabilir; primer 5' uclari esas alindigi icin tolerans dar tutuldu)"""
    if str(prod["chrom"]) != str(expected.get("chrom")):
        return False
    return (abs(prod["start"] - int(expected.get("start", -1))) <= 5 and
            abs(prod["end"] - int(expected.get("end", -1))) <= 5)
