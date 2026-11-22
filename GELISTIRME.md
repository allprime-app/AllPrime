# AllPrime - Geliştirici belgesi

Bu belge programın iç işleyişini, tasarım kararlarını ve geliştirme / test / paketleme adımlarını anlatır.
Kullanım için: [README.md](README.md), [KURULUM.txt](KURULUM.txt) ve İngilizcesi [USER_GUIDE.txt](USER_GUIDE.txt).
`USER_GUIDE.txt`, `KURULUM.txt`'nin bölüm bölüm çevirisidir: birini değiştirince ötekini de güncelleyin
(nöbetçi `test_ingilizce_kilavuz` bölüm sayısını ve ölçülen sayıları karşılaştırır).

Varyanta özgü primer tasarımı. Arayüz Türkçe ve İngilizce çalışır. Tasarım modları
(ayrıca hazır primerler için Değerlendir sekmesi):

- **DNA · genomik** — genomik koordinat (veya gen + koordinat) verilir, primerler doğrudan genomik (+) sarmal üzerinde tasarlanır.
- **RNA · cDNA** — NM_ transkript kodu verilir, şablon intronsuz cDNA'dır. Transkript her zaman **GRCh38** genomundan (MANE Select GRCh38 üzerinde tanımlıdır) kurulur; üstte GRCh37 seçili olsa da böyledir ve sonuçta bunu söyleyen kısa bir not çıkar. Kodlayan bölgesi tutarsız çıkan transkriptlerde hizalama uyarısı gösterilir (bkz. "RNA sekmesi: GRCh38 ve hizalama uyarısı"). İki alt mod:
  - **Varyant (c.)** — `c.1234`, `c.-45`, `c.*120` gösterimleri desteklenir. `c.524A>G` gibi tek baz değişiminde yazılan referans baz transkriptteki bazla karşılaştırılır; uyuşmazsa sonuçta uyarı çıkar (tasarım engellenmez); `c.215 A>G` gibi boşluklu yazım da denetlenir ve Değerlendir'in RNA modunda yazılan c. hedefi için de aynı uyarı çıkar.
  - **Ekson atlama testi** — atlanacak ekson(lar)ın iki yanındaki eksonlara primer konur; normal ve atlanmış transkript farklı boyda ürün verir. Bir ya da birden çok ekson seçilebilir (bkz. "Ekson atlama: birden çok ekson seçimi").
- **Dizi** — genom veya transkript gerekmez, dizi doğrudan yapıştırılır. İki alt mod:
  - **Tek dizi** — verilen dizi üzerinde primer. Hedef, köşeli parantezle (`ACGT[A/G]TTT`) veya konum girilerek işaretlenir. Hedef dizinin ucuna çok yakınsa (primerlere yer kalmıyorsa) çift çıkmaz ve sebep, gereken baz sayısıyla yazılır.
  - **İki dizi** — forward primer birinci dizinin, reverse primer ikinci dizinin içinden seçilir. **Füzyon transkripti** (forward A geninde, reverse B geninde) ve **delesyon kırılma noktası** tasarımlarının doğru modeli budur.
- **Kırılma noktası** — delesyon ya da duplikasyonun genomik sınırları verilir; dizi genomdan otomatik çekilir (bkz. aşağıdaki bölüm).

Hesaplama primer3 ile yapılır (SantaLucia 1998 NN Tm + tuz/Mg/dNTP düzeltmeleri). Self/dimer değerleri **legacy hizalama** ile üretilir, yani NCBI Primer-BLAST'ta görülen sayılarla birebir aynı birimdedir. Tablodaki **Hairpin °C** sütunu primerin termodinamik saç tokası erime sıcaklığıdır (ntthal); sıralamaya, rozetlere ve "En iyi Özgül çift"e katılmaz, ancak bir primerin hairpin Tm'i önerilen Ta'nın 5 °C altındaki değere ulaşır ya da onu aşarsa (hairpin Tm ≥ Ta − 5 °C; `engine.HAIRPIN_UYARI_PAYI`, DNA, RNA, Dizi ve Kırılma noktası kartlarında aynı kural) kartta o primer için tek satırlık amber çizgili bir uyarı çıkar. 298 hedefte birinci çiftlerin 29'unda (%9,7) uyarı çıkıyor; sıra aynı kalıyor (kalıcı test `test_hairpin_uyarisi`). Kırılma noktasının kontrol primerinde aynı eşik **seçimde** de kullanılır (v0.8.64): primer3'ün ilk 5 adayından eşiği geçmeyen ilki alınır, bir uçta yoksa öbür uçtaki; hiçbiri uygun değilse en iyi aday kalır ve kartta "Kontrol primerin hairpin Tm'i …" satırı çıkar (`_bp_kontrol_primeri`, `_bp_kontrol_ara`; test `test_kontrol_hairpin`). Çiftlerin sırası değişmez.

Her iki modda da sonuç kartındaki düğmeyle **özgüllük kontrolü** çalıştırılabilir; DNA modunda çiftler ayrıca arka planda **otomatik taranıp rozetle işaretlenir** (hiçbir çift atılmaz, sıra değişmez; kapatılabilir). Tasarım sırasında **yaygın varyantlardan otomatik kaçınılır**.

---

## Veri dosyalarının indirilmesi

