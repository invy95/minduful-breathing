from PIL import Image, ImageDraw
import math

SIZE = 800
CX, CY = SIZE // 2, SIZE // 2

base = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))

def draw_ellipse_rotated(target, cx, cy, offset_y, rx, ry, angle_deg, fill_rgba):
    layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse([cx - rx, cy - offset_y - ry, cx + rx, cy - offset_y + ry], fill=fill_rgba)
    if angle_deg != 0:
        layer = layer.rotate(-angle_deg, center=(cx, cy), resample=Image.BICUBIC)
    target.alpha_composite(layer)

# 外层 12 片: rgba(209,236,228,0.45) → alpha=115
outer_color = (209, 236, 228, 115)
for i in range(12):
    draw_ellipse_rotated(base, CX, CY, 180, 120, 220, i * 30, outer_color)

# 内层 8 片: rgba(232,250,244,0.55) → alpha=140
inner_color = (232, 250, 244, 140)
for i in range(8):
    draw_ellipse_rotated(base, CX, CY, 120, 80, 150, i * 45, inner_color)

# 中心: rgba(245,255,250,0.75) → alpha=191
draw = ImageDraw.Draw(base)
draw.ellipse([CX - 130, CY - 130, CX + 130, CY + 130], fill=(245, 255, 250, 191))

base.save('C:/Users/invy11/mindful-breathing/flower.png')
print('done')
