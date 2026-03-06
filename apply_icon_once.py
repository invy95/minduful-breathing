# -*- coding: utf-8 -*-
"""一次性：用指定图片生成 app_icon.ico，放入 dist 并创建带该图标的快捷方式。"""
import os
import shutil
import subprocess
import sys
from PIL import Image

base = os.path.dirname(os.path.abspath(__file__))
# 用户提供的图标图（圆+莲花+心形，干净版）
src = r'C:\Users\invy11\.cursor\projects\c-Users-invy11\assets\c__Users_invy11_AppData_Roaming_Cursor_User_workspaceStorage_3fb83db81dd5cdd9fdfdf07adf7d55ce_images_image-48cb3652-7790-4ae9-b074-8d3dba607dd6.png'

if not os.path.exists(src):
    print(f'未找到源图: {src}')
    sys.exit(1)

img = Image.open(src).convert('RGBA')
w, h = img.size
side = min(w, h)
left = (w - side) // 2
top = (h - side) // 2
img = img.crop((left, top, left + side, top + side))
sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img256 = img.resize((256, 256), Image.LANCZOS)
ico_path = os.path.join(base, 'app_icon.ico')
img256.save(ico_path, format='ICO', sizes=sizes)
print(f'已生成: {ico_path}')

# 放入 dist\MindfulBreathing
for folder in ['MindfulBreathing', '呼吸泡泡']:
    target = os.path.join(base, 'dist', folder)
    if not os.path.isdir(target):
        continue
    ico_dst = os.path.join(target, 'app_icon.ico')
    shutil.copy2(ico_path, ico_dst)
    exe_path = os.path.abspath(os.path.join(target, '呼吸泡泡.exe'))
    lnk_path = os.path.abspath(os.path.join(target, '呼吸泡泡.lnk'))
    if not os.path.exists(exe_path):
        continue
    env = dict(os.environ)
    env['BB_EXE'] = exe_path
    env['BB_LNK'] = lnk_path
    env['BB_ICO'] = os.path.abspath(ico_dst)
    env['BB_DIR'] = os.path.abspath(target)
    ps = (
        '$ws = New-Object -ComObject WScript.Shell; '
        '$s = $ws.CreateShortcut($env:BB_LNK); '
        '$s.TargetPath = $env:BB_EXE; '
        '$s.WorkingDirectory = $env:BB_DIR; '
        '$s.IconLocation = $env:BB_ICO + ",0"; '
        '$s.Description = "呼吸泡泡"; '
        '$s.Save()'
    )
    import base64
    ps_b64 = base64.b64encode(ps.encode('utf-16le')).decode('ascii')
    r = subprocess.run(['powershell', '-NoProfile', '-EncodedCommand', ps_b64], env=env, capture_output=True)
    if r.returncode == 0:
        print(f'已更新 {folder}: app_icon.ico + 呼吸泡泡.lnk')
    else:
        print(f'{folder} 快捷方式创建失败')

print('完成。将 呼吸泡泡.lnk 拖到桌面即可，图标已为你提供的图。')
