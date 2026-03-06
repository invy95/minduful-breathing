"""生成应用图标 ICO"""
from PIL import Image, ImageDraw
import math

def draw_ellipse_rotated(target, size, cx, cy, offset_y, rx, ry, angle_deg, fill_rgba):
    layer = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - rx, cy - offset_y - ry, cx + rx, cy - offset_y + ry], fill=fill_rgba)
    if angle_deg != 0:
        layer = layer.rotate(-angle_deg, center=(cx, cy), resample=Image.BICUBIC)
    target.alpha_composite(layer)

def radial_gradient(img, cx, cy, r, center_rgba, edge_rgba):
    d = ImageDraw.Draw(img)
    for i in range(r, 0, -1):
        f = i / r
        c = tuple(int(center_rgba[j] * (1 - f) + edge_rgba[j] * f) for j in range(3))
        a = int(center_rgba[3] * (1 - f) + edge_rgba[3] * f)
        d.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(*c, a))

SIZE = 512
CX, CY = SIZE // 2, SIZE // 2

# 背景圆：深青渐变
icon = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(icon)

# 圆形背景
bg_r = 240
radial_gradient(icon, CX, CY, bg_r, (40, 100, 95, 255), (25, 65, 60, 255))

# 边缘光圈
draw = ImageDraw.Draw(icon)
draw.ellipse([CX - bg_r, CY - bg_r, CX + bg_r, CY + bg_r],
             outline=(109, 179, 168, 100), width=3)

# 莲花（白色系，透明感）
hues = [
    (200, 240, 235), (190, 230, 240), (210, 225, 240),
    (200, 235, 238), (215, 240, 230), (205, 242, 228),
    (200, 240, 235),
]

def hue_at(angle):
    angle = angle % 360
    pos = angle / 360 * (len(hues) - 1)
    idx = int(pos)
    frac = pos - idx
    c1, c2 = hues[idx], hues[min(idx + 1, len(hues) - 1)]
    return tuple(int(c1[j] + (c2[j] - c1[j]) * frac) for j in range(3))

# 莲花花瓣放大至占满图标（原 105,70,130 → 0,160,250）
for i in range(12):
    angle = i * 30
    color = hue_at(angle)
    draw_ellipse_rotated(icon, SIZE, CX, CY, 0, 160, 250, angle, (*color, 140))

# 中心光点放大
radial_gradient(icon, CX, CY, 100, (255, 255, 250, 200), (200, 240, 235, 0))

# 保存多尺寸 ICO
sizes = [16, 32, 48, 64, 128, 256]
imgs = []
for s in sizes:
    imgs.append(icon.resize((s, s), Image.LANCZOS))

icon.save('C:/Users/invy11/mindful-breathing/app_icon.ico', format='ICO',
          sizes=[(s, s) for s in sizes])

# 也存一个 PNG 版本
icon.save('C:/Users/invy11/mindful-breathing/app_icon.png')
print('done')
