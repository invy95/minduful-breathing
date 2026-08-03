# -*- coding: utf-8 -*-
"""
打包呼吸泡泡 Windows 本地激活码版，并生成可分发 zip。
更新：2026-08-03：供 GitHub Actions 发布完整 Windows 包（含 _internal）。
"""
import os
import shutil
import subprocess
import sys
import zipfile


def _zip_dir(src_dir: str, zip_path: str) -> None:
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(src_dir):
            for name in files:
                full = os.path.join(root, name)
                arc = os.path.relpath(full, os.path.dirname(src_dir))
                zf.write(full, arc)


def main():
    # Windows CI 默认 cp1252，避免中文 print 导致打包中断
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    base = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base)

    for d in ['build', 'dist']:
        p = os.path.join(base, d)
        if os.path.exists(p):
            try:
                shutil.rmtree(p)
            except PermissionError:
                print(f'skip clean {d}')

    # 仓库已有 app_icon.ico，图标更新失败不影响打包
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        r_icon = subprocess.run(
            [sys.executable, 'update_app_icon.py'],
            cwd=base,
            env=env,
            check=False,
        )
        if r_icon.returncode == 0:
            print('updated app_icon')
        else:
            print('skip update_app_icon (non-zero exit)')
    except Exception as e:
        print(f'skip update_app_icon: {e}')

    r = subprocess.run(
        [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', 'BreathingBallLocal.spec'],
        cwd=base,
    )
    if r.returncode != 0:
        print('PyInstaller failed')
        sys.exit(1)

    dist_dir = os.path.join(base, 'dist', '呼吸泡泡')
    if not os.path.isdir(dist_dir):
        print(f'missing dist dir: {dist_dir}')
        sys.exit(1)

    usage_content = (
        '呼吸泡泡 - 使用说明\n'
        '====================\n'
        '\n'
        '【温馨提示】请勿单独将 呼吸泡泡.exe 移动到桌面或其他位置运行！\n'
        '本程序需要与 _internal 文件夹保持在一起才能正常启动。\n'
        '请解压后进入「呼吸泡泡」文件夹，双击 呼吸泡泡.exe。\n'
        '首次启动需输入激活码（需联网）。\n'
    )
    with open(os.path.join(dist_dir, '使用说明.txt'), 'w', encoding='utf-8') as f:
        f.write(usage_content)
    print('已写入 使用说明.txt')

    env_dist = os.path.join(base, '.env.dist')
    if os.path.exists(env_dist):
        shutil.copy(env_dist, os.path.join(dist_dir, '.env'))
        print('已复制 .env（来自 .env.dist）')

    zip_path = os.path.join(base, 'dist', 'BreathingBall-Windows.zip')
    if os.path.exists(zip_path):
        os.remove(zip_path)
    _zip_dir(dist_dir, zip_path)
    print(f'created {zip_path}')

    # 完整性检查：缺这些文件会导致 Failed to start embedded python interpreter
    internal = os.path.join(dist_dir, '_internal')
    if not os.path.isdir(internal):
        print('打包完整性检查失败: 缺少 _internal 目录')
        sys.exit(1)
    names = set()
    pyd_count = 0
    for _r, _d, files in os.walk(internal):
        for f in files:
            names.add(f.lower())
            if f.lower().endswith('.pyd'):
                pyd_count += 1
    has_python3 = 'python3.dll' in names
    has_python_ver = any(n.startswith('python3') and n.endswith('.dll') and n != 'python3.dll' for n in names)
    has_base = 'base_library.zip' in names
    if not (has_python3 and has_python_ver and has_base and pyd_count > 0):
        print(
            '打包完整性检查失败: '
            f'python3.dll={has_python3}, python3x.dll={has_python_ver}, '
            f'base_library.zip={has_base}, pyd_count={pyd_count}'
        )
        sys.exit(1)
    print(f'完整性检查通过: pyd_count={pyd_count}')

    print('\n打包完成（Windows 本地激活码版）')


if __name__ == '__main__':
    main()
