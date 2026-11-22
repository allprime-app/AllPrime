// AllPrime - Primer Tasarim Araci
// Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
//
// GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
// (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
// verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
// AllPrime - renderer
// Kullaniciya gorunen TUM metinler i18n.js'ten gelir; burada duz metin birakilmaz.
// Sayilar ARAYUZ diline gore bicimlenir: toLocaleString() yerel ayar verilmeden Windows
// ayarini kullaniyordu; Ingilizce arayuzde "Position: 7.676.059" yaziyordu (2026-10-31).
const yerel = () => (LANG === "en" ? "en-US" : "tr-TR");
let PORT = 5077;
let TOKEN = "";         // motor anahtari (main.js her acilista uretir)
let ASSEMBLY = "GRCh38";
let MODE = "dna";         // dna | rna | seq | bp | eval
let RNA_MODE = "variant"; // variant | skipping
let SEQ_MODE = "single";  // single | pair
let BP_MODE = "del";      // del | dup (kirilma noktasi sekmesi)
let lastResult = null;
// Sonuclar HANGI sekmede uretildi. Sekme degisince sonuc paneli eskiden
// kosulsuz gizleniyordu; kullanici bir primeri degerlendirip geri donunce
// tasarimi bastan yapmak zorunda kaliyordu. Artik sonuclar kendi sekmesine
// donuldugunde geri geliyor (icerik zaten DOM'da duruyordu).
let RESULT_TAB = null;
let HEALTH = null;

function setTab(mode) {
  MODE = mode;
  document.querySelectorAll(".tab").forEach((x) =>
    x.classList.toggle("active", x.dataset.tab === mode));
  $("panel-dna").classList.toggle("hidden", mode !== "dna");
  $("panel-rna").classList.toggle("hidden", mode !== "rna");
  $("panel-seq").classList.toggle("hidden", mode !== "seq");
  $("panel-bp").classList.toggle("hidden", mode !== "bp");
  $("panel-eval").classList.toggle("hidden", mode !== "eval");
  // Degerlendirme kendi butonunu kullanir; tasarim paneli gizlenir
  $("sharedPanel").classList.toggle("hidden", mode === "eval");
  // Serbest dizi modunda genomik koordinat yok -> dbSNP kacinmasi uygulanamaz
  $("box-snp").classList.toggle("hidden", mode === "seq");
  // Sonuclar yalnizca kendi sekmesinde gorunur
  $("results").classList.toggle("hidden", !lastResult || RESULT_TAB !== mode);
  mesajiTazele();
}

const PARAM_IDS = [
  "pcr_max", "product_min_gc", "product_max_gc",
  "product_size_min", "product_size_max", "min_dist_from_variant",
  "primer_min_size", "primer_opt_size", "primer_max_size",
  "primer_min_tm", "primer_max_tm", "primer_max_tm_diff",
  "primer_min_gc", "primer_max_gc", "primer_gc_clamp", "primer_max_end_gc", "primer_max_poly_x",
  "salt_monovalent", "salt_divalent", "dntp_conc", "dna_conc", "dmso_conc", "num_return",
];
// Degerlendir de tasarimla AYNI reaksiyon kosullariyla Tm hesaplasin (eskiden hep
// varsayilanlarla hesapliyordu; gelismis ayarlardaki tuz/DMSO yok sayiliyordu)
// (pcr_max: Degerlendir hedef urunu laboratuvarin sinirina gore de yorumlar)
const KOSUL_IDS = ["salt_monovalent", "salt_divalent", "dntp_conc", "dna_conc", "dmso_conc", "pcr_max"];

const $ = (id) => document.getElementById(id);
const api = (path) => `http://127.0.0.1:${PORT}${path}`;
// Motora giden HER istek buradan gecer: anahtar basligi eklenir; motor anahtarsiz
// istegi reddeder (tarayicidaki baska bir site yerel portu kullanamasin).
// Zaman asimi + iptal (inceleme bulgusu 15): motor takilirsa arayuz sonsuza dek
// "Hesaplaniyor" demesin, kullanici da beklemeyi birakabilsin (opts.signal).
// Iptal yalnizca BEKLEMEYI keser; motordaki hesap arka planda kendi biter.
const ZAMAN_ASIMI_MS = 5 * 60 * 1000;
const motor = (url, opts = {}) => {
  const sinyaller = [AbortSignal.timeout(ZAMAN_ASIMI_MS)];
  if (opts.signal) sinyaller.push(opts.signal);
  return fetch(url, {
    ...opts, signal: AbortSignal.any(sinyaller),
    headers: { ...(opts.headers || {}), "X-AllPrime-Token": TOKEN },
  });
};
// motor() hatasini kullaniciya gosterilecek metne cevir
const istekHatasi = (e) => e && e.name === "TimeoutError" ? t("msg.timeout")
  : e && e.name === "AbortError" ? t("msg.cancelled") : t("msg.error", e.message);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let APP_VERSION = "";      // arayuzun surumu (package.json); motorunkiyle karsilastirilir
// Laboratuvarin cogaltabildigi en uzun urun: diger gelismis ayarlar gibi her acilista
// varsayilana donmez, dil secimi gibi bu bilgisayarda kaydedilir (laboratuvar ozelligi).
let PCR_MAX_KAYIT = null;
// Ayarlar ekrani tercihleri (main.js bu bilgisayarda saklar). LAB_KAYIT: fabrika
// degerinden farkli kaydedilmis gelismis parametreler; bos nesne = fabrika degerleri.
let LAB_KAYIT = {};
let TEMA = "dark";
let BOYUT = 1;
let ACILIS_GENOM = "GRCh38";
// Gelismis parametreler bir kez, ilk saglik yanitinda doldurulur (bkz. loadHealth)
let PARAMS_DOLDU = false;
// Laboratuvar varsayilani olabilen parametreler; pcr_max kendi anahtariyla saklanir
const LAB_IDS = PARAM_IDS.filter((id) => id !== "pcr_max");

async function init() {
  if (window.allprime) {
    PORT = await window.allprime.getPort();
    TOKEN = await window.allprime.getToken();
    const info = await window.allprime.getAppInfo();
    setLangDict(info.lang || "tr");
    APP_VERSION = info.version || "";
    PCR_MAX_KAYIT = info.pcr_max || null;
    LAB_KAYIT = info.lab || {};
    TEMA = info.theme || "dark";
    BOYUT = info.zoom || 1;
    ACILIS_GENOM = info.assembly || "GRCh38";
  }
  // Acilistaki referans genom (Ayarlar); ust cubuktaki secim yalnizca bu oturum icin
  ASSEMBLY = ACILIS_GENOM;
  document.querySelectorAll(".seg-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.asm === ASSEMBLY));
  applyStaticTexts();
  syncLangButtons();
  loadLicenseText();
  await loadHealth();
  bindUI();
  favYukle();                    // favori listesi (sayac ve kart durumlari); motoru beklemez
}

// ---------------- dil ----------------
function syncLangButtons() {
  document.querySelectorAll(".lang-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.lang === LANG));
}

async function loadLicenseText() {
  if (!window.allprime) return;
  try {
    $("licenseBox").innerHTML = await window.allprime.getTerms(LANG);
  } catch (e) { /* lisans metni okunamazsa panel bos kalir */ }
}

async function switchLang(lang) {
  if (lang === LANG) return;
  setLangDict(lang);
  if (window.allprime) await window.allprime.setLang(lang);
  applyStaticTexts();
  syncLangButtons();
  ayarlariCiz();
  exonCiz();                     // ipucu ve ozet metinleri yeni dilde
  loadLicenseText();
  // Durum metinleri ve varsa sonuclar yeni dilde yeniden uretilir
  if (HEALTH) {
    updateGenomeStatus(HEALTH.genomes);
    updateAnnotStatus(HEALTH.annotations);
    updateSnpStatus(HEALTH.dbsnp);
    loadHealth();          // motorun urettigi uyari metinleri (genome_warnings) yeni dilde gelir
  }
  if (lastResult) {
    renderResults(lastResult);
    tasarimDiliniYenile();
  }
  if (lastEval && $("evalResult").innerHTML.trim()) {   // bos panel diriltilmez
    evalCiz(lastEval);
    degerlendirmeDiliniYenile();
  }
  if (document.body.classList.contains("fav-modu")) favListeyiCiz();
  mesajiTazele();
  if (EV_HATA) evalMsg(EV_HATA(), "error");     // arayuz hatasi yeni dilde yeniden yazilir
}

// Dil degisince motorun yazdigi metinler (notlar, uyarilar, bulgular) eski dilde
// kaliyordu, Degerlendir paneli hic yeniden cizilmiyordu (2026-10-29 hata taramasi):
// o metinler istek aninda motorda uretilir. Son istek AYNI govdeyle yeni dilde
// tekrarlanir ve yalnizca metinler tazelenir. Sessizdir: basarisiz olursa metinler
// eski dilde kalir, sonuc bozulmaz.
async function yeniDildeIste(istek) {
  const dil = LANG;
  const r = await motor(api(istek.path), {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...istek.body, lang: dil }),
  });
  const y = await okuJson(r);
  return (y.error || LANG !== dil) ? null : y;       // arada dil yine degistiyse at
}

async function tasarimDiliniYenile() {
  const j = lastResult, istek = lastIstek;
  if (!j || !istek || TASARIM_IPTAL) return;         // suren tasarim kendisi yeniler
  try {
    const y = await yeniDildeIste(istek);
    if (!y || lastResult !== j) return;              // arada yeni tasarim yapildi
    const imza = (x) => (x.pairs || [])
      .map((p) => `${p.forward?.sequence}/${p.reverse?.sequence}`).join();
    if (imza(y) !== imza(j)) return;                 // ayni sonuc degilse dokunulmaz
    Object.assign(j, y);     // ayni nesne kalir: arka plandaki ozgulluk taramasi kesilmez
    renderResults(j);
  } catch (e) { /* sessiz */ }
}

async function degerlendirmeDiliniYenile() {
  const j = lastEval, istek = lastEvalIstek;
  if (!j || !istek || EV_IPTAL) return;
  try {
    const y = await yeniDildeIste(istek);
    if (!y || lastEval !== j || !$("evalResult").innerHTML.trim()) return;
    lastEval = y;
    evalCiz(y);
  } catch (e) { /* sessiz */ }
}

// ---------------- durum ----------------
// Motorun cevabini JSON olarak oku; degilse ANLASILIR bir hata uret.
// Eski bir motor bilmedigi uca Flask'in HTML 404 sayfasini donuyor; onu
// .json() ile okumak "Unexpected token '<'" gibi anlamsiz bir hata veriyordu.
async function okuJson(r) {
  const tur = (r.headers.get("content-type") || "").toLowerCase();
  if (!tur.includes("application/json")) {
    if (r.status === 404) throw new Error(t("err.oldEngine"));
    throw new Error(t("err.notJson", r.status));
  }
  return r.json();
}

// Arayuzun calismak icin motorda bulunmasini BEKLEDIGI uclar. Motor bunlardan
// birini tanimiyorsa arayuz yeni, motor eskidir (klasor kopyalamada tipik).
const GEREKLI_UCLAR = ["/design", "/design_cdna", "/design_skipping",
  "/design_sequence", "/design_sequence_pair", "/design_breakpoint", "/specificity",
  "/evaluate", "/evaluate_cdna", "/downloads", "/transcripts", "/transcript_exons",
  "/kopya_ciftleri"];

function motorUyumu(h) {
  const kutu = $("engineWarn");
  if (!kutu) return;
  // Eski motorun /health'inde 'endpoints' alani hic yok - o da bir cevap
  const uclar = Array.isArray(h.endpoints) ? h.endpoints : null;
  // Eski motor listeyi hic vermez; o durumda "su uclar yok" diye tek tek
  // saymak yaniltici olur (tasarim uclari eski motorda da var). Sadece
  // "eski surum" de ve hangi sekmelerin etkilendigini soyle.
  const eksik = uclar ? GEREKLI_UCLAR.filter((u) => !uclar.includes(u)) : [];
  const eskiMotor = uclar === null;
  const surumFarki = h.version && APP_VERSION && h.version !== APP_VERSION;
  // Motor acik ama hesaplama cekirdegi (primer3) yuklenememis olabilir: Windows
  // Akilli Uygulama Denetimi ya da eksik kopyalanmis klasor. Eskiden bu durum
  // ancak tasarim dugmesine basinca "module 'primer3' has no attribute ..."
  // diye anlasiliyordu. Oncelik bunda: diger uyarilardan once gosterilir.
  if (h.primer3 && h.primer3.ok === false) {
    kutu.innerHTML = `<b>${t("engine.p3")}</b> ${esc(h.primer3.message || "")}`;
    kutu.classList.remove("hidden");
    return;
  }
  if (!eksik.length && !eskiMotor && !surumFarki) { kutu.classList.add("hidden"); return; }
  const parcalar = [];
  if (eskiMotor) parcalar.push(t("engine.old"));
  if (eksik.length) parcalar.push(t("engine.missing", eksik.join(", ")));
  if (surumFarki) parcalar.push(t("engine.versionDiff", h.version, APP_VERSION));
  kutu.innerHTML = `<b>${t("engine.mismatch")}</b> ${parcalar.join(" ")} ${t("engine.fix")}`;
  kutu.classList.remove("hidden");
  // Degerlendir motoru olmayan makinede sekmeyi de isaretle
  // Sekme yalnizca ucun YOKLUGU kesinse isaretlenir. Liste vermeyen motor
  // "bilinmiyor" demektir, "yok" degil - o motorda Degerlendir calisiyor olabilir.
  const evalTab = document.querySelector('.tab[data-tab="eval"]');
  if (evalTab && (eksik.includes("/evaluate") || eksik.includes("/evaluate_cdna"))) {
    evalTab.classList.add("tab-disabled");
    evalTab.title = t("engine.mismatch");
  }
}

async function loadHealth() {
  try {
    // lang: primer3 uyarisi gibi motorun urettigi metinler secili dilde gelsin
    const r = await motor(api(`/health?lang=${LANG}`));
    const h = await okuJson(r);
    HEALTH = h;
    // Gelismis parametreler YALNIZCA ilk yanitta doldurulur: laboratuvar varsayilani
    // varsa o, yoksa motorun fabrika degeri. Bu fonksiyon genom her degistiginde de
    // cagriliyor ve alanlari fabrika degerine donduruyordu; kullanicinin girdigi Mg /
    // DMSO sessizce kayboluyor, Tm fabrika kosuluyla hesaplaniyordu (2026-11-01,
    // olculdu: GRCh37'ye gecince Mg 2 -> 1,5, DMSO 5 -> 0).
    if (!PARAMS_DOLDU) {
      for (const id of PARAM_IDS) {
        const v = LAB_KAYIT[id] !== undefined ? LAB_KAYIT[id] : h.defaults[id];
        if (v !== undefined && $(id)) $(id).value = v;
      }
      if (PCR_MAX_KAYIT) $("pcr_max").value = PCR_MAX_KAYIT;
      PARAMS_DOLDU = true;
    }
    updateGenomeStatus(h.genomes);
    updateAnnotStatus(h.annotations);
    updateSnpStatus(h.dbsnp);
    motorUyumu(h);
    ayarlariCiz();
  } catch (e) {
    setMsg(t("msg.noEngine", e.message), "error");
  }
}

function updateGenomeStatus(genomes) {
  const dot = $("genomeStatus");
  const local = genomes && genomes[ASSEMBLY];
  dot.classList.toggle("local", !!local);
  dot.title = t(local ? "status.genomeLocal" : "status.genomeApi", ASSEMBLY);
  // Hesaplama cekirdegi calismiyorsa gosterge yesil KALMAMALI
  const p3 = HEALTH && HEALTH.primer3;
  const engelli = !!(HEALTH && HEALTH.genome_blocked && HEALTH.genome_blocked[ASSEMBLY]);
  dot.classList.toggle("bad", !!(p3 && p3.ok === false) || engelli);
  if (engelli) dot.title = (HEALTH.genome_warnings || {})[ASSEMBLY] || t("genome.warn.blocked", ASSEMBLY);
  if (p3 && p3.ok === false) dot.title = p3.message || t("engine.p3");
  genomUyarisiCiz();
}

// Motorun /health yanitindaki genome_warnings: secili derlemenin uyarisi ust bantta, her derlemeninki
// Ayarlar > Genom satirinda gorunur (kullanilamayan genom kirmizi, yalniz uyari sari)
function genomUyarisiCiz() {
  const h = HEALTH || {};
  const uyari = h.genome_warnings || {};
  const engel = h.genome_blocked || {};
  const kutu = $("genomeWarn");
  if (kutu) {
    const m = uyari[ASSEMBLY];
    kutu.classList.toggle("hidden", !m);
    kutu.classList.toggle("blocked", !!engel[ASSEMBLY]);
    kutu.innerHTML = m ? `<b>${t(engel[ASSEMBLY] ? "genome.warn.blocked" : "genome.warn.note", ASSEMBLY)}</b> ${esc(m)}` : "";
  }
  for (const a of ["GRCh38", "GRCh37"]) {
    const p = $("gwarn_" + a);
    if (!p) continue;
    p.classList.toggle("hidden", !uyari[a]);
    p.classList.remove("hint-error");
    p.classList.add("hint-warn");
    p.textContent = uyari[a] || "";
  }
}

// RNA sekmesi transkript tablosu olmadan calisamaz
function updateAnnotStatus(annot) {
  const ok = annot && annot[ASSEMBLY];
  const tab = document.querySelector('.tab[data-tab="rna"]');
  tab.classList.toggle("tab-disabled", !ok);
  tab.title = ok ? "" : t("status.rnaDisabled", ASSEMBLY);
}

// dbSNP tablosu yoksa kacinma yapilamaz - kullanici bunu bilmeli
function updateSnpStatus(status) {
  const ok = status && status[ASSEMBLY];
  const box = $("snpStatus");
  $("avoid_common_snps").disabled = !ok;
  box.textContent = ok ? "" : t("snp.missing", ASSEMBLY);
  box.className = "hint" + (ok ? "" : " hint-warn");
}

function bindUI() {
  document.querySelectorAll(".lang-btn").forEach((b) =>
    b.addEventListener("click", () => switchLang(b.dataset.lang)));

  // Laboratuvar siniri degisince kaydedilir; gecersiz deger (100 alti) kaydedilmez,
  // motor zaten anlasilir hata verir.
  $("pcr_max").addEventListener("change", () => {
    const v = parseInt($("pcr_max").value, 10);
    if (!(v >= 100)) return;
    PCR_MAX_KAYIT = v;
    if (window.allprime && window.allprime.setPcrMax) window.allprime.setPcrMax(v);
  });

  document.querySelectorAll(".seg-btn").forEach((b) => {
    b.addEventListener("click", () => {
      document.querySelectorAll(".seg-btn").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      ASSEMBLY = b.dataset.asm;
      loadHealth();
      exonVeriPlanla(true);
    });
  });

  document.querySelectorAll(".tab").forEach((tb) => {
    tb.addEventListener("click", () => setTab(tb.dataset.tab));
  });

  document.querySelectorAll(".seq-mode-btn").forEach((b) => {
    b.addEventListener("click", () => {
      document.querySelectorAll(".seq-mode-btn").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      SEQ_MODE = b.dataset.smode;
      $("seq-single").classList.toggle("hidden", SEQ_MODE !== "single");
      $("seq-pair").classList.toggle("hidden", SEQ_MODE !== "pair");
    });
  });

  document.querySelectorAll(".rna-mode-btn").forEach((b) => {
    b.addEventListener("click", () => {
      document.querySelectorAll(".rna-mode-btn").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      RNA_MODE = b.dataset.rmode;
      const skipping = RNA_MODE === "skipping";
      $("field-cpos").classList.toggle("hidden", skipping);
      $("field-exon").classList.toggle("hidden", !skipping);
      $("box-skip").classList.toggle("hidden", !skipping);
      // Sinir kutusu iki tipte de gorunur (ayni onay kutusu); yalniz aciklamasi degisir
      $("junctionHelp").classList.toggle("hidden", skipping);
      $("junctionHelpSkip").classList.toggle("hidden", !skipping);
      if (skipping) { exonCiz(); exonVeriPlanla(true); }
    });
  });

  document.querySelectorAll(".bp-mode-btn").forEach((b) => {
    b.addEventListener("click", () => {
      document.querySelectorAll(".bp-mode-btn").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      BP_MODE = b.dataset.bpmode;
      $("bp-help-del").classList.toggle("hidden", BP_MODE !== "del");
      $("bp-help-dup").classList.toggle("hidden", BP_MODE !== "dup");
    });
  });
  // "chr2:50,000,001-50,012,000" (genom tarayicisi / CNV raporu yazimi) tek
  // kutuya yapistirilirsa kromozom, baslangic ve bitise dagitilir.
  ["bp_start", "bp_chrom"].forEach((id) => $(id).addEventListener("input", () => {
    const m = $(id).value.trim().match(
      /^(?:chr)?([0-9]{1,2}|X|Y|MT?)\s*:\s*([\d.,]+)\s*[-–_]\s*([\d.,]+)$/i);
    if (!m) return;
    $("bp_chrom").value = m[1].toUpperCase();
    $("bp_start").value = m[2].replace(/[.,]/g, "");
    $("bp_end").value = m[3].replace(/[.,]/g, "");
  }));

  $("designBtn").addEventListener("click", runDesign);
  $("evalBtn").addEventListener("click", evalDugmesi);
  ["ev_fwd", "ev_rev"].forEach((id) =>
    $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") evalDugmesi(); }));
  $("exportBtn").addEventListener("click", exportCsv);
  // Otomatik ozgulluk tercihi bu bilgisayarda hatirlanir (varsayilan acik)
  try { $("autoSpec").checked = localStorage.getItem("allprime.autoSpec") !== "0"; } catch (e) {}
  $("autoSpec").addEventListener("change", () => {
    try { localStorage.setItem("allprime.autoSpec", $("autoSpec").checked ? "1" : "0"); } catch (e) {}
    if ($("autoSpec").checked && lastResult) otoOzgulluk(lastResult);
    else otoDurdur();
  });
  $("findTxBtn").addEventListener("click", findTranscripts);

  document.querySelectorAll(".ev-mode-btn").forEach((b) =>
    b.addEventListener("click", () => setEvalMode(b.dataset.emode)));
  $("evFindTxBtn").addEventListener("click", evFindTranscripts);
  $("ev_acc").addEventListener("keydown", (e) => {
    if (e.key === "Enter") evalDugmesi();
  });
  $("evTxList").addEventListener("click", (e) => {
    const row = e.target.closest(".tx-row");
    if (!row) return;
    $("ev_acc").value = row.dataset.acc;
    $("evTxList").classList.add("hidden");
    evalMsg("");
  });

  // Olay delegasyonu - dinamik satirlar icin
  $("pairs").addEventListener("click", (e) => {
    if (favKartTiklama(e)) return;          // favori dugmesi ve paneli (spec / amp dugmelerinden once)
    const copy = e.target.closest(".copy-btn");
    if (copy) { copyToClipboard(copy.dataset.seq, copy); return; }
    const low = e.target.closest(".spec-low-btn");
    if (low) { toggleSpecLow(parseInt(low.dataset.rank, 10), low); return; }
    const toEval = e.target.closest(".to-eval-btn");
    if (toEval) { pairToEvaluate(parseInt(toEval.dataset.rank, 10)); return; }
    const amp = e.target.closest(".amp-btn");
    if (amp) { toggleAmplicon(parseInt(amp.dataset.rank, 10), amp); return; }
    const spec = e.target.closest(".spec-btn");
    if (spec) runSpecificity(parseInt(spec.dataset.rank, 10), spec);
  });

  $("evalResult").addEventListener("click", (e) => {
    if (favKartTiklama(e)) return;
    const c = e.target.closest(".copy-btn");
    if (c) { copyToClipboard(c.dataset.seq, c); return; }
    const low = e.target.closest(".low-btn");
    if (low) { toggleLowProducts(low); return; }
    const amp = e.target.closest(".amp-btn");
    if (amp) toggleEvalAmplicon(amp);
  });

  $("txList").addEventListener("click", (e) => {
    const row = e.target.closest(".tx-row");
    if (!row) return;
    $("acc").value = row.dataset.acc;
    exonVeriPlanla(true);
    $("txList").classList.add("hidden");
    setMsg("");
  });

  document.querySelectorAll("[data-pick]").forEach((b) => {
    b.addEventListener("click", () => pickGenome(b.dataset.pick));
  });

  // Veri indirme paneli: acilinca yukle, kapaninca yoklamayi durdur
  $("dlPanel").addEventListener("toggle", () => {
    if ($("dlPanel").open) loadDownloads();
    else if (DL_TIMER) { clearInterval(DL_TIMER); DL_TIMER = null; }
  });
  $("dlList").addEventListener("click", (e) => {
    const s = e.target.closest(".dl-start");
    if (s) { startDownload(s.dataset.item); return; }
    const c = e.target.closest(".dl-cancel");
    if (c) cancelDownload(c.dataset.item);
  });

  ["gene", "chrom", "position", "acc", "c_position", "skip_exon",
   "bp_chrom", "bp_start", "bp_end", "bp_margin"].forEach((id) =>
    $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") runDesign(); })
  );
  $("gene_rna").addEventListener("keydown", (e) => {
    if (e.key === "Enter") findTranscripts();
  });
  // Ekson atlama: kod degisince (yazarak ya da listeden) ekson dugmeleri tazelenir
  $("acc").addEventListener("input", () => exonVeriPlanla(false));
  $("acc").addEventListener("change", () => exonVeriPlanla(true));
  $("skip_exon").addEventListener("input", exonCiz);
  $("exonBox").addEventListener("click", exonTikla);
  // Sinir kutusu degisince ozetteki "primerler nereye konur" satiri da degisir
  $("junction_overlap").addEventListener("change", exonCiz);
  exonCiz();

  // ---- Favoriler ekrani (2026-11-14) ----
  $("favAc").addEventListener("click", () =>
    document.body.classList.contains("fav-modu") ? favorilerKapat() : favorilerAc());
  $("favGeri").addEventListener("click", favorilerKapat);
  $("favAra").addEventListener("input", favListeyiCiz);
  $("favCsv").addEventListener("click", favCsvIndir);
  $("favListe").addEventListener("click", favListeTiklama);

  // ---- Ayarlar ekrani ----
  $("ayarAc").addEventListener("click", () =>
    document.body.classList.contains("ayar-modu") ? ayarlariKapat() : ayarlariAc());
  $("ayarGeri").addEventListener("click", ayarlariKapat);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.body.classList.contains("ayar-modu")) ayarlariKapat();
    // Not / silme sorusu acikken Escape yalniz onu kapatir (alanin kendi dinleyicisi)
    else if (e.key === "Escape" && document.body.classList.contains("fav-modu")
             && !e.target.closest(".fav-panel, .fav-not-duzen")) favorilerKapat();
  });
  $("ayarlarEkrani").addEventListener("click", (e) => {
    const b = e.target.closest(".ayar-btn");
    if (b) ayarSec(b.closest(".ayar-seg").dataset.ayar, b.dataset.deger);
  });
  // Ayarlar'daki sinir Gelismis parametrelerdekiyle ayni alan gibi davranir (ayni kayit)
  $("ayar_pcr_max").addEventListener("change", () => {
    $("pcr_max").value = $("ayar_pcr_max").value;
    $("pcr_max").dispatchEvent(new Event("change"));
  });
  $("pairs").addEventListener("click", (e) => {
    const b = e.target.closest("[data-kopya]");
    if (!b) return;
    const k = b.dataset.kopya;
    if (k === "ara") kopyaAra(lastResult);
    else if (k === "hepsi") { KOPYA.hepsi = true; kopyaCiz(lastResult); }
    else if (k === "git") kopyaGit();
    else kopyaDegerlendir(k);
  });
  $("labKaydet").addEventListener("click", labKaydet);
  $("labKaydetAdv").addEventListener("click", labKaydet);
  $("labSifirla").addEventListener("click", labSifirla);
  // Ctrl + / Ctrl - / Ctrl 0 (main.js kaydeder): secili boyut dugmesi de degissin
  if (window.allprime && window.allprime.onZoomChanged) {
    window.allprime.onZoomChanged((v) => { BOYUT = v; ayarlariCiz(); });
  }
  // Alt bilgideki "Ayarlar > Hakkinda" baglantisi lisans metnini acar
  document.querySelector(".app-footer").addEventListener("click", (e) => {
    if (!e.target.closest("a.ayar-git")) return;
    e.preventDefault();
    ayarlariAc();
    $("licensePanel").open = true;
    $("licensePanel").scrollIntoView({ block: "start" });
  });
}

