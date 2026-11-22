# AllPrime - kurulu uygulamayi kaynaktan guncelle
#
# Neden var: kurulu uygulama (..\AllPrime) baska bilgisayarlara OLDUGU GIBI
# kopyalanan sey. Kaynakta yapilan her degisiklik oraya elle tasiniyordu ve
# uc ayri seferde bir dosya unutuldu (motor, sonra package.json). Sonuc: lab
# makinelerinde "yeni arayuz + eski motor" ya da "surum uyusmuyor" uyarilari.
# Bu betik tam listeyi tek yerde tutar. Her calistirmada uygulama klasorune
# kaynak\AllPrime-kaynak-<surum>.zip de konur (GPL v2 Bolum 3a; bkz. kaynak-zip.ps1).
# Sonunda kurulu-temizle.ps1 Electron artiklarini, fazla dil paketlerini ve eski
# yedekleri temizler.
#
# Kullanim (PowerShell, depo kokunde):
#     .\kurulu-guncelle.ps1            # arayuz + main.js + package.json
#     .\kurulu-guncelle.ps1 -Motor     # ustune motoru da derleyip yerlestirir
#
# Motor derlemesi OneDrive DISINDA yapilir (OneDrive build klasorunu kilitler).
# Not: bu makinede Smart App Control artik kapali (2026-10-29 denetlendi); kurulu
# uygulama paketli exe'yi kullanir, backend.txt kaldirildi. SAC'nin imzasiz exe'yi
# engelledigi bir makinede uygulama klasorune backend.txt (icinde kaynagin backend
# yolu) konursa motor Python ile kaynaktan calisir - bkz. electron/main.js.

param(
    [switch]$Motor
)

$ErrorActionPreference = "Stop"
$kaynak = $PSScriptRoot
$uygulama = Join-Path (Split-Path $kaynak -Parent) "AllPrime"

if (-not (Test-Path (Join-Path $uygulama "AllPrime.exe"))) {
    Write-Host "Kurulu uygulama bulunamadi: $uygulama" -ForegroundColor Red
    exit 1
}
$acik = Get-Process "AllPrime" -ErrorAction SilentlyContinue
if ($acik) {
    Write-Host "AllPrime acik - once kapatin (dosyalar kilitli olur, kopya yarim kalir)." -ForegroundColor Red
    exit 1
}

# ---- 1) Arayuz katmani: TAM liste burada ------------------------------------
$app = Join-Path $uygulama "resources\app"
$dosyalar = @(
    @{ k = "electron\main.js";               h = "main.js" },
    @{ k = "electron\preload.js";            h = "preload.js" },
    @{ k = "electron\favoriler.js";          h = "favoriler.js" },    # main.js require eder
    @{ k = "electron\sagTik.js";             h = "sagTik.js" },       # main.js require eder
    @{ k = "electron\motorBekle.js";         h = "motorBekle.js" },   # main.js require eder
    @{ k = "electron\package.json";          h = "package.json" },   # SURUM buradan okunur
    @{ k = "electron\renderer\index.html";   h = "renderer\index.html" },
    @{ k = "electron\renderer\app.js";       h = "renderer\app.js" },
    @{ k = "electron\renderer\csv.js";       h = "renderer\csv.js" },      # CSV bicimi (app.js'ten once)
    @{ k = "electron\renderer\yon.js";       h = "renderer\yon.js" },      # F/R genin yonunde (app.js'ten once)
    @{ k = "electron\renderer\i18n.js";      h = "renderer\i18n.js" },
    @{ k = "electron\renderer\style.css";    h = "renderer\style.css" },
    @{ k = "electron\renderer\logo.svg";     h = "renderer\logo.svg" },     # ust bar + onay ekrani
    @{ k = "electron\renderer\icon.png";     h = "renderer\icon.png" },     # pencere ikonu
    @{ k = "electron\renderer\consent.html"; h = "renderer\consent.html" },
    @{ k = "electron\renderer\consent.js";   h = "renderer\consent.js" },
    @{ k = "electron\renderer\terms.html";   h = "renderer\terms.html" },
    @{ k = "electron\renderer\terms_en.html";h = "renderer\terms_en.html" }
)
$degisen = 0
foreach ($d in $dosyalar) {
    # .claude (gelistirme aracinin yerel izin / komut gecmisi dosyalari) kurulu klasore ASLA kopyalanmaz
    if ($d.k -match '(^|\\)\.claude(\\|$)') { Write-Host "  .claude atlandi: $($d.k)" -ForegroundColor Yellow; continue }
    $src = Join-Path $kaynak $d.k
    $dst = Join-Path $app $d.h
    if (-not (Test-Path $src)) { Write-Host "  kaynakta yok: $($d.k)" -ForegroundColor Yellow; continue }
    $ayni = (Test-Path $dst) -and ((Get-FileHash $src).Hash -eq (Get-FileHash $dst).Hash)
    if (-not $ayni) {
        Copy-Item $src $dst -Force
        Write-Host "  guncellendi: $($d.h)"
        $degisen++
    }
}
Write-Host "Arayuz: $degisen dosya guncellendi, $($dosyalar.Count - $degisen) zaten ayniydi."

