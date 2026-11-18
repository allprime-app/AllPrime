# AllPrime - kaynak kodunu zip olarak uret (GPL v2 Bolum 3a)
#
# Neden var: uygulama klasoru kurum disina verilirse primer3'un lisansi (GPL v2
# Bolum 3) programla birlikte TAM kaynagin da verilmesini ister. Arayuz zaten duz
# JS, primer3'un C kaynaklari resources\backend\_internal\primer3 altinda; eksik
# olan motorun kendi .py dosyalari ve derleme betikleriydi (tarama bulgusu L-A,
# 2026-10-31). Yazili teklif (Bolum 3b) yerine kaynagin kendisi konur: teklif 3 yil
# boyunca isteyen HERKESE kaynak verme yuku getirir ve kodu zaten saklamaz.
#
# Zip git'ten uretilir, yani .gitignore'dakiler (.venv, node_modules, genom...)
# girmez. Commit edilmemis degisiklikler de girer (git stash create: calisma
# agacina ve stash listesine dokunmaz). git'e HIC eklenmemis dosyalar girmez;
# varsa uyarilir.
#
# Kullanim (kurulu-guncelle.ps1 her calistiginda cagirir):
#     .\kaynak-zip.ps1 -Hedef ..\AllPrime\kaynak

param(
    [Parameter(Mandatory = $true)][string]$Hedef
)

$ErrorActionPreference = "Stop"
$kaynak = $PSScriptRoot
$surum = (Get-Content (Join-Path $kaynak "electron\package.json") -Raw | ConvertFrom-Json).version
$ad = "AllPrime-kaynak-$surum"
# git -C ile calisir: goreli yol git'te depoya gore cozulurdu, mutlak yola cevir
$Hedef = (New-Item -ItemType Directory -Force $Hedef).FullName

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Kaynak zip'i uretilemedi: git bulunamadi." -ForegroundColor Red
    exit 1
}

# git uyarilari (LF/CRLF) stderr'e yazar; Windows PowerShell 5.1 cikti
# yonlendirilmisken bunu hata sayip betigi durdurabilir. Bu yuzden git cagrilari
# Continue ile yapilir, basari $LASTEXITCODE ile denetlenir.
$ErrorActionPreference = "Continue"
$ref = & git -C $kaynak -c core.safecrlf=false stash create
if ($LASTEXITCODE -ne 0) {
    Write-Host "Kaynak zip'i uretilemedi: burasi bir git deposu degil mi? ($kaynak)" -ForegroundColor Red
    exit 1
}
$degisiklik = [bool]$ref
if (-not $ref) { $ref = "HEAD" }
$izsiz = @(& git -C $kaynak ls-files --others --exclude-standard)
$dosyaSayisi = @(& git -C $kaynak ls-tree -r --name-only $ref).Count

$zip = Join-Path $Hedef "$ad.zip"
$gecici = "$zip.yeni"
# .claude (gelistirme aracinin yerel izin / komut gecmisi dosyalari) zip'e GIRMEZ: ust duzeyde de, alt
# klasorlerde de glob pathspec ile acikca dislanir (git'e yanlislikla eklenmis olsa bile);
# asagidaki denetim zip'te hala .claude kalirsa uretimi durdurur.
& git -C $kaynak archive --format=zip --prefix="$ad/" -o $gecici $ref -- . ":(exclude,glob)**/.claude/**"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $gecici)) {
    Write-Host "Kaynak zip'i uretilemedi: git archive basarisiz (kod $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}
$ErrorActionPreference = "Stop"

# Denetim: zip'te .claude girdisi olmamali (varsa uretim basarisiz sayilir)
Add-Type -AssemblyName System.IO.Compression.FileSystem
$arsiv = [System.IO.Compression.ZipFile]::OpenRead($gecici)
try { $claudeGirdi = @($arsiv.Entries | Where-Object { $_.FullName -match '(^|/)\.claude(/|$)' }) }
finally { $arsiv.Dispose() }
if ($claudeGirdi.Count -gt 0) {
    Remove-Item $gecici -Force
    Write-Host "Kaynak zip'i uretilemedi: zip icinde .claude girdisi var ($($claudeGirdi.Count))." -ForegroundColor Red
    exit 1
}

# Eski surumlerin zip'i kalmasin: klasorde yalnizca icindeki programin kaynagi olmali
Get-ChildItem $Hedef -Filter "AllPrime-kaynak-*.zip" | Remove-Item -Force
Move-Item $gecici $zip
$kb = [math]::Round((Get-Item $zip).Length / 1KB)
$not = if ($degisiklik) { ", commit edilmemis degisiklikler dahil" } else { "" }
Write-Host "Kaynak: $zip ($dosyaSayisi dosya, $kb KB$not)"
foreach ($f in $izsiz) {
    Write-Host "  UYARI: git'e eklenmemis, zip'e girmedi: $f" -ForegroundColor Yellow
}
exit 0