// ---------------- ayarlar ----------------
function ayarlariAc() {
  if (document.body.classList.contains("fav-modu")) favorilerKapat();
  document.body.classList.add("ayar-modu");
  $("ayarAc").classList.add("active");
  $("ayarMsg").textContent = "";
  ayarlariCiz();
  window.scrollTo(0, 0);
}

function ayarlariKapat() {
  document.body.classList.remove("ayar-modu");
  $("ayarAc").classList.remove("active");
}

// ---------------- favoriler (2026-11-14) ----------------
// Kullanici istegi: "kullanacagim primeri kaydedebilecegim bir alan" / "Favorilere ekle gibi bi
// sey". Liste main.js'te (electron/favoriler.js; yalniz bu bilgisayarda, userData\favoriler.json);
// burada kaydin kurulmasi ve gosterim. Kayit kartta GORUNEN adlarla tutulur (eksi iplikteki gende
// F/R genin yonunde). Ayni cift ikinci kez eklenmez; kartlardaki "Favorilerde" durumu anahtarla
// bulunur - favoriler.js anahtar() ile AYNI ifade (test_smoke denetler).
let FAVORILER = [];
let FAV_HATA = null;          // liste okunamadiysa sebep: "bozuk" / "okunamadi"
const favVar = () => !!(window.allprime && window.allprime.favAdd);
const favAnahtar = (k) => [k.tur, k.derleme || "", ...k.primerler.map((p) => p.rol + ":" + p.dizi.toUpperCase())].join("|");
// Degerlendir kaydi (v0.8.66): anahtar tam tutmasa da ayni derlemede ayni Forward + Reverse dizisini
// tasiyan kayit (tasarim kaydi da olabilir; "Degerlendir'de ac") favoride sayilir: ikinci kez eklenmez,
// dugme "Favorilerde" der, cikarma o kaydi siler. Anahtar degismez (favoriler.js anahtar() ile ayni).
const favBul = (k) => {
  const a = favAnahtar(k);
  const tam = FAVORILER.find((x) => favAnahtar(x) === a);
  if (tam || !String(k.tur).startsWith("degerlendir_")) return tam || null;
  const dizi = (x, rol) => ((x.primerler || []).find((p) => p.rol === rol) || {}).dizi;
  const F = dizi(k, "forward"), R = dizi(k, "reverse");
  if (!F || !R) return null;
  const ayni = (a1, b1) => typeof a1 === "string" && a1.toUpperCase() === b1.toUpperCase();
  return FAVORILER.find((x) => (x.derleme || "") === (k.derleme || "")
    && ayni(dizi(x, "forward"), F) && ayni(dizi(x, "reverse"), R)) || null;
};
const favSayi = (n) => (typeof n === "number" ? n.toLocaleString(yerel()) : "");

// Kart ve Degerlendir dugmesi; durumu (Favorilerde mi) cizimden sonra favDurumlariniCiz yazar
const favDugmesi = (veri, kap = "") => {
  if (!favVar()) return "";
  const d = `<button class="fav-btn" ${veri} title="${t("fav.add.title")}">${t("fav.add")}</button>`;
  return kap ? `<div class="${kap}">${d}</div>` : d;
};

async function favYukle() {
  if (!favVar()) return;
  try {
    const r = await window.allprime.favList();
    FAVORILER = r.kayitlar || [];
    FAV_HATA = r.hata || null;
  } catch (e) {
    FAVORILER = [];
    FAV_HATA = "okunamadi";
  }
  favSayaciCiz();
  favDurumlariniCiz();
  if (document.body.classList.contains("fav-modu")) favListeyiCiz();
}

function favSayaciCiz() {
  const s = $("favSayac");
  s.textContent = FAVORILER.length ? FAVORILER.length.toLocaleString(yerel()) : "";
  s.classList.toggle("hidden", !FAVORILER.length);
}

const FAV_TURLERI = { cdna: "cdna", exon_skipping: "atlama", sequence: "dizi",
  sequence_pair: "dizi_cift", breakpoint: "kirilma" };

// Tasarim cifti -> kayit. Genomik modlarda (DNA, Kirilma noktasi) kartta gorunen F/R (genYonunde).
function favTasarimKaydi(j, p) {
  const tur = FAV_TURLERI[j.mode] || "dna";
  const genomik = tur === "dna" || tur === "kirilma";
  const rna = tur === "cdna" || tur === "atlama";
  const v = genomik ? genYonunde(p) : p;
  const konum = (x) => genomik ? { tur: "genomik", bas: x.genomic_start, bit: x.genomic_end }
    : rna ? { tur: "cdna", bas: x.cdna_start, bit: x.cdna_end, ekson: (x.exons || []).join("/") }
    : { tur: "dizi", bas: x.seq_start, bit: x.seq_end, bolum: x.region || "" };
  const pr = (rol, x) => ({ rol, dizi: x.sequence, uzunluk: x.length, tm: x.tm, gc: x.gc, konum: konum(x) });
  const primerler = [pr("forward", v.forward), pr("reverse", v.reverse)];
  const k = p.control;
  if (k) {
    // Kontrolun esi kartta gorunen adla: eksi iplikte genomik F "reverse" gorunur
    const esR = (k.pairs_with === "reverse") !== (v !== p);
    primerler.push({ ...pr("control", k), es: esR ? "reverse" : "forward" });
  }
  const i = j.input || {};
  const tx = j.transcript || {};
  const girdi = tur === "dna"
    ? { chrom: i.chrom, position: i.position, position_end: i.position_end > i.position ? i.position_end : null }
    : tur === "kirilma" ? { chrom: i.chrom, start: i.start, end: i.end, type: i.type, margin: i.margin || null }
    : tur === "cdna" ? { acc: tx.mane_acc || tx.acc || i.acc, c_label: i.c_label || i.c_position }
    : tur === "atlama" ? { acc: tx.mane_acc || tx.acc || i.acc, exons: i.exons || i.exon }
    : tur === "dizi" ? { length: i.length, target: i.target || null } : {};
  const urun = { ta: p.ta_suggested };
  if (tur === "kirilma") {
    const b = p.bp || {};
    if (i.type === "del") Object.assign(urun, { kirilma_min: b.mut_min, kirilma_max: b.mut_max, normal_alel: b.wt });
    else if (i.approach === "tandem_junction") Object.assign(urun, { birlesim_min: b.junction_min, birlesim_max: b.junction_max });
    else Object.assign(urun, { normal: b.wt, dup_min: b.dup_min, dup_max: b.dup_max });
    if (k) urun.kontrol = k.band;
  } else if (tur === "atlama") {
    Object.assign(urun, { normal: p.product_size_normal, atlanmis: p.product_size_skipped, fark: p.band_difference });
  } else {
    Object.assign(urun, { boy: p.product_size, gdna: rna && sinirdaPrimer(p) ? null : p.gdna_product_size });
  }
  return { tur, derleme: genomik || rna ? (i.assembly || ASSEMBLY) : "",
    gen: p.strand_gene || tx.gene || (v.forward.gene_region || {}).gene || "",
    girdi, urun, primerler, surum: APP_VERSION };
}

// Degerlendir sonucu -> kayit (primerler kullanicinin girdigi gibi; hedef urun varsa boyu)
function favDegerlendirKaydi(j) {
  const cdna = j.mode === "cdna";
  const g = (lastEvalIstek && lastEvalIstek.body) || {};
  const tx = j.transcript || {};
  const pr = (rol, m) => ({ rol, dizi: m.sequence, uzunluk: m.length, tm: m.tm, gc: m.gc });
  const primerler = [pr("forward", j.primers.forward)];
  if (j.primers.reverse) primerler.push(pr("reverse", j.primers.reverse));
  const hedef = (j.products || []).find((o) => o.risk === "hedef");
  return {
    tur: cdna ? "degerlendir_cdna" : "degerlendir_dna",
    derleme: (cdna ? j.assembly : g.assembly) || ASSEMBLY,
    gen: cdna ? (tx.gene || "") : ((hedef && Array.isArray(hedef.genes) && hedef.genes[0]) || ""),
    girdi: { acc: cdna ? (tx.mane_acc || tx.acc || g.acc) : null, target: g.target || null },
    urun: { ta: j.pair ? j.pair.ta_suggested : null, boy: hedef ? hedef.size : null },
    primerler, surum: APP_VERSION,
  };
}

function favDugmeDurumu(b, kayit) {
  b.classList.toggle("fav-on", !!kayit);
  b.textContent = t(kayit ? "fav.in" : "fav.add");
  b.title = t(kayit ? "fav.in.title" : "fav.add.title");
}

function favDurumlariniCiz() {
  const j = lastResult;
  document.querySelectorAll("#pairs .fav-btn").forEach((b) => {
    const p = j && (j.pairs || []).find((x) => x.rank === parseInt(b.dataset.rank, 10));
    favDugmeDurumu(b, p ? favBul(favTasarimKaydi(j, p)) : null);
  });
  const e = document.querySelector("#evalResult .fav-btn");
  if (e && lastEval && lastEval.primers) favDugmeDurumu(e, favBul(favDegerlendirKaydi(lastEval)));
}

// Panelin ait oldugu cift / Degerlendir sonucu -> kayit
function favPaneldenKayit(panel) {
  if (panel.dataset.ev) return lastEval && lastEval.primers ? favDegerlendirKaydi(lastEval) : null;
  const j = lastResult;
  const p = j && (j.pairs || []).find((x) => x.rank === parseInt(panel.dataset.rank, 10));
  return p ? favTasarimKaydi(j, p) : null;
}

// Karttaki (ve Degerlendir'deki) favori dugmesi ve paneli. Ele aldiysa true.
function favKartTiklama(e) {
  const b = e.target.closest(".fav-btn");
  if (b) { favPanelAc(b); return true; }
  const k = e.target.closest(".fav-kaydet");
  if (k) { favKaydet(k); return true; }
  const c = e.target.closest(".fav-cikar");
  if (c) { favCikar(c); return true; }
  const v = e.target.closest(".fav-vazgec");
  if (v) { v.closest(".fav-panel").remove(); return true; }
  return false;
}

// Dugmeye basinca: favoride degilse not alani + Kaydet, favorideyse cikarma sorusu.
// Ikinci basis paneli kapatir.
function favPanelAc(b) {
  const kap = b.closest(".spec-wrap, .fav-ev");
  const eski = kap.querySelector(".fav-panel");
  if (eski) { eski.remove(); return; }
  kap.querySelectorAll(".fav-mesaj").forEach((m) => m.remove());
  const panel = document.createElement("div");
  panel.className = "fav-panel";
  panel.dataset.rank = b.dataset.rank || "";
  panel.dataset.ev = b.dataset.ev || "";
  const kayit = favPaneldenKayit(panel);
  if (!kayit) return;
  if (favBul(kayit)) {
    panel.innerHTML = `<p>${esc(t("fav.remove.q"))}</p>
      <div class="fav-panel-alt"><button class="fav-cikar">${t("fav.remove")}</button>
      <button class="fav-vazgec">${t("fav.cancel")}</button></div>`;
  } else {
    panel.innerHTML = `<label>${t("fav.note.label")}</label>
      <input type="text" class="fav-not-girdi" maxlength="500" placeholder="${esc(t("fav.note.ph"))}">
      <div class="fav-panel-alt"><button class="fav-kaydet">${t("fav.save")}</button>
      <button class="fav-vazgec">${t("fav.cancel")}</button>
      <small>${esc(t("fav.note.privacy"))}</small></div>`;
  }
  kap.insertBefore(panel, kap.querySelector(".amp-result, .spec-result"));
  const g = panel.querySelector("input");
  if (g) {
    g.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") favKaydet(panel.querySelector(".fav-kaydet"));
      else if (ev.key === "Escape") panel.remove();
    });
    g.focus();
  }
}

// Kartin altinda kisa mesaj (zaten favoride, yedek, hata); favoriler ekranindaysa ustte
function favUyari(mesaj, hata, kap) {
  if (!mesaj) return;
  if (!kap) {
    $("favMsg").textContent = mesaj;
    $("favMsg").className = "msg" + (hata ? " error" : "");
    return;
  }
  kap.querySelectorAll(".fav-mesaj").forEach((m) => m.remove());
  const p = document.createElement("p");
  p.className = "note fav-mesaj" + (hata ? " note-warn" : "");
  p.textContent = mesaj;
  kap.insertBefore(p, kap.querySelector(".amp-result, .spec-result"));
}

// main cagrisi: listeyi gunceller, hata / yedek / "zaten var" mesajini yazar; basarida sonucu doner
async function favCagir(f, kap) {
  let r;
  try {
    r = await f();
  } catch (e) {
    r = { ok: false, hata: "yazilamadi" };
  }
  if (r && Array.isArray(r.kayitlar)) {
    FAVORILER = r.kayitlar;
    FAV_HATA = null;
  }
  favSayaciCiz();
  favDurumlariniCiz();
  const basarili = !!(r && r.ok);
  const mesaj = !basarili ? t("fav.err." + ((r && r.hata) || "yazilamadi"))
    : r.yedek ? t("fav.backup", r.yedek) : r.zatenVar ? t("fav.already") : "";
  favUyari(mesaj, !basarili, kap);
  if (document.body.classList.contains("fav-modu")) favListeyiCiz();
  return basarili ? r : null;
}

async function favKaydet(btn) {
  if (!btn || btn.disabled) return;
  const panel = btn.closest(".fav-panel");
  const kap = panel.parentElement;
  const kayit = favPaneldenKayit(panel);
  if (!kayit) { panel.remove(); return; }
  kayit.not = panel.querySelector(".fav-not-girdi").value;
  btn.disabled = true;
  const r = await favCagir(() => window.allprime.favAdd(kayit), kap);
  if (r) panel.remove();
  else btn.disabled = false;
}

async function favCikar(btn) {
  const panel = btn.closest(".fav-panel");
  const kap = panel.parentElement;
  const kayit = favPaneldenKayit(panel);
  const var_ = kayit && favBul(kayit);
  panel.remove();
  if (var_) await favCagir(() => window.allprime.favRemove(var_.id), kap);
}

// ---- Favoriler ekrani ----
function favorilerAc() {
  if (document.body.classList.contains("ayar-modu")) ayarlariKapat();
  document.body.classList.add("fav-modu");
  $("favAc").classList.add("active");
  $("favMsg").textContent = "";
  favListeyiCiz();
  window.scrollTo(0, 0);
  favYukle();                 // baska pencerede degismis olabilir (ikinci kopya acilmaz ama dosya elle)
}

function favorilerKapat() {
  document.body.classList.remove("fav-modu");
  $("favAc").classList.remove("active");
}

function favTurAdi(k) {
  return k.tur === "kirilma"
    ? t((k.girdi || {}).type === "dup" ? "fav.kind.kirilma.dup" : "fav.kind.kirilma.del")
    : t("fav.kind." + k.tur);
}

function favGirdiMetni(k) {
  const g = k.girdi || {};
  const hedef = g.target ? `${t("fav.target")} ${g.target}` : "";
  switch (k.tur) {
    case "dna":
      return g.chrom ? `chr${g.chrom}:${favSayi(g.position)}${g.position_end ? "–" + favSayi(g.position_end) : ""}` : "";
    case "kirilma":
      return g.chrom ? `chr${g.chrom}:${favSayi(g.start)}–${favSayi(g.end)}${g.margin ? ` · ${t("fav.margin")} ±${favSayi(g.margin)} bp` : ""}` : "";
    case "cdna":
      return [g.acc, g.c_label].filter(Boolean).join(" ");
    case "atlama":
      return [g.acc, g.exons ? `Δ${g.exons}` : ""].filter(Boolean).join(" ");
    case "dizi":
      return [g.length ? `${favSayi(g.length)} bp` : "", hedef].filter(Boolean).join(" · ");
    default:                  // Degerlendir
      return [g.acc, hedef].filter(Boolean).join(" · ");
  }
}

// Urun / bant ozeti: kartlardaki cip adlariyla (ayni sey iki adla gorunmesin)
function favUrunMetni(k) {
  const u = k.urun || {};
  const bp = (x) => `<b>${favSayi(x)} bp</b>`;
  const aralik = (a, z) => `<b>${a === z ? favSayi(a) : favSayi(a) + "–" + favSayi(z)} bp</b>`;
  const parca = [];
  if (u.kirilma_min != null) parca.push(`${t("bp.chip.mut")} ${aralik(u.kirilma_min, u.kirilma_max)}`);
  if (u.normal_alel != null) parca.push(`${t("bp.chip.wt")} ${favSayi(u.normal_alel)} bp`);
  if (u.birlesim_min != null) parca.push(`${t("bp.chip.junction")} ${aralik(u.birlesim_min, u.birlesim_max)}`);
  if (u.dup_min != null) {
    parca.push(`${t("bp.chip.wtShort")} ${bp(u.normal)}`, `${t("bp.chip.dupBand")} ${aralik(u.dup_min, u.dup_max)}`);
  } else if (u.normal != null) {
    parca.push(`${t("chip.normal")} ${bp(u.normal)}`);
  }
  if (u.atlanmis != null) parca.push(`${t("chip.skipped")} ${bp(u.atlanmis)}`);
  if (u.boy != null) parca.push(`${t(k.tur === "cdna" ? "chip.cdnaProduct" : "chip.amplicon")} ${bp(u.boy)}`);
  if (u.gdna != null) parca.push(`${t("chip.gdna")} ${favSayi(u.gdna)} bp`);
  if (u.kontrol != null) parca.push(`${t("bp.chip.control")} ${bp(u.kontrol)}`);
  if (u.ta != null) parca.push(`${t("chip.ta")} <b>${favSayi(u.ta)} °C</b>`);
  return parca.join(" · ");
}

function favKonumMetni(p) {
  const kn = p.konum;
  if (!kn) return "—";
  const aralik = `${favSayi(kn.bas)}–${favSayi(kn.bit)}`;
  if (kn.tur === "cdna") return `${aralik} (cDNA${kn.ekson ? " · " + t("csv.exon") + " " + kn.ekson : ""})`;
  if (kn.bolum) return `${t(kn.bolum === "F" ? "seq.region1" : "seq.region2")} · ${aralik}`;
  return aralik;
}

function favKayitHtml(k) {
  const ad = { forward: "dir.forward", reverse: "dir.reverse", control: "bp.dir.control" };
  const cls = { forward: "dir-f", reverse: "dir-r", control: "dir-k" };
  const satir = (p) => `<tr>
      <td class="${cls[p.rol]}"${p.es ? ` title="${esc(t("fav.controlWith", t("dir." + p.es).toLowerCase()))}"` : ""}>${t(ad[p.rol])}</td>
      ${seqCell({ sequence: p.dizi })}
      <td class="sayi">${p.uzunluk}</td><td class="sayi">${p.tm ?? "—"}</td><td class="sayi">${p.gc ?? "—"}</td>
      <td>${esc(favKonumMetni(p))}</td></tr>`;
  const tarih = new Date(k.tarih).toLocaleString(yerel(), { dateStyle: "short", timeStyle: "short" });
  const girdi = favGirdiMetni(k);
  // Genomik kayitta (DNA, Kirilma noktasi) primerlerin araligi IGV icin kopyalanabilir
  const gk = k.primerler.filter((p) => p.konum && p.konum.tur === "genomik");
  const konum = gk.length && (k.girdi || {}).chrom
    ? konumCipi(k.girdi.chrom, Math.min(...gk.map((p) => p.konum.bas)), Math.max(...gk.map((p) => p.konum.bit)), k.derleme)
    : "";
  return `
    <div class="fav-kayit" data-id="${esc(k.id)}">
      <div class="fav-bas">
        <span class="fav-gen">${esc(k.gen || "—")}</span>
        <span class="chip">${esc(favTurAdi(k))}</span>
        ${k.derleme ? `<span class="chip">${esc(k.derleme)}</span>` : ""}
        ${girdi ? `<span class="chip">${esc(girdi)}</span>` : ""}
        ${konum}
        <span class="fav-tarih">${esc(tarih)}${k.surum ? " · AllPrime " + esc(k.surum) : ""}</span>
      </div>
      <table class="primer-table"><thead><tr><th>${t("th.dir")}</th><th>${t("th.seq")}</th>
        <th class="sayi">${t("th.nt")}</th><th class="sayi">${t("th.tm")}</th><th class="sayi">${t("th.gc")}</th>
        <th>${t("th.pos")}</th></tr></thead>
        <tbody>${k.primerler.map(satir).join("")}</tbody></table>
      <div class="fav-urun">${favUrunMetni(k)}</div>
      <div class="fav-notu${k.not ? "" : " bos"}">${k.not ? `<b>${t("fav.noteLabel")}:</b> ${esc(k.not)}` : esc(t("fav.noNote"))}</div>
      <div class="fav-eylem">
        ${k.tur === "kirilma" ? "" : `<button class="fav-deg" title="${esc(t("fav.toEval.title"))}">${t("fav.toEval")}</button>`}
        <button class="fav-not-ac">${t("fav.editNote")}</button>
        <button class="fav-sil">${t("fav.delete")}</button>
      </div>
    </div>`;
}

