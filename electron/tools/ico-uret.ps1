# AllPrime - exe ikonu (icon.ico) uretimi
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
#
# renderer\icon.png (256x256, ikon-uret.js logo.svg'den uretir) -> build\icon.ico
# Her boy (16-256) ayri ayri yuksek kaliteli kucultmeyle cizilir ve PNG olarak
# ICO'ya gomulur (Windows Vista+ PNG'li ICO okur). Tek 256'lik goruntu verince
# Explorer 16/32 boyutlarda bulaniklastiriyor.
#
# build\icon.ico: kurulu-guncelle.ps1 exe'ye gomer (rcedit); electron-builder da
# "build" klasorundeki icon.ico'yu kendiliginden kullanir.
#
# Calistirma (depo kokunden):  .\electron\tools\ico-uret.ps1

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$kok = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$kaynak = Join-Path $kok "electron\renderer\icon.png"
$hedefDizin = Join-Path $kok "electron\build"
$hedef = Join-Path $hedefDizin "icon.ico"
New-Item -ItemType Directory -Force $hedefDizin | Out-Null

$boylar = @(16, 24, 32, 48, 64, 128, 256)
$asil = [System.Drawing.Image]::FromFile($kaynak)
$pngler = @()
try {
    foreach ($b in $boylar) {
        $bmp = New-Object System.Drawing.Bitmap $b, $b, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $g.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
        $g.Clear([System.Drawing.Color]::Transparent)
        $g.DrawImage($asil, 0, 0, $b, $b)
        $g.Dispose()
        $ms = New-Object System.IO.MemoryStream
        $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
        $bmp.Dispose()
        $pngler += , $ms.ToArray()
        $ms.Dispose()
    }
} finally { $asil.Dispose() }

# ICO: 6 bayt baslik + her goruntu icin 16 bayt dizin + PNG verileri
$out = New-Object System.IO.MemoryStream
$w = New-Object System.IO.BinaryWriter $out
$w.Write([UInt16]0); $w.Write([UInt16]1); $w.Write([UInt16]$boylar.Count)
$ofset = 6 + 16 * $boylar.Count
for ($i = 0; $i -lt $boylar.Count; $i++) {
    $b = $boylar[$i]; $veri = $pngler[$i]
    $kenar = if ($b -ge 256) { 0 } else { $b }       # 256 -> 0 (ICO kurali)
    $w.Write([Byte]$kenar); $w.Write([Byte]$kenar)
    $w.Write([Byte]0); $w.Write([Byte]0)              # renk sayisi, ayrilmis
    $w.Write([UInt16]1); $w.Write([UInt16]32)         # duzlem, bit derinligi
    $w.Write([UInt32]$veri.Length); $w.Write([UInt32]$ofset)
    $ofset += $veri.Length
}
foreach ($veri in $pngler) { $w.Write($veri) }
$w.Flush()
[System.IO.File]::WriteAllBytes($hedef, $out.ToArray())
$w.Dispose()
Write-Host "icon.ico yazildi: $hedef ($((Get-Item $hedef).Length) bayt, $($boylar -join '/') px)"
