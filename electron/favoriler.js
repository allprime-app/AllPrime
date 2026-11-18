// AllPrime - Primer Tasarim Araci
// Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
//
// GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
// (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
// verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
//
// Favoriler (kullanici istegi 2026-11-14: "Favorilere ekle gibi bi sey", "kullanacagim primeri
// kaydedebilecegim bir alan"). Kullanicinin sectigi ciftlerin kunyesi YALNIZCA bu bilgisayarda,
// kullanici klasorundeki tek dosyada (userData\favoriler.json) durur; disari hicbir sey gitmez.
// Islevler saf: dosya yolu disaridan verilir (main.js; testte gecici klasor). Kayit arayuzden
// gelir ama BURADA dogrulanir: bilinmeyen alan atilir, metinler kisaltilir, dizi yalniz harf.
// Bozuk dosyanin USTUNE YAZILMAZ: yeni kayit gelince once yanina yedek adiyla tasinir.
"use strict";
const fs = require("fs");
const path = require("path");

const BICIM = 1;                  // dosya bicimi
const EN_COK = 2000;              // kayit siniri: asilirsa yeni kayit reddedilir, eskiler silinmez
const NOT_SINIRI = 500;           // not (karakter)
const TURLER = ["dna", "cdna", "atlama", "dizi", "dizi_cift", "kirilma", "degerlendir_dna",
  "degerlendir_cdna"];
const ROLLER = ["forward", "reverse", "control"];
const KONUM_TURLERI = ["genomik", "cdna", "dizi"];
const GIRDI_ALANLARI = ["chrom", "position", "position_end", "start", "end", "type", "margin", "acc",
  "c_label", "exons", "target", "length"];
const URUN_ALANLARI = ["boy", "gdna", "normal", "atlanmis", "fark", "kirilma_min", "kirilma_max",
  "normal_alel", "birlesim_min", "birlesim_max", "dup_min", "dup_max", "kontrol", "ta"];

// Kontrol karakterleri (satir sonu dahil) bosluga; bas / son bosluk atilir; uzunluk sinirlanir.
// Kesimden sonra da kirpilir: kesim bosluga denk gelirse kayit ile diskten okunan ayni kalsin.
const metin = (v, n) => (typeof v === "string" ? v : v == null ? "" : String(v))
  .replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, n).trim();
const sayi = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
const deger = (v) => (typeof v === "number" ? sayi(v) : (metin(v, 80) || null));

function yeniKimlik() {
  return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
}

// Ayni cift ikinci kez eklenmez; kartta "Favorilerde" durumu da bu anahtarla bulunur.
// app.js'teki favAnahtar ile AYNI olmali (test_smoke denetler).
function anahtar(k) {
  return [k.tur, k.derleme || "", ...k.primerler.map((p) => p.rol + ":" + p.dizi.toUpperCase())].join("|");
}

function primerTemizle(p) {
  if (!p || typeof p !== "object" || !ROLLER.includes(p.rol)) return null;
  const dizi = typeof p.dizi === "string" ? p.dizi.trim() : "";
  if (!/^[A-Za-z]{5,200}$/.test(dizi)) return null;
  const o = { rol: p.rol, dizi, uzunluk: sayi(p.uzunluk) ?? dizi.length, tm: sayi(p.tm), gc: sayi(p.gc) };
  const k = p.konum;
  if (k && typeof k === "object" && KONUM_TURLERI.includes(k.tur) && sayi(k.bas) !== null && sayi(k.bit) !== null) {
    o.konum = { tur: k.tur, bas: k.bas, bit: k.bit };
    const ekson = metin(k.ekson, 40);
    if (ekson) o.konum.ekson = ekson;
    const bolum = metin(k.bolum, 4);
    if (bolum) o.konum.bolum = bolum;
  }
  if (p.rol === "control" && (p.es === "forward" || p.es === "reverse")) o.es = p.es;
  return o;
}

// Gecerli kayit ya da null. Primer sirasi her zaman forward, reverse, control (anahtar buna bagli).
function temizle(k) {
  if (!k || typeof k !== "object" || !TURLER.includes(k.tur)) return null;
  const roller = new Set();
  const primerler = (Array.isArray(k.primerler) ? k.primerler : []).map(primerTemizle)
    .filter((p) => p && !roller.has(p.rol) && roller.add(p.rol))
    .sort((a, b) => ROLLER.indexOf(a.rol) - ROLLER.indexOf(b.rol));
  if (!roller.has("forward")) return null;
  const girdi = {};
  for (const a of GIRDI_ALANLARI) {
    const d = k.girdi && typeof k.girdi === "object" ? deger(k.girdi[a]) : null;
    if (d !== null) girdi[a] = d;
  }
  const urun = {};
  for (const a of URUN_ALANLARI) {
    const d = k.urun && typeof k.urun === "object" ? sayi(k.urun[a]) : null;
    if (d !== null) urun[a] = d;
  }
  const tarih = typeof k.tarih === "string" && !Number.isNaN(Date.parse(k.tarih)) ? k.tarih : new Date().toISOString();
  return {
    id: typeof k.id === "string" && /^[A-Za-z0-9-]{6,40}$/.test(k.id) ? k.id : yeniKimlik(),
    tarih,
    surum: metin(k.surum, 20),
    tur: k.tur,
    derleme: k.derleme === "GRCh37" || k.derleme === "GRCh38" ? k.derleme : "",
    gen: metin(k.gen, 40),
    girdi,
    urun,
    primerler,
    not: metin(k.not, NOT_SINIRI),
  };
}