Paketin içeriği (ölçüldü: `electron/package.json` `extraResources` ve kurulu klasörün
`annotations\` dizini): **refGene tabloları (UCSC), MANE listesi (NCBI) ve dbSNP indeksleri
(UCSC `snp151Common` tablosundan üretilmiş) pakete dahildir** (~300 MB). **Genom FASTA
dosyaları (GRCh37 ve GRCh38, toplam ~6 GB) pakete dahil değildir.** Genomlar ve isteğe
bağlı olarak diğer üç veri de **⚙ Ayarlar › Veri dosyaları ve genom** altındaki "Veri dosyaları
(indirme)" panelinden kaynağından indirilir; böylece paket küçük kalır ve her kurulum
hangi dosyayı aldığını bilir. Her veri setinin kaynağı, adresi ve pakette olup olmadığı
aşağıdaki **Veri kaynakları** bölümünde.

| Öğe | Kaynak | İndirilen | Sonuç |
|---|---|---|---|
| Referans genom ×2 | Ensembl | ~840 MB (gz) | ~3 GB `.fa` + `.fai` |
| refGene ×2 | UCSC | 8 MB | doğrudan kullanılır |
| MANE | NCBI | 1 MB | doğrudan kullanılır |
| dbSNP indeksi ×2 | UCSC snp151Common | ~760 MB | 138 MB `.apidx` |

Tasarım kararları:

- **İndirme kaldığı yerden devam eder** (HTTP Range). 840 MB'lik bir dosyada kopan
  bağlantı yüzünden baştan başlamak kabul edilemezdi; kaynakların hepsinin
  `Accept-Ranges` desteklediği doğrulandı ve devam etme davranışı test edildi.
- **Aynı anda tek dosya iner.** Yavaş bağlantıda paralel indirme toplam süreyi
  kısaltmaz, sadece ilerlemeyi okunmaz hale getirir.
- İndirme öncesi **disk alanı kontrol edilir** (genom için ~3,4 GB gerekir).
- Ham arşivler işlendikten sonra silinir: 760 MB'lik dbSNP tablosu indekse
  çevrildikten sonra diskte kalmaz.
- İndirme bitince dosya **çalışan uygulamaya tanıtılır**; yeniden başlatmak gerekmez.
- MANE dosya adı sürüm taşıdığı için (`MANE.GRCh38.v1.5...`) adres çalışma anında
  klasör listelenerek çözülür; MANE yenilendiğinde de çalışır.

Dosyalar zaten elinizdeyse indirmeye gerek yok — aynı yerdeki "Genom dosyaları" bölümünden
doğrudan gösterebilirsiniz. Yavaş bağlantıda 6 GB'ı USB ile taşımak daha hızlı olabilir;
iki yol da açık bırakıldı.

---

## Dil (Türkçe / İngilizce)

Arayüzün tamamı iki dilde çalışır. Dil, açılıştaki bilgilendirme ekranından, üst bardaki
**TR / EN** düğmesinden ya da ⚙ Ayarlar'dan seçilir ve tercih makinede saklanır.

Çeviri yalnızca etiketlerle sınırlı değil: **hata mesajları ve uyarı notları da**
seçilen dilde üretilir. Bunlar Python tarafında oluştuğu için her istek `lang`
alanını taşır; `backend/lang.py` bunu istek bazında ayarlar (Flask threaded çalıştığı
için `ContextVar` kullanılır, istekler birbirinin dilini bozmaz).

Arayüz metinleri `renderer/i18n.js` içinde tek bir sözlükte toplanır (TR ve EN'de
659'er anahtar). HTML tarafında `data-i18n` / `data-i18n-ph` / `data-i18n-title`
nitelikleri kullanılır, JS tarafında `t("anahtar")`. Backend mesajlarında ise ayrı
katalog yerine iki dil yan yana yazılır:

```python
raise PrimerError(t(f"Dizi çok kısa ({n} bp)", f"Sequence too short ({n} bp)"))
```

Bunun sebebi mesajların çoğunun içinde hesaplanmış değer taşıması (koordinat, gen adı,
sayı); anahtar tabanlı bir katalog bu değerleri mesajdan koparıp okunmaz hale getirirdi.

CSV başlıkları da seçilen dile göre yazılır.

CSV'nin sütunları: DNA, RNA ve Kırılma noktası dosyalarının son iki sütunu `Derleme`
(GRCh37 / GRCh38; RNA'da transkriptin kurulduğu derleme, yani her zaman GRCh38) ve
`Kromozom` (`chr17` biçiminde)'dur; RNA dosya adında da derleme yazar. Dizi sekmesinin
CSV'sinde bu iki sütun yoktur. İki dizi kipinde mesafe bilinmiyorsa (serbest ürün boyu)
`Amplikon_bp` düz sayı kalır, `Amplikon_Not` sütunu "bitişik varsayımıyla; gerçek mesafe
bilinmiyor" der. Kırılma noktası delesyonunda `IkinciBant_Durum` sütunu normal alel bandının
sizin ürün sınırınıza göre durumunu (içinde / üstünde / çok üstünde) kartla aynı sözlerle yazar.

---

## Açılış bilgilendirme ekranı

Uygulama ilk açılışta **bilgilendirme ve sorumluluk bildirimini** gösterir. Ekran onay
istemez: üstte "Önemli uyarılar" kutusu (3 madde), altında bildirimin tam metni ve tek bir
**"Anladım, devam et" / "Got it, continue"** düğmesi vardır; zorunlu kutu, kaydırma şartı ya da
"Reddet" düğmesi yoktur. Düğmeye basılınca yalnızca **bildirim metni sürümü ve gösterilme
tarihi** yerelde saklanır (`%APPDATA%\AllPrime\consent.json`: `noticeVersion`, `noticeShownAt`);
Windows kullanıcı adı ve bilgisayar adı tutulmaz, hiçbir veri dışarı gönderilmez. Bildirim ilk
açılışta ve bildirim metni sürümü değişince bir kez gösterilir. Düğmeye basmadan pencere
kapatılırsa kayıt yazılmaz, ekran bir sonraki açılışta yine çıkar. Motor bildirim ekranından
bağımsız başlar.

Metin `renderer/terms.html` (TR) ve `terms_en.html` (EN) dosyalarında; aynı metin
⚙ Ayarlar › Hakkında altındaki "Lisans ve sorumluluk bildirimi" bölümünde de gösterilir (tek
kaynak). **Metni değiştirirseniz `main.js` içindeki `NOTICE_VERSION` değerini artırın** — yoksa
bildirimi daha önce görmüş kullanıcıya yeniden gösterilmez.

Bildirimin kapsadıkları: aracın tanı cihazı olmadığı, primerlerin laboratuvarca
doğrulanması gerektiği, garanti verilmediği, üçüncü taraf lisansları ve AllPrime'ın
lisansı (GNU GPL; yalnızca lisans ve metinlerinin yeri — sürüm 1.4'te sadeleşti, GPL v3 ve
dağıtım ayrıntısı aşağıdaki **Lisans** paragrafında ve KURULUM.txt'de) ve veri kaynakları.
6. madde bir kullanım kısıtlaması değil, sorumluluk bildirimidir — GPL ek kısıtlamaya
izin vermez (sürüm 1.1'de bu yüzden değiştirildi).

**Ana ekranın altındaki duyuru** (`app.notice`, her açılışta ve ⚙ Ayarlar açıkken de görünür)
dört öge taşır: telif satırı, garanti verilmediği, dağıtım koşulu ve lisans metninin yeri. Dağıtım
cümlesi duyurudan çıkarılmaz: GPL v2 md. 2(c) ve GPL v3'teki "Appropriate Legal Notices" tanımı
onu duyurunun parçası sayar, ve program bu duyuruyu gösterdiği için değiştirilmiş sürümler de eser
sahibinin adıyla birlikte göstermek zorundadır. Cümle izin veren değil koşulu vurgulayan ifadeyle
yazılır: "Kopyalanması ve dağıtılması yalnızca bu lisansın koşullarıyla mümkündür." (nöbetçi:
`test_telif_gorunur`).

---

## Ayarlar ekranı

Üst çubuktaki **⚙ Ayarlar** düğmesi açar; "← Tasarıma dön" ya da Esc kapatır. Açıkken tasarım
ekranı gizlenir, alttaki lisans bildirimi yerinde kalır (bildirimdeki bağlantı lisans metnini
açar). Tercihler bildirim kaydıyla aynı dosyada (`consent.json`) yalnızca o bilgisayarda saklanır;
bildirim metni sürümü değiştiğinde silinmez.

- **Tema: Koyu / Açık / Windows'a uy.** `main.js` `nativeTheme.themeSource`'u ayarlar; CSS'teki
  `prefers-color-scheme: light` bloğu aynı değişkenleri açık değerlerle yeniden tanımlar. Bilgilendirme
  ekranı aynı stil dosyasını kullandığı için onunla birlikte değişir; pencere zemini de temaya
  uyar (açılışta koyu parlama olmaz). Açık tema ayrı, koyu tonlu bir palettir: koyu temanın
  renkleri beyaz zeminde okunmuyordu (ölçüldü: turkuaz 1,86:1, amber 1,67:1, yeşil 1,74:1,
  kırmızı 2,77:1; gereken 4,5:1). Stil kurallarında sabit renk kalmadı; renkli tonlar
  `rgba(var(--warn-rgb), .12)` gibi değişkenden gelir.
- **Arayüz boyutu: %90 – %150.** Sayfa yakınlaştırması (`setZoomFactor`), bilgilendirme ekranı dahil.
  Stiller piksel ölçüsüyle yazıldığı için yalnızca yazı boyutunu büyütmek orantıyı bozardı.
  Ctrl + / Ctrl − / Ctrl 0 aynı adımları kullanır (`main.js` `kisayolBoyutu`, `before-input-event`;
  seçim kaydedilir, Ayarlar'daki düğme `zoom-changed` bildirimiyle güncellenir). Electron'un
  varsayılan menüsü kaldırıldı (`Menu.setApplicationMenu(null)`): gizliyken de kısayolları
  çalışıyordu; v0.8.29'da ölçüldü: Ctrl+R sayfayı yenileyip sonuçları siliyor, Ctrl + / −
  Ayarlar'a yansımadan ve kaydedilmeden yakınlaştırıyor (üç basışta %83), Ctrl+Shift+I
  geliştirici araçlarını, F11 tam ekranı açıyordu. Yazı alanlarındaki Ctrl+A / C / V / X / Z
  Chromium'un kendi düzenleme kısayollarıdır, menüye bağlı değildir; menüsüz Ctrl+A, Ctrl+Z ve
  Ctrl+V (yapıştırma olayı) denendi, Ctrl+C kullanıcının panosu değişmesin diye doğrudan
  denenmedi. Nöbetçi: `test_menu_kisayollari`.
  En küçük pencerede (900 px) %150'de içerik 600 CSS piksele iner; 900 px altında üst çubuk ve
  sekmeler sarar, form satırları daralır, tablolar kartın içinde kayar (dizi bölünmez).
- **Laboratuvar varsayılanları.** Açılıştaki referans genom (üst çubuktaki seçim yalnızca o
  oturum için), çoğaltılabilen en uzun ürün ve gelişmiş parametrelerdeki 23 değer. "Bu değerleri
  laboratuvar varsayılanı yap" yalnızca fabrika değerinden farklı olanları saklar; fabrika değeri
  ileride değişirse diğerleri onu kendiliğinden izler. "Fabrika değerlerine dön" kaydı siler.
  Bu sırada düzeltilen hata: genom her değiştiğinde (`loadHealth`) gelişmiş parametreler fabrika
  değerine dönüyordu (ölçüldü: GRCh37'ye geçince Mg²⁺ 2 → 1,5 mM, DMSO %5 → 0); kullanıcının
  girdiği koşul sessizce kayboluyordu. Artık alanlar yalnızca ilk yanıtta doldurulur.
- **Veri dosyaları ve genom** ile **Hakkında** (sürüm, primer3, yüklü genom / transkript /
  dbSNP, veri kaynakları, lisans metni). Eskiden ana ekranın altındaki paneldeydiler.

Doğrulama (gerçek arayüz, CDP): iki temada ekrandaki her yazı en az 4,5:1 (ana ekran, sonuç
kartı + amplikon + özgüllük, RNA, Değerlendir, kırılma noktası, Ayarlar, bilgilendirme ekranı);
1366×768, 1024×640 ve 900×650 pencerede beş boyutun hiçbirinde sayfa ya da kart yana taşmıyor;
tema, boyut, genom ve laboratuvar değerleri yeniden açılışta korunuyor. Nöbetçi:
`test_smoke.py: test_ayarlar_ekrani` (iki temanın kontrastını CSS'ten hesaplar).

**Üçüncü taraf lisans bildirimleri** `THIRD-PARTY-NOTICES.txt` dosyasındadır (Electron,
Python, OpenSSL ve motora giren tüm Python paketleri, tam metinleriyle; ayrıca pakette
bulunan expat, libmpdec, liblzma, klib/khash.h ve Microsoft C++ çalışma kitaplığı
(`msvcp140`) satırları). Elle yazılmaz:
paketler güncellenince `backend\.venv\Scripts\python.exe backend\lisans_bildirimi.py`
ile yeniden üretin; `kurulu-guncelle.ps1` dosyayı uygulama klasörüne kopyalar. expat ve
libmpdec metinleri Python'un kendi yerel belgesinden (`Doc\html\license.html`), kalan
paket metinleri paketlerin kendi lisans dosyalarından alınır; liblzma için yerelde metin
bulunmadığından yalnız ad ve lisans kimliği yazılır. primer3 tekerleğinin getirdiği beş
komut satırı aracı (`primer3_core`, `ntthal`, `ntdpal`, `oligotm`, `amplicon3_core`) motor
tarafından hiçbir yerde çağrılmadığı için `allprime-server.spec` bunları pakete almaz;
primer3'ün C kaynakları (GPL kaynak teklifi için) pakette kalır.

**Lisans:** AllPrime GNU GPL sürüm 2 ya da (isteğinize göre) daha sonraki bir sürümü ile
lisanslıdır (`GPL-2.0-or-later`; v0.8.17'ye kadar yalnızca sürüm 2 yazıyordu). Paketli motor
Apache-2.0 lisanslı `requests` ve OpenSSL'i içerir; FSF'ye göre Apache-2.0, GPL v2 ile
uyumsuz, GPL v3 ile uyumludur. Bu yüzden program kurum dışına GPL v3 koşullarıyla verilir;
iki lisans metni de uygulama klasöründedir (`LICENSE` = GPL v2, `LICENSE-GPL-3.0.txt` =
GPL v3).

---

## Ekson atlama: birden çok ekson seçimi

RNA · cDNA sekmesinde "Ekson atlama testi" seçilince **Atlanacak eksonlar** alanı çıkar.

- **Düğmeler:** geçerli bir NM_ kodu girilince transkriptin eksonları numara ve cDNA uzunluğuyla düğme olarak gelir (uç: `GET /transcript_exons?acc=NM_…&assembly=GRCh38`, genom okumadan). Tıklama seçimi açar/kapatır, Shift+tıklama aralık seçer. İlk ve son ekson seçilemez (bir yanında çapa ekson yok). Kod yoksa ya da uç hata verirse yalnız yazı kutusu çalışır.
- **Aralık kutusu:** `5`, `4-6` (bitişik), `4,6` (bitişik değil), `4-6,9` biçimleri (tire ya da en tire, virgül/boşluk). Kutu ile düğmeler birbirini günceller. Ayrıştırma tek yerde: `engine.parse_exon_list`; hatalı biçim 400.
- **Motor:** `POST /design_skipping` yeni `exons` alanını (sayı, liste ya da metin) kabul eder; eski `exon` (tek sayı) aynen çalışır. Yinelenenler atılır, sıralanır; her ekson 2..n−1 aralığında olmalıdır.
- **Hedef blok:** en küçük seçilen eksonun başından en büyüğünün sonuna. Bitişik değilse aradaki eksonlar da bloğa girer; primerler bloğun dışındaki komşu eksonlara (en küçük−1 ve en büyük+1) oturur. Ürün aralığı blok uzunluğu + 2×`skip_min_flank` … + 2×`skip_max_flank`; `pcr_max` aşılırsa blok için açık mesaj çıkar ("Ekson 45–47 toplam 474 bp: …").
- **Yanıt:** `skip_exons`, `skip_block`, `skip_len` (bitişikse blok farkı; bitişik değilse seçilenlerin toplamı), `skip_frame` (seçilenlerin kodlayan uzunluğu 3'e bölünüyor mu), `skip_utr`, `anchor_exons`. Eski alanlar (`input.exon`, `target_exon`, çift başına `product_size_normal/skipped`, `band_difference`) yerinde kalır.
- **Bitişik olmayan seçimde bantlar:** her tekli seçim ve hepsi birden için `skip_bands` (`exons`, `diff`, `frame`); her çiftte bant boyu normal − diff (`bands`). Arayüz bunları "Δ4: 412 bp · Δ6: 578 bp · Δ4+6: 299 bp" biçiminde gösterir; CSV'ye seçilen eksonlar ve bantlar sütunu eklenir, dosya adında seçim yazar (`exon4-6`, `exon4,6`).
- **Bant uyarısı eşiği (bir tasarım seçimidir, ölçülmüş bir ayrım sınırı değildir):** iki beklenen bant (normal dahil) arasındaki fark `max(20 bp, büyük bandın %5'i)`'nden küçükse çiftte `band_close` işaretlenir ve jelde ayırt etmenin zor olabileceği yazılır. Eşik gerçek jel çözünürlüğüne göre doğrulanmamıştır; gerekirse kapiler elektroforez ya da yüksek yüzdeli jel düşünülmelidir.
- **Okuma çerçevesi:** kodlayan baz sayısı CDS ile örtüşen kısımdan hesaplanır; seçimin bir kısmı UTR'deyse özet bunu belirtir.
- **Sınır üstü primer (isteğe bağlı):** `params.junction_overlap` açıkken (arayüzde Varyant tipiyle ortak "Primer ekson sınırının üzerine otursun" kutusu; varsayılan kapalı) primerlerden biri hedef bloğun **dışındaki** bir ekson sınırına oturur. Mekanizma Varyant tipindekiyle aynıdır (`SEQUENCE_OVERLAP_JUNCTION_LIST`, 3' ≥ 4 ve 5' ≥ 7 baz). Bloğa komşu iki sınır ve bloğun içindekiler listeye girmez: atlanmış transkriptte bulunmadıkları için primer oraya otursa iki banttan biri görünmezdi. Dışarıda sınır yoksa (çapa eksonları transkriptin ilk ve son eksonuysa) 400 döner; sınıra uyan çift yoksa liste boş gelir ve not seçeneği kapatmayı söyler (eleme dökümünde primer3'ün `no overlap of required point` kalemi "ekson sınırı şartı" diye yazılır; Varyant tipinde de). Yanıtta `junction_mode` (`overlap` / `flanking`) vardır. Kartta primerlerden biri sınırı tasarım kuralındaki kadar aşıyorsa (motor her primere `junction_solid` yazar: 3' tarafta ≥ `min_3p_overlap_junction`, 5' tarafta ≥ `min_5p_overlap_junction`) gDNA çipi boy yerine "çoğalmaz" yazar (`gdnaCipi`; Varyant kartı, CSV ve favori kaydı da aynı kurala uyar, Değerlendir RNA için `product.gdna_none`). Sınıra yalnız değen primerde boy yazılmaya devam eder (ölçüm: LAMA2'nin varsayılan atlama tasarımlarında sınıra değen 109 primerin 51'i kuralı karşılıyor); kutu işaretliyken seçim özetindeki "Primerler ekson a ve ekson b içine konur" satırı da sınır primerini anlatan satırla değişir (`ex.primerSinir`); dışarıda sınır yoksa özet bunu tasarımdan önce söyler (`ex.primerSinirYok`). Ölçüm (250 rastgele MANE Select iç eksonu, GRCh38, varsayılan ayarlar): ayar kapalıyken 1. çiftin gDNA ürünü eksonların %14'ünde 1.500 bp'nin, %2,5'inde 700 bp'nin altında; ayar açıkken, kapalıyken çift çıkan eksonların %87'sinde çift çıkar ve normal bant ortanca 367 bp'den 390 bp'ye uzar. Nöbetçiler: `test_atlama_sinir_ayari`, `test_atlama_sinir_arayuz`.

## Dizi sekmesi

Girdi temizliği kullanıcıyı uğraştırmaz: FASTA başlığı, satır sonları, boşluk, konum
numaraları ve küçük harf otomatik ayıklanır. `U` içeren dizi RNA kabul edilip `T`'ye
çevrilir; IUPAC belirsizlik kodları (`R`, `Y`, …) `N`'e çevrilir ve primer o konumlara
oturmaz. Yapılan her dönüşüm sonuçlarda not olarak bildirilir.

**Hedef konum** tam sayıdır (`1234`) ya da aralıktır (`1200-1260`, `1200..1260`,
`1200_1260`). Geçersiz girişte doğru sebep söylenir: ondalık sayı (`600.5`) "tam sayı
olmalı", ters aralık (`600-500`) "sonu başlangıcından küçük olamaz", dizi dışı konum "dizi
sınırları dışında" der (`engine._parse_target_arg`).

**İki dizi modunda** forward yalnızca birinci, reverse yalnızca ikinci dizinin içinden
seçilir; hiçbiri diğerine taşmaz (primer3 `SEQUENCE_PRIMER_PAIR_OK_REGION_LIST`).
Bu modda varyant/hedef kavramı yoktur — füzyon yalnızca tipik bir kullanım örneğidir,
"şu diziden bir forward, şu diziden bir reverse bul" demek için de aynı mod kullanılır.

Diziler varsayılan olarak bitişik kabul edilir; bilinen bir mesafe varsa girilir, araya
o kadar `N` konur ve primer oraya oturamaz. **Mesafe bilinmiyorsa** ilgili seçenek
işaretlenir: ürün boyu kısıtı kalkar ve primerler dizilerin her yerinden, yalnızca
kaliteye göre seçilir.

Bu ayrımın ölçülen etkisi (801 + 801 bp'lik iki dizide, varsayılan 180–650 bp aralığıyla):

| | Forward, 1. dizide | Reverse, 2. dizide |
|---|---|---|
| Kısıt açık | dizinin %56–88'i | dizinin %32–39'u |
| Kısıt kapalı | %0–65 | %99'a kadar |

Yani kısıt açıkken dizilerin büyük kısmına primer konamaz. Füzyon/kırılma noktasında
bu doğrudur (ürün gerçekten o boyda olacaktır); mesafe bilinmiyorsa iyi primerleri
gereksiz yere eler. Kısıt kapalıyken kısa amplikon tercihi de devre dışı bırakılır,
aksi hâlde sıralama primerleri yine birleşme noktasına doğru çekerdi.

Bu sekmede genomik koordinat olmadığı için dbSNP kaçınması uygulanmaz. Özgüllük
kontrolü **çalışır** ve anlamlıdır: füzyon çifti sağlıklı genomdan ürün vermemelidir.
Test edildi — BCR/ABL1 bölgelerinden tasarlanan çift normal genomda hiçbir ürün vermiyor.

---

## Kırılma noktası sekmesi

Delesyon ya da duplikasyonun sınırları (kromozom, silinen / kopyalanan bölgenin ilk ve
son bazı) girilir; `engine.design_breakpoint`. Tasarım, referansta OLMAYAN dizi üzerinde
yapılır: iki genomik parça birleştirilip primer3'e verilir, F birinci parçadan, R ikinci
parçadan ve ikisi de birleşim noktasına en az 100 bp uzak seçilir.

- **Delesyon (gap-PCR)** — parçalar: silinen bölgenin solu + sağı, yani delesyonlu alelin
  kendisi. Kırılma bandı doğrudan ölçülür; normal alel bandı = R5' − F5' + 1 (ayarlanan
  `pcr_max` sınırının içindeyse "çoğalır", 2 katına kadar "sınırın üstünde", ötesi "çok
  üstünde" diye işaretlenir; varsayılan 700 bp: ≤700 / 700–1.400 / >1.400 bp).
- **Tandem duplikasyon** — parçalar: bölgenin sonu + başı (iki kopyanın birleşimi).
  Primerler bölgenin içinde, dışa bakar; referansta ürün vermez, bağlantı ürünü dup
  büyüklüğünden bağımsızdır. Ters yönlü / insersiyonel kopyayı yakalamaz. ≤1,5 kb dup
  için dış primerler + boy farkı (`size_shift`).
- **Belirsizlik payı (`bp_margin`)** — primerler olası tüm kırılma noktalarının güvenli
  tarafına konur; bant boyu `[P, P + 4m]` aralığı olur.
- **Kontrol primeri (`control_primer`)** — önce çiftin F'i ile aranır: DEL'de silinen
  bölgenin başında normal alel primeri, büyük DUP'ta bölge sonunun dışında PCR kontrolü.
  Orada bulunamazsa öbür uçta R ile aranır: DEL'de silinen bölgenin sonu, DUP'ta bölge
  başının dışı (`_bp_kontrol_ara`, v0.8.62). Kontrol sözlüğündeki `pairs_with` hangi
  primerle bant verdiğini söyler; arayüzdeki adlar ve dimer uyarısı (tüpteki üçüncü primer)
  buna göre yazılır. Bandı, ana bandın TÜM olası boylarından en az 100 bp uzak seçilir.
  Adaylar arasından hairpin Tm'i çiftin Ta önerisinin 5 °C altını geçmeyen ilki seçilir
  (v0.8.64; tekrar dizisindeki aday ayrıca elenir); uygun aday yoksa en iyisi uyarıyla kalır.

Doğrulama: mutant / duplike alel genomdan elle kurulup primerlerin iki ucuna oturduğu ve
bant boylarının tuttuğu kontrol edilir (`test_smoke.py: test_kirilma_noktasi`).

---

## Favoriler (`electron/favoriler.js`, v0.8.63)

Kullanıcının seçtiği çiftlerin künyesi; yalnızca bu bilgisayarda, `userData\favoriler.json`
(`%APPDATA%\AllPrime`) dosyasında durur. Ayarlar dosyasından (`consent.json`) ayrıdır: biri
bozulursa öteki etkilenmez.

- **Saklama (`favoriler.js`, saf işlevler; yol dışarıdan):** `liste`, `ekle`, `sil`, `notYaz`.
  Kayıt arayüzden gelir ama burada doğrulanır (`temizle`): bilinmeyen alan atılır, metinler
  kırpılır (not 500 karakter), dizi yalnız harf (5–200). Primer sırası her zaman forward,
  reverse, control. Aynı çift (`anahtar`: tür + derleme + primer dizileri) ikinci kez eklenmez.
  Yazım geçici dosya + yeniden adlandırma. Bozuk dosyanın üstüne yazılmaz; yeni kayıt gelince
  önce `favoriler.bozuk-<tarih>.json` adıyla yedeklenir. 2000 kayıt sınırında yeni kayıt reddedilir.
- **Köprü:** `main.js` → `fav-list`, `fav-add`, `fav-remove`, `fav-note`; `preload.js` →
  `favList`, `favAdd`, `favRemove`, `favNote`.
- **Arayüz (`app.js`):** düğme bütün tasarım kartlarının ortak altlığında (`specFooter`) ve iki
  Değerlendir sonucunda. Kayıt kartta görünen adlarla kurulur (eksi iplikteki gende F/R genin
  yönünde; `genYonunde`). "Favorilerde" durumu `favAnahtar` ile bulunur (`favoriler.js`
  `anahtar` ile aynı ifade). Favoriler ekranı Ayarlar gibi açılır (`body.fav-modu`): arama,
  CSV (primer başına satır; `=`, `+`, `-`, `@` ile başlayan serbest metne `'` eklenir),
  "Değerlendir'de aç" (genomik kayıtta üst çubuk kaydın derlemesine geçer; kırılma noktası
  kayıtlarında yok), not düzenleme, silme.
- **Paket:** `favoriler.js` hem `kurulu-guncelle.ps1` listesinde hem `package.json`
  `build.files`'ta olmalı (yoksa `main.js` açılışta düşer).

Doğrulama: `test_smoke.py: test_favoriler` (node ile gerçek diskte; bozuk dosya, BOM, sınır,
anahtar eşliği) ve gerçek uygulamada `v0863_favoriler_ui.mjs`.

## Sağ tık menüsü (`electron/sagTik.js`, v1.1.3)

Electron'da varsayılan sağ tık menüsü yoktur: seçili metin fareyle kopyalanamıyor, kutulara
fareyle yapıştırılamıyordu (yalnız Ctrl+C / Ctrl+V çalışıyordu). `main.js` `createWindow`
içinde `context-menu` olayını dinler ve `sagTik.sablon(p, L)` boş değilse menüyü açar:

- yazı kutusunda Kes / Kopyala / Yapıştır / Tümünü seç (yapılamayan seçenek soluk görünür);
- sayfada seçili metin varsa Kopyala;
- ikisi de değilse menü açılmaz.

Öğeler Electron'un hazır rolleridir; pano içeriği bu kodda okunmaz. Etiketler kayıtlı dile
göre (`L`). Bilgilendirme ekranında da çalışır (aynı pencere).

- **Paket:** `sagTik.js` hem `kurulu-guncelle.ps1` listesinde hem `package.json`
  `build.files`'ta olmalı (yoksa `main.js` açılışta düşer).

Doğrulama: `test_smoke.py: test_sag_tik_menusu` (şablon node ile çağrılır).

## Motorun açılışını bekleme (`electron/motorBekle.js`, v1.1.4)

`main.js` motoru başlatır ve `/health` cevap verene kadar bekler. Bekleme `motorBekle.js`'tedir
(Electron'a bağlı değil; node ile sınanır):

- **Motor açılırken kapanırsa bekleme hemen biter.** Motor süreci bittiğinde (`close`) ya da hiç
  başlatılamadığında (`error`) `motorDurumu()` bunu bildirir; süre dolması beklenmez. Ölçüm
  (motoru açılışta ölen temiz kopya): hata kutusu v1.1.3'te 187–202. saniyede geliyordu.
- **Kapanan motor en çok 3 kez başlatılır** (denemeler arası 1,5 sn). Dosyalara o an
  erişilememesi gibi geçici bir durum sonraki denemede geçmiş olabilir. Zaman aşımı (motor
  yaşıyor ama yavaş; 180 sn) ve "başlatılamadı" (dosya yok, izin yok) yeniden denenmez.
- **Tanı metni** kaç kez denendiğini, dosyaların eksik / yarım olabileceğini (zip açılırken
  çalıştırma) ve klasör OneDrive altındaysa bunu söyler. Ölçüm: `_internal` altındaki
  `werkzeug-*.dist-info` yokken çıkış 1 + `PackageNotFoundError`; ikinci yarısı boş bir `.pyd`
  ile çıkış 3221225477 (0xC0000005). Gözlem (2026-11-22, başka bilgisayar): OneDrive ile
  eşitlenen Masaüstü'ne açılan kopyada motor bu iki hatayla açılmadı; klasörü `C:\`'ye taşımak
  düzeltmedi, zip'i doğrudan `C:\`'ye açmak düzeltti. Kılavuzlar bu yüzden eşitlenen klasöre
  açmamayı söyler.
- **Paket:** `motorBekle.js` hem `kurulu-guncelle.ps1` listesinde hem `package.json`
  `build.files`'ta olmalı (yoksa `main.js` açılışta düşer).

Doğrulama: `test_smoke.py: test_motor_acilirken_kapanirsa`.

---

## Primer genin neresinde (`transcripts.konum_bolgesi`)

DNA ve Kırılma noktası sekmelerinde her primere "ekzon 7 / intron 7 / ekzon 7 – intron 7
sınırı" etiketi eklenir (`_bolge_ekle` → primer sözlüğüne `gene_region`). Kontrol primeri
dahil.

- **Transkript seçimi:** ekzon numarası transkripte göre değişir, bu yüzden tek bir
  transkript seçilir ve hangisi olduğu hücre ipucunda + CSV'de yazar. Öncelik: MANE Select
  > MANE Plus Clinical > kodlayan ve en çok ekzonlu.
- **İplik:** numaralandırma transkript yönündedir. Eksi iplikli bir genin ekzonunun iki ucu
  **farklı** intronlara komşudur (TP53 ekzon 8: alt uç intron 8, üst uç intron 7); sınır
  etiketi bunu ayırır. Nöbetçi: `test_gen_bolgesi` iki iplikte de her ekzon/intron ortasını
  ve her ekzonun iki ucunu doğrular (TP53 11 ekzon, CFTR 27 ekzon).
- **Alan adı `gene_region`**, `region` değil: Dizi modunda primerlerde zaten `region` var ve
  "F / R" (hangi girdi dizisi) anlamına geliyor.
- **Etiket istemcide kurulur** (`bolgeEtiket`), sunucudan gelen `label` yalnızca yedek:
  TR/EN düğmesi sonuçları yeniden çiziyor ama yeni istek atmıyor, dolayısıyla sunucu metni
  eski dilde kalırdı.
- Koordinat hiçbir transkriptle kesişmiyorsa alan hiç eklenmez — uydurma bölge yazılmaz.

---

## RNA sekmesi: GRCh38 ve hizalama uyarısı (`engine.RNA_DERLEME`, `engine.kod_denetimi`)

**cDNA NM dizisinden değil, genom + UCSC refGene hizalamasından kurulur.** Hizalama küçük eksonlarda ya da genomun NM'den farklı olduğu yerlerde boşluk bırakabilir; o transkriptte c. ve ekson numaraları NM'ninkinden kayar. Ölçüm (MANE Select, kodlayan; `olcut_say.py`, 2026-11-11): kodlayan bölgesi tutarsız çıkan transkript GRCh38'de 64 / 18.761, GRCh37'de 185 / 18.751. Bu yüzden:

- **RNA sekmesindeki bütün yollar** (c. ile tasarım, ekson atlama, ekson düğmeleri, Değerlendir RNA, gen sembolüyle transkript listesi) transkripti **her zaman GRCh38** genomundan ve GRCh38 hizalamasından kurar; üstteki derleme seçimi fark etmez. Seçili derleme GRCh37 ise sonuçta (liste ve ekson düğmelerinde de) "RNA sekmesi transkripti her zaman GRCh38 genomundan kurar; gösterilen genomik konumlar GRCh38 konumlarıdır" notu çıkar. GRCh38 genomu tanıtılmamışsa dizi eskisi gibi yerel yoksa Ensembl'den gelir.
- **Hizalama denetimi** (tek yerde, transkript kurulurken; sonuç önbellekte): kodlayan bölgede (a) uzunluk 3'ün katı değil, (b) son kodon durdurma kodonu değil, (c) son kodondan önce durdurma kodonu var. ATG ile başlamama ölçüt değildir (MYC, VEGFA gibi gerçek ATG dışı başlangıçlar var). Selenoproteinler ve referansta gerçek durdurma taşıyan genler elenmeden işaretlenir; uyarı bunu söyler.
- **İşaretli transkriptte** sonucun en üstünde göze çarpan uyarı çıkar, **tasarım sürer**: neyin işaretlendiği, c. ve ekson numaralarının NM'ninkinden kayabileceği, gerçek bir durdurma kodonu da olabileceği, NM dizisiyle karşılaştırma ya da DNA sekmesinde genomik koordinatla tasarlama önerisi. Aynı bilgi transkript listesinde "Hizalama uyarısı" rozetiyle ve ekson düğmelerinin üstünde kısa biçimde görünür. Değerlendir RNA modunda uyarı bulgu olarak gelir.
- **Referans baz uyarısı** (`c.524A>G`, yazılan baz ≠ transkriptteki baz) kullanıcıyı suçlamaz: karşılaştırılan şeyin "GRCh38 genom dizisinden kurulan transkript" olduğunu söyler; işaretli transkriptte c. numarasının kaymış olabileceğini, sağlam transkriptte referans genomun NM dizisinden farklı olabileceğini (referansta varyantlı alel taşıyan yerler) belirtir.
- **DNA ve Kırılma noktası sekmeleri** seçili derlemeyi kullanmaya devam eder. Primerin ekzon etiketinin ipucuna, o transkript seçili derlemede işaretliyse (GRCh37'de ayrıca aynı NM'nin GRCh38 satırına göre ekson sayısı ya da kodlayan uzunluk farkı varsa) "ekzon numarası NM'ninkinden farklı olabilir" notu eklenir (`gene_region.kod_isareti`).
- **Kalıcı çözüm (uygulanmadı, öneri):** NCBI'ın kendi hizalamasını taşıyan bir tabloya (UCSC `ncbiRefSeq`) geçmek. Veri dosyası değişir; ölçmeden yapılmamalıdır.

---

## Birden çok yere hizalanan transkript: hangi lokus kullanılır (`transcripts._lokus_sec`)

UCSC refGene tablosu bir NM_ kodunu genomda birden çok yere hizalayabilir (SMN2, U2AF1, CRYAA, C4B, OPN1MW, AMY1A-C gibi kopyalı bölgeler; PAR genleri). RNA modu (c. ile tasarım, ekson atlama, Değerlendir RNA) bu satırlardan **birini** kullanır; RNA modu her zaman GRCh38'i kullandığından bu kural GRCh38 satırlarına işler:

- **GRCh38, MANE transkripti:** MANE özet dosyasındaki konumla (`GRCh38_chr`, `chr_start`, `chr_end`) örtüşen satır seçilir. Ölçüm (MANE Select + Plus Clinical, tabloda birden çok satırı olan 274 transkript): seçilen satırın MANE konumuyla örtüşmediği transkript 0. MANE konumu yama ya da alternatif iskelede olan 51 transkriptte ve MANE listesinde olmayan transkriptlerde bu kural uygulanamaz; "en uzun genomik yayılım" kuralı kalır ve sonuç notlarında (RNA tasarımı, ekson atlama ve Değerlendir RNA bulguları) kullanılan lokus ve öteki lokuslar yazılır. Doğru lokus bu değilse koordinatı ve diziyi doğrulayın.
- **GRCh37 satırları** (RNA sekmesi dışında `transcripts.get_transcript` ile okunduğunda): MANE konumu yoktur; en uzun genomik yayılımlı satır kullanılır ve aynı not üretilir. Bu seçimin doğruluğu GRCh37 için ölçülemedi.
- Gen sembolüne göre aranan transkript listesi (`/transcripts`) de aynı satırı gösterir.

---

## Primer adları (F / R) genin yönünde

Laboratuvar F/R'yi genin okuma yönüne göre adlandırır; Değerlendir de v0.8.8'den beri böyle
bekler (yayınlanmış 22 TP53 çiftinin 21'i bu kurala uyuyordu). DNA ve Kırılma noktası sekmeleri
ise çiftleri genomun + ipliğine göre adlandırıyordu: eksi iplikteki bir gende "Forward" genin
tersine okuyordu. Ölçülen sonuçları (v0.8.27):

- TP53 c.215 (P72R) = chr17:7676154; burada + iplikte **G**, c. dizisinde **C**. "Forward"
  primerle yapılan Sanger okuması c. dizisinin ters tümleyeniydi.
- DNA sekmesinin TP53 çifti kartın "Değerlendir" düğmesiyle gönderilince Değerlendir "F ve R
  rolleri yer değişmiş" diyordu.

v0.8.28'den beri sunucu her çifte ürünün örtüştüğü genin adını ve ipliğini ekler
(`server._gen_yonu_ekle`). Kural Değerlendir'inkiyle aynı fonksiyondur (`evaluate._urun_geni`):
MANE öncelikli; zıt yönlü genler örtüşüyorsa ya da gen yoksa genom yönü kalır. Eksi iplikte
arayüz (`renderer/yon.js`, saf fonksiyonlar) F ile R'yi yer değiştirir, ürün dizisini ters
tümleyen gösterir (F'den başlar, c. ile aynı yönde) ve sonuçların üstüne not yazar; özette
genin ipliği görünür. Pozisyonlar genomik kalır, motorun çıktısı değişmez. Kart, ürün dizisi
(FASTA başlığı yönü söyler), CSV, Değerlendir düğmesi ve özgüllük taraması aynı adları
kullanır; kırılma noktasındaki kontrol primeri metinleri ortak primerin gösterilen adını alır.
Özgüllük taramasının sonucu çiftin yönüne bağlı değil (ölçüldü: TP53 çiftinde iki yönde aynı).
"Sonuç yok" açıklaması bu iki sekmede F/R yerine koordinat tarafını yazar.

RNA/cDNA sekmesi zaten transkript yönündedir; Dizi sekmesi yapıştırılan dizinin yönünde kalır.

Değerlendir'in ürün dizisi (v0.8.30): motor ürünü genomun + ipliğinde (cDNA'da transkript
yönünde) verir, her ürün sol ve sağ uçtaki primeri bildirir (`forward_primer` /
`reverse_primer`). R+F üründe (eksi iplikli genin kartından gelen çift; cDNA'da roller yer
değişmiş) dizi ters tümleyen gösterilir ve F'den başlar (`yon.js` `degerlendirmeUrunu`); lejant
uçlardaki primerin adını alır, F+F / R+R yan ürünleri dahil; çevrilen üründe lejantta ve FASTA
başlığında not vardır. v0.8.29'da ölçüldü: lejant her zaman "Forward / Reverse" diyordu, TP53
kartının çiftinde kullanıcının R'si (GGTAGGTTTT…) "Forward primer" diye işaretliydi, aynı
ekrandaki tablo "R 0 / F 0" diyordu. Nöbetçi: `test_degerlendir_urun_yonu`.

Nöbetçiler: `test_gen_yonu_gorunum`, `test_gen_yonu_adlari`; yeni arayüz dosyası kurulu
klasöre de gitsin diye `test_kurulu_arayuz_dosyalari` (`kurulu-guncelle.ps1` sabit liste kullanır).

---

## Ürün dizisinde girilen konum (`variant_span`)

Kullanıcı isteği (v0.8.33): koordinat verilince ürün dizisinde o nükleotit ayrı renkle görünsün.
Motor konumu amplikon içi ofset olarak verir (`amplicon.variant_span`, 0-tabanlı, kapsayıcı);
arayüz `amp-v` sınıfıyla dolgulu işaretler, lejantta konumun adını ve ürünün kaçıncı bazı olduğunu
yazar. İşaret en son uygulanır, primerin üstüne düşse de görünür. Eksi iplikli gende ürün
`amplikonTers` ile çevrilirken ofset de aynalanır; R+F Değerlendir ürününde de aynı.

| Sekme | İşaretlenen |
|---|---|
| DNA | Girilen koordinat ya da aralık |
| RNA · cDNA | c. konumu (ekson atlama testinde yok) |
| Dizi | Köşeli parantez ya da hedef konum (hedefsiz ve iki dizi modunda yok) |
| Kırılma noktası | Birleşim çizgisinin iki yanındaki baz (delesyonda silinen bazlar üründe yoktur); dış primerli küçük duplikasyonda girilen bölge |
| Değerlendir | İsteğe bağlı `target` (`chr19:11537002`, RNA modunda `c.215`); kart düğmesi doldurur |

Nöbetçi: `test_urun_hedef_isareti` (TP53 c.215: + iplikte G, cDNA'da C).

---

## Aday havuzu (`dimer_pool`)

primer3'ten `dimer_pool` kadar aday çift istenir, sonra self/dimer skoruna göre **yeniden
sıralanıp** `num_return`'e kırpılır (primer3 kendi cezasında self/dimer'e ağırlık vermiyor).

**300 → 1000 (2026-10-27).** Kullanıcı TP53'te aracın 532 bp'lik bir çift önerdiğini, ürün
sınırını düşürünce çıkan 360 bp'lik çiftin hem daha kısa hem self-komplementaritesinin daha
düşük olduğunu bildirdi. Ölçüldü: 300'lük havuz **çeşitlilikten yoksundu** — 300 çift
yalnızca 42 farklı forward ve 29 farklı reverse içeriyordu, gerisi 1-2 baz kaymış
kopyalardı; daha iyi çift havuza **hiç girmiyordu**. Sıralama kusurlu değildi, havuz
kusurluydu.

Elenen açıklamalar: dbSNP kaçınması (kapatınca sonuç aynı) ve sıralama formülü (havuz
büyüyünce doğru çifti 1. sıraya koyuyor).

12 gende ölçüm: ortalama dimer skoru **4,48 → 4,17**, ürün **442 → 423 bp**, maliyet
**+0,1 sn**. 8 gende sonuç aynı, 3'ünde belirgin iyileşme (MYH7 4,5 → 2,0; RYR1 4,1 → 2,0),
1'inde (TP53) dimer 3,4 → 4,4 ama ürün 506 → 230 bp — aracın kendi toplam puanına göre daha
iyi. 2000 ile 1000 aynı sonucu veriyor, iki kat yavaş.

Nöbetçi: `test_aday_havuzu` — TP53'te 360 bp'lik çift 1. sırada olmalı ve `dimer_pool=300`
ile olmamalı.

---

## DNA sekmesinde varyant aralığı

Konum alanı tek koordinat (`7676154`) ya da varyantın tamamını kapsayan aralık
(`7676154-7676208`, `chr2:50,000,001-50,000,300`) kabul eder — `varyant_araligi`.
Aralık verilince `SEQUENCE_TARGET` varyantın **tamamı + iki yanda
`min_dist_from_variant`** olur, yani yasak bölge doğal olarak asimetriktir.

**Neden:** tek koordinat verilen çok bazlı varyantta primer varyantın içine düşebiliyordu;
o primer varyantlı alele bağlanmaz ve **heterozigot örnek homozigot görünür**. Ölçüldü
(2026-10-25): 120 bp'lik delesyonun başlangıcı verildiğinde 20 primerin 5'i içeride; 300
bp'likte 10/10 içeride.

Simetrik `min_dist_from_variant`'ı büyütmek bunu çözmüyor: 300 bp'lik varyant için 400 bp
pay gerekiyor, o da ürünü `pcr_max`'ın üstüne çıkarıp **hiç çift bulunamamasına** yol
açıyor. Aralık girişi iki yana ayrı davrandığı için 300 bp'lik varyantta ürün 484–617 bp'de
kalıyor.

Varyant tek amplikona sığmıyorsa (hedef + primerler > geçerli üst sınır) sessizce boş sonuç
yerine Kırılma noktası sekmesini öneren açık bir hata verilir.

**Nöbetçi (regex):** kromozom öneki yalnızca iki nokta ile birlikte sayılır. İlk sürümde
`:` isteğe bağlıydı ve `[\dXYMT]*` başlangıç koordinatını yutuyordu —
`50000001-50000120` → kromozom `50000000`, başlangıç `1`.

---

## Çoğaltılabilen en uzun ürün (`pcr_max`)

Laboratuvarın PCR ile güvenle çoğaltabildiği en uzun ürün. Varsayılan **700 bp**; gelişmiş
parametrelerden değiştirilir ve **dil seçimi gibi bu bilgisayarda saklanır**
(`main.js: set-pcr-max`).

Bir "tercih" değil, **ölçü birimi**: ürün boyu üst sınırı her modda buna göre kısılır
(`_urun_araligi`) ve kırılma noktası sekmesinde hangi bandın çıkacağı buna göre
değerlendirilir. Eskiden bu eşikler sabit 3 / 6 kb idi; en fazla ~700 bp çoğaltan bir
laboratuvarda 900 bp'lik normal alel bandına "çoğalır" deniyordu (2026-10-25).

**Dil kuralı:** sınır kullanıcının kendi protokolüdür, PCR hakkında mutlak bir hüküm
değil — araç başka laboratuvarlarda da çalışıyor. Bu yüzden hiçbir metin "şu boyun üstü
çoğalmaz" demez; "ayarladığınız sınırın üstünde" der ve bu boyu çoğaltan bir protokolde
bandın görülebileceğini ekler. Bant tablosunda sınır üstü bant **silinmez**, boyuyla
birlikte işaretlenir (`bp.wt.*` etiketleri: sınırınızın içinde / üstünde / çok üstünde).
Nöbetçi: `test_smoke.py`, "'ürün beklenmez' gibi mutlak ifade kullanilmaz".

Etkileri:

- Küçük DUP'ta dış primerlerle bant sınıra sığmıyorsa `size_shift` yerine
  `tandem_junction` seçilir ve nedeni yazılır.
- Belirsizlik payı yüzünden bant sınırı aşacaksa **bu sınırla en fazla kaç bp'lik payla
  çalışılabileceği** hesaplanıp söylenir.
- Sınıra sığan pencerede hiç primer çıkmazsa tasarım sınırsız tekrarlanır (boş sonuç
  yerine sonuç + uyarı; `_bp_baglanti_sinirli`).
- Ekson atlama testinde hedef ekson normal transkript ürününü sınırın üstüne çıkarıyorsa
  bu açıkça söylenir (BRCA1 ekson 10 ≈ 3,4 kb).

**Değerlendir de bu sınıra bakar (v0.8.32).** Arayüz kayıtlı değeri `/evaluate` ve `/evaluate_cdna`
isteğine ekler (`KOSUL_IDS`); hedef ürün sınırın üstündeyse karar "uyarı" olur ve metin tasarım
sekmeleriyle aynı dili kullanır: "sınırınızın üstünde", daha uzun ürün çoğaltan bir protokolde bant
görülebilir. v0.8.31'de ölçüldü: yayınlanmış 647 çiftin 46'sı 700 bp üstündeydi, 8'ine "Sorun
görünmüyor" deniyordu (Nie 2018, ASXL1 ekzon 12, 772 bp). Yan ürün tarama penceresi değişmedi
(`max_product`, 5 kb). Nöbetçi: `test_degerlendir_pcr_siniri`.

---

## Ürün GC aralığı (`product_min_gc` / `product_max_gc`)

Amplikonun GC yüzdesi için **isteğe bağlı** alt/üst sınır. Varsayılan 0-100, yani kısıt yok
ve GC yalnızca bilgi olarak gösterilir (DMSO/betain notu ayrıca çalışır). Değer verilirse
aralık dışındaki adaylar `_rank_order` içinde, listeyi `num_return`'e kırpmadan **önce**
elenir; kaç adayın elendiği not olarak yazılır. primer3'te ürün GC kısıtı yoktur, süzgeç
bizde.

Hiç çift kalmazsa sebebi GC olarak söylenir. **Nöbetçi:** bu durumda primer3'ün kendi
dökümüne bakmak yanlış sebep gösteriyordu ("adayların çoğu ürün boyu kısıtına takıldı",
oysa primer3 1269 uygun çift bulmuştu). Artık primer3 çift ürettiyse döküme hiç
bakılmıyor, sonuca `self_filtered` konuyor ve arayüz ham dökümü gizliyor.

---

## Psödogen / yakın-özdeş kopya uyarısı (`paralog.py`)

Bazı genlerin genomda neredeyse birebir ikizi vardır (PMS2/PMS2CL, CYP21A2/CYP21A1P,
NCF1/NCF1B, HBA1/HBA2, SMN1/SMN2, STRC/STRCP1). Böyle bir gende tasarlanan primer kopyadan
da ürün verebilir; iki lokus birlikte çoğalırsa hastanın varyantı seyrelir ya da kopyanın
dizisi hastaya yazılır. Özgüllük taraması tasarımı **süzmez** (kullanıcı şartı: primer3'ün
en iyi adayı kopyaya takıldı diye atılmaz); DNA modunda otomatik rozetler kopyadan ürün veren
çifti işaretler, diğer modlarda tarama yalnızca düğmeyle çalışır. Bu uyarı, hangi genlerde
rozetlere ya da düğmeye bakmak gerektiğini önceden haber verir.

Uyarı DNA, RNA/cDNA, ekson atlama ve kırılma noktası modlarında çıkar. Gen adı girilmese de
koordinattan bulunur (`konum_genleri`; yalnızca tablodaki genlerin aralıkları kurulur, o
yüzden ucuz).

**Tablo nasıl üretildi** (`scratchpad/paralog_uret3.py`, yerel GRCh37 FASTA):

1. Aday çiftler gen sembolü ailesinden (sondaki `P1` / `CL` / harf / rakam atılarak aynı
   köke inen semboller).
2. Her aday **gerçek diziyle** ölçüldü: genden 500 bp'lik pencereler alınır, pencerenin
   ortasındaki 20-mer (primer boyu) paralog bölgesinde aranır, bulunduğu yerden 500 bp
   boyunca kimlik hesaplanır; ≥%90 ise pencere "homolog" sayılır.
3. **500 bp şartı bilerek:** ilk denemede tek tek 20-mer sayılmıştı ve o ölçüm BRCA1 ile
   BRCA2'ye bile %7,8 veriyordu — tamamı intronlardaki Alu tekrarlarından geliyordu. Alu
   ~300 bp olduğu için 500 bp'yi %90 kimlikle taşıyamaz.
4. `dna` = gen gövdesi (intronlar dahil) → genomik tasarım riski; `ekzon` = eklenmiş cDNA
   ↔ eklenmiş cDNA → RNA riski. İşlenmiş (intronsuz) psödogende `dna` düşük, `ekzon`
   yüksek çıkar ve uyarı bunu ayırt eder.

Üretimde çıkan üç tuzak: refGene SMN1'i hem SMN1 hem SMN2 lokusuna hizalıyor (min/max 903
kb'lik sahte bir "gen" üretiyordu → lokuslar kümeleniyor); `STRC` gibi semboller kök
hesabında iki harfe inip 71 üyeli aileye düşüyordu (kök en az 3 karakter); eklenmiş cDNA'yı
genomik diziyle karşılaştırmak intronunu koruyan kopyalarda ekzon oranını 0 gösteriyordu.

### En iyi Özgül çift ve kopyadan ayrışan çiftler (`kopya.py`, `cok_tarama.py`, v0.8.36)

Liste primer3'ün ilk 1.000 adayından seçilir ve özgüllük sıralamaya girmez (rozet yalnızca işarettir).
Ölçüldü (2026-11-08, 300 rastgele hedef, `AllPrime-tarama/rapor-en-iyi-cift.md`): 1. çift 57/298 hedefte
"Özgül" değildi ve bunların 52'sinde Özgül çift vardı (19'unda ilk 10'da hiç yoktu); 13/298 hedefte havuz
kesimi aynı cezalı, ortanca 108 bp daha kısa ürünlü çifti dışarıda bırakıyordu (primer3 cezası pratikte
yalnızca primer boyundan geldiği için kesim eşit cezalı binlerce çiftin içinden geçer). "Önce Özgül, sonra
bugünkü skor" tanımıyla 1. çift 63/298 hedefte en iyi değildi; bütün adaylar taranıp seçilince 0/298.
Kullanıcı kararı (2026-11-09): "en iyi" bu tanımdır; liste ve sırası değişmez, en iyi Özgül çift ayrıca
gösterilir; kurallara uyan bütün adaylar taranır, deneme sınırı ve çeşitlilik sınırı yoktur (primer
başına en çok 5 çift sınırı en iyi Özgül çifti %76 hedefte dışarıda bırakıyordu).

Rozetler bitince arayüz tasarımın kendi isteğini `POST /kopya_ciftleri` ucuna gönderir (yalnızca DNA modu;
otomatik kontrol kapalıysa yalnızca psödogenli genlerde düğmeyle; kontrol sonradan açılırsa son tasarım için
de başlar, arama sürerken kapatılırsa psödogensiz gende bölüm gizlenir — `kopyaBeklet`,
`test_oto_kontrol_sonradan`):

1. Tasarım yeniden çalışır (`design_primers(havuz=...)`); aynı girdiyle primer3'ten kurallara uyan bütün
   çiftler istenir (`PRIMER_NUM_RETURN` 500.000; ölçülen en büyük liste 54.365 çift) ve `_rank_order` ile
   sıralanır. 1.000'lik havuz bu listenin primer3 sırasındaki öneğidir (338/338 hedef).
2. Listenin bütün farklı primerleri tek geçişte taranır (`cok_tarama.Tarama`): tohumlar (3' son 6 baz)
   6-mer kodlarıyla bulunur, her primerin isabetleri `specificity`'nin iş parçası / alt aralık / desen
   sırası ve sınırlarıyla saklanır. Bir çiftin isabetleri bu kayıtlardan kurulur ve `check_pair`'e
   `isabet=` ile verilir; geri kalan her adım (ürün, PAR ikizi, hedef ürün, risk katmanları, tekrar ve
   ürün sınırları) aynı koddur. Hızlı yol (`Tarama.risk`) yan ürün sayılarını isabet dizilerinden vektörle
   hesaplar; yalnızca karar gerektiğinde kendi ürünleri (F+F, R+R) orta/yüksek riskliyse erken durur.
3. Bugünkü sırayla gidilir: ilk Özgül çift en iyisidir (psödogenli gende ilk 8'i).
4. Sonuç (`durum`): `bir` 1. çift en iyisi (kutu açılmaz); `ilk10` en iyisi listede k. sırada; `disari`
   listede yok; `k2` 1. çift Özgül ama havuz dışında daha iyi skorlu Özgül çift var; `yok` hiç Özgül çift
   yok, en az riskli 3 çift (önce en az yüksek, sonra en az orta riskli ürün; kendi ürünleri alt sınır).
   Her çiftte 1. çifte göre fark yazılır (primer boyu sapması, dimer, ürün boyu).
5. Psödogenli gende listelenen çiftlerin kopyadan farkı hesaplanır (`kopya_farki`, v0.8.35). Kopya
   bölgeleri ilk 10 çiftin yan ürünlerinden çıkar (6 kb'lik gruplar, en sık 40'ı, iki yanına 3 kb).
   İki primer bu bölgelerde tohum kuralı olmadan aranır (primer başına en çok 4 uyumsuz; primer 5
   parçaya bölünür, biri tam eşleşmek zorundadır), 3 kb içinde bakışan, toplam en çok 5 uyumsuzlu en
   tehlikeli ürün seçilir: en az uyumsuzlu, eşitse farkı 3' uca en uzak olan. Arayüz "Kopyadan fark"
   sütununda en yakın farkı yazar ("R: 3' son baz"; birden çok farkta sayısını da); böyle ürün yoksa
   "Çok farklı". Primer adı kartlardaki gibi genin yönündedir. Sıra değişmez.

Yeni tasarım ya da otomatik kontrolün kapatılması yarım aramayı durdurur (`POST /kopya_durdur`).

**Doğruluk ve süre** (2026-11-08/09): tek geçiş, gerçek `check_pair` ile 204/204 çiftte birebir (TP53,
SORD, CYP21A2, PMS2, SHOX/PAR1, SMN1, BRCA1, NKX2-3 ve (CA)n, Alu, poli-A çiftleri); ana ölçümde 16.659
çift daha farksız. Nöbetçiler: `test_cok_tarama`, `test_kopya_ciftleri`. Tek geçiş (12 işçi): havuz
(130–190 primer) 6,5–8,5 sn, tam liste (ortanca 503 primer) ortanca 12,8 sn; 4 işçiyle 11–14 / 12–25 sn.
Arama başına toplam 10–55 sn (TP53, UBE2L6, DENND6A, GABARAP, SORD, SMN1, CYP21A2; 12 işçi); yoğun tekrar
bölgesinde risk sayımı dakikalar sürebilir (GOLGA6L1 384 sn). İşçi belleği (çalışma kümesi) 80–122 MB; ayrılan (commit) bellek için bkz. v0.8.44. Tek geçiş numpy
gerektirir (`requirements.txt`); numpy yalnızca arama başlayınca yüklenir.

**"En iyi çift" ifadesi:** İlk 10, primer3'ün kurallarına uyan adaylardan primer3 cezasına göre ilk 1.000'i
alınıp self/dimer ve kısa ürün tercihine göre sıralanmış listedir; özgüllük sıralamaya girmez. Kurallara
uyan bütün adaylar ayrıca genomda taranır; en iyi Özgül çift (önce 3 kb içinde yüksek ya da orta riskli
yan ürün olmaması, sonra aynı sıralama) 1. çift değilse ayrıca gösterilir.

Aşağıdaki iki ölçüm v0.8.34–0.8.35 aramasına (ilk 10'un yan ürünlerinden hızlı eleme, en çok 12 deneme)
aittir; teknik tarihçe olarak duruyor.

**Ölçüm** (2026-11-07, `kopya.ara`, GRCh38; beklenmeyen hata 0):

| Küme | Hedef | Listede özgül çift var | Yalnızca havuzda | Bulunamadı |
|---|---:|---:|---:|---:|
| 10 gen (PMS2, CYP21A2, SMN1, NCF1, HBA1, GBA, PTEN, PKD1, STRC, CHEK2) | 39 | 15 | 12 | 12 |
| primer3 kıyasında yeşil rozetsiz kalan hedefler | 24 | 0 | 19 | 5 |
| Toplam | 63 | 15 | 31 | 17 |

Listede özgül çift olmayan 48 hedefin 31'inde (%65) havuzda tam taramayla doğrulanan çift var; ilk
çiftin havuz sırası 11 ile 519 arasında. "Bulunamadı" kesin değildir: 3 hedefte (PMS2, STRC, GOLGA6L1)
elemeyi geçen çift denenen 12'den fazlaydı, arayüz bu durumda ayrı metin gösterir. Bir hedefte
(PKD1 chr16:2135582) primer3 hiç aday üretmedi. SMN1'in dört hedefinin hiçbirinde çift yok. Süre:
arama gereken 47 hedefte ortanca 63 sn, en çok 142 sn (rozetler bunun dışında). Aynı anda dört iş
parçacığıyla 48 tasarımın hiçbiri tek başına çalışan tasarımdan farklı çıkmadı. Bu sonuçlar
hesaplamadır; laboratuvar doğrulaması yoktur.

**Kopyadan nasıl ayrışıyorlar?** (2026-11-08, `kopya_fark.py`) Havuzda çift bulunan 31 hedefin
psödogen uyarısı çıkan 15'inde 107 çift, iki primeri kopya bölgelerinde tohum kuralı olmadan
(her konum, en çok 4 uyumsuz) aranarak incelendi:

| Ayrışma | Çift |
|---|---:|
| Tohum kuralı olmasa da kopyada en çok 5 uyumsuzlu ürün yok | 17 |
| Yalnızca 3' tohum kuralıyla; fark son 2 bazda | 40 |
| Yalnızca 3' tohum kuralıyla; en yakın fark 3' uçtan 3.–6. bazda | 50 |

Yani çiftlerin %84'ü kopyadan tek primerin 3' bölgesindeki farkla ayrışıyor. Hedef başına en iyi
çift: 3 hedefte birden çok farkla, 10 hedefte son 2 bazdaki farkla, 2 hedefte (NCF1) yalnızca
3.–6. bazdaki farkla ayrışıyor. CYP21A2 chr6:32040495'te bulunan 8 çiftin hepsinde Forward kopyaya
da tam oturur; ayrışmayı Reverse'ün son ya da sondan ikinci bazı sağlar (Değerlendir bu yüzden
"Forward 2 yere tam oturuyor" uyarısı verir, ürün ise tektir). Tek bir uyumsuzluk kopyanın
çoğalmasını her zaman durdurmaz; arayüz ve KURULUM bu yüzden Sanger kontrolünü önerir.
Motorun kendi hesabı (`kopya_farki`, `kopya_fark2.py`) aynı 15 hedefteki 107 çiftin hepsini bu
bağımsız ölçümle aynı sınıfa koydu; 22 çiftte en tehlikeli kopya ürününde birden çok fark var.
Fark hesabıyla birlikte arama süresi ortanca 53 sn, en çok 93 sn.

---

## Yaygın varyant (dbSNP) kaçınması

Primerin bağlandığı yerde yaygın bir varyant varsa o allel çoğalmaz: **heterozigot hasta homozigot görünür.** Sonuç sessizce yanlış çıkar ve üstelik temiz bir sonuç gibi durur — özgüllükten bile sinsi bir hata tipidir.

Ölçüm: rastgele bir 20 bazlık primerin MAF ≥ %1 bir varyanta denk gelme olasılığı **~%8**, yani çift başına ~%16. Nadir bir kenar durum değil.

Bu yüzden davranış "uyarmak" değil **kaçınmaktır**: şablondaki yaygın varyant konumları primer3'e `SEQUENCE_EXCLUDED_REGION` olarak verilir, primer oralara hiç oturmaz. Bölge yoğunsa ve hiç çift kalmazsa kısıt otomatik gevşetilir — ama sessizce değil, sonuçlarda açık bir uyarıyla. Ekson atlama modunda yalnızca SNP kısıtı geri alınır; hedef ekson kısıtı testin kendisi için zorunlu olduğundan korunur.

Kaçınılamayan varyantlar her primer için rs numarası, MAF ve **3' uca uzaklığıyla** raporlanır. Bu uzaklık kritiktir: 3' uçtaki bir uyumsuzluk uzamayı tamamen durdurur, 5' uçtaki çoğu zaman tolere edilir.

Kaçınma bir onay kutusuyla kapatılabilir (örn. allele-spesifik primer tasarlarken kasıtlı olarak varyantın üzerine oturmak istenir). Kapatıldığında varyantlar yine **raporlanır**, sadece yasaklanmaz.

Veri: UCSC `snp151Common` (dbSNP b151'in MAF ≥ %1 alt kümesi), genom başına ~14,4 milyon varyant. Ham tablo 750 MB; uygulamayla dağıtılan, ondan üretilen ~138 MB'lık sıkıştırılmış indekstir. Sorgu mmap üzerinde ikili arama ile **0,005 ms** sürer — bu yüzden otomatik çalışır, düğme gerektirmez.

İndeksi yeniden üretmek (dbSNP güncellendiğinde):

```powershell
.venv\Scripts\python backend\dbsnp.py snp151Common.txt.gz annotations\dbsnp_common_hg19.apidx --assembly GRCh37
```

---

## Özgüllük kontrolü

Bir primer **çiftinin** genomda istenmeyen ürün verip vermediğini bulur. Tarama tasarımı bekletmez: sonuçlar hemen gösterilir.

**DNA modunda otomatik rozetler** (v0.8.9). Sonuçlar göründükten sonra çiftler arka planda sırayla taranır (~3 sn/çift) ve her kartın üstüne bir rozet eklenir: *Özgül*, *Orta riskli yan ürün* ya da *Yüksek riskli yan ürün* (ipucunda en riskli ürünün yeri, boyu ve uyumsuzluk sayısı). Rozetler yalnızca işarettir: hiçbir çift atılmaz, sıralama değişmez, çünkü özgül olmayan bir çift primer3'ün en iyi adayı olabilir ve seçim kullanıcınındır. "Özgüllüğü otomatik kontrol et" kutusuyla kapatılır (tercih hatırlanır); yerel genom yoksa çalışmaz. Tarama durdurulunca (kutu kapatılır ya da yeni bir tasarım başlar) taranmamış kartlarda "sırada" rozeti kalmaz; eskiden kalıyordu ve başka bir modda tasarım yapılınca yeni kartların hepsine de geçiyordu (`otoDurdur`, nöbetçi `test_oto_rozet_durumu`). Diğer modlarda (RNA/cDNA, ekson atlama, dizi, kırılma noktası) genomda "hedef ürün" tek başına tanımlı olmadığından rozet yanıltır; orada tarama yalnızca düğmeyle yapılır. *Özgül* rozetli bir çiftin kartında, 3' kuralının (son 6 baz tam) dışında kalan ama yalnızca 1–2 baz farkla ürün verebilecek bir kopya varsa (Değerlendir'deki "kopyadan yalnızca tek baz farkı" notuyla aynı hesap, aynı isabetlerden; çift başına ~1,5 ms) rozetin altında tek satırlık sarı çizgili bir **yakın kopya** notu çıkar; not yalnızca bilgidir, rozet, sıra ve "En iyi Özgül çift" değişmez.

**Düğme.** Her çiftin altındaki "Özgüllüğü kontrol et" tüm modlarda çalışır ve yan ürünlerin tam listesini açar; otomatik taranmış bir çiftte sonuç önbellekten anında gelir.

**Neden BLAST/BLAT değil.** BLAT 18–24 nt primerler için uygun değildir; eşleşmeyi ~20 bp'lik kusursuz bloklar üzerinden kurduğu için kısa dizilerde gerçek eşleşmeleri kaçırır — özgüllükte en tehlikeli hata tipi, çünkü sonuç "temiz" görünür. BLAST doğru araçtır ama primer **başına** cevap verir; bizim sorumuz çift bazındadır ("kaç yan ürün amplikonu çıkar"), yani eşleştirme mantığı yine elle yazılmak zorundadır. Üstelik genom başına ~5 GB veritabanı ve 20–40 dakikalık `makeblastdb` gerektirir, dağıtılan uygulamaya üçüncü parti ikili eklenmesini zorunlu kılar.

**Yöntem (seed-and-extend).** Uzama yalnızca 3' uç oturduğunda gerçekleşir; bu yüzden önce primerin son 6 bazı genomda tam eşleşme olarak aranır, bulunan her noktada primerin tamamı hizalanıp uyumsuz baz sayılır, eşiği aşanlar elenir. Kalan bölgeler yönlerine göre eşleştirilir: bir `+` yönlü bölge ile sağındaki bir `−` yönlü bölge, aralarındaki mesafe makulse yan ürün oluşturur. `F+F` ve `R+R` kombinasyonları da kontrol edilir.

Sonuçlar üç risk seviyesinde sunulur (iki bağlanma bölgesindeki **toplam** uyumsuzluğa göre): ≤2 yüksek, 3–5 orta, 6+ düşük. 20 bazlık bir primerde 3–4 uyumsuzluk pratikte çoğalmayı durdurur.

**Değerlendir: 3' kuralının dışında kalan yakın yer** (`evaluate._yakin_kopya`, v0.8.39). Tohum kuralı yüzünden taramaya girmeyen ama çiftin yalnızca 1–2 baz farkla ürün verebileceği yer ayrıca aranır: taramanın 0–1 uyumsuzla bulduğu yerlerin (çapa) iki yanında ürün boyu kadar pencerede iki primer 3' kuralı olmadan aranır (`kopya._yakin_yerler`); ürünün en az bir yerinde fark primerin son 6 bazındadır (yoksa ürün zaten listededir). Bulunursa ürün tablosunun altında "Kopyadan yalnızca tek baz farkı var — temkinli olun" notu çıkar: yer, boy, farkın hangi primerde ve 3' uçtan kaçıncı bazda olduğu, primer bazı ve karşısındaki kalıp bazı. Liste ve karar değişmez. Sınırlar: iki primerin kopya yeri de 3' kuralı dışında kalırsa çapa olmadığından bulunmaz (iki ayrı 3' farkı daha güçlü bir ayrımdır); 0–1 uyumsuzlu çapa 100'ü aşarsa (tekrar dizisi) arama yapılmaz. Örnek: CYP21A2 çifti (GRCh37) — R'nin CYP21A1P'deki yeri yalnız 3' son bazda farklı (primerin G'si karşısında T), 514 bp'lik kopya ürünü iki tabloda da yoktu. Ek süre ölçülemeyecek kadar küçük (<0,01 sn). Nöbetçiler: `test_yakin_kopya_notu`, `test_yakin_not_metni`.

**Değerlendir: F/R rol kararı, hedef konum, RNA tek primer, hedef kopya sayılmaz** (`evaluate.py`, düzeltme aşaması 2, K3). (1) F/R rolleri genin KENDİ lokusundaki üründen okunur: MANE transkriptiyle örtüşen ürün(ler) esas alınır, her biri kendi genin ipliğine göre sınanır (`_urun_geni_mane`; psödogenlerde MANE yoktur). Eskiden tüm çift ürünlerine bakan `all()`, ters yönlü bir psödogen kopyası (PMS2/PMS2CL, NCF1/NCF1B-C) beklenen yönde ürün verince uyarıyı susturuyordu. Genin lokusu dışındaki kopyalar farklı yönde oturuyorsa `pair_roles_copies` alanı ve kısa bir bilgi notu gelir. MANE'li ürün yoksa eski kural sürer. (2) Hedef konum alanı en başta çözülür (`_hedef_coz`): tanınmayan kromozom öneki ve derlemeye uymayan RefSeq sürümü 400; hedef verilmiş ama hiçbir üründe değilse `target_info` ve bilgi bulgusu. (3) RNA/cDNA modunda tek primer, DNA modundaki gibi yalnızca kendi özellikleri ve yerleşimiyle değerlendirilir; "sırtları dönük" teşhisi çifte özgüdür, tek primerde bilgi notu "ikinci primeri girin" der. (4) `_yakin_kopya` hedef lokusla (tam eşleşen ürün ya da dolaylı ürün; verilmişse hedef konum) örtüşen adayı atar ve hedef hiç bilinmiyorsa not vermez: hedefin 3' ucunda yazım hatası olan çiftte hedefin kendisi "kopya" sayılıyordu. Nöbetçi: `test_degerlendir_k3`.

**Performans.** Tam genom taraması çift başına ~2–3 saniye (24 çekirdekli makinede, 12 işçi). Kromozomlar 16 Mbp'lik parçalara bölünerek taranır; bu hem belleği işçi başına ~50 MB'de tutar hem de iş dağılımını dengeler. Kromozomun tamamını belleğe alan ilk sürüm 12 işçiyle takasa girip taramayı 47 saniyeye çıkarıyordu. Bütün primerler bağlanma yeri sınırını aşınca (tekrar dizisi, ör. poli-A) tarama erken biter: işçilere işaret verilir, kalan parçalar taranmaz, sonuçlar okunup bırakılır ve havuz olağan yoldan (`close` + `join`) kapanır; en iyi Özgül çift aramasının durdurulması da aynı yoldan geçer (`_durdu`, nöbetçi `test_havuz_olagan_kapanir`). Havuzu işçiler ~10 MB'lik sonuç gönderirken `terminate()` ile kesmek Windows'ta arada bir kilitleniyordu (2026-11-09: poli-A çiftinde 41 erken bitişte 1; sonuç iş parçacığı yarım mesajı bekliyordu) ve tarama kilidi bırakılmadığı için sonraki bütün taramalar da beklerdi.

**Doğrulama.** SMN1 ekson 7'ye tasarlanan çift, SMN2 paralogunu her iki genomda da 0 uyumsuzlukla ve birebir aynı ürün boyunda yakalar (2026-10-31: 295 bp, iki yönde de) — SMA tanısındaki klasik tuzak. İlk sıradaki çiftte bile bir primer tekrar dizisine oturabilir: 2026-10-31 taramasında TP53 ekson 7'nin ortasına tasarlanan 1. çiftin reverse primeri genomda 304 kez tam geçiyordu; otomatik rozet bunu "Yüksek riskli yan ürün" olarak gösterir.

Bu kontrol **yerel genom dosyası gerektirir**; Ensembl API ile yapılamaz.

### Genom dosyası denetimi (`engine.genome_check`, `specificity.fai_engeli`, v0.8.40)

Genom üç kapıdan tanıtılır (elle seçim `/set_genome`, `config.json`, uygulama klasöründeki `genomes\` taraması); üçünde de aynı denetim çalışır ve denetimden geçmeyen genom hiçbir yolda kullanılmaz.

- **Kesik FASTA / yarım `.fai`** (`fai_denetle`: `kesik`, `yarim`; `uyusmuyor` zaten engelliydi). Eskiden açılışta uyarı üretilip atılıyordu ve özgüllük taraması eksik genomda `specific: true` diyordu (A7-04). Şimdi `S.fai_engeli` bu üç durumda mesaj döndürür; `engine._open_fasta_ham` (tasarım, dizi okuma) ve `S.read_fai` (özgüllük taraması, rozetler, En iyi Özgül çift, Değerlendir) bu mesajla hata verir (400). Genom kayıtlı kalır, böylece sessizce Ensembl'e düşülmez ve kullanıcı `.fai`'yi onarınca yeniden seçmesine gerek kalmaz. `/health`: `genomes[asm]` yalnız var **ve** kullanılabilir ise `true`; `genome_warnings[asm]` (istek dilinde metin) ve `genome_blocked[asm]` eklendi. Arayüz bu uyarıyı üst bantta (kullanılamıyorsa kırmızı, yalnız uyarı ise sarı), Ayarlar > Genom satırında ve Hakkında'da gösterir; `/set_genome` yanıtına `usable` eklendi, `warning` varsa yeşil "tanıtıldı" yerine sarı uyarı çıkar (A6-02).
- **Yanlış derleme** (`engine.derleme_denetle`, A6-01). `.fai`'deki 1, 17 ve X uzunlukları (`DERLEME_UZUNLUK`: GRCh37 249.250.621 / 81.195.210 / 155.270.560; GRCh38 248.956.422 / 83.257.441 / 156.040.895, iki genomun `.fai`'lerinden ölçüldü) ile karşılaştırılır; `chr` öneki fark etmez. Yalnız **öbür** derlemeye uyuyorsa dosya reddedilir (`/set_genome` 400, `config.json`'a yazılmaz, `GENOME_REJECTED`'a sebep yazılır; mesaj hangi derlemeye benzediğini ve ölçülen uzunlukları söyler). `.fai` yoksa denetlenemez (dosya reddedilmez; indeks uyarısı zaten çıkar); indeks ilk kez kurulduğunda (`engine._open_fasta_ham`, `downloads.py`) tamlık denetimi hemen çalışır. Ortam değişkeniyle (`ALLPRIME_GENOME_GRCH37/38`) gelen yol da açılışta `ortam_genomlarini_denetle` ile aynı denetimden geçer.
- **Eksik ya da kesik genom** (`engine.tamlik_mesaji`, D3-04, Kritik). Kendi içinde tutarlı ama kesik bir FASTA'nın `.fai`'si (örneğin `.fai` yokken ilk istekte kesik dosyadan kurulan) `fai_denetle`'den "tamam" geçer; eskiden özgüllük taraması bu genomda "Özgül" diyebiliyordu. Şimdi `.fai`'deki ana kromozomların **hepsi** (1–22, X, Y, MT) tanınan derlemenin bilinen uzunluğunda olmalı (`ANA_KROMOZOM_UZUNLUK`; `DERLEME_UZUNLUK` bunun 1, 17, X alt kümesidir). Değerler bu makinedeki gerçek Ensembl GRCh37 ve GRCh38 `.fai` dosyalarından alındı (2026-11-10). Adlar `chr` önekli/öneksiz, `M`/`MT` olabilir; alt/random/Un contig'ler, yamalar ve haplotipler sağlayıcıya göre değiştiği için denetime katılmaz. MT: iki derlemede de yalnız rCRS (NC_012920.1, 16.569 bp; yerel `.fai`'lerde ölçüldü) kabul edilir. UCSC hg19'un eski chrM dizisi (16.571 bp, rCRS değil; bu değer genel bilgidir, yerelde doğrulanmadı) kullanıcı kararıyla (2026-11-10) kabul edilmez; mesaj bunu ayrıca söyler ve rCRS'li bir genom (ör. Ensembl GRCh37 primary_assembly) önerir. Bir kromozom yoksa ya da uzunluğu bilinenden farklıysa (öbür derlemenin uzunluğu değilse) genom kullanılmaz: `genom_uyarisi` engelli döner (`/health` `genome_blocked`), `S.fai_engeli` aynı mesajı döndürdüğü için `_open_fasta_ham`, `S.read_fai` (özgüllük, kopya çiftleri, Değerlendir) ve `/design` 400 verir; mesaj ilk 3 sorunu "chrX bekleniyor 156.040.895 bp, dosyada 101.640 bp (ya da yok)" biçiminde yazar, Y sorunluysa erkek örnekte Y'deki yan ürünlerin kaçabileceğini söyler. Öbür derlemenin uzunlukları bu denetimde sorun sayılmaz, yukarıdaki yanlış derleme kuralı geçerlidir. Denetim yalnız `.fai`'yi okur ve `.fai` imzasıyla önbelleklenir. Yalnız `TAMLIK_MIN_BYTES` (100 MB; `MIN_GENOME_BYTES` ile aynı değer ama ayrı sabit, testler `MIN_GENOME_BYTES`'i 0'a çekebildiği için) ve üstü dosyalara uygulanır: küçük dosya zaten `genome_check`'te reddedilir, testlerin küçük yapay genomları ise bu eşiğin altında kalır ve etkilenmez. Nöbetçi: `test_genom_tamlik` ve `betikler\nobetci_tam_genom.py` (kapsamlı tarama klasörü).
- **Sıkıştırılmış FASTA (`.gz`) tanıtılırken reddedilir** (`engine.genome_check`, G-02, v0.8.61). Motor genomu `.fai` ile doğrudan konum okuyarak kullanır; gzip / bgzip dosyada bu çalışmaz (BioPython yok), eskiden 161 MB'lık bir `.gz` `/set_genome`'da 200 ile kabul edilip `/design` "BioPython >= 1.73 must be installed" ile 500 veriyordu. Denetim uzantıya değil dosyanın ilk iki baytına (`1f 8b`) bakar; üç kapıda da (`/set_genome` 400, `config.json`, `ALLPRIME_GENOME_*`) çalışır, sebep `GENOME_REJECTED`'a yazılır. Mesaj açıktır: dosyayı açıp (`.fa`) tanıtın; Veri dosyaları panelinden indirilen genom zaten açılmış gelir. Nöbetçi: `test_gz_genom_reddi`.
- **Tek kopya kilidi** (`electron/main.js`, G-01, v0.8.61). Aynı kullanıcı profiliyle ikinci kez açılan AllPrime yeni pencere ve motor başlatmaz, kendini kapatır; açık olan pencere öne gelir (küçültülmüşse geri açılır). Kilit `userData` klasörüne bağlıdır: farklı profil ve APPDATA kullanan ölçüm ve test altyapısı etkilenmez. Nöbetçi: `test_gz_genom_reddi` içindeki `main.js` denetimi ve gerçek iki-kopya denemesi.
- Nöbetçiler: `test_genom_eksik_kullanilmaz`, `test_genom_derleme_birim`, `test_genom_derleme_gercek`.

### Girdi çelişkileri ve hatalı deneme (v0.8.41)

- **Konum öneki** (`engine.konum_oneki`, `kromozom_celiskisi`, `oneksiz_koordinat`). Konum kutusundaki `chr2:50.000.001` / `2:50.000.001-50.000.300` öneki, kromozom alanındaki (ya da gen adından bulunan) kromozomla çelişirse tasarım yapılmaz; hata iki kromozomu da adıyla söyler (TR/EN). Aynı kromozom (`chr17:` ile 17) sessizce kabul edilir. Kural motorda (`design_primers`), yani arayüzden ve doğrudan API çağrısından aynen geçerlidir; arayüz öneki kendisi ayrıştırmaz. Kırılma noktası başlangıç/bitiş alanları aynı kuralı izler (`/design_breakpoint`: çelişen önek 400, aynı kromozom önekiyle koordinat kabul). Değerlendir'deki hedef konum alanı kromozom alanı olmadığı için çelişki üretmez; ama aynı önek kuralları orada da geçerlidir (`evaluate._hedef_coz`): tanınmayan kromozom öneki ve derlemeye uymayan RefSeq sürümü 400 verir, konum hiçbir ürünün içinde değilse (başka kromozom dahil) bilgi bulgusu gelir.
- **RefSeq öneki ve tanınmayan önek.** `NC_000001`–`NC_000024` ve `NC_012920` erişim numaraları (`NC_000017.11:7676154`, ClinVar/HGVS biçimi) kromozoma eşlenir (17, X, Y, MT) ve aynı kurala girer; `NC_000017.11:g.7676154` ve `NC_000017.11:7676154-7676160` (aralık), `chr17:7676154-7676160` ile aynı okunur. Konum en çok 12 basamak olabilir; yalnız `0-9` rakamları kabul edilir (okunamayan sayı 400 ile açıkça reddedilir). Tam sayı ayarlarda (örn. çoğaltılabilen en uzun ürün) `1.500` ya da `1,500` 1500 okunur. Kromozom olarak tanınmayan bir önek (`abc:123`) "çelişki" değil "tanınmadı" mesajı alır; önek kromozom alanıyla birebir aynıysa (yerleşmemiş contig adları dahil) sessizce kabul edilir. **Erişim sürümü seçili derlemeyle karşılaştırılır** (`engine.erisim_surumu_denetimi`; konum kutusu, kırılma noktası başlangıç ve bitiş): `NC_000017.10` GRCh37, `NC_000017.11` GRCh38 koordinatıdır. GRCh38 seçiliyken MANE dosyasındaki GRCh38 sürümünden (`annotations/MANE.summary.txt.gz`, `GRCh38_chr` sütunu) farklı bir sürüm, GRCh37 seçiliyken GRCh38'in sürümü 400 ile reddedilir (tasarım yapılmaz). GRCh37 sürümleri için yerelde doğrulanabilir bir liste olmadığından GRCh37 seçiliyken GRCh38'inkinden başka bir sürüm kabul edilir; sürümsüz erişim (`NC_000017`), mitokondri (`NC_012920.1`, iki derlemede de rCRS) ve MANE dosyası yokken (karşılaştırılamaz) de kabul edilir.
- **Çoklu FASTA** (`engine.parse_sequence_input`). Dizi içeriği olan birden fazla FASTA kaydı varsa tasarım yapılmaz; hata kayıt sayısını söyler. İçeriği olmayan başlık kayıt sayılmaz, tek başlıklı tek kayıt eskisi gibi çalışır. İki dizi modunda kural her kutu için ayrı uygulanır (hata kutuyu adlandırır).
- **Hatalı deneme** (`app.js`: `tasarimHatasi`, `mesajiTazele`, `evalHatasi`). Tasarım ya da Değerlendir hatayla bitince (motor hatası, istek hatası ya da arayüz doğrulama hatası) o denemenin önceki sonucu atılır; sonuç alanında yalnız hata görünür ve hata sekme ile dil değişiminde kalır. Arayüzün kendi metni yeni dilde yeniden yazılır, motordan gelen metin olduğu gibi kalır. DNA, RNA, Dizi, Kırılma noktası ve Değerlendir sekmelerinin hepsinde aynı desen.
- Nöbetçiler: `test_coklu_fasta_reddi`, `test_konum_oneki_celiskisi`.

### Kırılma noktası önerisi, küçük duplikasyon yedeği ve MANE gen yönü (v0.8.42)

- **Önerilen belirsizlik payı** (`engine._bp_pay_ara`). "UYARI: Bant ... uzayabilir" notundaki pay önerisi eskiden kuramsal bir formüldü (`(sınır − geo_min) // 4`: primerler en kısa boyda ve tam 100 bp uzakta olsaydı); primer3 o daracık pencerede çoğu zaman çift bulamadığı için önerilen payda uyarı sürüyor ya da hiç çift çıkmıyordu. Formül artık yalnız üst sınırdır: motorun kendisi (`design_breakpoint`, iç çağrı `_oneri_ara=True`, kontrol primersiz) önce bu değerle, sonra 0 ile, sonra ikili aramayla (4 bp adım, en çok 10 sn bütçe) denenir; en az bir çift veren ve en uzun bandı sınırın altında tutan değer yazılır ("motorla denendi"; "en fazla" denmez, çünkü en büyük değer olduğu garanti değildir). Kısa duplikasyonda kuramsal üst sınır negatif çıkabilir; yine de pay 0 denenir ve çalışıyorsa öneri 0'dır ("yalnızca kırılma noktaları tam biliniyorsa"). Hiçbir pay çalışmıyorsa sayı verilmez; not çoğaltılabilen en uzun ürün sınırının en az kaç bp yapılacağını söyler (o sınırda aynı tasarım uyarısız çıkar). Pay girilmemişken (m = 0) de aynı sınır önerisi yazılır.
- **Boy farkı yolunda yedek** (`design_breakpoint`, `size_shift`; yaklaşık 100–220 bp duplikasyon, varsayılan `pcr_max` = 700). Duplike alel bandı sınıra sığsın diye ürün penceresi 436–500 bp'ye daralıyordu; primer3 bu pencerede bulamayınca sonuç boştu. Birleşim yolundaki `_bp_baglanti_sinirli` ile aynı mantık: daralan pencerede çift çıkmazsa (ya da pencere hiç sığmıyorsa) pencere `[taban, taban + 350]` ve `pcr_max` yükseltilerek yeniden denenir; bant sınırı aşabilir ve bu UYARI notuyla söylenir (D bp'lik bant farkı kartta aynen durur). Yedekle de çift çıkmayan bölgede not artık "payı küçült / ürün boyunu genişlet" demez (ikisi bu yolda pencereyi değiştirmez); primer GC aralığını gevşetmeyi önerir.
- **MANE işareti ve gen yönü** (`evaluate._gene_index`, `_urun_geni`, `_context`). refGene satırları `mane_status` taşımaz; "MANE öncelikli" kuralı bu yüzden hiç çalışmıyordu (zıt yönlü genle örtüşen üründe yön "?" kalıp F/R yer değişimi uyarısı susuyordu). Gen indeksi kurulurken MANE listesiyle sürümsüz erişim numarasından (MANE `NM_000546.6`, refGene `NM_000546`) eşlenir; yalnız MANE satırın kopyası işaretlenir, ortak transkript indeksi değişmez. Yön, örtüşen MANE transkriptlerinin genine göre belirlenir (Select > Plus Clinical); MANE transkriptlerin kendisi de zıt yönlü genlerdense (PKD1 + TSC2 gibi) yön "?" kalır. `server._gen_yonu_ekle` (DNA/Kırılma noktası kartları) ve Değerlendir aynı `_urun_geni` fonksiyonunu kullanır; `_context` (ekzon/intron etiketi) de MANE transkripti seçer.
- Nöbetçi: `test_dup_yedegi_ve_mane_yonu` (ve `test_kirilma_noktasi` içindeki ±200 pay denetimi).

### Bilgilendirme ekranı, belge ve paket düzeltmeleri (v0.8.43)

- **Açılış ekranı bilgilendirme ekranı oldu** (`main.js` `NOTICE_VERSION` = "2.1", `noticeSeen`, `noticeKaydi`, IPC `notice-ack`; `consent.html` / `consent.js`). Kayıt yalnız `noticeVersion` + `noticeShownAt` (+ dil tercihi); eski `accepted`, `acceptedAt`, `user`, `host`, `termsVersion`, `appVersion` alanları ilk yazımda silinir, tercihler (tema, boyut, `pcr_max`, laboratuvar değerleri) korunur. `consent.json` artık BOM'lu da okunur (`parseSettings`) ve geçici dosya + yeniden adlandırma ile yazılır; yarım/bozuk dosya `{}` sayılır ve bildirim yeniden gösterilir. Metin kutusu yüksekliği `clamp(150px, 100vh − 430px, 46vh)`: 1024×640'ta düğme ilk görünümde görünür.
- **AUTHORS** yer tutucu notu kalktı; kaynak başlıkları "AllPrime eser sahibi" der.
- **Dağıtıma `.claude` girmez:** `package.json` `build.files` ve `extraResources` filtreleri, `build.ps1` (sidecar temizliği + paket denetimi), `kurulu-guncelle.ps1` (kopyalama atlaması + kurulu klasör uyarısı), `kaynak-zip.ps1` (git pathspec dışlaması + zip denetimi), `.gitignore`.
- **Veri kaynakları** bölümü ve THIRD-PARTY-NOTICES notu (aşağıda).
- Nöbetçiler: `test_bilgilendirme_ekrani`, `test_bilgilendirme_kaydi`, `test_veri_kaynaklari_belgesi`, `test_claude_dagitima_girmez`.

### Bellek: OpenBLAS iş parçacığı sayısı (v0.8.44)

- **`OPENBLAS_NUM_THREADS=1`** (`server.py`, `import engine` öncesi, `os.environ.setdefault`). numpy her yüklenişinde OpenBLAS çekirdek sayısı kadar iş parçacığı tamponu ayırır ve tek geçiş taramasının (`cok_tarama.py`) her havuz işçisi numpy'yi ayrı yükler; tarama BLAS kullanmaz (yalnız eleman bazlı işlemler). 24 mantıksal çekirdekte (12 işçi) en iyi Özgül çift aramasında motor + işçilerin ayrılan özel (commit) belleği 11,6 GB idi, çalışma kümesi 1,65 GB; ayarla işçi başına 865 → 126 MB, toplam 11,6 → 2,0 GB. Ayar süreç ortamına yazıldığı için spawn edilen işçiler ve paketli exe (PyInstaller girişi de `server.py`) miras alır. Kullanıcı ortamda başka değer verdiyse o geçerli kalır (`OPENBLAS_NUM_THREADS=8` iken toplam 4,9 GB).
- **Ölçüm** (4 hedef: TP53, CYP21A2, GABARAP GRCh38 + SORD GRCh37; her koşul 2 tekrar, taze motor): sonuç iki koşulda ve tüm tekrarlarda birebir aynı (`params_used` hariç içerik özeti), süre farkı ≤ 1 sn (TP53 24,0–25,0 sn, CYP21A2 9,4–9,8, GABARAP 51,0–51,7, SORD 26,1–27,1). Toplam özel bayt tepesi 11.376–11.920 MB → 1.763–2.313 MB; çalışma kümesi değişmez (1.406–1.967 MB). Electron arayüzü dahil bütün süreç ağacı: boşta 0,43 GB çalışma kümesi / 0,26 GB özel; aramada tepe 1,96 GB / 2,13 GB.
- `KURULUM.txt` başına "Sistem gereksinimi" bölümü eklendi (RAM, çekirdek, disk, işletim sistemi; ölçülmeyen değerler ölçülmedi diye yazıldı).
- Nöbetçi: `test_openblas_ortami` (`import server` sonrası değer 1; kullanıcı değeri ezilmez; ayar `import engine` öncesinde).

---

## Klasör yapısı

```
AllPrime-kaynak/
├─ backend/                   Python hesaplama motoru
│  ├─ engine.py               primer3 tasarımı, skorlama, cDNA modları
│  ├─ transcripts.py          refGene okuma, c. ↔ cDNA ↔ genomik çeviri
│  ├─ specificity.py          genom taraması, yan ürün tespiti
│  ├─ dbsnp.py                yaygın varyant indeksi (kurulum + sorgu)
│  ├─ kopya.py                psödogenli gende kopyadan ayrışan çift araması
│  ├─ server.py               yerel Flask sunucu (Electron sidecar'ı)
│  ├─ allprime-server.spec   PyInstaller yapılandırması
│  ├─ requirements.txt        çalıştırma bağımlılıkları
│  └─ requirements-build.txt  sadece derleme (PyInstaller)
├─ electron/                  masaüstü arayüz
│  ├─ main.js, preload.js, favoriler.js, sagTik.js, motorBekle.js
│  ├─ renderer/               index.html, app.js, style.css
│  └─ sidecar/                derlenmiş Python sunucusu (build.ps1 üretir)
├─ annotations/               transkript tabloları — kaynak nüsha (~18 MB)
└─ build.ps1                  sidecar derlemesi + kurulum dosyası üretimi

..\AllPrime\                 ÇALIŞAN UYGULAMA — deponun YANINDA, içinde değil
   ├─ AllPrime.exe
   ├─ genomes/                referans FASTA (~6 GB)
   ├─ annotations/            transkript tabloları + dbSNP indeksleri
   ├─ KURULUM.txt             kullanım notları (son kullanıcı için)
   ├─ USER_GUIDE.txt          KURULUM.txt'nin İngilizcesi
   ├─ kaynak/                 AllPrime'ın kaynak kodu (zip; kurulu-guncelle.ps1 koyar)
   └─ resources/app, resources/backend
```

İki klasör: **`AllPrime-kaynak` = kaynak kod**, geliştirme için — günlük kullanımda
dokunulmaz; **`AllPrime` = çalışan uygulama**, başka bilgisayara kopyalanacak olan.
Uygulama eskiden deponun içinde, depoyla aynı adlı bir alt klasördeydi; bu karışıklık
yaratıyor ve kopyalarken kaynak kodu da taşıyordu, o yüzden dışarı alındı ve kaynak
klasörü açıkça adlandırıldı. Uygulama klasörüne isteğe bağlı bir `backend.txt`
(içinde kaynağın `backend` yolu) konursa motor paketli exe yerine Python ile kaynaktan
çalışır; Windows Akıllı Uygulama Denetimi imzasız exe'yi engelleyen makineler içindir.
Bu makinede denetim kapalı olduğu için 2026-10-29'da kaldırıldı: kurulu uygulama artık
dağıtılan paketli motoru kullanır, yani burada denenen motor kopyalanacak motorun aynısıdır.

Referans genomlar yalnızca `AllPrime\genomes\` altında, açılmış `.fa` + `.fai`
hâlinde tutulur. İndirilen `.gz` arşivleri açıldıktan sonra işlevsiz kaldığı için
saklanmıyor; yeniden gerekirse Ensembl'den indirilir.

**Dağıtım birimi `AllPrime\` klasörünün kendisidir** — zip'e gerek yok, olduğu
gibi kopyalanır. Bu yüzden her motor/arayüz değişikliğinden sonra bu klasör
güncellenmelidir; ayrı bir hazırlık klasörüne paketleyip kurulu olanı eski
bırakmak, kopyalanan makinelerde "yeni arayüz + eski motor" hatasına yol açar.

## Veri dosyaları

| Dosya | Kaynak | Boyut | Pakete dahil |
|---|---|---|---|
| `refGene_hg19.txt.gz`, `refGene_hg38.txt.gz` | UCSC `hgdownload.soe.ucsc.edu` | ~8 MB | evet |
| `MANE.summary.txt.gz` | NCBI `ftp.ncbi.nlm.nih.gov/refseq/MANE` | ~1 MB | evet |
| `dbsnp_common_hg19/38.apidx` | UCSC `snp151Common` (işlenmiş) | ~138 MB her biri | evet |
| `Homo_sapiens.GRCh37/38...fa` + `.fai` | Ensembl | ~3 GB her biri | **hayır** |

Genom FASTA dosyaları büyüklüğü nedeniyle kuruluma dahil edilmez. Kurulumdan sonra
`genomes\` klasörü **uygulamanın yanına** kopyalanır; program açılışta kendiliğinden bulur.
Bulunamazsa ⚙ Ayarlar'daki "Genom dosyaları" bölümünden elle tanıtılabilir (seçim
`%APPDATA%\AllPrime\config.json`'a kaydedilir; önceki sürümlerin eski adlı ayar
klasörü ilk açılışta buraya taşınır). Hiç tanıtılmazsa Ensembl REST API'ye
düşer — internet gerektirir, hasta verisi gönderilmez ama yavaştır.

> `.fa` dosyalarının yanında `.fai` indeks dosyası bulunmalıdır. Yoksa pyfaidx ilk
> açılışta üretir; 3 GB'lık dosyada bu birkaç dakika sürer.

## Veri kaynakları

Yalnız olgu: hangi veri nereden alınır, pakette mi, hangi sürüm. Kaynakların kendi
kullanım koşulu sayfaları ve alıntıları `THIRD-PARTY-NOTICES.txt` içindeki "Veri dosyaları /
Data files" bölümündedir. Adresler kodda geçen indirme ve sorgu adresleridir
(`backend/downloads.py`, `backend/engine.py`).

| Veri seti | Kaynak ve adres | Pakette | Sürüm / tarih | Atıf satırı (öneri) |
|---|---|---|---|---|
| Referans genom, GRCh38 ve GRCh37 primary assembly FASTA | Ensembl: `https://ftp.ensembl.org/pub/current_fasta/homo_sapiens/dna/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz`, `https://ftp.ensembl.org/pub/grch37/current/fasta/homo_sapiens/dna/Homo_sapiens.GRCh37.dna.primary_assembly.fa.gz` | **hayır** (indirilir ya da elle konur) | Adresler "current" klasörüne bakar: indirme anındaki güncel Ensembl sürümü. Sürüm numarası dosyada yazılı değil (başlık yalnız derleme adı ve kromozom uzunluğu). Ölçülen kurulu kopyaların dosya tarihi: 2026-07-01 | Ensembl, Homo sapiens GRCh38 / GRCh37 primary assembly (DNA), `ftp.ensembl.org`, erişim tarihi: GG.AA.YYYY |
| Transkript ve ekson yapısı (refGene; NCBI RefSeq kayıtlarının UCSC tablosu) | UCSC Genome Browser: `https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/refGene.txt.gz` ve `.../hg19/database/refGene.txt.gz` | **evet** (`annotations/refGene_hg19.txt.gz`, `refGene_hg38.txt.gz`) | UCSC'nin o günkü dosyası; sürüm dosyada yazılı değil. Ölçülen paket kopyalarının dosya tarihi: 2026-08-22 | UCSC Genome Browser, refGene tablosu (hg19 / hg38), `hgdownload.soe.ucsc.edu`, erişim tarihi: GG.AA.YYYY |
| Kanonik transkript işareti (MANE Select / Plus Clinical; NCBI RefSeq erişim numaraları) | NCBI: `https://ftp.ncbi.nlm.nih.gov/refseq/MANE/MANE_human/current/` (dosya adı `MANE.GRCh38.v<sürüm>.summary.txt.gz`, çalışma anında çözülür) | **evet** (`annotations/MANE.summary.txt.gz`) | İndirilen dosyanın adındaki sürüm yerelde saklanmaz (kaydedilen ad `MANE.summary.txt.gz`). Ölçülen paket kopyasının dosya tarihi: 2026-08-22 | NCBI RefSeq, MANE (Matched Annotation from NCBI and EMBL-EBI), `ftp.ncbi.nlm.nih.gov/refseq/MANE`, erişim tarihi: GG.AA.YYYY |
| Yaygın varyantlar (dbSNP build 151, MAF ≥ %1 alt kümesi) | NCBI dbSNP verisinin UCSC tablosu `snp151Common`: `https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/snp151Common.txt.gz` ve `.../hg19/database/snp151Common.txt.gz`. AllPrime veriyi NCBI'dan değil UCSC'den alır | **evet**, işlenmiş hâliyle (`annotations/dbsnp_common_hg19.apidx`, `dbsnp_common_hg38.apidx`; ham tablo pakette yok) | dbSNP build 151 (tablo adından). Ölçülen paket kopyalarının dosya tarihi: 2026-11-01 | NCBI dbSNP build 151 (UCSC Genome Browser `snp151Common` tablosu üzerinden), `hgdownload.soe.ucsc.edu`, erişim tarihi: GG.AA.YYYY |
| Ensembl REST (veri dosyası değil, ağ servisi) | `https://rest.ensembl.org` (GRCh38), `https://grch37.rest.ensembl.org` (GRCh37) | uygulamanın parçası değil | Yalnız yerel genom tanıtılmamışsa (dizi: koordinat sorgusu) ve yerel refGene yoksa (gen sembolü sorgusu) çağrılır; hasta verisi gönderilmez | Ensembl REST API, `rest.ensembl.org`, erişim tarihi: GG.AA.YYYY |

Dosya tarihleri kurulu klasörde ölçülen dosya değişiklik tarihleridir; kaynağın yayın tarihi ya da
sürümü değildir. Raporlarda ya da yayında bir veri setinin sürümü gerekiyorsa, kullanılan
dosyayı indirdiğiniz tarihi ve yukarıdaki adresi yazın.

## Geliştirme

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
cd ..\electron
npm install
npm start
```

Geliştirme modunda `electron/sidecar/` yoksa `backend/.venv` ile `server.py` doğrudan
çalıştırılır. Genom otomatik bulunamayabilir; ilk açılışta bir kez "Seç" ile tanıtmak yeterlidir.

### Duman testi

Kod değişikliğinden sonra çalıştırın — motoru uçtan uca sınar (~9 dk; genom taraması yapan testler dahil):

```powershell
backend\.venv\Scripts\python.exe backend\test_smoke.py
```

Genom/annotasyon dosyaları yoksa onlara bağlı testler atlanır, gerisi yine koşar.
Testlerin çoğu gerçekten yaşanmış bir hatanın nöbetçisidir; silmeden önce
ilgili yorumu okuyun.

### Kurulu uygulamayı güncelleme

Kaynakta yapılan değişiklik kurulu uygulamaya (`..\AllPrime`) kendiliğinden
gitmez. Elle kopyalarken dosya unutmak kolay (üç kez oldu); bunun yerine:

```powershell
.\kurulu-guncelle.ps1           # arayüz + main.js + package.json
.\kurulu-guncelle.ps1 -Motor    # üstüne motoru da derleyip yerleştirir
```

Betik sürüm tutarlılığını da denetler (`package.json` ↔ `server.py` SURUM).
Uygulama açıkken çalıştırmaz — dosyalar kilitli olur, kopya yarım kalır.
Kurulu klasöre `.claude` (geliştirme aracının yerel izin ve komut geçmişi dosyaları) kopyalanmaz;
kurulu klasörde böyle bir klasör varsa betik uyarır (silmez).

Sonunda `kurulu-temizle.ps1` çalışır: Electron'un artık dağıtmadığı eski çalışma
dosyalarını (yükseltmeden kalan dll'ler) ve arayüzün kullanmadığı dil paketlerini
(`locales\` içinde yalnızca `tr.pak` ve `en-US.pak` kalır) TEMP'teki yedeğe taşır;
exe, motor ve Electron yedeklerinin her türünden yalnızca en yenisini tutar.

Her çalıştırmada uygulama klasörüne `kaynak\AllPrime-kaynak-<sürüm>.zip` de konur:
klasör kurum dışına verilirse GPL (v2 Bölüm 3, v3 Bölüm 6) kaynağın da
birlikte verilmesini ister. Zip `kaynak-zip.ps1` ile git'ten üretilir; commit
edilmemiş değişiklikler de girer, git'e hiç eklenmemiş dosyalar girmez (betik uyarır);
`.claude` klasörleri (git'e eklenmiş olsalar bile) zip'e girmez ve betik zip'i bunun için denetler.

## Dağıtım paketi

```powershell
.\build.ps1
```

Sidecar'ı PyInstaller ile derler, `electron/sidecar/`'a koyar, ardından electron-builder
ile NSIS kurulum dosyası üretir (`electron/dist/`). Pakete `.claude` girmez (`package.json`
filtreleri; `build.ps1` paket klasöründe `.claude` bulursa hata verir). Bu yol kaynak zip'ini pakete
koymaz; kurulum dosyası kurum dışına verilecekse zip `kaynak-zip.ps1` ile üretilip
eklenmeli (GPL v2 Bölüm 3, v3 Bölüm 6).

İki tuzak:

1. **Sidecar "onedir" derlemesidir** — `allprime-server.exe` tek başına çalışmaz,
   yanındaki `_internal\` klasörüyle birlikte kopyalanmalıdır. `build.ps1` bunu yapar;
   elle kopyalarken atlanırsa uygulama açılır ama motor başlamaz.
2. **OneDrive** senkronize klasörde PyInstaller'ın `build\` dizini kilitlenip
   `PermissionError [WinError 5]` verir. `build.ps1` bu yüzden geçici klasörde derler.
