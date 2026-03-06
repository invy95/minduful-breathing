# -*- coding: utf-8 -*-
import sys
import os
import tkinter as tk
import ctypes
if sys.platform == 'win32':
    import ctypes.wintypes
import math
import random
import time
import threading
import struct
import subprocess
if sys.platform == 'win32':
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
    import pystray
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

try:
    from dotenv import load_dotenv
    _base = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(_base, 'backend', '.env'))
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        load_dotenv(os.path.join(exe_dir, '.env'))
        load_dotenv(os.path.join(os.getcwd(), '.env'))  # 快捷方式可能改变 cwd
    else:
        load_dotenv(os.path.join(_base, '.env'))
except Exception:
    pass

try:
    import auth_client
    _auth_imported = True
except ImportError:
    _auth_imported = False
AUTH_AVAILABLE = False  # 纯激活码模式，不需要登录注册
try:
    import activation_client
    ACTIVATION_AVAILABLE = True
except ImportError:
    ACTIVATION_AVAILABLE = False

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

COMPACT_W, COMPACT_H = 140, 180
IMMERSIVE_W, IMMERSIVE_H = 420, 560


# ─── 平台相关：Win32 分层窗口 / Mac Canvas 渲染 ───

IS_WIN = sys.platform == 'win32'
IS_MAC = sys.platform == 'darwin'

if IS_WIN:
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
    """获取窗口所在显示器的工作区域 (left, top, right, bottom)"""
    if IS_WIN:
        try:
            hmon = ctypes.windll.user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                return (mi.rcWork.left, mi.rcWork.top, mi.rcWork.right, mi.rcWork.bottom)
        except Exception:
            pass
    return None


def clamp_to_visible(x, y, w, h, root=None):
    """确保坐标在可见范围内。Mac 需传入 root 获取屏幕尺寸。"""
    if IS_WIN:
        try:
            SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
            SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
            vx = ctypes.windll.user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            vy = ctypes.windll.user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            vw = ctypes.windll.user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vh = ctypes.windll.user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            x = max(vx, min(x, vx + vw - w - 1))
            y = max(vy, min(y, vy + vh - h - 1))
        except Exception:
            pass
    elif root:
        try:
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            x = max(0, min(x, sw - w - 1))
            y = max(0, min(y, sh - h - 1))
        except Exception:
            pass
    return x, y


def _get_shortcut_marker_path():
    """快捷方式询问标记文件路径（Windows/Mac 共用）"""
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA', '') or os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
    else:
        base = os.path.expanduser('~/Library/Application Support')
    return os.path.abspath(os.path.join(base, 'MindfulBreathing', 'shortcut_asked'))


def _ask_and_create_desktop_shortcut(root):
    """首次启动时弹窗询问是否创建桌面快捷方式；已有快捷方式不再创建；之后不再询问。"""
    if not getattr(sys, 'frozen', False):
        return
    marker_file = _get_shortcut_marker_path()
    if os.path.exists(marker_file):
        return
    try:
        from tkinter import messagebox
        root.lift()
        root.attributes('-topmost', True)
        root.after(100, lambda: root.attributes('-topmost', False))
        ok = messagebox.askyesno('呼吸泡泡', '是否在桌面创建快捷方式？\n\n选择「是」将创建桌面快捷方式，便于下次启动。\n选择「否」将不再询问。', parent=root)
        if sys.platform == 'win32':
            exe_path = os.path.abspath(sys.executable)
            work_dir = os.path.dirname(exe_path)
            CSIDL_DESKTOPDIRECTORY = 0x0010
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(0, CSIDL_DESKTOPDIRECTORY, 0, 0, buf) != 0:
                _write_shortcut_marker(marker_file)
                return
            desktop = buf.value
            shortcut_path = os.path.join(desktop, '\u547b\u5438\u6ce1\u6ce1.lnk')
            if ok and not os.path.exists(shortcut_path):
                _create_shortcut_win32(exe_path, work_dir, shortcut_path)
        elif sys.platform == 'darwin':
            # Mac: sys.executable 指向 .app/Contents/MacOS/xxx，app 路径为上三层
            exe_path = os.path.abspath(sys.executable)
            app_path = os.path.dirname(os.path.dirname(os.path.dirname(exe_path)))
            desktop = os.path.expanduser('~/Desktop')
            alias_path = os.path.join(desktop, '\u547b\u5438\u6ce1\u6ce1.app')
            if ok and not os.path.exists(alias_path):
                script = f'tell application "Finder" to make alias file at (path to desktop folder) to (POSIX file "{app_path}")'
                try:
                    subprocess.run(['osascript', '-e', script], capture_output=True, timeout=5)
                except Exception:
                    pass
        _write_shortcut_marker(marker_file)
    except Exception:
        try:
            _write_shortcut_marker(marker_file)
        except Exception:
            pass


