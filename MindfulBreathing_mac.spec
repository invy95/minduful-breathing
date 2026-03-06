# -*- mode: python ; coding: utf-8 -*-
# 呼吸泡泡 Mac 版（需在 Mac 上执行 PyInstaller）

from PyInstaller.utils.hooks import collect_all

supabase_datas, supabase_bins, supabase_hidden = collect_all('supabase')
httpx_datas, httpx_bins, httpx_hidden = collect_all('httpx')

datas = [
    ('ambient.wav', '.'), ('app_icon.png', '.'), ('login_logo.png', '.'),
    ('flower.png', '.'),
    ('icon_lotus_cyan.png', '.'), ('icon_lotus_red.png', '.'),
    ('icon_lotus_orange.png', '.'), ('icon_lotus_yellow.png', '.'),
    ('icon_lotus_green.png', '.'), ('icon_lotus_blue.png', '.'),
    ('icon_lotus_purple.png', '.'),
    ('icon_ripple_cyan.png', '.'), ('icon_ripple_red.png', '.'),
    ('icon_ripple_orange.png', '.'), ('icon_ripple_yellow.png', '.'),
    ('icon_ripple_green.png', '.'), ('icon_ripple_blue.png', '.'),
    ('icon_ripple_purple.png', '.'),
    ('icon_seed_of_life_cyan.png', '.'), ('icon_seed_of_life_red.png', '.'),
    ('icon_seed_of_life_orange.png', '.'), ('icon_seed_of_life_yellow.png', '.'),
    ('icon_seed_of_life_green.png', '.'), ('icon_seed_of_life_blue.png', '.'),
    ('icon_seed_of_life_purple.png', '.'),
    ('iri_lotus.png', '.'), ('iri_ripple.png', '.'), ('iri_seed_of_life.png', '.'),
] + supabase_datas + httpx_datas

a = Analysis(
    ['mindful_breathing.pyw'],
    pathex=[],
    binaries=supabase_bins + httpx_bins,
    datas=datas,
    hiddenimports=['activation_client', 'supabase', 'dotenv'] + supabase_hidden + httpx_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['utf8_hook.py'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='呼吸泡泡',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon='app_icon.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='呼吸泡泡',
)
