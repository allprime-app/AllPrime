# AllPrime - dagitim paketi uretimi
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
# Kullanim:  .\build.ps1            -> sidecar + kurulum dosyasi
#            .\build.ps1 -SidecarOnly -> sadece Python sidecar'i derle
param([switch]$SidecarOnly)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venvPy = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    throw "backend\.venv bulunamadi. Once: python -m venv backend\.venv"
}

# --- 1) Python sidecar (PyInstaller) ---------------------------------------
# ONEMLI: OneDrive senkronize klasorde build/ kilitlenip PermissionError verir.
# Bu yuzden gecici klasorde derleyip sonucu electron\sidecar'a kopyaliyoruz.
$tmp = Join-Path $env:TEMP ("allprime-build-" + [guid]::NewGuid().ToString("N").Substring(0,8))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null

Write-Host "[1/3] Sidecar derleniyor..." -ForegroundColor Cyan
& $venvPy -m PyInstaller --noconfirm --clean `
    --workpath (Join-Path $tmp "build") `
    --distpath (Join-Path $tmp "dist") `
    (Join-Path $root "backend\allprime-server.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller derlemesi basarisiz." }

Write-Host "[2/3] Sidecar electron\sidecar'a kopyalaniyor..." -ForegroundColor Cyan
$sidecar = Join-Path $root "electron\sidecar"
if (Test-Path $sidecar) { Remove-Item -Recurse -Force $sidecar }
New-Item -ItemType Directory -Path $sidecar -Force | Out-Null
# onedir derlemesi: exe TEK BASINA calismaz, _internal\ ile birlikte kopyalanmali
Copy-Item -Recurse -Force (Join-Path $tmp "dist\allprime-server\*") $sidecar
Remove-Item -Recurse -Force $tmp
# Dagitima .claude (gelistirme aracinin yerel izin / komut gecmisi dosyalari) GIRMEZ: uretilen sidecar'dan
# acikca temizlenir; electron-builder tarafinda da package.json "build" filtreleri disarida birakir.
Get-ChildItem $sidecar -Recurse -Force -Directory -Filter ".claude" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force

if ($SidecarOnly) {
    Write-Host "Sidecar hazir: $sidecar" -ForegroundColor Green
    return
}

# --- 2) Electron kurulum dosyasi -------------------------------------------
Write-Host "[3/3] Kurulum dosyasi uretiliyor (electron-builder)..." -ForegroundColor Cyan
Push-Location (Join-Path $root "electron")
try {
    npm run dist
    if ($LASTEXITCODE -ne 0) { throw "electron-builder basarisiz." }
} finally { Pop-Location }

# Denetim: uretilen paket klasorunde .claude varsa dagitim durdurulur (filtre calismamis demektir).
$paketKlasoru = Join-Path $root "electron\dist\win-unpacked"
if (Test-Path $paketKlasoru) {
    $claude = @(Get-ChildItem $paketKlasoru -Recurse -Force -Directory -Filter ".claude" -ErrorAction SilentlyContinue)
    if ($claude.Count -gt 0) {
        throw ("Paketin icinde .claude var, dagitmayin: " + (($claude | ForEach-Object { $_.FullName }) -join "; "))
    }
    Write-Host "Denetim: pakette .claude yok." -ForegroundColor Green
}

Write-Host "Bitti. Cikti: electron\dist\" -ForegroundColor Green
Write-Host "NOT: Genom FASTA dosyalari pakete DAHIL DEGIL (~6 GB)." -ForegroundColor Yellow
Write-Host "     Kurulumdan sonra genomes\ klasorunu uygulamanin yanina kopyalayin." -ForegroundColor Yellow
