"""RoofStudio 0.5: editable concept plan, schedules and ASCII DXF export.
Geometry and quantities are preliminary, not structural verification.

UI редизайн: современный светлый интерфейс (карточки со скруглёнными углами,
единая палитра, аккуратная типографика). Расчётная логика, форматы файлов и
экспорт не менялись.
"""
import json
import math
import tkinter as tk
import traceback
import sys
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont

# Диагностический журнал в профиле пользователя; доступен и в собранном EXE.
def log_exception(exc_type, exc_value, exc_tb):
    details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        import os
        home = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "RoofStudio"
        home.mkdir(parents=True, exist_ok=True)
        with (home / "roofstudio_error.log").open("a", encoding="utf-8") as f:
            f.write("\n" + details)
    except Exception:
        pass
    return details


VERSION = '0.8'

# ---------------------------------------------------------------- палитра ---
APP_BG = '#EEF2F8'       # фон окна
SURFACE = '#FFFFFF'      # карточки
SOFT = '#F4F7FC'         # плитки, неактивные поля
BORDER = '#E1E7F0'       # тонкие границы
TEXT = '#162033'         # основной текст
MUTED = '#6B778C'        # второстепенный текст
BRAND = '#0F1B2D'        # шапка
BRAND_2 = '#9FB3CF'      # подзаголовок в шапке
PRIMARY = '#2563EB'
PRIMARY_H = '#1D4FD0'
PRIMARY_SOFT = '#E6EEFF'
GRID = '#E9EEF6'

DEFAULTS = {
    'name': 'Новый проект', 'length': 20, 'width': 12, 'eave': 0.6,
    'side': 7.3, 'end': 7.3, 'rafter_step': 1.0, 'rafter_size': '50×200',
    'lath_step': 0.4, 'lath_size': '50×150', 'cover': 'Профлист',
    'eave_height': 0.0, 'ridge_height': 3.2, 'complex_pitch': 28.0,
}
TABS = ('Геометрия', 'Контур здания', 'Чердак', 'Каталог ВШ', 'Разрез 1–1',
        'Стропильная система', 'Обрешётка', 'Элементы кровли', 'Ведомости', 'Документация')
KINDS = ('Вентшахта', 'Слуховое окно', 'Фановый стояк', 'Воронка', 'Ограждение')
PARAM_GROUPS = (
    ('ОБЪЕКТ', (('name', 'Объект'),)),
    ('ГАБАРИТЫ КРОВЛИ', (('length', 'Длина дома, м'), ('width', 'Ширина дома, м'),
                         ('eave', 'Свес, м'), ('side', 'Боковой скат, м'),
                         ('end', 'Торцевой скат, м'))),
    ('СТРОПИЛА И ОБРЕШЁТКА', (('rafter_step', 'Шаг стропил, м'),
                              ('rafter_size', 'Сечение стропил'),
                              ('lath_step', 'Шаг обрешётки, м'),
                              ('lath_size', 'Сечение обрешётки'))),
    ('ПОКРЫТИЕ', (('cover', 'Покрытие'),)),
    ('СЛОЖНАЯ КРОВЛЯ', (('eave_height', 'Отметка карниза, м'),
                        ('ridge_height', 'Отметка конька, м'),
                        ('complex_pitch', 'Уклон по умолчанию, °'))),
)
RESULT_ROWS = (('area', 'Общая площадь'), ('side_area', 'Боковые скаты'),
               ('end_area', 'Торцевые скаты'), ('ridge', 'Длина конька'),
               ('height', 'Высота подъёма'), ('slope', 'Уклон боковых'),
               ('rafters', 'Стропила (оценка)'), ('laths', 'Ряды обрешётки'),
               ('planes', 'Плоскости скатов'), ('valleys', 'Ендовы / рёбра'))
# сокращение, цвет метки на плане
OBJECT_STYLE = {
    'Вентшахта': ('ВШ', '#F97316'), 'Слуховое окно': ('ОС', '#0EA5E9'),
    'Фановый стояк': ('ФС', '#8B5CF6'), 'Воронка': ('ВВ', '#14B8A6'),
    'Ограждение': ('ОК', '#84CC16'),
}


def pick_family(root):
    import os
    if os.environ.get('ROOFSTUDIO_FONT'):
        return os.environ['ROOFSTUDIO_FONT']
    have = set(tkfont.families(root))
    for name in ('Segoe UI', 'Inter', 'Noto Sans', 'Open Sans', 'Roboto',
                 'Helvetica Neue', 'DejaVu Sans', 'Arial'):
        if name in have:
            return name
    return 'TkDefaultFont'




def resource_path(name):
    import os
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return str(Path(base) / name)

def round_rect(cv, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


class Card(tk.Frame):
    """Карточка со скруглёнными углами. Содержимое кладётся в card.body.
    fit=True  - высота подстраивается под содержимое;
    fit=False - карточка заполняет выделенное место."""

    def __init__(self, parent, bg=APP_BG, fill=SURFACE, outline=BORDER,
                 radius=14, pad=14, fit=False, width=None, height=None):
        super().__init__(parent, bg=bg)
        self.fill, self.outline, self.r, self.pad, self.fit = fill, outline, radius, pad, fit
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, width=width or 10,
                            height=height or 10)
        self.cv.pack(fill='both', expand=True)
        self.body = tk.Frame(self.cv, bg=fill)
        self.win = self.cv.create_window(pad, pad, window=self.body, anchor='nw')
        self.cv.bind('<Configure>', self._redraw)
        if fit:
            self.body.bind('<Configure>', self._fit)
            self.after_idle(self._fit)

    def _fit(self, _e=None):
        h = self.body.winfo_reqheight() + 2 * self.pad
        if getattr(self, '_fit_h', None) != h:
            self._fit_h = h
            self.cv.configure(height=h)

    def _redraw(self, _e=None):
        w, h = self.cv.winfo_width(), self.cv.winfo_height()
        self.cv.delete('bg')
        round_rect(self.cv, 1, 1, w - 1, h - 1, self.r, fill=self.fill,
                   outline=self.outline, width=1, tags='bg')
        self.cv.tag_lower('bg')
        opts = {'width': max(w - 2 * self.pad, 1)}
        if not self.fit:
            opts['height'] = max(h - 2 * self.pad, 1)
        self.cv.itemconfigure(self.win, **opts)
        if self.fit:
            self._fit()


