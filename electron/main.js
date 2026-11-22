// AllPrime - Primer Tasarim Araci
// Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
//
// GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
// (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
// verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
const { app, BrowserWindow, ipcMain, dialog, shell, nativeTheme, Menu } = require("electron");
const { spawn, spawnSync } = require("child_process");
const path = require("path");
const { pathToFileURL } = require("url");
const http = require("http");
const net = require("net");
const fs = require("fs");
const crypto = require("crypto");
// Favoriler: secilen ciftlerin kunyesi, yalniz bu bilgisayarda (userData\favoriler.json)
const favoriler = require("./favoriler");
// Sag tik menusu sablonu (Kes / Kopyala / Yapistir / Tumunu sec)
const sagTik = require("./sagTik");

// Motor anahtari: her acilista yeni. Motora ALLPRIME_TOKEN ile, arayuze preload ile
// verilir; motor anahtarsiz istegi reddeder. Boylece tarayicida acik bir site
// yerel portu bulsa bile motoru kullanamaz (bkz. server.py ERISIM DENETIMI).
const TOKEN = crypto.randomBytes(32).toString("hex");
const ANAHTAR_BASLIGI = "X-AllPrime-Token";

// Sabit port KULLANMIYORUZ. Uygulama zorla kapatilirsa (Gorev Yoneticisi, cokme)
// Electron oluyor ama baslattigi Python motoru oksuz kalip portu tutmaya devam
// ediyordu; bir sonraki acilista yeni motor portu alamiyor, arayuz ise porta
// bakip "motor hazir" sanarak ESKI motorla konusuyordu. Sonuc: ayarlar guncel
// olmasina ragmen "genom tanitilmamis" gibi yanlis durumlar.
let PORT = 0;

function bosPortBul() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.unref();
    s.on("error", reject);
    s.listen(0, "127.0.0.1", () => {
      const p = s.address().port;
      s.close(() => resolve(p));
    });
  });
}
let pyProc = null;
let mainWindow = null;

// Tek kopya kilidi (G-01): ayni kullanici profiliyle ikinci kez acilan AllPrime yeni pencere
// ve motor baslatmaz, kendini kapatir; aciktaki pencere one gelir (kucultulmusse geri acilir).
// Kilit userData klasorune baglidir: baska profil (olcum ve test altyapisi) etkilenmez.
const TEK_KOPYA = app.requestSingleInstanceLock();
if (!TEK_KOPYA) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      if (!mainWindow.isVisible()) mainWindow.show();
      mainWindow.focus();
    }
  });
}

// Bilgilendirme ve sorumluluk bildiriminin metin surumu. terms.html / terms_en.html
// degistiginde BU DEGERI ARTIR - yoksa bildirim daha once gormus kullaniciya yeniden
// gosterilmez. Ekran onay istemez; yalnizca "gosterildi" kaydi tutulur.
// 1.1 (2026-10-07): 6. madde kisitlama degil sorumluluk bildirimi oldu (GPL ek
// kisitlamaya izin vermez); 4. maddeye THIRD-PARTY-NOTICES.txt eklendi.
// 1.2 (2026-10-10): uygulamanin adi AllPrime oldu.
// 1.3 (2026-10-31): lisans GPL-2.0-or-later; Apache-2.0 bilesenler (requests, OpenSSL)
// yuzunden kurum disina GPL v3 ile dagitim (4. madde ve 3. onay kutusu).
// 1.4 (2026-11-01): 4. maddedeki lisans paragrafi sadelesti (kullanici: "su ile
// lisanslidir desek yeter"): yalnizca lisans ve metinlerinin yeri; GPL v3 / dagitim
// ayrintisi GELISTIRME.md, KURULUM.txt ve THIRD-PARTY-NOTICES.txt'de. 3. onay kutusu da buna gore.
// 2.0 (2026-11-10): onay ekrani bilgilendirme ekrani oldu (onay kutulari, kaydirma sarti
// ve "Reddet" kalkti; metin uyari diline cevrildi). Kayit yalniz noticeVersion + noticeShownAt.
// 2.1 (2026-11-11): bolum 5 olguya uydu: transkript tablosu da yoksa gen sembolu de Ensembl'e gider.
const NOTICE_VERSION = "2.1";
// Onay donemine ait eski alanlar: bildirim kaydi yazilirken dosyadan silinir.
const ESKI_ONAY_ALANLARI = ["accepted", "acceptedAt", "user", "host", "termsVersion", "appVersion"];

