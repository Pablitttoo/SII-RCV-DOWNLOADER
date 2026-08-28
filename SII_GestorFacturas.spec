# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_all

datas = [
    ('assets', 'assets'),
    ('empresas.json', '.'),
]

for extra_file in ['config_app.json', 'config_app.example.json', 'app_icon.ico', 'app_icon.png']:
    if os.path.exists(extra_file):
        datas.append((extra_file, '.'))
binaries = []
hiddenimports = [
    'dotenv',
    'requests',
    'urllib3',
    'trio',
    'trio_websocket',
    'src',
    'src.ui',
    'src.core',
    'src.ai',
    'src.utils'
]

for pkg in ['selenium', 'selenium_stealth', 'webdriver_manager', 'pypdf', 'pypdfium2', 'PIL']:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ['main.py'],
    pathex=['.', 'src'],
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
    a.binaries,
    a.datas,
    [],
    name='SII_GestorFacturas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/app_icon.ico'],
)