const favAramaMetni = (k) => [k.gen, favTurAdi(k), k.derleme, favGirdiMetni(k), k.not,
  ...k.primerler.map((p) => p.dizi)].join(" ").toLocaleLowerCase(yerel());

function favListeyiCiz() {
  const ara = $("favAra").value.trim().toLocaleLowerCase(yerel());
  const liste = ara ? FAVORILER.filter((k) => favAramaMetni(k).includes(ara)) : FAVORILER;
  $("favOzet").textContent = ara && FAVORILER.length
    ? t("fav.countFiltered", liste.length, FAVORILER.length) : t("fav.count", FAVORILER.length);
  $("favCsv").disabled = !FAVORILER.length;
  if (FAV_HATA) favUyari(t("fav.err." + FAV_HATA), true);
  $("favListe").innerHTML = !FAVORILER.length ? `<div class="panel fav-bos">${t("fav.empty")}</div>`
    : !liste.length ? `<div class="panel fav-bos">${esc(t("fav.noMatch"))}</div>`
    : liste.map(favKayitHtml).join("");
}

function favListeTiklama(e) {
  const c = e.target.closest(".copy-btn");
  if (c) { copyToClipboard(c.dataset.seq, c); return; }
  const kart = e.target.closest(".fav-kayit");
  if (!kart) return;
  const id = kart.dataset.id;
  if (e.target.closest(".fav-deg")) { favDegerlendir(id); return; }
  if (e.target.closest(".fav-not-ac")) { favNotDuzenle(kart, id); return; }
  if (e.target.closest(".fav-sil")) { favSilSor(kart); return; }
  if (e.target.closest(".fav-sil-evet")) {
    favCagir(() => window.allprime.favRemove(id));
    return;
  }
  if (e.target.closest(".fav-not-kaydet")) {
    const g = kart.querySelector(".fav-not-duzen input");
    favCagir(() => window.allprime.favNote(id, g.value));
    return;
  }
  if (e.target.closest(".fav-vazgec")) favListeyiCiz();
}

function favSilSor(kart) {
  if (kart.querySelector(".fav-panel")) return;
  const d = document.createElement("div");
  d.className = "fav-panel";
  d.innerHTML = `<p>${esc(t("fav.delete.q"))}</p>
    <div class="fav-panel-alt"><button class="fav-sil-evet">${t("fav.delete")}</button>
    <button class="fav-vazgec">${t("fav.cancel")}</button></div>`;
  kart.appendChild(d);
  d.querySelector(".fav-vazgec").focus();
}

function favNotDuzenle(kart, id) {
  const k = FAVORILER.find((x) => x.id === id);
  const yer = kart.querySelector(".fav-notu");
  if (!k || !yer || kart.querySelector(".fav-not-duzen")) return;
  const d = document.createElement("div");
  d.className = "fav-not-duzen";
  d.innerHTML = `<input type="text" maxlength="500" placeholder="${esc(t("fav.note.ph"))}">
    <div class="fav-panel-alt"><button class="fav-not-kaydet">${t("fav.save")}</button>
    <button class="fav-vazgec">${t("fav.cancel")}</button>
    <small>${esc(t("fav.note.privacy"))}</small></div>`;
  yer.replaceWith(d);
  const g = d.querySelector("input");
  g.value = k.not || "";
  g.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") favCagir(() => window.allprime.favNote(id, g.value));
    else if (ev.key === "Escape") favListeyiCiz();
  });
  g.focus();
}

// Kayitli cifti Degerlendir'de ac. Genomik kayitta ust cubuktaki referans genom kaydin genomuna
// gecer: GRCh37'de kaydedilmis cift GRCh38'de degerlendirilirse koordinat ve urun yanlis olurdu.
// RNA kayitlari zaten GRCh38 / MANE ile degerlendirilir; ust cubuk degismez.
function favDegerlendir(id) {
  const k = FAVORILER.find((x) => x.id === id);
  if (!k || k.tur === "kirilma") return;
  const f = k.primerler.find((p) => p.rol === "forward");
  const r = k.primerler.find((p) => p.rol === "reverse");
  const cdna = k.tur === "cdna" || k.tur === "atlama" || k.tur === "degerlendir_cdna";
  const g = k.girdi || {};
  favorilerKapat();
  if (!cdna && k.derleme && k.derleme !== ASSEMBLY) {
    const b = document.querySelector(`.seg-btn[data-asm="${k.derleme}"]`);
    if (b) b.click();
  }
  $("ev_fwd").value = f ? f.dizi : "";
  $("ev_rev").value = r ? r.dizi : "";
  $("ev_hedef").value = k.tur === "dna"
    ? (g.chrom && g.position ? `chr${g.chrom}:${g.position}${g.position_end ? "-" + g.position_end : ""}` : "")
    : k.tur === "cdna" ? (g.c_label || "")
    : k.tur.startsWith("degerlendir") ? (g.target || "") : "";
  if (cdna) $("ev_acc").value = g.acc || "";
  setEvalMode(cdna ? "cdna" : "dna");
  setTab("eval");
  runEvaluate();
}

// Listenin tamami CSV: her primer bir satir (siparis listesine aktarmaya uygun). Konum iki sayi sutunu
// (oteki CSV'ler gibi; tek hucrede "5-24" Excel'de tarihe donuyordu, v0.8.66). Not ve gen gibi
// serbest metinler "=", "+", "-", "@" ile baslarsa basina ' konur: Excel formul olarak calistirmasin.
function favCsvIndir() {
  const guvenli = (s) => (/^[=+\-@]/.test(String(s)) ? "'" + s : s);
  const duz = (s) => String(s).replace(/<[^>]+>/g, "");
  const tarih = (iso) => {
    const d = new Date(iso);
    const iki = (x) => String(x).padStart(2, "0");
    return `${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())} ${iki(d.getHours())}:${iki(d.getMinutes())}`;
  };
  const ad = { forward: "dir.forward", reverse: "dir.reverse", control: "bp.dir.control" };
  const rows = [CSV.satir(H("favNo", "favDate", "favKind", "assembly", "favGene", "favInput", "dir", "seq",
    "len", "tm", "gc", "posStart", "posEnd", "favProduct", "favTa", "favNote", "favVersion"))];
  FAVORILER.forEach((k, n) => {
    for (const p of k.primerler) {
      const kn = p.konum;
      rows.push(CSV.satir([n + 1, tarih(k.tarih), favTurAdi(k), k.derleme, guvenli(k.gen), guvenli(favGirdiMetni(k)),
        t(ad[p.rol]), p.dizi, p.uzunluk, p.tm, p.gc, kn ? kn.bas : "", kn ? kn.bit : "",
        duz(favUrunMetni(k)), k.urun && k.urun.ta != null ? k.urun.ta : "", guvenli(k.not), k.surum]));
    }
  });
  downloadCsv(rows, "AllPrime_favoriler");
}

// Secili dugmeler, ayna alan ve dile bagli icerik (laboratuvar ozeti, Hakkinda)
function ayarlariCiz() {
  const secili = { tema: TEMA, boyut: String(BOYUT), dil: LANG, genom: ACILIS_GENOM };
  document.querySelectorAll("#ayarlarEkrani .ayar-seg").forEach((seg) =>
    seg.querySelectorAll(".ayar-btn").forEach((b) =>
      b.classList.toggle("active", b.dataset.deger === secili[seg.dataset.ayar])));
  document.querySelectorAll('.ayar-seg[data-ayar="boyut"] .ayar-btn').forEach((b) => {
    b.textContent = t("fmt.pct", Math.round(Number(b.dataset.deger) * 100));
  });
  $("ayar_pcr_max").value = $("pcr_max").value;
  $("labYardim").textContent = t("set.params.help", LAB_IDS.length);
  labOzetCiz();
  hakkindaCiz();
}

async function ayarSec(ayar, deger) {
  if (ayar === "dil") return switchLang(deger);
  const k = window.allprime;
  if (!k) return;
  if (ayar === "tema") TEMA = (await k.setTheme(deger)) || TEMA;
  if (ayar === "boyut") BOYUT = (await k.setZoom(Number(deger))) || BOYUT;
  if (ayar === "genom") ACILIS_GENOM = (await k.setDefaultAssembly(deger)) || ACILIS_GENOM;
  ayarlariCiz();
}

// Kayitli laboratuvar varsayilanlarindan fabrika degerinden farkli olanlar
function labOzetCiz() {
  const fabrika = (HEALTH && HEALTH.defaults) || {};
  const sayi = (v) => Number(v).toLocaleString(yerel());
  const farkli = LAB_IDS.filter((id) =>
    LAB_KAYIT[id] !== undefined && Number(LAB_KAYIT[id]) !== Number(fabrika[id]));
  $("labOzet").innerHTML = !farkli.length ? `<p class="lab-yok">${t("set.params.none")}</p>`
    : `<table class="lab-ozet"><thead><tr><th>${t("set.params.name")}</th>` +
      `<th class="sayi">${t("set.params.saved")}</th><th class="sayi">${t("set.params.factory")}</th></tr></thead><tbody>` +
      farkli.map((id) => `<tr><td>${t("adv." + id)}</td><td class="sayi"><b>${sayi(LAB_KAYIT[id])}</b></td>` +
        `<td class="sayi">${fabrika[id] === undefined ? "-" : sayi(fabrika[id])}</td></tr>`).join("") +
      "</tbody></table>";
}

// Gelismis parametrelerdeki degerler laboratuvar varsayilani olur. Yalnizca fabrika
// degerinden farkli olanlar saklanir: fabrika degeri ileride degisirse geri kalanlar
// onu kendiliginden izler.
async function labKaydet() {
  if (!window.allprime || !HEALTH) return;
  const yeni = {};
  for (const id of LAB_IDS) {
    const v = $(id).value.trim();
    if (v !== "" && Number.isFinite(Number(v)) && Number(v) !== Number(HEALTH.defaults[id])) yeni[id] = Number(v);
  }
  const kayit = await window.allprime.setLabDefaults(yeni);
  if (!kayit) { setMsg(t("set.params.fail"), "error"); return; }
  LAB_KAYIT = kayit;
  labOzetCiz();
  setMsg(t("set.params.done", Object.keys(kayit).length), "ok");
}

// Kayit silinir, alanlar fabrika degerine doner (pcr_max kendi alaninda, dokunulmaz)
async function labSifirla() {
  if (!window.allprime || !HEALTH) return;
  if (!(await window.allprime.setLabDefaults({}))) { setMsg(t("set.params.fail"), "error"); return; }
  LAB_KAYIT = {};
  for (const id of LAB_IDS) if (HEALTH.defaults[id] !== undefined) $(id).value = HEALTH.defaults[id];
  labOzetCiz();
  setMsg(t("set.params.resetDone"), "ok");
}

// Hakkinda: surum ve yuklu veri dosyalari (laboratuvar kalite belgeleri icin)
function hakkindaCiz() {
  const h = HEALTH;
  if (!h) { $("hakkinda").innerHTML = ""; return; }
  const durum = (ok, evet, hayir) =>
    `<span class="${ok ? "durum-iyi" : "durum-yok"}">${ok ? evet : hayir}</span>`;
  const hazir = (o, k) => durum(o && o[k], t("about.ready"), t("about.missing"));
  const satir = (ad, deger) => `<dt>${ad}</dt><dd>${deger}</dd>`;
  const p3 = h.primer3 || {};
  $("hakkinda").innerHTML = [
    satir(t("about.version"), `${esc(APP_VERSION || "-")} (${t("about.engine", esc(h.version || "-"))})`),
    satir(t("about.core"), p3.ok === false ? durum(false, "", t("about.core.bad")) : "primer3"),
    ...["GRCh38", "GRCh37"].map((a) =>
      satir(t("about.genome", a), h.genome_blocked && h.genome_blocked[a]
        ? durum(false, "", t("about.blocked"))
        : durum(h.genomes && h.genomes[a], t("about.local"), t("about.api")))),
    satir(t("about.annot"), `GRCh38 ${hazir(h.annotations, "GRCh38")} · GRCh37 ${hazir(h.annotations, "GRCh37")}` +
      ` · MANE ${hazir(h.annotations, "mane")}`),
    satir(t("about.dbsnp"), `GRCh38 ${hazir(h.dbsnp, "GRCh38")} · GRCh37 ${hazir(h.dbsnp, "GRCh37")}`),
    satir(t("about.sources"), t("about.sourcesText")),
  ].join("");
}

async function pickGenome(asm) {
  if (!window.allprime) return;
  const p = await window.allprime.pickFasta();
  if (!p) return;
  const r = await motor(api("/set_genome"), {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ assembly: asm, path: p, lang: LANG }),
  });
  const j = await okuJson(r);
  // Ayarlar'in ust mesaji genom satirindan kayinca gorunmez: sonuc satirin altinda da gosterilir
  const satir = $("gwarn_" + asm);
  const satirYaz = (m, hata) => {
    if (!satir) return;
    satir.textContent = m || "";
    satir.classList.toggle("hidden", !m);
    satir.classList.toggle("hint-error", !!hata);
    satir.classList.toggle("hint-warn", !hata);
  };
  // Reddedilen dosya (yanlis surum, bozuk) alana yazilmaz: kayit degismedi
  if (j.error) { setMsg(j.error, "error"); satirYaz(j.error, true); return; }
  satirYaz("");
  $("path_" + asm).value = p;
  // Yesil "tanitildi" yalniz uyarisiz ve kullanilabilir genomda; motor uyari verdiyse (genom
  // kullanilmadi, surum dogrulanamadi, indeks yok) sari uyari olarak aynen gosterilir
  if (j.warning || j.usable === false) setMsg(j.warning || t("genome.warn.blocked", asm), "warn");
  else setMsg(t("msg.genomeSet", asm), "ok");
  loadHealth();
}

// ---------------- transkript arama ----------------
async function findTranscripts() {
  const gene = $("gene_rna").value.trim();
  if (!gene) { setMsg(t("err.needGene"), "error"); return; }
  setMsg(t("msg.searching"));
  try {
    const r = await motor(api(
      `/transcripts?gene=${encodeURIComponent(gene)}&assembly=${ASSEMBLY}&lang=${LANG}`));
    const j = await okuJson(r);
    if (j.error) { setMsg(j.error, "error"); $("txList").classList.add("hidden"); return; }
    renderTxList(j.transcripts, rnaDerlemeNotu(j.assembly));
    setMsg("");
  } catch (e) {
    setMsg(t("msg.error", e.message), "error");
  }
}

// Kodlayan dizisi tutarsiz transkript (K1): hangi olcutlerin tuttugu, gecerli dilde
function kodNedenleri(den) {
  return (den && den.nedenler || []).map((n) => t("kod." + "neden." + n)).join("; ");
}

// RNA yollari transkripti her zaman GRCh38'den kurar (K1); ustte baska derleme secili ise not
function rnaDerlemeNotu(kullanilan) {
  return kullanilan && kullanilan !== ASSEMBLY ? t("rna.derleme.not", kullanilan) : "";
}

// RNA transkript listesi satirlari (RNA sekmesi ve Degerlendir RNA modu ortak): MANE rozeti,
// hizalama uyarisi rozeti, ekson / nt. Ustte GRCh37 secili ise GRCh38 kullanildigi notu basta.
function txSatirlariHtml(list, derlemeNotu) {
  const not = derlemeNotu ? `<div class="tx-not">${esc(derlemeNotu)}</div>` : "";
  return not + list.map((x) => {
    const badge = x.mane_status
      ? `<span class="mane ${x.mane_status === "MANE Select" ? "mane-sel" : "mane-plus"}">${esc(x.mane_status)}</span>`
      : "";
    const kod = x.kod_denetimi && x.kod_denetimi.isaretli
      ? `<span class="kod-rozet" title="${esc(t("kod.kisa", kodNedenleri(x.kod_denetimi)))}">⚠ ${t("kod.rozet")}</span>`
      : "";
    // MANE dosyasinda surumlu hali var; refGene'de yok - varsa surumlusunu goster
    const shown = x.mane_acc || x.acc;
    return `<div class="tx-row" data-acc="${esc(shown)}">
      <span class="tx-acc">${esc(shown)}</span>
      ${badge}${kod}
      <span class="tx-meta">${esc(t("tx.meta", x.exon_count, x.cdna_length.toLocaleString(yerel()), x.coding))}</span>
    </div>`;
  }).join("");
}

function renderTxList(list, derlemeNotu) {
  $("txList").innerHTML = txSatirlariHtml(list, derlemeNotu);
  $("txList").classList.remove("hidden");
}

// ---- Ekson atlama: ekson dugmeleri, aralik kutusu, ozet ----
// Dugmeler /transcript_exons verisiyle cizilir (genom okunmaz). Transkript yoksa ya da istek
// basarisizsa yalniz aralik kutusu calisir. Motor (engine.parse_exon_list) kesin hakemdir:
// buradaki ayristirma yalnizca dugmeleri ve ozeti gostermek icindir.
const EXON = { key: null, data: null, anchor: null, sira: 0, zamanlayici: null };
const EXON_PARCA = /^(\d{1,6})(?:[-–—−](\d{1,6}))?$/;

function exonListesi(metin) {
  const s = (metin || "").trim();
  if (!s) return [];
  const kume = new Set();
  for (const parca of s.split(/[,;\s]+/)) {
    if (!parca) continue;
    const m = EXON_PARCA.exec(parca);
    if (!m) return null;
    const a = +m[1], b = m[2] ? +m[2] : a;
    if (b < a || b - a > 10000) return null;
    for (let i = a; i <= b; i++) kume.add(i);
  }
  return [...kume].sort((x, y) => x - y);
}

function exonYaz(liste) {            // [4,5,6,9] -> "4-6,9"; [4,6] -> "4,6"
  const p = [];
  for (let i = 0; i < liste.length;) {
    let j = i;
    while (j + 1 < liste.length && liste[j + 1] === liste[j] + 1) j++;
    p.push(i === j ? String(liste[i]) : `${liste[i]}-${liste[j]}`);
    i = j + 1;
  }
  return p.join(",");
}

function exonVeriPlanla(hemen) {
  clearTimeout(EXON.zamanlayici);
  EXON.zamanlayici = setTimeout(exonVeriIste, hemen ? 0 : 450);
}

async function exonVeriIste() {
  if (RNA_MODE !== "skipping") return;
  const acc = $("acc").value.trim();
  const key = `${ASSEMBLY}|${acc.toUpperCase()}`;
  if (key === EXON.key) return;                       // ayni kod ve genom: gereksiz istek yok
  if (!/^NM_\d{4,}(\.\d+)?$/i.test(acc)) {            // yazarken yarim kodla istek atilmaz
    EXON.key = null; EXON.data = null; exonCiz(); return;
  }
  EXON.key = key;
  const sira = ++EXON.sira;
  let veri = null;
  try {
    const r = await motor(api(
      `/transcript_exons?acc=${encodeURIComponent(acc)}&assembly=${ASSEMBLY}&lang=${LANG}`));
    const j = await okuJson(r);
    if (!j.error && Array.isArray(j.exons) && j.exons.length) veri = j;
  } catch (e) { /* motor yanit vermezse yalniz kutu calisir */ }
  if (sira !== EXON.sira) return;                     // arada baska kod girildi
  if (!veri) EXON.key = null;                         // basarisiz: sonraki tetikte yeniden denenir
  EXON.data = veri;
  exonCiz();
}

function exonOzetHtml(d, sec) {
  if (!d || !sec || !sec.length) return "";
  const n = d.exon_count;
  const E = (no) => d.exons[no - 1];
  const s = sec.filter((x) => x >= 2 && x <= n - 1);
  const disi = sec.filter((x) => x < 2 || x > n - 1);
  const disiHtml = disi.length ? `<div class="ex-disi">${esc(t("ex.disi", disi.join(", ")))}</div>` : "";
  if (!s.length) return disiHtml;
  const cer = (nolar) => (nolar.reduce((a, no) => a + E(no).coding, 0) % 3 === 0
    ? `<span class="korunur">${t("ex.korunur")}</span>` : `<span class="kayar">${t("ex.kayar")}</span>`);
  const uz = (nolar) => nolar.reduce((a, no) => a + E(no).len, 0);
  const utr = s.some((no) => E(no).coding < E(no).len)
    ? `<br><span class="ex-utr">${t("ex.utr")}</span>` : "";
  const not = `<br><span class="ex-not">${t("ex.not")}</span>`;
  const a = s[0], b = s[s.length - 1];
  // Sinir kutusu isaretliyse primerlerin yeri degisir: biri secilen eksonlarin disindaki bir
  // ekson sinirina oturur ("ekson a-1 ve b+1 icine konur" demek o zaman yanlis olurdu).
  // Capa eksonlari transkriptin ilk ve son eksonuysa disarida sinir yoktur; motor o tasarimi
  // reddeder (design_exon_skipping), ozet bunu tasarimdan once soyler.
  const disSinirYok = a === 2 && b === n - 1;
  const primer = !$("junction_overlap").checked ? t("ex.primer")
    : (disSinirYok ? `<span class="ex-disi">${t("ex.primerSinirYok")}</span>` : t("ex.primerSinir"));
  if (s.length === b - a + 1) {
    const ad = a === b ? `${t("ex.ekson")} ${a}` : `${t("ex.ekson")} ${a}–${b} (${s.length} ${t("ex.ekson")})`;
    return `<b>${t("ex.secilen")}:</b> ${ad} · ${t("ex.atlanan")} ${uz(s)} bp · ${cer(s)}<br>` +
      `${primer} ${t("ex.fark", uz(s))}${utr}${not}${disiHtml}`;
  }
  const satir = [...s.map((x) => [x]), s]
    .map((k) => `Δ${k.join("+")}: −${uz(k)} bp (${cer(k)})`).join(" · ");
  return `<b>${t("ex.secilen")}:</b> ${t("ex.ekson")} ${s.join(", ")} (${t("ex.bitisikDegil")}) · ` +
    `${primer}<br><b>${t("ex.bantlar")}:</b> ${satir}${utr}${not}${disiHtml}`;
}

function exonCiz() {
  const d = EXON.data, kutu = $("exonBox");
  const sec = exonListesi($("skip_exon").value);
  $("exonHint").textContent = t(d ? "rna.exon.hint" : "rna.exon.hint0");
  // Hizalama uyarisi (kodlayan dizi tutarsiz) ve "GRCh38 kullanildi" notu (K1)
  const kodNot = [];
  if (d && d.kod_denetimi && d.kod_denetimi.isaretli) {
    kodNot.push(`<span class="kod-metin">⚠ ${esc(t("kod.kisa", kodNedenleri(d.kod_denetimi)))}</span>`);
  }
  const dn = d ? rnaDerlemeNotu(d.assembly) : "";
  if (dn) kodNot.push(`<span>${esc(dn)}</span>`);
  $("exonKodNot").innerHTML = kodNot.join("<br>");
  $("exonKodNot").classList.toggle("hidden", !kodNot.length);
  kutu.classList.toggle("hidden", !d);
  if (d) {
    if (kutu._veri !== d) {                           // dugmeler yalniz veri degisince yeniden kurulur
      kutu._veri = d;
      kutu.innerHTML = d.exons.map((x) =>
        `<button type="button" class="exon-cip" data-no="${x.no}"><b>${x.no}</b><small>${x.len} bp</small></button>`
      ).join("");
      kutu.scrollTop = 0;
    }
    kutu.querySelectorAll(".exon-cip").forEach((b) => {
      const no = +b.dataset.no, uc = no === 1 || no === d.exon_count;
      b.disabled = uc;
      b.classList.toggle("exon-uc", uc);
      b.title = uc ? t("ex.uc") : "";
      const acik = !!sec && sec.includes(no);
      b.classList.toggle("exon-sec", acik);
      b.setAttribute("aria-pressed", acik ? "true" : "false");
    });
  }
  const oz = $("exonSummary"), html = exonOzetHtml(d, sec);
  oz.innerHTML = html;
  oz.classList.toggle("hidden", !html);
}

