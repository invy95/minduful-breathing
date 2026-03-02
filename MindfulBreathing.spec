# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['mindful_breathing.pyw'],
    pathex=[],
    binaries=[],
    datas=[('ambient.wav', '.'), ('app_icon.ico', '.'), ('flower.png', '.'), ('icon_lotus_cyan.png', '.'), ('icon_lotus_red.png', '.'), ('icon_lotus_orange.png', '.'), ('icon_lotus_yellow.png', '.'), ('icon_lotus_green.png', '.'), ('icon_lotus_blue.png', '.'), ('icon_lotus_purple.png', '.'), ('icon_ripple_cyan.png', '.'), ('icon_ripple_red.png', '.'), ('icon_ripple_orange.png', '.'), ('icon_ripple_yellow.png', '.'), ('icon_ripple_green.png', '.'), ('icon_ripple_blue.png', '.'), ('icon_ripple_purple.png', '.'), ('icon_seed_of_life_cyan.png', '.'), ('icon_seed_of_life_red.png', '.'), ('icon_seed_of_life_orange.png', '.'), ('icon_seed_of_life_yellow.png', '.'), ('icon_seed_of_life_green.png', '.'), ('icon_seed_of_life_blue.png', '.'), ('icon_seed_of_life_purple.png', '.'), ('iri_lotus.png', '.'), ('iri_ripple.png', '.'), ('iri_seed_of_life.png', '.')],
    hiddenimports=[],
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
    name='觉察呼吸',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\invy11\\mindful-breathing\\app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='觉察呼吸',
)