class RoundButton(tk.Canvas):
    """Кнопка со скруглёнными углами и эффектом наведения."""
    STYLES = {
        'primary': dict(bg=PRIMARY, hover=PRIMARY_H, fg='#FFFFFF', line=PRIMARY),
        'ghost': dict(bg='#FFFFFF', hover='#EEF3FA', fg=TEXT, line=BORDER),
        'soft': dict(bg=PRIMARY_SOFT, hover='#D8E5FF', fg=PRIMARY, line=PRIMARY_SOFT),
    }

    def __init__(self, parent, text, command, style='ghost', font=None,
                 padx=14, pady=7, radius=10):
        self.st = self.STYLES[style]
        self.cmd = command
        self.r = radius
        w = font.measure(text) + 2 * padx
        h = font.metrics('linespace') + 2 * pady
        super().__init__(parent, width=w, height=h, bg=parent['bg'],
                         highlightthickness=0, bd=0, cursor='hand2')
        self.shape = round_rect(self, 1, 1, w - 1, h - 1, radius,
                                fill=self.st['bg'], outline=self.st['line'])
        self.create_text(w / 2, h / 2, text=text, font=font, fill=self.st['fg'])
        self.bind('<Enter>', lambda e: self.itemconfigure(self.shape, fill=self.st['hover']))
        self.bind('<Leave>', lambda e: self.itemconfigure(self.shape, fill=self.st['bg']))
        self.bind('<ButtonPress-1>', lambda e: self.itemconfigure(self.shape, fill=self.st['hover']))
        self.bind('<ButtonRelease-1>', self._release)

    def _release(self, e):
        if 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            self.cmd()


