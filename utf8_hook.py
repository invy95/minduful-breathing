# -*- coding: utf-8 -*-
"""PyInstaller 启动时尽早设置 UTF-8，减少 Windows 下中文乱码"""
import sys
import os

if sys.platform == 'win32':
    os.environ['PYTHONUTF8'] = '1'
