# -*- mode: python ; coding: utf-8 -*-
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['flask', 'flask_cors']
tmp_ret = collect_all('primer3')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pyfaidx')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# primer3 tekerlegi 5 derlenmis komut satiri araci getirir; motor primer3-py'yi
# yalnizca kitaplik (.pyd) olarak kullanir, bu exe'leri hicbir yerde cagirmaz.
# Pakete girmesinler (gereksiz, imzasiz exe; amplicon3_core GPL v3 kaynaklidir).
_GEREKSIZ_EXE = {'primer3_core.exe', 'ntthal.exe', 'ntdpal.exe', 'oligotm.exe',
                 'amplicon3_core.exe'}


def _exe_degil(oge):
    # datas/binaries ogesi: (kaynak, hedef[, tur]); kaynak dosya adina bakilir
    import os
    return os.path.basename(oge[0]).lower() not in _GEREKSIZ_EXE


datas = [d for d in datas if _exe_degil(d)]
binaries = [b for b in binaries if _exe_degil(b)]


a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='allprime-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='allprime-server',
)