// --- Onay ve dil tercihi (yalnizca bu bilgisayarda saklanir) ---
function settingsPath() {
  return path.join(app.getPath("userData"), "consent.json");
}

// Dosya metnini ayarlar nesnesine cevirir. Bas tarafta BOM (Not Defteri / PowerShell'in
// yazdigi UTF-8 imzasi) olsa da okunur; gecersiz, yarim ya da nesne olmayan icerik {} sayilir.
function parseSettings(metin) {
  try {
    const t = String(metin).replace(/^﻿/, "");
    const s = JSON.parse(t);
    return s && typeof s === "object" && !Array.isArray(s) ? s : {};
  } catch (e) {
    return {};
  }
}

function readSettings() {
  try {
    return parseSettings(fs.readFileSync(settingsPath(), "utf8"));
  } catch (e) {
    return {};
  }
}

function writeSettings(obj) {
  let gecici = null;
  try {
    fs.mkdirSync(path.dirname(settingsPath()), { recursive: true });
    // Once gecici dosyaya, sonra yerine tasi: yazim yarida kesilirse eski kayit bozulmaz.
    gecici = settingsPath() + ".tmp";
    fs.writeFileSync(gecici, JSON.stringify(obj, null, 2), "utf8");
    fs.renameSync(gecici, settingsPath());
    return true;
  } catch (e) {
    console.log("[onay] kaydedilemedi:", e.message);
    // Yazim ya da yer degistirme (salt okunur consent.json) basarisizsa gecici dosya artik
    // olarak kalmasin (D3-03).
    if (gecici) {
      try { fs.unlinkSync(gecici); } catch (e2) { console.log("[onay] gecici dosya silinemedi:", e2.message); }
    }
    return false;
  }
}

// Bildirim bu surumde zaten gosterildi mi? (ilk acilista ve metin surumu degisince false)
function noticeSeen(s = readSettings()) {
  return s.noticeVersion === NOTICE_VERSION && typeof s.noticeShownAt === "string" && s.noticeShownAt !== "";
}

// "Anladim, devam et" sonrasi yazilacak kayit: yalniz bildirim surumu + gosterilme tarihi
// (Windows kullanici adi ve bilgisayar adi tutulmaz); eski onay alanlari silinir, tercihler korunur.
function noticeKaydi(s, lang, simdi) {
  const y = { ...s };
  for (const a of ESKI_ONAY_ALANLARI) delete y[a];
  y.noticeVersion = NOTICE_VERSION;
  y.noticeShownAt = simdi;
  y.lang = lang === "en" ? "en" : "tr";
  return y;
}

// --- Ayarlar ekrani tercihleri (2026-11-01) ---
// Onay kaydiyla ayni dosyada, yalnizca bu bilgisayarda. Gecersiz deger yok sayilir,
// kayitli deger yoksa varsayilan kullanilir (koyu tema, %100, GRCh38, fabrika degerleri).
const TEMALAR = ["dark", "light", "system"];
const BOYUTLAR = [0.9, 1, 1.1, 1.25, 1.5];
const GENOMLAR = ["GRCh38", "GRCh37"];
// Laboratuvar varsayilani olarak saklanabilen gelismis parametreler: app.js PARAM_IDS
// ile ayni, pcr_max haric (o kendi anahtariyla saklaniyor; test_smoke denetler).
const LAB_PARAMETRELERI = [
  "product_min_gc", "product_max_gc",
  "product_size_min", "product_size_max", "min_dist_from_variant",
  "primer_min_size", "primer_opt_size", "primer_max_size",
  "primer_min_tm", "primer_max_tm", "primer_max_tm_diff",
  "primer_min_gc", "primer_max_gc", "primer_gc_clamp", "primer_max_end_gc", "primer_max_poly_x",
  "salt_monovalent", "salt_divalent", "dntp_conc", "dna_conc", "dmso_conc", "num_return",
];

function kayitliTema(s = readSettings()) {
  return TEMALAR.includes(s.theme) ? s.theme : "dark";
}

function kayitliBoyut(s = readSettings()) {
  return BOYUTLAR.includes(s.zoom) ? s.zoom : 1;
}

// Arayuz boyutunu kaydet, uygula ve acik sayfaya bildir (Ayarlar secili dugmeyi gunceller).
// Ayarlar'daki secim de klavye kisayolu da buradan gecer: ikisi hep ayni degeri gosterir.
function boyutUygula(v) {
  const s = readSettings();
  s.zoom = v;
  writeSettings(s);
  if (mainWindow) {
    mainWindow.webContents.setZoomFactor(v);
    mainWindow.webContents.send("zoom-changed", v);
  }
  return v;
}