def _create_shortcut_win32(exe_path, work_dir, shortcut_path):
    """用 win32com 创建快捷方式，不弹出控制台窗口，名称即文件名（无「-快捷方式」后缀）。"""
    try:
        import win32com.client
        shell = win32com.client.Dispatch('WScript.Shell')
        shortcut = shell.CreateShortcut(shortcut_path)
        shortcut.TargetPath = exe_path
        shortcut.WorkingDirectory = work_dir
        shortcut.IconLocation = exe_path + ',0'
        shortcut.Description = '\u547b\u5438\u6ce1\u6ce1'
        shortcut.Save()
    except ImportError:
        # 打包环境无 win32com，使用 powershell（隐藏窗口）
        try:
            cf = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            env = dict(os.environ)
            env['BB_EXE'] = exe_path
            env['BB_DIR'] = work_dir
            env['BB_LNK'] = shortcut_path
            subprocess.run(
                ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command',
                 '$w=New-Object -ComObject WScript.Shell;$s=$w.CreateShortcut($env:BB_LNK);'
                 '$s.TargetPath=$env:BB_EXE;$s.WorkingDirectory=$env:BB_DIR;'
                 '$s.IconLocation=$env:BB_EXE+\',0\';$s.Save()'],
                capture_output=True, timeout=10, env=env, creationflags=cf,
            )
        except Exception:
            pass


def _write_shortcut_marker(marker_file):
    try:
        os.makedirs(os.path.dirname(marker_file), exist_ok=True)
        with open(marker_file, 'w') as f:
            f.write('1')
    except Exception:
        pass


def update_layered(hwnd, pil_rgba, pos=None):
    """用 RGBA 图片更新分层窗口（仅 Windows）。Mac 使用 Canvas 渲染。"""
    if not IS_WIN:
        return
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
    if IS_WIN:
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
    else:
        def __init__(self):
            pass
        def get_idle_seconds(self):
            return 0.0  # Mac 暂不支持空闲检测


