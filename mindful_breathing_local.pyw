# -*- coding: utf-8 -*-
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

# Windows 下尽量使用 UTF-8，避免托盘/标题等中文乱码
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from PIL import Image, ImageDraw, ImageFont, ImageFilter
try:
    from dotenv import load_dotenv
    _base = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(_base, 'backend', '.env'))
    if getattr(sys, 'frozen', False):
        load_dotenv(os.path.join(os.path.dirname(sys.executable), '.env'))
    else:
        load_dotenv(os.path.join(_base, '.env'))
except Exception:
    pass

try:
    import pystray
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# 本地免登录版：不显示登录/注册，所有功能直接可用
AUTH_AVAILABLE = False

PROMPTS = [
    '你的肩膀是紧的还是松的？',
    '感受一下你的双脚接触地面',
    '不管此刻感受如何，允许它存在',
    '你有想切走的冲动吗？只是观察它',
    '说出你现在能看到的三样东西',
    '听听此刻周围有什么声音？',
    '尝试多使用腹式呼吸',
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
APP_VERSION = '1.0.0'

COMPACT_W, COMPACT_H = 140, 180
IMMERSIVE_W, IMMERSIVE_H = 420, 560

# ─── Win32 分层窗口 API ───

GWL_EXSTYLE = -20
MONITOR_DEFAULTTONEAREST = 2


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_ulong),
        ('rcMonitor', RECT),
        ('rcWork', RECT),
        ('dwFlags', ctypes.c_ulong),
    ]
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


def get_monitor_work_rect(hwnd):
    """获取窗口所在显示器的工作区域 (left, top, right, bottom)，多显示器下更准确"""
    try:
        hmon = ctypes.windll.user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            return (mi.rcWork.left, mi.rcWork.top, mi.rcWork.right, mi.rcWork.bottom)
    except Exception:
        pass
    return None