function exonTikla(e) {
  const b = e.target.closest(".exon-cip");
  const d = EXON.data;
  if (!b || b.disabled || !d) return;
  const no = +b.dataset.no;
  const sec = exonListesi($("skip_exon").value) || [];
  if (e.shiftKey && EXON.anchor && EXON.anchor !== no) {
    const a = Math.min(EXON.anchor, no), z = Math.max(EXON.anchor, no);
    for (let i = Math.max(a, 2); i <= Math.min(z, d.exon_count - 1); i++) if (!sec.includes(i)) sec.push(i);
  } else if (sec.includes(no)) {
    sec.splice(sec.indexOf(no), 1);
  } else {
    sec.push(no);
  }
  EXON.anchor = no;
  sec.sort((x, y) => x - y);
  $("skip_exon").value = exonYaz(sec);
  exonCiz();
}

function collectParams() {
  const p = {};
  for (const id of PARAM_IDS) {
    const v = $(id).value;
    if (v !== "") p[id] = parseFloat(v);
  }
  p.avoid_common_snps = $("avoid_common_snps").checked;
  return p;
}

async function copyToClipboard(text, btn) {
  let ok = false;
  try {
    await navigator.clipboard.writeText(text);
    ok = true;
  } catch (e) {
    // Yedek yontem (bazi ortamlarda clipboard API kisitli)
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.focus(); ta.select();
      ok = document.execCommand("copy");
      document.body.removeChild(ta);
    } catch (e2) { ok = false; }
  }
  if (btn) {
    const old = btn.innerHTML;
    btn.innerHTML = t(ok ? "copy.ok" : "copy.fail");
    btn.classList.add(ok ? "copied" : "copy-fail");
    setTimeout(() => {
      btn.innerHTML = old;
      btn.classList.remove("copied", "copy-fail");
    }, 1200);
  }
}

// Hatayla biten son tasarim denemesi (sekme -> metni ureten fonksiyon). Hata, sekme ya da dil
// degisince kalir; arayuzun kendi i18n anahtarindan gelen metin yeni dilde yeniden uretilir,
// motordan gelen metin oldugu gibi kalir. Hatali denemede eski sonuc atilir: yeni girdinin
// sonucu sanilmasin, sekme ya da dil degisince geri gelmesin.
const TASARIM_HATA = {};
let EV_HATA = null;        // Degerlendir icin ayni desen (tek sekme)

function tasarimHatasi(yap, sekme = MODE) {
  otoDurdur();
  lastResult = null; lastIstek = null; RESULT_TAB = null;
  for (const k of Object.keys(SPEC_RESULTS)) delete SPEC_RESULTS[k];
  SPEC_LOW_OPEN.clear();
  $("summary").innerHTML = ""; $("pairs").innerHTML = "";
  $("results").classList.add("hidden");
  $("exportBtn").disabled = true;
  TASARIM_HATA[sekme] = yap;
  if (MODE === sekme) setMsg(yap(), "error");
}

function mesajiTazele() {
  const yap = TASARIM_HATA[MODE];
  if (yap && !document.body.classList.contains("ayar-modu")) setMsg(yap(), "error");
  else setMsg("");
}

function evalHatasi(yap) {
  lastEval = null; lastEvalIstek = null; EV_AMP_ACIK = null;
  $("evalResult").innerHTML = "";
  EV_HATA = yap;
  evalMsg(yap(), "error");
}

function setMsg(text, kind = "") {
  // Ayarlar acikken tasarim paneli gizli: genom secimi ve indirme mesaji orada gorunsun
  const m = document.body.classList.contains("ayar-modu") ? $("ayarMsg") : $("msg");
  m.textContent = text;
  m.className = "msg" + (kind ? " " + kind : "");
}

// ---------------- tasarim ----------------
function buildRequest() {
  if (MODE === "dna") {
    const position = $("position").value.trim();
    const chrom = $("chrom").value.trim();
    const gene = $("gene").value.trim();
    if (!position) return { err: () => t("err.needPos") };
    if (!chrom && !gene) return { err: () => t("err.needChromOrGene") };
    return {
      path: "/design",
      body: { assembly: ASSEMBLY, chrom, gene, position, params: collectParams() },
    };
  }

  if (MODE === "bp") {
    const chrom = $("bp_chrom").value.trim();
    const start = $("bp_start").value.trim();
    const end = $("bp_end").value.trim();
    if (!chrom || !start || !end) return { err: () => t("err.needBp") };
    const params = collectParams();
    const pay = $("bp_margin").value.trim();
    params.bp_margin = pay === "" ? 0 : parseInt(pay, 10);
    params.control_primer = $("bp_control").checked;
    return {
      path: "/design_breakpoint",
      body: { assembly: ASSEMBLY, chrom, start, end, type: BP_MODE, params },
    };
  }

  if (MODE === "seq") {
    const params = collectParams();
    if (SEQ_MODE === "pair") {
      const fwd = $("seq_fwd").value.trim();
      const rev = $("seq_rev").value.trim();
      if (!fwd || !rev) return { err: () => t("err.needBothSeq") };
      const gap = $("seq_gap").value.trim();
      params.gap = gap === "" ? 0 : parseInt(gap, 10);
      params.ignore_product_size = $("ignore_product_size").checked;
      return { path: "/design_sequence_pair", body: { forward: fwd, reverse: rev, params } };
    }
    const sequence = $("seq_single").value.trim();
    if (!sequence) return { err: () => t("err.needSeq") };
    return {
      path: "/design_sequence",
      body: { sequence, target: $("seq_target").value.trim() || null, params },
    };
  }

  const acc = $("acc").value.trim();
  if (!acc) return { err: () => t("err.needAcc") };

  if (RNA_MODE === "skipping") {
    const exon = $("skip_exon").value.trim();
    if (!exon) return { err: () => t("err.needExon") };
    // Sinir kutusu Varyant tipiyle ortak: aciksa primerlerden biri secilen eksonlarin
    // DISINDAKI bir ekson sinirina oturur (motor: design_exon_skipping)
    const atlamaParams = collectParams();
    atlamaParams.junction_overlap = $("junction_overlap").checked;
    return {
      path: "/design_skipping",
      body: { assembly: ASSEMBLY, acc, exons: exon, params: atlamaParams },
    };
  }

  const c_position = $("c_position").value.trim();
  if (!c_position) return { err: () => t("err.needCpos") };
  const params = collectParams();
  params.junction_overlap = $("junction_overlap").checked;
  params.junction_flanking = !params.junction_overlap;
  return { path: "/design_cdna", body: { assembly: ASSEMBLY, acc, c_position, params } };
}

let TASARIM_IPTAL = null;     // calisan tasarimin AbortController'i; dugme o surede "Iptal"
let lastIstek = null;         // lastResult'u ureten istek {path, body}: dil degisince tekrarlanir

async function runDesign() {
  if (TASARIM_IPTAL) { TASARIM_IPTAL.abort(); return; }
  const req = buildRequest();
  const sekme = MODE;
  if (req.err) { tasarimHatasi(req.err, sekme); return; }

  delete TASARIM_HATA[sekme];
  TASARIM_IPTAL = new AbortController();
  otoDurdur();                             // onceki tasarimin arka plan taramasi
  $("designBtn").textContent = t("act.cancel");
  setMsg(t("msg.calculating"));
  const dil = LANG;
  try {
    const r = await motor(api(req.path), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...req.body, lang: dil }),    // backend mesajlari da dile uyar
      signal: TASARIM_IPTAL.signal,
    });
    const j = await okuJson(r);
    if (j.error) { tasarimHatasi(() => j.error, sekme); return; }
    lastResult = j;
    lastIstek = req;
    RESULT_TAB = MODE;          // sonuclar bu sekmeye ait; geri donunce gorunsun
    // Ozgulluk sonuclari rank ile tutuluyor; yeni tasarimda eskileri yanlis
    // ciftin uzerinde kalirdi (rank 1 artik baska bir cift).
    for (const k of Object.keys(SPEC_RESULTS)) delete SPEC_RESULTS[k];
    SPEC_LOW_OPEN.clear();
    renderResults(j);
    sonucaKaydir($("results"));
    otoOzgulluk(j);             // beklenmez: sonuclar hemen gorunur, rozetler sonra dolar
    setMsg("");
  } catch (e) {
    if (e.name === "AbortError") setMsg("");
    else tasarimHatasi(() => istekHatasi(e), sekme);
  } finally {
    TASARIM_IPTAL = null;
    $("designBtn").textContent = t("act.design");
  }
  if (lastIstek === req && dil !== LANG) tasarimDiliniYenile();   // istek surerken dil degisti
}

// ---------------- sonuclar ----------------
// dbSNP indeksi MAF'i %0,5 adimla saklar; %0,25'in altindaki (tablonun %0,2'si)
// 0 olarak duruyor. "0" frekansi bilinmeyen/hic gorulmeyen gibi okunuyordu
// (inceleme bulgusu 20); dogrusu "<0,0025".
const mafYaz = (m) => (m === 0 ? "<0.0025" : m);
const isSeqMode = (j) => j.mode === "sequence" || j.mode === "sequence_pair";
const isWarnNote = (n) => /^(UYARI|WARNING)/.test(n);

// Tm'in yontemi ve kosullari (2026-10-31): sentez firmasinin raporundaki "Basic" Tm
// (yalnizca uzunluk + G+C) programinkinden 4-7 derece dusuk cikinca programin degeri
// yanlis sanildi. Kosullar formdan degil motorun KULLANDIGI degerlerden (params_used) gelir.
function tmNotu(j) {
  const k = j.params_used || {};
  if (k.salt_monovalent == null) return "";
  const say = (v) => Number(v).toLocaleString(yerel());
  const kosul = t("tm.cond", say(k.salt_monovalent), say(k.salt_divalent), say(k.dntp_conc),
                  say(k.dna_conc), Number(k.dmso_conc) > 0 ? say(k.dmso_conc) : "");
  // Kisa satir + acilir aciklama: tam metin kartlarin ustunde iki satir yer kapliyordu
  return `<div class="hint tm-notu"><span>${t("tm.note", kosul)}</span>
    <details class="tm-neden"><summary>${t("tm.why")}</summary><p>${t("tm.whyText")}</p></details></div>`;
}

// Tasarim / degerlendirme bitince sonuclara kaydir: 1024x640'ta sonuclar y=575'te
// basliyordu, sonucu gormek icin kaydirmak gerekiyordu (2026-11-01). Zaten gorunuyorsa
// dokunmaz; hareket azaltma tercihinde animasyonsuz kayar.
function sonucaKaydir(el) {
  if (!el || el.classList.contains("hidden")) return;
  const ust = el.getBoundingClientRect().top;
  if (ust >= 0 && ust < innerHeight * 0.4) return;
  const az = matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: az ? "auto" : "smooth", block: "start" });
}

function renderResults(j) {
  // Serbest dizi modunda referans dizi kaynagi yok
  const srcTag = isSeqMode(j) ? "" :
    `<span class="src-tag">${t(j.sequence_source === "local" ? "sum.srcLocal" : "sum.srcApi")}</span>`;
  const summary = isSeqMode(j) ? renderSeqSummary(j)
    : j.mode === "breakpoint" ? renderBpSummary(j)
    : j.mode ? renderCdnaSummary(j) : renderDnaSummary(j);
  $("summary").innerHTML = summary + snpSummary(j) + srcTag;

  // Sonuc yokken not EN ONEMLI bilgidir (primer neden bulunamadi); orada
  // soluk kucuk yazi yerine one cikan bicimde gosterilir.
  const notesHtml = (extra) => (j.notes || []).map((n) =>
    `<p class="note ${extra} ${isWarnNote(n) ? "note-warn" : ""}">${esc(n)}</p>`).join("");

  if (!j.pairs.length) {
    $("pairs").innerHTML =
      `<p class="none-title">${t("res.none")}</p>` + notesHtml("note-lead") +
      // self_filtered: primer3 cift URETTI, listeyi bizim suzgecimiz bosaltti
      // (urun GC, tekrar...). Ham dokum o zaman yanlis sebep gosteriyor; gizlenir.
      (j.self_filtered ? "" :
        `<p class="hint"><small>${esc((j.explain && j.explain.pair) || "")}</small></p>`);
    $("results").classList.remove("hidden");
    $("exportBtn").disabled = true;
    return;
  }

  const render = j.mode === "exon_skipping" ? ((p) => renderSkipPair(p, j))
    : j.mode === "breakpoint" ? ((p) => renderBpPair(p, j))
    : isSeqMode(j) ? ((p) => renderSeqPair(p, j))
    : j.mode === "cdna" ? ((p) => renderCdnaPair(p, j)) : ((p) => renderPair(p, j));
  $("pairs").innerHTML = notesHtml("") + tmNotu(j) + yonNotu(j)
    + (j.mode ? "" : `<div id="kopyaBolum"></div>`) + j.pairs.map(render).join("");
  $("results").classList.remove("hidden");
  $("exportBtn").disabled = false;
  // Yeniden cizimde (dil degisimi) rozetler kaybolmasin; tarama surerken
  // henuz sirasi gelmemis ciftler 'sirada' gorunur
  for (const p of j.pairs) {
    if (SPEC_RESULTS[p.rank]) rozetYaz(p.rank);
    else if (OTO_IPTAL && OTO_SONUC === j) rozetYaz(p.rank, "sirada");
  }
  if (!j.mode) kopyaCiz(j);
  favDurumlariniCiz();
}

function renderDnaSummary(j) {
  const inp = j.input;
  // Gen ve ipligi: girilen gen adi yoksa urunun ortustugu gen (sunucu, _gen_yonu_ekle)
  const p0 = (j.pairs || [])[0] || {};
  const gen = inp.gene || p0.strand_gene;
  const iplik = p0.gene_strand === "+" || p0.gene_strand === "-" ? ` (${t("sum.strand", p0.gene_strand)})` : "";
  return `
    <span>${t("sum.genome")}: <b>${inp.assembly}</b></span>
    <span>${t("sum.position")}: <b>${esc(inp.chrom)}:${inp.position.toLocaleString(yerel())}</b></span>
    ${gen ? `<span>${t("sum.gene")}: <b>${esc(gen)}</b>${iplik}</span>` : ""}
    <span>${t("sum.found")}: <b>${j.num_returned}</b></span>`;
}

// Eksi iplikteki genlerde F/R ve urun dizisi genin yonunde gosterilir (yon.js). Not,
// Sanger okumasinin yonunu ve eski surumlerle kayit farkini soyler.
function yonNotu(j) {
  if (j.mode && j.mode !== "breakpoint") return "";
  const eksi = [...new Set(j.pairs.filter((p) => p.gene_strand === "-").map((p) => p.strand_gene))];
  const metin = [eksi.length ? t("yon.eksi", eksi.map(esc).join(", ")) : "",
                 j.pairs.some((p) => p.gene_strand === "?") ? t("yon.belirsiz") : ""].filter(Boolean);
  return metin.length ? `<p class="note">${metin.join(" ")}</p>` : "";
}

function renderCdnaSummary(j) {
  const tx = j.transcript;
  const mane = tx.mane_status
    ? `<span class="mane ${tx.mane_status === "MANE Select" ? "mane-sel" : "mane-plus"}">${esc(tx.mane_status)}</span>`
    : "";
  const acc = tx.mane_acc || tx.acc;
  let target;
  if (j.mode === "exon_skipping") {
    const e = j.target_exon;
    const sec = j.skip_exons || [e.number];
    const bitisik = sec.length === sec[sec.length - 1] - sec[0] + 1;
    const ad = sec.length === 1 ? `${sec[0]}` : (bitisik ? `${sec[0]}–${sec[sec.length - 1]}` : sec.join(", "));
    const cer = j.skip_frame === true || j.skip_frame === false
      ? ` · ${t(j.skip_frame ? "ex.korunur" : "ex.kayar")}` : "";
    target = `<span>${t("sum.target")}: <b>${t("sum.exon")} ${ad}</b> (${j.skip_len ?? e.length} bp)${cer}</span>`;
  } else {
    target = `<span>${t("sum.variant")}: <b>${esc(j.input.c_label)}</b> · ${t("sum.exon")}
      <b>${j.variant_exon}</b> · cDNA ${j.variant_cdna_index.toLocaleString(yerel())} nt</span>`;
  }
  const note = tx.version_note
    ? `<span class="src-tag" title="${esc(tx.version_note)}">${t("sum.versionless")}</span>` : "";
  return `
    <span>${t("sum.genome")}: <b>${tx.chrom}</b> (${j.input.assembly}, ${t("sum.strand", tx.strand)})</span>
    <span>${t("sum.transcript")}: <b>${esc(acc)}</b> ${mane}</span>
    <span>${esc(tx.gene)} · ${t("sum.exonCount", tx.exon_count)} · ${tx.cdna_length.toLocaleString(yerel())} nt</span>
    ${target}
    <span>${t("sum.found")}: <b>${j.num_returned}</b></span>
    ${note}`;
}

function renderSeqSummary(j) {
  const i = j.input;
  if (j.mode === "sequence_pair") {
    const gap = i.free_product_size
      ? `<span class="src-tag" title="${t("sum.gapUnknown.title")}">${t("sum.gapUnknown")}</span>`
      : `<span title="${t("sum.gap.title")}">${t("sum.gap")}: <b>${i.gap.toLocaleString(yerel())} bp</b></span>`;
    return `
      <span>${t("sum.fwdRegion")}: <b>${i.forward_length.toLocaleString(yerel())} bp</b></span>
      <span>${t("sum.revRegion")}: <b>${i.reverse_length.toLocaleString(yerel())} bp</b></span>
      ${gap}
      <span>${t("sum.found")}: <b>${j.num_returned}</b></span>`;
  }
  const tgt = i.target
    ? `<span>${t("sum.target")}: <b>${i.target[0] + 1}${i.target[1] > 1 ? "–" + (i.target[0] + i.target[1]) : ""}</b></span>`
    : `<span class="src-tag" title="${t("sum.noTarget.title")}">${t("sum.noTarget")}</span>`;
  return `
    <span>${t("sum.seqLen")}: <b>${i.length.toLocaleString(yerel())} bp</b></span>
    ${tgt}
    <span>${t("sum.found")}: <b>${j.num_returned}</b></span>`;
}

function snpSummary(j) {
  const d = j.dbsnp;
  if (!d || d.not_applicable) return "";
  if (!d.available) {
    return `<span class="src-tag src-tag-warn" title="${t("snp.none.title")}">${t("snp.none")}</span>`;
  }
  if (d.applied) {
    return `<span class="src-tag src-tag-ok" title="${t("snp.avoided.title")}">${t("snp.avoided", d.excluded)}</span>`;
  }
  if (d.in_template) {
    return `<span class="src-tag src-tag-warn" title="${t("snp.notApplied.title")}">${t("snp.notApplied", d.in_template)}</span>`;
  }
  return `<span class="src-tag src-tag-ok">${t("snp.clean")}</span>`;
}

// Ortak: self/dimer kalite cipleri. Ana degerler (dTm, Ta) cip; ikincil olanlar (self,
// 3' self, dimer, SNP ve kartin verdigi ek bilgi: konum / eksonlar) alttaki sade satirda.
// Eskiden 9 cip iki satira tasiyor, hepsi ayni agirlikta gorunuyordu (2026-11-01).
// IGV / UCSC konumu (2026-11-14, kullanici istegi: "primerlerin bulundugu koordinatlarin araligi da
// yazsin, IGV'den bulmak kolay olsun"). Kartta okunur bicim (binlik ayiricili), kopyada IGV'nin arama
// kutusunun anladigi bicim: chr7:117559410-117559715 (ayiricisiz, duz tire; MT -> chrM).
function igvKonum(kr, bas, bit) {
  const c = String(kr == null ? "" : kr).replace(/^chr/i, "");
  return `chr${c.toUpperCase() === "MT" ? "M" : c}:${bas}-${bit}`;
}

// Primerlerin kapsadigi aralik icin "Konum" cipi + "IGV icin kopyala". asm ipucunda: IGV'de dogru genom.
function konumCipi(kr, bas, bit, asm) {
  if (kr == null || kr === "" || !Number.isFinite(bas) || !Number.isFinite(bit)) return "";
  const a = Math.min(bas, bit), z = Math.max(bas, bit);
  const ad = String(kr).replace(/^chr/i, "");
  return `<span class="chip konum-cip">${t("chip.position")}: <b>chr${esc(ad)}:${a.toLocaleString(yerel())}–${z.toLocaleString(yerel())}</b>
    <button class="copy-btn" data-seq="${esc(igvKonum(ad, a, z))}" title="${esc(t("igv.copy.title", asm || "", asm === "GRCh37" ? "hg19" : "hg38"))}">${t("igv.copy")}</button></span>`;
}

// Bir ciftin primerlerinin (varsa kontrol dahil) genomik araligi: [en kucuk, en buyuk] ya da null
function primerAraligi(...xs) {
  const g = xs.filter((x) => x && Number.isFinite(x.genomic_start) && Number.isFinite(x.genomic_end));
  if (!g.length) return null;
  return [Math.min(...g.map((x) => Math.min(x.genomic_start, x.genomic_end))),
          Math.max(...g.map((x) => Math.max(x.genomic_start, x.genomic_end)))];
}

function qualityChips(p, ikincil = "") {
  const f = p.forward, r = p.reverse;
  const worst = Math.max(f.self_dimer_tm, r.self_dimer_tm).toFixed(1);
  return `
    <span class="chip">${t("chip.dTm")}: <b>${Math.abs(f.tm - r.tm).toFixed(1)}°C</b></span>
    ${p.ta_suggested != null ? `<span class="chip" title="${t("chip.ta.title")}">${t("chip.ta")}: <b>${p.ta_suggested}°C</b></span>` : ""}
    <div class="cip-ikincil">${ikincil}
      <span class="chip" title="${t("chip.selfMax.title")}">${t("chip.selfMax")}: <b>${worst}</b></span>
      <span class="chip ${p.high_3p_self ? "chip-warn" : ""}" title="${t("chip.self3p.title")}">${t("chip.self3p")}: <b>${p.self3p_max}</b></span>
      <span class="chip" title="${t("chip.dimer.title")}">${t("chip.dimer")}: <b>${p.hetero_dimer_tm}</b></span>
      ${snpChip(p)}
    </div>`;
  // "Ceza" cipi kaldirildi (2026-10-27): primer3'un cift cezasi bu yapilandirmada
  // |F boyu - opt| + |R boyu - opt|'a esit ve secilen primerler hep opt boyda
  // oldugu icin HER ZAMAN 0 cikiyordu (8 gende 80 ciftin 80'i). Tm/GC/self
  // agirliklarini bilerek sifirladigimiz icin (secimi kendi dimer skorumuz yapsin)
  // geriye yalnizca boy terimi kalmisti. Deger API'de ve CSV'de duruyor.
}

// Primer genin neresine oturuyor: ekzon 7 / intron 7 / sinir. Ekzon numarasi
// TRANSKRIPTE gore degistigi icin hangi transkript esas alindigi ipucunda yazar.
// Etiket burada kurulur, sunucudan gelen hazir metin yalnizca yedektir: TR/EN
// dugmesi sonuclari YENIDEN CIZIYOR, sunucu metni ise eski dilde kalirdi.
const bolgeEtiket = (r) => {
  if (r.kind === "ekzon") return t("region.exon", r.exon);
  if (r.kind === "intron") return t("region.intron", r.intron);
  if (r.kind === "aralik") return t("region.exonRange", r.exon, r.exon_to);
  if (r.kind === "sinir") {
    return r.intron ? t("region.boundary", r.exon, r.intron)
                    : t("region.boundaryEnd", r.exon, t("region.side." + (r.side || "bas")));
  }
  return r.label || "";
};

// Gen adi HER ZAMAN yazilir ("LAMA2 · intron 45"): kullanici primerin hangi genin hangi
// ekzon / intronunda oldugunu goremedi (2026-11-01). Eskiden yalnizca F ve R farkli
// genlerdeyse yaziyordu (bas basa genler, 2026-10-31), gerisi yalnizca ipucundaydi.
// Transkript (ekzon numaralandirmasinin dayanagi) hucrenin ipucunda.
const bolgeCell = (x) => {
  const r = x.gene_region;
  if (!r) return `<td class="bolge" title="${esc(t("th.region.none"))}">—</td>`;
  const mane = r.mane ? " · " + r.mane : "";
  const ipucu = t("th.region.cell", r.gene || "?", r.acc || "?", mane, r.exon_count || "?")
    + (r.kod_isareti ? " · " + t("region.kod") : "");
  const etiket = (r.gene ? r.gene + "\u00a0· " : "") + bolgeEtiket(r);
  return `<td class="bolge" title="${esc(ipucu)}">${esc(etiket)}</td>`;
};

