# AllPrime - kurulu klasordeki artiklar ve TEMP'teki eski yedekler
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
#
# kurulu-guncelle.ps1 her calistirmanin sonunda cagirir; tek basina da calisir:
#     .\kurulu-temizle.ps1 -Uygulama ..\AllPrime -Dist electron\node_modules\electron\dist
#
# 1. Electron'un artik dagitmadigi calisma dosyalari (koktaki *.dll *.pak *.bin *.dat)
#    yedege tasinir. Yukseltme yeni surumun dosyalarini koyup ayni adli eskilerin
#    yerini aliyordu; yeni surumde OLMAYANLAR ise kaliyordu: 33.x'ten libEGL.dll ve
#    libGLESv2.dll (8,6 MB) - 44.10.0'da hicbir surec yuklemiyordu (2026-11-01; ana,
#    GPU, renderer ve motor surecleri tek tek denetlendi).
# 2. Dil paketleri: arayuz yalnizca Turkce ve Ingilizce. locales\ icinde yalnizca
#    -Diller kalir (55 paketten 53'u, ~48 MB eksilir); Chromium sistem dilinin
#    paketini bulamazsa en-US'i kullanir.
# 3. Eski yedekler: kurulu-guncelle.ps1 her calistirmada exe / motor / Electron
#    yedegi birakiyor, hicbirini silmiyordu (2026-11-01: TEMP'te 26 exe + 35 motor
#    yedegi, 6,6 GB). Her turden yalnizca en yenisi kalir; geri donmek icin bir
#    onceki surum yeter.

param(
    [Parameter(Mandatory = $true)] [string]$Uygulama,
    [string]$Dist = "",
    [string[]]$Diller = @("tr.pak", "en-US.pak"),
    [string]$Yedek = "",
    [string]$Gecici = $env:TEMP
)

$ErrorActionPreference = "Stop"
$Uygulama = (Resolve-Path $Uygulama).Path
if (-not $Yedek) {
    $Yedek = Join-Path $Gecici ("AllPrime-electron-yedek-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
}

# ---- 1-2) Artik calisma dosyalari ve fazla dil paketleri -----------------------
$artik = @()
if ($Dist -and (Test-Path (Join-Path $Dist "version"))) {
    $artik += @(Get-ChildItem $Uygulama -File | Where-Object {
        @(".dll", ".pak", ".bin", ".dat") -contains $_.Extension -and
        -not (Test-Path (Join-Path $Dist $_.Name)) })
}
$loc = Join-Path $Uygulama "locales"
if (Test-Path $loc) {
    $artik += @(Get-ChildItem $loc -File -Filter "*.pak" | Where-Object { $Diller -notcontains $_.Name })
}
if ($artik.Count) {
    $mb = ($artik | Measure-Object Length -Sum).Sum / 1MB
    foreach ($f in $artik) {
        # Dil paketleri ayri alt klasore: Electron yukseltmesi eski locales\ klasorunu
        # de ayni yedege tasir, adlar cakismasin.
        $alt = if ($f.DirectoryName -eq $loc) { Join-Path $Yedek "locales-fazla" } else { $Yedek }
        New-Item -ItemType Directory $alt -Force | Out-Null
        Move-Item $f.FullName (Join-Path $alt $f.Name)
    }
    Write-Host ("Kullanilmayan {0} Electron dosyasi kaldirildi ({1:N1} MB; yedek: {2})" -f $artik.Count, $mb, $Yedek)
}

# ---- 3) Eski yedekler: her turden yalnizca en yenisi ---------------------------
# Adlardaki tarih-saat (yyyyMMdd-HHmmss) siralamayi verir.
foreach ($desen in @("AllPrime-exe-yedek-*.exe", "AllPrime-electron-yedek-*",
                     "allprime-derleme\backend-yedek-*")) {
    $eskiler = @(Get-Item (Join-Path $Gecici $desen) -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -Skip 1)
    foreach ($e in $eskiler) { Remove-Item $e.FullName -Recurse -Force }
    if ($eskiler.Count) { Write-Host "  eski yedek silindi: $($eskiler.Count) x $desen" }
}