// Ctrl + / Ctrl - / Ctrl 0 -> Ayarlar'daki bir sonraki / onceki boyut, %100; kisayol degilse
// null. input.key klavye duzenine gore gelir: TR-Q'da "+" Shift+4 ya da sayi tus takimi,
// ABD duzeninde "=" tusu. AltGr (Ctrl+Alt) ve Windows tusu (Buyutec) karismaz.
function kisayolBoyutu(input) {
  if (input.type !== "keyDown" || !input.control || input.alt || input.meta) return null;
  const i = BOYUTLAR.indexOf(kayitliBoyut());
  if (input.key === "+" || input.key === "=") return BOYUTLAR[Math.min(i + 1, BOYUTLAR.length - 1)];
  if (input.key === "-") return BOYUTLAR[Math.max(i - 1, 0)];
  if (input.key === "0") return 1;
  return null;
}

function labTemizle(o) {
  const temiz = {};
  for (const k of LAB_PARAMETRELERI) {
    if (!o || o[k] === undefined || o[k] === null || o[k] === "") continue;
    const v = Number(o[k]);
    if (Number.isFinite(v)) temiz[k] = v;
  }
  return temiz;
}

// Pencerenin sayfa cizilmeden onceki zemini temaya uysun (acik temada koyu parlama olmasin)
function pencereZemini() {
  return nativeTheme.shouldUseDarkColors ? "#0f1115" : "#f3f5f8";
}

// Ana surecin kullaniciya gosterdigi metinler (hata kutusu, dosya secme) icin
// dil: arayuzle ayni kayitli tercih.
function L(tr, en) {
  return readSettings().lang === "en" ? en : tr;
}

// --- Python yorumlayicisini bul (gelistirme: venv; paket: sidecar exe) ---
function resolvePython() {
  const isPackaged = app.isPackaged;
  let backendDir = isPackaged
    ? path.join(process.resourcesPath, "backend")
    : path.join(__dirname, "..", "backend");

  // KAYNAKTAN CALISTIRMA KOPRUSU
  // Uygulama klasorunde "backend.txt" varsa, icindeki yol backend olarak
  // kullanilir ve oradaki .venv ile server.py dogrudan calistirilir.
  // Neden: derlenmis sidecar bazi makinelerde calistirilamiyor (Windows
  // Smart App Control imzasiz yeni exe'leri engelliyor). Python.exe imzali
  // oldugu icin bu yol calisir. Dosyayi silmek eski davranisa dondurur.
  try {
    const isaret = path.join(path.dirname(app.getPath("exe")), "backend.txt");
    if (fs.existsSync(isaret)) {
      const ozel = fs.readFileSync(isaret, "utf8").trim();
      if (ozel && fs.existsSync(path.join(ozel, "server.py"))) {
        console.log("[AllPrime] backend.txt bulundu, kaynaktan calistiriliyor:", ozel);
        backendDir = ozel;
        const venv = path.join(ozel, ".venv", "Scripts", "python.exe");
        return {
          cmd: fs.existsSync(venv) ? venv : "python",
          args: [path.join(ozel, "server.py"), "--port", String(PORT)],
          cwd: ozel,
        };
      }
      console.log("[AllPrime] backend.txt gecersiz, yok sayildi:", ozel);
    }
  } catch (e) {
    console.log("[AllPrime] backend.txt okunamadi:", e.message);
  }

  // Paketlenmis sidecar exe (PyInstaller) varsa onu kullan
  const sidecarExe = path.join(backendDir, "allprime-server.exe");
  if (fs.existsSync(sidecarExe)) {
    return { cmd: sidecarExe, args: ["--port", String(PORT)], cwd: backendDir };
  }
  // Gelistirme: venv python + server.py
  const venvPy = path.join(backendDir, ".venv", "Scripts", "python.exe");
  const py = fs.existsSync(venvPy) ? venvPy : "python";
  return {
    cmd: py,
    args: [path.join(backendDir, "server.py"), "--port", String(PORT)],
    cwd: backendDir,
  };
}