const seqCell = (x) => `<td class="seq">5'-${x.sequence}-3'
  <button class="copy-btn" data-seq="${x.sequence}" title="${t("copy.title")}">${t("copy.btn")}</button></td>`;

const qualCells = (x) => `
  <td class="sayi">${x.hairpin_tm}</td>
  <td class="sayi">${x.self_dimer_tm}</td>
  <td class="sayi ${x.self_dimer_3p_tm >= 3 ? "cell-warn" : ""}"><b>${x.self_dimer_3p_tm}</b></td>
  ${snpCell(x)}`;

// Primer uzerindeki yaygin varyantlar. 3' uca yakin olan cok daha tehlikeli:
// oradaki bir uyumsuzluk uzamayi tamamen durdurur.
function snpCell(x) {
  const s = x.snps || [];
  if (!s.length) return `<td class="snp-none">—</td>`;
  const worst = Math.min(...s.map((h) => h.distance_from_3p));
  const title = s.map((h) =>
    t("snpCell.title", h.rsid, mafYaz(h.maf), h.indel, h.distance_from_3p)).join("\n");
  return `<td class="${worst <= 5 ? "cell-warn" : "cell-note"}" title="${esc(title)}">
    <b>${s.length}</b>${worst <= 5 ? " ⚠" : ""}</td>`;
}

const snpTh = () => `<th title="${t("th.snp.title")}">${t("th.snp")}</th>`;

function snpChip(p) {
  if (!p.snp_count) return "";
  const cls = p.snp_at_3p ? "chip-warn" : "";
  return `<span class="chip ${cls}" title="${t(p.snp_at_3p ? "chip.snp.title3p" : "chip.snp.title")}">${t("chip.snp")}: <b>${p.snp_count}</b></span>`;
}

// Ortak tablo basligi; posLabel moda gore degisir
const tableHead = (posTh) => `
  <thead><tr>
    <th>${t("th.dir")}</th><th>${t("th.seq")}</th><th class="sayi">${t("th.nt")}</th>
    <th class="sayi">${t("th.tm")}</th><th class="sayi">${t("th.gc")}</th>
    ${posTh}
    <th class="sayi" title="${t("th.hairpin.title")}">${t("th.hairpin")}</th>
    <th class="sayi" title="${t("th.self.title")}">${t("th.self")}</th>
    <th class="sayi" title="${t("th.self3.title")}">${t("th.self3")}</th>
    ${snpTh()}
  </tr></thead>`;

const cdnaHead = () => tableHead(
  `<th>${t("th.exon")}</th><th title="${t("th.cdnaPos.title")}">${t("th.cdnaPos")}</th>`);

// ---------------- ozgulluk (otomatik degil, dugmeyle) ----------------
// Amplikon GC cipi. Esikler motorda (65 / 75 / 30); bayrakliysa renklenir ve
// uzerine gelince DMSO/betain onerisi cikar. Tasarimi etkilemez, bilgi verir.
function gcChip(amp) {
  if (!amp || amp.gc_percent == null) return "";
  const cls = amp.gc_flag === "cok_yuksek" ? "chip-bad"
    : amp.gc_flag === "yuksek" ? "chip-warn"
    : amp.gc_flag === "dusuk" ? "chip-warn" : "";
  const title = amp.gc_note ? esc(amp.gc_note) : t("chip.gc.title");
  return `<span class="chip ${cls}" title="${title}">${t("chip.gc")}: <b>${t("fmt.pct", amp.gc_percent)}</b></span>`;
}

// noEval: kirilma noktasi ciftleri Degerlendir'e gonderilmez - Degerlendir
// referans genoma bakar; orada bu ciftler bilerek "urun yok / birbirinden uzaga"
// verir ve bu yaniltici bir "sorun" gibi gorunur.
const specFooter = (p, opts = {}) => `
  <div class="spec-wrap">
    <button class="spec-btn" data-rank="${p.rank}">${t("spec.btn")}</button>
    ${p.amplicon ? `<button class="amp-btn" data-rank="${p.rank}">${t("amp.btn")}</button>` : ""}
    ${opts.noEval ? "" : `<button class="amp-btn to-eval-btn" data-rank="${p.rank}"
            title="${t("ev.handoff.title")}">${t("ev.handoff")}</button>`}
    ${favDugmesi(`data-rank="${p.rank}"`)}
    <span class="spec-note">${t("spec.note")}</span>
    <div class="amp-result hidden" id="amp-${p.rank}"></div>
    <div class="spec-result" id="spec-${p.rank}"></div>
  </div>`;

// Tasarlanan bir cifti dogrudan Degerlendir sekmesinde ac. Kullanicinin
// akisi zaten buydu: primeri kopyala, sekme degistir, yapistir. Transkript
// modunda NM_ kodu da tasinir - RNA degerlendirmesi onsuz calismaz.
// Tasarimdaki konum Degerlendir'e de gelsin: urun dizisinde orada da isaretlensin
function evHedefMetni(j) {
  const i = j.input || {};
  return j.mode === "cdna" ? i.c_label
    : (!j.mode && i.position) ? `chr${i.chrom}:${i.position}${i.position_end > i.position ? "-" + i.position_end : ""}` : "";
}

function pairToEvaluate(rank) {
  const j = lastResult;
  if (!j) return;
  const pair = (j.pairs || []).find((x) => x.rank === rank);
  if (!pair) return;
  // Kartta gorunen adlarla: eksi iplikteki gende genin yonunde (Degerlendir de boyle bekler)
  const v = genYonunde(pair);
  $("ev_fwd").value = v.forward.sequence;
  $("ev_rev").value = v.reverse.sequence;
  $("ev_hedef").value = evHedefMetni(j);
  const cdna = j.mode === "cdna" || j.mode === "exon_skipping";
  if (cdna && j.transcript) {
    $("ev_acc").value = j.transcript.mane_acc || j.transcript.acc;
  }
  setEvalMode(cdna ? "cdna" : "dna");
  setTab("eval");
  runEvaluate();
}

// ---------------- amplikon (cogaltilan dizi) gosterimi ----------------
// Diziyi duz bir harf yigini olarak gostermek ise yaramaz; asil deger
// primerlerin dizinin NERESINDE oturdugunu gorebilmek. Bas taraf forward,
// son taraf reverse'un ters tumleyeni olarak isaretlenir. Degerlendir'de uclarda
// baska primer olabilir: lejant adi opts.fwdLabel / opts.revLabel, kisa not opts.note.
function renderAmplicon(a, opts = {}) {
  const s = a.sequence;
  const cls = new Array(s.length).fill("");
  const isaretle = (span, c) => {
    if (!span) return;
    for (let i = Math.max(0, span[0]); i <= Math.min(s.length - 1, span[1]); i++) cls[i] = c;
  };
  isaretle(a.forward_span, "amp-f");
  isaretle(a.reverse_span, "amp-r");
  isaretle(a.unknown_span, "amp-n");     // iki dizi modunda bilinmeyen ara bolge
  // Girilen konum: en son, primerin ustune dusse de (Degerlendir) gorunsun
  isaretle(a.variant_span, "amp-v");
  const hedefAdi = a.variant_span
    ? t("amp.target", esc(opts.targetLabel || ""), a.variant_span[0] + 1, a.variant_span[1] + 1) : "";
  const sinir = new Set(opts.junctions || a.junction_offsets || []);
  // Ayni isaret RNA modunda ekson siniri, kirilma noktasi modunda kirilma noktasi
  const sinirAdi = opts.junctionLabel || t("amp.junction");

  const SATIR = 60, GRUP = 10;
  let govde = "";
  for (let i = 0; i < s.length; i += SATIR) {
    const son = Math.min(i + SATIR, s.length);
    let parcalar = "", tampon = "", tamponCls = cls[i];
    const bosalt = () => {
      if (!tampon) return;
      parcalar += !tamponCls ? tampon
        : `<span class="${tamponCls}"${tamponCls === "amp-v" ? ` title="${hedefAdi}"` : ""}>${tampon}</span>`;
      tampon = "";
    };
    for (let k = i; k < son; k++) {
      if (k > i && (k - i) % GRUP === 0) { bosalt(); parcalar += " "; tamponCls = cls[k]; }
      if (sinir.has(k)) { bosalt(); parcalar += `<span class="amp-j" title="${sinirAdi}">|</span>`; tamponCls = cls[k]; }
      if (cls[k] !== tamponCls) { bosalt(); tamponCls = cls[k]; }
      tampon += s[k];
    }
    bosalt();
    govde += `<div class="amp-line"><span class="amp-no">${(i + 1).toLocaleString(yerel())}</span>${parcalar}</div>`;
  }

  const efsane = `
    <div class="amp-legend">
      <span><i class="amp-sw amp-f"></i>${opts.fwdLabel || t("amp.fwd")}</span>
      <span><i class="amp-sw amp-r"></i>${opts.revLabel || t("amp.rev")}</span>
      ${sinir.size ? `<span><i class="amp-sw amp-j"></i>${sinirAdi}</span>` : ""}
      ${a.unknown_span ? `<span><i class="amp-sw amp-n"></i>${t("amp.unknown", a.unknown_length)}</span>` : ""}
      ${a.variant_span ? `<span><i class="amp-sw amp-v"></i>${hedefAdi}</span>` : ""}
      ${opts.note ? `<span class="muted-note">${opts.note}</span>` : ""}
    </div>`;

  return `
    <div class="amp-box">
      <div class="amp-head">
        <b>${t("amp.title", a.length.toLocaleString(yerel()))}</b>
        ${a.gc_percent != null ? `<span class="${a.gc_flag === "cok_yuksek" ? "gc-bad" : a.gc_flag ? "gc-warn" : "gc-ok"}"
            title="${a.gc_note ? esc(a.gc_note) : t("chip.gc.title")}">GC ${t("fmt.pct", a.gc_percent)}</span>` : ""}
        <button class="copy-btn" data-seq="${s}" title="${t("copy.title")}">${t("amp.copy")}</button>
        <button class="copy-btn" data-seq="${esc(opts.fasta || (">" + (opts.name || "amplicon") + "\n" + s))}"
                title="${t("amp.copyFasta.title")}">${t("amp.copyFasta")}</button>
      </div>
      ${efsane}
      <pre class="amp-seq">${govde}</pre>
    </div>`;
}

// Urun dizisinde isaretlenen konumun adi, kullanicinin girdigi bicimde
function hedefEtiketi(j, a) {
  if (j.mode === "cdna") return j.input.c_label;
  if (j.mode === "breakpoint") return t((a.junction_offsets || []).length ? "amp.target.bp" : "amp.target.region");
  if (isSeqMode(j)) return t("amp.target.seq");
  const i = j.input, s = (x) => x.toLocaleString(yerel());
  return `chr${i.chrom}:${s(i.position)}` + (i.position_end > i.position ? `-${s(i.position_end)}` : "");
}

function toggleAmplicon(rank, btn) {
  const j = lastResult;
  if (!j) return;
  const pair = (j.pairs || []).find((x) => x.rank === rank);
  const box = $("amp-" + rank);
  if (!pair || !pair.amplicon || !box) return;
  if (!box.innerHTML) {
    const ad = j.mode === "cdna" || j.mode === "exon_skipping"
      ? `${j.transcript.gene}_${j.transcript.mane_acc || j.transcript.acc}_${pair.rank}`
      : j.mode === "breakpoint"
        ? `chr${j.input.chrom}_${j.input.start}-${j.input.end}_${j.input.type}_${pair.rank}`
      : isSeqMode(j) ? `amplicon_${pair.rank}`
      : `chr${j.input.chrom}_${pair.amplicon_genomic_start}-${pair.amplicon_genomic_end}`;
    // Eksi iplikteki gende dizi genin yonunde (F'den baslar, c. ile ayni yonde);
    // FASTA basligi bunu soyler, yoksa genomik koordinatli ad + iplik sanilir
    const v = genYonunde(pair);
    box.innerHTML = renderAmplicon(v.amplicon, {
      name: ad, junctionLabel: j.mode === "breakpoint" ? t("amp.breakpoint") : null,
      targetLabel: v.amplicon.variant_span ? hedefEtiketi(j, v.amplicon) : null,
      fasta: v !== pair ? `>${ad} ${t("amp.geneDir", pair.strand_gene)}\n${v.amplicon.sequence}` : null });
  }
  const gizli = box.classList.toggle("hidden");
  btn.textContent = gizli ? t("amp.btn") : t("amp.btn.hide");
}

const SPEC_IPTAL = {};       // rank -> AbortController (tarama surerken dugme "Iptal")

async function runSpecificity(rank, btn) {
  if (SPEC_IPTAL[rank]) { SPEC_IPTAL[rank].abort(); return; }
  const j = lastResult;
  if (!j) return;
  const pair = j.pairs.find((x) => x.rank === rank);
  const box = $("spec-" + rank);
  if (!pair || !box) return;

  // Otomatik tarama bu cifti zaten taradiysa ayrinti hemen gosterilir
  if (SPEC_RESULTS[rank] && !box.innerHTML.trim()) {
    const s0 = SPEC_RESULTS[rank];
    box.innerHTML = s0.error ? `<p class="note note-warn">${esc(s0.error)}</p>`
      : renderSpec(s0, j, rank);
    return;
  }

  const label = btn.textContent;
  SPEC_IPTAL[rank] = new AbortController();
  btn.textContent = t("spec.scanning") + " — " + t("act.cancel");
  box.innerHTML = "";

  try {
    const r = await motor(api("/specificity"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(specGovdesi(j, pair)),
      signal: SPEC_IPTAL[rank].signal,
    });
    const s = await okuJson(r);
    if (lastResult !== j) return;        // bu arada yeni tasarim yapildi
    SPEC_RESULTS[rank] = s;              // dusuk olasiliklilari acip kapatmak icin
    SPEC_LOW_OPEN.delete(rank);
    rozetYaz(rank);
    box.innerHTML = s.error
      ? `<p class="note note-warn">${esc(s.error)}</p>`
      : renderSpec(s, j, rank);
  } catch (e) {
    box.innerHTML = `<p class="note note-warn">${esc(istekHatasi(e))}</p>`;
  } finally {
    delete SPEC_IPTAL[rank];
    btn.textContent = label;
  }
}

// /specificity istek govdesi (dugme ve otomatik tarama ayni hedefi kullanir).
// Hedef bolge: taramada cikan bu lokus "yan urun" degildir, ayrilir.
// Serbest dizi modunda genomik karsilik bilinmez -> hedef verilmez.
// Kirilma noktasi modunda asil urun referansta YOKTUR; referanstaki tek
// "beklenen" urun normal alelinki (delesyon / kucuk dup'ta F..R arasi).
// Tandem baglanti ciftinde primerler referansta disa baktigi icin hedef yok.
function specGovdesi(j, pair) {
  const bp = j.mode === "breakpoint";
  const chrom = isSeqMode(j) ? null
    : bp ? j.input.chrom : (j.mode ? j.transcript.chrom : j.input.chrom);
  // Normal alelin bolgesi iki primerin genomik uclarindan (hangisinin F gosterildigi
  // genin yonune bagli, yon.js; bolge degismez)
  const uclar = [pair.forward, pair.reverse];
  const expected = bp
    ? (j.input.approach === "tandem_junction" ? null
      : { chrom, start: Math.min(...uclar.map((x) => x.genomic_start)),
          end: Math.max(...uclar.map((x) => x.genomic_end)) })
    : (chrom && pair.amplicon_genomic_start && pair.amplicon_genomic_end)
      ? { chrom, start: pair.amplicon_genomic_start, end: pair.amplicon_genomic_end }
      : null;
  // Primerler ekrandaki adlariyla gonderilir: taramanin "F" / "R" sutunlari kartla ayni
  const v = genYonunde(pair);
  return { assembly: j.input.assembly || ASSEMBLY, forward: v.forward.sequence,
           reverse: v.reverse.sequence, expected, lang: LANG };
}

// ---------------- otomatik ozgulluk (yalnizca ISARETLER) ----------------
// Kullanicinin kaygisi (2026-10-29): "ozgul" olcutune gore eleyip siralamak,
// primer3'un en iyi adayini kaybettirebilir - "ozgul degil" orta riskli (3-5
// uyumsuzluklu, cogu zaman bant vermeyen) yan urunleri de sayar. Bu yuzden
// hicbir cift atilmaz, sira degismez; her cifte yalnizca bir rozet eklenir.
// Sonuclar hemen gorunur, ciftler arka planda sirayla (~3 sn/cift) taranir.
// Yalnizca DNA modu: diger modlarda genomda "hedef urun" tanimsiz, rozet yaniltir.
let OTO_IPTAL = null;
// Calisan taramanin AIT OLDUGU sonuc: yeniden cizimde "sirada" rozeti yalnizca onun
// kartlarina konur. Eskiden lastResult'a bakiliyor ve durdurulan tarama OTO_IPTAL'de
// kaliyordu: DNA taramasi surerken baska modda tasarim yapilinca yeni kartlarin hepsi,
// kutu kapatilinca da taranmamis kartlar hic bitmeyen "sirada" / "taraniyor" rozeti
// tasiyordu (2026-11-01, kurulu 0.8.24 / 0.8.25'te olculdu: 10 / 8 kart).
let OTO_SONUC = null;

// ---------------- en iyi Ozgul cift / kopyadan ayrisan ciftler ----------------
// DNA tasariminda rozetler bitince kurallara uyan butun adaylar motorda taranir (kopya.py,
// cok_tarama.py). Normal liste ve sirasi degismez; 1. cift en iyisi degilse en iyi Ozgul cift
// kartlarin ustunde ayri bolumde gosterilir (psodogenli gende ilk 8'i, kopyadan farkiyla).
// Otomatik kontrol kapaliyken arama yalniz psodogenli gende dugmeyle baslar; kontrol sonradan
// acilinca son tasarim icin de baslar.
let KOPYA = null;       // { j, durum, sonuc, hepsi, hata, iptal }

// Arama yapilmadi ya da durduruldu: dugme yalniz psodogenli gende, psodogensiz gende kutu
// gizlenir (kontrol kapaliyken yeni tarama istenmemis olur). Tasarimda, kontrol kapatilinca ve
// motor aramayi biraktiginda hep ayni kural (2026-11-09).
function kopyaBeklet(d) {
  d.durum = d.j.paralog_var ? "dugme" : "gizli";
}

function kopyaHazirla(j) {
  if (!KOPYA || KOPYA.j !== j) KOPYA = { j, durum: "dugme" };
  const genom = HEALTH && HEALTH.genomes && HEALTH.genomes[j.input.assembly || ASSEMBLY];
  // Arama hic baslamadiysa karar her cagrida yeniden verilir: kontrol tasarimdan sonra acilinca
  // "gizli" de "sirada" olur (2026-11-09: yalniz "dugme"ye bakiliyordu; psodogensiz gende
  // rozetler geliyor, arama hic baslamiyor, sessiz kutu "1. cift en iyisi" gibi okunuyordu)
  const baslamadi = KOPYA.durum === "dugme" || KOPYA.durum === "gizli";
  if (!genom || !j.pairs.length) KOPYA.durum = "gizli";
  else if (baslamadi && $("autoSpec").checked) KOPYA.durum = "sirada";
  else if (baslamadi) kopyaBeklet(KOPYA);
}

// Yeni tasarim ya da otomatik kontrolun kapatilmasi: motor da yarim aramayi birakir
function kopyaDurdur() {
  const d = KOPYA;
  if (!d) return;
  if (d.iptal) {
    d.iptal.abort();
    d.iptal = null;
    motor(api("/kopya_durdur"), { method: "POST" }).catch(() => {});
  }
  if (d.durum === "sirada" || d.durum === "araniyor") {
    kopyaBeklet(d);
    kopyaCiz(d.j);
  }
}

function kopyaCiz(j) {
  const k = $("kopyaBolum");
  if (!k || !KOPYA || KOPYA.j !== j) return;
  const d = KOPYA, sayi = (x) => x.toLocaleString(yerel());
  const kutu = (cls, ic) => { k.className = "kopya-bolum" + cls; k.innerHTML = ic; };
  const gizle = () => { k.className = ""; k.innerHTML = ""; };
  const paralog = !!j.paralog_var;
  const baslik = `<b>${t(paralog ? "kopya.title" : "eniyi.title")}</b>`;
  if (d.durum === "gizli") return gizle();
  if (d.durum === "dugme") {
    return kutu("", `${baslik}<p class="hint">${t("kopya.dugme")}</p>
      <button class="amp-btn" data-kopya="ara">${t("kopya.ara")}</button>`);
  }
  if (d.durum === "sirada" || d.durum === "araniyor") {
    return kutu("", `${baslik} <span class="muted-note">${t("eniyi." + d.durum)}</span>`);
  }
  if (d.durum === "hata") return kutu(" kopya-yok", `${baslik}<p class="hint">${esc(d.hata || "")}</p>`);
  const s = d.sonuc;
  // 1. cift zaten en iyi: sessiz (kullanici karari, 2026-11-09)
  if (!s || s.durum === "bos" || s.durum === "bir") return gizle();
  const N = sayi(s.taranan);
  const neden = s.bir && !s.bir.ozgul ? t("eniyi.neden", s.bir.yuksek ? sayi(s.bir.yuksek) : "", s.bir.orta ? sayi(s.bir.orta) : "") : "";
  const sira = (p) => p.havuz_sira ? sayi(p.havuz_sira)
    : `<span title="${t("eniyi.havuz_disi.title", sayi(s.havuz))}">${t("eniyi.havuz_disi")}</span>`;
  const tablo = (liste, onek, th, hucre) => `<div class="tablo-kaydir"><table class="spec-table"><thead><tr>
    <th>${t("kopya.th.sira")}</th><th>${t("kopya.th.f")}</th><th>${t("kopya.th.r")}</th><th>${t("kopya.th.urun")}</th>
    <th>${th}</th><th></th></tr></thead><tbody>${liste.map((p, i) => {
    const v = genYonunde(p);
    return `<tr><td class="sayi">${sira(p)}</td><td class="seq">5'-${v.forward.sequence}-3'</td>
      <td class="seq">5'-${v.reverse.sequence}-3'</td><td class="sayi">${sayi(p.product_size)} bp</td>
      <td class="kopya-fark">${hucre(p)}</td>
      <td><button class="amp-btn" data-kopya="${onek}${i}">${t("ev.handoff")}</button></td></tr>`;
  }).join("")}</tbody></table></div>`;
  if (s.durum === "yok") {
    return kutu(" kopya-yok", `<b>${t("eniyi.yok.title")}</b><p class="hint">${t("eniyi.yok.hint", N, paralog)}</p>
      ${tablo(s.aday, "a", t("eniyi.th.yan"), (p) => t("eniyi.yan", sayi(p.yuksek), sayi(p.orta)))}`);
  }
  const p0 = s.pairs[0];
  if (s.durum === "ilk10") {
    return kutu("", `<div class="pair-head"><b>${t("eniyi.ilk10.title", p0.havuz_sira)}</b>
      <span class="chip chip-ok">${t("eniyi.taranan", N)}</span></div>
      <p class="hint">${neden}${t("eniyi.ilk10.hint", p0.havuz_sira, eniyiFark(p0.fark))}</p>
      <button class="amp-btn" data-kopya="git">${t("eniyi.git", p0.havuz_sira)}</button>`);
  }
  const k2 = s.durum === "k2";
  if (paralog) {
    const liste = d.hepsi ? s.pairs : s.pairs.slice(0, 3);
    return kutu("", `<div class="pair-head">${baslik} <span class="chip chip-ok">${t("eniyi.paralog.chip", s.pairs.length, N)}</span></div>
      <p class="hint">${t("eniyi.paralog.hint", k2 ? t("eniyi.k2.bir", sayi(s.havuz)) : neden, N, s.pairs.length)}</p>
      ${tablo(liste, "", t("kopya.th.fark"), kopyaFarkHucre)}
      ${!d.hepsi && s.pairs.length > 3 ? `<button class="amp-btn" data-kopya="hepsi">${t("kopya.hepsi", s.pairs.length)}</button>` : ""}`);
  }
  return kutu("", `<div class="pair-head"><b>${t(k2 ? "eniyi.k2.title" : "eniyi.title")}</b>
    <span class="chip chip-ok">${t("eniyi.taranan", N)}</span></div>
    <p class="hint">${k2 ? t("eniyi.k2.hint", eniyiFark(p0.fark), sayi(s.havuz)) : neden + t("eniyi.disari.hint")}</p>
    ${tablo([p0], "", t("eniyi.th.fark"), (p) => eniyiFark(p.fark))}`);
}

