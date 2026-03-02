"""预渲染所有图案的幻彩版本"""
from PIL import Image, ImageDraw
import math

SIZE = 800
CX, CY = SIZE // 2, SIZE // 2

HUES = [
    (130, 210, 200), (120, 195, 215), (140, 185, 220),
    (130, 200, 205), (150, 215, 195), (140, 220, 185),
    (130, 210, 200),
]

def hue_at(angle):
    angle = angle % 360
    pos = angle / 360 * (len(HUES) - 1)
    idx = int(pos)
    frac = pos - idx
    c1, c2 = HUES[idx], HUES[min(idx + 1, len(HUES) - 1)]
    return tuple(int(c1[j] + (c2[j] - c1[j]) * frac) for j in range(3))

def light(color, amt=0.5):
    return tuple(int(c + (255 - c) * amt) for c in color)

def draw_ellipse_rotated(target, cx, cy, offset_y, rx, ry, angle_deg, fill_rgba):
    layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - rx, cy - offset_y - ry, cx + rx, cy - offset_y + ry], fill=fill_rgba)
    if angle_deg != 0:
        layer = layer.rotate(-angle_deg, center=(cx, cy), resample=Image.BICUBIC)
    target.alpha_composite(layer)

def draw_circle_alpha(target, cx, cy, r, fill_rgba):
    layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill_rgba)
    target.alpha_composite(layer)

def radial_gradient_circle(img, cx, cy, r, center_rgba, edge_rgba):
    d = ImageDraw.Draw(img)
    for i in range(r, 0, -1):
        f = i / r
        c = tuple(int(center_rgba[j] * (1 - f) + edge_rgba[j] * f) for j in range(3))
        a = int(center_rgba[3] * (1 - f) + edge_rgba[3] * f)
        d.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(*c, a))

# ─── 莲花幻彩 ───
def render_lotus_iri():
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    for i in range(12):
        angle = i * 30
        color = light(hue_at(angle), 0.3)
        draw_ellipse_rotated(img, CX, CY, 180, 120, 220, angle, (*color, 135))
    return img

# ─── 涟漪幻彩 ───
def render_ripple_iri():
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rings = [(320,55),(270,75),(220,95),(170,115),(120,135),(80,160)]
    for i, (r, a) in enumerate(rings):
        color = light(hue_at(i * 60), 0.1 + i * 0.08)
        d.ellipse([CX - r, CY - r, CX + r, CY + r], fill=(*color, a))
    ct = light(hue_at(0), 0.8)
    radial_gradient_circle(img, CX, CY, 60, (*ct, 210), (*ct, 0))
    return img

# ─── 生命之花幻彩 ───
def render_seed_iri():
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    r = 170
    for i in range(6):
        angle_deg = i * 60
        color = light(hue_at(angle_deg), 0.55)
        angle_rad = math.radians(angle_deg)
        px = CX + int(r * 0.8 * math.cos(angle_rad))
        py = CY + int(r * 0.8 * math.sin(angle_rad))
        draw_circle_alpha(img, px, py, r, (*color, 110))
    return img

icons = {
    'lotus': render_lotus_iri,
    'ripple': render_ripple_iri,
    'seed_of_life': render_seed_iri,
}

for name, fn in icons.items():
    img = fn()
    img.save(f'C:/Users/invy11/mindful-breathing/iri_{name}.png')
    print(f'  iri_{name}')

print('done')
