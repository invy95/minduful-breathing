# -*- mode: python ; coding: utf-8 -*-
# 呼吸泡泡·激活码版（打包 mindful_breathing.pyw）

from PyInstaller.utils.hooks import collect_all

# 确保 supabase 及依赖完整打包（激活码校验必需）
supabase_datas, supabase_bins, supabase_hidden = collect_all('supabase')
httpx_datas, httpx_bins, httpx_hidden = collect_all('httpx')

a = Analysis(
    ['mindful_breathing.pyw'],
    pathex=[],
    binaries=supabase_bins + httpx_bins,
    datas=[('ambient.wav', '.'), ('app_icon.ico', '.'), ('app_icon.png', '.'), ('login_logo.png', '.'), ('flower.png', '.'), ('icon_lotus_cyan.png', '.'), ('icon_lotus_red.png', '.'), ('icon_lotus_orange.png', '.'), ('icon_lotus_yellow.png', '.'), ('icon_lotus_green.png', '.'), ('icon_lotus_blue.png', '.'), ('icon_lotus_purple.png', '.'), ('icon_ripple_cyan.png', '.'), ('icon_ripple_red.png', '.'), ('icon_ripple_orange.png', '.'), ('icon_ripple_yellow.png', '.'), ('icon_ripple_green.png', '.'), ('icon_ripple_blue.png', '.'), ('icon_ripple_purple.png', '.'), ('icon_seed_of_life_cyan.png', '.'), ('icon_seed_of_life_red.png', '.'), ('icon_seed_of_life_orange.png', '.'), ('icon_seed_of_life_yellow.png', '.'), ('icon_seed_of_life_green.png', '.'), ('icon_seed_of_life_blue.png', '.'), ('icon_seed_of_life_purple.png', '.'), ('iri_lotus.png', '.'), ('iri_ripple.png', '.'), ('iri_seed_of_life.png', '.')] + supabase_datas + httpx_datas,
    hiddenimports=['activation_client', 'supabase', 'dotenv'] + supabase_hidden + httpx_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['utf8_hook.py'],
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
    name='呼吸泡泡',  # exe 仍为中文名
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
    icon='app_icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MindfulBreathing',  # 英文名避免占用锁，build_release 会处理
)
