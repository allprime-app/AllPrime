# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""
AllPrime - Yaygin Varyant (dbSNP) Katmani
===========================================
Primerin oturdugu bolgeye denk gelen YAYGIN varyantlari bulur.

Neden onemli: primerin baglandigi yerde bir varyant varsa o allel cogalmaz.
Heterozigot hasta HOMOZIGOT gorunur - yani sonuc sessizce yanlis cikar, üstelik
temiz bir sonuc gibi durur. Ozgullukten bile sinsi bir hata tipi.

Veri: UCSC snp151Common (dbSNP b151'in MAF >= %1 alt kumesi).
Ham tablo 750 MB/genom; burada ~10 bayt/kayitlik sikistirilmis bir indekse
cevrilir ve uygulamayla yalnizca o indeks dagitilir.

Indeks bicimi (kucuk-endian):
    baslik   : sihirli sayi(8) + assembly(16) + kromozom_sayisi(4) + ayrilmis(4)
    dizin    : kromozom basina 40 bayt -> ad(8) count(4) pad(4) pos(8) rs(8) maf(8)
    veriler  : kromozom basina  pos:uint32[]  rs:uint32[]  maf:uint8[]  span:uint8[]

maf baytinda: bit7 = indel mi, bit0-6 = MAF * 200 (0-100, yani %0.5 cozunurluk).
Sorgu mmap uzerinde ikili arama ile yapilir; dosya bellege yuklenmez.
"""

import os
import sys
import glob
import gzip
import threading
import mmap
import struct
from array import array

from lang import t

MAGIC = b"APSNP1\x00\x00"
UZANTI = ".apidx"
# Uygulamanin onceki adiyla uretilmis indeks: bicim ayni, yalnizca sihirli sayi ve
# uzanti farkli. Eski klasorden kopyalanan indeks yeniden indirilmesin diye okunur
# ve bulundugu yerde bir kez yeni ada cevrilir (autodetect_dbsnp).
ESKI_MAGIC = b"EKSNP1\x00\x00"                  # onceki-ad-uyumu
ESKI_UZANTI = ".ekidx"                          # onceki-ad-uyumu
HDR = struct.Struct("<8s16sII")
DIR = struct.Struct("<8sIIQQQ")
MAX_SPAN = 255

DBSNP_PATHS = {
    "GRCh37": os.environ.get("ALLPRIME_DBSNP_GRCH37", ""),
    "GRCh38": os.environ.get("ALLPRIME_DBSNP_GRCH38", ""),
}
UCSC_DB = {"GRCh37": "hg19", "GRCh38": "hg38"}

_INDEX_CACHE = {}


class DbSnpError(Exception):
    """Kullaniciya gosterilebilir dbSNP hatasi."""
    pass


# ------------------------------------------------------------------
# Dosya bulma (genomes/ ve annotations/ ile ayni mantik)
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
        if b and os.path.normpath(b) not in seen:
            seen.add(os.path.normpath(b))
            out.append(os.path.normpath(b))
    return out


def eski_indeksi_cevir(yol):
    """Onceki adla uretilmis indeksi yeni ada ve sihirli sayiya cevirir; kullanilacak
    yolu dondurur. Dosya baska bir surecte aciksa ya da klasor yazilamiyorsa eski
    haliyle kalir ve oldugu gibi okunur (SnpIndex iki sihirli sayiyi da tanir)."""
    yeni = yol[:-len(ESKI_UZANTI)] + UZANTI
    if os.path.exists(yeni):
        return yeni
    try:
        os.replace(yol, yeni)
    except OSError:
        return yol
    try:
        with open(yeni, "r+b") as f:
            if f.read(len(ESKI_MAGIC)) == ESKI_MAGIC:
                f.seek(0)
                f.write(MAGIC)
    except OSError:
        pass
    return yeni


def autodetect_dbsnp():
    """annotations\\ klasorundeki dbsnp_common_*.apidx dosyalarini bul."""
    for base in _candidate_bases():
        adir = os.path.join(base, "annotations")
        if not os.path.isdir(adir):
            continue
        for eski in glob.glob(os.path.join(adir, "dbsnp_common_*" + ESKI_UZANTI)):
            eski_indeksi_cevir(eski)
        for asm, db in UCSC_DB.items():
            if DBSNP_PATHS.get(asm):
                continue
            hits = [p for uz in (UZANTI, ESKI_UZANTI)
                    for p in glob.glob(os.path.join(adir, "dbsnp_common_*" + uz))
                    if db in os.path.basename(p).lower()]
            if hits:
                DBSNP_PATHS[asm] = hits[0]


autodetect_dbsnp()


def dbsnp_status():
    # Bozuk indeks "var" sayilmaz: arayuz gostergesi yesil kalip kullaniciyi yaniltmasin
    return {asm: bool(p) and os.path.exists(p) and get_index(asm) is not None
            for asm, p in DBSNP_PATHS.items()}


def normalize_chrom(c):
    c = str(c).strip()
    if c.lower().startswith("chr"):
        c = c[3:]
    cu = c.upper()
    if cu in ("X", "Y", "MT"):
        return cu
    if cu == "M":
        return "MT"
    return c


# ------------------------------------------------------------------
# Indeks kurulumu (tek seferlik, dagitimda calismaz)
# ------------------------------------------------------------------
def maf_yaz(maf):
    """Gosterim: indeks MAF'i %0,5 adimla saklar, %0,25'in altindakiler 0 olarak
    durur (GRCh38 indeksinde 25.609 kayit, %0,18 - olculdu 2026-10-28). Bunlar
    snp151Common'dan gelir, yani frekansi BILINIR ama kucuktur; "0" yazmak
    "bilinmiyor / hic gorulmedi" gibi okunuyordu (inceleme bulgusu 20)."""
    return "<0.0025" if maf == 0 else f"{maf:g}"


def _maf_from_freqs(freq_field):
    """UCSC alleleFreqs alanindan minor allel frekansi.
    MAF = ikinci en yuksek frekans (cok allelli kayitlarda 'min' yaniltir)."""
    if not freq_field:
        return 0.0
    vals = []
    for x in freq_field.rstrip(",").split(","):
        if x:
            try:
                vals.append(float(x))
            except ValueError:
                pass
    if len(vals) < 2:
        return 0.0
    vals.sort(reverse=True)
    return vals[1]


def build_index(src_gz, out_path, assembly, progress=None):
    """UCSC snp151Common tablosunu sikistirilmis indekse cevir."""
    pos_a, rs_a, maf_a, span_a = {}, {}, {}, {}
    kept = skipped = 0

    with gzip.open(src_gz, "rt", encoding="utf-8", errors="replace") as f:
        for n, line in enumerate(f):
            c = line.rstrip("\n").split("\t")
            if len(c) < 25:
                continue
            chrom = normalize_chrom(c[1])
            # alt-haplotip / patch kayitlari ise yaramaz
            if not (chrom.isdigit() or chrom in ("X", "Y", "MT")):
                skipped += 1
                continue
            name = c[4]
            if not name.startswith("rs"):
                skipped += 1
                continue
            try:
                rs = int(name[2:])
                start0 = int(c[2])
                end = int(c[3])
            except ValueError:
                skipped += 1
                continue
            if rs > 0xFFFFFFFF:
                skipped += 1
                continue

            span = max(1, min(MAX_SPAN, end - start0))
            indel = 0 if c[11] == "single" else 1
            maf = _maf_from_freqs(c[24])
            mafv = min(100, int(round(maf * 200)))

            if chrom not in pos_a:
                pos_a[chrom] = array("I")
                rs_a[chrom] = array("I")
                maf_a[chrom] = array("B")
                span_a[chrom] = array("B")
            pos_a[chrom].append(start0 + 1)          # 1-tabanli
            rs_a[chrom].append(rs)
            maf_a[chrom].append((indel << 7) | mafv)
            span_a[chrom].append(span)
            kept += 1
            if progress and kept % 2_000_000 == 0:
                progress(kept)

    # Sorgu ikili aramaya dayaniyor: pozisyonlar SIRALI olmak zorunda.
    # UCSC dokumu genelde sirali gelir; sadece bozuk olani siralariz (bellek dostu).
    for chrom, pos in pos_a.items():
        if all(pos[i] <= pos[i + 1] for i in range(len(pos) - 1)):
            continue
        order = sorted(range(len(pos)), key=pos.__getitem__)
        pos_a[chrom] = array("I", (pos[i] for i in order))
        rs_a[chrom] = array("I", (rs_a[chrom][i] for i in order))
        maf_a[chrom] = array("B", (maf_a[chrom][i] for i in order))
        span_a[chrom] = array("B", (span_a[chrom][i] for i in order))

    chroms = sorted(pos_a.keys(), key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))
    body_off = HDR.size + DIR.size * len(chroms)

    # Once gecici dosyaya, bitince yerine: yarida kesilen yazim (iptal, kapanan
    # uygulama, dolan disk) eskiden yarim bir indeks birakiyordu; panel onu
    # "kurulu" gosteriyor, sorgular bozuk dizinden okunuyordu.
    gecici = out_path + ".part"
    try:
        with open(gecici, "wb") as out:
            out.write(HDR.pack(MAGIC, assembly.encode()[:16], len(chroms), 0))
            off = body_off
            for ch in chroms:
                n = len(pos_a[ch])
                p_off = off
                r_off = p_off + 4 * n
                m_off = r_off + 4 * n           # maf ve span pesipese: m_off, m_off+n
                off = m_off + 2 * n
                out.write(DIR.pack(ch.encode()[:8], n, 0, p_off, r_off, m_off))
            for ch in chroms:
                for arr in (pos_a[ch], rs_a[ch], maf_a[ch], span_a[ch]):
                    if sys.byteorder != "little":  # pragma: no cover
                        arr = array(arr.typecode, arr)
                        arr.byteswap()
                    out.write(arr.tobytes())
        os.replace(gecici, out_path)
    except BaseException:
        try:
            os.remove(gecici)
        except OSError:
            pass
        raise

    return {"records": kept, "skipped": skipped, "chroms": len(chroms),
            "bytes": os.path.getsize(out_path)}


# ------------------------------------------------------------------
# Calisma zamani sorgusu
# ------------------------------------------------------------------
class SnpIndex:
    """mmap uzerinde ikili arama. Dosya bellege yuklenmez."""

    def __init__(self, path):
        self.path = path
        self._f = open(path, "rb")
        self._mm = mmap.mmap(self._f.fileno(), 0, access=mmap.ACCESS_READ)
        magic, asm, n_chrom, _ = HDR.unpack_from(self._mm, 0)
        if magic not in (MAGIC, ESKI_MAGIC):
            raise DbSnpError(t(f"Geçersiz dbSNP indeksi: {os.path.basename(path)}",
                               f"Invalid dbSNP index: {os.path.basename(path)}"))
        self.assembly = asm.rstrip(b"\x00").decode()
        self.chroms = {}
        # Yarim/bozuk dosya: dizindeki uzakliklar dosyanin disini gosterir. Eskiden
        # bu kontrol yoktu; disaridaki okumalar bos donuyor, sorgu "varyant yok"
        # diyordu - yaygin varyant kacinmasi SESSIZCE kapaniyordu (2026-10-29:
        # 138 MB'lik indeksin ilk 40 MB'i ile TP53'te 7 yerine 0 varyant).
        boy = len(self._mm)
        if HDR.size + DIR.size * n_chrom > boy:
            self.close()
            raise DbSnpError(t(f"dbSNP indeksi yarım ya da bozuk: {os.path.basename(path)}",
                               f"The dbSNP index is truncated or corrupt: {os.path.basename(path)}"))
        for i in range(n_chrom):
            name, cnt, _pad, p, r, m = DIR.unpack_from(self._mm, HDR.size + DIR.size * i)
            if p + 4 * cnt > boy or r + 4 * cnt > boy or m + 2 * cnt > boy:
                self.close()
                raise DbSnpError(t(
                    f"dbSNP indeksi yarım ya da bozuk: {os.path.basename(path)}",
                    f"The dbSNP index is truncated or corrupt: {os.path.basename(path)}"))
            self.chroms[name.rstrip(b"\x00").decode()] = (cnt, p, r, m)

    def close(self):
        try:
            self._mm.close()
            self._f.close()
        except Exception:
            pass

    def _lower_bound(self, base, n, target):
        """pos dizisinde target'tan kucuk olmayan ilk indeks."""
        mm = self._mm
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            v = int.from_bytes(mm[base + mid * 4: base + mid * 4 + 4], "little")
            if v < target:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def overlaps(self, chrom, start, end):
        """[start, end] araligina (1-tabanli, kapsayici) degen yaygin varyantlar."""
        ent = self.chroms.get(normalize_chrom(chrom))
        if not ent:
            return []
        n, p_off, r_off, m_off = ent
        mm = self._mm
        # Uzun bir delesyon aralikten ONCE baslayip icine tasabilir; sola pay birak
        i = self._lower_bound(p_off, n, max(1, start - MAX_SPAN))
        out = []
        while i < n:
            pos = int.from_bytes(mm[p_off + i * 4: p_off + i * 4 + 4], "little")
            if pos > end:
                break
            span = mm[m_off + n + i]
            if pos + span - 1 >= start:          # gercekten kesisiyor mu
                mb = mm[m_off + i]
                out.append({
                    "rsid": "rs%d" % int.from_bytes(
                        mm[r_off + i * 4: r_off + i * 4 + 4], "little"),
                    "position": pos,
                    "span": span,
                    "maf": round((mb & 0x7F) / 200.0, 3),
                    "indel": bool(mb >> 7),
                })
            i += 1
        return out


_INDEX_KILIDI = threading.Lock()


_BOZUK = {}          # assembly -> (dosya yolu, hata mesaji): acilamayan indeks


def get_index(assembly):
    """Assembly icin indeksi ac (bir kez; kilitli - eszamanli ilk istekler).
    Indeks bozuksa None doner ve sebep bozuk_mu() ile okunur - cagiranlar
    'indeks yok' ile 'indeks var ama bozuk'u ayirip kullaniciya soyleyebilsin."""
    if assembly in _INDEX_CACHE:
        return _INDEX_CACHE[assembly]
    with _INDEX_KILIDI:
        if assembly in _INDEX_CACHE:
            return _INDEX_CACHE[assembly]
        path = DBSNP_PATHS.get(assembly, "")
        if not path or not os.path.exists(path):
            return None
        if _BOZUK.get(assembly, (None,))[0] == path:
            return None                  # ayni bozuk dosyayi her istekte yeniden acma
        try:
            _INDEX_CACHE[assembly] = SnpIndex(path)
        except (DbSnpError, ValueError, OSError, struct.error) as e:
            _BOZUK[assembly] = (path, str(e))
            return None
        _BOZUK.pop(assembly, None)
        return _INDEX_CACHE[assembly]


def bozuk_mu(assembly):
    """Indeks dosyasi var ama acilamadiysa kullaniciya gosterilecek uyari, yoksa None."""
    get_index(assembly)
    if assembly not in _BOZUK:
        return None
    return t(f"UYARI: Yaygın varyant indeksi (dbSNP, {assembly}) yarım ya da bozuk; bu "
             "işlemde yaygın varyantlardan KAÇINILMADI ve primer üzerindeki varyantlar "
             "gösterilmedi. Veri dosyaları panelinden indeksi yeniden indirin.",
             f"WARNING: The common-variant index (dbSNP, {assembly}) is truncated or "
             "corrupt; common variants were NOT avoided in this run and variants on the "
             "primers are not shown. Download the index again from the data files panel.")


# ------------------------------------------------------------------
# Komut satiri: indeksi yeniden uret
# ------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import time

    ap = argparse.ArgumentParser(
        description="UCSC snpNNNCommon tablosundan AllPrime dbSNP indeksi uretir.",
        epilog="Kaynak: https://hgdownload.soe.ucsc.edu/goldenPath/<db>/database/"
               "snp151Common.txt.gz  (hg19 ~748 MB, hg38 ~768 MB)")
    ap.add_argument("source", help="snp151Common.txt.gz yolu")
    ap.add_argument("output", help="uretilecek .apidx yolu")
    ap.add_argument("--assembly", required=True, choices=["GRCh37", "GRCh38"])
    a = ap.parse_args()

    t0 = time.time()
    st = build_index(a.source, a.output, a.assembly,
                     progress=lambda n: print(f"  {n:,} kayit... "
                                              f"({time.time() - t0:.0f} sn)", flush=True))
    print(f"Bitti: {st['records']:,} kayit, {st['chroms']} kromozom, "
          f"{st['bytes'] / 2**20:.0f} MB, {time.time() - t0:.0f} sn "
          f"({st['skipped']:,} kayit elendi)")
