// AllPrime - Primer Tasarim Araci
// Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
//
// GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
// (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
// verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
// AllPrime - F/R adlari genin okuma yonunde (saf fonksiyonlar; DOM'a dokunmaz, node
// ile de sinanir)
//
// Motor DNA ve kirilma noktasi ciftlerini genomun + ipligine gore verir: "forward"
// kucuk koordinattaki primerdir. Laboratuvar ise F/R'yi GENIN okuma yonune gore
// adlandirir (Degerlendir de boyle bekler, v0.8.8). Eksi iplikteki bir gende (TP53)
// genomik forward primer genin tersine okur: o primerle yapilan Sanger okumasi c.
// dizisinin ters tumleyeni olur (TP53 c.215C, chr17:7676154'te + iplikte G) ve
// tasarlanan cift Degerlendir'e verilince "roller yer degismis" deniyordu (2026-11-01).
// Burada yalnizca GORUNUM cevrilir: genin F'si genomik reverse primerdir, urun dizisi
// ters tumleyen olur. Pozisyonlar genomik kalir; motorun ciktisi degismez.

const TUMLEYEN = { A: "T", T: "A", G: "C", C: "G", a: "t", t: "a", g: "c", c: "g" };

function tersTumleyen(s) {
  let o = "";
  for (let i = s.length - 1; i >= 0; i--) o += TUMLEYEN[s[i]] || s[i];   // N ve digerleri ayni
  return o;
}

// Urun dizisi ters tumleyen: isaretli araliklar aynalanir, F ile R yer degistirir.
// Sinir (kirilma noktasi / ekson siniri) k. bazin ONUNDE cizilir; aynada n - k olur.
function amplikonTers(a) {
  const n = a.sequence.length;
  const ayna = (span) => (span ? [n - 1 - span[1], n - 1 - span[0]] : span);
  return Object.assign({}, a, {
    sequence: tersTumleyen(a.sequence),
    forward_span: ayna(a.reverse_span),
    reverse_span: ayna(a.forward_span),
    unknown_span: ayna(a.unknown_span),
    variant_span: ayna(a.variant_span),
    junction_offsets: (a.junction_offsets || []).map((k) => n - k),
  });
}

// Ciftin genin yonundeki gorunumu. Yalnizca urun eksi iplikteki bir genle ortusuyorsa
// cevrilir (gene_strand "-"); "+", zit yonlu genler ("?") ve gen yoksa cift aynen doner.
function genYonunde(p) {
  if (!p || p.gene_strand !== "-") return p;
  return Object.assign({}, p, {
    forward: p.reverse,
    reverse: p.forward,
    amplicon: p.amplicon ? amplikonTers(p.amplicon) : p.amplicon,
  });
}

// Degerlendir'in urun dizisi (2026-11-03). Motor urunu genomun + ipliginde (cDNA'da
// transkriptin yonunde) verir; sol uctaki primer sol, sagdaki sag ("F" ya da "R").
// Kullanicinin R'si solda, F'si sagdaysa (R+F: eksi iplikli genin kartindan gelen cift ya
// da cDNA'da roller yer degismis) dizi ters cevrilir: kartlardaki gibi F'den baslar, F ile
// yapilan Sanger okumasiyla ayni yonde olur. F+F / R+R tek primerin iki ucudur, cevrilmez.
// Lejant uclardaki primerin kendi adini alir (once her zaman "Forward / Reverse" idi).
function degerlendirmeUrunu(a, sol, sag) {
  const ters = sol === "R" && sag === "F";
  return {
    amplicon: ters ? amplikonTers(a) : a,
    sol: ters ? "F" : sol,
    sag: ters ? "R" : sag,
    ters,
  };
}

if (typeof module !== "undefined") module.exports = { tersTumleyen, amplikonTers, genYonunde, degerlendirmeUrunu };
