// AllPrime - Primer Tasarim Araci
// Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
//
// GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
// (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
// verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
// AllPrime - dil sozlugu
// Arayuzdeki TUM metinler buradan gelir. HTML tarafinda data-i18n / data-i18n-ph /
// data-i18n-title nitelikleri kullanilir; app.js tarafinda t("anahtar") cagrilir.
// Deger fonksiyon olabilir: t("anahtar", 5) -> fonksiyona parametre gecer.

const I18N = {
  tr: {
    // --- ust bar / sekmeler ---
    "app.title": "AllPrime",
    "app.subtitle": "Varyanta özgü primer tasarımı · primer3 motoru",
    "app.copyright": "© 2026 Eren Kılınç · GNU GPL v2 veya sonrası",
    "app.notice":
      "AllPrime © 2026 Eren Kılınç. Bu program GNU Genel Kamu Lisansı (GPL) sürüm 2 ya da " +
      "(isteğinize göre) daha sonraki bir sürümü ile lisanslıdır ve <b>hiçbir garanti " +
      "olmaksızın</b> sunulur; bu koşullar altında kopyalanıp dağıtılabilir. Lisans metinleri " +
      "uygulama klasöründeki LICENSE (GPL v2) ve LICENSE-GPL-3.0.txt (GPL v3) dosyalarındadır; " +
      "bildirim metni için <a href='#' class='ayar-git'>⚙ Ayarlar › Hakkında</a> bölümündeki " +
      "\"Lisans ve sorumluluk bildirimi\"ne bakın.",
    "genome.label": "Referans Genom",
    "tab.dna": "DNA · genomik",
    "tab.rna": "RNA · cDNA",
    "tab.seq": "Dizi",

    // --- DNA sekmesi ---
    "dna.gene": "Gen (opsiyonel)",
    "dna.gene.ph": "örn. TP53",
    "dna.gene.help": "Kromozom boşsa gen adından bulunur.",
    "dna.chrom": "Kromozom",
    "dna.chrom.ph": "örn. 17 veya chr17",
    "dna.pos": "Genomik Koordinat (varyant)",
    "dna.pos.ph": "örn. 7676154  ya da  7676154-7676208",
    "dna.pos.hint": "Tek nokta ya da varyantın tamamı (aralık)",
    "dna.pos.title":
      "Nokta varyantta tek koordinat yazın. Varyant birkaç bazdan uzunsa (indel, delins) " +
      "tamamını aralık olarak yazın: 7676154-7676208. O zaman primerler aralığın tamamının " +
      "dışına konur; aksi hâlde primer varyantın içine düşebilir, varyantlı alele bağlanamaz " +
      "ve heterozigot örnek homozigot görünür. Delesyon/duplikasyonda Kırılma noktası sekmesi " +
      "daha uygundur: primerleri bölgenin dışına koyar ve iki bandı birlikte verir.",

    // --- RNA sekmesi ---
    "rna.acc": "Transkript (NM_)",
    "rna.acc.ph": "örn. NM_000546.6",
    "rna.acc.help": "Sürüm numarası yok sayılır.",
    "rna.search": "Gen ile ara (opsiyonel)",
    "rna.find": "Bul",
    "rna.search.help": "Genin transkriptlerini listeler, MANE Select işaretlenir.",
    "mode.label": "Tasarım tipi",
    "rna.mode.variant": "Varyant (c.)",
    "rna.mode.skip": "Ekson atlama testi",
    "rna.cpos": "c. Koordinatı",
    "rna.cpos.ph": "örn. c.1234 · c.-45 · c.*120",
    "rna.exon": "Atlanacak eksonlar",
    "rna.exon.ph": "örn. 4-6",
    "rna.exon.range": "ya da aralık yazın:",
    "rna.exon.hint0":
      "Ekson numarasını yazın: 7, 4-6 (bitişik) ya da 4,6 (bitişik değil). Geçerli bir transkript " +
      "kodu girilince eksonlar düğme olarak da görünür.",
    "rna.exon.hint":
      "Eksonlara tıklayarak seçin; bitişik birkaç ekson için ilkine ve sonuncusuna tıklayın " +
      "(Shift+tıklama aralığı seçer). İlk ve son ekson seçilemez (bir yanında çapa ekson yok).",
    "ex.uc": "İlk/son ekson: bir yanında çapa ekson olmadığı için seçilemez",
    "ex.secilen": "Seçilen",
    "ex.ekson": "ekson",
    "ex.bitisikDegil": "bitişik değil",
    "ex.atlanan": "atlanan",
    "ex.korunur": "okuma çerçevesi korunur",
    "ex.kayar": "okuma çerçevesi kayar",
    "ex.primer": (a, b) => `Primerler ekson ${a} ve ekson ${b} içine konur.`,
    "ex.fark": (n) => `Normal ve atlanmış bant arasındaki fark ${n} bp.`,
    "ex.bantlar": "Beklenen bantlar (normale göre)",
    "ex.utr": "Seçimin bir kısmı UTR'de; çerçeve yalnız kodlayan kısımdan hesaplandı.",
    "ex.not": "Ürün boyu tasarımda hesaplanır; en uzun ürün sınırını aşarsa açık bir mesaj çıkar.",
    "ex.disi": (l) => `Seçilemez: ${l} (ilk/son ekson ya da transkriptte yok).`,
    "ex.yakin": (a, b) => `${a} bp ve ${b} bp bantları birbirine çok yakın; jelde ayırt etmek zor olabilir.`,
    "chip.bandsTitle": "Seçilen eksonlar tek tek ya da birlikte atlanırsa görülecek bant.",
    "csv.skipExons": "Atlanan_eksonlar",
    "csv.bands": "Beklenen_bantlar",
    "rna.junction.label": "Primer ekson sınırının <b>üzerine</b> otursun",
    "rna.junction.help":
      "Kapalıyken (varsayılan) forward ve reverse farklı eksonlara yerleşir; ürün gDNA'da " +
      "intron kadar uzar, iki boyut da gösterilir. Açıkken primerlerden biri doğrudan ekson " +
      "sınırına oturur ve gDNA'ya hiç bağlanmaz — daha kesindir ama bazen uygun primer bulunamaz.",
    "rna.skip.help":
      "Seçilen eksonların (bitişik blok için ilkinin ve sonuncusunun) <b>öncesindeki ve " +
      "sonrasındaki</b> eksonlara primer yerleştirilir. Normal transkript uzun, atlanmış " +
      "transkript kısa ürün verir; fark atlanan eksonların toplam uzunluğu kadardır. " +
      "Bitişik olmayan eksonlar seçilirse (örn. 4,6) aradaki eksonlar da hedef bloğun içinde " +
      "kalır; her ekson tek başına ya da hepsi birlikte atlanırsa görülecek bantlar ayrı " +
      "hesaplanıp gösterilir, birbirine çok yakın bantlar uyarıyla işaretlenir. Primerler " +
      "hedef bloğa komşu sınırların üzerine <b>oturmaz</b> — otursaydı atlanmış " +
      "transkripte bağlanamaz, aranan bant hiç görünmezdi. Amplikon aralığı bu modda " +
      "otomatik ayarlanır (gelişmiş parametrelerdeki değerler kullanılmaz).",

    // --- Dizi sekmesi ---
    "seq.mode.single": "Tek dizi",
    "seq.mode.pair": "İki dizi (F / R bölgesi)",
    "seq.single.label": "Dizi",
    "seq.single.ph":
      "Diziyi yapıştırın. FASTA başlığı, boşluk, satır numaraları ve küçük harf sorun değil.\n" +
      "Hedefi köşeli parantezle işaretleyebilirsiniz:  ...ACGT[A/G]TTTC...",
    "seq.single.help": "Genom veya transkript gerekmez; primerler doğrudan bu dizi üzerinde tasarlanır.",
    "seq.target": "Hedef konum (opsiyonel)",
    "seq.target.ph": "örn. 1234 veya 1200-1260",
    "seq.target.help": "Boş bırakılırsa köşeli parantez kullanılır; o da yoksa dizinin tamamı serbesttir.",
    "seq.fwd.label": "Forward primer bu dizinin içinden seçilsin",
    "seq.fwd.ph": "1. bölge (örn. füzyonun 5' partneri)",
    "seq.rev.label": "Reverse primer bu dizinin içinden seçilsin",
    "seq.rev.ph": "2. bölge (örn. füzyonun 3' partneri)",
    "seq.free.label": "Mesafe bilinmiyor — <b>ürün boyu kısıtı uygulanmasın</b>",
    "seq.free.help1":
      "İki dizinin gerçekte ne kadar uzakta olduğunu bilmiyorsanız bunu işaretleyin. " +
      "Primerler dizilerin <b>her yerinden</b>, yalnızca kaliteye göre seçilir. " +
      "Kapalıyken amplikon aralığı (gelişmiş parametreler) devrededir ve primerleri " +
      "dizilerin birleşme noktasına doğru çeker — füzyon/kırılma noktasında doğru " +
      "davranış budur, ama mesafe bilinmiyorsa iyi primerleri gereksiz yere eler.",
    "seq.free.help2":
      "Her iki durumda da forward yalnızca birinci, reverse yalnızca ikinci dizinin " +
      "içinden seçilir; hiçbiri diğerine taşmaz.",
    "seq.gap.summary": "İki dizi arası mesafe",
    "seq.gap.label": "Mesafe (bp)",
    "seq.gap.help":
      "Yalnızca şu durumda gerekir: iki dizi tek bir gerçek ürünün iki ucu, aradaki " +
      "parçayı yapıştırmadınız ama uzunluğunu biliyorsunuz. Yazarsanız araya o kadar " +
      "<b>N</b> konur — ürün boyu doğru hesaplanır ve primer o bilinmeyen bölgeye " +
      "oturamaz. Diğer tüm durumlarda <b>0</b> bırakın.",

    // --- dbSNP ---
    "snp.label": "Yaygın varyantların (dbSNP) üzerine primer <b>koyma</b>",
    "snp.help":
      "Primerin bağlandığı yerde yaygın bir varyant varsa o allel çoğalmaz ve " +
      "heterozigot hasta <b>homozigot</b> görünür. Açıkken bu konumlar primer3'e baştan " +
      "yasaklanır. Bölge çok yoğunsa kısıt otomatik gevşetilir ve size bildirilir. " +
      "Kapatmak yalnızca kasıtlı durumlarda anlamlıdır (örn. allele-spesifik primer).",
    "snp.missing": (asm) => `${asm} için yaygın varyant tablosu bulunamadı — bu kontrol devre dışı.`,
    "snp.none": "SNP kontrolü yok",
    "snp.none.title": "Bu genom için dbSNP tablosu kurulu değil; primerler yaygın varyant kontrolünden geçmedi.",
    "snp.avoided": (n) => `${n} yaygın varyanttan kaçınıldı`,
    "snp.avoided.title": "Şablondaki bu konumlar primer3'e yasaklandı; primerler oralara oturmadı.",
    "snp.notApplied": (n) => `${n} yaygın varyant · kısıt uygulanmadı`,
    "snp.notApplied.title": "Kısıt uygulanamadı — notlara bakın.",
    "snp.clean": "Bölgede yaygın varyant yok",

    // --- gelismis parametreler ---
    "adv.summary": "Gelişmiş parametreler",
    "adv.pcr_max": "Çoğaltılabilen en uzun ürün (bp)",
    "adv.pcr_max.title":
      "Laboratuvarınızda PCR ile güvenle çoğaltabildiğiniz en uzun ürün — bir tavan. " +
      "'Amplikon max'tan farkı: amplikon aralığı primer3'ten istediğiniz hedef boydur ve " +
      "yalnızca o tasarımı bağlar; bu sınır HER modda geçerlidir (amplikon aralığını kendi " +
      "hesaplayan ekson atlama gibi modlarda da) ve primer3'ün seçmediği bantları — kırılma " +
      "noktasındaki normal alel, kontrol ve duplikasyon bantlarını — değerlendirirken ölçü " +
      "budur. İkisi çelişirse küçük olan geçerlidir. Bu bilgisayarda kaydedilir.",
    "adv.product_min_gc": "Ürün GC min (%)",
    "adv.product_max_gc": "Ürün GC max (%)",
    "adv.product_gc.title":
      "Çoğaltılacak ürünün (amplikonun) GC yüzdesi bu aralıkta olsun. 0-100 bırakırsanız " +
      "kısıt uygulanmaz, GC yalnızca bilgi olarak gösterilir. Aralık dışında kalan aday " +
      "çiftler elenir ve kaç tanesinin elendiği sonuçların üstünde yazılır.",
    "adv.product_size_min": "Amplikon min (bp)",
    "adv.product_size_max": "Amplikon max (bp)",
    "adv.min_dist_from_variant": "Varyanta min uzaklık (bp)",
    "adv.primer_min_size": "Primer uzunluk min",
    "adv.primer_opt_size": "Primer uzunluk opt",
    "adv.primer_max_size": "Primer uzunluk max",
    "adv.primer_min_tm": "Tm min (°C)",
    "adv.primer_max_tm": "Tm max (°C)",
    "adv.primer_max_tm_diff": "Tm farkı max (°C)",
    "adv.primer_min_gc": "GC min (%)",
    "adv.primer_max_gc": "GC max (%)",
    "adv.primer_gc_clamp": "GC clamp",
    "adv.primer_max_end_gc": "3' uçta en fazla G/C",
    "adv.primer_max_end_gc.title":
      "Son 5 bazda izin verilen en fazla G/C sayısı. 4-5 G/C'li 3' uç aşırı kararlı olur, " +
      "yanlış yerde bile tutunup uzar. Öneri 3; GC clamp bundan büyük olamaz.",
    "adv.primer_max_poly_x": "Max homopolimer",
    "adv.salt_monovalent": "Na⁺ (mM)",
    "adv.salt_divalent": "Mg²⁺ (mM)",
    "adv.dntp_conc": "dNTP (mM)",
    "adv.dna_conc": "Primer (nM)",
    "adv.dmso_conc": "DMSO (%)",
    "adv.num_return": "Sonuç sayısı",

    // --- eylemler / genom paneli ---
    "act.design": "Primer Tasarla",
    "act.export": "CSV indir",
    "act.autoSpec": "Özgüllüğü otomatik kontrol et",
    "act.autoSpec.title": "DNA modunda her çift arka planda genomda taranır ve kartına bir rozet eklenir. Hiçbir çift atılmaz, sıralama değişmez; seçimi siz yaparsınız. Yerel genom gerekir; çift başına ~3 sn.",
    "auto.queued": "Özgüllük: sırada",
    "auto.scanning": "Özgüllük: taranıyor…",
    "auto.failed": "Özgüllük: kontrol edilemedi",
    "auto.error": "Özgüllük: taranamadı",
    "auto.specific": "Özgül",
    "auto.specific.title": "Hedef dışında kayda değer (en fazla 5 uyumsuzluklu) ürün bulunmadı.",
    "auto.high": (n) => `Yüksek riskli yan ürün: ${n}`,
    "auto.medium": (n) => `Orta riskli yan ürün: ${n}`,
    "auto.medium.title": "İki primerde toplam 3–5 uyumsuzlukla oluşan yan ürün; çoğu zaman bant vermez. Ayrıntı için Özgüllüğü kontrol et.",
    "auto.where": (c, s, n, m) => `En riskli: chr${c}:${s} · ${n} bp · ${m} uyumsuzluk`,
    // Rozetin altındaki "yakın kopya" satırı (server._yakin_not; yalnız bilgi, rozet kararı değişmez)
    "auto.yakin": (yer, boy, parca) => `Yakın kopya: ${yer} (${boy} bp); ${parca}. Ayrıntı Değerlendir'de.`,
    "hairpin.uyari": (ad, hp, ta, pay) => `Hairpin: ${ad} primerin hairpin Tm'i ${hp} °C; önerilen Ta ${ta} °C'nin ${pay} °C altını geçiyor. Primer kendi üzerine katlanıp verimi düşürebilir.`,
    "auto.yakin.primer": (ad, y) => `${ad} primerin ${y.map((u) => (u === 1 ? "3' son bazında" : `3' ucundan ${u}. bazda`)).join(" ve ")} ${y.length} uyumsuzluk`,
    "gp.summary": "Genom dosyaları (yerel FASTA)",
    "gp.help": "İndirilen GRCh37 / GRCh38 FASTA (.fa) dosyalarını burada tanıtın. " +
               "Tanıtılmazsa geçici olarak Ensembl API kullanılır (internet gerekir).",
    "gp.pick": "Seç",
    "license.summary": "Lisans ve sorumluluk bildirimi",

    // --- favoriler (2026-11-14) ---
    "fav.open": "★ Favoriler",
    "fav.open.title": "Kaydettiğiniz primer çiftleri (yalnızca bu bilgisayarda)",
    "fav.title": "Favoriler",
    "fav.add": "☆ Favorilere ekle",
    "fav.add.title": "Bu çifti Favoriler listesine kaydeder (yalnızca bu bilgisayarda)",
    "fav.in": "★ Favorilerde",
    "fav.in.title": "Favorilerden çıkarmak için tıklayın",
    "fav.note.label": "Not (isteğe bağlı)",
    "fav.note.ph": "örn. hangi çalışma için, sipariş tarihi",
    "fav.note.privacy": "Hasta adı ya da kimliği yazmayın. Favoriler yalnızca bu bilgisayarda saklanır.",
    "fav.save": "Kaydet",
    "fav.cancel": "Vazgeç",
    "fav.remove.q": "Bu çift favorilerden çıkarılsın mı? Notu da silinir.",
    "fav.remove": "Çıkar",
    "fav.search": "Gen, konum, primer dizisi ya da notta ara",
    "fav.csv": "Listeyi CSV indir",
    "fav.count": (n) => `${n} kayıt · yalnızca bu bilgisayarda saklanır`,
    "fav.countFiltered": (n, m) => `${m} kayıttan ${n} tanesi gösteriliyor · yalnızca bu bilgisayarda saklanır`,
    "fav.empty": "Henüz favori yok. Bir çift kartındaki <b>☆ Favorilere ekle</b> düğmesiyle ekleyin.",
    "fav.noMatch": "Aramaya uyan kayıt yok.",
    "fav.toEval": "Değerlendir'de aç",
    "fav.toEval.title": "Çifti Değerlendir sekmesinde, kaydedildiği referans genomla yeniden değerlendirir",
    "fav.editNote": "Notu düzenle",
    "fav.delete": "Sil",
    "fav.delete.q": "Bu kayıt silinsin mi? Geri alınamaz.",
    "fav.noNote": "Not yok",
    "fav.noteLabel": "Not",
    "fav.controlWith": (ad) => `Kontrol primeri ${ad} primerle bant verir`,
    "fav.saved": "Favorilere eklendi.",
    "fav.already": "Bu çift zaten favorilerde.",
    "fav.err.gecersiz": "Kayıt okunamadı; favorilere eklenmedi.",
    "fav.err.yazilamadi": "Favoriler dosyası yazılamadı (klasör salt okunur olabilir); değişiklik kaydedilmedi.",
    "fav.err.okunamadi": "Favoriler dosyası okunamadı; değişiklik kaydedilmedi.",
    "fav.err.bozuk": "Favoriler dosyası bozuk, okunamadı. Yeni bir çift eklediğinizde bozuk dosya silinmez, yanına yedek adıyla taşınır.",
    "fav.err.sinir": "Favori sınırına ulaşıldı; eski kayıtlardan bazılarını silin.",
    "fav.err.yok": "Kayıt bulunamadı (silinmiş olabilir).",
    "fav.backup": (yol) => `Bozuk favoriler dosyası silinmedi, şu adla saklandı: ${yol}`,
    "fav.kind.dna": "DNA",
    "fav.kind.cdna": "RNA · varyant",
    "fav.kind.atlama": "RNA · ekson atlama",
    "fav.kind.dizi": "Dizi",
    "fav.kind.dizi_cift": "Dizi · iki dizi",
    "fav.kind.kirilma.del": "Kırılma noktası · delesyon",
    "fav.kind.kirilma.dup": "Kırılma noktası · duplikasyon",
    "fav.kind.degerlendir_dna": "Değerlendir · DNA",
    "fav.kind.degerlendir_cdna": "Değerlendir · RNA",
    "fav.target": "hedef",
    "fav.margin": "belirsizlik",
    "csv.favNo": "Kayit",
    "csv.favDate": "Tarih",
    "csv.favKind": "Tur",
    "csv.favGene": "Gen",
    "csv.favInput": "Girdi",
    "csv.favProduct": "Urun",
    "csv.favTa": "Ta_onerisi_C",
    "csv.favNote": "Not",
    "csv.favVersion": "AllPrime_surumu",

    // --- ayarlar ekrani ---
    "set.open": "⚙ Ayarlar",
    "set.back": "← Tasarıma dön",
    "set.title": "Ayarlar",
    "set.view": "Görünüm",
    "set.theme": "Tema",
    "set.theme.help": "“Windows'a uy” seçilirse Windows'un açık / koyu ayarı izlenir.",
    "set.theme.dark": "Koyu",
    "set.theme.light": "Açık",
    "set.theme.system": "Windows'a uy",
    "set.zoom": "Arayüz boyutu",
    "set.zoom.help": "Yazılar, düğmeler ve tablolar birlikte büyür.",
    "set.lang": "Dil",
    "set.lang.help": "Üst çubuktaki TR / EN ile aynı.",
    "set.lab": "Laboratuvar varsayılanları",
    "set.lab.intro": "Program her açıldığında bu değerlerle başlar; değerler yalnızca bu " +
      "bilgisayarda saklanır. Tek bir tasarım için geçici değişikliği “Gelişmiş parametreler”den yapın.",
    "set.asm": "Açılıştaki referans genom",
    "set.asm.help": "Üst çubuktaki seçim yalnızca o oturum için geçerlidir.",
    "set.pcrMax.help": "Laboratuvarınızın PCR ile güvenle çoğaltabildiği en uzun ürün. Gelişmiş " +
      "parametrelerdeki alanla aynıdır; değiştirince hemen kaydedilir.",
    "set.params": "PCR koşulları ve primer parametreleri",
    "set.params.help": (n) => `Gelişmiş parametrelerdeki ${n} değer. Fabrika değerinden farklı kaydedilenler listelenir.`,
    "set.params.name": "Parametre",
    "set.params.saved": "Kayıtlı varsayılan",
    "set.params.factory": "Fabrika",
    "set.params.none": "Fabrika değerleri kullanılıyor (kayıtlı fark yok).",
    "set.params.save": "Gelişmiş parametrelerdeki değerleri varsayılan yap",
    "set.params.saveHere": "Bu değerleri laboratuvar varsayılanı yap",
    "set.params.where": "Kayıtlı değerler: ⚙ Ayarlar › Laboratuvar varsayılanları",
    "set.params.reset": "Fabrika değerlerine dön",
    "set.params.done": (n) => n ? `${n} değer laboratuvar varsayılanı olarak kaydedildi.`
      : "Tüm değerler fabrika değerinde; kayıtlı fark yok.",
    "set.params.resetDone": "Fabrika değerlerine dönüldü.",
    "set.params.fail": "Ayar kaydedilemedi.",
    "set.data": "Veri dosyaları ve genom",
    "set.about": "Hakkında",
    "about.version": "AllPrime sürümü",
    "about.engine": (v) => `motor ${v}`,
    "about.core": "Hesaplama çekirdeği",
    "about.core.bad": "primer3 yüklenemedi",
    "about.genome": (a) => `Referans genom ${a}`,
    "about.local": "yerel dosya",
    "about.api": "yok – Ensembl'e bağlanır",
    "about.annot": "Transkript tablosu (refGene)",
    "about.dbsnp": "Yaygın varyant indeksi (dbSNP)",
    "about.ready": "hazır",
    "about.missing": "yok",
    "about.sources": "Veri kaynakları",
    "about.sourcesText": "Ensembl (genom), UCSC (refGene, dbSNP b151 Common), NCBI (MANE)",

    // --- durum / mesajlar ---
    "msg.calculating": "Hesaplanıyor…",
    "act.cancel": "İptal",
    "msg.cancelled": "İptal edildi.",
    "msg.timeout": "Motor 5 dakikada cevap vermedi; istek durduruldu. Motor hâlâ çalışıyor olabilir — biraz bekleyip yeniden deneyin.",
    "msg.searching": "Aranıyor…",
    "msg.error": (e) => `Hata: ${e}`,
    "msg.noEngine": (e) => `Motor bağlantısı kurulamadı: ${e}`,
    "msg.genomeSet": (asm) => `${asm} genomu tanıtıldı.`,
    "err.needPos": "Genomik koordinat gerekli.",
    "err.needChromOrGene": "Kromozom veya gen adı gerekli.",
    "err.needAcc": "Transkript kodu (NM_) gerekli.",
    "err.needExon": "Ekson numarası gerekli.",
    "err.needCpos": "c. koordinatı gerekli (örn. c.1234).",
    "err.needSeq": "Dizi gerekli.",
    "err.needBothSeq": "Her iki dizi de gerekli.",
    "err.needGene": "Gen sembolü girin.",
    "status.genomeLocal": (asm) => `${asm}: yerel FASTA`,
    "status.genomeApi": (asm) => `${asm}: Ensembl API (internet)`,
    "status.rnaDisabled": (asm) =>
      `${asm} için transkript tablosu (refGene) bulunamadı ya da okunamıyor (dosya yarım/bozuk olabilir) — Veri dosyaları panelinden yeniden indirin.`,

    // --- kopyalama ---
    "copy.btn": "⧉ Kopyala",
    "copy.title": "Diziyi panoya kopyala",
    "copy.ok": "✓ Kopyalandı",
    "copy.fail": "✗ Olmadı",

    // --- transkript listesi ---
    "tx.meta": (ex, nt, coding) =>
      `${ex} ekson · ${nt} nt${coding ? "" : " · kodlamayan"}`,
    // hizalama isareti: kodlayan dizi tutarsiz transkript (K1)
    "rna.derleme.not": (asm) =>
      `RNA sekmesi transkripti her zaman ${asm} genomundan kurar (MANE Select ${asm} üzerinde tanımlıdır); gösterilen genomik konumlar ${asm} konumlarıdır.`,
    "kod.rozet": "Hizalama uyarısı",
    "kod.neden.mod3": "uzunluk 3'ün katı değil",
    "kod.neden.son_kodon": "son kodon durdurma değil",
    "kod.neden.erken_durdurma": "erken durdurma kodonu",
    "kod.kisa": (nedenler) =>
      `Genom hizalaması NM dizisiyle birebir olmayabilir (${nedenler}): c. ve ekson numaraları ` +
      "kayabilir; gerçek bir durdurma kodonu da olabilir. NM dizisiyle karşılaştırın ya da " +
      "DNA sekmesinde genomik koordinatla tasarlayın.",
    "region.kod": "Bu transkriptin hizalaması NM dizisiyle birebir olmayabilir: ekzon numarası NM'ninkinden farklı olabilir.",

    // --- sonuc ozeti ---
    "sum.genome": "Genom",
    "sum.position": "Konum",
    "sum.gene": "Gen",
    "sum.found": "Bulunan çift",
    "sum.srcLocal": "Yerel FASTA",
    "sum.srcApi": "Ensembl API",
    "sum.transcript": "Transkript",
    "sum.exonCount": (n) => `${n} ekson`,
    "sum.strand": (s) => `${s} iplik`,
    // F/R adlari genin okuma yonunde (yon.js)
    "yon.eksi": (g) => `${g} eksi (−) iplikte: primer adları ve ürün dizisi genin okuma yönündedir. ` +
      "Forward ile yapılan Sanger okuması c. dizisiyle aynı yönde, Reverse ile yapılan okuma ters tümleyendir. " +
      "Pozisyonlar genomik (+) koordinattır.",
    "yon.belirsiz": "Ürün zıt yönlü genlerle örtüşüyor: F/R adları genomun + ipliğine göredir.",
    "amp.geneDir": (g) => `${g} (− iplik) gen yönünde, ters tümleyen`,
    "sum.variant": "Varyant",
    "sum.exon": "ekson",
    "sum.target": "Hedef",
    "sum.versionless": "sürümsüz eşleşti",
    "sum.noTarget": "Hedef yok",
    "sum.noTarget.title": "Hedef verilmedi; primerler dizinin tamamından seçildi.",
    "sum.seqLen": "Dizi",
    "sum.fwdRegion": "Forward bölgesi",
    "sum.revRegion": "Reverse bölgesi",
    "sum.gap": "Aradaki mesafe",
    "sum.gap.title": "0 ise diziler bitişik kabul edildi (füzyon / kırılma noktası).",
    "sum.gapUnknown": "mesafe bilinmiyor",
    "sum.gapUnknown.title": "Ürün boyu kısıtı uygulanmadı; primerler dizilerin tamamından seçildi.",

    // --- cift kartlari ---
    "chip.amplicon": "Amplikon",
    "tm.cond": (mv, mg, dntp, dna, dmso) =>
      `${mv} mM K⁺/Na⁺, ${mg} mM Mg²⁺, ${dntp} mM dNTP, ${dna} nM primer` + (dmso ? `, %${dmso} DMSO` : ""),
    "tm.note": (kosul) => `Tm: en yakın komşu yöntemi (SantaLucia 1998), ${kosul}.`,
    "tm.why": "Başka bir araçtaki Tm neden farklı olabilir?",
    "tm.whyText":
      `Tm, hesaplama yöntemine ve koşullara göre araçtan araca değişir. Örneğin yalnızca uzunluk ve ` +
      `G+C sayısından hesaplanan "Basic" Tm tuz ve Mg²⁺'u hesaba katmaz, bu yüzden genellikle birkaç ` +
      `derece düşük çıkar. Değerleri karşılaştırırken hangi yöntem ve koşullarla hesaplandığına bakın; ` +
      `buradaki koşulları Gelişmiş parametrelerden değiştirebilirsiniz.`,
    "chip.ta": "Ta önerisi",
    "chip.ta.title": "Bağlanma sıcaklığı için başlangıç noktası: düşük Tm'li primerin Tm'i − 5 °C (Taq). Tm, gelişmiş ayarlardaki tuz, primer ve DMSO koşullarıyla hesaplanır. Kesin değeri gradyan PCR ile bulun; polimeraz üreticisinin önerisi farklı olabilir.",
    "chip.gc": "GC",
    "fmt.pct": (v) => `%${v}`,
    "chip.gc.title":
      "Çoğaltılan bölgenin GC yüzdesi. %65 ve üzeri GC'ce zengin sayılır (GC tamponu / " +
      "%3-5 DMSO / ~1 M betain düşünün), %75 ve üzerinde katkı neredeyse şarttır; " +
      "%30 ve altı AT'ce zengindir. Kaynak: Thermo Phusion kılavuzu, PLOS One 2016.",
    "chip.position": "Konum",
    "igv.copy": "IGV için kopyala",
    "igv.copy.title": (asm, hg) => `Primerlerin kapsadığı aralığı IGV ya da UCSC arama kutusuna yapıştırılacak biçimde kopyalar (chr7:117559410-117559715). IGV'de ${asm} (${hg}) genomu açık olmalı.`,
    "chip.dTm": "ΔTm",
    "chip.selfMax": "Self-komp. (en yüksek)",
    "chip.selfMax.title": "Primerin kendine tamamlayıcılığı: iki kopyasının birbirine yapışma eğilimi (iki primerden yüksek olanı gösterilir). Düşük = iyi; 8'in üstü sorunlu.",
    "chip.self3p": "3' self-komp.",
    "chip.self3p.title": "3' ucun kendine ya da diğer primere yapışma eğilimi. 3' uç tutunursa polimeraz uzatır ve primer-dimer oluşur — en tehlikeli türü. Düşük = iyi; tasarım 3'ün üstünü eler.",
    "chip.dimer": "Dimer skoru",
    "chip.dimer.title": "İki primerin birbirine tamamlayıcılığı (heterodimer): birbirlerine yapışma eğilimi. Düşük = iyi; tasarım 8'in üstünü eler.",
    "chip.snp": "Yaygın varyant",
    "chip.snp.title3p": "Varyantlardan en az biri 3' uca 5 baz veya daha yakın — allel dropout riski yüksek.",
    "chip.snp.title": "Varyantlar 3' uçtan uzakta; risk daha düşük ama not edin.",
    "chip.cdnaProduct": "cDNA ürün",
    "chip.gdna": "gDNA",
    "chip.gdna.title": "Aynı primerler genomik DNA üzerinde bu boyutta ürün verir — jelde ayırt etmek için.",
    "chip.gdna.titleSkip": "Genomik DNA üzerinde beklenen ürün — intronları da kapsar.",
    "chip.junctions": "Kapsanan sınır",
    "chip.junctions.title": "Ürün bu kadar ekson sınırını kapsıyor.",
    "chip.noJunction": "Sınır kapsamıyor",
    "chip.noJunction.title": "Ürün hiçbir ekson sınırını kapsamıyor — gDNA'dan ayırt edilemez.",
    "chip.exons": "Eksonlar",
    "chip.normal": "Normal",
    "chip.normal.title": "Ekson yerindeyse görülecek bant.",
    "chip.skipped": "Atlanmış",
    "chip.skipped.title": "Ekson atlanmışsa görülecek bant.",
    "chip.diff": "Fark",
    "chip.diff.title": "İki bant arasındaki fark. Küçükse jelde ayırt etmek zorlaşır.",
    "chip.assumeContig": "(bitişik varsayımıyla)",
    "chip.assumeContig.title": "İki dizinin gerçek mesafesi bilinmediği için bu sayı yalnızca dizileri bitişik varsayarsak geçerlidir.",

    // --- tablo basliklari ---
    "th.dir": "Yön",
    "th.seq": "Dizi (5'→3')",
    "th.nt": "nt",
    "th.tm": "Tm",
    "th.gc": "GC%",
    "region.exon": (n) => `ekzon\u00a0${n}`,
    "region.intron": (n) => `intron\u00a0${n}`,
    "region.exonRange": (a, b) => `ekzon\u00a0${a}–${b} arası`,
    "region.boundary": (e, i) => `ekzon\u00a0${e} / intron\u00a0${i} sınırı`,
    "region.boundaryEnd": (e, uc) => `ekzon\u00a0${e} / ${uc} sınırı`,
    "region.side.bas": "gen başı",
    "region.side.son": "gen sonu",
    "th.region": "Gen bölgesi",
    "th.region.title":
      "Primerin genin neresine oturdugu: ekzon 7, intron 7 ya da ikisinin sınırı. " +
      "Ekzon numarası transkripte göre değişir; hücrenin üzerine gelince hangi " +
      "transkriptin esas alındığı yazar (varsa MANE Select).",
    "th.region.cell": (gen, acc, mane, sayi) =>
      `${gen} ${acc}${mane} · ${sayi} ekzon — numaralandırma bu transkripte göre`,
    "th.region.none": "Bu konum tablodaki hiçbir genin içinde değil (genler arası) ya da bu genom için transkript tablosu yüklü değil.",
    "th.pos": "Pozisyon",
    "th.exon": "Ekson",
    "th.cdnaPos": "cDNA konumu",
    "th.cdnaPos.title": "Transkript üzerindeki konum (nt)",
    "th.regionPos": "Bölge içindeki konum",
    "th.hairpin": "Hairpin °C",
    "th.hairpin.title": "Hairpin erime sıcaklığı (termodinamik, °C)",
    "th.self": "Self-komp.",
    "th.self.title": "Primerin kendine tamamlayıcılığı: iki kopyasının birbirine yapışma eğilimi. Düşük = iyi; 8'in üstü sorunlu.",
    "th.self3": "3' Self-komp.",
    "th.self3.title": "Primerin 3' ucunun kendine tamamlayıcılığı: 3' uçtan yapışırsa uzayıp primer-dimer verir. Düşük = iyi; 3'ün üstü riskli.",
    "th.snp": "SNP",
    "th.snp.title": "Primerin üzerine denk gelen yaygın varyant (dbSNP) sayısı. Üzerine gelin: rs numarası, MAF ve 3' uca uzaklık.",
    "dir.forward": "Forward",
    "dir.reverse": "Reverse",
    "flag.junction": "sınır",
    "flag.junction.title": "Bu primer ekson sınırının üzerine oturuyor — gDNA'ya bağlanmaz.",
    "snpCell.title": (rs, maf, indel, d) =>
      `${rs} · MAF ${maf}${indel ? " · indel" : ""} · 3' ucundan ${d} baz`,
    "seq.region1": "1. dizi",
    "seq.region2": "2. dizi",

    // --- sonuc yok ---
    "res.none": "Uygun primer çifti bulunamadı. Parametreleri gevşetmeyi deneyin.",

    // --- ozgulluk ---
    "spec.btn": "⌕ Özgüllüğü kontrol et",
    "spec.note": "genom taraması · birkaç saniye",
    "spec.scanning": "Taranıyor…",
    "spec.ok": "Özgül görünüyor",
    "spec.high": (n) => `${n} yüksek riskli yan ürün`,
    "spec.mid": (n) => `${n} orta riskli yan ürün`,
    "spec.targetFound": "Hedef bölge bulundu",
    "spec.targetCdna": "Hedef bölge genomda bitişik değil (beklenen)",
    "spec.targetCdna.title": "cDNA modunda beklenen: ürün intron kapsadığı için genomda bitişik değil.",
    "spec.targetMissing": "Hedef bölge bulunamadı",
    "spec.targetMissing.title": "Tasarlanan ürün genom taramasında görünmedi.",
    "spec.seqMode": "Serbest dizi · hedef ayrımı yok",
    "spec.seqMode.title": "Verilen dizinin genomdaki yeri bilinmediği için hedef ayrımı yapılamaz; aşağıdaki liste genomdaki TÜM olası ürünlerdir.",
    "spec.sites": "Bağlanma bölgesi",
    "spec.sites.title": (mm) => `Genomda primerin uzayabileceği bölge sayısı. Parantez içi: en fazla ${mm} uyumsuzlukla oturanlar.`,
    "spec.riskCounts": "Risk",
    "spec.riskSummary": (h, m, l) => `${h} yüksek · ${m} orta · ${l} düşük`,
    "spec.th.risk": "Risk",
    "spec.th.combo": "Kombinasyon",
    "spec.th.combo.title": "Hangi primer çifti bu ürünü veriyor",
    "spec.th.loc": "Konum",
    "spec.th.product": "Ürün",
    "spec.th.mismatch": "Uyumsuz",
    "spec.th.mismatch.title": "Her primerin kendi bağlanma bölgesindeki uyumsuz baz sayısı — soldaki ile sağdaki, iki AYRI primerdir (5'/3' değil). Hangisi olduğu başındaki harfle yazılıdır. 3' uçtaki son 8 baz zaten tam eşleşiyor, uyumsuzluklar 5' tarafındadır.",
    "spec.clean": "Kayda değer yan ürün bulunamadı.",
    "spec.truncated": (n, tot) => `Listede ilk ${n} kayıt gösteriliyor (toplam ${tot}).`,
    "spec.lowHidden": (n) => `${n} adet bağlanma olasılığı düşük bölge listelenmedi `
      + `(iki primerde toplam 6+ uyumsuzluk).`,
    "risk.yuksek": "yüksek",
    "risk.orta": "orta",
    "risk.dusuk": "düşük",
    "risk.hedef": "hedef",
    "ev.showLow": (n) => `Bağlanma olasılığı düşük ${n} ürünü göster`,
    "ev.hideLow": "Düşük olasılıklıları gizle",
    // --- motor surum uyusmazligi ---
    "err.oldEngine":
      "Motor bu isteği tanımıyor (HTTP 404). Arayüz yeni, motor eski görünüyor — " +
      "resources\\backend klasörünü güncel sürümle değiştirin.",
    "err.notJson": (kod) => `Motordan beklenmeyen bir cevap geldi (HTTP ${kod}).`,
    "engine.mismatch": "Motor ile arayüz uyuşmuyor.",
    "engine.p3": "Hesaplama motoru çalışmıyor.",
    "genome.warn.blocked": (a) => `${a} genomu kullanılamıyor.`,
    "genome.warn.note": (a) => `${a} genomu için uyarı.`,
    "about.blocked": "dosya var ama kullanılamıyor",
    "engine.old":
      "Motor sürümünü bildirmiyor (13 Eylül 2026 öncesi bir derleme). Çalışıyor " +
      "olabilir ama hangi özellikleri desteklediği doğrulanamıyor; güncel motorla " +
      "değiştirmeniz önerilir.",
    "engine.missing": (u) => `Motor şu işlevleri tanımıyor: ${u}.`,
    "engine.versionDiff": (m, a) => `Motor sürümü ${m}, arayüz sürümü ${a}.`,
    "engine.fix":
      "Bu genellikle klasör kopyalanırken motorun eski kalmasıyla olur. Uygulamayı " +
      "kapatıp resources\\backend klasörünü güncel sürümdeki ile değiştirin.",
    "ev.handoff": "Değerlendir",
    "ev.handoff.title":
      "Bu çifti Değerlendir sekmesinde açar. Diziler, varyant konumu ve (cDNA modunda) " +
      "transkript kodu otomatik doldurulur; tasarım sonuçlarınız kaybolmaz.",
    "ev.lowExplain":
      "Bu bölgelerde iki primerde toplam 6 veya daha fazla uyumsuzluk var. " +
      "Bu boyda bir primerde pratikte bant vermezler, ama beklenmedik bir ürün " +
      "araştırıyorsanız buradan bakabilirsiniz.",
    "ev.lowTruncated": (n, tot) => `İlk ${n} tanesi gösteriliyor (toplam ${tot}).`,
    // "kopyadan yalnizca 1-2 baz farki" notu (evaluate._yakin_kopya)
    "ev.yakin.title": (n) => (n === 1 ? "Kopyadan yalnızca tek baz farkı var — temkinli olun"
      : `Kopyadan yalnızca ${n} baz farkı var — temkinli olun`),
    "ev.yakin.yer": (u) => (u === 1 ? "3' son bazında" : `3' uçtan ${u}. bazında`),
    "ev.yakin.cift": (pb, kb) => `primerin ${({ A: "A'sı", C: "C'si", G: "G'si", T: "T'si" })[pb] || pb} karşısında ${kb}`,
    "ev.yakin.primer": (p, f) => (!f.length ? `${p} kopyaya birebir oturuyor`
      : f.length === 1 ? `${p} yalnız ${f[0][0]} farklı (${f[0][1]})`
      : `${p} ${f.map(([y, c]) => `${y} (${c})`).join(" ve ")} farklı`),
    "ev.yakin.text": (yer, konum, bp, kombi, parca, n, adet) =>
      `${yer} bölgesinde (${konum ? konum + ", " : ""}${bp} bp${kombi === "F+R" || kombi === "R+F" ? "" : ", " + kombi}) ` +
      `bu çiftten ürün oluşabilir: ${parca}. Tarama 3' ucu tutmayan primeri uzamaz saydığı için bu ürün ` +
      `yukarıdaki listede yok. ${n === 1 ? "Tek bazlık fark zayıf bir ayrımdır" : "Bu kadar az fark zayıf bir ayrım olabilir"}; ` +
      "kopya da çoğalabilir. Düzeltme yapmayan Taq kullanın ve ürünü Sanger ile okuyup hangi kopyadan " +
      `geldiğini kontrol edin.${adet > 1 ? ` Bu türden ${adet} yer var; en az farklı olanı yazıldı.` : ""}`,

    // --- kirilma noktasi sekmesi ---
    "tab.bp": "Kırılma noktası",
    "bp.intro": "Delesyon ya da duplikasyonun sınırlarını girin; araç kırılma noktasını çoğaltan primerleri tasarlar. Başlangıç ve bitiş, silinen / kopyalanan bölgenin ilk ve son bazıdır. 'chr2:50,000,001-50,012,000' biçimindeki bir konumu başlangıç kutusuna yapıştırırsanız kutular kendiliğinden dolar.",
    "bp.mode.del": "Delesyon",
    "bp.mode.dup": "Duplikasyon",
    "bp.start": "Başlangıç",
    "bp.start.ph": "örn. 50000001",
    "bp.start.help": "chr:başlangıç-bitiş yapıştırılabilir.",
    "bp.end": "Bitiş",
    "bp.end.ph": "örn. 50012000",
    "bp.margin": "Kırılma noktası belirsizliği (± bp)",
    "bp.margin.help": "Sınırlar dizilemeyle baz düzeyinde biliniyorsa 0. MLPA, array ya da ekzom gibi yaklaşık sonuçlarda her iki uç için olası kayma: primerler olası tüm kırılma noktalarının güvenli tarafına konur, bant boyu aralık olarak verilir.",
    "bp.control.label": "Kontrol primeri ekle (3. primer)",
    "bp.control.help": "Delesyonda silinen bölgenin içine normal alel primeri konur: tek jelde normal / heterozigot / homozigot ayrılır. Büyük duplikasyonda bölgenin dışına bir kontrol primeri konur: normal örnekte de bant çıkar, PCR'ın çalıştığı görülür. Kontrol bandı kırılma bandından en az 100 bp farklı seçilir.",
    "bp.help.del": "Delesyon: primerler silinen bölgenin iki yanına konur. Delesyonlu alelde yan yana gelip kısa bir kırılma noktası ürünü verirler; kırılma noktası ürünün içindedir ve Sanger ile okunabilir. Primerler kırılma noktasına en az 100 bp uzak tutulur.",
    "bp.help.dup": "Duplikasyon (tandem): primerler kopyalanan bölgenin içine, uçlara yakın ve dışa bakacak şekilde konur; yalnızca iki kopyanın birleşim yerinden ürün verirler, ürün boyu duplikasyonun büyüklüğünden bağımsızdır. Ters yönlü ya da genomun başka bir yerine eklenmiş kopyayı yakalamaz: negatif sonuç duplikasyonu dışlamaz. 1,5 kb'tan küçük duplikasyonlarda dış primerlerle boy farkı kullanılır.",
    "bp.approach.gap_pcr": "Gap-PCR (kırılma noktası)",
    "bp.approach.tandem_junction": "Tandem bağlantı (dışa bakan primerler)",
    "bp.approach.size_shift": "Boy farkı (dış primerler)",
    "sum.region": "Bölge",
    "sum.type": "Tip",
    "sum.approach": "Yaklaşım",
    "sum.margin": "Belirsizlik",
    "bp.chip.mut": "Kırılma bandı",
    "bp.chip.mut.title": "Delesyonlu alelden çıkan ürün; kırılma noktası ürünün içinde.",
    "bp.chip.wt": "Normal alel",
    "bp.chip.wt.title": "Normal alelden beklenen ürün: iki primerin arası delesyon bölgesini de kapsar. 'Sınırınız', gelişmiş parametrelerdeki 'çoğaltılabilen en uzun ürün' ayarıdır — mutlak bir sınır değil, sizin protokolünüz. Daha uzun ürün çoğaltan bir protokolde sınırın üstündeki bantlar da görülebilir.",
    "bp.wt.var": "sınırınızın içinde",
    "bp.wt.zayif": "sınırınızın üstünde",
    "bp.wt.yok": "sınırınızın çok üstünde",
    "bp.chip.junction": "Bağlantı bandı",
    "bp.chip.junction.title": "Yalnızca tandem duplikasyonlu alelde, iki kopyanın birleşim yerinden çıkan ürün.",
    "bp.chip.noWt": "Normal genomda ürün yok",
    "bp.chip.noWt.title": "Primerler referans genomda birbirinden uzağa bakar; normal alelden ürün çıkmaz.",
    "bp.chip.wtShort": "Normal alel",
    "bp.chip.dupBand": "Duplike alel",
    "bp.chip.control": "Kontrol bandı",
    "bp.chip.control.title": (ad) => `Kontrol primeri ile ${ad} primerin verdiği bant (normal alel / PCR kontrolü).`,
    "bp.dir.control": "Kontrol",
    "bp.th.genotype": "Genotip",
    "bp.th.bands": "Beklenen bantlar",
    "bp.gt.normal": "Normal",
    "bp.gt.het": "Heterozigot delesyon",
    "bp.gt.homDel": "Homozigot delesyon",
    "bp.gt.dup": "Duplikasyon (heterozigot / homozigot)",
    "bp.gt.hetDup": "Heterozigot duplikasyon",
    "bp.gt.homDup": "Homozigot duplikasyon",
    "bp.noBand": "bant yok",
    "bp.controlMissing": (neden) => `Kontrol primeri eklenemedi: ${neden}.`,
    "bp.controlDimer": (s, ad) => `UYARI: Kontrol primeri diğer ${ad} primerle 3' ucundan dimer kurabilir (3' dimer skoru ${s}); üç primer aynı tüpte kullanılacaksa başka bir çift deneyin.`,
    "bp.controlSpecHint": (ad) => `Özgüllük taraması forward ve reverse primeri tarar. Kontrol primerinin genomdaki bağlanmasını görmek için Değerlendir sekmesinde ${ad} + kontrol primerini birlikte değerlendirin; normal referansta sıradan bir ürün verdikleri için sonuç doğrudan okunur.`,
    "spec.bpNoRef": "Kırılma ürünü referansta yok (beklenen)",
    "spec.bpWtFound": "Normal alel ürünü bulundu",
    "spec.bpNoRef.title": "Kırılma noktası ürünü delesyonlu / duplike alele özgüdür, referans genomda bulunmaz. Aşağıdaki liste referanstaki diğer olası ürünlerdir.",
    "err.needBp": "Kromozom, başlangıç ve bitiş gerekli.",
    "csv.bpMain": "AnaBant_bp",
    "csv.bpSecond": "IkinciBant_bp",
    "csv.bpControl": "KontrolBandi_bp",

    // --- CSV basliklari (Excel uyumu icin sade karakterler) ---
    // --- degerlendirme sekmesi ---
    "tab.eval": "Değerlendir",
    "ev.intro":
      "Elinizdeki bir primer çiftini inceler — tasarlamaz. Genomda nereye oturduğunu, " +
      "ne ürün vereceğini ve <b>vermiyorsa nedenini</b> söyler.",
    "ev.fwd": "Forward primer (5'→3')",
    "ev.rev": "Reverse primer (5'→3')",
    "ev.rev.help": "Boş bırakırsanız yalnızca forward primer değerlendirilir.",
    "ev.target": "Varyant konumu (isteğe bağlı)",
    "ev.target.ph": "örn. chr19:11537002 · RNA modunda c.215",
    "ev.target.help": "Verirseniz ürün dizisinde bu konum işaretlenir. Kartın Değerlendir düğmesiyle gelince kendiliğinden dolar.",
    "ev.run": "Değerlendir",
    "ev.running": "İnceleniyor…",
    "ev.verdict.iyi": "Sorun görünmüyor",
    "ev.verdict.uyari": "Dikkat edilmesi gerekenler var",
    "ev.verdict.sorun": "Ciddi sorun var",
    "ev.props": "Primer özellikleri",
    "ev.sites": "Genomdaki bağlanma bölgeleri",
    "ev.products": "Öngörülen ürünler",
    "ev.findings": "Bulgular",
    "ev.noProduct": "Bu çift hiçbir ürün vermiyor.",
    "ev.overflow": "Ürün tahmini yapılmadı: primerler bir tekrar dizisinde, olası ürünler sayılamayacak kadar çok. Ayrıntı aşağıdaki bulgularda.",
    "ev.noGenome": "Yerel genom tanıtılmadığı için genom analizi yapılamadı.",
    "ev.level.sorun": "sorun",
    "ev.level.uyari": "uyarı",
    "ev.level.bilgi": "bilgi",
    // --- degerlendirme: RNA / cDNA modu ---
    "ev.mode.label": "Primer tipi",
    "ev.mode.dna": "DNA (genomik)",
    "ev.mode.cdna": "RNA / cDNA",
    "ev.mode.help":
      "cDNA primerleri ekson sınırına oturabilir; böyle bir primer genomda bütün " +
      "hâlde bulunmaz, o yüzden DNA modu onlara yanlış alarm verir.",
    "ev.acc": "Transkript (NM_)",
    "ev.acc.find": "Gen ile bul",
    "ev.acc.help": "NM_ kodu yazın ya da gen sembolü yazıp \"Gen ile bul\"a basın.",
    "ev.err.needAcc": "RNA modunda transkript kodu (NM_) gerekli.",
    "ev.cdna.placement": "Transkript üzerindeki yerleşim",
    "ev.cdna.th.pos": "cDNA konumu",
    "ev.cdna.th.exon": "Ekson",
    "ev.cdna.th.exon.title": "Primerin oturduğu ekson(lar). İki numara varsa primer sınırın üzerindedir.",
    "ev.cdna.th.junction": "Ekson sınırı",
    "ev.cdna.th.junction.title":
      "Primer ekson sınırının üzerine oturuyorsa sınırın iki yanında kalan baz sayısı. " +
      "Böyle bir primer genomik DNA'ya bağlanamaz.",
    "ev.cdna.junction": (a, b) => `${a}+${b} baz`,
    "ev.cdna.notFound": "Bu transkriptte bulunamadı",
    "ev.cdna.product": "Öngörülen ürün",
    "ev.cdna.cdnaBand": "cDNA bandı",
    "ev.cdna.gdnaBand": "gDNA bandı",
    "ev.cdna.gdnaBand.title":
      "Aynı primerler genomik DNA üzerinde ne verirdi? Kontaminasyonu ayırt " +
      "edebilmek için bu bandın cDNA bandından farklı olması gerekir.",
    "ev.cdna.junctions": "Kapsanan ekson sınırı",
    // --- amplikon (cogaltilan dizi) ---
    "amp.btn": "Ürün dizisi",
    "amp.btn.hide": "Diziyi gizle",
    "amp.th": "Dizi",
    "amp.title": (n) => `Çoğaltılan dizi — ${n} bp`,
    "amp.fwd": "Forward primer",
    "amp.rev": "Reverse primer (ters tümleyeni)",
    "amp.fwd.rc": "Forward primer (ters tümleyeni)",
    "amp.rev.self": "Reverse primer",
    "amp.fromF": "Ters tümleyen: dizi F primerinden başlar",
    "amp.target": (ad, a, b) => `${ad} (ürünün ${a === b ? `${a}. bazı` : `${a}–${b}. bazları`})`,
    "amp.target.bp": "Kırılma noktasının iki yanı",
    "amp.target.region": "Girilen bölge",
    "amp.target.seq": "Hedef",
    "kopya.title": "Kopyadan ayrışan çiftler",
    "eniyi.title": "En iyi Özgül çift",
    "eniyi.sirada": "Rozetler bitince kurallara uyan bütün adaylar taranacak.",
    "eniyi.araniyor": "Kurallara uyan bütün adaylar genomda taranıyor…",
    "eniyi.taranan": (n) => `taranan ${n} aday`,
    "eniyi.neden": (y, o) => `1. çift Özgül değil: 3 kb içinde ${[y && `${y} yüksek`, o && `${o} orta`].filter(Boolean).join(", ")} riskli yan ürün. `,
    "eniyi.ilk10.title": (k) => `En iyi Özgül çift: listede ${k}. sırada`,
    "eniyi.ilk10.hint": (k, f) => `Kurallara uyan bütün adaylar genomda tarandı; Özgül çiftlerin en iyisi listedeki ${k}. çift (1. çifte göre: ${f}). Normal liste değişmedi.`,
    "eniyi.git": (k) => `${k}. çifte git`,
    "eniyi.disari.hint": "Kurallara uyan bütün adaylar genomda tarandı; Özgül çiftlerin en iyisi aşağıda. Normal liste değişmedi.",
    "eniyi.k2.title": "Daha iyi bir Özgül çift var",
    "eniyi.k2.hint": (f, n) => `1. çift Özgül. Kurallara uyan bütün adaylar tarandığında aynı kurallarla skoru daha iyi bir Özgül çift çıktı (${f}). Liste primer3'ün ilk ${n} adayından seçildiği için bu çift listede yok. Normal liste değişmedi.`,
    "eniyi.k2.bir": (n) => `1. çift Özgül; liste primer3'ün ilk ${n} adayından seçildiği için skoru daha iyi Özgül çiftler listede yok. `,
    "eniyi.paralog.chip": (n, m) => `ilk ${n} Özgül çift · taranan ${m} aday`,
    "eniyi.paralog.hint": (neden, m, n) => `Bu gende yakın kopya var. ${neden}Kurallara uyan ${m} adayın hepsi genomda tarandı; Özgül çiftlerden ilk ${n} tanesi aşağıda, en iyisi en üstte. Normal liste değişmedi. Kopyadan fark, çifti kopyadan ayıran bazın primerin 3' ucuna uzaklığıdır; uca yakın fark daha güçlü ayırır.`,
    "eniyi.yok.title": "Özgül çift bulunamadı",
    "eniyi.yok.hint": (m, paralog) => `Kurallara uyan ${m} adayın hepsi genomda tarandı; hiçbiri Özgül değil. En az riskli çiftler aşağıda (önce en az yüksek, sonra en az orta riskli yan ürün).${paralog ? " Bu bölgede gen ile kopya çok benzer. Bir çift kullanacaksanız ürünü Sanger ile okuyup hangi kopyadan geldiğini ayırt edici bazlardan kontrol edin." : " Bir çift kullanacaksanız yan ürünlerini Değerlendir sekmesinde inceleyin."}`,
    "eniyi.th.fark": "1. çifte göre",
    "eniyi.th.yan": "Yan ürün (3 kb)",
    "eniyi.yan": (y, o) => `${y} yüksek / ${o} orta`,
    "eniyi.havuz_disi": "havuz dışı",
    "eniyi.havuz_disi.title": (n) => `Liste primer3'ün ilk ${n} adayından seçiliyor; bu çift onların dışında.`,
    "eniyi.fark.ceza": (x) => `boy sapması ${x} nt`,
    "eniyi.fark.dimer": (x) => `dimer ${x}`,
    "eniyi.fark.boy": (n, kisa) => `ürün ${n} bp ${kisa ? "kısa" : "uzun"}`,
    "eniyi.fark.ayni": "aynı",
    "kopya.dugme": "Bu gende yakın kopya var. Aday havuzunda kopyadan ürün vermeyen çift aranabilir.",
    "kopya.ara": "Kopyadan ayrışan çift ara",
    "kopya.hepsi": (n) => `Tümünü göster (${n})`,
    "kopya.th.sira": "Havuz sırası",
    "kopya.th.f": "Forward (5'→3')",
    "kopya.th.r": "Reverse (5'→3')",
    "kopya.th.urun": "Ürün",
    "kopya.th.fark": "Kopyadan fark",
    "kopya.fark.son": (p) => `${p}: 3' son baz`,
    "kopya.fark.uc": (p, k) => `${p}: 3' uçtan ${k}. baz`,
    "kopya.fark.toplam": (n) => ` · ${n} fark`,
    "kopya.fark.cok": "Çok farklı",
    "kopya.fark.cok.title": "Kopya bölgelerinde, 3' uç kuralı olmadan da en çok 5 uyumsuzlukla ürün verecek bağlanma yok.",
    "kopya.fark.title": (c, s, n) => `Kopyada en az farkla oluşabilecek ürün: chr${c}:${s}, ${n} bp. Fark 3' uca ne kadar yakınsa ayrışma o kadar güçlüdür.`,
    "amp.junction": "Ekson sınırı",
    "amp.breakpoint": "Kırılma noktası",
    "amp.unknown": (n) => `Bilinmeyen ara bölge (${n} bp, N ile gösterildi)`,
    "amp.copy": "Kopyala",
    "amp.copyFasta": "FASTA",
    "amp.copyFasta.title": "Başlık satırıyla birlikte FASTA olarak kopyalar.",
    "ev.th.len": "nt",
    "ev.th.clamp": "GC clamp",
    "ev.th.poly": "Homopolimer",
    "ev.th.self3": "3' self",
    "ev.th.self3.title": "Primerin 3' ucunun kendine tamamlayıcılığı: 3' uçtan yapışırsa uzayıp primer-dimer verir. Tasarım 3'ün üstünü eler; Değerlendir 3'ün üstünde bilgi, 6 ve üstünde uyarı verir.",
    "ev.hetero3": "3' dimer skoru",
    "ev.hetero3.title": "İki primerin 3' uçlarının birbirine tamamlayıcılığı: uçlar birbirine tutunursa birbirleri üzerinde uzayıp primer-dimer oluşturur. Tasarım 3'ün üstünü eler; Değerlendir 3'ün üstünde bilgi, 6 ve üstünde uyarı verir.",
    "ev.th.site": "Konum",
    "ev.th.orient": "Yön",
    "ev.th.mm": "Uyumsuz",
    "ev.th.where": "Bölge",
    "ev.region.exon": (n) => `ekzon ${n}`,
    "ev.region.intron": "intron",
    "ev.siteCount": (perfect, good, total) =>
      `${perfect} tam eşleşme · ${good} iyi · ${total} toplam`,
    "ev.dTm": "ΔTm",
    "ev.heteroTm": "Dimer Tm",
    "ev.heteroTm.title": "İki primerin birbirine bağlanmasının termodinamik erime sıcaklığı (primer3). 45 °C ve üstü uyarı verir.",

    // --- veri dosyasi indirme ---
    "dl.summary": "Veri dosyaları (indirme)",
    "dl.intro":
      "Genom ve varyant dosyaları uygulamayla birlikte gelmez; buradan kaynağından " +
      "indirilir. İndirme <b>kaldığı yerden devam eder</b>, bağlantı koparsa baştan " +
      "başlamaz. Aynı anda tek dosya iner — yavaş bağlantıda paralel indirme toplam " +
      "süreyi kısaltmaz. Dosyalar elinizde varsa indirmek yerine " +
      "“Genom dosyaları” bölümünden doğrudan gösterebilirsiniz.",
    "dl.root": "Konum",
    "dl.free": "Boş alan",
    "dl.installed": "kurulu",
    "dl.download": "İndir",
    "dl.cancel": "İptal",
    "dl.retry": "Tekrar dene",
    "dl.state.hazir": "hazır değil",
    "dl.state.basliyor": "başlatılıyor…",
    "dl.state.indiriliyor": "indiriliyor",
    "dl.state.isleniyor": "işleniyor",
    "dl.state.tamam": "tamamlandı",
    "dl.state.hata": "hata",
    "dl.progress": (inen, top, hiz) =>
      `${inen} / ${top}` + (hiz ? ` · ${hiz}/sn` : ""),
    "dl.eta": (s) => `kalan ~${s}`,
    "dl.sizeNote": (mb) => `yaklaşık ${mb} MB`,

    "csv.rank": "Sira",
    "csv.dir": "Yon",
    "csv.seq": "Dizi_5_3",
    "csv.len": "Uzunluk_nt",
    "csv.tm": "Tm_C",
    "csv.gc": "GC_yuzde",
    "csv.region": "Bolge",
    "csv.geneRegion": "Gen_bolgesi",
    "csv.posStart": "Konum_Baslangic",
    "csv.posEnd": "Konum_Bitis",
    "csv.gStart": "Genomik_Baslangic",
    "csv.gEnd": "Genomik_Bitis",
    "csv.exon": "Ekson",
    "csv.cdnaStart": "cDNA_Baslangic",
    "csv.cdnaEnd": "cDNA_Bitis",
    "csv.onJunction": "Sinir_Ustunde",
    "csv.hairpin": "Hairpin_C",
    "csv.self": "SelfKomp",
    "csv.self3": "SelfKomp_3p",
    "csv.snpCount": "SNP_Sayisi",
    "csv.snpDetail": "SNP_Detay",
    "csv.cdnaProduct": "cDNA_Urun_bp",
    "csv.gdnaProduct": "gDNA_Urun_bp",
    "csv.junctions": "Kapsanan_Sinir",
    "csv.normal": "Normal_bp",
    "csv.skipped": "Atlanmis_bp",
    "csv.diff": "Fark_bp",
    "csv.amplicon": "Amplikon_bp",
    "csv.ampStart": "Amplikon_Baslangic",
    "csv.ampEnd": "Amplikon_Bitis",
    "csv.dimer": "PrimerDimer",
    "csv.dimer3": "PrimerDimer_3p",
    "csv.self3max": "Self3p_Max",
    "csv.dimerScore": "DimerSkor",
    "csv.penalty": "Ceza",
    "csv.assembly": "Derleme",
    "csv.chrom": "Kromozom",
    "csv.bpSecondStatus": "IkinciBant_Durum",
    "csv.ampNote": "Amplikon_Not",
    "csv.ampAssume": "bitişik varsayımıyla; gerçek mesafe bilinmiyor",
    "csv.yes": "evet",
    "csv.no": "hayir",
  },

  en: {
    "app.title": "AllPrime",
    "app.subtitle": "Variant-specific primer design · primer3 engine",
    "app.copyright": "© 2026 Eren Kılınç · GNU GPL v2 or later",
    "app.notice":
      "AllPrime © 2026 Eren Kılınç. This program is licensed under the GNU General Public " +
      "License (GPL) version 2 or (at your option) any later version and comes with " +
      "<b>absolutely no warranty</b>; you may copy and redistribute it under these conditions. " +
      "The licence texts are in the LICENSE (GPL v2) and LICENSE-GPL-3.0.txt (GPL v3) files in the " +
      "application folder; for the notice text see \"Licence and disclaimer\" under " +
      "<a href='#' class='ayar-git'>⚙ Settings › About</a>.",
    "genome.label": "Reference genome",
    "tab.dna": "DNA · genomic",
    "tab.rna": "RNA · cDNA",
    "tab.seq": "Sequence",

    "dna.gene": "Gene (optional)",
    "dna.gene.ph": "e.g. TP53",
    "dna.gene.help": "Used to look up the chromosome when it is left empty.",
    "dna.chrom": "Chromosome",
    "dna.chrom.ph": "e.g. 17 or chr17",
    "dna.pos": "Genomic coordinate (variant)",
    "dna.pos.ph": "e.g. 7676154  or  7676154-7676208",
    "dna.pos.hint": "A single point, or the whole variant (a range)",
    "dna.pos.title":
      "For a point variant enter one coordinate. If the variant is longer than a few bases " +
      "(indel, delins) enter its whole span as a range: 7676154-7676208. The primers are then " +
      "placed outside the entire range; otherwise a primer may fall inside the variant, fail " +
      "to bind the variant allele, and make a heterozygous sample look homozygous. For a " +
      "deletion or duplication the Breakpoint tab is a better fit: it places the primers " +
      "outside the region and reports both bands.",

    "rna.acc": "Transcript (NM_)",
    "rna.acc.ph": "e.g. NM_000546.6",
    "rna.acc.help": "The version suffix is ignored.",
    "rna.search": "Search by gene (optional)",
    "rna.find": "Find",
    "rna.search.help": "Lists the gene's transcripts; MANE Select is flagged.",
    "mode.label": "Design type",
    "rna.mode.variant": "Variant (c.)",
    "rna.mode.skip": "Exon skipping assay",
    "rna.cpos": "c. coordinate",
    "rna.cpos.ph": "e.g. c.1234 · c.-45 · c.*120",
    "rna.exon": "Exons to skip",
    "rna.exon.ph": "e.g. 4-6",
    "rna.exon.range": "or type a range:",
    "rna.exon.hint0":
      "Type the exon number: 7, 4-6 (adjacent) or 4,6 (not adjacent). Once a valid transcript " +
      "accession is entered, the exons also appear as buttons.",
    "rna.exon.hint":
      "Click exons to select them; for a run of adjacent exons click the first and the last " +
      "(Shift+click selects the range). The first and last exon cannot be selected (no anchor exon on one side).",
    "ex.uc": "First/last exon: cannot be selected, there is no anchor exon on one side",
    "ex.secilen": "Selected",
    "ex.ekson": "exon",
    "ex.bitisikDegil": "not adjacent",
    "ex.atlanan": "skipped",
    "ex.korunur": "reading frame preserved",
    "ex.kayar": "reading frame shifted",
    "ex.primer": (a, b) => `Primers are placed in exon ${a} and exon ${b}.`,
    "ex.fark": (n) => `The difference between the normal and skipped band is ${n} bp.`,
    "ex.bantlar": "Expected bands (relative to normal)",
    "ex.utr": "Part of the selection is UTR; the frame is computed from the coding part only.",
    "ex.not": "The product size is computed in the design; if it exceeds the longest-product limit a clear message is shown.",
    "ex.disi": (l) => `Cannot be selected: ${l} (first/last exon, or not in the transcript).`,
    "ex.yakin": (a, b) => `The ${a} bp and ${b} bp bands are very close; they may be hard to tell apart on a gel.`,
    "chip.bandsTitle": "The band seen if the selected exons are skipped, singly or together.",
    "csv.skipExons": "Skipped_exons",
    "csv.bands": "Expected_bands",
    "rna.junction.label": "Place one primer <b>across</b> an exon junction",
    "rna.junction.help":
      "When off (the default), forward and reverse sit in different exons; on gDNA the product " +
      "is longer by the intron length and both sizes are shown. When on, one primer sits directly " +
      "on an exon junction and cannot bind gDNA at all — more definitive, but sometimes no suitable " +
      "primer is found.",
    "rna.skip.help":
      "Primers are placed in the exons <b>before and after</b> the selected exons (for an " +
      "adjacent block, its first and last exon). The normal transcript gives the longer product, " +
      "the skipped transcript the shorter one; the difference equals the total length of the " +
      "skipped exons. If non-adjacent exons are selected (e.g. 4,6), the exons in between stay " +
      "inside the target block; the bands seen when each exon is skipped alone or all together " +
      "are calculated and shown separately, and bands that are very close are flagged. Primers " +
      "are <b>kept off</b> the junctions flanking the target block — a primer sitting there could " +
      "not bind the skipped transcript, and the band you are looking for would never appear. " +
      "The amplicon range is set automatically in this mode (the values under advanced " +
      "parameters are not used).",

    "seq.mode.single": "Single sequence",
    "seq.mode.pair": "Two sequences (F / R regions)",
    "seq.single.label": "Sequence",
    "seq.single.ph":
      "Paste the sequence. FASTA headers, whitespace, position numbers and lower case are fine.\n" +
      "You can mark the target with square brackets:  ...ACGT[A/G]TTTC...",
    "seq.single.help": "No genome or transcript needed; primers are designed directly on this sequence.",
    "seq.target": "Target position (optional)",
    "seq.target.ph": "e.g. 1234 or 1200-1260",
    "seq.target.help": "If left empty the square-bracket marker is used; without that, the whole sequence is free.",
    "seq.fwd.label": "Pick the forward primer from this sequence",
    "seq.fwd.ph": "Region 1 (e.g. the 5' partner of a fusion)",
    "seq.rev.label": "Pick the reverse primer from this sequence",
    "seq.rev.ph": "Region 2 (e.g. the 3' partner of a fusion)",
    "seq.free.label": "Distance unknown — <b>do not apply the product size limit</b>",
    "seq.free.help1":
      "Tick this if you do not know how far apart the two sequences really are. " +
      "Primers are then chosen from <b>anywhere</b> in either sequence, on quality alone. " +
      "When unticked, the amplicon range (advanced parameters) applies and pulls primers " +
      "towards the junction between the two sequences — that is correct for a fusion or " +
      "breakpoint, but discards good primers when the distance is unknown.",
    "seq.free.help2":
      "In both cases the forward primer comes only from the first sequence and the reverse " +
      "only from the second; neither crosses into the other.",
    "seq.gap.summary": "Distance between the two sequences",
    "seq.gap.label": "Distance (bp)",
    "seq.gap.help":
      "Only needed in one situation: the two sequences are the two ends of a single real " +
      "product, you did not paste the piece in between, but you know its length. If you enter " +
      "it, that many <b>N</b> bases are inserted — the product size is then correct and no " +
      "primer can sit in the unknown region. In every other case leave it at <b>0</b>.",

    "snp.label": "<b>Keep primers off</b> common variants (dbSNP)",
    "snp.help":
      "If a common variant sits where the primer binds, that allele will not amplify and a " +
      "heterozygous patient looks <b>homozygous</b>. When on, those positions are excluded from " +
      "primer3 up front. If the region is too dense the constraint is relaxed automatically and " +
      "you are told about it. Turning this off only makes sense deliberately (e.g. allele-specific primers).",
    "snp.missing": (asm) => `No common-variant table found for ${asm} — this check is disabled.`,
    "snp.none": "No SNP check",
    "snp.none.title": "The dbSNP table is not installed for this genome; primers were not checked against common variants.",
    "snp.avoided": (n) => `${n} common variants avoided`,
    "snp.avoided.title": "These template positions were excluded from primer3; no primer was placed on them.",
    "snp.notApplied": (n) => `${n} common variants · constraint not applied`,
    "snp.notApplied.title": "The constraint could not be applied — see the notes.",
    "snp.clean": "No common variants in the region",

    "adv.summary": "Advanced parameters",
    "adv.pcr_max": "Longest amplifiable product (bp)",
    "adv.pcr_max.title":
      "The longest product your lab can reliably amplify by PCR — a ceiling. How it differs " +
      "from 'Amplicon max': the amplicon range is the target size you ask primer3 for and " +
      "binds only that design; this limit applies in EVERY mode (including ones that compute " +
      "their own amplicon range, such as exon skipping) and is the yardstick for bands " +
      "primer3 did not choose — the normal-allele, control and duplication bands in the " +
      "breakpoint tab. If the two conflict, the smaller one wins. Saved on this computer.",
    "adv.product_min_gc": "Product GC min (%)",
    "adv.product_max_gc": "Product GC max (%)",
    "adv.product_gc.title":
      "Keep the GC content of the product (amplicon) within this range. Left at 0-100 no " +
      "constraint is applied and GC is only reported. Candidate pairs outside the range are " +
      "dropped, and how many were dropped is stated above the results.",
    "adv.product_size_min": "Amplicon min (bp)",
    "adv.product_size_max": "Amplicon max (bp)",
    "adv.min_dist_from_variant": "Min distance to variant (bp)",
    "adv.primer_min_size": "Primer length min",
    "adv.primer_opt_size": "Primer length opt",
    "adv.primer_max_size": "Primer length max",
    "adv.primer_min_tm": "Tm min (°C)",
    "adv.primer_max_tm": "Tm max (°C)",
    "adv.primer_max_tm_diff": "Max Tm difference (°C)",
    "adv.primer_min_gc": "GC min (%)",
    "adv.primer_max_gc": "GC max (%)",
    "adv.primer_gc_clamp": "GC clamp",
    "adv.primer_max_end_gc": "Max 3' G/C",
    "adv.primer_max_end_gc.title":
      "Maximum G/C allowed in the last 5 bases. A 3' end with 4-5 G/C is over-stable and " +
      "extends even at wrong sites. Recommended 3; GC clamp cannot exceed this.",
    "adv.primer_max_poly_x": "Max homopolymer",
    "adv.salt_monovalent": "Na⁺ (mM)",
    "adv.salt_divalent": "Mg²⁺ (mM)",
    "adv.dntp_conc": "dNTP (mM)",
    "adv.dna_conc": "Primer (nM)",
    "adv.dmso_conc": "DMSO (%)",
    "adv.num_return": "Number of results",

    "act.design": "Design primers",
    "act.export": "Download CSV",
    "act.autoSpec": "Check specificity automatically",
    "act.autoSpec.title": "In DNA mode every pair is scanned against the genome in the background and gets a badge. No pair is removed and the order does not change; you decide. Needs a local genome; ~3 s per pair.",
    "auto.queued": "Specificity: queued",
    "auto.scanning": "Specificity: scanning…",
    "auto.failed": "Specificity: not checked",
    "auto.error": "Specificity: scan failed",
    "auto.specific": "Specific",
    "auto.specific.title": "No notable (up to 5 mismatches) product outside the target was found.",
    "auto.high": (n) => `High-risk side product: ${n}`,
    "auto.medium": (n) => `Medium-risk side product: ${n}`,
    "auto.medium.title": "Side product formed with 3–5 mismatches across both primers; it usually gives no band. See Check specificity for details.",
    "auto.where": (c, s, n, m) => `Riskiest: chr${c}:${s} · ${n} bp · ${m} mismatches`,
    // "Near copy" line under the badge (server._yakin_not; informational, the badge verdict is unchanged)
    "auto.yakin": (yer, boy, parca) => `Near copy: ${yer} (${boy} bp); ${parca}. Details in Evaluate.`,
    "hairpin.uyari": (ad, hp, ta, pay) => `Hairpin: the hairpin Tm of the ${ad} primer is ${hp} °C; it exceeds the suggested Ta of ${ta} °C minus ${pay} °C. The primer may fold onto itself and lower the yield.`,
    "auto.yakin.primer": (ad, y) => `${y.length} mismatch${y.length > 1 ? "es" : ""} at ${y.map((u) => (u === 1 ? "the last 3' base" : `base ${u} from the 3' end`)).join(" and ")} of the ${ad} primer`,
    "gp.summary": "Genome files (local FASTA)",
    "gp.help": "Point the tool at the downloaded GRCh37 / GRCh38 FASTA (.fa) files here. " +
               "Without them the Ensembl API is used instead (requires internet).",
    "gp.pick": "Browse",
    "license.summary": "Licence and disclaimer",

    // --- favorites (2026-11-14) ---
    "fav.open": "★ Favorites",
    "fav.open.title": "Primer pairs you saved (on this computer only)",
    "fav.title": "Favorites",
    "fav.add": "☆ Add to favorites",
    "fav.add.title": "Saves this pair to the Favorites list (on this computer only)",
    "fav.in": "★ In favorites",
    "fav.in.title": "Click to remove from favorites",
    "fav.note.label": "Note (optional)",
    "fav.note.ph": "e.g. which study, order date",
    "fav.note.privacy": "Do not write patient names or IDs. Favorites are stored on this computer only.",
    "fav.save": "Save",
    "fav.cancel": "Cancel",
    "fav.remove.q": "Remove this pair from favorites? Its note is deleted too.",
    "fav.remove": "Remove",
    "fav.search": "Search gene, position, primer sequence or note",
    "fav.csv": "Download list as CSV",
    "fav.count": (n) => `${n} ${n === 1 ? "entry" : "entries"} · stored on this computer only`,
    "fav.countFiltered": (n, m) => `${n} of ${m} entries shown · stored on this computer only`,
    "fav.empty": "No favorites yet. Add one with the <b>☆ Add to favorites</b> button on a pair card.",
    "fav.noMatch": "No entry matches the search.",
    "fav.toEval": "Open in Evaluate",
    "fav.toEval.title": "Re-evaluates the pair in the Evaluate tab with the reference genome it was saved with",
    "fav.editNote": "Edit note",
    "fav.delete": "Delete",
    "fav.delete.q": "Delete this entry? This cannot be undone.",
    "fav.noNote": "No note",
    "fav.noteLabel": "Note",
    "fav.controlWith": (ad) => `The control primer gives its band with the ${ad} primer`,
    "fav.saved": "Added to favorites.",
    "fav.already": "This pair is already in favorites.",
    "fav.err.gecersiz": "The entry could not be read; it was not added to favorites.",
    "fav.err.yazilamadi": "The favorites file could not be written (the folder may be read-only); the change was not saved.",
    "fav.err.okunamadi": "The favorites file could not be read; the change was not saved.",
    "fav.err.bozuk": "The favorites file is corrupt and could not be read. When you add a new pair the corrupt file is not deleted; it is moved aside under a backup name.",
    "fav.err.sinir": "The favorites limit was reached; delete some old entries.",
    "fav.err.yok": "Entry not found (it may have been deleted).",
    "fav.backup": (yol) => `The corrupt favorites file was not deleted; it was kept as: ${yol}`,
    "fav.kind.dna": "DNA",
    "fav.kind.cdna": "RNA · variant",
    "fav.kind.atlama": "RNA · exon skipping",
    "fav.kind.dizi": "Sequence",
    "fav.kind.dizi_cift": "Sequence · two sequences",
    "fav.kind.kirilma.del": "Breakpoint · deletion",
    "fav.kind.kirilma.dup": "Breakpoint · duplication",
    "fav.kind.degerlendir_dna": "Evaluate · DNA",
    "fav.kind.degerlendir_cdna": "Evaluate · RNA",
    "fav.target": "target",
    "fav.margin": "uncertainty",
    "csv.favNo": "Entry",
    "csv.favDate": "Date",
    "csv.favKind": "Kind",
    "csv.favGene": "Gene",
    "csv.favInput": "Input",
    "csv.favProduct": "Product",
    "csv.favTa": "Suggested_Ta_C",
    "csv.favNote": "Note",
    "csv.favVersion": "AllPrime_version",

    // --- settings screen ---
    "set.open": "⚙ Settings",
    "set.back": "← Back to design",
    "set.title": "Settings",
    "set.view": "Appearance",
    "set.theme": "Theme",
    "set.theme.help": "“Follow Windows” uses the Windows light / dark setting.",
    "set.theme.dark": "Dark",
    "set.theme.light": "Light",
    "set.theme.system": "Follow Windows",
    "set.zoom": "Interface size",
    "set.zoom.help": "Text, buttons and tables scale together.",
    "set.lang": "Language",
    "set.lang.help": "Same as TR / EN in the top bar.",
    "set.lab": "Laboratory defaults",
    "set.lab.intro": "The program starts with these values every time; they are stored on this " +
      "computer only. For a one-off change to a single design, use “Advanced parameters”.",
    "set.asm": "Reference genome at start-up",
    "set.asm.help": "The choice in the top bar applies to the current session only.",
    "set.pcrMax.help": "The longest product your laboratory amplifies reliably by PCR. Same field " +
      "as in Advanced parameters; saved as soon as it changes.",
    "set.params": "PCR conditions and primer parameters",
    "set.params.help": (n) => `The ${n} values in Advanced parameters. Saved values that differ from the factory value are listed.`,
    "set.params.name": "Parameter",
    "set.params.saved": "Saved default",
    "set.params.factory": "Factory",
    "set.params.none": "Factory values are in use (no saved differences).",
    "set.params.save": "Make the Advanced parameter values the default",
    "set.params.saveHere": "Make these values the laboratory default",
    "set.params.where": "Saved values: ⚙ Settings › Laboratory defaults",
    "set.params.reset": "Restore factory values",
    "set.params.done": (n) => n ? `${n} value(s) saved as laboratory defaults.`
      : "All values are at their factory setting; no differences saved.",
    "set.params.resetDone": "Factory values restored.",
    "set.params.fail": "The setting could not be saved.",
    "set.data": "Data files and genome",
    "set.about": "About",
    "about.version": "AllPrime version",
    "about.engine": (v) => `engine ${v}`,
    "about.core": "Calculation core",
    "about.core.bad": "primer3 could not be loaded",
    "about.genome": (a) => `Reference genome ${a}`,
    "about.local": "local file",
    "about.api": "none – uses Ensembl",
    "about.annot": "Transcript table (refGene)",
    "about.dbsnp": "Common variant index (dbSNP)",
    "about.ready": "ready",
    "about.missing": "missing",
    "about.sources": "Data sources",
    "about.sourcesText": "Ensembl (genome), UCSC (refGene, dbSNP b151 Common), NCBI (MANE)",

    "msg.calculating": "Working…",
    "act.cancel": "Cancel",
    "msg.cancelled": "Cancelled.",
    "msg.timeout": "The engine did not answer within 5 minutes; the request was stopped. The engine may still be working — wait a little and try again.",
    "msg.searching": "Searching…",
    "msg.error": (e) => `Error: ${e}`,
    "msg.noEngine": (e) => `Could not reach the engine: ${e}`,
    "msg.genomeSet": (asm) => `${asm} genome registered.`,
    "err.needPos": "Genomic coordinate is required.",
    "err.needChromOrGene": "Chromosome or gene name is required.",
    "err.needAcc": "Transcript accession (NM_) is required.",
    "err.needExon": "Exon number is required.",
    "err.needCpos": "c. coordinate is required (e.g. c.1234).",
    "err.needSeq": "Sequence is required.",
    "err.needBothSeq": "Both sequences are required.",
    "err.needGene": "Enter a gene symbol.",
    "status.genomeLocal": (asm) => `${asm}: local FASTA`,
    "status.genomeApi": (asm) => `${asm}: Ensembl API (internet)`,
    "status.rnaDisabled": (asm) =>
      `The transcript table (refGene) for ${asm} is missing or unreadable (the file may be partial/damaged) — download it again from the data files panel.`,

    "copy.btn": "⧉ Copy",
    "copy.title": "Copy sequence to clipboard",
    "copy.ok": "✓ Copied",
    "copy.fail": "✗ Failed",

    "tx.meta": (ex, nt, coding) =>
      `${ex} exons · ${nt} nt${coding ? "" : " · non-coding"}`,
    "rna.derleme.not": (asm) =>
      `The RNA tab always builds the transcript from the ${asm} genome (MANE Select is defined on ${asm}); the genomic positions shown are ${asm} positions.`,
    "kod.rozet": "Alignment warning",
    "kod.neden.mod3": "length is not a multiple of 3",
    "kod.neden.son_kodon": "last codon is not a stop",
    "kod.neden.erken_durdurma": "premature stop codon",
    "kod.kisa": (nedenler) =>
      `The genome alignment may not match the NM sequence exactly (${nedenler}): c. and exon ` +
      "numbers may shift; it may also be a genuine stop codon. Compare with the NM sequence " +
      "or design in the DNA tab with a genomic coordinate.",
    "region.kod": "This transcript's alignment may not match the NM sequence exactly: the exon number may differ from the NM's.",

    "sum.genome": "Genome",
    "sum.position": "Position",
    "sum.gene": "Gene",
    "sum.found": "Pairs found",
    "sum.srcLocal": "Local FASTA",
    "sum.srcApi": "Ensembl API",
    "sum.transcript": "Transcript",
    "sum.exonCount": (n) => `${n} exons`,
    "sum.strand": (s) => `${s} strand`,
    // F/R names follow the gene's reading direction (yon.js)
    "yon.eksi": (g) => `${g} is on the minus (−) strand: primer names and the product sequence follow the ` +
      "gene's reading direction. A Sanger read from the Forward primer runs in the same direction as the c. " +
      "sequence; a read from the Reverse primer is its reverse complement. Positions are genomic (+) " +
      "coordinates.",
    "yon.belirsiz": "The product overlaps genes on opposite strands: F/R names follow the genome's + strand.",
    "amp.geneDir": (g) => `${g} (− strand) in gene direction, reverse complement`,
    "sum.variant": "Variant",
    "sum.exon": "exon",
    "sum.target": "Target",
    "sum.versionless": "matched without version",
    "sum.noTarget": "No target",
    "sum.noTarget.title": "No target given; primers were chosen from the whole sequence.",
    "sum.seqLen": "Sequence",
    "sum.fwdRegion": "Forward region",
    "sum.revRegion": "Reverse region",
    "sum.gap": "Distance between",
    "sum.gap.title": "0 means the sequences were treated as contiguous (fusion / breakpoint).",
    "sum.gapUnknown": "distance unknown",
    "sum.gapUnknown.title": "No product size limit was applied; primers were chosen from the whole of both sequences.",

    "chip.amplicon": "Amplicon",
    "tm.cond": (mv, mg, dntp, dna, dmso) =>
      `${mv} mM K⁺/Na⁺, ${mg} mM Mg²⁺, ${dntp} mM dNTP, ${dna} nM primer` + (dmso ? `, ${dmso}% DMSO` : ""),
    "tm.note": (kosul) => `Tm: nearest-neighbour method (SantaLucia 1998), ${kosul}.`,
    "tm.why": "Why might another tool's Tm differ?",
    "tm.whyText":
      `Tm varies between tools with the calculation method and conditions. For example, a "Basic" Tm ` +
      `computed only from length and G+C count ignores salt and Mg²⁺, so it usually comes out a few ` +
      `degrees lower. When comparing values, check which method and conditions were used; you can ` +
      `change the conditions used here under advanced parameters.`,
    "chip.ta": "Suggested Ta",
    "chip.ta.title": "Starting point for the annealing temperature: Tm of the lower-Tm primer − 5 °C (Taq). Tm is computed with the salt, primer and DMSO conditions under advanced parameters. Find the exact value by gradient PCR; your polymerase vendor's advice may differ.",
    "chip.gc": "GC",
    "fmt.pct": (v) => `${v}%`,
    "chip.gc.title":
      "GC percentage of the amplified region. 65% and above counts as GC-rich (consider a GC " +
      "buffer / 3-5% DMSO / ~1 M betaine), 75% and above almost always needs an additive; " +
      "30% and below is AT-rich. Sources: Thermo Phusion manual, PLOS One 2016.",
    "chip.position": "Position",
    "igv.copy": "Copy for IGV",
    "igv.copy.title": (asm, hg) => `Copies the range spanned by the primers in the form the IGV or UCSC search box accepts (chr7:117559410-117559715). IGV must have the ${asm} (${hg}) genome loaded.`,
    "chip.dTm": "ΔTm",
    "chip.selfMax": "Self-compl. (worst)",
    "chip.selfMax.title": "Self-complementarity of the primer: the tendency of two copies to stick to each other (the higher of the two primers is shown). Lower is better; above 8 is a problem.",
    "chip.self3p": "3' self-compl.",
    "chip.self3p.title": "The tendency of the 3' end to stick to itself or to the other primer. If the 3' end holds, the polymerase extends it and a primer-dimer forms — the most dangerous kind. Lower is better; design rejects values above 3.",
    "chip.dimer": "Dimer score",
    "chip.dimer.title": "Complementarity between the two primers (heterodimer): their tendency to stick to each other. Lower is better; design rejects pairs above 8.",
    "chip.snp": "Common variant",
    "chip.snp.title3p": "At least one variant lies within 5 bases of the 3' end — high allele dropout risk.",
    "chip.snp.title": "The variants are away from the 3' end; lower risk, but worth noting.",
    "chip.cdnaProduct": "cDNA product",
    "chip.gdna": "gDNA",
    "chip.gdna.title": "The same primers give a product of this size on genomic DNA — useful for telling them apart on a gel.",
    "chip.gdna.titleSkip": "Expected product on genomic DNA — includes the introns.",
    "chip.junctions": "Junctions spanned",
    "chip.junctions.title": "The product spans this many exon junctions.",
    "chip.noJunction": "Spans no junction",
    "chip.noJunction.title": "The product spans no exon junction — it cannot be told apart from gDNA.",
    "chip.exons": "Exons",
    "chip.normal": "Normal",
    "chip.normal.title": "The band seen if the exon is present.",
    "chip.skipped": "Skipped",
    "chip.skipped.title": "The band seen if the exon is skipped.",
    "chip.diff": "Difference",
    "chip.diff.title": "The difference between the two bands. A small difference is hard to resolve on a gel.",
    "chip.assumeContig": "(assuming contiguous)",
    "chip.assumeContig.title": "The real distance between the two sequences is unknown, so this number only holds if they are contiguous.",

    "th.dir": "Direction",
    "th.seq": "Sequence (5'→3')",
    "th.nt": "nt",
    "th.tm": "Tm",
    "th.gc": "GC%",
    "region.exon": (n) => `exon\u00a0${n}`,
    "region.intron": (n) => `intron\u00a0${n}`,
    "region.exonRange": (a, b) => `exons\u00a0${a}–${b}`,
    "region.boundary": (e, i) => `exon\u00a0${e} / intron\u00a0${i} boundary`,
    "region.boundaryEnd": (e, uc) => `exon\u00a0${e} / ${uc} boundary`,
    "region.side.bas": "gene start",
    "region.side.son": "gene end",
    "th.region": "Gene region",
    "th.region.title":
      "Where the primer sits in the gene: exon 7, intron 7, or the boundary between " +
      "them. Exon numbering depends on the transcript; hover a cell to see which " +
      "transcript it is based on (MANE Select when available).",
    "th.region.cell": (gene, acc, mane, n) =>
      `${gene} ${acc}${mane} · ${n} exons — numbering follows this transcript`,
    "th.region.none": "This position is not inside any gene in the table (intergenic), or no transcript table is loaded for this genome.",
    "th.pos": "Position",
    "th.exon": "Exon",
    "th.cdnaPos": "cDNA position",
    "th.cdnaPos.title": "Position along the transcript (nt)",
    "th.regionPos": "Position within region",
    "th.hairpin": "Hairpin °C",
    "th.hairpin.title": "Hairpin melting temperature (thermodynamic, °C)",
    "th.self": "Self-compl.",
    "th.self.title": "Self-complementarity of the primer: the tendency of two copies to stick to each other. Lower is better; above 8 is a problem.",
    "th.self3": "3' Self-compl.",
    "th.self3.title": "Self-complementarity of the primer's 3' end: if it sticks at the 3' end it extends and gives a primer-dimer. Lower is better; above 3 is risky.",
    "th.snp": "SNP",
    "th.snp.title": "Number of common variants (dbSNP) falling on the primer. Hover for rs number, MAF and distance from the 3' end.",
    "dir.forward": "Forward",
    "dir.reverse": "Reverse",
    "flag.junction": "junction",
    "flag.junction.title": "This primer sits across an exon junction — it cannot bind gDNA.",
    "snpCell.title": (rs, maf, indel, d) =>
      `${rs} · MAF ${maf}${indel ? " · indel" : ""} · ${d} bases from the 3' end`,
    "seq.region1": "sequence 1",
    "seq.region2": "sequence 2",

    "res.none": "No suitable primer pair found. Try relaxing the parameters.",

    "spec.btn": "⌕ Check specificity",
    "spec.note": "genome scan · a few seconds",
    "spec.scanning": "Scanning…",
    "spec.ok": "Appears specific",
    "spec.high": (n) => `${n} high-risk off-target products`,
    "spec.mid": (n) => `${n} medium-risk off-target products`,
    "spec.targetFound": "Intended region found",
    "spec.targetCdna": "Intended region not contiguous in the genome (expected)",
    "spec.targetCdna.title": "Expected in cDNA mode: the product spans introns, so it is not contiguous in the genome.",
    "spec.targetMissing": "Intended region not found",
    "spec.targetMissing.title": "The designed product did not show up in the genome scan.",
    "spec.seqMode": "Free sequence · no intended region",
    "spec.seqMode.title": "The genomic location of the pasted sequence is unknown, so the intended product cannot be separated; the list below shows ALL possible products in the genome.",
    "spec.sites": "Binding sites",
    "spec.sites.title": (mm) => `Number of places in the genome where the primer could extend. In brackets: those binding with at most ${mm} mismatches.`,
    "spec.riskCounts": "Risk",
    "spec.riskSummary": (h, m, l) => `${h} high · ${m} medium · ${l} low`,
    "spec.th.risk": "Risk",
    "spec.th.combo": "Combination",
    "spec.th.combo.title": "Which primer pair gives this product",
    "spec.th.loc": "Location",
    "spec.th.product": "Product",
    "spec.th.mismatch": "Mismatches",
    "spec.th.mismatch.title": "Mismatched bases in each primer's own binding site — the left and right figures are two SEPARATE primers (not 5'/3'). The letter in front says which. The last 8 bases at the 3' end already match exactly, so mismatches lie on the 5' side.",
    "spec.clean": "No off-target products worth noting.",
    "spec.truncated": (n, tot) => `Showing the first ${n} entries (${tot} in total).`,
    "spec.lowHidden": (n) => `${n} sites with low binding probability are not listed `
      + `(6+ mismatches across the two primers).`,
    "risk.yuksek": "high",
    "risk.orta": "medium",
    "risk.dusuk": "low",
    "risk.hedef": "target",
    "ev.showLow": (n) => `Show ${n} products with low binding probability`,
    "ev.hideLow": "Hide low-probability products",
    // --- engine version mismatch ---
    "err.oldEngine":
      "The engine does not recognise this request (HTTP 404). The UI looks newer than " +
      "the engine — replace the resources\\backend folder with the current version.",
    "err.notJson": (kod) => `Unexpected response from the engine (HTTP ${kod}).`,
    "engine.mismatch": "Engine and UI do not match.",
    "engine.p3": "The calculation engine is not working.",
    "genome.warn.blocked": (a) => `The ${a} genome cannot be used.`,
    "genome.warn.note": (a) => `Warning for the ${a} genome.`,
    "about.blocked": "file present but unusable",
    "engine.old":
      "The engine does not report its version (a build from before 13 Sep 2026). It may " +
      "work, but which features it supports cannot be verified; replacing it with the " +
      "current engine is recommended.",
    "engine.missing": (u) => `The engine does not provide: ${u}.`,
    "engine.versionDiff": (m, a) => `Engine version ${m}, UI version ${a}.`,
    "engine.fix":
      "This usually happens when the folder is copied and the engine is left behind. " +
      "Close the app and replace the resources\\backend folder with the current one.",
    "ev.handoff": "Evaluate",
    "ev.handoff.title":
      "Opens this pair in the Evaluate tab. The sequences, the variant position and (in cDNA mode) " +
      "the transcript accession are filled in automatically; your design results are kept.",
    "ev.lowExplain":
      "These sites carry 6 or more mismatches across the two primers. At this primer " +
      "length they do not give a band in practice, but if you are chasing an " +
      "unexpected product you can look here.",
    "ev.lowTruncated": (n, tot) => `Showing the first ${n} (${tot} in total).`,
    // "differs from a copy by only 1-2 bases" note (evaluate._yakin_kopya)
    "ev.yakin.title": (n) => (n === 1 ? "Differs from a copy by a single base only — be cautious"
      : `Differs from a copy by only ${n} bases — be cautious`),
    "ev.yakin.yer": (u) => (u === 1 ? "its last 3' base" : `base ${u} from the 3' end`),
    "ev.yakin.cift": (pb, kb) => `primer ${pb} opposite ${kb}`,
    "ev.yakin.primer": (p, f) => (!f.length ? `${p} matches the copy exactly`
      : f.length === 1 ? `${p} differs only at ${f[0][0]} (${f[0][1]})`
      : `${p} differs at ${f.map(([y, c]) => `${y} (${c})`).join(" and ")}`),
    "ev.yakin.text": (yer, konum, bp, kombi, parca, n, adet) =>
      `This pair can give a product in ${yer} (${konum ? konum + ", " : ""}${bp} bp${kombi === "F+R" || kombi === "R+F" ? "" : ", " + kombi}): ` +
      `${parca}. The scan treats a primer whose 3' end does not match as not extending, so this product is not ` +
      `in the list above. ${n === 1 ? "A single-base difference is a weak separation" : "So few differences can be a weak separation"}; ` +
      "the copy may amplify too. Use a non-proofreading Taq and check by Sanger which copy the product comes from." +
      `${adet > 1 ? ` There are ${adet} such sites; the one with the fewest differences is shown.` : ""}`,

    // --- breakpoint tab ---
    "tab.bp": "Breakpoint",
    "bp.intro": "Enter the boundaries of a deletion or duplication; the tool designs primers that amplify the breakpoint. Start and end are the first and last base of the deleted / duplicated region. Pasting a location like 'chr2:50,000,001-50,012,000' into the start box fills the boxes automatically.",
    "bp.mode.del": "Deletion",
    "bp.mode.dup": "Duplication",
    "bp.start": "Start",
    "bp.start.ph": "e.g. 50000001",
    "bp.start.help": "chr:start-end can be pasted.",
    "bp.end": "End",
    "bp.end.ph": "e.g. 50012000",
    "bp.margin": "Breakpoint uncertainty (± bp)",
    "bp.margin.help": "0 if the boundaries are known to the base from sequencing. For approximate results (MLPA, array, exome), the possible shift of each end: primers are placed on the safe side of every possible breakpoint and band sizes are given as ranges.",
    "bp.control.label": "Add a control primer (3rd primer)",
    "bp.control.help": "For a deletion, a normal-allele primer is placed inside the deleted region: normal / heterozygous / homozygous can be told apart on one gel. For a large duplication, a control primer is placed outside the region: a normal sample also gives a band, showing the PCR worked. The control band is chosen at least 100 bp away from the breakpoint band.",
    "bp.help.del": "Deletion: the primers are placed on either side of the deleted region. On the deleted allele they come together and give a short breakpoint product; the breakpoint lies inside the product and can be read by Sanger. The primers are kept at least 100 bp from the breakpoint.",
    "bp.help.dup": "Duplication (tandem): the primers are placed inside the duplicated region, near its ends, facing outward; they amplify only across the junction of the two copies, and the product size does not depend on the size of the duplication. It does not detect inverted or insertional copies: a negative result does not exclude the duplication. Duplications under 1.5 kb use outer primers and the size difference.",
    "bp.approach.gap_pcr": "Gap-PCR (breakpoint)",
    "bp.approach.tandem_junction": "Tandem junction (outward-facing primers)",
    "bp.approach.size_shift": "Size shift (outer primers)",
    "sum.region": "Region",
    "sum.type": "Type",
    "sum.approach": "Approach",
    "sum.margin": "Uncertainty",
    "bp.chip.mut": "Breakpoint band",
    "bp.chip.mut.title": "Product from the deleted allele; the breakpoint lies inside it.",
    "bp.chip.wt": "Normal allele",
    "bp.chip.wt.title": "Expected product from the normal allele: the primers also span the deleted region. 'Your limit' is the 'longest amplifiable product' setting under advanced parameters — your protocol, not an absolute bound. With a protocol that covers longer products, bands above the limit may also be seen.",
    "bp.wt.var": "within your limit",
    "bp.wt.zayif": "above your limit",
    "bp.wt.yok": "far above your limit",
    "bp.chip.junction": "Junction band",
    "bp.chip.junction.title": "Product only from the tandem-duplicated allele, across the junction of the two copies.",
    "bp.chip.noWt": "No product on a normal genome",
    "bp.chip.noWt.title": "On the reference genome the primers face away from each other; the normal allele gives no product.",
    "bp.chip.wtShort": "Normal allele",
    "bp.chip.dupBand": "Duplicated allele",
    "bp.chip.control": "Control band",
    "bp.chip.control.title": (ad) => `Band from the control primer with the ${ad} primer (normal allele / PCR control).`,
    "bp.dir.control": "Control",
    "bp.th.genotype": "Genotype",
    "bp.th.bands": "Expected bands",
    "bp.gt.normal": "Normal",
    "bp.gt.het": "Heterozygous deletion",
    "bp.gt.homDel": "Homozygous deletion",
    "bp.gt.dup": "Duplication (heterozygous / homozygous)",
    "bp.gt.hetDup": "Heterozygous duplication",
    "bp.gt.homDup": "Homozygous duplication",
    "bp.noBand": "no band",
    "bp.controlMissing": (why) => `No control primer could be added: ${why}.`,
    "bp.controlDimer": (s, ad) => `WARNING: The control primer may form a 3'-end dimer with the other ${ad} primer (3' dimer score ${s}); if all three primers go in one tube, try another pair.`,
    "bp.controlSpecHint": (ad) => `The specificity scan checks the forward and reverse primers. To see where the control primer binds in the genome, evaluate the ${ad} + control primers together in the Evaluate tab; they give an ordinary product on the normal reference, so the result reads directly.`,
    "spec.bpNoRef": "Breakpoint product not in the reference (expected)",
    "spec.bpWtFound": "Normal-allele product found",
    "spec.bpNoRef.title": "The breakpoint product is specific to the deleted / duplicated allele and does not exist in the reference genome. The list below shows other possible products in the reference.",
    "err.needBp": "Chromosome, start and end are required.",
    "csv.bpMain": "MainBand_bp",
    "csv.bpSecond": "SecondBand_bp",
    "csv.bpControl": "ControlBand_bp",

    // --- evaluate tab ---
    "tab.eval": "Evaluate",
    "ev.intro":
      "Examines a primer pair you already have — it does not design one. Tells you where " +
      "it binds in the genome, what product it gives, and <b>why it gives none</b> if that " +
      "is the case.",
    "ev.fwd": "Forward primer (5'→3')",
    "ev.rev": "Reverse primer (5'→3')",
    "ev.rev.help": "Leave empty to evaluate the forward primer alone.",
    "ev.target": "Variant position (optional)",
    "ev.target.ph": "e.g. chr19:11537002 · c.215 in RNA mode",
    "ev.target.help": "If given, this position is marked in the product sequence. Filled in automatically when you arrive from a card's Evaluate button.",
    "ev.run": "Evaluate",
    "ev.running": "Analysing…",
    "ev.verdict.iyi": "No problems found",
    "ev.verdict.uyari": "Points to watch",
    "ev.verdict.sorun": "Serious problem",
    "ev.props": "Primer properties",
    "ev.sites": "Binding sites in the genome",
    "ev.products": "Predicted products",
    "ev.findings": "Findings",
    "ev.noProduct": "This pair gives no product at all.",
    "ev.overflow": "No product prediction was made: the primers sit in a repeat and the possible products are too many to count. See the findings below.",
    "ev.noGenome": "No local genome configured, so no genome analysis was possible.",
    "ev.level.sorun": "problem",
    "ev.level.uyari": "warning",
    "ev.level.bilgi": "info",
    // --- evaluation: RNA / cDNA mode ---
    "ev.mode.label": "Primer type",
    "ev.mode.dna": "DNA (genomic)",
    "ev.mode.cdna": "RNA / cDNA",
    "ev.mode.help":
      "cDNA primers may sit across an exon junction; such a primer does not exist " +
      "contiguously in the genome, so DNA mode raises a false alarm for them.",
    "ev.acc": "Transcript (NM_)",
    "ev.acc.find": "Find by gene",
    "ev.acc.help": "Enter an NM_ accession, or type a gene symbol and press \"Find by gene\".",
    "ev.err.needAcc": "RNA mode needs a transcript accession (NM_).",
    "ev.cdna.placement": "Placement on the transcript",
    "ev.cdna.th.pos": "cDNA position",
    "ev.cdna.th.exon": "Exon",
    "ev.cdna.th.exon.title": "Exon(s) the primer sits in. Two numbers mean it spans the junction.",
    "ev.cdna.th.junction": "Exon junction",
    "ev.cdna.th.junction.title":
      "If the primer spans an exon junction, the number of bases on either side. " +
      "Such a primer cannot bind genomic DNA.",
    "ev.cdna.junction": (a, b) => `${a}+${b} bases`,
    "ev.cdna.notFound": "Not found in this transcript",
    "ev.cdna.product": "Predicted product",
    "ev.cdna.cdnaBand": "cDNA band",
    "ev.cdna.gdnaBand": "gDNA band",
    "ev.cdna.gdnaBand.title":
      "What the same primers would give on genomic DNA. To tell contamination apart, " +
      "this band must differ from the cDNA band.",
    "ev.cdna.junctions": "Junctions spanned",
    // --- amplicon (amplified sequence) ---
    "amp.btn": "Product sequence",
    "amp.btn.hide": "Hide sequence",
    "amp.th": "Sequence",
    "amp.title": (n) => `Amplified sequence — ${n} bp`,
    "amp.fwd": "Forward primer",
    "amp.rev": "Reverse primer (reverse complement)",
    "amp.fwd.rc": "Forward primer (reverse complement)",
    "amp.rev.self": "Reverse primer",
    "amp.fromF": "Reverse complement: the sequence starts at the F primer",
    "amp.target": (ad, a, b) => `${ad} (${a === b ? `base ${a}` : `bases ${a}–${b}`} of the product)`,
    "amp.target.bp": "Both sides of the breakpoint",
    "amp.target.region": "Entered region",
    "amp.target.seq": "Target",
    "kopya.title": "Pairs that separate from the copy",
    "eniyi.title": "Best specific pair",
    "eniyi.sirada": "All candidates that meet the rules will be scanned when the badges finish.",
    "eniyi.araniyor": "Scanning all candidates that meet the rules in the genome…",
    "eniyi.taranan": (n) => `${n} candidates scanned`,
    "eniyi.neden": (y, o) => `Pair 1 is not specific: ${[y && `${y} high`, o && `${o} medium`].filter(Boolean).join(", ")}-risk off-target products within 3 kb. `,
    "eniyi.ilk10.title": (k) => `Best specific pair: number ${k} in the list`,
    "eniyi.ilk10.hint": (k, f) => `All candidates that meet the rules were scanned in the genome; the best specific pair is number ${k} in the list (compared with pair 1: ${f}). The normal list is unchanged.`,
    "eniyi.git": (k) => `Go to pair ${k}`,
    "eniyi.disari.hint": "All candidates that meet the rules were scanned in the genome; the best specific pair is below. The normal list is unchanged.",
    "eniyi.k2.title": "A better specific pair exists",
    "eniyi.k2.hint": (f, n) => `Pair 1 is specific. Scanning all candidates that meet the rules found a specific pair with a better score under the same rules (${f}). It is not in the list because the list is taken from primer3's first ${n} candidates. The normal list is unchanged.`,
    "eniyi.k2.bir": (n) => `Pair 1 is specific; specific pairs with a better score are not in the list because it is taken from primer3's first ${n} candidates. `,
    "eniyi.paralog.chip": (n, m) => `first ${n} specific pairs · ${m} candidates scanned`,
    "eniyi.paralog.hint": (neden, m, n) => `This gene has a close copy. ${neden}All ${m} candidates that meet the rules were scanned in the genome; the first ${n} specific pairs are below, the best on top. The normal list is unchanged. Difference from copy is how far the base that separates the pair from the copy lies from the primer's 3' end; a difference near the end separates more strongly.`,
    "eniyi.yok.title": "No specific pair found",
    "eniyi.yok.hint": (m, paralog) => `All ${m} candidates that meet the rules were scanned in the genome; none is specific. The least risky pairs are below (fewest high-risk, then fewest medium-risk off-target products).${paralog ? " The gene and its copy are very similar in this region. If you use a pair, read the product by Sanger and check which copy it came from at the distinguishing bases." : " If you use a pair, review its off-target products in the Evaluate tab."}`,
    "eniyi.th.fark": "Compared with pair 1",
    "eniyi.th.yan": "Off-target (3 kb)",
    "eniyi.yan": (y, o) => `${y} high / ${o} medium`,
    "eniyi.havuz_disi": "outside pool",
    "eniyi.havuz_disi.title": (n) => `The list is taken from primer3's first ${n} candidates; this pair is outside them.`,
    "eniyi.fark.ceza": (x) => `length deviation ${x} nt`,
    "eniyi.fark.dimer": (x) => `dimer ${x}`,
    "eniyi.fark.boy": (n, kisa) => `product ${n} bp ${kisa ? "shorter" : "longer"}`,
    "eniyi.fark.ayni": "same",
    "kopya.dugme": "This gene has a close copy. The candidate pool can be searched for pairs that give no product from the copy.",
    "kopya.ara": "Search for pairs that separate from the copy",
    "kopya.hepsi": (n) => `Show all (${n})`,
    "kopya.th.sira": "Pool rank",
    "kopya.th.f": "Forward (5'→3')",
    "kopya.th.r": "Reverse (5'→3')",
    "kopya.th.urun": "Product",
    "kopya.th.fark": "Difference from copy",
    "kopya.fark.son": (p) => `${p}: last 3' base`,
    "kopya.fark.uc": (p, k) => `${p}: base ${k} from 3' end`,
    "kopya.fark.toplam": (n) => ` · ${n} differences`,
    "kopya.fark.cok": "Very different",
    "kopya.fark.cok.title": "In the copy regions there is no binding that would give a product with at most 5 mismatches, even without the 3' end rule.",
    "kopya.fark.title": (c, s, n) => `Closest possible product in the copy: chr${c}:${s}, ${n} bp. The nearer the difference is to the 3' end, the stronger the separation.`,
    "amp.junction": "Exon junction",
    "amp.breakpoint": "Breakpoint",
    "amp.unknown": (n) => `Unknown middle region (${n} bp, shown as N)`,
    "amp.copy": "Copy",
    "amp.copyFasta": "FASTA",
    "amp.copyFasta.title": "Copies as FASTA, with a header line.",
    "ev.th.len": "nt",
    "ev.th.clamp": "GC clamp",
    "ev.th.poly": "Homopolymer",
    "ev.th.self3": "3' self",
    "ev.th.self3.title": "Self-complementarity of the primer's 3' end: if it sticks at the 3' end it extends and gives a primer-dimer. Design rejects primers above 3; Evaluate notes values above 3 and warns at 6 or more.",
    "ev.hetero3": "3' dimer score",
    "ev.hetero3.title": "Complementarity between the 3' ends of the two primers: if the ends hold on to each other they extend on each other and form a primer-dimer. Design rejects pairs above 3; Evaluate notes values above 3 and warns at 6 or more.",
    "ev.th.site": "Location",
    "ev.th.orient": "Orient.",
    "ev.th.mm": "Mismatch",
    "ev.th.where": "Region",
    "ev.region.exon": (n) => `exon ${n}`,
    "ev.region.intron": "intron",
    "ev.siteCount": (perfect, good, total) =>
      `${perfect} perfect · ${good} good · ${total} total`,
    "ev.dTm": "ΔTm",
    "ev.heteroTm": "Dimer Tm",
    "ev.heteroTm.title": "Thermodynamic melting temperature of the two primers binding each other (primer3). 45 °C or higher gives a warning.",

    // --- data file downloads ---
    "dl.summary": "Data files (download)",
    "dl.intro":
      "Genome and variant files are not shipped with the application; they are " +
      "downloaded here from their source. Downloads <b>resume where they left off</b>, " +
      "so a dropped connection does not start over. One file downloads at a time — on a " +
      "slow link, parallel downloads do not shorten the total time. If you already have " +
      "the files, you can point at them directly under “Genome files” instead.",
    "dl.root": "Location",
    "dl.free": "Free space",
    "dl.installed": "installed",
    "dl.download": "Download",
    "dl.cancel": "Cancel",
    "dl.retry": "Retry",
    "dl.state.hazir": "not installed",
    "dl.state.basliyor": "starting…",
    "dl.state.indiriliyor": "downloading",
    "dl.state.isleniyor": "processing",
    "dl.state.tamam": "done",
    "dl.state.hata": "error",
    "dl.progress": (inen, top, hiz) =>
      `${inen} / ${top}` + (hiz ? ` · ${hiz}/s` : ""),
    "dl.eta": (s) => `~${s} left`,
    "dl.sizeNote": (mb) => `about ${mb} MB`,

    "csv.rank": "Rank",
    "csv.dir": "Direction",
    "csv.seq": "Sequence_5_3",
    "csv.len": "Length_nt",
    "csv.tm": "Tm_C",
    "csv.gc": "GC_percent",
    "csv.region": "Region",
    "csv.geneRegion": "Gene_region",
    "csv.posStart": "Position_start",
    "csv.posEnd": "Position_end",
    "csv.gStart": "Genomic_start",
    "csv.gEnd": "Genomic_end",
    "csv.exon": "Exon",
    "csv.cdnaStart": "cDNA_start",
    "csv.cdnaEnd": "cDNA_end",
    "csv.onJunction": "On_junction",
    "csv.hairpin": "Hairpin_C",
    "csv.self": "SelfCompl",
    "csv.self3": "SelfCompl_3p",
    "csv.snpCount": "SNP_count",
    "csv.snpDetail": "SNP_detail",
    "csv.cdnaProduct": "cDNA_product_bp",
    "csv.gdnaProduct": "gDNA_product_bp",
    "csv.junctions": "Junctions_spanned",
    "csv.normal": "Normal_bp",
    "csv.skipped": "Skipped_bp",
    "csv.diff": "Difference_bp",
    "csv.amplicon": "Amplicon_bp",
    "csv.ampStart": "Amplicon_start",
    "csv.ampEnd": "Amplicon_end",
    "csv.dimer": "PrimerDimer",
    "csv.dimer3": "PrimerDimer_3p",
    "csv.self3max": "Self3p_max",
    "csv.dimerScore": "DimerScore",
    "csv.penalty": "Penalty",
    "csv.assembly": "Assembly",
    "csv.chrom": "Chromosome",
    "csv.bpSecondStatus": "SecondBand_status",
    "csv.ampNote": "Amplicon_note",
    "csv.ampAssume": "assuming contiguous; real distance unknown",
    "csv.yes": "yes",
    "csv.no": "no",
  },
};

let LANG = "tr";

function setLangDict(lang) {
  LANG = I18N[lang] ? lang : "tr";
  document.documentElement.lang = LANG;
}

function t(key, ...args) {
  const dict = I18N[LANG] || I18N.tr;
  let v = dict[key];
  if (v === undefined) v = I18N.tr[key];      // eksik ceviri Turkce'ye duser
  if (v === undefined) return key;             // hic yoksa anahtari goster (fark edilsin)
  return typeof v === "function" ? v(...args) : v;
}

// data-i18n / data-i18n-ph / data-i18n-title niteliklerini uygula
function applyStaticTexts(root) {
  const r = root || document;
  r.querySelectorAll("[data-i18n]").forEach((el) => { el.innerHTML = t(el.dataset.i18n); });
  r.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  r.querySelectorAll("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); });
}
