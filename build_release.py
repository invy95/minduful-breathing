# -*- coding: utf-8 -*-
"""打包呼吸泡泡 Windows 版，并生成可分发的 zip"""
import os
import shutil
import subprocess
import sys

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base)
    dist_dir = os.path.join(base, 'dist', 'MindfulBreathing')

    # 1. 清理旧构建（若被占用则跳过，PyInstaller 会覆盖）
    for d in ['build', 'dist']:
        p = os.path.join(base, d)
        if os.path.exists(p):
            try:
                shutil.rmtree(p)
            except PermissionError:
                print(f'跳过清理 {d}（可能有程序占用），继续打包...')

    # 打包前生成 app_icon.ico / app_icon.png（与 login_logo 一致）
    try:
        subprocess.run([sys.executable, 'update_app_icon.py'], cwd=base, check=True)
        print('已更新 app_icon')
    except Exception as e:
        print(f'update_app_icon 跳过: {e}')

    # 2. PyInstaller 打包（--clean 强制完整重建，避免缓存导致莲花旋转方向错误）
    r = subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', 'MindfulBreathing.spec'], cwd=base)
    if r.returncode != 0:
        print('PyInstaller 打包失败')
        sys.exit(1)

    # 3. 写入使用说明（固定内容，保证每次打包一致）
    usage_content = (
        '呼吸泡泡 - 使用说明\n'
        '====================\n'
        '\n'
        '【温馨提示】请勿单独将 呼吸泡泡.exe 移动到桌面或其他位置运行！\n'
        '本程序需要与 _internal 文件夹保持在一起才能正常启动。\n'
        '若单独移动 exe，会出现「Failed to load Python DLL」错误。\n'
    )
    with open(os.path.join(dist_dir, '使用说明.txt'), 'w', encoding='utf-8') as f:
        f.write(usage_content)
    print('已写入 使用说明.txt')

    # 复制 .env.dist 到发布包（仅含 URL+ANON_KEY，不含 SERVICE_ROLE_KEY）
    env_dist = os.path.join(base, '.env.dist')
    if os.path.exists(env_dist):
        shutil.copy(env_dist, os.path.join(dist_dir, '.env'))
        print('已复制 .env（来自 .env.dist）')

    # 4. 复制为 呼吸泡泡 目录便于用户使用
    final_dir = os.path.join(base, 'dist', '呼吸泡泡')
    if os.path.exists(final_dir):
        try:
            shutil.rmtree(final_dir)
        except PermissionError:
            pass
    if os.path.exists(dist_dir):
        try:
            shutil.copytree(dist_dir, final_dir)
            print('已生成 呼吸泡泡 目录')
        except Exception as e:
            print(f'复制到 呼吸泡泡 失败: {e}')
    if os.path.exists(env_dist) and os.path.exists(final_dir):
        try:
            shutil.copy(env_dist, os.path.join(final_dir, '.env'))
        except Exception:
            pass

    print('\n打包完成（Windows 版）')
    print('首次运行 exe 时会询问是否创建桌面快捷方式。')
    print('勿单独移动 exe 到桌面。详见 使用说明.txt')

if __name__ == '__main__':
    main()
