from PIL import Image, ImageDraw, ImageFilter
import math

SIZE = 800
CX, CY = SIZE // 2, SIZE // 2

COLORS = {
    'red':    (200, 100, 100),
    'orange': (210, 155, 90),
    'yellow': (200, 190, 100),
    'green':  (100, 180, 120),
    'blue':   (100, 140, 200),
    'cyan':   (109, 179, 168),
    'purple': (150, 120, 190),
}

def col(base, alpha):
    return (*base, alpha)

def draw_ellipse_rotated(target, cx, cy, offset_y, rx, ry, angle_deg, fill_rgba):
    layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse([cx - rx, cy - offset_y - ry, cx + rx, cy - offset_y + ry], fill=fill_rgba)
    if angle_deg != 0:
        layer = layer.rotate(-angle_deg, center=(cx, cy), resample=Image.BICUBIC)
    target.alpha_composite(layer)

def draw_circle_alpha(target, cx, cy, r, fill_rgba):
    layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill_rgba)
    target.alpha_composite(layer)

def radial_gradient_circle(img, cx, cy, r, center_rgba, edge_rgba):
    draw = ImageDraw.Draw(img)
    for i in range(r, 0, -1):
        frac = i / r
        c = tuple(int(center_rgba[j] * (1 - frac) + edge_rgba[j] * frac) for j in range(3))
        a = int(center_rgba[3] * (1 - frac) + edge_rgba[3] * frac)
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(*c, a))

def light(base, amount=0.6):
    return tuple(int(c + (255 - c) * amount) for c in base)

# ─── 莲花 ───
def render_lotus(base):
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    lt = light(base, 0.35)
    for i in range(12):
        draw_ellipse_rotated(img, CX, CY, 180, 120, 220, i * 30, col(lt, 135))
    return img

# ─── 涟漪 ───
def render_ripple(base):
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i, (r, a) in enumerate([(320,55),(270,75),(220,95),(170,115),(120,135),(80,160)]):
        c = light(base, 0.1 + i * 0.08)
        draw.ellipse([CX - r, CY - r, CX + r, CY + r], fill=col(c, a))
    ct = light(base, 0.8)
    radial_gradient_circle(img, CX, CY, 60, col(ct, 210), col(ct, 0))
    return img

# ─── 生命之花 ───
def render_seed(base):
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    lt = light(base, 0.55)
    lt2 = light(base, 0.7)
    ct = light(base, 0.85)
    r = 170
    # 6 个圆围成一圈（无中心光晕）
    for i in range(6):
        angle = math.radians(i * 60)
        px = CX + int(r * 0.8 * math.cos(angle))
        py = CY + int(r * 0.8 * math.sin(angle))
        draw_circle_alpha(img, px, py, r, col(lt, 110))
    return img

# ─── 莲花Pro: 多层渐变花瓣 + 暖光中心 ───
def render_lotus_pro(base):
    from PIL import ImageFilter
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    # 3层花瓣，从外到内逐渐亮
    for layer_i, (n, off_y, rx, ry, lighten, alpha) in enumerate([
        (12, 200, 130, 240, 0.45, 80),
        (12, 170, 115, 200, 0.55, 95),
        (8,  130, 90,  160, 0.65, 110),
        (8,  90,  65,  120, 0.75, 130),
    ]):
        c = light(base, lighten)
        offset_angle = 15 if layer_i % 2 else 0
        for i in range(n):
            draw_ellipse_rotated(img, CX, CY, off_y, rx, ry, i * (360 // n) + offset_angle, col(c, alpha))
    # 暖光中心渐变
    warm = light(base, 0.92)
    radial_gradient_circle(img, CX, CY, 120, (255, 255, 245, 200), col(warm, 0))
    img = img.filter(ImageFilter.GaussianBlur(10))
    return img

# ─── 涟漪Pro: 更多圈 + 径向渐变 ───
def render_ripple_pro(base):
    from PIL import ImageFilter
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    rings = [(350,30),(310,40),(270,55),(230,70),(190,90),(155,110),(120,130),(90,155),(60,175)]
    for i, (r, a) in enumerate(rings):
        c = light(base, 0.1 + i * 0.08)
        draw_circle_alpha(img, CX, CY, r, col(c, a))
    # 中心强光
    radial_gradient_circle(img, CX, CY, 80, (255, 255, 248, 220), col(light(base, 0.85), 0))
    img = img.filter(ImageFilter.GaussianBlur(8))
    return img

# ─── 生命之花Pro: 更精细 + 外环 + 柔光 ───
def render_seed_pro(base):
    from PIL import ImageFilter
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    lt = light(base, 0.5)
    lt2 = light(base, 0.6)
    r = 170
    # 中心圆
    draw_circle_alpha(img, CX, CY, r, col(lt, 55))
    # 第一环 6圆
    for i in range(6):
        angle = math.radians(i * 60)
        px = CX + int(r * 0.85 * math.cos(angle))
        py = CY + int(r * 0.85 * math.sin(angle))
        draw_circle_alpha(img, px, py, r, col(lt, 55))
    # 第二环 12圆（更小、更淡）
    for i in range(12):
        angle = math.radians(i * 30)
        px = CX + int(r * 1.5 * math.cos(angle))
        py = CY + int(r * 1.5 * math.sin(angle))
        draw_circle_alpha(img, px, py, int(r * 0.7), col(lt2, 40))
    # 第三环 18圆（最外、最淡）
    for i in range(18):
        angle = math.radians(i * 20 + 10)
        px = CX + int(r * 2.0 * math.cos(angle))
        py = CY + int(r * 2.0 * math.sin(angle))
        draw_circle_alpha(img, px, py, int(r * 0.45), col(lt2, 25))
    # 中心暖光
    radial_gradient_circle(img, CX, CY, 90, (255, 255, 248, 200), col(light(base, 0.9), 0))
    img = img.filter(ImageFilter.GaussianBlur(8))
    return img


# ─── 生命之花·光（参考图2：6圆 + 中心光晕） ───
def render_seed_glow(base):
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    lt = light(base, 0.55)
    r = 170
    for i in range(6):
        angle = math.radians(i * 60)
        px = CX + int(r * 0.8 * math.cos(angle))
        py = CY + int(r * 0.8 * math.sin(angle))
        draw_circle_alpha(img, px, py, r, col(lt, 55))
    radial_gradient_circle(img, CX, CY, 55, (255, 255, 248, 150), (255, 255, 250, 0))
    return img


ICONS = {
    'lotus': render_lotus,
    'ripple': render_ripple,
    'seed_of_life': render_seed,
    'seed_glow': render_seed_glow,
}

for color_name, base in COLORS.items():
    for icon_name, fn in ICONS.items():
        img = fn(base)
        img.save(f'C:/Users/invy11/mindful-breathing/icon_{icon_name}_{color_name}.png')
        print(f'  {icon_name}_{color_name}')

print('done')