// --- Motor baslatma tanisi ---------------------------------------------
// "Hesaplama motoru baslatilamadi" tek basina hicbir sey anlatmiyordu:
// spawn hatasi HIC yakalanmiyordu (Windows dosyayi engellerse EPERM firlatir),
// motorun kendi hata ciktisi da yalnizca gorunmeyen konsola gidiyordu.
// Baska bir bilgisayarda bu, kullaniciyi tamamen karanlikta birakiyor.
let BACKEND_KOMUT = "";
let BACKEND_HATA = null;
let BACKEND_KOD = null;
const BACKEND_CIKTI = [];

function ciktiEkle(etiket, veri) {
  String(veri).split(/\r?\n/).forEach((s) => {
    if (s.trim()) BACKEND_CIKTI.push(etiket + s.trim());
  });
  while (BACKEND_CIKTI.length > 40) BACKEND_CIKTI.shift();
}

function startBackend() {
  const { cmd, args, cwd } = resolvePython();
  // Motora UYGULAMA KLASORUNU soyle. Kaynaktan calisirken motor kendini
  // backend\.venv icinde gorup yukari dogru arayarak "AllPrime\genomes"
  // klasorunu bulamiyordu; tek dayanagi kalici ayar dosyasi kaliyordu ve o
  // silinince genomlar "yok" gorunuyordu. ALLPRIME_APP_ROOT ile bu belirsizlik biter.
  const appRoot = path.dirname(app.getPath("exe"));
  const env = Object.assign({}, process.env, { ALLPRIME_APP_ROOT: appRoot, ALLPRIME_TOKEN: TOKEN });
  BACKEND_KOMUT = [cmd].concat(args).join(" ");
  console.log("[AllPrime] uygulama klasoru (ALLPRIME_APP_ROOT):", appRoot);
  console.log("[AllPrime] motor komutu:", BACKEND_KOMUT);

  // Kopyalama eksik kalmis olabilir - once dosyalar yerinde mi bak
  if (cmd.toLowerCase().endsWith(".exe") && !fs.existsSync(cmd)) {
    BACKEND_HATA = { code: "YOK", message: L("Motor dosyası bulunamadı: ",
                                             "Engine file not found: ") + cmd };
    return;
  }
  const yanIc = path.join(path.dirname(cmd), "_internal");
  if (cmd.toLowerCase().endsWith("allprime-server.exe") && !fs.existsSync(yanIc)) {
    BACKEND_HATA = {
      code: "EKSIK",
      message: L("Motorun yanındaki '_internal' klasörü yok. Kopyalama yarım "
                 + "kalmış olabilir (klasörün TAMAMI kopyalanmalı).",
                 "The '_internal' folder next to the engine is missing. The copy may "
                 + "be incomplete (the WHOLE folder must be copied)."),
    };
    return;
  }

  try {
    pyProc = spawn(cmd, args, { cwd, env, windowsHide: true });
  } catch (e) {
    BACKEND_HATA = e;
    return;
  }
  // BU DINLEYICI SART: yoksa spawn hatasi yakalanmayan bir olay olarak kaybolur
  pyProc.on("error", (e) => {
    BACKEND_HATA = e;
    console.log("[py] baslatilamadi:", e.code, e.message);
  });
  pyProc.stdout.on("data", (d) => { ciktiEkle("", d); console.log("[py]", String(d)); });
  pyProc.stderr.on("data", (d) => { ciktiEkle("! ", d); console.log("[py:err]", String(d)); });
  pyProc.on("close", (code) => {
    BACKEND_KOD = code;
    console.log("[py] kapandi, kod:", code);
  });
}

