# -*- coding: utf-8 -*-
"""打包呼吸泡泡 Mac 版（需在 Mac 上运行）"""
import os
import shutil
import subprocess
import sys

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base)
    dist_dir = os.path.join(base, 'dist', '呼吸泡泡')

    for d in ['build', 'dist']:
        p = os.path.join(base, d)
        if os.path.exists(p):
            try:
                shutil.rmtree(p)
            except PermissionError:
                print(f'跳过清理 {d}，继续打包...')

    # 打包前生成 app_icon.png
    try:
        subprocess.run([sys.executable, 'update_app_icon.py'], cwd=base, check=True)
        print('已更新 app_icon')
    except Exception as e:
        print(f'update_app_icon 跳过: {e}')

    # --clean 强制完整重建
    r = subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                        'MindfulBreathing_mac.spec'], cwd=base)
    if r.returncode != 0:
        print('PyInstaller 打包失败')
        sys.exit(1)

    # 写入使用说明（固定内容，保证每次打包一致）
    usage_content = (
        '呼吸泡泡 - 使用说明\n'
        '====================\n'
        '\n'
        '【温馨提示】请勿单独将「呼吸泡泡」可执行文件移动到其他位置！\n'
        '本程序需要与同目录下的所有文件保持在一起才能正常启动。\n'
        '\n'
        '首次运行：右键点击「呼吸泡泡」→ 打开（macOS 安全提示）。\n'
    )
    with open(os.path.join(dist_dir, '使用说明.txt'), 'w', encoding='utf-8') as f:
        f.write(usage_content)
    print('已写入 使用说明.txt')

    # 复制 .env
    env_dist = os.path.join(base, '.env.dist')
    if os.path.exists(env_dist):
        shutil.copy(env_dist, os.path.join(dist_dir, '.env'))
        print('已复制 .env（来自 .env.dist）')

    # 设置可执行权限
    exe_path = os.path.join(dist_dir, '呼吸泡泡')
    if os.path.exists(exe_path):
        os.chmod(exe_path, 0o755)

    # 打包为 zip
    zip_base = os.path.join(base, 'dist', '呼吸泡泡-mac')
    shutil.make_archive(zip_base, 'zip', os.path.join(base, 'dist'), '呼吸泡泡')
    print(f'\nMac 版打包完成: {zip_base}.zip')
    print('将 zip 发给 Mac 用户，解压后双击「呼吸泡泡」即可运行。')

if __name__ == '__main__':
    main()
