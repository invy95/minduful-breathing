# -*- coding: utf-8 -*-
"""复制快捷方式到桌面并运行"""
import os
import shutil
import subprocess

base = os.path.dirname(os.path.abspath(__file__))
dist_dir = os.path.join(base, 'dist', '呼吸泡泡')
lnk_src = os.path.join(dist_dir, '呼吸泡泡.lnk')
exe_path = os.path.join(dist_dir, '呼吸泡泡.exe')

# 可能的桌面路径
desktops = [
    os.path.join(os.path.expanduser('~'), 'Desktop'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'OneDrive', 'Desktop'),
    r'D:\Personal\Desktop',
]

if not os.path.exists(lnk_src):
    print('未找到快捷方式，请先运行 build_release.py 打包')
    if os.path.exists(exe_path):
        print('直接启动 exe...')
        subprocess.Popen([exe_path], cwd=dist_dir)
    exit(1)

copied = []
for desktop in desktops:
    if os.path.isdir(desktop):
        lnk_dst = os.path.join(desktop, '呼吸泡泡.lnk')
        try:
            shutil.copy2(lnk_src, lnk_dst)
            copied.append(lnk_dst)
            print('已复制到:', lnk_dst)
        except Exception as e:
            print('复制失败', desktop, e)

if copied:
    subprocess.Popen(['cmd', '/c', 'start', '', copied[0]], shell=True)
    print('已启动')
else:
    subprocess.Popen([exe_path], cwd=dist_dir)
    print('未找到桌面目录，已直接启动 exe')
