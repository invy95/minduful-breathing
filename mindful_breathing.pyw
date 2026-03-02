import tkinter as tk
import ctypes
import ctypes.wintypes
import math
import random
import time
import threading
import struct
import sys
import os
import winreg
import winsound

from PIL import Image, ImageDraw, ImageFont, ImageFilter
try:
    import pystray
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

PROMPTS = [
    '你的肩膀是紧的还是松的？',
    '感受一下你的双脚接触地面',
    '不管此刻感受如何，允许它存在',
    '你有想切走的冲动吗？只是观察它',
    '说出你现在能看到的三样东西',
    '听听此刻周围有什么声音？',
    '你的下巴紧吗？试着松开',
    '感受一下你的手心，是温的还是凉的？',
    '此刻的你，需要什么？',
    '觉察一下此刻身体哪里最紧绷',
    '此刻的空气是凉还是暖？',
]

BREATHING_MODES = {
    'focus': {
        'name': '保持专注',
        'phases': [
            ('吸　气', 4.0),
            ('屏　息', 4.0),
            ('呼　气', 4.0),
            ('屏　息', 4.0),
        ],
        'guide': [
            ('用鼻\n吸气', 4.0),
            ('屏气', 4.0),
            ('用嘴\n呼气', 4.0),
            ('屏气', 4.0),
        ],
    },
    'calm': {
        'name': '恢复平静',
        'phases': [
            ('吸　气', 4.5),
            ('', 0.5),
            ('呼　气', 4.5),
            ('', 0.5),
        ],
        'guide': [
            ('用鼻\n吸气', 4.5),
            ('', 0.5),
            ('用嘴\n呼气', 4.5),
            ('', 0.5),
        ],
    },
    'rest': {
        'name': '深度休息',
        'phases': [
            ('吸　气', 4.0),
            ('屏　息', 7.0),
            ('呼　气', 7.5),
            ('', 0.5),
        ],
        'guide': [
            ('用鼻\n吸气', 4.0),
            ('屏气', 7.0),
            ('用嘴\n呼气', 7.5),
            ('', 0.5),
        ],
    },
}
GUIDE_CYCLES = 3

IDLE_THRESHOLD = 8
PRIMARY = (109, 179, 168)

COMPACT_W, COMPACT_H = 140, 180
IMMERSIVE_W, IMMERSIVE_H = 420, 560

# ─── Win32 分层窗口 API ───

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
ULW_ALPHA = 0x02
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
BI_RGB = 0


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ('BlendOp', ctypes.c_byte),
        ('BlendFlags', ctypes.c_byte),
        ('SourceConstantAlpha', ctypes.c_byte),
        ('AlphaFormat', ctypes.c_byte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', ctypes.c_uint), ('biWidth', ctypes.c_int),
        ('biHeight', ctypes.c_int), ('biPlanes', ctypes.c_ushort),
        ('biBitCount', ctypes.c_ushort), ('biCompression', ctypes.c_uint),
        ('biSizeImage', ctypes.c_uint), ('biXPelsPerMeter', ctypes.c_int),
        ('biYPelsPerMeter', ctypes.c_int), ('biClrUsed', ctypes.c_uint),
        ('biClrImportant', ctypes.c_uint),
    ]


def update_layered(hwnd, pil_rgba, pos=None):
    """用 RGBA 图片更新分层窗口，实现逐像素透明。
    pos: 可选 (x, y)，原子地同时移动窗口位置+更新尺寸+刷新像素。
    """
    w, h = pil_rgba.size

    hdcScreen = ctypes.windll.user32.GetDC(0)
    hdcMem = ctypes.windll.gdi32.CreateCompatibleDC(hdcScreen)

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = BI_RGB

    ppvBits = ctypes.c_void_p()
    hBitmap = ctypes.windll.gdi32.CreateDIBSection(
        hdcMem, ctypes.byref(bi), 0, ctypes.byref(ppvBits), None, 0
    )

    # BGRA + 预乘 alpha
    raw = pil_rgba.tobytes('raw', 'BGRA')
    buf = bytearray(raw)
    for i in range(0, len(buf), 4):
        a = buf[i + 3]
        if a < 255:
            buf[i] = buf[i] * a // 255
            buf[i + 1] = buf[i + 1] * a // 255
            buf[i + 2] = buf[i + 2] * a // 255
    ctypes.memmove(ppvBits, bytes(buf), len(buf))

    oldBmp = ctypes.windll.gdi32.SelectObject(hdcMem, hBitmap)

    ptSrc = ctypes.wintypes.POINT(0, 0)
    size = ctypes.wintypes.SIZE(w, h)
    blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)

    if pos is not None:
        ptDst = ctypes.wintypes.POINT(pos[0], pos[1])
        pptDst = ctypes.byref(ptDst)
    else:
        pptDst = None

    ctypes.windll.user32.UpdateLayeredWindow(
        hwnd, hdcScreen, pptDst, ctypes.byref(size),
        hdcMem, ctypes.byref(ptSrc), 0, ctypes.byref(blend), ULW_ALPHA
    )

    ctypes.windll.gdi32.SelectObject(hdcMem, oldBmp)
    ctypes.windll.gdi32.DeleteObject(hBitmap)
    ctypes.windll.gdi32.DeleteDC(hdcMem)
    ctypes.windll.user32.ReleaseDC(0, hdcScreen)