function baslatmaTanisi() {
  const s = [];
  s.push(L("Hesaplama motoru başlatılamadı.", "The calculation engine could not be started."));
  s.push("");
  s.push(L("Çalıştırılmaya çalışılan:", "Attempted command:"));
  s.push("  " + BACKEND_KOMUT);

  if (BACKEND_HATA) {
    s.push("");
    s.push(L("Hata: ", "Error: ") + (BACKEND_HATA.code || "") + " " + (BACKEND_HATA.message || ""));
    if (BACKEND_HATA.code === "EPERM" || BACKEND_HATA.code === "EACCES") {
      s.push("");
      s.push(...L([
        "Bu hata, dosyanın ÇALIŞTIRILMASINA İZİN VERİLMEDİĞİ anlamına gelir.",
        "Genellikle Windows Smart App Control / SmartScreen ya da antivirus",
        "imzasız programı engeller. Deneyin:",
        "  1. Klasördeki allprime-server.exe dosyasına sağ tık > Özellikler,",
        "     altta 'Engellemeyi kaldır' kutusu varsa işaretleyip Tamam.",
        "  2. Windows Güvenliği > Koruma geçmişi'nde engellenen öğeye izin verin.",
      ], [
        "This error means the file was NOT ALLOWED TO RUN.",
        "Usually Windows Smart App Control / SmartScreen or an antivirus",
        "blocks unsigned programs. Try:",
        "  1. Right-click allprime-server.exe in the folder > Properties;",
        "     if there is an 'Unblock' box at the bottom, tick it and press OK.",
        "  2. Allow the blocked item under Windows Security > Protection history.",
      ]));
    } else if (BACKEND_HATA.code === "ENOENT" || BACKEND_HATA.code === "YOK"
               || BACKEND_HATA.code === "EKSIK") {
      s.push("");
      s.push(...L([
        "Dosyalar eksik görünüyor. Klasörün TAMAMI kopyalandığından ve",
        "çok derin bir yola açılmadığından emin olun (Windows 260 karakter).",
      ], [
        "Files seem to be missing. Make sure the WHOLE folder was copied and",
        "that it is not unpacked into a very deep path (Windows 260 characters).",
      ]));
    }
  }
  if (BACKEND_KOD !== null && BACKEND_KOD !== 0) {
    s.push("");
    s.push(L("Motor beklenmedik şekilde kapandı. Çıkış kodu: ",
             "The engine exited unexpectedly. Exit code: ") + BACKEND_KOD);
  }
  if (BACKEND_CIKTI.length) {
    s.push("");
    s.push(L("Motorun son çıktısı:", "Last engine output:"));
    BACKEND_CIKTI.slice(-15).forEach((x) => s.push("  " + x));
  }
  if (!BACKEND_HATA && BACKEND_KOD === null && !BACKEND_CIKTI.length) {
    // Surec YASIYOR ama tek satir bile yazmadi. Motor acilirken hemen bir
    // satir basar; ona bile gelememisse buyuk ihtimalle HALA YUKLENIYOR.
    // Yavas disk (ozellikle USB) ve her DLL'i tarayan antivirus bu acilisi
    // dakikalara cikarabiliyor. Once bunu soyle - guvenlik duvari cok daha
    // nadir bir sebep.
    const yasiyor = pyProc && pyProc.exitCode === null && !pyProc.killed;
    const sn = Math.round(BEKLEME_MS / 1000);
    s.push("");
    if (yasiyor) {
      s.push(...L([
        "Motor hâlâ çalışıyor ama " + sn + " saniyede açılışını tamamlayamadı.",
        "",
        "En olası sebep YAVAŞ DİSK: uygulama flash bellekten ya da ağ",
        "sürücüsünden çalıştırılıyorsa, antivirüs her dosyayı tek tek",
        "taradığı için açılış dakikalar sürebilir.",
        "  -> Klasörü bilgisayarın kendi diskine kopyalayıp oradan çalıştırın.",
        "",
        "Uygulamayı kapatmadan birkaç dakika beklemek de işe yarayabilir;",
        "motor açılışını tamamlarsa uygulama kendiliğinden çalışmaya başlar.",
      ], [
        "The engine is still running but did not finish starting in " + sn + " seconds.",
        "",
        "Most likely cause: a SLOW DISK. When the app runs from a flash drive or a",
        "network drive, the antivirus scans every file one by one and start-up",
        "can take minutes.",
        "  -> Copy the folder to the computer's own disk and run it from there.",
        "",
        "Waiting a few minutes without closing the app may also help; if the",
        "engine finishes starting, the app will start working on its own.",
      ]));
    } else {
      s.push(L("Motor cevap vermedi ve çalışmıyor görünüyor.",
               "The engine did not respond and does not seem to be running."));
    }
    s.push("");
    s.push(...L([
      "Daha nadir sebep: bir güvenlik yazılımı yerel (127.0.0.1) bağlantıyı",
      "engelliyor olabilir.",
    ], [
      "Less common cause: security software may be blocking the local",
      "(127.0.0.1) connection.",
    ]));
  }

  const metin = s.join("\n");
  // Kayit dosyasi: kullanicinin bize gonderebilecegi tek parca
  let kayit = "";
  try {
    kayit = path.join(app.getPath("userData"), "baslatma-hatasi.log");
    fs.mkdirSync(path.dirname(kayit), { recursive: true });
    fs.writeFileSync(kayit, new Date().toISOString() + "\n" + metin + "\n", "utf8");
  } catch (e) {
    kayit = "";
  }
  return { metin, kayit };
}