// { kayitlar, hata }: hata null | "bozuk" (gecersiz JSON / bicim) | "okunamadi" (izin vb.).
// Dosya yoksa bos liste. Bas taraftaki BOM (Not Defteri) sorun degil.
function oku(dosya) {
  let ham;
  try {
    ham = fs.readFileSync(dosya, "utf8");
  } catch (e) {
    return { kayitlar: [], hata: e.code === "ENOENT" ? null : "okunamadi" };
  }
  try {
    const v = JSON.parse(ham.replace(/^﻿/, ""));
    const liste = Array.isArray(v) ? v : (v && Array.isArray(v.kayitlar) ? v.kayitlar : null);
    if (!liste) return { kayitlar: [], hata: "bozuk" };
    return { kayitlar: liste.map(temizle).filter(Boolean), hata: null };
  } catch (e) {
    return { kayitlar: [], hata: "bozuk" };
  }
}

// Once gecici dosyaya, sonra yerine: yazim yarida kesilirse eski liste bozulmaz.
function yaz(dosya, kayitlar) {
  const gecici = dosya + ".tmp";
  try {
    fs.mkdirSync(path.dirname(dosya), { recursive: true });
    fs.writeFileSync(gecici, JSON.stringify({ bicim: BICIM, kayitlar }, null, 2), "utf8");
    fs.renameSync(gecici, dosya);
    return true;
  } catch (e) {
    try { fs.unlinkSync(gecici); } catch (e2) { /* gecici hic olusmamis olabilir */ }
    return false;
  }
}

// Bozuk dosya silinmez: ayni klasorde favoriler.bozuk-YYYYMMDD-HHMMSS.json adiyla saklanir.
function yedekle(dosya) {
  const d = new Date();
  const iki = (x) => String(x).padStart(2, "0");
  const ek = `${d.getFullYear()}${iki(d.getMonth() + 1)}${iki(d.getDate())}-${iki(d.getHours())}${iki(d.getMinutes())}${iki(d.getSeconds())}`;
  const yedek = path.join(path.dirname(dosya), `${path.basename(dosya, ".json")}.bozuk-${ek}.json`);
  try {
    fs.renameSync(dosya, yedek);
    return yedek;
  } catch (e) {
    return null;
  }
}

function liste(dosya) {
  const d = oku(dosya);
  return { ok: !d.hata, kayitlar: d.kayitlar, hata: d.hata };
}

function ekle(dosya, kayit) {
  const k = temizle(kayit);
  if (!k) return { ok: false, hata: "gecersiz" };
  const d = oku(dosya);
  let yedek = null;
  if (d.hata === "bozuk") {
    yedek = yedekle(dosya);
    if (!yedek) return { ok: false, hata: "bozuk" };
  } else if (d.hata) {
    return { ok: false, hata: d.hata };
  }
  const anah = anahtar(k);
  const onceki = d.kayitlar.find((x) => anahtar(x) === anah);
  if (onceki) return { ok: true, kayit: onceki, zatenVar: true, kayitlar: d.kayitlar, yedek };
  if (d.kayitlar.length >= EN_COK) return { ok: false, hata: "sinir", sinir: EN_COK };
  const yeni = [k, ...d.kayitlar];
  if (!yaz(dosya, yeni)) return { ok: false, hata: "yazilamadi" };
  return { ok: true, kayit: k, kayitlar: yeni, yedek };
}

function sil(dosya, id) {
  const d = oku(dosya);
  if (d.hata) return { ok: false, hata: d.hata };
  const kalan = d.kayitlar.filter((x) => x.id !== id);
  if (kalan.length === d.kayitlar.length) return { ok: true, kayitlar: d.kayitlar };
  if (!yaz(dosya, kalan)) return { ok: false, hata: "yazilamadi" };
  return { ok: true, kayitlar: kalan };
}

function notYaz(dosya, id, not) {
  const d = oku(dosya);
  if (d.hata) return { ok: false, hata: d.hata };
  const k = d.kayitlar.find((x) => x.id === id);
  if (!k) return { ok: false, hata: "yok" };
  k.not = metin(not, NOT_SINIRI);
  if (!yaz(dosya, d.kayitlar)) return { ok: false, hata: "yazilamadi" };
  return { ok: true, kayit: k, kayitlar: d.kayitlar };
}

module.exports = { liste, ekle, sil, notYaz, temizle, anahtar, oku, BICIM, EN_COK, NOT_SINIRI };