# ---- 1b) Lisans dosyalari + KURULUM.txt / USER_GUIDE.txt: uygulama klasorunun KOKUNE
# Klasor kopyalandiginda lisans ve telif bildirimleri de gitmeli (MIT/BSD/Apache
# bunu sart kosar). THIRD-PARTY-NOTICES.txt backend\lisans_bildirimi.py ile uretilir.
# LICENSE-GPL-3.0.txt: motordaki Apache-2.0 bilesenler (requests, OpenSSL) GPL v2 ile
# uyumsuz, GPL v3 ile uyumlu; program kurum disina GPL v3 ile verilir (2026-10-31).
foreach ($ad in @("LICENSE", "LICENSE-GPL-3.0.txt", "AUTHORS", "THIRD-PARTY-NOTICES.txt", "KURULUM.txt", "USER_GUIDE.txt")) {
    $src = Join-Path $kaynak $ad
    $dst = Join-Path $uygulama $ad
    if (-not (Test-Path $src)) { Write-Host "  kaynakta yok: $ad" -ForegroundColor Yellow; continue }
    if (-not ((Test-Path $dst) -and ((Get-FileHash $src).Hash -eq (Get-FileHash $dst).Hash))) {
        Copy-Item $src $dst -Force
        Write-Host "  guncellendi: $ad (uygulama koku)"
    }
}