def clamp_to_visible(x, y, w, h):
    """确保坐标在可见范围内，防止窗口跑出屏幕"""
    SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
    SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
    vx = ctypes.windll.user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = ctypes.windll.user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = ctypes.windll.user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = ctypes.windll.user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    x = max(vx, min(x, vx + vw - w - 1))
    y = max(vy, min(y, vy + vh - h - 1))
    return x, y


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
        self.root.title('呼吸泡泡')
        _base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        _ico = os.path.join(_base, 'app_icon.ico')
        if os.path.exists(_ico):
            try:
                self.root.iconbitmap(_ico)
            except Exception:
                pass
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
        self._hover_tip_label = None
        self._hovering = False
        self.root.bind('<Enter>', self._on_hover_enter)
        self.root.bind('<Leave>', self._on_hover_leave)
        self.root.bind('<Motion>', self._on_motion)

        # 变量（菜单 UI 中使用）
        self._icon_var = tk.StringVar(value=self._current_icon)
        self._mode_var = tk.StringVar(value=self._breathing_mode)
        self._color_var = tk.StringVar(value=self._current_color)
        self._sound_mode_var = tk.StringVar(value='off')
        self.auto_start_var = tk.BooleanVar(value=self._is_auto_start())

        # 自定义菜单状态
        self._custom_menu = None
        self._speaker_rect = None

        self.idle_detector = IdleDetector()
        self.was_idle = False

        self.tray_icon = None
        if HAS_TRAY:
            threading.Thread(target=self._setup_tray, daemon=True).start()

        # 延迟初始化分层窗口
        self.root.after(100, self._init_layered)
        self._check_idle()
        # 后台检查更新
        threading.Thread(target=self._check_update, daemon=True).start()

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
        hwnd = getattr(self, '_hwnd', None)
        work = get_monitor_work_rect(hwnd) if hwnd else None
        if work:
            l, t, r, b = work
            mw, mh = r - l, b - t
        else:
            mw = self.root.winfo_screenwidth()
            mh = self.root.winfo_screenheight()
            l, t = 0, 0

        if self.immersive:
            self.win_w, self.win_h = IMMERSIVE_W, IMMERSIVE_H
            x = l + (mw - self.win_w) // 2
            y = t + (mh - self.win_h) // 2
            self.guide_dismissed = False
            self._start_breathing()
            self._update_sound()
        else:
            self.breathing = False
            self._update_sound()
            self.win_w, self.win_h = COMPACT_W, COMPACT_H
            x = l + mw - self.win_w - 30
            y = t + mh - self.win_h - 60
        x, y = clamp_to_visible(x, y, self.win_w, self.win_h)
        self.current_prompt = random.choice(PROMPTS)
        self._update_tray_menu()

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

    def _update_tray_menu(self):
        if self.tray_icon:
            try:
                self.tray_icon.update_menu()
            except Exception:
                pass

    def minimize(self):
        self.minimized = True
        self.root.withdraw()
        self._update_tray_menu()

    def restore(self, to_immersive=None):
        """恢复窗口。to_immersive=True 恢复到沉浸模式，False/None 背景模式"""
        self.minimized = False
        want_immersive = to_immersive is True
        if self.immersive and not want_immersive:
            self.immersive = False
            self.breathing = False
            self._stop_sound()
            self.win_w, self.win_h = COMPACT_W, COMPACT_H
        self.root.deiconify()
        self.root.attributes('-topmost', True)
        if want_immersive and not self.immersive:
            self.toggle_immersive()
            return
        # 确保窗口在屏幕可见区域（背景模式）
        hwnd = getattr(self, '_hwnd', None)
        work = get_monitor_work_rect(hwnd) if hwnd else None
        if work:
            l, t, r, b = work
            x = l + (r - l) - self.win_w - 30
            y = t + (b - t) - self.win_h - 60
        else:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = sw - self.win_w - 30
            y = sh - self.win_h - 60
        x, y = clamp_to_visible(x, y, self.win_w, self.win_h)
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
        self._update_tray_menu()

    def bring_back_window(self):
        """将窗口移到可见区域并置于前台（用于窗口跑出屏幕时找回）"""
        self.minimized = False
        self.root.deiconify()
        hwnd = getattr(self, '_hwnd', None)
        work = get_monitor_work_rect(hwnd) if hwnd else None
        if work:
            l, t, r, b = work
            x = l + ((r - l) - self.win_w) // 2
            y = t + ((b - t) - self.win_h) // 2
        else:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = (sw - self.win_w) // 2
            y = (sh - self.win_h) // 2
        x, y = clamp_to_visible(x, y, self.win_w, self.win_h)
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
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        self.root.lift()
        self._update_tray_menu()

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

        # 沉浸模式：底部 [双击呼吸球 → 背景模式]
        if not self.immersive:
            self._speaker_rect = None
        elif self.immersive:
            hint = '双击呼吸球 → 背景模式'
            hfont = self._get_font(13)
            tw = draw.textlength(hint, font=hfont)
            pw, ph = int(tw) + 32, 36
            hy = self.win_h - 38
            pill = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
            pd = ImageDraw.Draw(pill)
            pd.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=10,
                                 fill=GLASS_BG, outline=GLASS_BORDER)
            frame.alpha_composite(pill, (int(cx - pw / 2), hy))
            draw = ImageDraw.Draw(frame)
            draw.text(
                (cx - tw / 2, hy + 9), hint,
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

    def _check_update(self):
        """后台检查更新，若有新版本则弹窗+下载链接"""
        url = os.environ.get('UPDATE_VERSION_URL', '')
        if not url:
            return
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={'User-Agent': 'BreathingBall/1.0'})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode())
            remote = data.get('version', '')
            download_url = data.get('url', '')
            if remote and download_url and remote != APP_VERSION:
                def _show_popup():
                    top = tk.Toplevel(self.root)
                    top.title('发现新版本')
                    top.geometry('420x150')
                    top.configure(bg='#f2faf9')
                    top.attributes('-topmost', True)
                    tk.Label(top, text=f'发现新版本 {remote}', bg='#f2faf9',
                            font=('Microsoft YaHei UI', 12, 'bold')).pack(pady=(16, 8))
                    tk.Label(top, text=download_url, bg='#f2faf9', fg='#408a82',
                            font=('Microsoft YaHei UI', 9), wraplength=380).pack(pady=(0, 12))
                    tk.Button(top, text='确定', command=top.destroy,
                              bg='#6db3a8', fg='white', relief='flat',
                              font=('Microsoft YaHei UI', 10), padx=24, pady=6,
                              cursor='hand2').pack(pady=(0, 16))
                self.root.after(0, _show_popup)
        except Exception:
            pass

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
    _MENU_HOVER_BG = '#2a6070'
    _THEME_MENU = {
        'red': ('#4a2525', '#5c3535'),
        'orange': ('#4a3520', '#5c4530'),
        'yellow': ('#454020', '#565030'),
        'green': ('#1e3d28', '#2a4a38'),
        'blue': ('#1e2d4a', '#2a3d5c'),
        'cyan': ('#1e3a40', '#2a5058'),
        'purple': ('#2e1e4a', '#3a2a5c'),
    }
    # 清新治愈风登录页：浅色背景 + 主题色点缀 (bg, card, accent, muted)
    _THEME_LOGIN = {
        'red': ('#fdf5f5', '#fff0f0', '#c86464', '#8a5050'),
        'orange': ('#fdf8f2', '#fff5e8', '#d29b5a', '#8a7040'),
        'yellow': ('#fdfcf5', '#fffce8', '#c8be64', '#8a8640'),
        'green': ('#f2faf5', '#e8f8ef', '#64b478', '#408a58'),
        'blue': ('#f2f6fd', '#e8f0ff', '#648cc8', '#40608a'),
        'cyan': ('#f2faf9', '#e8f6f5', '#6db3a8', '#408a82'),
        'purple': ('#f8f5fd', '#f0e8ff', '#9678be', '#60508a'),
    }

    def _get_menu_colors(self):
        bg, hover = self._THEME_MENU.get(self._current_color, (self._MENU_BG, self._MENU_HOVER_BG))
        return bg, hover

    def _get_login_colors(self):
        """清新治愈风登录页配色，随主题变化"""
        return self._THEME_LOGIN.get(self._current_color, ('#f2faf9', '#e8f6f5', '#6db3a8', '#408a82'))
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

        menu_bg, menu_hover = self._get_menu_colors()

        menu = tk.Toplevel(self.root)
        menu.overrideredirect(True)
        menu.attributes('-topmost', True)
        menu.attributes('-alpha', 0.92)
        menu.configure(bg=menu_bg)
        self._custom_menu = menu
        self._active_submenu_frame = None
        self._active_submenu_key = None
        self._menu_bg = menu_bg
        self._menu_hover = menu_hover

        container = tk.Frame(menu, bg=menu_bg, padx=6, pady=6)
        container.pack(fill=tk.BOTH, expand=True)

        # ─ 主题、图案、模式，下面隔开一行白噪声（无沉浸模式项）
        cur_color_name = self._color_names.get(self._current_color, '')
        self._add_submenu_item(container, f'◕  主题 · {cur_color_name}', 'color', self._build_color_submenu)
        cur_icon_name = self._icon_names.get(self._current_icon, '')
        self._add_submenu_item(container, f'❋  图案 · {cur_icon_name}', 'icon', self._build_icon_submenu)
        cur_mode_name = BREATHING_MODES[self._breathing_mode]['name']
        self._add_submenu_item(container, f'◐  模式 · {cur_mode_name}', 'mode', self._build_mode_submenu)
        self._add_separator(container)
        sound_label = '白噪声 · 开' if self._sound_mode_var.get() == 'immersive' else '白噪声 · 关'
        self._add_submenu_item(container, f'◉  {sound_label}', 'sound', self._build_sound_submenu)
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
        bg = getattr(self, '_menu_bg', self._MENU_BG)
        hv = getattr(self, '_menu_hover', self._MENU_HOVER_BG)
        lbl = tk.Label(
            parent, text=text, anchor='w',
            bg=bg, fg='#d6d6d6',
            font=self._MENU_FONT,
            padx=8, pady=3, cursor='hand2',
        )
        lbl.pack(fill=tk.X, pady=0)
        lbl.bind('<Enter>', lambda ev, h=hv: lbl.configure(bg=h))
        lbl.bind('<Leave>', lambda ev, b=bg: lbl.configure(bg=b))
        lbl.bind('<ButtonRelease-1>', lambda ev: self._menu_exec(command))
        return lbl

    def _add_submenu_item(self, parent, text, key, builder):
        bg = getattr(self, '_menu_bg', self._MENU_BG)
        hv = getattr(self, '_menu_hover', self._MENU_HOVER_BG)
        frm = tk.Frame(parent, bg=bg, cursor='hand2')
        frm.pack(fill=tk.X, pady=0)
        lbl = tk.Label(
            frm, text=text, anchor='w',
            bg=bg, fg='#d6d6d6',
            font=self._MENU_FONT, padx=8, pady=3,
        )
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        arrow = tk.Label(
            frm, text='▾', anchor='e',
            bg=bg, fg='#d6d6d6',
            font=self._MENU_FONT, padx=6, pady=3,
        )
        arrow.pack(side=tk.RIGHT)

        sub_container = tk.Frame(parent, bg=bg)
        # 不 pack — 由 toggle 控制

        def hover_in(ev):
            lbl.configure(bg=hv)
            frm.configure(bg=hv)
            arrow.configure(bg=hv)

        def hover_out(ev):
            lbl.configure(bg=bg)
            frm.configure(bg=bg)
            arrow.configure(bg=bg)

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
        bg = getattr(self, '_menu_bg', self._MENU_BG)
        hv = getattr(self, '_menu_hover', self._MENU_HOVER_BG)
        prefix = '●' if selected else '○'
        lbl = tk.Label(
            parent, text=f'  {prefix}  {text}', anchor='w',
            bg=bg, fg='#c0c0c0',
            font=self._MENU_FONT,
            padx=12, pady=2, cursor='hand2',
        )
        lbl.pack(fill=tk.X, pady=0)
        lbl.bind('<Enter>', lambda ev: lbl.configure(bg=hv))
        lbl.bind('<Leave>', lambda ev: lbl.configure(bg=bg))
        lbl.bind('<ButtonRelease-1>', lambda ev: self._menu_exec(command))
        return lbl

    def _menu_exec(self, command):
        self._close_custom_menu()
        command()

    # ─ 登录相关 ─

    def _get_login_email(self):
        if not AUTH_AVAILABLE:
            return None
        try:
            return auth_client.get_user_email()
        except Exception:
            return None

    def _menu_logout(self):
        if AUTH_AVAILABLE:
            try:
                auth_client.logout()
            except Exception:
                pass
        self._close_custom_menu()

    def _show_login_dialog(self):
        self._close_custom_menu()
        lg_bg, lg_card, lg_accent, lg_muted = self._get_login_colors()
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(base_dir, 'app_icon.ico')

        dlg = tk.Toplevel(self.root)
        dlg.title('呼吸泡泡')
        dlg.resizable(False, False)
        dlg.configure(bg=lg_bg)
        dlg.attributes('-topmost', True)
        if os.path.exists(ico_path):
            try:
                dlg.iconbitmap(ico_path)
            except Exception:
                pass

        main = tk.Frame(dlg, bg=lg_bg, padx=32, pady=24)
        main.pack()

        # 顶部 logo：去白底+去觉察呼吸，透明嵌入页面
        logo_path = os.path.join(base_dir, 'login_logo.png')
        if os.path.exists(logo_path):
            from PIL import ImageTk
            try:
                logo_img = Image.open(logo_path).convert('RGBA')
                # 裁掉下方“觉察呼吸”文字，只保留花+心图形
                logo_img = logo_img.crop((0, 0, logo_img.width, int(logo_img.height * 0.55)))
                # 白色/浅色背景变透明
                data = logo_img.getdata()
                new_data = []
                for item in data:
                    r, g, b, a = item
                    if r > 248 and g > 248 and b > 248:
                        new_data.append((r, g, b, 0))
                    else:
                        new_data.append(item)
                logo_img.putdata(new_data)
                # 合成到页面背景色，实现透明镶嵌
                bg_rgb = tuple(int(lg_bg.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                bg_layer = Image.new('RGB', logo_img.size, bg_rgb)
                logo_rgba = logo_img
                bg_layer.paste(logo_rgba, (0, 0), logo_rgba)
                logo_img = bg_layer.resize((100, 100), Image.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_img)
                logo_lbl = tk.Label(main, image=logo_photo, bg=lg_bg)
                logo_lbl.image = logo_photo
                logo_lbl.pack(pady=(0, 4))
            except Exception:
                pass
        tk.Label(
            main, text='呼吸泡泡',
            bg=lg_bg, fg=lg_accent,
            font=('Microsoft YaHei UI', 20, 'bold')
        ).pack(pady=(0, 2))
        tk.Label(
            main, text='Breathing · Meditation',
            bg=lg_bg, fg=lg_muted,
            font=('Microsoft YaHei UI', 10)
        ).pack(pady=(0, 20))

        # 表单卡片区
        card = tk.Frame(main, bg=lg_card, padx=20, pady=16)
        card.pack(fill=tk.X, pady=(0, 12))

        tk.Label(card, text='邮箱', bg=lg_card, fg=lg_muted,
                 font=('Microsoft YaHei UI', 10)).pack(anchor='w', pady=(0, 4))
        var_email = tk.StringVar()
        ent_email = tk.Entry(card, textvariable=var_email, width=26,
                            bg='white', fg='#333', insertbackground='#333',
                            relief='flat', font=('Microsoft YaHei UI', 11))
        ent_email.pack(fill=tk.X, ipady=8, pady=(0, 14))

        tk.Label(card, text='密码', bg=lg_card, fg=lg_muted,
                 font=('Microsoft YaHei UI', 10)).pack(anchor='w', pady=(0, 4))
        var_pwd = tk.StringVar()
        ent_pwd = tk.Entry(card, textvariable=var_pwd, width=26, show='●',
                          bg='white', fg='#333', insertbackground='#333',
                          relief='flat', font=('Microsoft YaHei UI', 11))
        ent_pwd.pack(fill=tk.X, ipady=8, pady=(0, 8))

        lbl_msg = tk.Label(main, text='', bg=lg_bg, fg='#e06666',
                          font=('Microsoft YaHei UI', 9))
        lbl_msg.pack(anchor='w', pady=(0, 6))

        def show_msg(text):
            lbl_msg.configure(text=text)
            dlg.after(3000, lambda: lbl_msg.configure(text=''))

        def do_forgot():
            email = var_email.get().strip()
            if not email:
                show_msg('请先输入邮箱')
                return
            try:
                ok, msg = auth_client.reset_password(email)
                show_msg(msg)
            except Exception as e:
                show_msg(str(e) or '发送失败')

        lbl_forgot = tk.Label(main, text='忘记密码？', bg=lg_bg, fg=lg_accent,
                              font=('Microsoft YaHei UI', 9), cursor='hand2')
        lbl_forgot.pack(anchor='e', pady=(0, 12))
        lbl_forgot.bind('<ButtonRelease-1>', lambda e: do_forgot())

        def do_login():
            email = var_email.get().strip()
            pwd = var_pwd.get()
            if not email or not pwd:
                show_msg('请输入邮箱和密码')
                return
            try:
                ok, msg = auth_client.login(email, pwd)
                if ok:
                    dlg.destroy()
                else:
                    show_msg(msg)
            except Exception as e:
                show_msg(str(e) or '登录失败')

        def do_register():
            email = var_email.get().strip()
            pwd = var_pwd.get()
            if not email or not pwd:
                show_msg('请输入邮箱和密码')
                return
            try:
                ok, msg = auth_client.register(email, pwd)
                if ok:
                    dlg.destroy()
                else:
                    show_msg(msg)
            except Exception as e:
                show_msg(str(e) or '注册失败')

        btn_container = tk.Frame(main, bg=lg_bg)
        btn_container.pack(fill=tk.X, pady=(0, 4))
        tk.Frame(btn_container, bg=lg_bg).pack(side=tk.LEFT, expand=True)
        btn_frm = tk.Frame(btn_container, bg=lg_bg)
        btn_frm.pack(side=tk.LEFT)
        for txt, cmd in [('登录', do_login), ('注册', do_register)]:
            b = tk.Button(btn_frm, text=txt, command=cmd,
                         bg=lg_accent, fg='white', activebackground=lg_muted,
                         relief='flat', font=('Microsoft YaHei UI', 11),
                         padx=24, pady=10, cursor='hand2')
            b.pack(side=tk.LEFT, padx=(0, 12))
        tk.Frame(btn_container, bg=lg_bg).pack(side=tk.LEFT, expand=True)

        dlg.update_idletasks()
        dw = dlg.winfo_reqwidth()
        dh = dlg.winfo_reqheight()
        hwnd = getattr(self, '_hwnd', None)
        work = get_monitor_work_rect(hwnd) if hwnd else None
        if work:
            l, t, r, b = work
            mw, mh = r - l, b - t
            x = l + (mw - dw) // 2
            y = t + (mh - dh) // 2
        else:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = (sw - dw) // 2
            y = (sh - dh) // 2
        dlg.geometry(f'+{x}+{y}')
        ent_email.focus_set()

    def _check_feature_and_run(self, feature_key, run, prompt='该功能需要登录'):
        if not AUTH_AVAILABLE:
            run()
            return
        try:
            if auth_client.can_use_feature(feature_key):
                run()
            else:
                self._show_login_dialog()
                # 不执行 run
        except Exception:
            run()

    # ─ 子菜单构建 ─

    def _build_icon_submenu(self, parent):
        for key, label in self._icon_names.items():
            self._add_sub_radio(
                parent, label, key == self._current_icon,
                lambda k=key: self._check_feature_and_run('all_icons', lambda kk=k: self._switch_icon(kk))
            )

    def _build_mode_submenu(self, parent):
        for key, cfg in BREATHING_MODES.items():
            self._add_sub_radio(
                parent, cfg['name'], key == self._breathing_mode,
                lambda k=key: self._check_feature_and_run(f'{k}_mode', lambda kk=k: self._switch_mode(kk))
            )

    def _build_sound_submenu(self, parent):
        cur = self._sound_mode_var.get()
        if cur not in ('off', 'immersive'):
            self._sound_mode_var.set('off')
        sound_opts = [
            ('off', '关'),
            ('immersive', '开'),
        ]
        cur = self._sound_mode_var.get()
        for val, label in sound_opts:
            def make_cb(v):
                def cb():
                    if v == 'off':
                        self._menu_switch_sound(v)
                    else:
                        self._check_feature_and_run('sound', lambda: self._menu_switch_sound(v))
                return cb
            self._add_sub_radio(parent, label, val == cur, make_cb(val))

    def _build_color_submenu(self, parent):
        bg = getattr(self, '_menu_bg', self._MENU_BG)
        hv = getattr(self, '_menu_hover', self._MENU_HOVER_BG)
        for key, label in self._color_names.items():
            hex_color = self._color_hex[key]
            selected = key == self._current_color
            prefix = '●' if selected else '○'
            frm = tk.Frame(parent, bg=bg, cursor='hand2')
            frm.pack(fill=tk.X, pady=0)
            # 色块圆点
            dot = tk.Canvas(frm, width=14, height=14, bg=bg,
                            highlightthickness=0)
            dot.create_oval(1, 1, 13, 13, fill=hex_color, outline=hex_color)
            dot.pack(side=tk.LEFT, padx=(16, 4), pady=2)
            # 文字
            lbl = tk.Label(
                frm, text=f'{prefix}  {label}', anchor='w',
                bg=bg, fg='#c0c0c0',
                font=self._MENU_FONT, pady=2,
            )
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

            def hover_in(ev, f=frm, d=dot, l=lbl, h=hv):
                f.configure(bg=h)
                d.configure(bg=h)
                l.configure(bg=h)
            def hover_out(ev, f=frm, d=dot, l=lbl, b=bg):
                f.configure(bg=b)
                d.configure(bg=b)
                l.configure(bg=b)
            def click(ev, k=key):
                self._menu_exec(lambda: self._check_feature_and_run('all_colors', lambda kk=k: self._switch_color(kk)))

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
        self._hover_tip_label = lbl

    def _update_tooltip(self, e, text):
        if self._hover_tip and self._hover_tip_label:
            self._hover_tip_label.configure(text=text)
            self._hover_tip.update_idletasks()
            tw = self._hover_tip.winfo_reqwidth()
            th = self._hover_tip.winfo_reqheight()
            sw = self.root.winfo_screenwidth()
            tx = e.x_root + 12
            ty = e.y_root - th - 8
            if tx + tw > sw:
                tx = e.x_root - tw - 8
            if ty < 0:
                ty = e.y_root + 18
            self._hover_tip.geometry(f'+{tx}+{ty}')
        else:
            self._show_tooltip(e, text)

    def _on_motion(self, e):
        if self.immersive:
            self._ripple_time = time.time()
            self._update_tooltip(e, '双击呼吸球 → 背景模式')
        else:
            self.root.configure(cursor='arrow')

    def _on_hover_enter(self, e):
        self._ripple_time = time.time()
        if self.immersive:
            self._on_motion(e)
        else:
            self._show_tooltip(e, '双击呼吸球 → 沉浸模式')

    def _on_hover_leave(self, e):
        if self._hover_tip:
            self._hover_tip.destroy()
            self._hover_tip = None
            self._hover_tip_label = None

    # ─── 系统托盘 ───

    def _setup_tray(self):
        # 优先使用应用图标， fallback 为绿色圆点
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ico_path = os.path.join(base_dir, 'app_icon.ico')
        png_path = os.path.join(base_dir, 'app_icon.png')
        if os.path.exists(png_path):
            img = Image.open(png_path).convert('RGBA').resize((64, 64), Image.LANCZOS)
        elif os.path.exists(ico_path):
            img = Image.open(ico_path).convert('RGBA').resize((64, 64), Image.LANCZOS)
        else:
            img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse([8, 8, 56, 56], fill=(*PRIMARY, 180))

        def _tray_go_immersive(icon, item):
            self.root.after(0, lambda: self.restore(to_immersive=True))

        def _tray_go_background(icon, item):
            self.root.after(0, lambda: self.restore(to_immersive=False))

        def _build_tray_menu():
            return (
                pystray.MenuItem(
                    '沉浸模式',
                    _tray_go_immersive,
                    checked=lambda item: self.immersive,
                    default=self.immersive,
                ),
                pystray.MenuItem(
                    '背景模式',
                    _tray_go_background,
                    checked=lambda item: not self.immersive,
                    default=not self.immersive,
                ),
                pystray.MenuItem('显示呼吸球', lambda icon, item: self.root.after(0, self.bring_back_window)),
                pystray.MenuItem('最小化', lambda icon, item: self.root.after(0, self.minimize)),
                pystray.MenuItem('退出', lambda icon, item: self.root.after(0, self.quit)),
            )

        menu = pystray.Menu(_build_tray_menu)
        self.tray_icon = pystray.Icon('mindful_breathing_local', img, '呼吸泡泡', menu)
        self.tray_icon.run()

    # ─── 开机自启动 ───

    REG_PATH = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
    REG_NAME = 'BreathingBallLocal'

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
                if getattr(sys, 'frozen', False):
                    cmd = f'"{sys.executable}"'
                else:
                    cmd = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, self.REG_NAME, 0, winreg.REG_SZ, cmd)
                winreg.CloseKey(key)
                self.auto_start_var.set(True)
            except Exception:
                pass


def _show_activation_dialog():
    """首次激活弹窗，返回 True 表示已激活可继续，False 表示用户退出。未激活则不可用。"""
    try:
        import activation_client
    except ImportError:
        return False  # 无激活模块则不可运行
    if activation_client.is_activated():
        return True
    root = tk.Tk()
    root.withdraw()
    lg_bg, lg_card, lg_accent, lg_muted = '#f2faf9', '#e8f6f5', '#6db3a8', '#408a82'
    dlg = tk.Toplevel(root)
    dlg.title('呼吸泡泡 - 激活')
    dlg.resizable(False, False)
    dlg.configure(bg=lg_bg)
    dlg.attributes('-topmost', True)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ico = os.path.join(base_dir, 'app_icon.ico')
    if os.path.exists(ico):
        try:
            dlg.iconbitmap(ico)
        except Exception:
            pass
    main = tk.Frame(dlg, bg=lg_bg, padx=32, pady=24)
    main.pack()
    tk.Label(main, text='呼吸泡泡', bg=lg_bg, fg=lg_accent,
             font=('Microsoft YaHei UI', 20, 'bold')).pack(pady=(0, 2))
    tk.Label(main, text='请输入激活码', bg=lg_bg, fg=lg_muted,
             font=('Microsoft YaHei UI', 10)).pack(pady=(0, 12))
    var_code = tk.StringVar()
    ent = tk.Entry(main, textvariable=var_code, width=24,
                   bg='white', fg='#333', font=('Microsoft YaHei UI', 12),
                   relief='flat', highlightthickness=1, highlightcolor=lg_accent)
    ent.pack(ipady=10, ipadx=12, pady=(0, 8))
    lbl_msg = tk.Label(main, text='', bg=lg_bg, fg='#e06666', font=('Microsoft YaHei UI', 9))
    lbl_msg.pack(pady=(0, 12))
    activated = [False]
    def do_activate():
        ok, msg = activation_client.activate(var_code.get().strip())
        if ok:
            activated[0] = True
            dlg.destroy()
        else:
            lbl_msg.configure(text=msg)
    tk.Button(main, text='激 活', command=do_activate,
              bg=lg_accent, fg='white', activebackground=lg_muted,
              relief='flat', font=('Microsoft YaHei UI', 11),
              padx=32, pady=10, cursor='hand2').pack(pady=(0, 8))
    def _on_close():
        activated[0] = False
        dlg.destroy()
    dlg.protocol('WM_DELETE_WINDOW', _on_close)
    dlg.update_idletasks()
    dw, dh = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    dlg.geometry(f'+{(sw-dw)//2}+{(sh-dh)//2}')
    ent.focus_set()
    dlg.grab_set()
    root.wait_window(dlg)
    root.destroy()
    return activated[0]

if __name__ == '__main__':
    if not _show_activation_dialog():
        sys.exit(0)
    app = BreathingBall()
    app.run()
