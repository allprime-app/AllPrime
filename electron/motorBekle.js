// AllPrime - Primer Tasarim Araci
// Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
//
// GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
// (GPL-2.0-or-later); tam metin LICENSE dosyasinda.
//
// Motorun acilisini bekler. Electron'a bagli degildir (node ile sinanir: test_smoke.py).
//
// Motor acilirken OLURSE beklemeyi HEMEN keser. Onceden yalnizca sure dolunca vazgeciliyordu:
// motor ilk saniyede kapansa bile 180 saniye boyunca ekrana hicbir sey gelmiyordu (olcum
// 2026-11-22: hata kutusu 187-202. saniyede). Kapanan motor birkac kez yeniden baslatilir;
// dosyalara o an erisilememesi gibi gecici bir durum ikinci denemede gecmis olabilir.
"use strict";

// istek(cb): motora tek bir saglik istegi; cevap geldiyse cb(true), gelmediyse cb(false).
// durum(): "" motor sureci yasiyor; "kapandi" surec bitti; "baslatilamadi" surec hic acilamadi.
function bekle({ istek, durum, toplamMs, aralikMs = 500, gunluk = () => {} }) {
  return new Promise((resolve, reject) => {
    const t0 = Date.now();
    let sayac = 0;
    const hata = (ileti, neden) => Object.assign(new Error(ileti), { neden, gecenMs: Date.now() - t0 });
    const tur = () => {
      istek((cevap) => {
        if (cevap) return resolve(Date.now() - t0);
        const d = durum();
        if (d) return reject(hata("Motor " + d, d));
        if (Date.now() - t0 >= toplamMs) return reject(hata("Motor zaman asimi", "zaman"));
        if (++sayac % 20 === 0) gunluk(Date.now() - t0);
        setTimeout(tur, aralikMs);
      });
    };
    tur();
  });
}

// Motoru baslatir ve acilisini bekler; motor acilirken KAPANIRSA en cok `enCok` kez dener.
// Zaman asimi (motor yasiyor ama yavas) ve "baslatilamadi" (dosya yok, izin yok) yeniden
// denenmez: ilki icin beklemek, ikincisi icin kullanicinin bir sey yapmasi gerekir.
// Sonuc: { deneme, gecenMs }. Hata: Error + { neden, deneme, gecenMs }.
async function baslatVeBekle({ baslat, istek, durum, toplamMs, aralikMs = 500, enCok = 3,
                               araMs = 1500, gunluk = () => {} }) {
  for (let deneme = 1; ; deneme++) {
    baslat(deneme);
    try {
      const gecenMs = await bekle({ istek, durum, toplamMs, aralikMs, gunluk });
      return { deneme, gecenMs };
    } catch (e) {
      e.deneme = deneme;
      if (e.neden !== "kapandi" || deneme >= enCok) throw e;
      await new Promise((r) => setTimeout(r, araMs));
    }
  }
}

module.exports = { bekle, baslatVeBekle };