// Motorun acilmasi icin ne kadar beklenecek.
// 30 saniyeydi ve YETMIYORDU: PyInstaller paketi acilirken onlarca DLL
// yukluyor; yavas bir diskten (flash bellek, ag surucusu) ve antivirus her
// dosyayi taradiginda bu is dakikalar aliyor. Kullanici calisan bir motora
// ragmen "baslatilamadi" hatasi goruyordu.
const BEKLEME_MS = 180000;

function waitForBackend(toplamMs = BEKLEME_MS) {
  const ARALIK = 500;
  return new Promise((resolve, reject) => {
    const bitis = Date.now() + toplamMs;
    let sayac = 0;
    const tryOnce = () => {
      const kalan = bitis - Date.now();
      const req = http.get(
        { host: "127.0.0.1", port: PORT, path: "/health", timeout: 1000,
          headers: { [ANAHTAR_BASLIGI]: TOKEN } },
        (res) => {
          res.resume();
          console.log("[AllPrime] motor hazir (" + ((toplamMs - kalan) / 1000).toFixed(1) + " sn)");
          resolve(true);
        }
      );
      const tekrar = () => {
        if (kalan <= 0) return reject(new Error("Motor zaman asimi"));
        if (++sayac % 20 === 0) {
          console.log("[AllPrime] motor bekleniyor... " + Math.round((toplamMs - kalan) / 1000) + " sn");
        }
        setTimeout(tryOnce, ARALIK);
      };
      req.on("error", tekrar);
      req.on("timeout", () => { req.destroy(); tekrar(); });
    };
    tryOnce();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 900,
    minHeight: 650,
    title: "AllPrime",
    backgroundColor: pencereZemini(),
    // Pencere / gorev cubugu ikonu. logo.svg'den tools/ikon-uret.js uretir.
    // (Exe'nin Explorer'daki ikonu ayri: derlemede gomulur, Node ister.)
    icon: path.join(__dirname, "renderer", "icon.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      zoomFactor: kayitliBoyut(),     // arayuz boyutu: onay ekrani dahil her sayfada
    },
  });
  // Sag tik menusu: Electron'da varsayilan yoktur, fareyle kopyalama / yapistirma calismiyordu.
  // Yazi kutusunda Kes / Kopyala / Yapistir / Tumunu sec, secili metinde Kopyala; baska yerde
  // menu acilmaz. Dil o anki kayitli tercihtir. Bilgilendirme ekraninda da calisir.
  mainWindow.webContents.on("context-menu", (_e, p) => {
    const ogeler = sagTik.sablon(p, L);
    if (ogeler.length) Menu.buildFromTemplate(ogeler).popup({ window: mainWindow });
  });
  // Varsayilan menu yok (app.whenReady): yakinlastirma kisayollari Ayarlar'daki adimlari
  // kullanir, secim kaydedilir ve Ayarlar'da gorunur. Onay ekraninda da calisir.
  mainWindow.webContents.on("before-input-event", (e, input) => {
    const v = kisayolBoyutu(input);
    if (v === null) return;
    e.preventDefault();
    boyutUygula(v);
  });
  // Onay ekranindan ana ekrana geciste de kayitli boyut gecerli kalsin
  mainWindow.webContents.on("did-finish-load", () => {
    mainWindow.webContents.setZoomFactor(kayitliBoyut());
  });
  // Pencere YALNIZCA kendi sayfalarini gosterir (inceleme bulgusu 7). Bir
  // baglanti ya da sayfaya sizan bir icerik pencereyi baska bir adrese
  // goturemez, yeni pencere de acamaz; https baglantilari varsayilan
  // tarayicida acilir, gerisi yok sayilir.
  const kendi = pathToFileURL(path.join(__dirname, "renderer")).href + "/";
  mainWindow.webContents.on("will-navigate", (e, url) => {
    if (url.startsWith(kendi)) return;
    e.preventDefault();
    disaridaAc(url);
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    disaridaAc(url);
    return { action: "deny" };
  });
  // Sayfa sureci (renderer) cokerse pencere bos kalir ve kendiliginden duzelmez;
  // acilislarin bir bolumunde goruldu (cikis kodu 0x80000003, nedeni bilinmiyor).
  // Sayfa yeniden yuklenir, en cok 3 kez. Cokme ilk yukleme bitmeden oldugunda
  // pencerenin adresi bostur: reload() bir sey yuklemez, sayfa adiyla yuklenir.
  const pencere = mainWindow;
  let yenidenYukleme = 0;
  pencere.webContents.on("render-process-gone", (e, ayrinti) => {
    console.log("[AllPrime] sayfa sureci kapandi:", ayrinti.reason, ayrinti.exitCode);
    if (ayrinti.reason === "clean-exit" || yenidenYukleme >= 3) return;
    yenidenYukleme++;
    setTimeout(() => {
      if (!pencere.isDestroyed()) pencere.loadFile(acilisSayfasi());
    }, 300);
  });
  mainWindow.loadFile(acilisSayfasi());
}

