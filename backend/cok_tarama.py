# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""Tek geciste cok primer genom taramasi (v0.8.36).

specificity.check_pair her cift icin genomu bastan tarar (4 desen, ~3 sn). Kurallara uyan butun
adaylarin (ortanca 10.544 cift, 500 farkli primer) ozgullugunu bilmek icin bu, saatler surerdi.
Burada butun farkli primerler TEK taramada aranir:
  - tohumlar (3' son 6 baz) 6-mer kodlariyla bulunur: her blokta gereken tohumlarin yerleri tek
    siralamayla gruplanir, her desenin pencereleri toplu karsilastirilir (numpy);
  - her primerin isabetleri specificity'nin is parcasi / alt aralik / desen sirasi ve parca basi
    sinirlariyla AYNEN saklanir. Bir cift icin isabet listesi bu kayitlardan kurulur ve gercek
    specificity._birlestir'den gecer: Tarama.check_pair, specificity.check_pair'in kendisidir
    (yalniz isabetler buradan gelir).
Olculdu (2026-11-08, 204 cift + 16.659 cift): sonuc check_pair ile birebir ayni (risk katmanlari,
hedef urun, PAR ikizi, tekrar ve urun sinirlari). Sure: havuz (130-190 primer) 6,5-8,5 sn (12 isci),
tam liste (ortanca 503 primer) ortanca 12,8 sn.

Tarama.risk: ciftin yan urun sayilarini isabet dizilerinden vektorle hesaplar (urun listesi kurmadan);
sadece_karar=True ise kendi urunleri zaten orta/yuksek riskliyse erken durur.
"""
import multiprocessing as mp

import numpy as np

import par
import specificity as S

BLOK = 250_000          # tohum kodlari bu boyda bloklarla (bellek ~80 MB/isci); sonuc bloktan bagimsiz
_LUT = np.full(256, 4, np.uint8)
for _i, _b in enumerate(b"ACGT"):
    _LUT[_b] = _i
_TUM = bytes.maketrans(b"ACGT", b"TGCA")
_KAYDIR = 33            # anahtar = kromozom sirasi << 33 | konum (konum < 2^31)


def _kod(seed):
    k = 0
    for b in seed:
        k = (k << 2) | int(_LUT[b])
    return k


# ------------------------------------------------------------------ isci
_CW = {}


def _durdu():
    """Arama durduruldu mu (Tarama: iptal): kalan parcalar taranmaz, sonuc gonderilmez."""
    dur = _CW.get("dur")
    return dur is not None and dur.is_set()


def _kur(path, primerler, seed_len, max_mm, sinir, dur=None):
    desen = []                  # (primer_no, yon 0='+' 1='-', dizi, tohum kodu, lead)
    for pi, s in enumerate(primerler):
        b = s.encode("ascii")
        rc = b.translate(_TUM)[::-1]
        desen.append((pi, 0, b, _kod(b[-seed_len:]), len(b) - seed_len))
        desen.append((pi, 1, rc, _kod(rc[:seed_len]), 0))
    M = max(len(d[2]) for d in desen)
    pat = np.ones((len(desen), M), np.uint8)        # dolgu 1: genom baytlariyla hep uyumsuz
    for j, d in enumerate(desen):
        pat[j, :len(d[2])] = np.frombuffer(d[2], np.uint8)
    plen = np.array([len(d[2]) for d in desen], np.int64)
    gerek = np.zeros(4097, bool)
    gerek[[d[3] for d in desen]] = True
    _CW.update(path=path, seed_len=seed_len, max_mm=max_mm, sinir=sinir, M=M, pat=pat, plen=plen,
               dolgu=M - plen, lead=np.array([d[4] for d in desen], np.int64), gerek=gerek,
               desen=[(d[0], d[1]) for d in desen], kod=np.array([d[3] for d in desen], np.uint16),
               pad=M + seed_len, dur=dur)
    S._ebeveyn_bekcisi()


def _blok_yerleri(arr, s0, s1):
    """Tohum baslangici [s0, s1) olan, gereken tohumlarin yerleri ve kodlari (koda gore gruplu,
    grup icinde artan; seq.find sirasiyla ayni)."""
    n = s1 - s0
    c = _LUT[arr[s0:s1 + 5]]
    k3 = c[:-2] * np.uint8(16)
    k3 += c[1:-1] * np.uint8(4)
    k3 += c[2:]
    k6 = k3[:n].astype(np.uint16)
    k6 <<= 6
    k6 += k3[3:3 + n]
    bad = c > 3                                     # A/C/G/T disi baz iceren 6-mer: gecersiz
    if bad.any():
        cs = np.concatenate([np.zeros(1, np.int32), np.cumsum(bad, dtype=np.int32)])
        k6[(cs[6:6 + n] - cs[:n]) > 0] = 4096
    yer = np.flatnonzero(_CW["gerek"][k6])
    kk = k6[yer]
    o = np.argsort(kk, kind="stable")
    return yer[o] + s0, kk[o]


def _parca(arg):
    """Bir is parcasi (specificity._build_tasks ile ayni). Doner: (ti, kayitlar, sayac, tasan)
    kayitlar: [(primer_no, alt_no, yon, bes int32, mm int8)]."""
    ti, task = arg
    sinir, M = _CW["sinir"], _CW["M"]
    desen = _CW["desen"]
    sayac, kayit = {}, []
    for si, sub in enumerate(task):
        if _durdu():
            return ti, [], {}, []
        name, offset, lenc, lenb, chrom_len, base_start, base_count = sub
        read_start = max(0, base_start - _CW["pad"])
        read_end = min(chrom_len, base_start + base_count + _CW["pad"])
        seq = S._read_bases(_CW["path"], offset, lenc, lenb, read_start, read_end - read_start)
        L = len(seq)
        arr = np.frombuffer(seq + bytes(M), np.uint8)
        pencere = np.lib.stride_tricks.sliding_window_view(arr, M)
        i_lo, i_hi = base_start - read_start, min(base_start + base_count - read_start, L - 5)
        toplanan = {}
        for s0 in range(i_lo, max(i_lo, i_hi), BLOK):
            if _durdu():
                return ti, [], {}, []                       # durduruldu: sonuc kullanilmaz
            yer, kk = _blok_yerleri(arr, s0, min(s0 + BLOK, i_hi))
            if not len(yer):
                continue
            los = np.searchsorted(kk, _CW["kod"], "left")
            cnt = np.searchsorted(kk, _CW["kod"], "right") - los
            for d0 in range(0, len(cnt), 256):              # bellek: desen gruplari
                c_ = cnt[d0:d0 + 256]
                t_ = int(c_.sum())
                if not t_:
                    continue
                di = np.repeat(np.arange(d0, d0 + len(c_)), c_)
                ofs = np.arange(t_) - np.repeat(np.cumsum(c_) - c_, c_) + np.repeat(los[d0:d0 + 256], c_)
                bas = yer[ofs] - _CW["lead"][di]
                ok = (bas >= 0) & (bas + _CW["plen"][di] <= L)
                if not ok.all():
                    bas, di = bas[ok], di[ok]
                if not len(bas):
                    continue
                mm = np.count_nonzero(pencere[bas] != _CW["pat"][di], axis=1) - _CW["dolgu"][di]
                k = mm <= _CW["max_mm"]
                if not k.any():
                    continue
                bas, di, mm = bas[k], di[k], mm[k]
                sinirlar = np.flatnonzero(np.diff(di)) + 1
                for b_, m_, d_ in zip(np.split(bas, sinirlar), np.split(mm, sinirlar),
                                      di[np.concatenate([[0], sinirlar])].tolist()):
                    toplanan.setdefault(desen[d_], []).append((b_, m_))
        # parca basi sinir: primer basina '+' sonra '-' (specificity._scan_range ile ayni)
        for pi in sorted({x[0] for x in toplanan}):
            for yon in (0, 1):
                if sayac.get(pi, 0) > sinir:
                    continue
                parc = toplanan.get((pi, yon))
                if not parc:
                    continue
                bas = np.concatenate([x[0] for x in parc])
                mm = np.concatenate([x[1] for x in parc])
                onceki = sayac.get(pi, 0)
                if onceki + len(bas) > sinir:
                    bas, mm = bas[:sinir - onceki], mm[:sinir - onceki]
                    sayac[pi] = sinir + 1
                else:
                    sayac[pi] = onceki + len(bas)
                if len(bas):
                    plen = int(_CW["plen"][2 * pi + yon])
                    bes = read_start + bas + 1 + (0 if yon == 0 else plen - 1)    # 5' ucu, 1-tabanli
                    kayit.append((pi, si, yon, bes.astype(np.int32), mm.astype(np.int8)))
    return ti, kayit, sayac, [pi for pi, n in sayac.items() if n > sinir]


# ------------------------------------------------------------------ ana surec
class Tarama:
    """Bir primer kumesinin tek gecis taramasi. iptal: her parca sonucunda cagrilir (istisna atarak
    durdurur). p: ozgulluk ayarlari (varsayilan specificity.SPEC_DEFAULTS, rozetle ayni)."""

    def __init__(self, fasta, primerler, p=None, iptal=None):
        self.p = p = dict(S.SPEC_DEFAULTS if p is None else p)
        assert int(p["max_mismatch"]) <= 4 and int(p["seed_len"]) == 6
        self.fasta = fasta
        self.primerler = sorted({x.upper() for x in primerler})
        self.no = {s: i for i, s in enumerate(self.primerler)}
        recs = S.read_fai(fasta)
        sira = {r[0]: i for i, r in enumerate(recs)}
        self.tasks = S._build_tasks(recs, int(p["chunk_bases"]))
        self._krom = [[sira[sub[0]] for sub in t] for t in self.tasks]
        n = len(self.primerler)
        self._seg = [[] for _ in range(n)]      # (ti, si, yon, bes, mm) ozgun sirada
        self._sayac = [dict() for _ in range(n)]
        self._tasan = [set() for _ in range(n)]
        self._dizi = {}
        args = (fasta, self.primerler, int(p["seed_len"]), int(p["max_mismatch"]), int(p["max_sites_per_task"]))
        workers = int(p.get("workers") or 0) or min(mp.cpu_count() or 1, 12)
        workers = max(1, min(workers, len(self.tasks)))
        sonuc = [None] * len(self.tasks)
        is_ = list(enumerate(self.tasks))
        with S._TARAMA:                         # ayni anda tek genom taramasi (bkz. specificity)
            if workers == 1:
                _kur(*args)
                for x in map(_parca, is_):
                    sonuc[x[0]] = x
                    if iptal:
                        iptal()
            else:
                # Durdurma (iptal istisnasi) havuzu terminate() ile kesmez: isciler isaretle bos
                # doner, kalan sonuclar okunur, havuz olagan yoldan kapanir, istisna sonra atilir.
                # Sonuc gonderilirken terminate() Windows'ta kilitlenebiliyordu ve tarama kilidi
                # (_TARAMA) birakilmiyordu (2026-11-09, bkz. specificity._scan_genome).
                dur, durdur = mp.Event(), None
                with mp.Pool(workers, initializer=_kur, initargs=args + (dur,)) as pool:
                    for x in pool.imap_unordered(_parca, is_, chunksize=1):
                        if durdur is not None:
                            continue            # havuz bosaltiliyor
                        sonuc[x[0]] = x
                        if iptal:
                            try:
                                iptal()
                            except BaseException as e:
                                durdur = e
                                dur.set()
                    pool.close()
                    pool.join()
                if durdur is not None:
                    raise durdur
        for ti, kayit, sayac, tasan in sonuc:
            for pi, si, yon, bes, mm in kayit:
                self._seg[pi].append((ti, si, yon, bes, mm))
            for pi, c in sayac.items():
                self._sayac[pi][ti] = c
            for pi in tasan:
                self._tasan[pi].add(ti)
        for v in self._seg:
            v.sort(key=lambda x: (x[0], x[1], x[2]))

    # -------- check_pair ile birebir yol
    def isabetler(self, fasta_path, fwd, rev, p):
        """specificity.scan_genome(fasta, fwd, rev, p) ile ayni Isabetler (check_pair'in isabet=)."""
        for k in ("seed_len", "max_mismatch", "max_sites_per_task", "max_sites_per_primer", "chunk_bases"):
            if int(p[k]) != int(self.p[k]):
                raise ValueError(f"tarama ayari farkli: {k}")
        pf, pr = self.no[fwd.upper()], self.no[rev.upper()]
        tasks = self.tasks

        def gruplu(pi):
            g = {}
            for ti, si, yon, bes, mm in self._seg[pi]:
                g.setdefault(ti, []).append((si, yon, bes, mm))
            return g
        gf, gr = gruplu(pf), (gruplu(pr) if pr != pf else None)
        gr = gf if gr is None else gr

        def parcalar():
            for ti in range(len(tasks)):
                kf, kr = gf.get(ti, []), gr.get(ti, [])
                hits = []
                for si in sorted({x[0] for x in kf} | {x[0] for x in kr}):
                    ad = tasks[ti][si][0]
                    for etiket, kay, p_ in (("F", kf, pf), ("R", kr, pr)):
                        L = len(self.primerler[p_])
                        for s_, yon, bes, mm in kay:
                            if s_ != si:
                                continue
                            y, d3 = ("+", L - 1) if yon == 0 else ("-", 1 - L)
                            hits.extend((etiket, y, ad, a, a + d3, c) for a, c in zip(bes.tolist(), mm.tolist()))
                sayac = {}
                if ti in self._sayac[pf]:
                    sayac["F"] = self._sayac[pf][ti]
                if ti in self._sayac[pr]:
                    sayac["R"] = self._sayac[pr][ti]
                yield hits, sayac, [e for e, p_ in (("F", pf), ("R", pr)) if ti in self._tasan[p_]]
        return S._birlestir(parcalar(), int(self.p["max_sites_per_primer"]), ("F", "R"))[0]

    def check_pair(self, fwd, rev, expected=None, assembly=None):
        """specificity.check_pair'in kendisi (params={}); genom bu taramanin kayitlarindan okunur."""
        return S.check_pair(self.fasta, fwd, rev, expected=expected, params={}, assembly=assembly,
                            isabet=self.isabetler)

    # -------- hizli risk sayimi
    def _diziler(self, pi, assembly):
        d = self._dizi.get(pi)
        if d is not None:
            return d
        pars = list(par.PAR.get(assembly, {}).values()) if assembly else []
        art = {0: ([], []), 1: ([], [])}
        yp, xp = {0: [], 1: []}, {0: set(), 1: set()}       # Y / X'in PAR'indaki isabetler
        toplam = 0
        for ti, si, yon, bes, mm in self._seg[pi]:
            art[yon][0].append(bes.astype(np.int64) + (self._krom[ti][si] << _KAYDIR))
            art[yon][1].append(mm)
            toplam += len(bes)
            kr = par._kr(self.tasks[ti][si][0]).upper()
            if kr in ("X", "Y"):
                for xb, yb in pars:
                    lo, hi = xb if kr == "X" else yb
                    sel = (bes >= lo) & (bes <= hi)
                    if sel.any():
                        z = list(zip(bes[sel].tolist(), mm[sel].tolist()))
                        if kr == "Y":
                            yp[yon] += z
                        else:
                            xp[yon].update(z)
        out = {}
        for yon in (0, 1):
            k = np.concatenate(art[yon][0]) if art[yon][0] else np.zeros(0, np.int64)
            m = np.concatenate(art[yon][1]) if art[yon][1] else np.zeros(0, np.int8)
            o = np.argsort(k, kind="stable")
            out[yon] = (k[o], m[o])
        # '-' isabetleri uyumsuz sayisina gore ayri dizilerde (bellek: anahtar basina 8 bayt)
        eksi = [out[1][0][out[1][1] == j] for j in range(5)]
        d = {"arti": out[0], "eksi": eksi, "yp": yp, "xp": xp,
             "tasti": bool(self._tasan[pi]) or toplam > int(self.p["max_sites_per_primer"])}
        d["oz"] = self._carp(d, d)
        self._dizi[pi] = d
        return d

    def _carp(self, A, B):
        """A'nin '+' isabetleri x B'nin '-' isabetleri: (urun, yuksek, orta) sayilari."""
        ka, ma = A["arti"]
        if not len(ka):
            return 0, 0, 0
        span = int(self.p["max_offtarget_product"]) - 1
        cnt = np.stack([np.searchsorted(kb, ka + span, "right") - np.searchsorted(kb, ka, "left")
                        for kb in B["eksi"]], axis=1)
        cc = np.concatenate([np.zeros((len(ka), 1), np.int64), np.cumsum(cnt, axis=1)], axis=1)
        r = np.arange(len(ka))
        yuk = cc[r, np.clip(int(self.p["risk_high_max"]) - ma.astype(np.int64), -1, 4) + 1].sum()
        le5 = cc[r, np.clip(int(self.p["risk_medium_max"]) - ma.astype(np.int64), -1, 4) + 1].sum()
        return int(cc[:, 5].sum()), int(yuk), int(le5 - yuk)

    def risk(self, fwd, rev, expected=None, assembly=None, sadece_karar=False):
        """check_pair (params={}) karar alanlari: {hata, specific, yuksek, orta, dusuk}.
        hata: None | 'tekrar' (isabet siniri) | 'urun' (urun siniri). sadece_karar: ozgul degilse
        sayilar eksik olabilir (yalniz specific=False guvenilir)."""
        F = self._diziler(self.no[fwd.upper()], assembly)
        R = self._diziler(self.no[rev.upper()], assembly)
        if F["tasti"] or R["tasti"]:
            return {"hata": "tekrar", "specific": False}
        hi_m, med_m = int(self.p["risk_high_max"]), int(self.p["risk_medium_max"])
        span = int(self.p["max_offtarget_product"]) - 1
        n_int, y_int, o_int = self._hedef(F, R, expected)
        ypar = bool(F["yp"][0] or F["yp"][1] or R["yp"][0] or R["yp"][1])
        if sadece_karar and not ypar:
            # kendi urunleri (F+F, R+R) tek basina orta/yuksek riskli urun veriyorsa ozgul degildir
            if F["oz"][1] + F["oz"][2] + (R["oz"][1] + R["oz"][2] if R is not F else 0) > y_int + o_int:
                return {"hata": None, "specific": False}
        top = yuk = orta = 0
        for a, b in ((F, F), (R, R), (F, R), (R, F)):          # F+F, R+R, F+R, R+F
            x = a["oz"] if a is b else self._carp(a, b)
            top, yuk, orta = top + x[0], yuk + x[1], orta + x[2]
        if top > int(self.p["max_products"]):
            return {"hata": "urun", "specific": False}
        # PAR ikizi (par.urun_ikizleri): Y'nin PAR'indaki urunun X'teki esi ayni etiket/uyumsuzlukla varsa
        n_tw = y_tw = o_tw = 0
        if assembly and ypar:
            for A in (F, R):
                for B in (F, R):
                    for fa, ma in A["yp"][0]:
                        for fb, mb in B["yp"][1]:
                            if 0 <= fb - fa <= span:
                                ea, eb = par.es_konum(assembly, "Y", fa), par.es_konum(assembly, "Y", fb)
                                if ea and eb and (ea[1], ma) in A["xp"][0] and (eb[1], mb) in B["xp"][1]:
                                    n_tw += 1
                                    y_tw += ma + mb <= hi_m
                                    o_tw += hi_m < ma + mb <= med_m
        yuk, orta = yuk - y_tw - y_int, orta - o_tw - o_int
        off = top - n_tw - n_int
        return {"hata": None, "specific": yuk == 0 and orta == 0, "yuksek": yuk, "orta": orta,
                "dusuk": off - yuk - orta, "intended": n_int > 0}

    def _hedef(self, F, R, expected):
        """Hedef urun(ler): ayni kromozom, iki ucu +-5 bp (specificity._is_intended). Doner: (sayi,
        yuksek riskli katmanda olan, orta riskli katmanda olan)."""
        n_int = y_int = o_int = 0
        if not expected or str(expected.get("chrom")) not in self._sira_ad():
            return 0, 0, 0
        hi_m, med_m = int(self.p["risk_high_max"]), int(self.p["risk_medium_max"])
        span = int(self.p["max_offtarget_product"]) - 1
        taban = self._sira_ad()[str(expected["chrom"])] << _KAYDIR
        es, ee = int(expected["start"]), int(expected["end"])
        artilar, eksiler = [], []
        for X_ in ((F, R) if F is not R else (F, F)):
            k, m = X_["arti"]
            a, b = np.searchsorted(k, [taban + es - 5, taban + es + 6])
            artilar += list(zip(k[a:b].tolist(), m[a:b].tolist()))
            for j, kb in enumerate(X_["eksi"]):
                a, b = np.searchsorted(kb, [taban + ee - 5, taban + ee + 6])
                eksiler += [(v, j) for v in kb[a:b].tolist()]
        for ka, ma in artilar:
            for kb, mb in eksiler:
                if 0 <= kb - ka <= span:
                    n_int += 1
                    y_int += ma + mb <= hi_m
                    o_int += hi_m < ma + mb <= med_m
        return n_int, y_int, o_int

    def _sira_ad(self):
        if not hasattr(self, "_sa"):
            self._sa = {}
            for t, kr in zip(self.tasks, self._krom):
                for sub, k in zip(t, kr):
                    self._sa[sub[0]] = k
        return self._sa

    def alt_sinir(self, fwd, rev, expected=None, assembly=None):
        """Ciftin (yuksek, orta) sayisinin alt siniri (sozluk sirasinda): yalniz kendi urunleri
        (F+F, R+R), hedef urun(ler) dusulerek. PAR ikizi de duser; Y PAR isabeti olan primerde (0, 0)."""
        F = self._diziler(self.no[fwd.upper()], assembly)
        R = self._diziler(self.no[rev.upper()], assembly)
        if F["tasti"] or R["tasti"] or F["yp"][0] or F["yp"][1] or R["yp"][0] or R["yp"][1]:
            return (0, 0)
        _n, y_int, o_int = self._hedef(F, R, expected)
        oy = F["oz"][1] + (R["oz"][1] if R is not F else 0)
        oo = F["oz"][2] + (R["oz"][2] if R is not F else 0)
        return (max(0, oy - y_int), max(0, oo - o_int))
