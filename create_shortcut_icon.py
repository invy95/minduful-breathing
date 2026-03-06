# -*- coding: utf-8 -*-
"""用用户提供的图生成所有图标：app_icon(EXE+托盘) 和 shortcut_icon(快捷方式)"""
import os
from PIL import Image

base = os.path.dirname(os.path.abspath(__file__))
src = r'C:\Users\invy11\.cursor\projects\c-Users-invy11\assets\c__Users_invy11_AppData_Roaming_Cursor_User_workspaceStorage_3fb83db81dd5cdd9fdfdf07adf7d55ce_images_image-6181f381-679d-480e-9850-e74cb4955d71.png'

if not os.path.exists(src):
    print('未找到源图')
    exit(1)

img = Image.open(src).convert('RGBA')
w, h = img.size
side = min(w, h)
left = (w - side) // 2
top = (h - side) // 2
img = img.crop((left, top, left + side, top + side))

sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img256 = img.resize((256, 256), Image.LANCZOS)

# app_icon：EXE 和托盘
img256.save(os.path.join(base, 'app_icon.ico'), format='ICO', sizes=sizes)
img.save(os.path.join(base, 'app_icon.png'))
print('app_icon.ico, app_icon.png')

# shortcut_icon：桌面快捷方式
img256.save(os.path.join(base, 'shortcut_icon.ico'), format='ICO', sizes=sizes)
print('shortcut_icon.ico')