// Bildirim bu surumde gosterilmediyse once bilgilendirme ekrani acilir
function acilisSayfasi() {
  return path.join(__dirname, "renderer", noticeSeen() ? "index.html" : "consent.html");
}

function disaridaAc(url) {
  if (/^https:\/\//i.test(url)) shell.openExternal(url);
  else console.log("[AllPrime] engellenen adres:", url);
}

// Klasor secme dialogu (genom FASTA secimi icin)
ipcMain.handle("pick-fasta", async () => {
  const res = await dialog.showOpenDialog(mainWindow, {
    title: L("Genom FASTA dosyası seç", "Choose a genome FASTA file"),
    properties: ["openFile"],
    filters: [{ name: "FASTA", extensions: ["fa", "fasta", "fna", "gz"] }],
  });
  if (res.canceled || !res.filePaths.length) return null;
  return res.filePaths[0];
});

ipcMain.handle("get-port", () => PORT);
ipcMain.handle("get-token", () => TOKEN);

ipcMain.handle("get-app-info", () => {
  const s = readSettings();
  return {
    version: app.getVersion(),
    noticeVersion: NOTICE_VERSION,
    lang: s.lang || "tr",
    noticeShown: noticeSeen(s),
    pcr_max: Number.isInteger(s.pcr_max) ? s.pcr_max : null,
    theme: kayitliTema(s),
    zoom: kayitliBoyut(s),
    assembly: GENOMLAR.includes(s.assembly) ? s.assembly : "GRCh38",
    lab: labTemizle(s.lab),
  };
});

ipcMain.handle("get-terms", (_e, lang) => {
  const file = lang === "en" ? "terms_en.html" : "terms.html";
  try {
    return fs.readFileSync(path.join(__dirname, "renderer", file), "utf8");
  } catch (e) {
    return `<p>Koşul metni okunamadı / Terms could not be read: ${e.message}</p>`;
  }
});

ipcMain.handle("notice-ack", (_e, lang) => {
  // "Anladim, devam et": bildirimin gosterildigi (surum + tarih) yazilir. Windows kullanici
  // adi ve bilgisayar adi TUTULMAZ; eski onay alanlari silinir, tercihler (tema, lab...) kalir.
  // Dosya yazilamazsa da uygulama acilir (bildirim bir sonraki acilista yine gosterilir).
  writeSettings(noticeKaydi(readSettings(), lang, new Date().toISOString()));
  if (mainWindow) {
    mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
  }
  return true;
});

ipcMain.handle("set-lang", (_e, lang) => {
  const s = readSettings();
  s.lang = lang === "en" ? "en" : "tr";
  writeSettings(s);
  return s.lang;
});

// Laboratuvarin cogaltabildigi en uzun urun (bp). Makul aralik disi yok sayilir.
ipcMain.handle("set-pcr-max", (_e, bp) => {
  const v = Math.round(Number(bp));
  if (!Number.isFinite(v) || v < 100 || v > 100000) return null;
  const s = readSettings();
  s.pcr_max = v;
  writeSettings(s);
  return v;
});

// Tema: CSS'teki prefers-color-scheme sorgusu buna uyar (onay ekrani dahil)
ipcMain.handle("set-theme", (_e, v) => {
  if (!TEMALAR.includes(v)) return null;
  const s = readSettings();
  s.theme = v;
  writeSettings(s);
  nativeTheme.themeSource = v;
  if (mainWindow) mainWindow.setBackgroundColor(pencereZemini());
  return v;
});

// Arayuz boyutu: yazilar, dugmeler ve tablolar birlikte buyur (sayfa yakinlastirma).
// Stiller piksel olcusuyle yazildigi icin yalnizca yazi boyutunu buyutmek orantiyi bozardi.
ipcMain.handle("set-zoom", (_e, z) => {
  const v = Number(z);
  if (!BOYUTLAR.includes(v)) return null;
  return boyutUygula(v);
});

// Acilistaki referans genom (ust cubuktaki secim yalnizca o oturum icin)
ipcMain.handle("set-default-assembly", (_e, a) => {
  if (!GENOMLAR.includes(a)) return null;
  const s = readSettings();
  s.assembly = a;
  writeSettings(s);
  return a;
});

// Laboratuvar varsayilanlari: fabrika degerinden farkli gelismis parametreler.
// Bos nesne kaydi temizler (fabrika degerlerine donus).
ipcMain.handle("set-lab-defaults", (_e, o) => {
  const s = readSettings();
  s.lab = labTemizle(o);
  return writeSettings(s) ? s.lab : null;
});

// Favoriler (2026-11-14). Dosya ayarlarla ayni klasorde ama ayri: biri bozulursa oteki etkilenmez.
// Kayit arayuzden gelir; dogrulama favoriler.js'te (bilinmeyen alan atilir, metin kisaltilir).
const favDosyasi = () => path.join(app.getPath("userData"), "favoriler.json");
ipcMain.handle("fav-list", () => favoriler.liste(favDosyasi()));
ipcMain.handle("fav-add", (_e, kayit) => favoriler.ekle(favDosyasi(), kayit));
ipcMain.handle("fav-remove", (_e, id) => favoriler.sil(favDosyasi(), String(id || "")));
ipcMain.handle("fav-note", (_e, id, not) => favoriler.notYaz(favDosyasi(), String(id || ""), not));

app.whenReady().then(async () => {
  if (!TEK_KOPYA) return;              // ikinci kopya: motor ve pencere yok (yukaridaki kilit)
  // Tema pencere ve motor hata kutusundan once: ilk cizim kayitli temayla olsun
  nativeTheme.themeSource = kayitliTema();
  // Electron'un varsayilan (Ingilizce) menusu gizliyken de kisayollari calisiyordu
  // (2026-11-03): Ctrl+R sayfayi yenileyip sonuclari siliyor, Ctrl + / - Ayarlar'a
  // yansimadan ve kaydedilmeden yakinlastiriyordu (uc basista %83; Ayarlar'da en kucuk
  // %90), Ctrl+Shift+I gelistirici araclarini, F11 tam ekrani aciyordu. Menu yok; yazi
  // alanlarindaki Ctrl+A / C / V / X / Z Chromium'un kendi duzenleme kisayollaridir,
  // menuye bagli degildir.
  Menu.setApplicationMenu(null);
  try {
    PORT = await bosPortBul();
    console.log("[AllPrime] motor portu:", PORT);
  } catch (e) {
    PORT = 5077;                       // son care: eski sabit port
    console.log("[AllPrime] bos port bulunamadi, 5077 kullaniliyor:", e.message);
  }
  startBackend();
  try {
    await waitForBackend();
  } catch (e) {
    // Genel bir cumle yerine NE OLDUGUNU soyle: hangi komut denendi, isletim
    // sistemi ne dedi, motor ne yazdi. Baska bir bilgisayarda tek ipucu bu.
    const { metin, kayit } = baslatmaTanisi();
    dialog.showErrorBox(
      L("Motor başlatılamadı", "Engine could not be started"),
      metin + (kayit ? L("\n\nBu rapor şu dosyaya da yazıldı:\n",
                         "\n\nThis report was also written to:\n") + kayit : ""));
  }
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// Motoru alt surecleriyle (ozgulluk taramasinin isci surecleri) birlikte kapat.
// Windows'ta child.kill() yalnizca ana sureci sonlandirir; tarama surerken uygulama
// kapatilinca isciler acik kaliyordu (2026-10-31). Motor tarafinda da bekci var
// (specificity._ebeveyn_bekcisi); bu, kapanisi beklemeden temizler. Iki olay da
// cagirir; ikinci cagri ayni PID'e (yeniden kullanilmis olabilir) dokunmasin.
function motoruKapat() {
  if (!pyProc || pyProc._kapatildi) return;
  pyProc._kapatildi = true;
  try {
    if (process.platform === "win32" && pyProc.pid && pyProc.exitCode === null) {
      spawnSync("taskkill", ["/PID", String(pyProc.pid), "/T", "/F"],
                { windowsHide: true, timeout: 5000 });
    } else {
      pyProc.kill();
    }
  } catch (e) {
    try { pyProc.kill(); } catch (e2) {}
  }
}

app.on("window-all-closed", () => {
  motoruKapat();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  motoruKapat();
});
