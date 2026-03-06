# -*- coding: utf-8 -*-
"""生成 app_icon.ico 和 app_icon.png，用作 exe/托盘/快捷方式图标。
【请勿修改图标】优先使用 app_icon_source.png（用户指定的圆+莲花+心形图），
使「右键→发送到桌面快捷方式」得到的图标正确。不要替换或修改 app_icon_source.png。"""
import os
from PIL import Image

base = os.path.dirname(os.path.abspath(__file__))
dst_ico = os.path.join(base, 'app_icon.ico')
dst_png = os.path.join(base, 'app_icon.png')

# 【勿改】优先使用用户指定的图标源（圆内莲花+心形）
src = os.path.join(base, 'app_icon_source.png')
if not os.path.exists(src):
    src = os.path.join(base, 'login_logo.png')
if not os.path.exists(src):
    src = os.path.join(base, 'icon_lotus_cyan.png')
if not os.path.exists(src):
    print('未找到 app_icon_source.png / login_logo.png / icon_lotus_cyan.png')
    exit(1)

img = Image.open(src).convert('RGBA')
w, h = img.size
side = min(w, h)
left = (w - side) // 2
top = (h - side) // 2
img = img.crop((left, top, left + side, top + side))

sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img256 = img.resize((256, 256), Image.LANCZOS)
img256.save(dst_ico, format='ICO', sizes=sizes)
print(f'已生成: {dst_ico}')

img256.save(dst_png, format='PNG')
print(f'已生成: {dst_png}')