class RoofStudio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('RoofStudio v0.8 — Капитальный ремонт кровли')
        self._set_application_icon()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f'{min(1500, sw - 40)}x{min(890, sh - 90)}')
        self.minsize(1150, 700)
        self.configure(bg=APP_BG)
        self.setup_style()
        self.path = None
        self.objects = []
        self.selected = None
        self.mode = 'select'
        self.scale = 1
        self.ox = 0
        self.oy = 0
        self.values = {k: tk.StringVar(value=str(v)) for k, v in DEFAULTS.items()}
        self.status = tk.StringVar(value='Готово • предварительная модель, не рабочая документация')
        self.res = {k: tk.StringVar() for k in ('area', 'ridge', 'side_area', 'end_area',
                                                'slope', 'height', 'rafters', 'laths', 'items', 'planes', 'valleys')}
        self.report_callback_exception = self._callback_error
        self.build()
        self.recalc()
        self.bind('<Configure>', self.adapt)

    def _set_application_icon(self):
        try:
            self._icon_img=tk.PhotoImage(file=resource_path('app_icon.png'))
            self.iconphoto(True,self._icon_img)
        except Exception: pass
        try:
            self.iconbitmap(default=resource_path('app_icon.ico'))
        except Exception: pass

    def _callback_error(self, exc, value, tb):
        details = log_exception(exc, value, tb)
        messagebox.showerror('Ошибка RoofStudio',
                             'Выполнение команды завершилось ошибкой.\n'
                             'Журнал: %LOCALAPPDATA%\\RoofStudio\\roofstudio_error.log\n\n'
                             + str(value))

    # ------------------------------------------------------------ стили ---
    def setup_style(self):
        fam = pick_family(self)
        mk = lambda size, weight='normal': tkfont.Font(family=fam, size=size, weight=weight)
        self.f_base, self.f_bold = mk(10), mk(10, 'bold')
        self.f_small, self.f_cap, self.f_tiny = mk(9), mk(8, 'bold'), mk(8)
        self.f_h1, self.f_h2, self.f_val = mk(16, 'bold'), mk(14, 'bold'), mk(11, 'bold')
        self.f_btn, self.f_btn_b = mk(10), mk(10, 'bold')
        st = ttk.Style(self)
        st.theme_use('clam')
        st.configure('Field.TEntry', fieldbackground='#FFFFFF', foreground=TEXT,
                     bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                     insertcolor=TEXT, padding=(8, 5), relief='flat')
        st.map('Field.TEntry', bordercolor=[('focus', PRIMARY)],
               lightcolor=[('focus', PRIMARY)], darkcolor=[('focus', PRIMARY)])
        st.configure('Side.Treeview', background=SURFACE, fieldbackground=SURFACE,
                     foreground=TEXT, rowheight=32, borderwidth=0, relief='flat',
                     font=self.f_base, indent=14)
        st.map('Side.Treeview', background=[('selected', PRIMARY_SOFT)],
               foreground=[('selected', PRIMARY)])
        st.layout('Side.Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])
        st.configure('Table.Treeview', background=SURFACE, fieldbackground=SURFACE,
                     foreground=TEXT, rowheight=36, borderwidth=0, relief='flat',
                     font=self.f_base)
        st.map('Table.Treeview', background=[('selected', PRIMARY_SOFT)],
               foreground=[('selected', PRIMARY)])
        st.configure('Table.Treeview.Heading', background=SOFT, foreground=MUTED,
                     font=self.f_bold, relief='flat', borderwidth=0, padding=(10, 9))
        st.map('Table.Treeview.Heading', background=[('active', '#E9EFF8')])

    def button(self, parent, label, action, accent=False, side='left', padx=14):
        b = RoundButton(parent, label, action, 'primary' if accent else 'ghost',
                        self.f_btn_b if accent else self.f_btn, padx=padx)
        b.pack(side=side, padx=3, pady=3)
        return b

    # --------------------------------------------------------- построение ---
    def build(self):
        # --- шапка
        head = tk.Frame(self, bg=BRAND)
        head.pack(fill='x')
        logo = tk.Canvas(head, width=34, height=34, bg=BRAND, highlightthickness=0)
        round_rect(logo, 1, 1, 33, 33, 10, fill=PRIMARY, outline=PRIMARY)
        logo.create_text(17, 17, text='⌂', fill='white', font=(self.f_h1.actual('family'), 17, 'bold'))
        logo.pack(side='left', padx=(18, 10), pady=9)
        tk.Label(head, text='RoofStudio', bg=BRAND, fg='white', font=self.f_h1).pack(side='left')
        tk.Label(head, text='  |  Проект капитального ремонта кровли', bg=BRAND, fg=BRAND_2,
                 font=self.f_base).pack(side='left', pady=(3, 0))
        pill = tk.Canvas(head, width=134, height=28, bg=BRAND, highlightthickness=0)
        round_rect(pill, 1, 1, 133, 27, 13, fill='#1B2D47', outline='#2A4268')
        pill.create_text(67, 14, text='ПРОТОТИП v0.8', fill='#9CCBED', font=self.f_cap)
        pill.pack(side='right', padx=18)

        # --- панель инструментов
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill='x')
        inner = tk.Frame(bar, bg=SURFACE)
        inner.pack(fill='x', padx=14, pady=3)
        actions = (
            ('Создать', self.new), ('Открыть', self.load), ('Сохранить', self.save),
            ('Сохранить как', lambda: self.save(True)), None,
            ('Экспорт DXF', self.export_dxf), ('Экспорт CSV', self.export_csv),
            ('DWG', lambda: self.soon('Экспорт DWG')), ('PDF', lambda: self.soon('PDF')))
        for item in actions:
            if item is None:
                tk.Frame(inner, bg=BORDER, width=1, height=26).pack(side='left', padx=10)
                continue
            self.button(inner, item[0], item[1], item[0] == 'Экспорт DXF')
        self.button(inner, 'Настройки', lambda: self.soon('Настройки'), side='right')

        # --- вкладки
        self.tabsrow = tk.Frame(self, bg=SURFACE)
        self.tabsrow.pack(fill='x')
        tk.Frame(self.tabsrow, bg=BORDER, height=1).pack(side='bottom', fill='x')
        self.tabbuttons = {}
        self.tabmarks = {}
        for t in TABS:
            cell = tk.Frame(self.tabsrow, bg=SURFACE, cursor='hand2')
            cell.pack(side='left', padx=(14 if t == TABS[0] else 0, 0))
            lab = tk.Label(cell, text=t, bg=SURFACE, fg=MUTED, font=self.f_bold, padx=8, pady=8,
                           cursor='hand2')
            lab.pack()
            mark = tk.Frame(cell, bg=SURFACE, height=3)
            mark.pack(fill='x', padx=8)
            for w in (cell, lab):
                w.bind('<Button-1>', lambda e, t=t: self.switch(t))
                w.bind('<Enter>', lambda e, t=t: self.hover_tab(t, True))
                w.bind('<Leave>', lambda e, t=t: self.hover_tab(t, False))
            self.tabbuttons[t] = lab
            self.tabmarks[t] = mark

        # --- строка состояния (внизу окна)
        sbar = tk.Frame(self, bg=SURFACE)
        sbar.pack(side='bottom', fill='x')
        tk.Frame(sbar, bg=BORDER, height=1).pack(fill='x')
        dot = tk.Canvas(sbar, width=12, height=12, bg=SURFACE, highlightthickness=0)
        dot.create_oval(2, 2, 10, 10, fill='#22C55E', outline='')
        dot.pack(side='left', padx=(16, 8), pady=9)
        tk.Label(sbar, textvariable=self.status, bg=SURFACE, fg=MUTED, font=self.f_small,
                 anchor='w').pack(side='left', fill='x', expand=True, pady=6)

        # --- рабочая область
        main = tk.PanedWindow(self, orient='horizontal', bg=APP_BG, sashwidth=14, bd=0,
                              sashrelief='flat', opaqueresize=True)
        main.pack(fill='both', expand=True, padx=12, pady=(12, 10))

        left = Card(main)
        main.add(left, minsize=175, width=218, stretch='never')
        tk.Label(left.body, text='СТРУКТУРА ПРОЕКТА', bg=SURFACE, fg=MUTED, font=self.f_cap,
                 anchor='w').pack(fill='x', pady=(2, 8), padx=4)
        self.tree = ttk.Treeview(left.body, show='tree', style='Side.Treeview')
        self.tree.pack(fill='both', expand=True)
        rt = self.tree.insert('', 'end', text='▸ Проект', open=True)
        for t in TABS:
            self.tree.insert(rt, 'end', text=t)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self.switch(
            self.tree.item(self.tree.selection()[0], 'text'))
            if self.tree.selection() and self.tree.item(self.tree.selection()[0], 'text') in self.tabbuttons
            else None)

        center = tk.Frame(main, bg=APP_BG)
        main.add(center, minsize=510, stretch='always')
        self.center = center
        # плитки результатов
        self.kpi = Card(center, fit=True, pad=8)
        self.kpi.pack(fill='x', pady=(0, 10))
        self.tiles = []
        for key, label in RESULT_ROWS:
            tile = tk.Frame(self.kpi.body, bg=SOFT)
            tk.Label(tile, text=label, bg=SOFT, fg=MUTED, font=self.f_tiny, anchor='w').pack(
                fill='x', padx=7, pady=(6, 0))
            tk.Label(tile, textvariable=self.res[key], bg=SOFT, fg=TEXT, font=self.f_val,
                     anchor='w').pack(fill='x', padx=7, pady=(0, 6))
            self.tiles.append(tile)
        self.kpi.body.bind('<Configure>', self.layout_tiles, add='+')
        self.tile_cols = 0
        self.layout_tiles()

        wcard = Card(center, pad=8)
        wcard.pack(fill='both', expand=True)
        self.workspace = wcard.body

        right = Card(main, pad=16)
        main.add(right, minsize=255, width=304, stretch='never')
        # панель параметров прокручивается колесом мыши, если окно низкое
        rcv = tk.Canvas(right.body, bg=SURFACE, highlightthickness=0, bd=0)
        rcv.pack(fill='both', expand=True)
        pane = tk.Frame(rcv, bg=SURFACE)
        rwin = rcv.create_window(0, 0, window=pane, anchor='nw')
        rcv.bind('<Configure>', lambda e: rcv.itemconfigure(rwin, width=e.width))
        pane.bind('<Configure>', lambda e: rcv.configure(scrollregion=(0, 0, e.width, e.height)))

        def wheel(e):
            if pane.winfo_reqheight() <= rcv.winfo_height():
                return
            delta = -1 if (e.num == 4 or e.delta > 0) else 1
            rcv.yview_scroll(delta * 2, 'units')
        right.bind('<Enter>', lambda e: [self.bind_all(ev, wheel) for ev in
                                         ('<MouseWheel>', '<Button-4>', '<Button-5>')])
        right.bind('<Leave>', lambda e: [self.unbind_all(ev) for ev in
                                         ('<MouseWheel>', '<Button-4>', '<Button-5>')])
        tk.Label(pane, text='ПАРАМЕТРЫ ПРОЕКТА', bg=SURFACE, fg=TEXT, font=self.f_h2,
                 anchor='w').pack(fill='x', pady=(0, 4))
        for title, rows in PARAM_GROUPS:
            tk.Label(pane, text=title, bg=SURFACE, fg=MUTED, font=self.f_cap,
                     anchor='w').pack(fill='x', pady=(12, 4))
            for key, label in rows:
                row = tk.Frame(pane, bg=SURFACE)
                row.pack(fill='x', pady=3)
                tk.Label(row, text=label, bg=SURFACE, fg=TEXT, font=self.f_base,
                         anchor='w').pack(side='left')
                e = ttk.Entry(row, textvariable=self.values[key], font=self.f_base, width=13,
                              justify='right', style='Field.TEntry')
                e.pack(side='right')
                e.bind('<Return>', lambda ev: self.recalc())
        btn = RoundButton(pane, 'ПЕРЕСЧИТАТЬ', self.recalc, 'primary', self.f_btn_b, pady=10)
        btn.pack(fill='x', pady=(18, 4))
        self._stretch_button(btn, pane)
        self.switch('Геометрия')

    def _stretch_button(self, btn, parent):
        """Кнопка «ПЕРЕСЧИТАТЬ» на всю ширину панели."""
        def redraw(e):
            w, h = e.width, e.height
            btn.delete('all')
            btn.shape = round_rect(btn, 1, 1, w - 1, h - 1, btn.r, fill=btn.st['bg'],
                                   outline=btn.st['line'])
            btn.create_text(w / 2, h / 2, text='ПЕРЕСЧИТАТЬ', font=self.f_btn_b, fill=btn.st['fg'])
        btn.bind('<Configure>', redraw)

    def layout_tiles(self, _e=None):
        w = self.kpi.cv.winfo_width()
        cols = 8 if w >= 860 else 4
        if cols == self.tile_cols:
            return
        self.tile_cols = cols
        for t in self.tiles:
            t.grid_forget()
        for i, t in enumerate(self.tiles):
            t.grid(row=i // cols, column=i % cols, sticky='nsew', padx=3, pady=3)
        for c in range(8):
            self.kpi.body.columnconfigure(c, weight=1 if c < cols else 0)
        self.kpi._fit()

    def adapt(self, e):
        """Прячет декоративные панели под планом, если окно низкое."""
        b = getattr(self, 'bottom', None)
        if e.widget is not self or b is None or not b.winfo_exists():
            return
        show = self.winfo_height() >= 820
        if show != bool(b.winfo_manager()):
            if show:
                b.pack(fill='x', padx=14, pady=(0, 10))
            else:
                b.pack_forget()

    def hover_tab(self, t, on):
        if t != getattr(self, 'tab', None):
            self.tabbuttons[t].configure(fg=TEXT if on else MUTED)

    def mark_tab(self, tab):
        for t, lab in self.tabbuttons.items():
            active = t == tab
            lab.configure(fg=PRIMARY if active else MUTED)
            self.tabmarks[t].configure(bg=PRIMARY if active else SURFACE)

    # ------------------------------------------------------------ расчёт ---
    def geom(self):
        try:
            L = float(self.values['length'].get().replace(',', '.'))
            B = float(self.values['width'].get().replace(',', '.'))
            e = float(self.values['eave'].get().replace(',', '.'))
            s = float(self.values['side'].get().replace(',', '.'))
            t = float(self.values['end'].get().replace(',', '.'))
            step = float(self.values['rafter_step'].get().replace(',', '.'))
            ls = float(self.values['lath_step'].get().replace(',', '.'))
            if min(L, B, s, t, step, ls) <= 0 or e < 0 or L < B:
                raise ValueError('Размеры должны быть положительными, длина дома ≥ ширины, свес ≥ 0')
            W = B + 2 * e
            D = L + 2 * e
            half = W / 2
            if s < half:
                raise ValueError(f'Боковой скат должен быть не короче {half:.2f} м (половина ширины по карнизу)')
            h = math.sqrt(max(s * s - half * half, 0))
            angle = math.degrees(math.atan2(h, half))
            a = math.sqrt(max(t * t - h * h, 0)) if t >= h else None
            if a is None or a <= 0:
                raise ValueError('Торцевой скат несовместим с высотой боковых скатов')
            ridge = D - 2 * a
            if ridge < 0:
                raise ValueError('Торцевые скаты не помещаются в длину кровли')
            side = (D + ridge) / 2 * s * 2
            end = W * t
            return dict(**{'L': L, 'B': B, 'e': e, 's': s, 't': t, 'W': W, 'D': D, 'h': h,
                           'a': a, 'ridge': ridge, 'area': side + end, 'side_area': side,
                           'end_area': end, 'angle': angle, 'step': step, 'lath_step': ls})
        except ValueError as ex:
            raise ValueError(str(ex))

    def recalc(self):
        try:
            g = self.geom()
        except ValueError as ex:
            self.status.set('Ошибка геометрии: ' + str(ex))
            messagebox.showwarning('Проверка исходных данных', str(ex))
            return
        self.g = g
        for key, fmt in (('area', '{area:.2f} м²'), ('side_area', '{side_area:.2f} м²'),
                         ('end_area', '{end_area:.2f} м²'), ('ridge', '{ridge:.2f} м'),
                         ('height', '{h:.2f} м'), ('slope', '{angle:.1f}°')):
            self.res[key].set(fmt.format(**g))
        n = max(2, math.floor(g['D'] / g['step']) + 1)
        rows = math.ceil(g['s'] / g['lath_step']) + 1
        self.res['rafters'].set(f'≈ {2 * n} шт.')
        self.res['laths'].set(f'≈ {2 * rows} ряда')
        self.res['items'].set(str(len(self.objects)))
        self.res['planes'].set('4')
        self.res['valleys'].set('0')
        self.status.set('Расчёт обновлён; объёмы ориентировочные — для рабочей документации нужна проверка проектировщика')
        if hasattr(self, 'canvas'):
            self.render()
        if hasattr(self, 'data_table'):
            self.fill_table()

    # ----------------------------------------------------------- вкладки ---
    def switch(self, tab):
        self.tab = tab
        self.mark_tab(tab)
        for child in self.workspace.winfo_children():
            child.destroy()
        self.canvas = None
        self.data_table = None
        header = tk.Frame(self.workspace, bg=SURFACE)
        header.pack(fill='x', padx=15, pady=(10, 4))
        tk.Label(header, text=tab, bg=SURFACE, fg=TEXT, font=self.f_h2, anchor='w').pack(side='left')
        if tab in ('Геометрия', 'Элементы кровли', 'Стропильная система', 'Обрешётка'):
            if tab == 'Элементы кровли':   # много кнопок - отдельной строкой
                tools = tk.Frame(self.workspace, bg=SURFACE)
                tools.pack(fill='x', padx=15, pady=(0, 6))
            else:                          # кнопки справа от заголовка
                tools = tk.Frame(header, bg=SURFACE)
                tools.pack(side='right')
            if tab == 'Элементы кровли':
                for kind in KINDS:
                    self.button(tools, '+ ' + kind, lambda k=kind: self.set_mode(k), padx=10)
                self.button(tools, 'Выбрать/переместить', lambda: self.set_mode('select'), True, padx=10)
                self.button(header, 'Удалить выбранный', self.delete_selected, side='right')
            elif tab == 'Геометрия':
                self.button(tools, 'Выбрать', lambda: self.set_mode('select'), True, padx=11)
                self.button(tools, 'Добавить шахту', lambda: self.set_mode('Вентшахта'), padx=11)
                self.button(tools, 'Добавить окно', lambda: self.set_mode('Слуховое окно'), padx=11)
                self.button(tools, 'Удалить', self.delete_selected, padx=11)
            else:
                self.button(tools, 'Пересчитать', self.recalc, True, padx=11)
                self.button(tools, 'Настройка размещения', lambda: self.soon('Редактирование схемы'), padx=11)
            self.canvas = tk.Canvas(self.workspace, bg='#F8FAFD', highlightthickness=0)
            self.canvas.pack(fill='both', expand=True, padx=18, pady=(4, 8))
            self.canvas.bind('<Configure>', lambda e: self.render())
            self.canvas.bind('<Button-1>', self.click)
            self.canvas.bind('<B1-Motion>', self.drag)
            self.canvas.bind('<ButtonRelease-1>', lambda e: setattr(self, 'drag_index', None))
            if tab != 'Элементы кровли':
                bottom = tk.Frame(self.workspace, bg=SURFACE)
                self.bottom = bottom
                if self.winfo_height() >= 820:      # на низких экранах место нужно плану
                    bottom.pack(fill='x', padx=14, pady=(0, 10))
                if tab == 'Геометрия':
                    for text in ('Раскладка скатов', 'Предпросмотр 3D', 'Разрез 1–1'):
                        card = Card(bottom, bg=SURFACE, fill=SOFT, radius=12, pad=12, height=84)
                        card.pack(side='left', fill='both', expand=True, padx=4)
                        tk.Label(card.body, text=text, bg=SOFT, fg=TEXT, font=self.f_bold,
                                 anchor='w').pack(fill='x')
                        tk.Label(card.body, text='Панель предварительного просмотра', bg=SOFT,
                                 fg=MUTED, font=self.f_small, anchor='w', justify='left',
                                 wraplength=190).pack(fill='x', pady=(6, 0))
                elif tab == 'Стропильная система':
                    self.note(bottom, 'Предварительная раскладка основных стропил по заданному шагу. '
                                      'Диагональные и нарожники пока не рассчитываются.')
                elif tab == 'Обрешётка':
                    self.note(bottom, 'Предварительные линии обрешётки по наклонной длине ската. '
                                      'Сплошные зоны и пересечения с шахтами будут добавлены позже.')
            self.render()
            return
        if tab == 'Ведомости':
            cols = ['Раздел', 'Наименование', 'Количество', 'Ед. изм.']
            self.data_table = ttk.Treeview(self.workspace, columns=cols, show='headings',
                                           style='Table.Treeview')
            for c in cols:
                self.data_table.heading(c, text=c, anchor='w')
                self.data_table.column(c, width=170, anchor='w')
            self.data_table.tag_configure('odd', background='#F8FAFD')
            self.data_table.pack(fill='both', expand=True, padx=18, pady=(8, 8))
            self.fill_table()
            tk.Label(self.workspace, text='Ведомость предварительная. Длина древесины, узлы и крепёж '
                                          'требуют дальнейшей детализации.', bg=SURFACE, fg=MUTED,
                     font=self.f_small, anchor='w').pack(fill='x', padx=18, pady=(0, 14))
            return
        empty = tk.Frame(self.workspace, bg=SURFACE)
        empty.pack(expand=True)
        ic = tk.Canvas(empty, width=76, height=76, bg=SURFACE, highlightthickness=0)
        round_rect(ic, 2, 2, 74, 74, 22, fill=PRIMARY_SOFT, outline=PRIMARY_SOFT)
        ic.create_text(38, 38, text='⌂', fill=PRIMARY, font=(self.f_h1.actual('family'), 28, 'bold'))
        ic.pack()
        tk.Label(empty, text='Раздел будет добавлен позже', bg=SURFACE, fg=MUTED,
                 font=self.f_h2).pack(pady=(14, 0))

    def note(self, parent, text):
        card = Card(parent, bg=SURFACE, fill=SOFT, radius=12, pad=14, fit=True)
        card.pack(fill='x')
        tk.Label(card.body, text=text, bg=SOFT, fg=TEXT, font=self.f_base, wraplength=720,
                 justify='left', anchor='w').pack(fill='x')

    def set_mode(self, mode):
        self.mode = mode
        self.status.set('Инструмент: ' + mode + ' — щёлкните по плану' if mode != 'select'
                        else 'Выбор объектов; перетаскивание мышью')

    # ------------------------------------------------------- план и мышь ---
    def coords(self, x, y):
        g = self.g
        return ((x - self.ox) / self.scale, (y - self.oy) / self.scale)

    def screen(self, x, y):
        return (self.ox + x * self.scale, self.oy + y * self.scale)

    def click(self, event):
        if not hasattr(self, 'g'):
            return
        x, y = self.coords(event.x, event.y)
        g = self.g
        if self.mode != 'select':
            if not (0 <= x <= g['D'] and 0 <= y <= g['W']):
                return
            self.objects.append({'type': self.mode, 'x': round(x, 3), 'y': round(y, 3)})
            self.selected = len(self.objects) - 1
            self.status.set('Элемент добавлен: ' + self.mode)
            self.mode = 'select'
            self.render()
            return
        self.selected = None
        for i in range(len(self.objects) - 1, -1, -1):
            o = self.objects[i]
            if math.hypot((x - o['x']) * self.scale, (y - o['y']) * self.scale) < 18:
                self.selected = i
                break
        self.drag_index = self.selected
        self.render()

    def drag(self, event):
        i = getattr(self, 'drag_index', None)
        if i is None or not (0 <= i < len(self.objects)):
            return
        x, y = self.coords(event.x, event.y)
        g = self.g
        self.objects[i]['x'] = round(min(max(x, 0), g['D']), 3)
        self.objects[i]['y'] = round(min(max(y, 0), g['W']), 3)
        self.render()

    def delete_selected(self):
        if self.selected is not None and self.selected < len(self.objects):
            del self.objects[self.selected]
            self.selected = None
            self.render()
            return
        self.status.set('Сначала выберите объект на плане')

    def render(self):
        c = getattr(self, 'canvas', None)
        if c is None or not c.winfo_exists() or not hasattr(self, 'g'):
            return
        c.delete('all')
        g = self.g
        w = max(c.winfo_width(), 600)
        h = max(c.winfo_height(), 320)
        self.scale = min((w - 125) / g['D'], (h - 135) / g['W'])
        self.ox = (w - g['D'] * self.scale) / 2
        self.oy = (h - g['W'] * self.scale) / 2
        D, W, a, ridge = g['D'], g['W'], g['a'], g['ridge']

        def line(p, q, color='#243b53', width=2, dash=None):
            c.create_line(*self.screen(*p), *self.screen(*q), fill=color, width=width, dash=dash)

        def poly(points, fill):
            flat = [v for p in points for v in self.screen(*p)]
            c.create_polygon(*flat, fill=fill, outline='')

        # сетка 1/2/5/10... м, привязанная к координатам плана
        step_m = 1
        for cand in (1, 2, 5, 10, 20, 50, 100):
            step_m = cand
            if cand * self.scale >= 28:
                break
        x_m = math.floor(-self.ox / self.scale / step_m) * step_m
        while self.ox + x_m * self.scale <= w:
            xx = self.ox + x_m * self.scale
            c.create_line(xx, 0, xx, h, fill=GRID)
            x_m += step_m
        y_m = math.floor(-self.oy / self.scale / step_m) * step_m
        while self.oy + y_m * self.scale <= h:
            yy = self.oy + y_m * self.scale
            c.create_line(0, yy, w, yy, fill=GRID)
            y_m += step_m
        # скаты
        poly([(0, 0), (D, 0), (D - a, W / 2), (a, W / 2)], '#E3ECFA')
        poly([(0, W), (D, W), (D - a, W / 2), (a, W / 2)], '#D3E1F6')
        poly([(0, 0), (a, W / 2), (0, W)], '#EDF2FB')
        poly([(D, 0), (D - a, W / 2), (D, W)], '#EDF2FB')
        c.create_rectangle(*self.screen(0, 0), *self.screen(D, W), outline='#1E3A5F', width=2)
        for p, q in (((0, 0), (a, W / 2)), ((0, W), (a, W / 2)),
                     ((D, 0), (D - a, W / 2)), ((D, W), (D - a, W / 2)),
                     ((a, W / 2), (D - a, W / 2))):
            line(p, q, '#2F4B6E')
        if self.tab == 'Стропильная система':
            count = int(D / g['step']) + 1
            for i in range(count + 1):
                x = min(i * g['step'], D)
                if x < a:
                    yc = W * x / (2 * a)
                elif x > D - a:
                    yc = W * (D - x) / (2 * a)
                else:
                    yc = W / 2
                if not yc > 0:
                    continue
                line((x, 0), (x, yc), '#E4572E', 1)
                line((x, W), (x, W - yc), '#E4572E', 1)
        if self.tab == 'Обрешётка':
            rows = min(150, int(g['s'] / g['lath_step']) + 1)
            for i in range(1, rows):
                y = W / 2 * i / rows
                line((0, y), (D, y), '#C58A2B', 1)
                line((0, W - y), (D, W - y), '#C58A2B', 1)
        for i, o in enumerate(self.objects):
            xx, yy = self.screen(o['x'], o['y'])
            lbl, color = OBJECT_STYLE.get(o['type'], ('ЭЛ', '#667788'))
            sel = i == self.selected
            if sel:
                c.create_oval(xx - 19, yy - 19, xx + 19, yy + 19, fill=PRIMARY_SOFT, outline=PRIMARY)
            c.create_oval(xx - 13, yy - 13, xx + 13, yy + 13, fill=color,
                          outline=PRIMARY if sel else '#FFFFFF', width=2)
            c.create_text(xx, yy, text=lbl, fill='white', font=self.f_cap)
        x0, y0 = self.screen(0, W)
        x1, y1 = self.screen(D, W)
        c.create_line(x0, y0 + 25, x1, y1 + 25, fill=PRIMARY, width=2, arrow='both',
                      arrowshape=(7, 9, 3))
        c.create_text((x0 + x1) / 2, y0 + 43, text=f'{D:.2f} м — габарит кровли', fill=PRIMARY,
                      font=self.f_bold)
        c.create_text((x0 + x1) / 2, self.oy - 25,
                      text=f"Конёк {ridge:.2f} м | Площадь {g['area']:.2f} м²", fill=PRIMARY,
                      font=self.f_bold)

    def fill_table(self):
        if self.data_table is None or not self.data_table.winfo_exists() or not hasattr(self, 'g'):
            return
        for i in self.data_table.get_children():
            self.data_table.delete(i)
        g = self.g
        data = [('Кровля', 'Общая площадь', round(g['area'], 2), 'м²'),
                ('Кровля', 'Боковые скаты (2 шт.)', round(g['side_area'], 2), 'м²'),
                ('Кровля', 'Торцевые скаты (2 шт.)', round(g['end_area'], 2), 'м²'),
                ('Стропила', 'Основные стропила, оценка', self.res['rafters'].get(), 'шт.'),
                ('Обрешётка', 'Ряды по двум боковым скатам', self.res['laths'].get(), 'ряд.'),
                ('Кровля', 'Плоскости скатов', self.res['planes'].get() or '4', 'шт.'),
                ('Кровля', 'Ендовы / рёбра', self.res['valleys'].get() or '0', 'шт.'),
                ('Элементы', 'Размещённые объекты', len(self.objects), 'шт.')]
        for n, item in enumerate(data):
            self.data_table.insert('', 'end', values=item, tags=('odd',) if n % 2 else ())

    # ----------------------------------------------------- файлы/экспорт ---
    def new(self):
        if not messagebox.askyesno('Новый проект', 'Очистить текущие данные и создать новый проект?'):
            return
        self.objects = []
        self.selected = None
        self.path = None
        for k, v in DEFAULTS.items():
            self.values[k].set(str(v))
        self.recalc()
        self.switch('Геометрия')

    def save(self, asnew=False):
        self.recalc()
        if not hasattr(self, 'g'):
            return
        path = None if asnew else self.path
        if not path:
            path = filedialog.asksaveasfilename(title='Сохранить проект', defaultextension='.roof.json',
                                                filetypes=[('Проект RoofStudio', '*.json')])
        if not path:
            return
        try:
            Path(path).write_text(json.dumps({'version': VERSION,
                                              'parameters': {k: v.get() for k, v in self.values.items()},
                                              'objects': self.objects},
                                             ensure_ascii=False, indent=2), encoding='utf-8')
            self.path = path
            self.status.set('Сохранено: ' + str(path))
        except OSError as ex:
            messagebox.showerror('Ошибка сохранения', str(ex))

    def load(self):
        path = filedialog.askopenfilename(title='Открыть проект',
                                          filetypes=[('Проект RoofStudio', '*.json')])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            params = data.get('parameters', data)
            for k in self.values:
                if k not in params:
                    continue
                self.values[k].set(str(params[k]))
            self.objects = [o for o in data.get('objects', []) if {'type', 'x', 'y'} <= set(o)]
            self.path = path
            self.recalc()
            self.switch('Геометрия')
            self.status.set('Открыт проект: ' + str(path))
        except (OSError, ValueError, KeyError, TypeError) as ex:
            messagebox.showerror('Ошибка открытия', str(ex))

    def export_csv(self):
        try:
            g = self.geom()
        except ValueError as ex:
            messagebox.showerror('Ошибка', str(ex))
            return
        path = filedialog.asksaveasfilename(title='Сохранить CSV', defaultextension='.csv',
                                            filetypes=[('CSV', '*.csv')])
        if not path:
            return
        import csv
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            wr = csv.writer(f, delimiter=';')
            wr.writerow([*('Показатель', 'Значение', 'Единица')])
            for title, key, unit in (('Общая площадь', 'area', 'м²'), ('Боковые скаты', 'side_area', 'м²'),
                                     ('Торцевые скаты', 'end_area', 'м²'), ('Конёк', 'ridge', 'м'),
                                     ('Размещённые объекты', None, 'шт.')):
                wr.writerow([title, round(g[key], 3) if key else len(self.objects), unit])
        self.status.set('CSV экспортирован: ' + path)

    def export_dxf(self):
        """DXF AC1009 (R12) без внешних библиотек: геометрия в мм, 1:1.

        LINE/TEXT считаются редактируемыми примитивами AutoCAD. Для
        будущих размеров, блоков и штриховок будет добавлен отдельный CAD-модуль.
        """
        try:
            g = self.geom()
        except ValueError as ex:
            messagebox.showerror('Ошибка геометрии', str(ex))
            return
        path = filedialog.asksaveasfilename(title='Экспорт DXF', defaultextension='.dxf',
                                            filetypes=[('AutoCAD DXF', '*.dxf')])
        if not path:
            return
        def pair(code, value):
            return f'{code}\n{value}\n'
        parts = [pair(0, 'SECTION'), pair(2, 'HEADER'), pair(9, '$ACADVER'),
                 pair(1, 'AC1009'), pair(0, 'ENDSEC'), pair(0, 'SECTION'),
                 pair(2, 'TABLES'), pair(0, 'ENDSEC'), pair(0, 'SECTION'),
                 pair(2, 'ENTITIES')]
        def line(x1, y1, x2, y2, layer):
            parts.extend([pair(0, 'LINE'), pair(8, layer), pair(10, f'{x1:.3f}'),
                          pair(20, f'{y1:.3f}'), pair(30, 0), pair(11, f'{x2:.3f}'),
                          pair(21, f'{y2:.3f}'), pair(31, 0)])
        def text(x, y, title, layer, height=170):
            # DXF R12 supports ASCII text. Do not export non-ASCII directly to
            # avoid misinterpreted codepages in different AutoCAD locales.
            parts.extend([pair(0, 'TEXT'), pair(8, layer), pair(10, f'{x:.3f}'),
                          pair(20, f'{y:.3f}'), pair(30, 0), pair(40, height),
                          pair(1, title)])
        def rectangle(x0, y0, x1, y1, layer):
            line(x0, y0, x1, y0, layer)
            line(x1, y0, x1, y1, layer)
            line(x1, y1, x0, y1, layer)
            line(x0, y1, x0, y0, layer)
        D, W, a = g['D'] * 1000, g['W'] * 1000, g['a'] * 1000
        R = D - a
        rectangle(0, 0, D, W, 'ROOF_OUTLINE')
        for x1, y1, x2, y2 in ((0, 0, a, W/2), (0, W, a, W/2),
                               (D, 0, R, W/2), (D, W, R, W/2)):
            line(x1, y1, x2, y2, 'ROOF_HIPS')
        line(a, W/2, R, W/2, 'ROOF_RIDGE')
        for i, obj in enumerate(self.objects, start=1):
            x, y = float(obj['x']) * 1000, float(obj['y']) * 1000
            rectangle(x-175, y-125, x+175, y+125, 'ROOF_OBJECTS')
            text(x+225, y, f'OBJ {i}', 'ROOF_LABELS')
        text(0, -800, f'ROOFSTUDIO v{VERSION}  AREA {g["area"]:.2f} m2',
             'ROOF_LABELS', 250)
        parts.extend([pair(0, 'ENDSEC'), pair(0, 'EOF')])
        try:
            Path(path).write_text(''.join(parts), encoding='ascii', newline='\n')
            self.status.set('DXF создан (мм, 1:1): ' + path)
        except OSError as ex:
            messagebox.showerror('Ошибка экспорта DXF', str(ex))

    def soon(self, name):
        messagebox.showinfo(name, 'Раздел будет добавлен позже')


from perimeter_editor import PerimeterMixin
from attic_ui import AtticMixin

class RoofStudioV08(AtticMixin, PerimeterMixin, RoofStudio):
    pass

RoofStudioV07 = RoofStudioV08
RoofStudioV06 = RoofStudioV08

if __name__ == '__main__':
    try:
        RoofStudioV08().mainloop()
    except Exception:
        details = log_exception(*sys.exc_info())
        try:
            messagebox.showerror('Ошибка запуска RoofStudio', details[-2400:])
        except Exception:
            print(details, file=sys.stderr)
        sys.exit(1)