// En iyi cift ile ekrandaki 1. cift arasindaki fark: primer boyu sapmasi (primer3 cezasi), dimer, urun boyu
function eniyiFark(f) {
  if (!f) return "—";
  const ond = (n) => (n > 0 ? "+" : "−") + Math.abs(n).toLocaleString(yerel(), { maximumFractionDigits: 1 });
  const p = [];
  if (f.ceza) p.push(t("eniyi.fark.ceza", ond(f.ceza)));
  if (f.dimer) p.push(t("eniyi.fark.dimer", ond(f.dimer)));
  if (f.boy) p.push(t("eniyi.fark.boy", Math.abs(f.boy).toLocaleString(yerel()), f.boy < 0));
  return p.join(" · ") || t("eniyi.fark.ayni");
}

// "k. cifte git": en iyi Ozgul cift listede; kartina kaydir
function kopyaGit() {
  const s = KOPYA && KOPYA.sonuc, p = s && s.pairs[0];
  const kart = p && $("spec-" + p.havuz_sira) && $("spec-" + p.havuz_sira).closest(".pair-card");
  if (kart) kart.scrollIntoView({ block: "start", behavior: "smooth" });
}

// Cifti kopyadan ayiran fark (motor: kopya.kopya_farki). Motor primeri tasarim yonunde verir;
// ad kartlardaki gibi genin yonunde yazilir (eksi iplikte F ile R yer degistirir, yon.js).
function kopyaFarkHucre(p) {
  const k = p.kopya;
  if (k === undefined) return "—";
  if (k === null) return `<span title="${t("kopya.fark.cok.title")}">${t("kopya.fark.cok")}</span>`;
  const f = k.fark[0];
  if (!f) return "—";
  const ad = (p.gene_strand === "-") === (f.primer === "forward") ? "R" : "F";
  const metin = f.uctan === 1 ? t("kopya.fark.son", ad) : t("kopya.fark.uc", ad, f.uctan);
  const ek = k.fark.length > 1 ? t("kopya.fark.toplam", k.fark.length) : "";
  return `<span title="${t("kopya.fark.title", k.chrom, k.start.toLocaleString(yerel()), k.size)}">${metin}${ek}</span>`;
}

async function kopyaAra(j) {
  const d = KOPYA;
  if (!d || d.j !== j) return;
  const ac = d.iptal = new AbortController();
  d.durum = "araniyor";
  kopyaCiz(j);
  try {
    // Tasarimin kendi istegi: motor ayni havuzu yeniden uretir
    const r = await motor(api("/kopya_ciftleri"), {
      method: "POST", headers: { "Content-Type": "application/json" }, signal: ac.signal,
      body: JSON.stringify({ ...lastIstek.body, lang: LANG }),
    });
    const s = await okuJson(r);
    if (ac.signal.aborted) return;
    if (s.error) { d.durum = "hata"; d.hata = s.error; }
    else if (s.iptal) kopyaBeklet(d);
    else { d.sonuc = s; d.durum = "bitti"; }
  } catch (e) {
    if (ac.signal.aborted) return;
    d.durum = "hata";
    d.hata = istekHatasi(e);
  }
  d.iptal = null;
  kopyaCiz(j);
}

function kopyaDegerlendir(k) {
  const j = lastResult, s = KOPYA && KOPYA.sonuc;
  const p = s && (String(k).startsWith("a") ? s.aday[parseInt(String(k).slice(1), 10)] : s.pairs[parseInt(k, 10)]);
  if (!p) return;
  const v = genYonunde(p);
  $("ev_fwd").value = v.forward.sequence;
  $("ev_rev").value = v.reverse.sequence;
  $("ev_hedef").value = evHedefMetni(j);
  setEvalMode("dna");
  setTab("eval");
  runEvaluate();
}

// Otomatik taramayi durdur. Taranmamis kartlarda bekleme rozeti birakilmaz: o kartlar
// artik taranmayacak (taranmis olanlarin sonucu kalir; dugme her zaman calisir).
function otoDurdur() {
  kopyaDurdur();
  if (OTO_IPTAL) OTO_IPTAL.abort();
  const j = OTO_SONUC;
  OTO_IPTAL = null;
  OTO_SONUC = null;
  if (!j) return;
  for (const p of j.pairs) {
    if (SPEC_RESULTS[p.rank]) continue;
    const kutu = $("spec-" + p.rank);
    const r = kutu && kutu.closest(".pair-card") && kutu.closest(".pair-card").querySelector(".spec-rozet");
    if (r) r.remove();
  }
}

async function otoOzgulluk(j) {
  otoDurdur();
  if (!j.mode) { kopyaHazirla(j); kopyaCiz(j); }
  if (!$("autoSpec").checked || j.mode || !j.pairs.length) return;
  const asm = j.input.assembly || ASSEMBLY;
  if (!HEALTH || !HEALTH.genomes || !HEALTH.genomes[asm]) return;
  const ac = OTO_IPTAL = new AbortController();
  OTO_SONUC = j;
  for (const pair of j.pairs) rozetYaz(pair.rank, "sirada");
  for (const pair of j.pairs) {
    if (ac.signal.aborted || lastResult !== j) return;
    if (SPEC_RESULTS[pair.rank]) { rozetYaz(pair.rank); continue; }   // dugmeyle taranmis
    rozetYaz(pair.rank, "taraniyor");
    try {
      const r = await motor(api("/specificity"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(specGovdesi(j, pair)), signal: ac.signal,
      });
      const s = await okuJson(r);
      if (lastResult !== j) return;
      SPEC_RESULTS[pair.rank] = s;
      rozetYaz(pair.rank);
    } catch (e) {
      if (e.name === "AbortError" || lastResult !== j) return;
      rozetYaz(pair.rank, "hata");
    }
  }
  if (OTO_IPTAL === ac) { OTO_IPTAL = null; OTO_SONUC = null; }
  // Rozetler bitti: kurallara uyan butun adaylar taranir (v0.8.36; 1. cift Ozgul olsa da: havuz disinda
  // ayni kurallarla daha iyi skorlu Ozgul cift olabilir, olculdu 10/298)
  if (!j.mode && KOPYA && KOPYA.j === j && KOPYA.durum === "sirada") kopyaAra(j);
}

// Cift kartinin basligina ozgulluk rozeti: yesil ozgul, sari orta riskli yan
// urun (bilgi), kirmizi yuksek riskli yan urun / tekrar dizisi.
function rozetYaz(rank, durum) {
  const kutu = $("spec-" + rank);
  const bas = kutu && kutu.closest(".pair-card") && kutu.closest(".pair-card").querySelector(".pair-head");
  if (!bas) return;
  let r = bas.querySelector(".spec-rozet");
  // Rozet kartin en onemli sonucu: sira numarasinin hemen yanina (eskiden sona eklenip
  // ikinci satirda "3' self-komp." cipiyle ayni gorunuyordu, 2026-11-01)
  if (!r) {
    r = document.createElement("span");
    const sira = bas.querySelector(".rank-badge");
    if (sira) sira.after(r); else bas.prepend(r);
  }
  const s = SPEC_RESULTS[rank];
  let cls = "", metin, baslik = "";
  if (durum === "sirada") metin = t("auto.queued");
  else if (durum === "taraniyor") metin = t("auto.scanning");
  else if (durum === "hata" || !s) metin = t("auto.failed");
  else if (s.error) { cls = "chip-bad"; metin = t("auto.error"); baslik = s.error; }
  else if (s.specific) { cls = "chip-ok"; metin = t("auto.specific"); baslik = t("auto.specific.title"); }
  else {
    const rc = s.risk_counts || {};
    const ilk = (s.offtargets || [])[0];
    const yer = ilk ? t("auto.where", ilk.chrom, ilk.start.toLocaleString(yerel()), ilk.size,
      ilk.mismatch_total) : "";
    if (rc.yuksek) { cls = "chip-bad"; metin = t("auto.high", rc.yuksek); baslik = yer; }
    else { cls = "chip-warn"; metin = t("auto.medium", rc.orta); baslik = t("auto.medium.title") + (yer ? " " + yer : ""); }
  }
  r.className = "chip spec-rozet " + cls;
  r.title = baslik;
  r.textContent = metin;
  yakinSatiriYaz(bas, !durum && s && !s.error && s.specific && lastResult && !lastResult.mode ? s.near_copy : null);
}

// "Ozgul" rozetli ciftte 3' kurali disinda kalan yakin kopya notu: kartta rozet satirinin altinda tek satir
// (F-03, kullanici karari 2026-11-11). Yalnizca bilgi: rozet, sira ve "En iyi Ozgul cift" degismez. Primer
// adlari istekteki (kartta gorunen) adlardir; motor 'forward' = kartin Forward'i der.
function yakinSatiriYaz(bas, n) {
  const eski = bas.nextElementSibling;
  if (eski && eski.classList.contains("spec-yakin")) eski.remove();
  if (!n || !n.sites) return;
  const sayi = (x) => x.toLocaleString(yerel());
  const yer = `chr${n.chrom}:${sayi(n.start)}–${sayi(n.end)}`;
  const parca = n.sites.filter((x) => x.mismatches.length)
    .map((x) => t("auto.yakin.primer", t("dir." + x.primer), x.mismatches.map((m) => m.from_3p)));
  if (!parca.length) return;
  const satir = document.createElement("div");
  satir.className = "spec-yakin";
  satir.textContent = t("auto.yakin", yer, sayi(n.size), parca.join("; "));
  bas.after(satir);
}

// Ozgulluk kutulari cift basina ayri; hangisinde dusuk olasiliklilarin acik
// oldugunu ve o kutunun sonucunu rank ile tutuyoruz.
const SPEC_RESULTS = {};
const SPEC_LOW_OPEN = new Set();

function toggleSpecLow(rank, btn) {
  const s = SPEC_RESULTS[rank];
  const kutu = $("spec-" + rank);
  if (!s || !kutu || !lastResult) return;
  if (SPEC_LOW_OPEN.has(rank)) SPEC_LOW_OPEN.delete(rank);
  else SPEC_LOW_OPEN.add(rank);
  kutu.innerHTML = renderSpec(s, lastResult, rank);
}

function renderSpec(s, j, rank) {
  const isCdna = j.mode === "cdna" || j.mode === "exon_skipping";
  const isBp = j.mode === "breakpoint";
  const rc = s.risk_counts;
  const verdict = s.specific
    ? `<span class="verdict verdict-ok">${t("spec.ok")}</span>`
    : rc.yuksek > 0
      ? `<span class="verdict verdict-bad">${t("spec.high", rc.yuksek)}</span>`
      : `<span class="verdict verdict-mid">${t("spec.mid", rc.orta)}</span>`;

  // Hedef bolge bulunamadiysa bu ANLAMLI bir bilgi: cDNA modunda beklenen durum
  // (urun intron kapsiyor), DNA modunda ise koordinat/dizi uyusmazligina isaret eder.
  const target = isSeqMode(j)
    ? `<span class="chip" title="${t("spec.seqMode.title")}">${t("spec.seqMode")}</span>`
    : isBp
      ? `<span class="chip" title="${t("spec.bpNoRef.title")}">${t(s.intended_found ? "spec.bpWtFound" : "spec.bpNoRef")}</span>`
    : s.intended_found
      ? `<span class="chip chip-ok">${t("spec.targetFound")}</span>`
      : `<span class="chip ${isCdna ? "" : "chip-warn"}" title="${t(isCdna ? "spec.targetCdna.title" : "spec.targetMissing.title")}">${t(isCdna ? "spec.targetCdna" : "spec.targetMissing")}</span>`;

  const specRow = (o) => `
    <tr class="risk-${o.risk}">
      <td><span class="risk-dot risk-${o.risk}"></span>${t("risk." + o.risk)}</td>
      <td>${o.combination}</td>
      <td>chr${esc(o.chrom)}:${o.start.toLocaleString(yerel())}–${o.end.toLocaleString(yerel())}</td>
      <td>${o.size.toLocaleString(yerel())} bp</td>
      <td>${o.forward_primer} ${o.mismatch_forward} / ${o.reverse_primer} ${o.mismatch_reverse}</td>
    </tr>`;
  // Dusuk olasiliklilar gizli baslar; SPEC_LOW_OPEN o kutu icin acik mi tutar
  const acik = SPEC_LOW_OPEN.has(rank);
  const rows = s.offtargets.map(specRow).join("")
    + (acik ? (s.offtargets_low || []).map(specRow).join("") : "");

  const lowBtn = s.low_hidden
    ? `<button class="amp-btn spec-low-btn" data-rank="${rank}">${
        acik ? t("ev.hideLow") : t("ev.showLow", s.low_hidden)}</button>` : "";

  const table = (s.offtargets.length || acik) ? `
    <table class="spec-table">
      <thead><tr>
        <th>${t("spec.th.risk")}</th>
        <th title="${t("spec.th.combo.title")}">${t("spec.th.combo")}</th>
        <th>${t("spec.th.loc")}</th><th>${t("spec.th.product")}</th>
        <th title="${t("spec.th.mismatch.title")}">${t("spec.th.mismatch")}</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${s.truncated ? `<p class="spec-note">${t("spec.truncated", s.offtargets.length, s.offtarget_count)}</p>` : ""}
    ${s.low_hidden ? `<p class="spec-note">${t("spec.lowHidden", s.low_hidden)}</p>${lowBtn}` : ""}`
    : `<p class="spec-note">${t("spec.clean")}${
        s.low_hidden ? " " + t("spec.lowHidden", s.low_hidden) : ""}</p>${lowBtn}`;

  return `
    <div class="spec-box">
      <div class="spec-head">
        ${verdict}${target}
        <span class="chip" title="${t("spec.sites.title", s.params_used.risk_high_max)}">${t("spec.sites")}: <b>F ${s.binding_sites.F.toplam.toLocaleString(yerel())} (${s.binding_sites.F.iyi}) · R ${s.binding_sites.R.toplam.toLocaleString(yerel())} (${s.binding_sites.R.iyi})</b></span>
        <span class="chip">${t("spec.riskCounts")}: <b>${t("spec.riskSummary", rc.yuksek, rc.orta, rc.dusuk)}</b></span>
      </div>
      ${s.par ? `<p class="spec-note">${esc(s.par.note)}</p>` : ""}
      ${table}
    </div>`;
}

