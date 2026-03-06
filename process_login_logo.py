# -*- coding: utf-8 -*-
"""
将登录 Logo 去白底/浅灰底，保留完整圆形，输出透明 PNG 用于嵌入注册页。
用法：将新 Logo 保存为 new_logo.png 放于此脚本同目录，运行后生成 login_logo.png
      或：python process_login_logo.py -i "图片路径"
"""
from PIL import Image
import os
import sys

def remove_light_bg(img, threshold=240):
    """
    将白色/浅灰背景转为透明。
    threshold=240：r,g,b 都>=240 的像素变透明，可去除径向渐变的白底。
    """
    img = img.convert('RGBA')
    data = img.getdata()
    new_data = []
    for item in data:
        r, g, b, a = item
        if r >= threshold and g >= threshold and b >= threshold:
            new_data.append((r, g, b, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img

def main():
    base = os.path.dirname(os.path.abspath(__file__))

    if len(sys.argv) >= 3 and sys.argv[1] == '-i':
        src = sys.argv[2].strip().strip('"')
    else:
        src = os.path.join(base, 'new_logo.png')

    if not os.path.exists(src):
        print(f'未找到: {src}')
        print(f'请将新 Logo 另存为 new_logo.png 放到 {base}')
        print('或运行: python process_login_logo.py -i "图片路径"')
        return

    img = Image.open(src).convert('RGBA')

    # 去除白色/浅灰背景（含径向渐变）
    img = remove_light_bg(img, threshold=240)

    out = os.path.join(base, 'login_logo.png')
    img.save(out)
    print(f'已保存: {out}')

if __name__ == '__main__':
    main()
