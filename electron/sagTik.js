// AllPrime - Primer Tasarim Araci
// Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
//
// GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
// (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
// verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
//
// Sag tik (baglam) menusu. Electron'da varsayilan sag tik menusu yoktur: secili primer dizisi
// ya da sonuc metni fareyle kopyalanamiyor, kutulara fareyle yapistirilamiyordu (yalniz
// Ctrl+C / Ctrl+V calisiyordu). Bu islev yalniz menunun SABLONUNU kurar (saf islev; Electron
// gerektirmez, testte node ile cagrilir); menuyu main.js acar.
//   - yazi kutusunda: Kes, Kopyala, Yapistir, Tumunu sec (yapilamayan secenek soluk gorunur)
//   - sayfada secili metin varsa: Kopyala
//   - ikisi de degilse: bos liste, menu acilmaz
// Ogeler Electron'un hazir rolleridir (kes / kopyala / yapistir Chromium'un kendi duzenleme
// komutlari); pano icerigi bu kodda okunmaz, hicbir yere gonderilmez.
"use strict";

function sablon(p, L) {
  p = p || {};
  const ef = p.editFlags || {};
  const secili = String(p.selectionText || "").trim().length > 0;
  if (p.isEditable) {
    return [
      { role: "cut", label: L("Kes", "Cut"), enabled: !!ef.canCut },
      { role: "copy", label: L("Kopyala", "Copy"), enabled: !!ef.canCopy },
      { role: "paste", label: L("Yapıştır", "Paste"), enabled: !!ef.canPaste },
      { type: "separator" },
      { role: "selectAll", label: L("Tümünü seç", "Select all"), enabled: !!ef.canSelectAll },
    ];
  }
  if (secili) return [{ role: "copy", label: L("Kopyala", "Copy") }];
  return [];
}

module.exports = { sablon };