// Hairpin uyarisi (F-05, kullanici karari 2026-11-11): hairpin Tm'i kartin Ta onerisinin 5 °C altini
// gecen primer icin tek satir. Kural motorda (engine.hairpin_uyarisi); burada yalniz gosterim. Sira, rozet
// ve "En iyi Ozgul cift" degismez. cevrik = kart eksi iplikli gende F/R'yi genin yonunde gosteriyor
// (genYonunde): motorun 'forward'u kartta "Reverse" gorunur, ad kartin gosterdigi ad olur.
function hairpinSatiri(p, cevrik = false) {
  const hesap = (x) => x.toLocaleString(yerel(), { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return (p.hairpin_warn || []).map((w) => {
    // Kirilma noktasinda kontrol primeri de uyari tasiyabilir (2026-11-14); adi cevrilmez
    const gor = w.primer === "control" ? "bp.dir.control"
      : (w.primer === "forward") !== cevrik ? "dir.forward" : "dir.reverse";
    return `<div class="hairpin-uyari">${esc(t("hairpin.uyari", t(gor), hesap(w.hairpin_tm), hesap(w.ta),
      +(w.ta - w.esik).toFixed(1)))}</div>`;
  }).join("");
}

// ---------------- cift kartlari ----------------
function renderPair(p, j) {
  const v = genYonunde(p);         // eksi iplikteki gende F/R genin yonunde (yon.js)
  const i = (j && j.input) || {};
  const row = (dirKey, cls, x) => `
    <tr>
      <td class="${cls}">${t(dirKey)}</td>
      ${seqCell(x)}
      <td class="sayi">${x.length}</td><td class="sayi">${x.tm}</td><td class="sayi">${x.gc}</td>
      <td>${x.genomic_start.toLocaleString(yerel())}–${x.genomic_end.toLocaleString(yerel())}</td>
      ${bolgeCell(x)}
      ${qualCells(x)}
    </tr>`;
  return `
    <div class="pair-card">
      <div class="pair-head">
        <span class="rank-badge">${p.rank}</span>
        <span class="chip">${t("chip.amplicon")}: <b>${p.product_size} bp</b></span>${gcChip(p.amplicon)}
        ${qualityChips(p, konumCipi(i.chrom, p.amplicon_genomic_start, p.amplicon_genomic_end, i.assembly))}
      </div>
      <table class="primer-table">${tableHead(`<th>${t("th.pos")}</th><th title="${t("th.region.title")}">${t("th.region")}</th>`)}
        <tbody>${row("dir.forward", "dir-f", v.forward)}${row("dir.reverse", "dir-r", v.reverse)}</tbody>
      </table>
      ${hairpinSatiri(p, v !== p)}
      ${specFooter(p)}
    </div>`;
}

// cDNA satiri: genomik pozisyon yerine EKSON + cDNA konumu
function cdnaRow(dirKey, cls, x) {
  const exons = x.exons.join("/");
  const jFlag = x.spans_junction
    ? `<span class="j-flag" title="${t("flag.junction.title")}">${t("flag.junction")}</span>` : "";
  return `
    <tr>
      <td class="${cls}">${t(dirKey)}</td>
      ${seqCell(x)}
      <td class="sayi">${x.length}</td><td class="sayi">${x.tm}</td><td class="sayi">${x.gc}</td>
      <td>${exons} ${jFlag}</td>
      <td>${x.cdna_start.toLocaleString(yerel())}–${x.cdna_end.toLocaleString(yerel())}</td>
      ${qualCells(x)}
    </tr>`;
}

// RNA kartlari: urunun genomik araligi (intronlar dahil) - IGV genomda gosterir. RNA sekmesi her zaman
// GRCh38 / MANE ile calisir; ipucundaki derleme motorun kullandigidir (input.assembly).
const rnaKonumCipi = (p, j) => konumCipi(((j && j.transcript) || {}).chrom, p.amplicon_genomic_start,
  p.amplicon_genomic_end, ((j && j.input) || {}).assembly);

// Primerlerden biri ekson sinirini tasarim kuralindaki kadar asiyorsa (motor: junction_solid;
// 3' tarafta >= 4, 5' tarafta >= 7 baz) o cift genomik DNA'dan urun vermez. Sinira bir iki bazla
// degen primer gDNA'ya baglanabilir: o ciftte boy yazilmaya devam eder.
const sinirdaPrimer = (p) => !!(p.forward.junction_solid || p.reverse.junction_solid);

// RNA kartlarinda (Varyant ve ekson atlama) gDNA cipi. Sinirda primer varsa boy yazilmaz,
// "cogalmaz" yazilir (boy yazmak yaniltirdi); yoksa genomik DNA'daki urun boyu (intronlar dahil).
function gdnaCipi(p, ipucu) {
  if (sinirdaPrimer(p)) {
    return `<span class="chip chip-ok" title="${t("chip.gdna.noneTitle")}">${t("chip.gdna")}: <b>${t("chip.gdna.none")}</b></span>`;
  }
  return p.gdna_product_size
    ? `<span class="chip" title="${t(ipucu)}">${t("chip.gdna")}: <b>${p.gdna_product_size.toLocaleString(yerel())} bp</b></span>` : "";
}

function renderCdnaPair(p, j) {
  const gdna = gdnaCipi(p, "chip.gdna.title");
  const junc = p.junctions_in_amplicon > 0
    ? `<span class="chip chip-ok" title="${t("chip.junctions.title")}">${t("chip.junctions")}: <b>${p.junctions_in_amplicon}</b></span>`
    : `<span class="chip chip-warn" title="${t("chip.noJunction.title")}">${t("chip.noJunction")}</span>`;
  return `
    <div class="pair-card">
      <div class="pair-head">
        <span class="rank-badge">${p.rank}</span>
        <span class="chip">${t("chip.cdnaProduct")}: <b>${p.product_size} bp</b></span>${gcChip(p.amplicon)}
        ${gdna}${junc}
        ${qualityChips(p, `<span class="chip">${t("chip.exons")}: <b>${p.amplicon_exons.join(", ")}</b></span>${rnaKonumCipi(p, j)}`)}
      </div>
      <table class="primer-table">${cdnaHead()}
        <tbody>${cdnaRow("dir.forward", "dir-f", p.forward)}${cdnaRow("dir.reverse", "dir-r", p.reverse)}</tbody>
      </table>
      ${hairpinSatiri(p)}
      ${specFooter(p)}
    </div>`;
}

// Bitisik olmayan secimde beklenen bantlar (CSV hucresi): "d4=412; d6=578; d4+6=299"
// (CSV'de BOM yok: ASCII "d4=412" yazilir, Turkce/Yunanca harfle sorun cikmaz)
function bantMetni(p) {
  return (p.bands || []).map((b) => `d${b.exons.join("+")}=${b.size}`).join("; ");
}

function renderSkipPair(p, j) {
  const warn = p.low_resolution ? "chip-warn" : "chip-ok";
  if (p.bands && p.bands.length) {
    const yakin = new Set((p.band_close || []).flat());
    const chips = p.bands.map((b) => `<span class="chip ${yakin.has(b.size) ? "chip-warn" : "chip-ok"}" title="${t("chip.bandsTitle")}">Δ${b.exons.join("+")}: <b>${b.size} bp</b></span>`).join("");
    const yakinMetin = (p.band_close || []).map((c) => esc(t("ex.yakin", c[0], c[1]))).join(" ");
    const gdna2 = gdnaCipi(p, "chip.gdna.titleSkip");
    return `
    <div class="pair-card">
      <div class="pair-head">
        <span class="rank-badge">${p.rank}</span>
        <span class="chip chip-ok" title="${t("chip.normal.title")}">${t("chip.normal")}: <b>${p.product_size_normal} bp</b></span>${chips}${gcChip(p.amplicon)}
        ${gdna2}
        ${qualityChips(p, `<span class="chip">${t("chip.exons")}: <b>${p.amplicon_exons.join(", ")}</b></span>${rnaKonumCipi(p, j)}`)}
      </div>
      ${yakinMetin ? `<p class="hint hint-warn pair-bands">${yakinMetin}</p>` : ""}
      <table class="primer-table">${cdnaHead()}
        <tbody>${cdnaRow("dir.forward", "dir-f", p.forward)}${cdnaRow("dir.reverse", "dir-r", p.reverse)}</tbody>
      </table>
      ${hairpinSatiri(p)}
      ${specFooter(p)}
    </div>`;
  }
  const gdna = gdnaCipi(p, "chip.gdna.titleSkip");
  return `
    <div class="pair-card">
      <div class="pair-head">
        <span class="rank-badge">${p.rank}</span>
        <span class="chip chip-ok" title="${t("chip.normal.title")}">${t("chip.normal")}: <b>${p.product_size_normal} bp</b></span>
        <span class="chip chip-ok" title="${t("chip.skipped.title")}">${t("chip.skipped")}: <b>${p.product_size_skipped} bp</b></span>${gcChip(p.amplicon)}
        <span class="chip ${warn}" title="${t("chip.diff.title")}">${t("chip.diff")}: <b>${p.band_difference} bp</b></span>
        ${gdna}
        ${qualityChips(p, `<span class="chip">${t("chip.exons")}: <b>${p.amplicon_exons.join(", ")}</b></span>${rnaKonumCipi(p, j)}`)}
      </div>
      <table class="primer-table">${cdnaHead()}
        <tbody>${cdnaRow("dir.forward", "dir-f", p.forward)}${cdnaRow("dir.reverse", "dir-r", p.reverse)}</tbody>
      </table>
      ${hairpinSatiri(p)}
      ${specFooter(p)}
    </div>`;
}

function seqRow(dirKey, cls, x, isPair) {
  const region = isPair
    ? `<b>${t(x.region === "F" ? "seq.region1" : "seq.region2")}</b> · ` : "";
  return `
    <tr>
      <td class="${cls}">${t(dirKey)}</td>
      ${seqCell(x)}
      <td class="sayi">${x.length}</td><td class="sayi">${x.tm}</td><td class="sayi">${x.gc}</td>
      <td>${region}${x.seq_start.toLocaleString(yerel())}–${x.seq_end.toLocaleString(yerel())}</td>
      ${qualCells(x)}
    </tr>`;
}

function renderSeqPair(p, j) {
  const isPair = j.mode === "sequence_pair";
  // Mesafe bilinmiyorsa "amplikon" sayisi gercek bir urunu temsil etmez
  const vague = isPair && j.input.free_product_size;
  const amplicon = vague
    ? `<span class="chip" title="${t("chip.assumeContig.title")}">${t("chip.amplicon")}: <b>${p.product_size} bp</b> <span class="muted-note">${t("chip.assumeContig")}</span></span>`
    : `<span class="chip">${t("chip.amplicon")}: <b>${p.product_size} bp</b></span>${gcChip(p.amplicon)}`;
  return `
    <div class="pair-card">
      <div class="pair-head">
        <span class="rank-badge">${p.rank}</span>
        ${amplicon}
        ${qualityChips(p, isPair ? "" : `<span class="chip">${t("chip.position")}: <b>${p.amplicon_start.toLocaleString(yerel())}–${p.amplicon_end.toLocaleString(yerel())}</b></span>`)}
      </div>
      <table class="primer-table">${tableHead(`<th>${t(isPair ? "th.regionPos" : "th.pos")}</th>`)}
        <tbody>${seqRow("dir.forward", "dir-f", p.forward, isPair)}${seqRow("dir.reverse", "dir-r", p.reverse, isPair)}</tbody>
      </table>
      ${hairpinSatiri(p)}
      ${specFooter(p)}
    </div>`;
}

// ---------------- kirilma noktasi (delesyon / duplikasyon) ----------------
const bpBoy = (a, b) => (a === b
  ? `${a.toLocaleString(yerel())} bp` : `${a.toLocaleString(yerel())}–${b.toLocaleString(yerel())} bp`);

function renderBpSummary(j) {
  const i = j.input;
  return `
    <span>${t("sum.genome")}: <b>${i.assembly}</b></span>
    <span>${t("sum.region")}: <b>chr${esc(i.chrom)}:${i.start.toLocaleString(yerel())}–${i.end.toLocaleString(yerel())}</b>
      (${i.length.toLocaleString(yerel())} bp)</span>
    <span>${t("sum.type")}: <b>${t(i.type === "del" ? "bp.mode.del" : "bp.mode.dup")}</b></span>
    <span>${t("sum.approach")}: <b>${t("bp.approach." + i.approach)}</b></span>
    ${i.margin ? `<span>${t("sum.margin")}: <b>±${i.margin.toLocaleString(yerel())} bp</b></span>` : ""}
    <span>${t("sum.found")}: <b>${j.num_returned}</b></span>`;
}

// Genotipe gore beklenen bantlar: kullanicinin jeli okurken asil sorusu bu.
function bpBantlar(p, j) {
  const i = j.input, b = p.bp, k = p.control;
  const kontrol = k ? `${k.band.toLocaleString(yerel())} bp (${t("bp.dir.control")})` : null;
  const birlestir = (liste) => liste.filter(Boolean).join(" + ") || t("bp.noBand");
  let satirlar;
  if (i.type === "del") {
    // Sinir ustundeki normal alel bandi tablodan SILINMEZ, isaretlenir: "700 bp'nin
    // ustu cogalmaz" mutlak bir gercek degil, kullanicinin kendi ayari (2026-10-25).
    const normal = `${b.wt.toLocaleString(yerel())} bp${
      b.wt_status === "var" ? "" : ` (${t("bp.wt." + b.wt_status)})`}`;
    const mut = bpBoy(b.mut_min, b.mut_max);
    satirlar = [["bp.gt.normal", birlestir([normal, kontrol])],
                ["bp.gt.het", birlestir([mut, normal, kontrol])],
                ["bp.gt.homDel", birlestir([mut])]];
  } else if (i.approach === "tandem_junction") {
    satirlar = [["bp.gt.normal", birlestir([kontrol])],
                ["bp.gt.dup", birlestir([bpBoy(b.junction_min, b.junction_max), kontrol])]];
  } else {
    const dup = bpBoy(b.dup_min, b.dup_max);
    satirlar = [["bp.gt.normal", `${b.wt.toLocaleString(yerel())} bp`],
                ["bp.gt.hetDup", birlestir([`${b.wt.toLocaleString(yerel())} bp`, dup])],
                ["bp.gt.homDup", dup]];
  }
  return `
    <table class="spec-table bp-bands">
      <thead><tr><th>${t("bp.th.genotype")}</th><th>${t("bp.th.bands")}</th></tr></thead>
      <tbody>${satirlar.map(([g, v]) => `<tr><td>${t(g)}</td><td>${esc(v)}</td></tr>`).join("")}</tbody>
    </table>`;
}

function renderBpPair(p, j) {
  const i = j.input, b = p.bp, k = p.control;
  // Eksi iplikteki gende F/R genin yonunde (yon.js). Kontrol primeri motorda genomik F ile
  // (silinen bolgenin basi / dup'in sagi) ya da obur uctan genomik R ile bant verir
  // (k.pairs_with); dimer uyarisi tupteki UCUNCU primere bakar. Metinler gosterilen adi kullanir.
  const v = genYonunde(p), cevrik = v !== p;
  const fAd = t(cevrik ? "dir.reverse" : "dir.forward").toLowerCase();
  const rAd = t(cevrik ? "dir.forward" : "dir.reverse").toLowerCase();
  const kR = !!k && k.pairs_with === "reverse";
  // IGV konumu: F, R ve (varsa) kontrol primerini kapsayan referans araligi
  const aralik = primerAraligi(p.forward, p.reverse, k);
  const esAd = kR ? rAd : fAd, digerAd = kR ? fAd : rAd;
  const digerDimer = k ? (kR ? k.dimer_with_f : k.dimer_with_r) : null;
  const row = (dirKey, cls, x) => `
    <tr>
      <td class="${cls}">${t(dirKey)}</td>
      ${seqCell(x)}
      <td class="sayi">${x.length}</td><td class="sayi">${x.tm}</td><td class="sayi">${x.gc}</td>
      <td>${x.genomic_start.toLocaleString(yerel())}–${x.genomic_end.toLocaleString(yerel())}</td>
      ${bolgeCell(x)}
      ${qualCells(x)}
    </tr>`;
  // wtCip: normal alelin bandi. Asagidaki genotip tablosu da gosterdigi icin ikincil
  // satirda; onde yalnizca bandi tanimlayan cipler (6 cip iki satira tasiyordu).
  let ana, wtCip;
  if (i.type === "del") {
    const cls = b.wt_status === "var" ? "" : b.wt_status === "zayif" ? "chip-warn" : "";
    ana = `<span class="chip chip-ok" title="${t("bp.chip.mut.title")}">${t("bp.chip.mut")}: <b>${bpBoy(b.mut_min, b.mut_max)}</b></span>`;
    wtCip = `<span class="chip ${cls}" title="${t("bp.chip.wt.title")}">${t("bp.chip.wt")}: <b>${b.wt.toLocaleString(yerel())} bp</b> · ${t("bp.wt." + b.wt_status)}</span>`;
  } else if (i.approach === "tandem_junction") {
    ana = `<span class="chip chip-ok" title="${t("bp.chip.junction.title")}">${t("bp.chip.junction")}: <b>${bpBoy(b.junction_min, b.junction_max)}</b></span>`;
    wtCip = `<span class="chip" title="${t("bp.chip.noWt.title")}">${t("bp.chip.noWt")}</span>`;
  } else {
    ana = `<span class="chip chip-ok">${t("bp.chip.dupBand")}: <b>${bpBoy(b.dup_min, b.dup_max)}</b></span>`;
    wtCip = `<span class="chip">${t("bp.chip.wtShort")}: <b>${b.wt.toLocaleString(yerel())} bp</b></span>`;
  }
  const kontrolCip = k
    ? `<span class="chip" title="${t("bp.chip.control.title", esAd)}">${t("bp.chip.control")}: <b>${k.band.toLocaleString(yerel())} bp</b></span>`
    : "";
  // Uc primer ayni tupte: kontrol primeri bant vermedigi DIGER primerle de dimer kurmamali
  const kontrolUyari = digerDimer != null && digerDimer >= 6
    ? `<p class="note note-warn">${esc(t("bp.controlDimer", digerDimer, digerAd))}</p>` : "";
  const kontrolYok = i.control && !k && p.control_reason
    ? `<p class="note">${esc(t("bp.controlMissing", p.control_reason))}</p>` : "";
  // Ozgulluk dugmesi yalnizca F+R'yi tarar; kontrol primeri esiyle normal referansta
  // siradan bir urun verdigi icin Degerlendir'de es + Kontrol olarak taranabilir.
  const kontrolIpucu = k ? `<p class="hint">${t("bp.controlSpecHint", esAd)}</p>` : "";
  return `
    <div class="pair-card">
      <div class="pair-head">
        <span class="rank-badge">${p.rank}</span>
        ${ana}${kontrolCip}${gcChip(p.amplicon)}
        ${qualityChips(p, wtCip + (aralik ? konumCipi(i.chrom, aralik[0], aralik[1], i.assembly) : ""))}
      </div>
      <table class="primer-table">${tableHead(`<th>${t("th.pos")}</th><th title="${t("th.region.title")}">${t("th.region")}</th>`)}
        <tbody>${row("dir.forward", "dir-f", v.forward)}${row("dir.reverse", "dir-r", v.reverse)}${
          k ? row("bp.dir.control", "dir-k", k) : ""}</tbody>
      </table>
      ${hairpinSatiri(p, cevrik)}
      ${kontrolUyari}${kontrolYok}
      ${bpBantlar(p, j)}${kontrolIpucu}
      ${specFooter(p, { noEval: true })}
    </div>`;
}

// ---------------- hazir primer degerlendirme ----------------
let EV_MODE = "dna";               // "dna" (genom taramasi) | "cdna" (transkript)
let lastEval = null;               // son degerlendirme sonucu (amplikon gosterimi icin)

function setEvalMode(mode) {
  EV_MODE = mode;
  document.querySelectorAll(".ev-mode-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.emode === mode));
  $("field-ev-acc").classList.toggle("hidden", mode !== "cdna");
  if (mode !== "cdna") $("evTxList").classList.add("hidden");
  // Calisan istek iptal edilir ve onun (ya da bitmis oteki modun) sonucu temizlenir:
  // DNA tablosu RNA ekraninda cizilmesin, gec gelen cevap panele yazilmasin.
  evalIptalEt();
  lastEval = null; lastEvalIstek = null; EV_AMP_ACIK = null;
  $("evalResult").innerHTML = "";
  EV_HATA = null;
  evalMsg("");
}

// NM_ alanina gen sembolu de yazilabilir; dugme onu transkript listesine cevirir
async function evFindTranscripts() {
  const q = $("ev_acc").value.trim();
  if (!q) { evalMsg(t("err.needGene"), "error"); return; }
  evalMsg(t("msg.searching"));
  try {
    const r = await motor(api(
      `/transcripts?gene=${encodeURIComponent(q)}&assembly=${ASSEMBLY}&lang=${LANG}`));
    const j = await okuJson(r);
    if (j.error) { evalMsg(j.error, "error"); $("evTxList").classList.add("hidden"); return; }
    $("evTxList").innerHTML = txSatirlariHtml(j.transcripts, rnaDerlemeNotu(j.assembly));
    $("evTxList").classList.remove("hidden");
    evalMsg("");
  } catch (e) {
    evalMsg(t("msg.error", e.message), "error");
  }
}

let EV_IPTAL = null;         // calisan Degerlendir isteginin AbortController'i
let lastEvalIstek = null;    // lastEval'i ureten istek {path, body}: dil degisince tekrarlanir

function evalCiz(j) {
  EV_AMP_ACIK = null;
  $("evalResult").innerHTML = j.mode === "cdna" ? renderEvaluationCdna(j) : renderEvaluation(j);
  favDurumlariniCiz();
}

// Calisan Degerlendir istegini iptal eder ve dugmeyi normale dondurur. Iptal edilen
// istegin kendi "finally"si yeni bir istegin durumunu bozmasin diye EV_IPTAL burada
// hemen bosaltilir; runEvaluate yalniz kendi denetleyicisi hala gecerliyse temizler.
function evalIptalEt() {
  if (!EV_IPTAL) return;
  EV_IPTAL.abort();
  EV_IPTAL = null;
  $("evalBtn").textContent = t("ev.run");
}

// Ana dugme: tarama surerken "Iptal" yazar ve istegi iptal eder (bilincli islev).
function evalDugmesi() {
  if (EV_IPTAL) { evalIptalEt(); evalMsg(""); return; }
  runEvaluate();
}

// runEvaluate her zaman YENI bir degerlendirme baslatir; surmekte olan istek varsa once
// iptal edilir (kart dugmeleri: eski cift yerine yeni cift degerlendirilir).
async function runEvaluate() {
  evalIptalEt();
  const fwd = $("ev_fwd").value.trim();
  const rev = $("ev_rev").value.trim();
  if (!fwd) { evalHatasi(() => t("err.needSeq")); return; }

  const cdna = EV_MODE === "cdna";
  const acc = $("ev_acc").value.trim();
  if (cdna && !acc) { evalHatasi(() => t("ev.err.needAcc")); return; }

  EV_HATA = null;
  const ben = new AbortController();     // bu istegin kimligi: iptal edilmisse sonucu yazilmaz
  EV_IPTAL = ben;
  $("evalBtn").textContent = t("act.cancel");
  evalMsg(t("ev.running"));
  $("evalResult").innerHTML = "";
  try {
    const govde = { forward: fwd, reverse: rev || null,
                    assembly: ASSEMBLY, lang: LANG };
    if (cdna) govde.acc = acc;
    const hedefKonum = $("ev_hedef").value.trim();
    if (hedefKonum) govde.target = hedefKonum;
    govde.params = {};
    for (const id of KOSUL_IDS) {
      const v = $(id) && $(id).value.trim();
      if (v !== "" && v != null) govde.params[id] = v;
    }
    const yol = cdna ? "/evaluate_cdna" : "/evaluate";
    const r = await motor(api(yol), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(govde),
      signal: ben.signal,
    });
    const j = await okuJson(r);
    if (EV_IPTAL !== ben) return;        // iptal edildi (ana dugme, yeni cift ya da mod degisimi)
    if (j.error) { evalHatasi(() => j.error); return; }
    lastEval = j;
    lastEvalIstek = { path: yol, body: govde };
    evalCiz(j);
    evalMsg("");
    sonucaKaydir($("evalResult"));
    if (govde.lang !== LANG) setTimeout(degerlendirmeDiliniYenile);   // istek surerken dil degisti
  } catch (e) {
    if (EV_IPTAL !== ben) return;        // iptal edilmis istek yeni istegin durumuna dokunmaz
    if (e.name === "AbortError") evalMsg("");
    else evalHatasi(() => istekHatasi(e));
  } finally {
    if (EV_IPTAL === ben) {
      EV_IPTAL = null;
      $("evalBtn").textContent = t("ev.run");
    }
  }
}

// Degerlendir sekmesinde amplikon gosterimi. Urun tablosu bir tablo oldugu icin
// satir icine acilir kutu koymak yerine tablonun ALTINDA tek bir kutu kullanilir;
// ayni dugmeye tekrar basmak kapatir, baska bir dugme icerigi degistirir.
let EV_AMP_ACIK = null;

function toggleEvalAmplicon(btn) {
  const j = lastEval;
  const kutu = $("ev-amp");
  if (!j || !kutu) return;
  const idx = btn.dataset.idx;
  let kaynak;
  if (idx === "product") kaynak = j.product;                        // RNA modu
  else if (idx.startsWith("low-"))                                  // dusuk olasilikli
    kaynak = (j.products_low_items || [])[parseInt(idx.slice(4), 10)];
  else kaynak = (j.products || [])[parseInt(idx, 10)];
  const a = idx === "product" ? kaynak : (kaynak || {}).amplicon;
  if (!a || !a.sequence) return;

  document.querySelectorAll("#evalResult .amp-btn").forEach((b) => {
    b.textContent = t("amp.btn");
  });
  if (EV_AMP_ACIK === idx) {          // ayni dugme -> kapat
    kutu.innerHTML = "";
    EV_AMP_ACIK = null;
    return;
  }
  const ad = j.mode === "cdna"
    ? `${j.transcript.gene}_${j.transcript.mane_acc || j.transcript.acc}`
    : `chr${kaynak.chrom}_${kaynak.start}-${kaynak.end}`;
  // Uclardaki primerler: DNA'da urunun kendi kaydi (F+R, R+F, F+F, R+R); cDNA'da
  // roller yer degismisse kullanicinin R'si solda. R+F urun F'den baslayacak sekilde
  // cevrilir (yon.js), lejant ve FASTA basligi bunu soyler.
  const cdnaUrun = idx === "product";
  const u = degerlendirmeUrunu(a,
    cdnaUrun ? (j.roles_swapped ? "R" : "F") : kaynak.forward_primer || "F",
    cdnaUrun ? (j.roles_swapped ? "F" : "R") : kaynak.reverse_primer || "R");
  kutu.innerHTML = renderAmplicon(u.amplicon, {
    name: ad,
    targetLabel: (lastEvalIstek && lastEvalIstek.body.target) || "",
    fwdLabel: t(u.sol === "F" ? "amp.fwd" : "amp.rev.self"),
    revLabel: t(u.sag === "R" ? "amp.rev" : "amp.fwd.rc"),
    note: u.ters ? t("amp.fromF") : null,
    fasta: u.ters ? `>${ad} ${t("amp.fromF")}\n${u.amplicon.sequence}` : null });
  btn.textContent = t("amp.btn.hide");
  EV_AMP_ACIK = idx;
}

function evalMsg(text, kind = "") {
  const m = $("evalMsg");
  m.textContent = text;
  m.className = "msg" + (kind ? " " + kind : "");
}

// DNA ve RNA degerlendirmesinin ORTAK parcalari: karar cubugu, primer ozellik
// tablosu ve bulgu listesi. Iki modda da ayni oldugu icin tek yerde durur.
function evVerdictBar(j) {
  return `<div class="verdict-bar verdict-${j.verdict}">${t("ev.verdict." + j.verdict)}</div>`;
}

// Urun tablosunun tek satiri. idx amplikon dugmesinin adresidir:
// "3" -> normal listenin 3. ogesi, "low-3" -> dusuk olasiliklilarin 3.'su.
function evProductRow(o, idx) {
  const a = o.amplicon || {};
  const gc = a.gc_percent == null ? "" :
    ` <span class="${a.gc_flag === "cok_yuksek" ? "gc-bad" : a.gc_flag ? "gc-warn" : "gc-ok"}"
        title="${a.gc_note ? esc(a.gc_note) : t("chip.gc.title")}">GC ${t("fmt.pct", a.gc_percent)}</span>`;
  return `
    <tr class="risk-${o.risk}">
      <td><span class="risk-dot risk-${o.risk}"></span>${t("risk." + o.risk)}</td>
      <td>${o.combination}</td>
      <td>chr${esc(o.chrom)}:${o.start.toLocaleString(yerel())}–${o.end.toLocaleString(yerel())}</td>
      <td>${o.size.toLocaleString(yerel())} bp${gc}</td>
      <td>${o.forward_primer} ${o.mismatch_forward} / ${o.reverse_primer} ${o.mismatch_reverse}</td>
      <td>${o.amplicon ? `<button class="amp-btn" data-idx="${idx}">${t("amp.btn")}</button>` : "—"}</td>
    </tr>`;
}

function toggleLowProducts(btn) {
  const j = lastEval;
  const tablo = $("ev-products");
  if (!j || !tablo) return;
  const govde = tablo.querySelector("tbody");
  const acik = btn.dataset.open === "1";
  if (acik) {
    govde.querySelectorAll("tr.low-row").forEach((r) => r.remove());
    btn.dataset.open = "0";
    btn.textContent = t("ev.showLow", j.products_low);
    return;
  }
  const satirlar = (j.products_low_items || [])
    .map((o, i) => evProductRow(o, "low-" + i).replace('<tr class="', '<tr class="low-row '))
    .join("");
  govde.insertAdjacentHTML("beforeend", satirlar
    + (j.products_low_truncated
      ? `<tr class="low-row"><td colspan="6" class="dl-meta">${
          t("ev.lowTruncated", (j.products_low_items || []).length, j.products_low)}</td></tr>`
      : ""));
  btn.dataset.open = "1";
  btn.textContent = t("ev.hideLow");
}

function evFindings(j) {
  const sira = { sorun: 0, uyari: 1, bilgi: 2 };
  return j.findings.length ? `
    <h4>${t("ev.findings")}</h4>
    <div class="ev-findings">${[...j.findings]
      .sort((a, b) => sira[a.level] - sira[b.level])
      .map((f) => `<div class="ev-finding ev-${f.level}">
        <span class="ev-badge ev-${f.level}">${t("ev.level." + f.level)}</span>
        <span>${esc(f.text)}</span></div>`).join("")}</div>` : "";
}

function renderEvaluation(j) {
  const bas = evVerdictBar(j);

  // --- primer ozellikleri ---
  const satir = (ad, m) => `
    <tr>
      <td class="${ad === "forward" ? "dir-f" : "dir-r"}">${t("dir." + ad)}</td>
      <td class="seq">5'-${m.sequence}-3'
        <button class="copy-btn" data-seq="${m.sequence}" title="${t("copy.title")}">${t("copy.btn")}</button></td>
      <td class="sayi">${m.length}</td><td class="sayi">${m.tm}</td><td class="sayi">${m.gc}</td>
      <td class="sayi">${m.hairpin_tm}</td><td class="sayi">${m.self_any ?? "—"}</td><td class="sayi">${m.self_end ?? "—"}</td>
      <td>${m.gc_clamp ? "✓" : "—"}</td><td class="sayi">${m.poly_x}</td>
    </tr>`;
  const ozellik = `
    <h4>${t("ev.props")}</h4>
    <table class="primer-table">
      <thead><tr>
        <th>${t("th.dir")}</th><th>${t("th.seq")}</th><th class="sayi">${t("ev.th.len")}</th>
        <th class="sayi">${t("th.tm")}</th><th class="sayi">${t("th.gc")}</th>
        <th class="sayi" title="${t("th.hairpin.title")}">${t("th.hairpin")}</th>
        <th class="sayi" title="${t("th.self.title")}">${t("th.self")}</th><th class="sayi" title="${t("ev.th.self3.title")}">${t("ev.th.self3")}</th>
        <th>${t("ev.th.clamp")}</th><th class="sayi">${t("ev.th.poly")}</th>
      </tr></thead>
      <tbody>${Object.entries(j.primers).map(([k, m]) => satir(k, m)).join("")}</tbody>
    </table>
    ${j.pair ? `<p class="dl-meta">${t("ev.dTm")}: <b>${j.pair.delta_tm} °C</b> ·
       <span title="${t("chip.ta.title")}">${t("chip.ta")}: <b>${j.pair.ta_suggested} °C</b></span> ·
       <span title="${t("ev.heteroTm.title")}">${t("ev.heteroTm")}: <b>${j.pair.hetero_dimer_tm} °C</b></span> ·
       <span title="${t("chip.dimer.title")}">${t("chip.dimer")}: <b>${j.pair.compl_any ?? "—"}</b></span> ·
       <span title="${t("ev.hetero3.title")}">${t("ev.hetero3")}: <b>${j.pair.compl_end ?? "—"}</b></span></p>` : ""}
    ${tmNotu(j)}
    ${favDugmesi('data-ev="1"', "fav-ev")}`;

  // --- baglanma bolgeleri ---
  let bolge = "";
  if (j.genome_used) {
    const blok = Object.entries(j.sites).map(([ad, list]) => {
      const c = j.counts[ad] || {};
      const rows = list.map((s) => {
        // Tasarim tablosuyla ayni etiket ("intron 45", "ekzon 3 / intron 3 siniri"); eskiden
        // intron numarasiz "intron" yaziyordu. Transkript ipucunda. Eski motor yedegi altta.
        const gb = s.gene_region;
        const yer = gb
          ? `<span title="${esc(t("th.region.cell", gb.gene || "?", gb.acc || "?", gb.mane ? " · " + gb.mane : "", gb.exon_count || "?") + (gb.kod_isareti ? " · " + t("region.kod") : ""))}">${esc(((s.genes || []).length > 1 && gb.gene ? gb.gene + "\u00a0· " : "") + bolgeEtiket(gb))}</span>`
          : s.region === "exon" ? t("ev.region.exon", s.exon)
          : s.region === "intron" ? t("ev.region.intron") : "—";
        const gen = (s.genes || []).join(", ") || "—";
        const snp = (s.snps || []).length
          ? ` <span class="j-flag" style="background:rgba(var(--danger-rgb),.15);color:var(--danger);border-color:var(--danger)">${
              s.snps.map((x) => x.rsid).join(", ")}</span>` : "";
        return `<tr class="${s.mismatch === 0 ? "" : "risk-dusuk"}">
          <td>chr${esc(s.chrom)}:${s.five_prime.toLocaleString(yerel())}</td>
          <td>${s.orientation}</td><td><b>${s.mismatch}</b></td>
          <td>${esc(gen)}</td><td>${yer}${snp}</td></tr>`;
      }).join("");
      return `
        <h4>${t("dir." + ad)} — ${t("ev.sites")}
          <span class="dl-meta">${t("ev.siteCount", c.perfect || 0, c.good || 0, (c.total || 0).toLocaleString(yerel()))}</span></h4>
        <table class="spec-table"><thead><tr>
          <th>${t("ev.th.site")}</th><th>${t("ev.th.orient")}</th><th>${t("ev.th.mm")}</th>
          <th>${t("sum.gene")}</th><th>${t("ev.th.where")}</th>
        </tr></thead><tbody>${rows}</tbody></table>`;
    }).join("");
    bolge = blok;
  } else {
    bolge = `<p class="note note-warn">${t("ev.noGenome")}</p>`;
  }

  // --- urunler ---
  let urun = "";
  if (j.genome_used && j.pair) {
    // Dusuk olasilikli urunler varsayilan olarak gizli ama ATILMIYOR;
    // dugmeyle acilir. Sayiyi soyleyip listeyi hic vermemek, "acaba orada
    // ne vardi" sorusunu cevapsiz birakiyordu.
    const lowBtn = j.products_low
      ? `<button class="amp-btn low-btn" data-open="0">${t("ev.showLow", j.products_low)}</button>
         <p class="hint" style="margin:6px 0 0">${t("ev.lowExplain")}</p>`
      : "";
    // Tekrar dizisinde motor urun tahminini bilerek yapmaz (bellek siniri);
    // bos liste "urun yok" demek DEGIL, "sayilamayacak kadar cok" demek.
    const ov = j.overflow || {};
    if (ov.forward || ov.reverse || ov.products) {
      urun = `<h4>${t("ev.products")}</h4><p class="note note-warn">${t("ev.overflow")}</p>`;
    } else if (j.products.length || j.products_low) {
      urun = `<h4>${t("ev.products")}</h4>
        <table class="spec-table" id="ev-products"><thead><tr>
          <th>${t("spec.th.risk")}</th><th>${t("spec.th.combo")}</th>
          <th>${t("spec.th.loc")}</th><th>${t("spec.th.product")}</th>
          <th>${t("spec.th.mismatch")}</th><th>${t("amp.th")}</th>
        </tr></thead><tbody>${j.products.map((o, i) => evProductRow(o, String(i))).join("")}</tbody></table>
        ${evYakinNot(j)}
        ${lowBtn}
        <div id="ev-amp"></div>`;
    } else {
      urun = `<h4>${t("ev.products")}</h4><p class="note note-warn">${t("ev.noProduct")}</p>${evYakinNot(j)}`;
    }
  }

  // Bulgular karar cubugunun hemen altinda: kullanicinin ilk sorusu "sorun ne?";
  // eskiden uzun urun tablolarinin arkasinda, sayfanin en altinda kaliyordu.
  return `<div class="ev-result">${bas}${evFindings(j)}${ozellik}${bolge}${urun}</div>`;
}

// "Kopyadan yalnizca tek baz farki var - temkinli olun": taramanin 3' kurali yuzunden listede olmayan ama
// yalnizca 1-2 baz farkla urun verebilecek yer (motor: evaluate._yakin_kopya; kullanici onayi 2026-11-09).
// Yalnizca bilgi: liste ve karar degismez.
function evYakinNot(j) {
  const n = j.near_copy;
  if (!n) return "";
  const sayi = (x) => x.toLocaleString(yerel());
  const konum = `chr${n.chrom}:${sayi(n.start)}–${sayi(n.end)}`;
  // gen adi varsa "CYP21A1P bolgesinde (konum, boy)", yoksa "konum bolgesinde (boy)"
  const gen = n.genes && n.genes.length ? esc(n.genes.join(", ")) : null;
  const parca = n.sites.map((s) => t("ev.yakin.primer", s.primer === "forward" ? "F" : "R",
    s.mismatches.map((m) => [t("ev.yakin.yer", m.from_3p), t("ev.yakin.cift", m.primer_base, m.template_base)])));
  return `<div class="note note-warn" id="ev-yakin"><b>${t("ev.yakin.title", n.total)}</b><br>
    ${t("ev.yakin.text", gen || konum, gen ? konum : null, sayi(n.size), n.combination, parca.join(", "), n.total, n.count)}</div>`;
}

// ---------------- RNA / cDNA degerlendirmesi ----------------
// DNA modundan farki: genom degil TRANSKRIPT esas alinir. Ekson sinirina oturan
// bir primer genomda butun halde bulunmadigi icin DNA modu ona yanlis alarm
// veriyor; burada primerin hangi eksonlarda oturdugu ve urunun intron kapsayip
// kapsamadigi gosterilir.
function renderEvaluationCdna(j) {
  const tx = j.transcript;
  const mane = tx.mane_status
    ? `<span class="mane ${tx.mane_status === "MANE Select" ? "mane-sel" : "mane-plus"}">${esc(tx.mane_status)}</span>`
    : "";
  const baslik = `
    <div class="summary">
      <span>${t("sum.transcript")}: <b>${esc(tx.mane_acc || tx.acc)}</b> ${mane}</span>
      <span>${esc(tx.gene)} · ${t("sum.exonCount", tx.exon_count)} · ${tx.cdna_length.toLocaleString(yerel())} nt</span>
      <span>${t("sum.genome")}: <b>${tx.chrom}</b> (${j.assembly}, ${t("sum.strand", tx.strand)})</span>
    </div>`;

  // --- primer ozellikleri (DNA moduyla ayni tablo) ---
  const satir = (ad, m) => `
    <tr>
      <td class="${ad === "forward" ? "dir-f" : "dir-r"}">${t("dir." + ad)}</td>
      <td class="seq">5'-${m.sequence}-3'
        <button class="copy-btn" data-seq="${m.sequence}" title="${t("copy.title")}">${t("copy.btn")}</button></td>
      <td class="sayi">${m.length}</td><td class="sayi">${m.tm}</td><td class="sayi">${m.gc}</td>
      <td class="sayi">${m.hairpin_tm}</td><td class="sayi">${m.self_any ?? "—"}</td><td class="sayi">${m.self_end ?? "—"}</td>
      <td>${m.gc_clamp ? "✓" : "—"}</td><td class="sayi">${m.poly_x}</td>
    </tr>`;
  const ozellik = `
    <h4>${t("ev.props")}</h4>
    <table class="primer-table">
      <thead><tr>
        <th>${t("th.dir")}</th><th>${t("th.seq")}</th><th class="sayi">${t("ev.th.len")}</th>
        <th class="sayi">${t("th.tm")}</th><th class="sayi">${t("th.gc")}</th>
        <th class="sayi" title="${t("th.hairpin.title")}">${t("th.hairpin")}</th>
        <th class="sayi" title="${t("th.self.title")}">${t("th.self")}</th><th class="sayi" title="${t("ev.th.self3.title")}">${t("ev.th.self3")}</th>
        <th>${t("ev.th.clamp")}</th><th class="sayi">${t("ev.th.poly")}</th>
      </tr></thead>
      <tbody>${Object.entries(j.primers).map(([k, m]) => satir(k, m)).join("")}</tbody>
    </table>
    ${j.pair ? `<p class="dl-meta">${t("ev.dTm")}: <b>${j.pair.delta_tm} °C</b> ·
       <span title="${t("chip.ta.title")}">${t("chip.ta")}: <b>${j.pair.ta_suggested} °C</b></span> ·
       <span title="${t("ev.heteroTm.title")}">${t("ev.heteroTm")}: <b>${j.pair.hetero_dimer_tm} °C</b></span> ·
       <span title="${t("chip.dimer.title")}">${t("chip.dimer")}: <b>${j.pair.compl_any ?? "—"}</b></span> ·
       <span title="${t("ev.hetero3.title")}">${t("ev.hetero3")}: <b>${j.pair.compl_end ?? "—"}</b></span></p>` : ""}
    ${tmNotu(j)}
    ${favDugmesi('data-ev="1"', "fav-ev")}`;

  // --- transkript uzerindeki yerlesim ---
  const yerRows = Object.entries(j.placement).map(([ad, y]) => {
    if (!y) {
      return `<tr class="risk-yuksek"><td class="${ad === "forward" ? "dir-f" : "dir-r"}">${t("dir." + ad)}</td>
        <td colspan="4">${t("ev.cdna.notFound")}</td></tr>`;
    }
    const sinir = y.spans_junction
      ? `<span class="j-flag">${t("ev.cdna.junction", y.five_side, y.three_side)}</span>`
      : "—";
    return `<tr>
      <td class="${ad === "forward" ? "dir-f" : "dir-r"}">${t("dir." + ad)}</td>
      <td>${y.cdna_start.toLocaleString(yerel())}–${y.cdna_end.toLocaleString(yerel())}</td>
      <td>${(y.exons || []).join(", ")}</td>
      <td>${sinir}</td>
      <td><b>${y.mismatch}</b></td>
    </tr>`;
  }).join("");
  const yerlesim = `
    <h4>${t("ev.cdna.placement")}</h4>
    <table class="spec-table"><thead><tr>
      <th>${t("th.dir")}</th><th>${t("ev.cdna.th.pos")}</th>
      <th title="${t("ev.cdna.th.exon.title")}">${t("ev.cdna.th.exon")}</th>
      <th title="${t("ev.cdna.th.junction.title")}">${t("ev.cdna.th.junction")}</th>
      <th title="${t("spec.th.mismatch.title")}">${t("spec.th.mismatch")}</th>
    </tr></thead><tbody>${yerRows}</tbody></table>`;

  // --- urun: cDNA bandi ve gDNA bandi yan yana (RT-PCR'daki asil soru) ---
  let urun = "";
  if (j.product) {
    const u = j.product;
    // Primerlerden biri ekson sinirinin uzerinde ve iki yaninda yeterli bazi varsa (motor:
    // product.gdna_none) genomik DNA'dan bant cikmaz: boy yazilmaz
    const gd = u.gdna_none ? t("chip.gdna.none")
      : u.gdna_size ? `${u.gdna_size.toLocaleString(yerel())} bp`
      : "—";
    urun = `
      <h4>${t("ev.cdna.product")}</h4>
      <div class="summary">
        <span>${t("ev.cdna.cdnaBand")}: <b>${u.cdna_size.toLocaleString(yerel())} bp</b></span>
        ${gcChip(u)}
        <span title="${t("ev.cdna.gdnaBand.title")}">${t("ev.cdna.gdnaBand")}: <b>${gd}</b></span>
        <span>${t("ev.cdna.junctions")}: <b>${u.junctions}</b></span>
        <span>${t("sum.exon")}: <b>${(u.exons || []).join(", ")}</b></span>
      </div>
      ${u.sequence ? `<div class="spec-wrap">
        <button class="amp-btn" data-idx="product">${t("amp.btn")}</button>
        <div id="ev-amp"></div></div>` : ""}`;
  }

  return `<div class="ev-result">${evVerdictBar(j)}${evFindings(j)}${baslik}${ozellik}${yerlesim}${urun}</div>`;
}

// ---------------- veri dosyasi indirme ----------------
// Yoklama SADECE panel acikken veya bir indirme surerken calisir; kapali panelde
// saniyede bir istek atmanin anlami yok.
let DL_TIMER = null;

const mb = (b) => `${Math.round((b || 0) / 1048576).toLocaleString(yerel())} MB`;
const sure = (sn) => {
  if (!isFinite(sn) || sn <= 0) return "";
  const d = Math.round(sn / 60), s = Math.round(sn);
  return d >= 1 ? `${d} dk` : `${s} sn`;
};

async function loadDownloads() {
  try {
    const r = await motor(api(`/downloads?lang=${LANG}`));
    renderDownloads(await okuJson(r));
  } catch (e) { /* motor kapaliysa panel bos kalir */ }
}

function renderDownloads(d) {
  $("dlRoot").innerHTML =
    `${t("dl.root")}: <code>${esc(d.kok)}</code> · ${t("dl.free")}: <b>${
      d.bos_alan ? (d.bos_alan / 1073741824).toFixed(1) + " GB" : "?"}</b>`;

  const sira = ["genome_GRCh37", "genome_GRCh38", "refgene_GRCh37",
    "refgene_GRCh38", "mane", "dbsnp_GRCh37", "dbsnp_GRCh38"];
  $("dlList").innerHTML = sira.filter((k) => d.ogeler[k])
    .map((k) => dlRow(k, d.ogeler[k], d.aktif)).join("");

  const calisiyor = !!d.aktif;
  if (calisiyor && !DL_TIMER) DL_TIMER = setInterval(loadDownloads, 1000);
  if (!calisiyor && DL_TIMER) { clearInterval(DL_TIMER); DL_TIMER = null; }
}

function dlRow(key, o, aktif) {
  const ad = LANG === "en" ? o.name : o.ad;
  const bu = aktif === key;
  const durum = o.durum || "hazir";
  const calisan = bu && (durum === "indiriliyor" || durum === "isleniyor" ||
                         durum === "basliyor");

  let sag;
  if (calisan) {
    sag = `<button class="ghost dl-cancel" data-item="${key}">${t("dl.cancel")}</button>`;
  } else if (o.kurulu) {
    sag = `<span class="dl-ok">✓ ${t("dl.installed")}</span>`;
  } else {
    sag = `<button class="ghost dl-start" data-item="${key}"${aktif ? " disabled" : ""}>${
      durum === "hata" ? t("dl.retry") : t("dl.download")}</button>`;
  }

  let alt = "";
  if (calisan && durum === "indiriliyor" && o.toplam) {
    const yuzde = Math.min(100, (o.indirilen / o.toplam) * 100);
    const kalan = o.hiz > 0 ? (o.toplam - o.indirilen) / o.hiz : 0;
    alt = `
      <div class="dl-bar"><div class="dl-fill" style="width:${yuzde.toFixed(1)}%"></div></div>
      <span class="dl-meta">${t("dl.progress", mb(o.indirilen), mb(o.toplam),
        o.hiz ? mb(o.hiz) : "")}${kalan ? " · " + t("dl.eta", sure(kalan)) : ""}</span>`;
  } else if (calisan) {
    alt = `<div class="dl-bar indeterminate"><div class="dl-fill"></div></div>
           <span class="dl-meta">${esc(o.mesaj || t("dl.state." + durum))}</span>`;
  } else if (durum === "hata" && o.hata) {
    alt = `<span class="dl-meta dl-err">${esc(o.hata)}</span>`;
  } else if (!o.kurulu) {
    alt = `<span class="dl-meta">${t("dl.sizeNote", Math.round(o.yaklasik / 1048576))}</span>`;
  } else {
    alt = `<span class="dl-meta">${mb(o.boyut)} · ${esc(o.kaynak)}</span>`;
  }

  return `<div class="dl-row${o.kurulu ? " dl-done" : ""}">
    <div class="dl-head"><span class="dl-name">${esc(ad)}</span>${sag}</div>
    ${alt}
  </div>`;
}

async function startDownload(item) {
  const r = await motor(api("/downloads/start"), {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item, lang: LANG }),
  });
  const j = await okuJson(r);
  if (j.error) { setMsg(j.error, "error"); return; }
  loadDownloads();
}

