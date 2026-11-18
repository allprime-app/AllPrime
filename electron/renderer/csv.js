// AllPrime - Primer Tasarim Araci
// Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
//
// GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
// (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
// verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
// AllPrime - CSV bicimi (saf fonksiyonlar; DOM'a dokunmaz, node ile de sinanir)
//
// Ayirici ';' iken sayilar "30.3" yaziliyordu; Turkce Excel (ondalik ',', tarih
// 'g.AA.yyyy') bunlari TARIHE ("30.Mar", "3.Ağu") ya da metne ceviriyordu: TP53
// CSV'sinde 20 satirda 16 hucre tarih oldu (2026-10-31 hata taramasi). Bicim artik
// sistemin ondalik isaretine gore secilir: ',' ise ';' ayirici + ondalik virgul
// (Turkce Excel'in varsayilani), '.' ise ',' ayirici + ondalik nokta. Ayiriciyi,
// tirnagi ya da satir sonunu iceren alanlar tirnak icine alinir (RFC 4180).

function csvBicimi(ondalik) {
  const ayirici = ondalik === "," ? ";" : ",";
  const ONDALIKLI = /^-?\d+\.\d+$/;
  function alan(v) {
    let s;
    if (typeof v === "number") s = Number.isFinite(v) ? String(v) : "";
    else s = v == null ? "" : String(v);
    if (ondalik === "," && ONDALIKLI.test(s)) s = s.replace(".", ",");
    return (s.includes(ayirici) || /["\r\n]/.test(s)) ? `"${s.replace(/"/g, '""')}"` : s;
  }
  return { ayirici, ondalik, alan, satir: (alanlar) => alanlar.map(alan).join(ayirici) };
}

// Excel CSV'yi Windows'un bolge ayariyla okur; tarayici ayni ayari Intl'den verir
// (arayuz dili degil: Ingilizce arayuzlu bir Turk Excel'i de ';' bekler).
function sistemOndaligi() {
  try {
    const p = new Intl.NumberFormat().formatToParts(1.5).find((x) => x.type === "decimal");
    return p ? p.value : ".";
  } catch (e) {
    return ".";
  }
}

if (typeof module !== "undefined") module.exports = { csvBicimi, sistemOndaligi };