class IdleDetector:
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [
            ('cbSize', ctypes.wintypes.UINT),
            ('dwTime', ctypes.wintypes.DWORD),
        ]

    def __init__(self):
        self.lii = self.LASTINPUTINFO()
        self.lii.cbSize = ctypes.sizeof(self.LASTINPUTINFO)

    def get_idle_seconds(self):
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(self.lii))
        return (ctypes.windll.kernel32.GetTickCount() - self.lii.dwTime) / 1000.0


class BreathingBall:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('觉察呼吸')
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='black')

        self.immersive = False
        self.breathing = False
        self.minimized = False
        self.breath_start = 0.0
        self.current_prompt = random.choice(PROMPTS)
        self.guide_dismissed = False
        self._last_double_click = 0.0
        self._ripple_time = 0.0
        self._drag_moved = False
        self._breathing_mode = 'focus'
        self._sound_on = False
        self._sound_path = os.path.join(
            getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))), 'ambient.wav'
        )
        self._timer_duration = 0
        self._timer_start = 0.0

        self.win_w, self.win_h = COMPACT_W, COMPACT_H
        self.root.geometry(f'{self.win_w}x{self.win_h}')
        self._position_bottom_right()

        # 加载所有图案（3图案 × 7颜色）
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        self._icon_names = {
            'lotus': '莲花',
            'ripple': '涟漪',
            'seed_of_life': '生命之花',
        }
        self._color_names = {
            'red': '热情红', 'orange': '活力橙', 'yellow': '暖阳黄', 'green': '生机绿',
            'blue': '静谧蓝', 'cyan': '清澈青', 'purple': '梦幻紫',
        }
        self._color_hex = {
            'red': '#c86464', 'orange': '#d29b5a', 'yellow': '#c8be64',
            'green': '#64b478', 'blue': '#648cc8', 'cyan': '#6db3a8',
            'purple': '#9678be',
        }
        self._icons = {}
        for icon_key in self._icon_names:
            for color_key in self._color_names:
                p = os.path.join(base_dir, f'icon_{icon_key}_{color_key}.png')
                if os.path.exists(p):
                    self._icons[(icon_key, color_key)] = Image.open(p).convert('RGBA')
        self._current_icon = 'lotus'
        self._current_color = 'cyan'
        self._flower_base = self._icons.get(
            (self._current_icon, self._current_color),
            list(self._icons.values())[0]
        )
        self._iri_icons = {}
        for icon_key in self._icon_names:
            iri_path = os.path.join(base_dir, f'iri_{icon_key}.png')
            if os.path.exists(iri_path):
                self._iri_icons[icon_key] = Image.open(iri_path).convert('RGBA')
        self._flower_iridescent = self._iri_icons.get(self._current_icon, self._flower_base)
        self._font_cache = {}

        # 绑定事件到整个窗口
        self.root.bind('<ButtonPress-1>', self._on_drag_start)
        self.root.bind('<B1-Motion>', self._on_drag_motion)
        self.root.bind('<ButtonRelease-1>', self._on_click)
        self.root.bind('<Double-Button-1>', self._on_double_click)
        self.root.bind('<Button-3>', self._on_right_click)

        self._drag_data = {'x': 0, 'y': 0}
        self._hover_tip = None
        self._hovering = False
        self.root.bind('<Enter>', self._on_hover_enter)
        self.root.bind('<Leave>', self._on_hover_leave)

        # 变量（菜单 UI 中使用）
        self._icon_var = tk.StringVar(value=self._current_icon)
        self._mode_var = tk.StringVar(value=self._breathing_mode)
        self._color_var = tk.StringVar(value=self._current_color)
        self._sound_mode_var = tk.StringVar(value='off')
        self.auto_start_var = tk.BooleanVar(value=self._is_auto_start())

        # 自定义菜单状态
        self._custom_menu = None

        self.idle_detector = IdleDetector()
        self.was_idle = False

        self.tray_icon = None
        if HAS_TRAY:
            threading.Thread(target=self._setup_tray, daemon=True).start()

        # 延迟初始化分层窗口
        self.root.after(100, self._init_layered)
        self._check_idle()

    def _init_layered(self):
        self.root.update_idletasks()
        self._hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        if self._hwnd == 0:
            self._hwnd = self.root.winfo_id()
        style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        self._animate()

    def run(self):
        self.root.mainloop()

    # ─── 字体 ───

    def _get_font(self, size):
        if size not in self._font_cache:
            fonts_dir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
            for name in ['msyh.ttc', 'msyhbd.ttc', 'simhei.ttf', 'simsun.ttc', 'segoeui.ttf']:
                try:
                    path = os.path.join(fonts_dir, name)
                    self._font_cache[size] = ImageFont.truetype(path, size)
                    break
                except Exception:
                    continue
            else:
                self._font_cache[size] = ImageFont.load_default()
        return self._font_cache[size]

    # ─── 窗口 ───

    def _position_bottom_right(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f'+{sw - self.win_w - 30}+{sh - self.win_h - 60}')

    def _move_window(self, x, y, w, h):
        if hasattr(self, '_hwnd'):
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            ctypes.windll.user32.SetWindowPos(
                self._hwnd, 0, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE
            )
        self.root.geometry(f'{w}x{h}+{x}+{y}')

    def toggle_immersive(self):
        self.immersive = not self.immersive
        if self.immersive:
            self._saved_pos = (self.root.winfo_x(), self.root.winfo_y())
            self.win_w, self.win_h = IMMERSIVE_W, IMMERSIVE_H
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = (sw - self.win_w) // 2
            y = (sh - self.win_h) // 2
            self.guide_dismissed = False
            self._start_breathing()
            self._update_sound()
        else:
            self.breathing = False
            self._update_sound()
            self.win_w, self.win_h = COMPACT_W, COMPACT_H
            if hasattr(self, '_saved_pos'):
                x, y = self._saved_pos
            else:
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                x = sw - self.win_w - 30
                y = sh - self.win_h - 60
        self.current_prompt = random.choice(PROMPTS)

        # 用 UpdateLayeredWindow 一次原子调用完成：位置 + 尺寸 + 像素
        # 不用 SetWindowPos / geometry，DWM 没有机会渲染中间状态
        if hasattr(self, '_hwnd'):
            frame = self._render_frame()
            update_layered(self._hwnd, frame, pos=(x, y))
            # 像素已到位，现在才移动 tkinter 窗口实体到相同位置
            # 这样后续 _animate 的 update_layered(无pos) 也能画在正确位置
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            SWP_NOREDRAW = 0x0008
            ctypes.windll.user32.SetWindowPos(
                self._hwnd, 0, x, y, self.win_w, self.win_h,
                SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOREDRAW
            )

    def _play_sound(self):
        if os.path.exists(self._sound_path):
            winsound.PlaySound(
                self._sound_path,
                winsound.SND_FILENAME | winsound.SND_LOOP | winsound.SND_ASYNC
            )

    def _stop_sound(self):
        winsound.PlaySound(None, winsound.SND_PURGE)

    def _update_sound(self):
        mode = self._sound_mode_var.get()
        should_play = (mode == 'immersive' and self.immersive)
        if should_play:
            self._play_sound()
        else:
            self._stop_sound()

    def _switch_mode(self, key):
        self._breathing_mode = key
        self._mode_var.set(key)
        if self.breathing:
            self.breath_start = time.time()
            self.guide_dismissed = False

    def _switch_icon(self, key):
        self._current_icon = key
        self._icon_var.set(key)
        self._flower_base = self._icons.get(
            (key, self._current_color),
            self._flower_base
        )
        self._flower_iridescent = self._iri_icons.get(key, self._flower_base)

    def _show_color_picker(self):
        if hasattr(self, '_color_picker') and self._color_picker:
            try:
                self._color_picker.destroy()
            except Exception:
                pass

        picker = tk.Toplevel(self.root)
        picker.overrideredirect(True)
        picker.attributes('-topmost', True)
        picker.configure(bg='#333333')
        self._color_picker = picker

        saved_color = self._current_color

        frame = tk.Frame(picker, bg='#333333', padx=10, pady=8)
        frame.pack()

        color_keys = list(self._color_names.keys())

        def preview(key):
            self._switch_color(key)

        def restore():
            self._switch_color(saved_color)

        def confirm(key):
            self._switch_color(key)
            picker.destroy()
            self._color_picker = None

        for key in color_keys:
            hex_color = self._color_hex[key]
            size = 30
            c = tk.Canvas(frame, width=size, height=size, bg='#333333',
                         highlightthickness=0, cursor='hand2')
            border = '#ffffff' if key == saved_color else '#555555'
            c.create_oval(3, 3, size - 3, size - 3, fill=hex_color, outline=border, width=2)
            c.pack(side=tk.LEFT, padx=2)
            c.bind('<Enter>', lambda e, k=key: preview(k))
            c.bind('<Leave>', lambda e: restore())
            c.bind('<ButtonRelease-1>', lambda e, k=key: confirm(k))

        picker.update_idletasks()
        pw = picker.winfo_reqwidth()
        ph = picker.winfo_reqheight()
        mx = self.root.winfo_x() + self.win_w // 2 - pw // 2
        my = self.root.winfo_y() - ph - 8
        if my < 0:
            my = self.root.winfo_y() + self.win_h + 8
        picker.geometry(f'+{mx}+{my}')

    def _switch_color(self, key):
        self._current_color = key
        self._color_var.set(key)
        self._flower_base = self._icons.get(
            (self._current_icon, key),
            self._flower_base
        )

    def minimize(self):
        self.minimized = True
        self.root.withdraw()

    def restore(self):
        self.minimized = False
        # 如果处于沉浸模式，先退回背景模式
        if self.immersive:
            self.immersive = False
            self.breathing = False
            self._stop_sound()
            self.win_w, self.win_h = COMPACT_W, COMPACT_H
        self.root.deiconify()
        self.root.attributes('-topmost', True)
        # 确保窗口在屏幕可见区域
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = sw - self.win_w - 30
        y = sh - self.win_h - 60
        # 强制刷新渲染 + 位置
        if hasattr(self, '_hwnd'):
            try:
                frame = self._render_frame()
                update_layered(self._hwnd, frame, pos=(x, y))
                SWP_NOZORDER = 0x0004
                SWP_NOACTIVATE = 0x0010
                SWP_NOREDRAW = 0x0008
                ctypes.windll.user32.SetWindowPos(
                    self._hwnd, 0, x, y, self.win_w, self.win_h,
                    SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOREDRAW
                )
            except Exception:
                pass
        self.root.geometry(f'{self.win_w}x{self.win_h}+{x}+{y}')

    def quit(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()
        sys.exit(0)

    # ─── 呼吸阶段 ───

    def _get_phase_and_scale(self):
        if not self.breathing:
            return '', 0.85, 0.0

        mode = BREATHING_MODES[self._breathing_mode]
        cycle_dur = sum(p[1] for p in mode['phases'])
        elapsed = time.time() - self.breath_start
        cycle_num = int(elapsed // cycle_dur)
        t = elapsed % cycle_dur

        # 文字透明度
        if self.guide_dismissed:
            text_alpha = 0.0
        elif cycle_num < GUIDE_CYCLES - 1:
            text_alpha = 1.0
        elif cycle_num == GUIDE_CYCLES - 1:
            last_dur = mode['phases'][-1][1]
            remaining = cycle_dur - t
            if remaining <= last_dur:
                text_alpha = remaining / last_dur
            else:
                text_alpha = 1.0
        else:
            text_alpha = 0.0

        phases = mode['guide'] if cycle_num < GUIDE_CYCLES and not self.guide_dismissed else mode['phases']
        num_phases = len(phases)

        cumul = 0.0
        for i, (label, dur) in enumerate(phases):
            if t < cumul + dur:
                p = (t - cumul) / dur
                if self._breathing_mode == 'calm':
                    # 平衡模式：吸→缓冲→呼→缓冲
                    if i == 0:      # 吸气
                        scale = 0.7 + 0.3 * p
                    elif i == 1:    # 缓冲（保持大）
                        scale = 1.0
                    elif i == 2:    # 呼气
                        scale = 1.0 - 0.3 * p
                    else:           # 缓冲（保持小）
                        scale = 0.7
                elif self._breathing_mode == 'rest':
                    # 4-7-8模式：吸→屏→呼→缓冲
                    if i == 0:      # 吸气
                        scale = 0.7 + 0.3 * p
                    elif i == 1:    # 屏息
                        scale = 1.0
                    elif i == 2:    # 呼气
                        scale = 1.0 - 0.3 * p
                    else:           # 缓冲
                        scale = 0.7
                else:
                    # 箱式模式：吸→屏→呼→屏
                    if i == 0:
                        scale = 0.7 + 0.3 * p
                    elif i == 1:
                        scale = 1.0
                    elif i == 2:
                        scale = 1.0 - 0.3 * p
                    else:
                        scale = 0.7
                return label, scale, text_alpha
            cumul += dur
        return phases[0][0], 0.7, text_alpha

    # ─── 渲染帧 ───

    def _render_frame(self):
        frame = Image.new('RGBA', (self.win_w, self.win_h), (0, 0, 0, 0))
        phase_label, scale, text_alpha = self._get_phase_and_scale()

        # 花朵
        cx = self.win_w // 2
        if self.immersive:
            cy = self.win_h // 2 - 90
            target = round(340 * scale)
        else:
            cy = 55
            target = round(100 * scale)

        now = time.time()
        target = max(10, target)
        if target % 2 != 0:
            target += 1

        if self.immersive:
            flower = self._flower_base.resize((target, target), Image.LANCZOS)
        else:
            if self.breathing:
                flower = self._flower_base.resize((target, target), Image.LANCZOS)
            else:
                rot_angle = (now * 45) % 360
                rotated = self._flower_base.rotate(-rot_angle, resample=Image.BICUBIC, expand=False)
                flower = rotated.resize((target, target), Image.LANCZOS)
        fx = cx - target // 2
        fy = cy - target // 2
        frame.alpha_composite(flower, (fx, fy))

        # 背景模式：光圈只在静止时显示，呼吸时不显示
        if not self.immersive and not self.breathing:
            ring_r = int(target * 0.6) + 6
            ring_layer = Image.new('RGBA', (self.win_w, self.win_h), (0, 0, 0, 0))
            rd = ImageDraw.Draw(ring_layer)

            flow_angle = (now * 40) % 360
            hues = [
                (130, 210, 200), (120, 195, 215), (140, 185, 220),
                (130, 200, 205), (150, 215, 195), (140, 220, 185),
                (130, 210, 200),
            ]
            def hue_at(a):
                a = a % 360
                pos = a / 360 * (len(hues) - 1)
                idx = int(pos)
                f = pos - idx
                c1, c2 = hues[idx], hues[min(idx + 1, len(hues) - 1)]
                return tuple(int(c1[j] + (c2[j] - c1[j]) * f) for j in range(3))

            # 幻彩细线光圈
            num_seg = 72
            for seg in range(num_seg):
                sa = seg * 360 / num_seg
                ext = 360 / num_seg + 1
                diff = ((sa - flow_angle + 180) % 360) - 180
                glow = math.exp(-diff * diff / 2000)
                alpha = int(70 + 160 * glow)
                cr, cg, cb = hue_at(sa + now * 25)
                rd.arc([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
                       sa, sa + ext, fill=(cr, cg, cb, min(255, alpha)), width=2)
                if glow > 0.3:
                    for g_off in [3, -3]:
                        rr = ring_r + g_off
                        rd.arc([cx - rr, cy - rr, cx + rr, cy + rr],
                               sa, sa + ext, fill=(cr, cg, cb, int(35 * glow)), width=1)

            # 触碰水波：一圈波纹从光圈向外扩散
            ripple_elapsed = now - self._ripple_time
            if 0 < ripple_elapsed < 1.2:
                progress = ripple_elapsed / 1.2
                wave_r = ring_r + int(progress * 35)
                fade = 1.0 - progress
                # 有厚度的波纹环
                for w_off in range(-3, 4):
                    dist = abs(w_off) / 3
                    a = int(80 * fade * fade * (1 - dist * dist))
                    if a > 1:
                        wr = wave_r + w_off
                        rd.ellipse(
                            [cx - wr, cy - wr, cx + wr, cy + wr],
                            outline=(255, 255, 255, a), width=1
                        )

            frame.alpha_composite(ring_layer)

        draw = ImageDraw.Draw(frame)

        # 毛玻璃面板色调（深青蓝色）
        GLASS_BG = (30, 75, 85, 100)
        GLASS_BORDER = (255, 255, 255, 40)
        GLASS_TEXT = (255, 255, 255, 210)

        # 阶段文字 → 花朵中央（仅沉浸模式）
        if self.immersive and text_alpha > 0.01:
            base_d = 260
            font = self._get_font(46)

            glass_a = int(110 * text_alpha)
            border_a = int(40 * text_alpha)
            text_a = int(230 * text_alpha)

            txt_img = Image.new('RGBA', (base_d, base_d), (0, 0, 0, 0))
            td = ImageDraw.Draw(txt_img)
            td.ellipse(
                [0, 0, base_d - 1, base_d - 1],
                fill=(30, 75, 85, glass_a), outline=(255, 255, 255, border_a)
            )

            if phase_label:
                lines = phase_label.split('\n')
                line_heights = []
                line_widths = []
                for line in lines:
                    bb = font.getbbox(line)
                    line_widths.append(int(td.textlength(line, font=font)))
                    line_heights.append(bb[3] - bb[1])

                gap = 8
                total_h = sum(line_heights) + (len(lines) - 1) * gap
                cr = base_d // 2
                start_y = cr - total_h // 2
                for j, line in enumerate(lines):
                    lx = cr - line_widths[j] // 2
                    bb = font.getbbox(line)
                    td.text((lx, start_y - bb[1]), line,
                            fill=(255, 255, 255, text_a), font=font)
                    start_y += line_heights[j] + gap

            final_d = max(4, int(target * 0.33))
            txt_img = txt_img.resize((final_d, final_d), Image.LANCZOS)
            frame.alpha_composite(txt_img, (cx - final_d // 2, cy - final_d // 2))

        # 觉察提示 + 毛玻璃底（沉浸模式）
        if self.immersive and self.breathing:
            pfont = self._get_font(15)
            tw = draw.textlength(self.current_prompt, font=pfont)
            py = self.win_h - 105
            pw, ph = int(tw) + 32, 32
            pill = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
            pd = ImageDraw.Draw(pill)
            pd.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=10,
                                 fill=GLASS_BG, outline=GLASS_BORDER)
            frame.alpha_composite(pill, (int(cx - pw / 2), py))
            draw = ImageDraw.Draw(frame)
            draw.text(
                (cx - tw / 2, py + 6), self.current_prompt,
                fill=GLASS_TEXT, font=pfont
            )

        # 底部提示 + 毛玻璃底（沉浸模式）
        if self.immersive:
            hint = '双击呼吸球 → 背景模式'
            hfont = self._get_font(13)
            tw = draw.textlength(hint, font=hfont)
            pw, ph = int(tw) + 32, 30
            hy = self.win_h - 38
            pill = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
            pd = ImageDraw.Draw(pill)
            pd.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=10,
                                 fill=GLASS_BG, outline=GLASS_BORDER)
            frame.alpha_composite(pill, (int(cx - pw / 2), hy))
            draw = ImageDraw.Draw(frame)
            draw.text(
                (cx - tw / 2, hy + 5), hint,
                fill=GLASS_TEXT, font=hfont
            )


        return frame

    # ─── 动画循环 ───

    def _animate(self):
        if not hasattr(self, '_hwnd'):
            self.root.after(100, self._animate)
            return
        try:
            frame = self._render_frame()
            update_layered(self._hwnd, frame)
            # 沉浸模式下持续确保窗口置顶，防止点击透明区域后被遮挡
            if self.immersive:
                HWND_TOPMOST = -1
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOACTIVATE = 0x0010
                ctypes.windll.user32.SetWindowPos(
                    self._hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                )
        except Exception:
            pass
        self.root.after(50, self._animate)

    def _start_breathing(self):
        if self.breathing:
            return
        self.breathing = True
        self.breath_start = time.time()
        self.current_prompt = random.choice(PROMPTS)
        self._update_sound()

    def _stop_breathing(self):
        if not self.breathing:
            return
        if self.immersive:
            return
        self.breathing = False
        self._stop_sound()

    # ─── 空闲检测 ───

    def _check_idle(self):
        idle = self.idle_detector.get_idle_seconds() >= IDLE_THRESHOLD
        if idle and not self.was_idle:
            self.was_idle = True
            if not self.minimized:
                self._start_breathing()
        elif not idle and self.was_idle:
            self.was_idle = False
            self._stop_breathing()
        self.root.after(1000, self._check_idle)

    # ─── 交互 ───

    def _on_drag_start(self, e):
        self._drag_data['x'] = e.x
        self._drag_data['y'] = e.y
        self._drag_moved = False

    def _on_drag_motion(self, e):
        self._drag_moved = True
        x = self.root.winfo_x() + e.x - self._drag_data['x']
        y = self.root.winfo_y() + e.y - self._drag_data['y']
        self.root.geometry(f'+{x}+{y}')

    def _on_click(self, e):
        if self._drag_moved:
            return
        if time.time() - self._last_double_click < 0.5:
            return
        if self.immersive and not self.guide_dismissed and self.breathing:
            mode = BREATHING_MODES[self._breathing_mode]
            cycle_dur = sum(p[1] for p in mode['phases'])
            elapsed = time.time() - self.breath_start
            cycle_num = int(elapsed // cycle_dur)
            if cycle_num < GUIDE_CYCLES:
                self.guide_dismissed = True

    def _on_double_click(self, e):
        # 计算球心和判定半径
        cx = self.win_w // 2
        if self.immersive:
            cy = self.win_h // 2 - 90
            hit_r = 170  # 340 * scale / 2
        else:
            cy = 55
            hit_r = 55   # 100 / 2 + 余量
        dx, dy = e.x - cx, e.y - cy
        if dx * dx + dy * dy > hit_r * hit_r:
            return  # 点击在球外，不响应
        self._last_double_click = time.time()
        self.toggle_immersive()

    def _on_right_click(self, e):
        self._show_custom_menu(e)

    # ─── 自定义半透明右键菜单 ───

    _MENU_BG = '#1e4b55'
    _MENU_FG = '#ffffffd6'
    _MENU_HOVER = '#ffffff1e'
    _MENU_SEP = '#ffffff1e'
    _MENU_FONT = ('Microsoft YaHei UI', 9)
    _MENU_ITEM_H = 28
    _MENU_W = 170
    _SUB_W = 140

    def _close_custom_menu(self):
        if self._custom_menu:
            try:
                self._custom_menu.destroy()
            except Exception:
                pass
            self._custom_menu = None

    def _show_custom_menu(self, e):
        self._close_custom_menu()

        menu = tk.Toplevel(self.root)
        menu.overrideredirect(True)
        menu.attributes('-topmost', True)
        menu.attributes('-alpha', 0.92)
        menu.configure(bg=self._MENU_BG)
        self._custom_menu = menu
        self._active_submenu_frame = None
        self._active_submenu_key = None

        container = tk.Frame(menu, bg=self._MENU_BG, padx=6, pady=6)
        container.pack(fill=tk.BOTH, expand=True)

        # ─ 沉浸模式
        self._add_menu_item(container, '◎  沉浸模式', self._menu_toggle_immersive)
        self._add_separator(container)

        # ─ 切换颜色（放在图案上面，避免紫色被遮挡）
        cur_color_name = self._color_names.get(self._current_color, '')
        self._add_submenu_item(container, f'◕  颜色 · {cur_color_name}', 'color', self._build_color_submenu)
        # ─ 切换图案（显示当前图案名）
        cur_icon_name = self._icon_names.get(self._current_icon, '')
        self._add_submenu_item(container, f'❋  图案 · {cur_icon_name}', 'icon', self._build_icon_submenu)
        # ─ 呼吸模式（显示当前模式名）
        cur_mode_name = BREATHING_MODES[self._breathing_mode]['name']
        self._add_submenu_item(container, f'◐  模式 · {cur_mode_name}', 'mode', self._build_mode_submenu)
        self._add_separator(container)

        # ─ 冥想白噪声（显示当前状态）
        sound_labels = {'off': '无声音', 'immersive': '限沉浸模式'}
        cur_sound = sound_labels.get(self._sound_mode_var.get(), '无声音')
        self._add_submenu_item(container, f'♪  白噪声 · {cur_sound}', 'sound', self._build_sound_submenu)
        self._add_separator(container)

        # ─ 开机自启动
        auto_check = '✓' if self.auto_start_var.get() else '   '
        self._add_menu_item(container, f'{auto_check} 开机自启动', self._menu_toggle_auto_start)
        # ─ 最小化
        self._add_menu_item(container, '─  最小化', self._menu_minimize)
        # ─ 退出
        self._add_menu_item(container, '✕  退出', self._menu_quit)

        # 定位
        menu.update_idletasks()
        mw = menu.winfo_reqwidth()
        mh = menu.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        mx = e.x_root
        my = e.y_root
        if mx + mw > sw:
            mx = sw - mw - 4
        if my + mh > sh:
            my = sh - mh - 4
        menu.geometry(f'+{mx}+{my}')

        # 点击外部关闭
        menu.bind('<FocusOut>', lambda ev: self.root.after(100, self._close_on_focus_out))
        menu.focus_set()

    def _close_on_focus_out(self):
        """延迟检查焦点，避免子菜单展开时误关闭"""
        if self._custom_menu:
            try:
                focused = self.root.focus_get()
                # 如果焦点仍在菜单窗口的子控件上，不关闭
                if focused and str(focused).startswith(str(self._custom_menu)):
                    return
            except Exception:
                pass
            self._close_custom_menu()

    def _add_menu_item(self, parent, text, command):
        lbl = tk.Label(
            parent, text=text, anchor='w',
            bg=self._MENU_BG, fg='#d6d6d6',
            font=self._MENU_FONT,
            padx=8, pady=3, cursor='hand2',
        )
        lbl.pack(fill=tk.X, pady=0)
        lbl.bind('<Enter>', lambda ev: lbl.configure(bg='#2a6070'))
        lbl.bind('<Leave>', lambda ev: lbl.configure(bg=self._MENU_BG))
        lbl.bind('<ButtonRelease-1>', lambda ev: self._menu_exec(command))
        return lbl

    def _add_submenu_item(self, parent, text, key, builder):
        frm = tk.Frame(parent, bg=self._MENU_BG, cursor='hand2')
        frm.pack(fill=tk.X, pady=0)
        lbl = tk.Label(
            frm, text=text, anchor='w',
            bg=self._MENU_BG, fg='#d6d6d6',
            font=self._MENU_FONT, padx=8, pady=3,
        )
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        arrow = tk.Label(
            frm, text='▾', anchor='e',
            bg=self._MENU_BG, fg='#d6d6d6',
            font=self._MENU_FONT, padx=6, pady=3,
        )
        arrow.pack(side=tk.RIGHT)

        sub_container = tk.Frame(parent, bg=self._MENU_BG)
        # 不 pack — 由 toggle 控制

        def hover_in(ev):
            lbl.configure(bg='#2a6070')
            frm.configure(bg='#2a6070')
            arrow.configure(bg='#2a6070')

        def hover_out(ev):
            lbl.configure(bg=self._MENU_BG)
            frm.configure(bg=self._MENU_BG)
            arrow.configure(bg=self._MENU_BG)

        def toggle(ev):
            if self._active_submenu_key == key:
                # 收起
                sub_container.pack_forget()
                self._active_submenu_key = None
                self._active_submenu_frame = None
            else:
                # 先收起旧的
                if self._active_submenu_frame:
                    self._active_submenu_frame.pack_forget()
                # 构建并展开
                for w in sub_container.winfo_children():
                    w.destroy()
                builder(sub_container)
                sub_container.pack(fill=tk.X, after=frm)
                self._active_submenu_key = key
                self._active_submenu_frame = sub_container
            # 重新定位避免超出屏幕
            self._custom_menu.update_idletasks()

        for widget in [frm, lbl, arrow]:
            widget.bind('<Enter>', hover_in)
            widget.bind('<Leave>', hover_out)
            widget.bind('<ButtonRelease-1>', toggle)

    def _add_separator(self, parent):
        sep = tk.Frame(parent, bg='#3a6a70', height=1)
        sep.pack(fill=tk.X, padx=8, pady=4)

    def _add_sub_radio(self, parent, text, selected, command):
        prefix = '●' if selected else '○'
        lbl = tk.Label(
            parent, text=f'  {prefix}  {text}', anchor='w',
            bg=self._MENU_BG, fg='#c0c0c0',
            font=self._MENU_FONT,
            padx=12, pady=2, cursor='hand2',
        )
        lbl.pack(fill=tk.X, pady=0)
        lbl.bind('<Enter>', lambda ev: lbl.configure(bg='#2a6070'))
        lbl.bind('<Leave>', lambda ev: lbl.configure(bg=self._MENU_BG))
        lbl.bind('<ButtonRelease-1>', lambda ev: self._menu_exec(command))
        return lbl

    def _menu_exec(self, command):
        self._close_custom_menu()
        command()

    # ─ 子菜单构建 ─

    def _build_icon_submenu(self, parent):
        for key, label in self._icon_names.items():
            self._add_sub_radio(
                parent, label, key == self._current_icon,
                lambda k=key: self._switch_icon(k)
            )

    def _build_mode_submenu(self, parent):
        for key, cfg in BREATHING_MODES.items():
            self._add_sub_radio(
                parent, cfg['name'], key == self._breathing_mode,
                lambda k=key: self._switch_mode(k)
            )

    def _build_sound_submenu(self, parent):
        cur = self._sound_mode_var.get()
        if cur not in ('off', 'immersive'):
            self._sound_mode_var.set('off')
        sound_opts = [
            ('off', '无声音'),
            ('immersive', '限沉浸模式'),
        ]
        cur = self._sound_mode_var.get()
        for val, label in sound_opts:
            self._add_sub_radio(
                parent, label, val == cur,
                lambda v=val: self._menu_switch_sound(v)
            )

    def _build_color_submenu(self, parent):
        for key, label in self._color_names.items():
            hex_color = self._color_hex[key]
            selected = key == self._current_color
            prefix = '●' if selected else '○'
            frm = tk.Frame(parent, bg=self._MENU_BG, cursor='hand2')
            frm.pack(fill=tk.X, pady=0)
            # 色块圆点
            dot = tk.Canvas(frm, width=14, height=14, bg=self._MENU_BG,
                            highlightthickness=0)
            dot.create_oval(1, 1, 13, 13, fill=hex_color, outline=hex_color)
            dot.pack(side=tk.LEFT, padx=(16, 4), pady=2)
            # 文字
            lbl = tk.Label(
                frm, text=f'{prefix}  {label}', anchor='w',
                bg=self._MENU_BG, fg='#c0c0c0',
                font=self._MENU_FONT, pady=2,
            )
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

            def hover_in(ev, f=frm, l=lbl):
                f.configure(bg='#2a6070')
                l.configure(bg='#2a6070')
            def hover_out(ev, f=frm, l=lbl):
                f.configure(bg=self._MENU_BG)
                l.configure(bg=self._MENU_BG)
            def click(ev, k=key):
                self._menu_exec(lambda: self._switch_color(k))

            for w in [frm, dot, lbl]:
                w.bind('<Enter>', hover_in)
                w.bind('<Leave>', hover_out)
                w.bind('<ButtonRelease-1>', click)

    # ─ 菜单命令 ─

    def _menu_toggle_immersive(self):
        self.toggle_immersive()

    def _menu_toggle_auto_start(self):
        self._toggle_auto_start()

    def _menu_minimize(self):
        self.minimize()

    def _menu_quit(self):
        self.quit()

    def _menu_switch_sound(self, val):
        self._sound_mode_var.set(val)
        self._update_sound()

    def _show_tooltip(self, e, text):
        if self._hover_tip:
            return
        tip = tk.Toplevel(self.root)
        tip.overrideredirect(True)
        tip.attributes('-topmost', True)
        tip.configure(bg='#2a3a3f')
        lbl = tk.Label(
            tip, text=text,
            bg='#2a3a3f', fg='#dddddd',
            font=('Microsoft YaHei UI', 9), padx=10, pady=5
        )
        lbl.pack()
        tip.update_idletasks()
        tw = tip.winfo_reqwidth()
        th = tip.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        tx = e.x_root + 12
        ty = e.y_root - th - 8
        if tx + tw > sw:
            tx = e.x_root - tw - 8
        if ty < 0:
            ty = e.y_root + 18
        tip.geometry(f'+{tx}+{ty}')
        self._hover_tip = tip

    def _on_hover_enter(self, e):
        if not self.immersive:
            self._ripple_time = time.time()
            self._show_tooltip(e, '双击呼吸球 → 沉浸模式')

    def _on_hover_leave(self, e):
        if self._hover_tip:
            self._hover_tip.destroy()
            self._hover_tip = None

    # ─── 系统托盘 ───

    def _setup_tray(self):
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill=(*PRIMARY, 180))

        menu = pystray.Menu(
            pystray.MenuItem('显示呼吸球', lambda: self.root.after(0, self.restore), default=True),
            pystray.MenuItem('沉浸模式', lambda: self.root.after(0, self.toggle_immersive)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('最小化', lambda: self.root.after(0, self.minimize)),
            pystray.MenuItem('退出', lambda: self.root.after(0, self.quit)),
        )
        self.tray_icon = pystray.Icon('mindful_breathing', img, '觉察呼吸', menu)
        self.tray_icon.run()

    # ─── 开机自启动 ───

    REG_PATH = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
    REG_NAME = 'MindfulBreathing'

    def _is_auto_start(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, self.REG_NAME)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def _toggle_auto_start(self):
        if self._is_auto_start():
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, self.REG_NAME)
                winreg.CloseKey(key)
                self.auto_start_var.set(False)
            except Exception:
                pass
        else:
            try:
                script = os.path.abspath(__file__)
                cmd = f'"{sys.executable}" "{script}"'
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, self.REG_NAME, 0, winreg.REG_SZ, cmd)
                winreg.CloseKey(key)
                self.auto_start_var.set(True)
            except Exception:
                pass


if __name__ == '__main__':
    app = BreathingBall()
    app.run()