class BreathingBall:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # 先隐藏，等首帧渲染完成再显示，避免加载时闪烁
        self.root.title('呼吸泡泡')
        _base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        if IS_WIN:
            _ico = os.path.join(_base, 'app_icon.ico')
            if os.path.exists(_ico):
                try:
                    self.root.iconbitmap(_ico)
                except Exception:
                    pass
        else:
            _png = os.path.join(_base, 'app_icon.png')
            if not os.path.exists(_png):
                _png = os.path.join(_base, 'login_logo.png')
            if os.path.exists(_png):
                try:
                    _img = Image.open(_png).convert('RGBA').resize((64, 64), Image.LANCZOS)
                    from PIL import ImageTk
                    self.root.iconphoto(True, ImageTk.PhotoImage(_img))
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
        # 打包版首次启动：弹窗询问是否创建桌面快捷方式（仅询问一次）
        if getattr(sys, 'frozen', False):
            self.root.after(800, lambda: _ask_and_create_desktop_shortcut(self.root))

    def _init_layered(self):
        self.root.update_idletasks()
        if IS_WIN:
            self._hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if self._hwnd == 0:
                self._hwnd = self.root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
            self._hwnd = self._hwnd  # 确保 _animate 中 hasattr 为 True
        else:
            self._mac_canvas = tk.Canvas(self.root, width=self.win_w, height=self.win_h,
                                         bg='black', highlightthickness=0)
            self._mac_canvas.pack(fill=tk.BOTH, expand=True)
            self._mac_photo = None
            for ev, cb in [
                ('<ButtonPress-1>', self._on_drag_start),
                ('<B1-Motion>', self._on_drag_motion),
                ('<ButtonRelease-1>', self._on_click),
                ('<Double-Button-1>', self._on_double_click),
                ('<Button-2>', self._on_right_click),
                ('<Enter>', self._on_hover_enter),
                ('<Leave>', self._on_hover_leave),
                ('<Motion>', self._on_motion),
            ]:
                self._mac_canvas.bind(ev, cb)
        self._animate()
        self.root.deiconify()  # 首帧已渲染，再显示窗口，避免加载时闪烁

    def run(self):
        self.root.mainloop()

    # ─── 字体 ───

    def _get_font(self, size):
        if size not in self._font_cache:
            if IS_WIN:
                fonts_dir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
                names = ['msyh.ttc', 'msyhbd.ttc', 'simhei.ttf', 'simsun.ttc', 'segoeui.ttf']
            else:
                fonts_dir = '/System/Library/Fonts/Supplemental'
                names = ['PingFang.ttc', 'STHeiti Light.ttc', 'Helvetica.ttc', 'Arial.ttf']
            for name in names:
                try:
                    path = os.path.join(fonts_dir, name)
                    if os.path.exists(path):
                        self._font_cache[size] = ImageFont.truetype(path, size)
                        break
                except Exception:
                    continue
            else:
                try:
                    self._font_cache[size] = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', size)
                except Exception:
                    self._font_cache[size] = ImageFont.load_default()
        return self._font_cache[size]

    # ─── 窗口 ───

    def _position_bottom_right(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f'+{sw - self.win_w - 30}+{sh - self.win_h - 60}')

    def _move_window(self, x, y, w, h):
        if IS_WIN and hasattr(self, '_hwnd'):
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            ctypes.windll.user32.SetWindowPos(
                self._hwnd, 0, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE
            )
        elif IS_MAC and hasattr(self, '_mac_canvas'):
            self._mac_canvas.configure(width=w, height=h)
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
        x, y = clamp_to_visible(x, y, self.win_w, self.win_h, self.root)
        self.current_prompt = random.choice(PROMPTS)
        self._update_tray_menu()

        if IS_WIN and hasattr(self, '_hwnd'):
            frame = self._render_frame()
            update_layered(self._hwnd, frame, pos=(x, y))
            SWP_NOZORDER, SWP_NOACTIVATE, SWP_NOREDRAW = 0x0004, 0x0010, 0x0008
            ctypes.windll.user32.SetWindowPos(
                self._hwnd, 0, x, y, self.win_w, self.win_h,
                SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOREDRAW
            )
        else:
            if hasattr(self, '_mac_canvas'):
                self._mac_canvas.configure(width=self.win_w, height=self.win_h)
            self.root.geometry(f'{self.win_w}x{self.win_h}+{x}+{y}')

    def _play_sound(self):
        if not os.path.exists(self._sound_path):
            return
        if IS_WIN:
            winsound.PlaySound(
                self._sound_path,
                winsound.SND_FILENAME | winsound.SND_LOOP | winsound.SND_ASYNC
            )
        else:
            try:
                self._sound_proc = subprocess.Popen(
                    ['afplay', '-l', '999', self._sound_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception:
                self._sound_proc = None

    def _stop_sound(self):
        if IS_WIN:
            winsound.PlaySound(None, winsound.SND_PURGE)
        else:
            proc = getattr(self, '_sound_proc', None)
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
            self._sound_proc = None

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
        x, y = clamp_to_visible(x, y, self.win_w, self.win_h, self.root)
        if IS_WIN and hasattr(self, '_hwnd'):
            try:
                frame = self._render_frame()
                update_layered(self._hwnd, frame, pos=(x, y))
                SWP_NOZORDER, SWP_NOACTIVATE, SWP_NOREDRAW = 0x0004, 0x0010, 0x0008
                ctypes.windll.user32.SetWindowPos(
                    self._hwnd, 0, x, y, self.win_w, self.win_h,
                    SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOREDRAW
                )
            except Exception:
                pass
        elif hasattr(self, '_mac_canvas'):
            self._mac_canvas.configure(width=self.win_w, height=self.win_h)
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
        x, y = clamp_to_visible(x, y, self.win_w, self.win_h, self.root)
        if IS_WIN and hasattr(self, '_hwnd'):
            try:
                frame = self._render_frame()
                update_layered(self._hwnd, frame, pos=(x, y))
                SWP_NOZORDER, SWP_NOACTIVATE, SWP_NOREDRAW = 0x0004, 0x0010, 0x0008
                ctypes.windll.user32.SetWindowPos(
                    self._hwnd, 0, x, y, self.win_w, self.win_h,
                    SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOREDRAW
                )
            except Exception:
                pass
        elif hasattr(self, '_mac_canvas'):
            self._mac_canvas.configure(width=self.win_w, height=self.win_h)
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
                rotated = self._flower_base.rotate(-rot_angle, resample=Image.BICUBIC, expand=False)  # 负角度=顺时针
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
        if IS_WIN and not hasattr(self, '_hwnd'):
            self.root.after(100, self._animate)
            return
        if IS_MAC and not hasattr(self, '_mac_canvas'):
            self.root.after(100, self._animate)
            return
        try:
            frame = self._render_frame()
            if IS_WIN:
                update_layered(self._hwnd, frame)
                if self.immersive:
                    HWND_TOPMOST = -1
                    SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x0002, 0x0001, 0x0010
                    ctypes.windll.user32.SetWindowPos(
                        self._hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                    )
            else:
                # Mac: Canvas 渲染
                from PIL import ImageTk
                bg_rgb = (0, 0, 0)
                rgb = Image.new('RGB', frame.size, bg_rgb)
                rgb.paste(frame, (0, 0), frame)
                self._mac_photo = ImageTk.PhotoImage(rgb)
                self._mac_canvas.delete('all')
                self._mac_canvas.create_image(0, 0, anchor=tk.NW, image=self._mac_photo)
                if self.immersive:
                    self.root.attributes('-topmost', True)
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
            font=self._MENU_FONT, padx=8, pady=3, cursor='hand2',
        )
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        arrow = tk.Label(
            frm, text='▾', anchor='e',
            bg=bg, fg='#d6d6d6',
            font=self._MENU_FONT, padx=6, pady=3, cursor='hand2',
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

    def _show_activation_dialog(self):
        """菜单中打开激活弹窗（与注册页同风格，仅激活码）"""
        self._close_custom_menu()
        _run_activation_gate([None])

    def _show_login_dialog(self):
        """登录/注册页已改为仅激活码，保留方法名供 _check_feature_and_run 调用"""
        self._show_activation_dialog()

    def _check_feature_and_run(self, feature_key, run, prompt='该功能需要登录'):
        if ACTIVATION_AVAILABLE and not activation_client.is_activated():
            self._show_activation_dialog()
            return
        if AUTH_AVAILABLE:
            try:
                if auth_client.can_use_feature(feature_key):
                    run()
                else:
                    self._show_login_dialog()
            except Exception:
                run()
        else:
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
                            highlightthickness=0, cursor='hand2')
            dot.create_oval(1, 1, 13, 13, fill=hex_color, outline=hex_color)
            dot.pack(side=tk.LEFT, padx=(16, 4), pady=2)
            # 文字
            lbl = tk.Label(
                frm, text=f'{prefix}  {label}', anchor='w',
                bg=bg, fg='#c0c0c0',
                font=self._MENU_FONT, pady=2, cursor='hand2',
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
        self._update_tray_menu()

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
        # Windows 下将托盘左键改为双击显示呼吸球（pystray 默认是单击）
        if HAS_TRAY and sys.platform == 'win32':
            try:
                import pystray._win32 as _win32
                from pystray._util import win32
                WM_LBUTTONDBLCLK = 0x0203
                _orig_on_notify = _win32.Icon._on_notify
                def _on_notify_dblclick(self, wparam, lparam):
                    if lparam == WM_LBUTTONDBLCLK:
                        self()
                    elif self._menu_handle and lparam == win32.WM_RBUTTONUP:
                        win32.SetForegroundWindow(self._hwnd)
                        point = ctypes.wintypes.POINT()
                        win32.GetCursorPos(ctypes.byref(point))
                        hmenu, descriptors = self._menu_handle
                        index = win32.TrackPopupMenuEx(
                            hmenu,
                            win32.TPM_RIGHTALIGN | win32.TPM_BOTTOMALIGN | win32.TPM_RETURNCMD,
                            point.x, point.y, self._menu_hwnd, None)
                        if index > 0:
                            descriptors[index - 1](self)
                _win32.Icon._on_notify = _on_notify_dblclick
            except Exception:
                pass
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
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

        def _build_tray_menu():
            return (
                pystray.MenuItem(
                    '开机自启动',
                    lambda icon, item: self.root.after(0, self._menu_toggle_auto_start),
                    checked=lambda item: self._is_auto_start(),
                ),
                pystray.MenuItem('最小化', lambda icon, item: self.root.after(0, self.minimize)),
                pystray.MenuItem('退出', lambda icon, item: self.root.after(0, self.quit)),
            )

        menu = pystray.Menu(_build_tray_menu)
        self.tray_icon = pystray.Icon(
            'mindful_breathing', img, '呼吸泡泡', menu,
            on_activate=lambda icon, item: self.root.after(0, self.bring_back_window),
        )
        self.tray_icon.run()

    # ─── 开机自启动 ───

    if IS_WIN:
        REG_PATH = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
        REG_NAME = 'MindfulBreathing'

    def _is_auto_start(self):
        if IS_WIN:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_READ)
                val, _ = winreg.QueryValueEx(key, self.REG_NAME)
                winreg.CloseKey(key)
                # 若已开启自启动但用的是 python.exe（会弹控制台），自动修正为 pythonw.exe
                if not getattr(sys, 'frozen', False) and val and 'python.exe' in val.lower() and 'pythonw.exe' not in val.lower():
                    py_dir = os.path.dirname(sys.executable)
                    pythonw = os.path.join(py_dir, 'pythonw.exe')
                    if os.path.isfile(pythonw):
                        try:
                            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_SET_VALUE)
                            winreg.SetValueEx(k, self.REG_NAME, 0, winreg.REG_SZ, f'"{pythonw}" "{os.path.abspath(__file__)}"')
                            winreg.CloseKey(k)
                        except Exception:
                            pass
                return True
            except Exception:
                return False
        else:
            plist = os.path.expanduser('~/Library/LaunchAgents/com.mindful.breathing.plist')
            return os.path.exists(plist)

    def _toggle_auto_start(self):
        if IS_WIN:
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
                        # 使用 pythonw.exe 避免开机自启动时弹出黑色控制台窗口
                        py_dir = os.path.dirname(sys.executable)
                        pythonw = os.path.join(py_dir, 'pythonw.exe')
                        if os.path.isfile(pythonw):
                            cmd = f'"{pythonw}" "{os.path.abspath(__file__)}"'
                        else:
                            cmd = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_SET_VALUE)
                    winreg.SetValueEx(key, self.REG_NAME, 0, winreg.REG_SZ, cmd)
                    winreg.CloseKey(key)
                    self.auto_start_var.set(True)
                except Exception:
                    pass
        else:
            plist = os.path.expanduser('~/Library/LaunchAgents/com.mindful.breathing.plist')
            if os.path.exists(plist):
                try:
                    os.remove(plist)
                    self.auto_start_var.set(False)
                except Exception:
                    pass
            else:
                try:
                    os.makedirs(os.path.dirname(plist), exist_ok=True)
                    exe = sys.executable if getattr(sys, 'frozen', False) else sys.executable
                    # Mac 打包后可能为 .app/Contents/MacOS/呼吸泡泡
                    plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>Label</key><string>com.mindful.breathing</string>
    <key>ProgramArguments</key><array><string>{exe}</string></array>
    <key>RunAtLoad</key><true/>