async function cancelDownload(item) {
  await motor(api("/downloads/cancel"), {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item, lang: LANG }),
  });
  loadDownloads();
}

// ---------------- CSV ----------------
// Ayirici ve ondalik isareti kullanicinin Excel'ine gore (csv.js): Turkce Excel ';' ve
// ondalik virgul bekler; "30.3" yazilinca tarihe donuyordu (2026-10-31 hata taramasi).
const CSV = csvBicimi(sistemOndaligi());

function downloadCsv(rows, name) {
  const blob = new Blob(["﻿" + rows.join("\n")], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name + ".csv";
  a.click();
}

const bolgeCsv = (x) => {
  const r = x.gene_region;
  return r ? `${bolgeEtiket(r).replace(/\u00a0/g, " ")} (${r.gene || "?"} ${r.acc || "?"})` : "";
};

const H = (...keys) => keys.map((k) => t("csv." + k));

function exportSeqCsv(j) {
  const isPair = j.mode === "sequence_pair";
  const head = [...H("rank", "dir", "seq", "len", "tm", "gc"),
    ...(isPair ? H("region") : []), ...H("posStart", "posEnd", "hairpin", "self",
      "self3", "amplicon", "dimer", "dimer3", "self3max", "dimerScore", "penalty"),
    // Mesafe bilinmiyorsa amplikon sayisi duz sayi kalir (Excel sayisal okusun); not ayri sutunda
    ...(isPair ? H("ampNote") : [])];
  const belirsiz = isPair && !!(j.input && j.input.free_product_size);
  const rows = [CSV.satir(head)];
  for (const p of j.pairs) {
    for (const [dirKey, x] of [["dir.forward", p.forward], ["dir.reverse", p.reverse]]) {
      rows.push(CSV.satir([p.rank, t(dirKey), x.sequence, x.length, x.tm, x.gc,
        ...(isPair ? [t(x.region === "F" ? "seq.region1" : "seq.region2")] : []),
        x.seq_start, x.seq_end, x.hairpin_tm, x.self_dimer_tm, x.self_dimer_3p_tm,
        p.product_size, p.hetero_dimer_tm, p.hetero_dimer_3p_tm, p.self3p_max,
        p.dimer_score, p.pair_penalty,
        ...(isPair ? [belirsiz ? t("csv.ampAssume") : ""] : [])]));
    }
  }
  downloadCsv(rows, isPair ? "AllPrime_two_sequences" : "AllPrime_sequence");
}

// CSV'de bant boyu birimsiz ve binlik ayiricisiz: Excel sayi olarak okusun ("612 bp",
// "12.612 bp" metin kaliyordu). Belirsizlik payi varsa "600-620" (metin).
const bpCsv = (a, b) => (a === b ? a : `${a}-${b}`);

// Kromozom sutunu her satirda "chr" onekli metin: "17" ile "X" ayni sutunda karisik tur olmasin.
const kromCsv = (c) => `chr${String(c == null ? "" : c).replace(/^chr/i, "")}`;

function exportBpCsv(j) {
  const i = j.input;
  const head = H("rank", "dir", "seq", "len", "tm", "gc", "gStart", "gEnd", "geneRegion",
    "hairpin", "self", "self3", "snpCount", "bpMain", "bpSecond", "bpControl",
    "assembly", "chrom", "bpSecondStatus");
  const rows = [CSV.satir(head)];
  for (const p of j.pairs) {
    const b = p.bp;
    // Delesyonda normal alel bandinin sinir durumu (kartta "sinirinizin cok ustunde")
    const ikinciDurum = i.type === "del" && b.wt_status ? t("bp.wt." + b.wt_status) : "";
    const [ana, ikinci] = i.type === "del" ? [bpCsv(b.mut_min, b.mut_max), b.wt]
      : i.approach === "tandem_junction" ? [bpCsv(b.junction_min, b.junction_max), ""]
      : [b.wt, bpCsv(b.dup_min, b.dup_max)];
    const k = p.control;
    const v = genYonunde(p);        // CSV'deki F/R kartla ayni (eksi iplikte genin yonunde)
    const satirlar = [["dir.forward", v.forward], ["dir.reverse", v.reverse]];
    if (k) satirlar.push(["bp.dir.control", k]);
    for (const [dirKey, x] of satirlar) {
      rows.push(CSV.satir([p.rank, t(dirKey), x.sequence, x.length, x.tm, x.gc, x.genomic_start,
        x.genomic_end, bolgeCsv(x), x.hairpin_tm, x.self_dimer_tm, x.self_dimer_3p_tm,
        (x.snps || []).length, ana, ikinci, k ? k.band : "",
        i.assembly, kromCsv(i.chrom), ikinciDurum]));
    }
  }
  downloadCsv(rows, `AllPrime_${i.assembly}_chr${i.chrom}_${i.start}-${i.end}_${i.type}`);
}

function exportCsv() {
  if (!lastResult || !lastResult.pairs.length) return;
  const j = lastResult;
  const seqMode = isSeqMode(j);
  if (j.mode === "breakpoint") return exportBpCsv(j);
  const cdna = !!j.mode && !seqMode;

  if (seqMode) return exportSeqCsv(j);

  const head = cdna
    ? [...H("rank", "dir", "seq", "len", "tm", "gc", "exon", "cdnaStart", "cdnaEnd",
            "gStart", "gEnd", "onJunction", "hairpin", "self", "self3",
            "snpCount", "snpDetail", "cdnaProduct", "gdnaProduct", "junctions"),
       ...(j.mode === "exon_skipping" ? H("normal", "skipped", "diff", "skipExons", "bands") : []),
       ...H("dimer", "dimer3", "self3max", "dimerScore", "penalty")]
    : [...H("rank", "dir", "seq", "len", "tm", "gc", "gStart", "gEnd", "geneRegion",
            "hairpin", "self", "self3", "snpCount", "snpDetail", "amplicon", "ampStart", "ampEnd",
            "dimer", "dimer3", "self3max", "dimerScore", "penalty")];
  head.push(...H("assembly", "chrom"));   // yeni sutunlar sona: eski sutun sirasi bozulmaz
  // RNA'da derleme yanittaki gercek derleme (her zaman GRCh38), kromozom transkriptinki
  const derlemeCsv = j.input.assembly || ASSEMBLY;
  const kromHucre = kromCsv(cdna ? j.transcript.chrom : j.input.chrom);

  // SNP detayinda ' | ' kullaniliyor: ayirici ',' olsa da alan tirnaklanir (csv.js)
  const snpText = (x) => (x.snps || []).map((h) =>
    `${h.rsid}(MAF ${mafYaz(h.maf)}, 3' -${h.distance_from_3p})`).join(" | ");

  const rows = [CSV.satir(head)];
  for (const p of j.pairs) {
    const v = genYonunde(p);        // CSV'deki F/R kartla ayni (eksi iplikte genin yonunde)
    for (const [dirKey, x] of [["dir.forward", v.forward], ["dir.reverse", v.reverse]]) {
      const common = [p.hetero_dimer_tm, p.hetero_dimer_3p_tm, p.self3p_max,
        p.dimer_score, p.pair_penalty];
      rows.push(CSV.satir([...(cdna
        ? [p.rank, t(dirKey), x.sequence, x.length, x.tm, x.gc, x.exons.join("/"),
           x.cdna_start, x.cdna_end,
           // eksi iplikli gende primerin 5' ucu genomda buyuk koordinattadir; CSV'de
           // DNA moduyla ayni duzen (kucukten buyuge), eskiden 7676046 -> 7676027 yaziliyordu
           Math.min(x.genomic_start, x.genomic_end), Math.max(x.genomic_start, x.genomic_end),
           t(x.spans_junction ? "csv.yes" : "csv.no"), x.hairpin_tm, x.self_dimer_tm,
           x.self_dimer_3p_tm, (x.snps || []).length, snpText(x),
           p.product_size, sinirdaPrimer(p) ? "" : p.gdna_product_size, p.junctions_in_amplicon,
           ...(j.mode === "exon_skipping"
             ? [p.product_size_normal, p.product_size_skipped, p.band_difference,
                j.input.exons || j.input.exon, bantMetni(p)] : []),
           ...common]
        : [p.rank, t(dirKey), x.sequence, x.length, x.tm, x.gc,
           x.genomic_start, x.genomic_end, bolgeCsv(x), x.hairpin_tm, x.self_dimer_tm,
           x.self_dimer_3p_tm, (x.snps || []).length, snpText(x),
           p.product_size, p.amplicon_genomic_start,
           p.amplicon_genomic_end, ...common]),
        derlemeCsv, kromHucre]));
    }
  }

  const name = cdna
    ? `AllPrime_${derlemeCsv}_${j.transcript.acc}_${j.mode === "exon_skipping"
        ? "exon" + (j.input.exons || j.input.exon) : j.input.c_label.replace(/[^\w.*-]/g, "")}`
    : `AllPrime_${j.input.assembly}_${j.input.chrom}_${j.input.position}`;

  downloadCsv(rows, name);
}

init();
