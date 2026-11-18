# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda.
"""
Ucuncu taraf lisans bildirimlerini (THIRD-PARTY-NOTICES.txt) uretir.

Neden: MIT/BSD/Apache lisanslari, bilesenle birlikte telif satirinin ve lisans
metninin de verilmesini SART kosar. Uygulama klasorundeki LICENSE dosyasi GPL
metniyle degistirildiginde Electron'un MIT bildirimi kaybolmustu (2026-10-01).
Metinler elle yazilmaz: sanal ortamdaki paketlerin KENDI lisans dosyalarindan
okunur; paket guncellenince betik yeniden calistirilir.

Calistirma (depo kokunde):
    backend\\.venv\\Scripts\\python.exe backend\\lisans_bildirimi.py
"""
import os
import re
import ssl
import sys
import platform
import pyexpat
import importlib.metadata as md

from packaging.requirements import Requirement

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(BURASI)
CIKTI = os.path.join(KOK, "THIRD-PARTY-NOTICES.txt")

# Paketin metadata'sinda lisans DOSYASI olmayanlar: metin resmi deposundan alindi.
ELLE = {
    "flask-cors": "Copyright (C) 2025 Cory Dolphin\n\n{MIT}",
}

MIT = """Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""

# Electron dagitimindaki LICENSE dosyasinin aynisi (electron/dist/LICENSE)
ELECTRON = "Copyright (c) Electron contributors\nCopyright (c) 2013-2020 GitHub Inc.\n\n" + MIT

# Python'un kendi belgesinden (Doc/html/license.html) birebir; yerel kaynak.
EXPAT = """Copyright (c) 1998, 1999, 2000 Thai Open Source Software Center Ltd
                               and Clark Cooper

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""

LIBMPDEC = """Copyright (c) 2008-2020 Stefan Krah. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
SUCH DAMAGE."""

# klib/khash.h: primer3 tekerleginin kaynak agacindaki dosyanin baslik yorumundan
# (primer3/src/libprimer3/klib/khash.h); lisans metni MIT ile ayni.
KHASH = "Copyright (c) 2008, 2009, 2011 by Attractive Chaos <attractor@live.co.uk>\n\n" + MIT

CIZGI = "=" * 78


def _oku(f):
    """Paket dosyasini oku (bozuk karakterde durma; lisans metni olduğu gibi kalsin)."""
    with open(f.locate(), encoding="utf-8", errors="replace") as h:
        return h.read()


def _surum_electron():
    for yol in (os.path.join(KOK, "..", "AllPrime", "version"),
                os.path.join(KOK, "electron", "node_modules", "electron", "dist", "version")):
        if os.path.exists(yol):
            return open(yol, encoding="utf-8").read().strip()
    return "?"


def _calisma_bagimliliklari():
    """requirements.txt'teki paketler + gecisli bagimliliklari (bu platform icin)."""
    kok = []
    for satir in open(os.path.join(BURASI, "requirements.txt"), encoding="utf-8"):
        satir = satir.split("#")[0].strip()
        if satir:
            kok.append(re.split(r"[=<>!~ ;]", satir)[0])
    gorulen, sira = {}, list(kok)
    while sira:
        ad = sira.pop(0)
        try:
            d = md.distribution(ad)
        except md.PackageNotFoundError:
            continue
        anahtar = d.metadata["Name"].lower()
        if anahtar in gorulen:
            continue
        gorulen[anahtar] = d
        for r in d.requires or []:
            req = Requirement(r)
            if req.marker and not req.marker.evaluate({"extra": ""}):
                continue
            sira.append(req.name)
    return [gorulen[k] for k in sorted(gorulen)]


def _lisans_dosyalari(d):
    out = []
    for f in d.files or []:
        s = str(f).replace("\\", "/")
        ad = s.rsplit("/", 1)[-1]
        if ".dist-info/" in s and re.match(r"(LICEN[CS]E|COPYING|NOTICE)", ad, re.I):
            out.append(f)
    return out


def _ana_sayfa(d):
    for u in d.metadata.get_all("Project-URL") or []:
        if any(k in u.lower().split(",")[0] for k in ("source", "repository", "code", "homepage", "home")):
            return u.split(",", 1)[-1].strip()
    ilk = (d.metadata.get_all("Project-URL") or [""])[0]
    return d.metadata.get("Home-page") or ilk.split(",", 1)[-1].strip()


def _lisans_adi(d):
    lic = d.metadata.get("License-Expression") or ""
    if not lic:
        siniflar = [c.split("::")[-1].strip() for c in d.metadata.get_all("Classifier") or []
                    if c.startswith("License")]
        lic = ", ".join(siniflar) or (d.metadata.get("License") or "").splitlines()[0:1]
        lic = lic if isinstance(lic, str) else (lic[0] if lic else "")
    return lic


