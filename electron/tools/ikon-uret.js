// AllPrime - pencere/gorev cubugu ikonunu logo.svg'den uret.
// Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
//
// GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
// (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
// verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
//
// Neden Electron ile: makinede Node yok, ama Electron'un icinde hem Node hem
// Chromium var. Gizli bir pencerede SVG'yi 256x256 cizdirip yakaliyoruz;
// saydam pencere sayesinde yuvarlak koseler PNG'de de saydam kalir.
//
// Calistirma (depo kokunden):
//   electron\node_modules\electron\dist\electron.exe electron\tools\ikon-uret.js
//
// Cikti: electron/renderer/icon.png (256x256). main.js pencereye bunu verir.
// Exe'nin Explorer / Gorev Yoneticisi ikonu icin ardindan
// electron\tools\ico-uret.ps1 calistirilir (build\icon.ico); kurulu-guncelle.ps1
// onu rcedit ile exe'ye gomer (Node gerekmez).
const { app, BrowserWindow } = require("electron");
const fs = require("fs");
const path = require("path");

const renderer = path.join(__dirname, "..", "renderer");
const BOY = 256;

app.whenReady().then(async () => {
  const svg = fs.readFileSync(path.join(renderer, "logo.svg"), "utf8");
  const html = `<!doctype html><meta charset="utf-8">
    <style>html,body{margin:0;background:transparent;width:${BOY}px;height:${BOY}px;overflow:hidden}
           svg{display:block;width:${BOY}px;height:${BOY}px}</style>
    <body>${svg}</body>`;
  const win = new BrowserWindow({
    show: false, width: BOY, height: BOY, frame: false, transparent: true,
    webPreferences: { offscreen: true },
  });
  await win.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(html));
  await new Promise((r) => setTimeout(r, 400));          // cizim tamamlansin
  const img = await win.webContents.capturePage({ x: 0, y: 0, width: BOY, height: BOY });
  const hedef = path.join(renderer, "icon.png");
  fs.writeFileSync(hedef, img.toPNG());
  const { width, height } = img.getSize();
  console.log(`icon.png yazildi: ${width}x${height}, ${fs.statSync(hedef).size} bayt`);
  app.quit();
});