</dict></plist>'''
                    with open(plist, 'w', encoding='utf-8') as f:
                        f.write(plist_content)
                    self.auto_start_var.set(True)
                except Exception:
                    pass


def _run_activation_gate(result, show_network_hint=False):
    """
    独立激活弹窗，与注册页同风格。仅未激活时显示。
    使用单一 Tk 窗口，先隐藏等 UI 构建完成再显示，避免加载时闪烁。
    """
    lg_bg, lg_card, lg_accent, lg_muted = '#f2faf9', '#e8f6f5', '#6db3a8', '#408a82'
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    root = tk.Tk()
    root.withdraw()  # 先隐藏，等 UI 构建完成再显示
    root.title('呼吸泡泡 - 激活')
    root.resizable(False, False)
    root.configure(bg=lg_bg)
    if IS_WIN:
        ico_path = os.path.join(base_dir, 'app_icon.ico')
        if os.path.exists(ico_path):
            try:
                root.iconbitmap(ico_path)
            except Exception:
                pass
    else:
        for p in [os.path.join(base_dir, 'app_icon.png'), os.path.join(base_dir, 'login_logo.png')]:
            if os.path.exists(p):
                try:
                    from PIL import ImageTk
                    img = Image.open(p).convert('RGBA').resize((64, 64), Image.LANCZOS)
                    root.iconphoto(True, ImageTk.PhotoImage(img))
                    break
                except Exception:
                    pass
    main = tk.Frame(root, bg=lg_bg, padx=32, pady=24)
    main.pack()
    logo_path = os.path.join(base_dir, 'login_logo.png')
    if os.path.exists(logo_path):
        try:
            from PIL import ImageTk
            logo_img = Image.open(logo_path).convert('RGBA').resize((96, 96), Image.LANCZOS)
            bg_rgb = (0xf2, 0xfa, 0xf9)
            bg_layer = Image.new('RGB', logo_img.size, bg_rgb)
            bg_layer.paste(logo_img, (0, 0), logo_img)
            logo_photo = ImageTk.PhotoImage(bg_layer)
            lbl = tk.Label(main, image=logo_photo, bg=lg_bg)
            lbl.image = logo_photo
            lbl.pack(pady=(0, 4))
        except Exception:
            pass
    tk.Label(main, text='呼吸泡泡', bg=lg_bg, fg=lg_accent,
             font=('Microsoft YaHei UI', 20, 'bold')).pack(pady=(0, 2))
    tk.Label(main, text='Breathing · Meditation', bg=lg_bg, fg=lg_muted,
             font=('Microsoft YaHei UI', 10)).pack(pady=(0, 20))
    card = tk.Frame(main, bg=lg_card, padx=20, pady=16)
    card.pack(fill=tk.X, pady=(0, 12))
    tk.Label(card, text='激活码', bg=lg_card, fg=lg_muted,
             font=('Microsoft YaHei UI', 10)).pack(anchor='w', pady=(0, 4))
    var_code = tk.StringVar()
    ent_code = tk.Entry(card, textvariable=var_code, width=26,
                       bg='white', fg='#333', insertbackground='#333',
                       relief='flat', font=('Microsoft YaHei UI', 11))
    ent_code.pack(fill=tk.X, ipady=8, pady=(0, 8))
    ent_code.bind('<Return>', lambda e: do_activate())
    lbl_msg = tk.Label(main, text='', bg=lg_bg, fg='#e06666', font=('Microsoft YaHei UI', 9))
    lbl_msg.pack(anchor='w', pady=(0, 6))
    if show_network_hint:
        tk.Label(main, text='无法连接服务器，请检查网络后点击激活重试', bg=lg_bg, fg=lg_muted,
                 font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=(0, 4))
    def do_activate():
        ok, msg = activation_client.activate(var_code.get().strip())
        if ok:
            result[0] = True
            root.destroy()
        else:
            lbl_msg.configure(text=msg)
    btn_frm = tk.Frame(main, bg=lg_bg)
    btn_frm.pack(pady=(0, 8))
    tk.Button(btn_frm, text='激 活', command=do_activate,
             bg=lg_accent, fg='white', activebackground=lg_muted,
             relief='flat', font=('Microsoft YaHei UI', 11),
             padx=24, pady=10, cursor='hand2').pack()
    def on_close():
        result[0] = False
        root.destroy()
    root.protocol('WM_DELETE_WINDOW', on_close)
    root.update_idletasks()
    dw, dh = root.winfo_reqwidth(), root.winfo_reqheight()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f'+{(sw-dw)//2}+{(sh-dh)//2}')
    ent_code.focus_set()
    root.deiconify()  # UI 已就绪，再显示
    root.mainloop()

def _ensure_single_instance():
    """单实例锁：若已有实例在运行则直接退出，防止开机自启动等场景弹出两个呼吸泡泡。"""
    if not IS_WIN:
        return
    try:
        mutex_name = 'Global\\MindfulBreathing_SingleInstance'
        h = ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
        err = ctypes.windll.kernel32.GetLastError()
        if err == 183:  # ERROR_ALREADY_EXISTS，已有实例
            sys.exit(0)
    except Exception:
        pass


def _is_activated_local():
    """离线时检查本地激活缓存，若未过期则视为已激活，避免每次开机都弹窗。"""
    try:
        path = os.path.join(os.path.expanduser('~'), '.mindful_breathing', 'activation.json')
        if not os.path.exists(path):
            return False
        with open(path, 'r', encoding='utf-8') as f:
            data = __import__('json').load(f)
        exp = data.get('expires_at')
        if not exp:
            return False
        from datetime import datetime
        exp = exp.replace('Z', '+00:00')
        if 'T' in exp:
            exp_ts = datetime.fromisoformat(exp).timestamp()
            return exp_ts > datetime.now().timestamp()
    except Exception:
        pass
    return False


def _fix_auto_start_cmd():
    """若开机自启动仍使用 python.exe（会弹控制台），自动改为 pythonw.exe。"""
    if not IS_WIN or getattr(sys, 'frozen', False):
        return
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, BreathingBall.REG_PATH, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, BreathingBall.REG_NAME)
        winreg.CloseKey(key)
    except Exception:
        return
    if 'python.exe' not in val.lower() or 'pythonw.exe' in val.lower():
        return
    py_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(py_dir, 'pythonw.exe')
    if not os.path.isfile(pythonw):
        return
    new_cmd = f'"{pythonw}" "{os.path.abspath(__file__)}"'
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, BreathingBall.REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, BreathingBall.REG_NAME, 0, winreg.REG_SZ, new_cmd)
        winreg.CloseKey(key)
    except Exception:
        pass


if __name__ == '__main__':
    _ensure_single_instance()
    if IS_WIN and not getattr(sys, 'frozen', False):
        _fix_auto_start_cmd()
    # 未激活则完全不可用，必须激活后才能进入
    if not ACTIVATION_AVAILABLE:
        root_err = tk.Tk()
        root_err.withdraw()
        root_err.geometry('1x1+-10000+-10000')
        from tkinter import messagebox
        messagebox.showerror('错误', '缺少激活模块，无法运行。请使用完整安装包。')
        sys.exit(0)
    # 启动时检查激活（网络未就绪时自动重试 3 次，应对开机自启动）
    status, activated = activation_client.check_activation_with_retry(max_retries=3, delay_sec=4)
    if status == 'no_config':
        root_err = tk.Tk()
        root_err.withdraw()
        root_err.geometry('1x1+-10000+-10000')
        from tkinter import messagebox
        messagebox.showerror(
            '未配置激活服务',
            '请将 .env 文件（含 SUPABASE_URL、SUPABASE_ANON_KEY）放在程序同一目录。\n\n'
            '可从项目 backend/.env 复制到 exe 所在文件夹。'
        )
        sys.exit(0)
    network_failed = (status == 'offline')
    if activated:
        app = BreathingBall()
        app.run()
        sys.exit(0)
    # 离线时若本地有未过期激活缓存，视为已激活，避免每次开机都弹窗
    if status == 'offline' and _is_activated_local():
        app = BreathingBall()
        app.run()
        sys.exit(0)
    # 未激活或网络检测失败：显示激活弹窗，用户可重试
    result = [None]
    _run_activation_gate(result, show_network_hint=network_failed)
    if result[0] is not True:
        sys.exit(0)
    app = BreathingBall()
    app.run()
