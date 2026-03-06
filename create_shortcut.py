# -*- coding: utf-8 -*-
"""创建桌面快捷方式（正确处理中文，避免乱码）"""
import os
import sys

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(base, 'dist')
    
    # 查找 exe
    exe_path = None
    for root, _, files in os.walk(dist_dir):
        for f in files:
            if f.endswith('.exe') and not f.startswith('_'):
                exe_path = os.path.join(root, f)
                break
        if exe_path:
            break
    
    if not exe_path or not os.path.exists(exe_path):
        print('未找到 exe')
        return 1
    
    ico_path = os.path.join(os.path.dirname(exe_path), '_internal', 'shortcut_icon.ico')
    if not os.path.exists(ico_path):
        ico_path = os.path.join(base, 'shortcut_icon.ico')
    
    # 桌面路径
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    if not os.path.exists(desktop):
        desktop = os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop')
    
    shortcut_path = os.path.join(desktop, '呼吸泡泡.lnk')
    
    try:
        import win32com.client
        shell = win32com.client.Dispatch('WScript.Shell')
        shortcut = shell.CreateShortcut(shortcut_path)
        shortcut.TargetPath = exe_path
        shortcut.WorkingDirectory = os.path.dirname(exe_path)
        shortcut.IconLocation = ico_path + ',0'
        shortcut.Description = '呼吸泡泡'
        shortcut.Save()
        print('已创建:', shortcut_path)
        return 0
    except ImportError:
        try:
            import subprocess
            ps = os.path.join(base, 'create_shortcut.ps1')
            if os.path.exists(ps):
                subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', ps], cwd=base)
            return 0
        except Exception:
            pass
        print('请安装: pip install pywin32')
        return 1
    except Exception as e:
        print('创建失败:', e)
        return 1

if __name__ == '__main__':
    sys.exit(main())