# ---- 1c) Electron calisma dosyalari (exe, dll, pak, locales) ----------------
# Eskiden hic tasinmiyordu: package.json'da Electron yukseltilse de kurulu
# klasor ilk kurulumdaki surumde kaliyordu (33.4.11, destegi bitmis). Kaynak:
# electron\node_modules\electron\dist. Bu klasor bos kalirsa (yeni npm paket
# betiklerini calistirmiyor): "node node_modules\electron\install.js".
# Yalnizca surum farkliysa yapilir; eskiler TEMP'e yedeklenir. electron.exe ->
# AllPrime.exe; resources\ atlanir (app ve backend bizim, default_app istenmez).
# Yeni exe'nin kimligi asagidaki 2b adiminda yeniden gomulur. Yeni surumde OLMAYAN
# eski dosyalar ve fazla dil paketleri 5. adimda (kurulu-temizle.ps1) kalkar.
$dist = Join-Path $kaynak "electron\node_modules\electron\dist"
$surumDosyasi = Join-Path $dist "version"
$yedekEl = Join-Path $env:TEMP ("AllPrime-electron-yedek-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
if (Test-Path $surumDosyasi) {
    $yeniEl = (Get-Content $surumDosyasi -Raw).Trim()
    $kuruluSurum = Join-Path $uygulama "version"
    $eskiEl = if (Test-Path $kuruluSurum) { (Get-Content $kuruluSurum -Raw).Trim() } else { "?" }
    if ($yeniEl -ne $eskiEl) {
        New-Item -ItemType Directory $yedekEl | Out-Null
        foreach ($f in Get-ChildItem $dist) {
            if ($f.Name -eq "resources") { continue }
            # Electron'un MIT LICENSE'i AllPrime'in GPL LICENSE'inin USTUNE yaziliyordu
            # (2026-10-28, v0.8.5); MIT metni zaten THIRD-PARTY-NOTICES.txt icinde.
            if ($f.Name -eq "LICENSE") { continue }
            if ($f.Name -eq ".claude") { continue }      # gelistirme araci yerel dosyalari dagitima girmez
            $ad = if ($f.Name -eq "electron.exe") { "AllPrime.exe" } else { $f.Name }
            $hedefYol = Join-Path $uygulama $ad
            if (Test-Path $hedefYol) { Move-Item $hedefYol (Join-Path $yedekEl $ad) }
            Copy-Item $f.FullName $hedefYol -Recurse
        }
        Write-Host "Electron: $eskiEl -> $yeniEl (eskileri: $yedekEl)"
    }
} else {
    Write-Host "  Electron calisma dosyalari yok ($dist) - atlandi" -ForegroundColor Yellow
}

# ---- 2) Surum tutarliligi: package.json ile server.py SURUM esit mi? ---------
$pj = (Get-Content (Join-Path $kaynak "electron\package.json") -Raw | ConvertFrom-Json).version
$sv = (Select-String -Path (Join-Path $kaynak "backend\server.py") -Pattern 'SURUM\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
if ($pj -ne $sv) {
    Write-Host "UYARI: package.json surumu ($pj) ile server.py SURUM ($sv) farkli - ikisini birlikte artirin." -ForegroundColor Yellow
} else {
    Write-Host "Surum: $pj (arayuz = motor)"
}

# ---- 2b) Exe kimligi: Gorev Yoneticisi / Explorer'da "Electron" degil AllPrime -
# Kurulu exe Electron'un kendi calistiricisi (yeniden adlandirilmis electron.exe);
# icindeki ad, ikon ve surum hala Electron'unkuydu. rcedit ile gomulur. YALNIZCA
# gerekirse yapilir: her calistirmada exe'yi degistirmek parmak izini (hash) de
# gereksiz yere degistirirdi. Exe imzasiz oldugu icin bozulacak imza yok.
# rcedit electron-builder onbelleginde gelir; bulunamazsa adim atlanir.
$exe = Join-Path $uygulama "AllPrime.exe"
$ico = Join-Path $kaynak "electron\build\icon.ico"     # electron\tools\ico-uret.ps1 uretir
$vi = (Get-Item $exe).VersionInfo
if ($vi.ProductName -ne "AllPrime" -or $vi.ProductVersion -ne $pj) {
    $rcedit = Get-ChildItem (Join-Path $kaynak ".cache\electron-builder\winCodeSign"),
        (Join-Path $env:LOCALAPPDATA "electron-builder\Cache\winCodeSign") `
        -Recurse -Filter "rcedit-x64.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $rcedit -or -not (Test-Path $ico)) {
        Write-Host "  exe kimligi atlandi (rcedit-x64.exe ya da icon.ico yok)" -ForegroundColor Yellow
    } else {
        $yedekExe = Join-Path $env:TEMP ("AllPrime-exe-yedek-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".exe")
        Copy-Item $exe $yedekExe
        & $rcedit.FullName $exe --set-icon $ico `
            --set-version-string "FileDescription" "AllPrime" `
            --set-version-string "ProductName" "AllPrime" `
            --set-version-string "InternalName" "AllPrime" `
            --set-version-string "OriginalFilename" "AllPrime.exe" `
            --set-version-string "CompanyName" "Eren Kilinc" `
            --set-version-string "LegalCopyright" "Copyright (c) 2026 Eren Kilinc - GPL-2.0-or-later" `
            --set-file-version $pj --set-product-version $pj
        if ($LASTEXITCODE -ne 0) {
            Copy-Item $yedekExe $exe -Force
            Write-Host "  UYARI: rcedit basarisiz (kod $LASTEXITCODE); exe yedekten geri yuklendi." -ForegroundColor Yellow
        } else {
            Write-Host "  exe kimligi gomuldu: AllPrime $pj (eskisi: $yedekExe)"
        }
    }
}

# ---- 3) Motor (istege bagli) --------------------------------------------------
if ($Motor) {
    $py = Join-Path $kaynak "backend\.venv\Scripts\python.exe"
    $tmp = Join-Path $env:TEMP "allprime-derleme"
    Write-Host "Motor derleniyor (OneDrive disinda: $tmp)..."
    Push-Location (Join-Path $kaynak "backend")
    try {
        & $py -m PyInstaller --noconfirm --clean --workpath (Join-Path $tmp "build") `
            --distpath (Join-Path $tmp "dist") --log-level ERROR allprime-server.spec
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller basarisiz (kod $LASTEXITCODE)" }
    } finally { Pop-Location }

    $hedef = Join-Path $uygulama "resources\backend"
    $yedek = Join-Path $tmp ("backend-yedek-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    if (Test-Path $hedef) { Move-Item $hedef $yedek }
    Copy-Item (Join-Path $tmp "dist\allprime-server") $hedef -Recurse
    Get-ChildItem $hedef -Recurse -Force -Directory -Filter ".claude" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force
    $exe = Get-Item (Join-Path $hedef "allprime-server.exe")
    Write-Host "Motor yerlestirildi: $($exe.LastWriteTime)  (eskisi: $yedek)"
}

# ---- 4) AllPrime'in kaynak kodu (GPL v2 Bolum 3a) ----------------------------
# Klasor kurum disina verilirse kaynak da birlikte gitsin. Eskiden klasorde
# motorun .py dosyalari da, yazili teklif de yoktu (tarama bulgusu L-A,
# 2026-10-31). Her seferinde yeniden uretilir (~0,5 MB); eski surumun zip'i silinir.
& (Join-Path $kaynak "kaynak-zip.ps1") -Hedef (Join-Path $uygulama "kaynak")
if ($LASTEXITCODE -ne 0) {
    Write-Host "Kaynak zip'i uretilemedi - klasoru bu haliyle kurum disina vermeyin." -ForegroundColor Red
    exit 1
}

# ---- 5) Artiklar ve eski yedekler (bkz. kurulu-temizle.ps1) ------------------
& (Join-Path $kaynak "kurulu-temizle.ps1") -Uygulama $uygulama -Dist $dist -Yedek $yedekEl

# ---- 6) Denetim: kurulu klasorde .claude var mi? ------------------------------
# Bu betik .claude kopyalamaz; ama kurulu klasorde calisan bir gelistirme araci oturumu buraya
# yerel izinler ve komut gecmisi iceren .claude\settings.local.json yazabilir. SILINMEZ (sizin
# dosyaniz); yalniz uyarilir: klasoru baskasina vermeden once o klasoru cikarin.
$claudeKurulu = @(Get-ChildItem $uygulama -Recurse -Force -Directory -Filter ".claude" -ErrorAction SilentlyContinue)
foreach ($c in $claudeKurulu) {
    Write-Host "  UYARI: kurulu klasorde .claude var ($($c.FullName)); klasoru kurum disina vermeden once cikarin." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Bitti. Kopyalanacak klasor: $uygulama" -ForegroundColor Green
