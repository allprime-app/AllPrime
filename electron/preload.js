// AllPrime - Primer Tasarim Araci
// Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
//
// GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
// (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
// verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("allprime", {
  pickFasta: () => ipcRenderer.invoke("pick-fasta"),
  getPort: () => ipcRenderer.invoke("get-port"),
  // Motor anahtari: her istekte X-AllPrime-Token basligiyla gonderilir
  getToken: () => ipcRenderer.invoke("get-token"),
  // Acilis bilgilendirme ekrani + dil
  getAppInfo: () => ipcRenderer.invoke("get-app-info"),
  getTerms: (lang) => ipcRenderer.invoke("get-terms", lang),
  ackNotice: (lang) => ipcRenderer.invoke("notice-ack", lang),
  setLang: (lang) => ipcRenderer.invoke("set-lang", lang),
  // Laboratuvarin cogaltabildigi en uzun urun (bp) - kalici ayar
  setPcrMax: (bp) => ipcRenderer.invoke("set-pcr-max", bp),
  // Ayarlar ekrani: tema, arayuz boyutu, acilistaki genom, laboratuvar varsayilanlari
  setTheme: (tema) => ipcRenderer.invoke("set-theme", tema),
  setZoom: (boyut) => ipcRenderer.invoke("set-zoom", boyut),
  // Boyut klavyeyle (Ctrl + / - / 0) degisince Ayarlar'daki secim de guncellenir
  onZoomChanged: (cb) => ipcRenderer.on("zoom-changed", (_e, boyut) => cb(boyut)),
  setDefaultAssembly: (asm) => ipcRenderer.invoke("set-default-assembly", asm),
  setLabDefaults: (degerler) => ipcRenderer.invoke("set-lab-defaults", degerler),
  // Favoriler: yalniz bu bilgisayarda (userData\favoriler.json); dogrulama main tarafinda
  favList: () => ipcRenderer.invoke("fav-list"),
  favAdd: (kayit) => ipcRenderer.invoke("fav-add", kayit),
  favRemove: (id) => ipcRenderer.invoke("fav-remove", id),
  favNote: (id, not) => ipcRenderer.invoke("fav-note", id, not),
});
