# -*- coding: utf-8 -*-
"""
呼吸泡泡 - 登录/注册页预览
独立运行此脚本可单独查看登录页面设计，确认后再在主程序中使用
"""
import tkinter as tk
import sys
import os

# 模拟主程序的配色和布局
_THEME_LOGIN = {
    'red': ('#fdf5f5', '#fff0f0', '#c86464', '#8a5050'),
    'orange': ('#fdf8f2', '#fff5e8', '#d29b5a', '#8a7040'),
    'yellow': ('#fdfcf5', '#fffce8', '#c8be64', '#8a8640'),
    'green': ('#f2faf5', '#e8f8ef', '#64b478', '#408a58'),
    'blue': ('#f2f6fd', '#e8f0ff', '#648cc8', '#40608a'),
    'cyan': ('#f2faf9', '#e8f6f5', '#6db3a8', '#408a82'),
    'purple': ('#f8f5fd', '#f0e8ff', '#9678be', '#60508a'),
}

def show_preview(theme='cyan'):
    lg_bg, lg_card, lg_accent, lg_muted = _THEME_LOGIN.get(theme, _THEME_LOGIN['cyan'])
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(base_dir, 'app_icon.ico')
    logo_path = os.path.join(base_dir, 'login_logo.png')

    root = tk.Tk()
    root.title('呼吸泡泡 - 登录页预览')
    root.resizable(False, False)
    root.configure(bg=lg_bg)
    if os.path.exists(ico_path):
        try:
            root.iconbitmap(ico_path)
        except Exception:
            pass

    main = tk.Frame(root, bg=lg_bg, padx=32, pady=24)
    main.pack()

    # Logo
    if os.path.exists(logo_path):
        try:
            from PIL import Image, ImageTk
            logo_img = Image.open(logo_path).convert('RGBA')
            logo_img = logo_img.crop((0, 0, logo_img.width, int(logo_img.height * 0.55)))
            data = logo_img.getdata()
            new_data = []
            for item in data:
                r, g, b, a = item
                if r > 248 and g > 248 and b > 248:
                    new_data.append((r, g, b, 0))
                else:
                    new_data.append(item)
            logo_img.putdata(new_data)
            bg_rgb = tuple(int(lg_bg.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            bg_layer = Image.new('RGB', logo_img.size, bg_rgb)
            bg_layer.paste(logo_img, (0, 0), logo_img)
            logo_img = bg_layer.resize((100, 100), Image.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_img)
            tk.Label(main, image=logo_photo, bg=lg_bg).pack(pady=(0, 4))
            main.winfo_children()[-1].image = logo_photo
        except Exception:
            pass

    tk.Label(main, text='呼吸泡泡', bg=lg_bg, fg=lg_accent,
             font=('Microsoft YaHei UI', 20, 'bold')).pack(pady=(0, 2))
    tk.Label(main, text='Breathing · Meditation', bg=lg_bg, fg=lg_muted,
             font=('Microsoft YaHei UI', 10)).pack(pady=(0, 20))

    card = tk.Frame(main, bg=lg_card, padx=20, pady=16)
    card.pack(fill=tk.X, pady=(0, 12))

    tk.Label(card, text='邮箱', bg=lg_card, fg=lg_muted,
             font=('Microsoft YaHei UI', 10)).pack(anchor='w', pady=(0, 4))
    tk.Entry(card, width=26, bg='white', fg='#333', relief='flat',
             font=('Microsoft YaHei UI', 11)).pack(fill=tk.X, ipady=8, pady=(0, 14))

    tk.Label(card, text='密码', bg=lg_card, fg=lg_muted,
             font=('Microsoft YaHei UI', 10)).pack(anchor='w', pady=(0, 4))
    tk.Entry(card, width=26, show='●', bg='white', fg='#333', relief='flat',
             font=('Microsoft YaHei UI', 11)).pack(fill=tk.X, ipady=8, pady=(0, 8))

    tk.Label(main, text='忘记密码？', bg=lg_bg, fg=lg_accent,
             font=('Microsoft YaHei UI', 9), cursor='hand2').pack(anchor='e', pady=(0, 12))

    btn_container = tk.Frame(main, bg=lg_bg)
    btn_container.pack(fill=tk.X, pady=(0, 4))
    tk.Frame(btn_container, bg=lg_bg).pack(side=tk.LEFT, expand=True)
    btn_frm = tk.Frame(btn_container, bg=lg_bg)
    btn_frm.pack(side=tk.LEFT)
    for txt in ['登录', '注册']:
        b = tk.Button(btn_frm, text=txt,
                     bg=lg_accent, fg='white', relief='flat',
                     font=('Microsoft YaHei UI', 11), padx=24, pady=10)
        b.pack(side=tk.LEFT, padx=(0, 12))
    tk.Frame(btn_container, bg=lg_bg).pack(side=tk.LEFT, expand=True)

    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    root.geometry(f'+{(sw - w) // 2}+{(sh - h) // 2}')
    root.mainloop()

if __name__ == '__main__':
    theme = sys.argv[1] if len(sys.argv) > 1 else 'cyan'
    show_preview(theme)