def bolum(baslik, ust, metin=None):
    s = [CIZGI, baslik, CIZGI, ust.strip(), ""]
    if metin:
        s += [metin.strip(), ""]
    return "\n".join(s) + "\n"


def main():
    parcalar = []
    parcalar.append(f"""AllPrime - Ucuncu taraf bilesenler ve lisanslari / Third-party notices
{CIZGI}
Bu dosya backend/lisans_bildirimi.py ile uretilir; elle duzenlemeyin.
This file is generated by backend/lisans_bildirimi.py; do not edit by hand.

AllPrime'in kendisi: Copyright (c) 2026 Eren Kilinc (bkz. AUTHORS). GNU GPL
surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
(GPL-2.0-or-later). Paketli motor Apache-2.0 lisansli bilesenler (requests,
OpenSSL) icerdiginden program, kurum disina bunlarla uyumlu olan GPL v3
kosullariyla dagitilir. Tam metinler: LICENSE (GPL v2), LICENSE-GPL-3.0.txt
(GPL v3). Asagidaki bilesenler kendi lisanslariyla birlikte dagitilir; telif
hakki sahiplerine aittir. AllPrime'in kaynak kodu (motor, arayuz, derleme
betikleri) uygulama klasorundedir: kaynak/AllPrime-kaynak-<surum>.zip.

AllPrime itself: Copyright (c) 2026 Eren Kilinc (see AUTHORS). Licensed under
the GNU GPL version 2 or (at your option) any later version (GPL-2.0-or-later).
Because the packaged engine contains Apache-2.0 components (requests, OpenSSL),
the program is distributed outside the institution under the GPL v3, which is
compatible with them. Full texts: LICENSE (GPL v2), LICENSE-GPL-3.0.txt (GPL v3).
The components below are distributed under their own licences and remain the
property of their copyright holders. AllPrime's source code (engine, interface,
build scripts) is in the application folder: kaynak/AllPrime-kaynak-<version>.zip.
""")

    # --- Calisma ortami (paketlenmis motorun icinde) -------------------------
    py_lisans = os.path.join(sys.base_prefix, "LICENSE.txt")
    parcalar.append(bolum(
        f"Python {platform.python_version()}  (Python Software Foundation License)",
        "Paketlenmis motorun calisma ortami (python313.dll ve standart kutuphane). "
        "Asagidaki metin Python'un kendi lisans dosyasidir ve icine gomulu bzip2, "
        "libffi vb. bilesenlerin bildirimlerini de icerir.",
        open(py_lisans, encoding="utf-8", errors="replace").read()
        if os.path.exists(py_lisans) else "(LICENSE.txt bulunamadi: https://docs.python.org/3/license.html)"))

    parcalar.append(bolum(
        f"{ssl.OPENSSL_VERSION}  (Apache License 2.0)",
        "libssl-3.dll / libcrypto-3.dll - Python ile birlikte gelir.\n"
        "Copyright (c) 1998-2025 The OpenSSL Project Authors\n"
        "Copyright (c) 1995-1998 Eric A. Young, Tim J. Hudson\n"
        "Apache License 2.0 tam metni asagida 'requests' bolumundedir; "
        "https://www.openssl.org/source/license.html"))

    parcalar.append(bolum(
        "Microsoft Visual C++ calisma kitapligi  (VCRUNTIME140.dll, VCRUNTIME140_1.dll, "
        "msvcp140-*.dll)",
        "Microsoft Visual C++ Redistributable lisansinin izin verdigi bicimde uygulama "
        "ile birlikte dagitilir. Copyright (c) Microsoft Corporation. VCRUNTIME140*.dll "
        "Python ile, msvcp140-*.dll (numpy.libs klasorunde, adi derleme aracinca "
        "degistirilmis) numpy ile gelir. / Distributed with the application as permitted "
        "by the Microsoft Visual C++ Redistributable licence. VCRUNTIME140*.dll comes "
        "with Python, msvcp140-*.dll (in numpy.libs, renamed by the build tool) with "
        "numpy. Metin yerelde bulunamadi / licence text not found locally; "
        "https://visualstudio.microsoft.com/license-terms/"))

    # Python'un kendi derlemesine gomulu uc bilesen. Metinler Python'un yerel belgesinden
    # (Doc/html/license.html "expat" ve "libmpdec" bolumleri) birebir alinmistir.
    parcalar.append(bolum(
        f"expat {pyexpat.EXPAT_VERSION.replace('expat_', '')}  (MIT)   -  pyexpat.pyd",
        "XML ayristirici; Python'un pyexpat eklentisine gomulu. Asagidaki metin Python "
        "belgelerindeki (Doc/html/license.html) expat bolumunun aynisidir. / XML parser "
        "built into Python's pyexpat extension; the text below is copied from the expat "
        "section of Python's own licence documentation.", EXPAT))

    parcalar.append(bolum(
        "libmpdec  (BSD-2-Clause)   -  _decimal.pyd",
        "Ondalik aritmetik kitapligi; Python'un _decimal eklentisine gomulu. Asagidaki "
        "metin Python belgelerindeki (Doc/html/license.html) libmpdec bolumunun "
        "aynisidir. / Decimal arithmetic library built into Python's _decimal extension; "
        "the text below is copied from the libmpdec section of Python's own licence "
        "documentation.", LIBMPDEC))

    parcalar.append(bolum(
        "liblzma (xz)  (public domain / 0BSD)   -  _lzma.pyd",
        "LZMA sikistirma kitapligi; Python'un _lzma eklentisine gomulu. Lisans metni "
        "yerelde bulunamadi (yalnizca ad ve lisans kimligi verilir); surum yerelde "
        "okunamadi. / LZMA compression library built into Python's _lzma extension. "
        "Licence text not found locally (only name and licence identifier are given); "
        "the version could not be read locally. https://tukaani.org/xz/"))

    try:
        pi = md.distribution("pyinstaller")
        copying = [f for f in pi.files or [] if str(f).replace("\\", "/").endswith("COPYING.txt")]
        metin = _oku(copying[0]) if copying else ""
        # Yalnizca PyInstaller'in kendi lisans ozeti (GPL metni LICENSE'ta zaten var)
        ozet = metin.split("GNU GENERAL PUBLIC LICENSE")[0].strip() if metin else ""
        parcalar.append(bolum(
            f"PyInstaller {pi.version}  (GPL v2 veya sonrasi + Bootloader Exception)",
            "Paketlenmis motoru (allprime-server.exe) olusturan arac; onyukleyicisi exe'ye "
            "gomuludur. GPL v2 tam metni: LICENSE.", ozet))
    except md.PackageNotFoundError:
        pass

    # --- primer3 --------------------------------------------------------------
    p3 = md.distribution("primer3-py")
    yazarlar = [f for f in p3.files or [] if str(f).replace("\\", "/").endswith("licenses/AUTHORS")]
    parcalar.append(bolum(
        f"primer3-py {p3.version}  (icinde primer3 2.6.1 kutuphanesi)  -  GNU GPL v2 veya sonrasi",
        "Hesaplama motoru. Copyright (c) 1996-2022 Whitehead Institute for Biomedical "
        "Research, Steve Rozen, Andreas Untergasser, Helen Skaletsky; Python baglantilari "
        "Copyright (c) 2014-2026 Ben Pruitt & Nick Conway, 2014-2018 Wyss Institute.\n"
        "GPL v2 tam metni: LICENSE. Kaynak kod: uygulama klasorunde "
        "resources/backend/_internal/primer3 (C ve Cython kaynaklari) ve "
        "https://github.com/libnano/primer3-py , https://github.com/primer3-org/primer3\n"
        "Paketteki amplicontm.c, amplicontm.h ve amplicontm_main.c (Amplicon3, Copyright (c) "
        "2021 Andreas Untergasser) GPL v3 veya sonrasi ile lisanslidir; motora derlenmez, "
        "yalnizca kaynak olarak bulunur; tekerlekteki komut satiri araclari (primer3_core, "
        "ntthal, ntdpal, oligotm, amplicon3_core) pakete konmaz. GPL v3 tam metni: "
        "LICENSE-GPL-3.0.txt.",
        _oku(yazarlar[0]) if yazarlar else None))

    parcalar.append(bolum(
        "klib/khash.h  (MIT)   -  primer3 kaynak agacinda (resources/backend/_internal/"
        "primer3/src/libprimer3/klib)",
        "Karma tablo basligi; primer3 kaynaginin parcasi ve primer3-py motoruna derlenir. "
        "Telif satiri khash.h dosyasinin baslik yorumundandir. / Hash table header, part "
        "of the primer3 sources and compiled into the primer3-py engine; the copyright "
        "line is from the header comment of khash.h.", KHASH))

    # --- Electron / Chromium --------------------------------------------------
    parcalar.append(bolum(
        f"Electron {_surum_electron()}  (MIT)",
        "Arayuzun calistigi ortam (AllPrime.exe). Electron'un icindeki Chromium ve "
        "diger bilesenlerin lisanslari uygulama klasorundeki LICENSES.chromium.html "
        "dosyasindadir.", ELECTRON))

    # --- Veri dosyalari ------------------------------------------------------
    # Kosullar 2026-10-31'de kaynaklarin kendi sayfalarindan okundu; alintilar birebir.
    parcalar.append(bolum(
        "Veri dosyalari / Data files  (genomes/, annotations/)",
        "Uygulama klasorundeki veri dosyalari asagidaki kaynaklardan indirilir; dbSNP "
        "tablosu AllPrime'in kendi indeks bicimine (.apidx) donusturulur, digerleri "
        "degistirilmeden kullanilir.\n"
        "The data files in the application folder are downloaded from the sources below; "
        "the dbSNP table is converted to AllPrime's own index format (.apidx), the others "
        "are used unchanged.\n\n"
        "Pakette / In the package: annotations/ = refGene (UCSC), MANE (NCBI), dbSNP index "
        "(from UCSC snp151Common, NCBI dbSNP build 151). Pakette yok / Not in the package: "
        "genom FASTA / genome FASTA (Ensembl; indirilir / downloaded). Calisma aninda / At "
        "run time: Ensembl REST (rest.ensembl.org, grch37.rest.ensembl.org), yalniz yerel "
        "genom ya da refGene yoksa / only when no local genome or refGene exists. Surum ve "
        "adresler: GELISTIRME.md 'Veri kaynaklari' / versions and addresses: GELISTIRME.md "
        "'Veri kaynaklari'. Atif (oneri) / Citation (suggested): kaynak, veri seti, adres, "
        "erisim tarihi / source, data set, address, access date.\n\n"
        "- Referans genom / Reference genome (GRCh37, GRCh38 primary assembly FASTA): "
        "Ensembl, https://ftp.ensembl.org/ . \"Ensembl imposes no restrictions on access "
        "to, or use of, the data provided and the software used to analyse and present "
        "it.\" https://www.ensembl.org/info/about/legal/disclaimer.html\n"
        "- Transkript tablosu / Transcript table (refGene) ve yaygin varyantlar / common "
        "variants (snp151Common, dbSNP 151): UCSC Genome Browser, "
        "https://hgdownload.soe.ucsc.edu/ . \"Please cite us if you use the Genome Browser "
        "software or data in a publication or web page.\" "
        "https://genome.ucsc.edu/conditions.html\n"
        "- MANE Select / MANE Plus Clinical listesi / list: NCBI, "
        "https://ftp.ncbi.nlm.nih.gov/refseq/MANE/ . \"NCBI itself places no restrictions on "
        "the use or distribution of the data contained therein.\" "
        "https://www.ncbi.nlm.nih.gov/home/about/policies/"))

    # --- Python paketleri -----------------------------------------------------
    for d in _calisma_bagimliliklari():
        ad = d.metadata["Name"]
        if ad.lower() == "primer3-py":
            continue
        dosyalar = _lisans_dosyalari(d)
        metinler = [_oku(f).strip() for f in dosyalar]
        if not metinler and ad.lower() in ELLE:
            metinler = [ELLE[ad.lower()].replace("{MIT}", MIT)]
        if not metinler:
            metinler = ["(Paket lisans dosyasi icermiyor; ana sayfaya bakin.)"]
        parcalar.append(bolum(f"{ad} {d.version}  ({_lisans_adi(d)})", _ana_sayfa(d),
                              "\n\n".join(metinler)))

    # setuptools'un motora gomulen parcalari (PyInstaller calisma kancalari getirir)
    try:
        st = md.distribution("setuptools")
        gomulu = [f for f in st.files or [] if re.search(
            r"setuptools/_vendor/(importlib_metadata|jaraco[._]text)[^/]*\.dist-info/(licenses/)?LICENSE",
            str(f).replace("\\", "/"))]
        if gomulu:
            parcalar.append(bolum(
                f"setuptools {st.version} icinden gomulu parcalar (importlib_metadata, jaraco.text)",
                "PyInstaller'in calisma kancalari motora ekler.",
                "\n\n".join(f"--- {str(f).replace(chr(92), '/').split('/_vendor/')[1].split('.dist-info')[0]} ---\n"
                            + _oku(f).strip() for f in gomulu)))
    except md.PackageNotFoundError:
        pass

    with open(CIKTI, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parcalar))
    print(f"yazildi: {CIKTI}  ({os.path.getsize(CIKTI) / 1024:.0f} KB, {len(parcalar) - 1} bolum)")


if __name__ == "__main__":
    main()
