# AllPrime

**Varyanta özgü PCR primer tasarımı için Windows masaüstü programı.**
*A Windows desktop program for variant-specific PCR primer design.* ([English below](#english))

Tanıtım sayfası / Website: <https://allprime-app.github.io/>

---

## Türkçe

AllPrime, bir varyantı ya da bölgeyi çoğaltacak primer çiftlerini tasarlar, çiftleri insan
genomunda tarayarak özgüllüğünü denetler ve yaygın varyantların (dbSNP) üzerine gelen primerlerden
kaçınır. Hesaplama [primer3](https://github.com/primer3-org/primer3) ile yapılır. Arayüz Türkçe ve
İngilizcedir.

### Neler yapar

- **DNA · genomik:** genomik koordinattan (GRCh37 ya da GRCh38) primer tasarımı.
- **RNA · cDNA:** NM_ transkript kodu ve `c.` gösterimiyle intronsuz cDNA üzerinde tasarım; ekson atlama testi.
- **Dizi:** yapıştırılan dizi üzerinde tasarım; iki diziyle füzyon transkripti tasarımı.
- **Kırılma noktası:** delesyon ve duplikasyon sınırlarına primer ve isteğe bağlı kontrol primeri.
- **Değerlendir:** elinizdeki bir primer çiftinin Tm, dimer ve hairpin değerleri ile genomdaki ürünleri.
- **Özgüllük kontrolü:** çiftin yerel genomda başka ürün verip vermediği; psödogen / yakın-özdeş kopya uyarısı.
- **Favoriler:** beğenilen çiftleri saklama, CSV olarak dışa aktarma.

### Veriler bilgisayarınızda kalır

Genom ve ek veri dosyaları bilgisayarınıza indirildikten sonra bütün hesaplama yerelde yapılır ve
çalışmak için internet gerekmez. Yerel genom ya da transkript tablosu yoksa program yalnızca gereken
diziyi almak için Ensembl REST servisine sorgu gönderir.

### Sistem gereksinimi

- Windows 10 ya da 11, 64 bit
- RAM: önerilen 8 GB, en az 4 GB
- Disk: iki genom derlemesi ve bütün verilerle yaklaşık 8 GB boş yer

### İndirme ve kurulum

1. [Sürümler (Releases)](../../releases/latest) sayfasından `AllPrime-<sürüm>-win-x64.zip` dosyasını indirin.
2. Zip'i kısa yollu bir klasöre açın (örneğin `C:\AllPrime\`); iç içe çok sayıda klasörün altına açmayın.
3. `AllPrime.exe` dosyasını çalıştırın. Program imzalı olmadığı için Windows ilk açılışta bir uyarı gösterebilir.
   İlk açılışta pencerenin gelmesi 20–50 saniye sürebilir; bu sırada ekranda bir şey görünmez.
   Sonraki açılışlar birkaç saniye sürer.
4. **⚙ Ayarlar › Veri dosyaları ve genom** bölümünden kullanacağınız genom derlemesini indirin
   (her derleme yaklaşık 3 GB; kaynağı Ensembl).

Ayrıntılı kurulum ve kullanım: [KURULUM.txt](KURULUM.txt) (İngilizcesi: [USER_GUIDE.txt](USER_GUIDE.txt)).

### Kullanım amacı

AllPrime araştırma amaçlıdır; tanı amaçlı bir tıbbi cihaz değildir. Tasarlanan primerler
kullanılmadan önce laboratuvarda doğrulanmalıdır. Program hiçbir garanti olmaksızın sunulur.

### Atıf

Çalışmanızda AllPrime'ı kullandıysanız lütfen atıf yapın; bilgiler [CITATION.cff](CITATION.cff)
dosyasındadır (GitHub'da sağ üstteki "Cite this repository" düğmesi).

DOI (bütün sürümler; her zaman en son sürüme gider): [10.5281/zenodo.24444832](https://doi.org/10.5281/zenodo.24444832)

### Lisans

AllPrime © 2026 Eren Kılınç. Program GNU GPL sürüm 2 ya da (isteğinize göre) daha sonraki bir sürümü
ile lisanslıdır (GPL-2.0-or-later). Paketli motor Apache-2.0 lisanslı bileşenler içerdiğinden
derlenmiş program GPL v3 koşullarıyla dağıtılır. Metinler: [LICENSE](LICENSE) (GPL v2),
[LICENSE-GPL-3.0.txt](LICENSE-GPL-3.0.txt) (GPL v3). Üçüncü taraf bileşenler ve veri kaynakları:
[THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).

### Kaynak koddan çalıştırma ve geliştirme

Programın iç işleyişi, veri kaynakları, testler ve paketleme adımları:
[GELISTIRME.md](GELISTIRME.md).

### İletişim

Soru, öneri ve hata bildirimi: **eren.501kilinc@gmail.com**
Lütfen hasta adı ya da kimliği gibi kişisel veri göndermeyin.

---

## English

AllPrime designs primer pairs that amplify a variant or a region, checks their specificity by
scanning the human genome, and avoids primers that sit on common variants (dbSNP). Calculations
are done with [primer3](https://github.com/primer3-org/primer3). The interface is available in
Turkish and English.

### What it does

- **DNA · genomic:** primer design from a genomic coordinate (GRCh37 or GRCh38).
- **RNA · cDNA:** design on intron-free cDNA from an NM_ transcript and `c.` notation; exon-skipping assay.
- **Sequence:** design on a pasted sequence; fusion-transcript design from two sequences.
- **Breakpoint:** primers across deletion and duplication boundaries, with an optional control primer.
- **Evaluate:** Tm, dimer and hairpin values of an existing primer pair and its products in the genome.
- **Specificity check:** whether the pair gives other products in the local genome; pseudogene / near-identical copy warning.
- **Favorites:** save the pairs you like and export them as CSV.

### Your data stays on your computer

Once the genome and annotation files are downloaded, all calculations run locally and no internet
connection is needed. If no local genome or transcript table is present, the program queries the
Ensembl REST service only to fetch the required sequence.

### System requirements

- Windows 10 or 11, 64-bit
- RAM: 8 GB recommended, 4 GB minimum
- Disk: about 8 GB free with both genome assemblies and all data files

### Download and installation

1. Download `AllPrime-<version>-win-x64.zip` from the [Releases](../../releases/latest) page.
2. Extract it to a folder with a short path (for example `C:\AllPrime\`); avoid deeply nested folders.
3. Run `AllPrime.exe`. The program is not code-signed, so Windows may show a warning on first launch.
   On first launch the window may take 20–50 seconds to appear, with nothing on screen meanwhile.
   Later launches take a few seconds.
4. In **⚙ Settings › Data files and genome**, download the genome assembly you need
   (about 3 GB per assembly; source: Ensembl).

The detailed installation and user guide is [USER_GUIDE.txt](USER_GUIDE.txt) (Turkish: [KURULUM.txt](KURULUM.txt)).

### Intended use

AllPrime is for research use; it is not a diagnostic medical device. Designed primers must be
validated in the laboratory before use. The program comes with no warranty.

### Citation

If you use AllPrime in your work, please cite it; see [CITATION.cff](CITATION.cff)
(the "Cite this repository" button on GitHub).

DOI (all versions; always resolves to the latest): [10.5281/zenodo.24444832](https://doi.org/10.5281/zenodo.24444832)

### License

AllPrime © 2026 Eren Kılınç. Licensed under the GNU GPL version 2 or (at your option) any later
version (GPL-2.0-or-later). Because the packaged engine contains Apache-2.0 licensed components,
the compiled program is distributed under the terms of GPL v3. Texts: [LICENSE](LICENSE) (GPL v2),
[LICENSE-GPL-3.0.txt](LICENSE-GPL-3.0.txt) (GPL v3). Third-party components and data sources:
[THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).

### Running from source and development

Internals, data sources, tests and packaging are described in [GELISTIRME.md](GELISTIRME.md)
(in Turkish).

### Contact

Questions, suggestions and bug reports: **eren.501kilinc@gmail.com**
Please do not send personal data such as patient names or IDs.
