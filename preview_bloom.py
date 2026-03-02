from PIL import Image, ImageDraw, ImageFont
import math, os

SIZE = 500
HALF = SIZE // 2
BASE = (109, 179, 168)

def light(base, amt):
    return tuple(int(c + (255 - c) * amt) for c in base)

def draw_circle(target, cx, cy, r, fill_rgba, outline_rgba):
    layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1], fill=fill_rgba)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=outline_rgba, width=2)
    target.alpha_composite(layer)

def render_bloom(r, offset_ratio, n_petals, label):
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    c = light(BASE, 0.6)
    fill = (*c, 35)
    outline = (*light(BASE, 0.3), 75)
    offset = r * offset_ratio

    draw_circle(img, HALF, HALF, r, fill, outline)
    for i in range(n_petals):
        angle = math.radians(i * 360 / n_petals + 30)
        px = HALF + int(offset * math.cos(angle))
        py = HALF + int(offset * math.sin(angle))
        draw_circle(img, px, py, r, fill, outline)

    d = ImageDraw.Draw(img)
    fonts_dir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    try:
        font = ImageFont.truetype(os.path.join(fonts_dir, 'msyh.ttc'), 22)
    except:
        font = ImageFont.load_default()
    # 白字黑影标注
    tw = d.textlength(label, font=font)
    tx, ty = HALF - tw / 2, SIZE - 50
    d.text((tx + 1, ty + 1), label, fill=(0, 0, 0, 180), font=font)
    d.text((tx, ty), label, fill=(255, 255, 255, 240), font=font)
    return img

configs = [
    (140, 0.50, 6, 'A: 6瓣 紧密'),
    (130, 0.60, 6, 'B: 6瓣 适中'),
    (120, 0.50, 7, 'C: 7瓣 紧密'),
    (110, 0.55, 8, 'D: 8瓣 均匀'),
    (150, 0.45, 5, 'E: 5瓣 花苞'),
    (130, 0.65, 6, 'F: 6瓣 散开'),
]

# 用海蓝色渐变模拟壁纸背景
bg = Image.new('RGBA', (SIZE * 3, SIZE * 2), (255, 255, 255, 255))
d = ImageDraw.Draw(bg)
for y in range(SIZE * 2):
    frac = y / (SIZE * 2)
    r = int(50 + 30 * frac)
    g = int(190 + 40 * (1 - frac))
    b = int(210 + 30 * (1 - frac))
    d.line([(0, y), (SIZE * 3, y)], fill=(r, g, b))

for idx, cfg in enumerate(configs):
    img = render_bloom(*cfg)
    x = (idx % 3) * SIZE
    y = (idx // 3) * SIZE
    bg.alpha_composite(img, (x, y))

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'preview_bloom.png')
bg.save(out)
print(f'saved: {out}')
