"""RoofStudio v0.7 — measured outline editor and preliminary complex roof model."""
import math
import tkinter as tk
from tkinter import ttk, messagebox

from complex_roof import generate_roof_geometry, polygon_area as roof_polygon_area

DIRS = {'Вправо →': 0, 'Вверх ↑': 90, 'Влево ←': 180, 'Вниз ↓': 270}
EPS = 1e-7


def polygon_area(points):
    return abs(sum(points[i][0] * points[(i + 1) % len(points)][1] -
                   points[(i + 1) % len(points)][0] * points[i][1]
                   for i in range(len(points)))) / 2 if len(points) >= 3 else 0.0


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def polygon_edges(points, closed=True):
    return [(points[i], points[(i + 1) % len(points)]) for i in range(len(points) if closed else len(points) - 1)]


def orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a, b, p):
    return abs(orient(a, b, p)) < EPS and min(a[0], b[0]) - EPS <= p[0] <= max(a[0], b[0]) + EPS and min(a[1], b[1]) - EPS <= p[1] <= max(a[1], b[1]) + EPS


def segments_intersect(a, b, c, d):
    x, y, z, w = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if ((x > EPS and y < -EPS) or (x < -EPS and y > EPS)) and ((z > EPS and w < -EPS) or (z < -EPS and w > EPS)):
        return True
    return any([on_segment(a, b, c), on_segment(a, b, d), on_segment(c, d, a), on_segment(c, d, b)])


def validate_polygon(points):
    if len(points) < 3:
        return 'Нужно не менее трёх точек'
    for i, (a, b) in enumerate(polygon_edges(points)):
        if distance(a, b) < 0.01:
            return f'Очень короткая сторона {i + 1}'
    if polygon_area(points) < 0.01:
        return 'Нулевая площадь контура'
    edges = polygon_edges(points)
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i or abs(i - j) == 1 or (i == 0 and j == len(edges) - 1):
                continue
            if segments_intersect(a, b, c, d):
                return f'Пересечение сторон {i + 1} и {j + 1}'
    return None


class PerimeterMixin:
    def __init__(self):
        self.custom_outline = False
        self.outline_points = []
        self.outline_closed = False
        self.manual_ridges = []
        self.selected_vertex = None
        self.outline_drag = None
        self.line_start = None
        self.last_screen = None
        self.roof_type_choice = 'Вальмовая'
        self.outline_mode = 'select'
        self.complex_roof = None
        super().__init__()
        self.title('RoofStudio v0.7 — Капитальный ремонт кровли')

    def build(self):
        super().build()
        top = tk.Frame(self.tabsrow, bg='#FFFFFF')
        top.pack(side='right', padx=12)
        tk.Label(top, text='Тип кровли:', bg='#FFFFFF', font=self.f_small).pack(side='left', padx=6)
        self.roof_choice = tk.StringVar(value=self.roof_type_choice)
        roof_types = ['Вальмовая', 'Двускатная', 'Сложная / по точкам']
        choice = ttk.Combobox(top, values=roof_types, textvariable=self.roof_choice, width=22, state='readonly')
        choice.pack(side='left')
        choice.bind('<<ComboboxSelected>>', self._change_roof_type)

    def _change_roof_type(self, event=None):
        selected = self.roof_choice.get()
        self.roof_type_choice = selected
        if selected == 'Сложная / по точкам':
            if not self.outline_points:
                self.outline_points = [[0, 0]]
            self.custom_outline = True
            self.switch('Контур здания')
            self.recalc()
        else:
            self.custom_outline = False
            self.complex_roof = None
            self.recalc()
            self.switch('Геометрия')

    def geom(self):
        if self.roof_type_choice != 'Двускатная' or self.custom_outline:
            return super().geom()
        def val(key):
            return float(self.values[key].get().replace(',', '.'))
        L, B, e, s = val('length'), val('width'), val('eave'), val('side')
        step, ls = val('rafter_step'), val('lath_step')
        if min(L, B, s, step, ls) <= 0 or e < 0:
            raise ValueError('Недопустимые размеры двускатной кровли')
        D, W = L + 2 * e, B + 2 * e
        if s < W / 2:
            raise ValueError('Скат короче половины ширины кровли с карнизами')
        h = math.sqrt(max(s * s - (W / 2) ** 2, 0))
        return dict(L=L, B=B, e=e, s=s, t=0, W=W, D=D, h=h, a=0, ridge=D,
                    side_area=2 * D * s, end_area=0, area=2 * D * s,
                    angle=math.degrees(math.atan2(h, W / 2)), step=step, lath_step=ls)

    def switch(self, tab):
        if tab != 'Контур здания':
            super().switch(tab)
            if self.custom_outline and tab == 'Геометрия':
                self.status.set('Сложный контур: построены предварительные плоскости скатов, коньки и ендовы')
            return
        self.tab = tab
        self.mark_tab(tab)
        for child in self.workspace.winfo_children():
            child.destroy()
        self.canvas = None
        self.data_table = None
        if getattr(self, 'bottom', None) is not None and self.bottom.winfo_exists():
            self.bottom.pack_forget()
        outer = tk.Frame(self.workspace, bg='#FFFFFF')
        outer.pack(fill='both', expand=True, padx=10, pady=8)
        head = tk.Frame(outer, bg='#FFFFFF')
        head.pack(fill='x', pady=(0, 8))
        tk.Label(head, text='Редактор обмерного контура', bg='#FFFFFF', fg='#162033', font=self.f_h2).pack(side='left')
        for name, cmd in [('Прямоугольник', self.sample_rectangle), ('Г-образный дом', self.sample_l), ('С выступом', self.sample_protrusion), ('Новый контур', self.clear_outline)]:
            self.button(head, name, cmd, padx=8)
        self.button(head, 'Построить кровлю', self.recalc, accent=True, padx=10, side='right')

        self.edit_wrap = tk.Frame(outer, bg='#FFFFFF')
        self.edit_wrap.pack(fill='x', pady=(0, 7))
        self.segment_length = tk.StringVar(value='6.00')
        self.segment_dir = tk.StringVar(value='Вправо →')
        self.angle_value = tk.StringVar(value='0')
        self.point_x = tk.StringVar(value='0.00')
        self.point_y = tk.StringVar(value='0.00')
        for lab in [('Длина стены, м', self.segment_length, 8), ('Угол, °', self.angle_value, 6)]:
            tk.Label(self.edit_wrap, text=lab[0], bg='#FFFFFF', font=self.f_small).pack(side='left', padx=(8, 3))
            ttk.Entry(self.edit_wrap, textvariable=lab[1], width=lab[2]).pack(side='left')
        box = ttk.Combobox(self.edit_wrap, values=list(DIRS), textvariable=self.segment_dir, width=12, state='readonly')
        box.pack(side='left', padx=7)
        box.bind('<<ComboboxSelected>>', lambda e: self.angle_value.set(str(DIRS[self.segment_dir.get()])))
        self.button(self.edit_wrap, '+ Добавить стену', self.add_measured_segment, True, padx=8)
        self.button(self.edit_wrap, 'Замкнуть', self.close_outline, padx=8)
        self.button(self.edit_wrap, 'Отменить точку', self.undo_point, padx=8)
        self.button(self.edit_wrap, 'Добавить точку мышью', lambda: self._set_outline_mode('point'), padx=8)

        second = tk.Frame(outer, bg='#FFFFFF')
        second.pack(fill='x', pady=(0, 6))
        tk.Label(second, text='Выбранная вершина: X', bg='#FFFFFF', font=self.f_small).pack(side='left')
        ttk.Entry(second, textvariable=self.point_x, width=10).pack(side='left', padx=4)
        tk.Label(second, text='Y', bg='#FFFFFF', font=self.f_small).pack(side='left')
        ttk.Entry(second, textvariable=self.point_y, width=10).pack(side='left', padx=4)
        self.button(second, 'Изменить координаты', self.update_selected_point, padx=8)
        self.button(second, 'Линия конька / ребра', lambda: self._set_outline_mode('ridge'), padx=8)
        self.button(second, 'Удалить линию', self.delete_last_ridge, padx=8)
        self.button(second, 'Проверить контур', self.validate_current, padx=8)

        third = tk.Frame(outer, bg='#FFFFFF')
        third.pack(fill='x', pady=(0, 6))
        tk.Label(third, text='Для сложной кровли используются: отметка карниза, отметка конька, уклон по умолчанию — справа в панели параметров.',
                 bg='#FFFFFF', fg='#6B778C', font=self.f_small, anchor='w').pack(side='left', padx=8)

        self.canvas = tk.Canvas(outer, bg='#F8FAFD', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.render())
        self.canvas.bind('<Button-1>', self.click)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', lambda e: setattr(self, 'outline_drag', None))
        self.outline_summary = tk.StringVar()
        tk.Label(outer, textvariable=self.outline_summary, bg='#FFFFFF', fg='#2563EB', font=self.f_bold, anchor='w').pack(fill='x', pady=(5, 0))
        tk.Label(outer, text='ЛКМ по вершине — выбрать/перетащить. Новый контур: задавайте длину и направление каждой стены; '
                 'угол 0° — вправо, 90° — вверх. Для замыкания нажмите «Замкнуть». '
                 'Линии коньков задаются двумя кликами. Если линии не заданы, программа создаст центральный конёк автоматически.',
                 bg='#FFFFFF', fg='#6B778C', font=self.f_small, wraplength=1050, justify='left', anchor='w').pack(fill='x', pady=(4, 4))
        self.render()

    def _set_outline_mode(self, mode):
        self.outline_mode = mode
        self.line_start = None
        self.status.set({'ridge': 'Кликните две точки для линии конька или ребра',
                         'point': 'Кликните точку на плане, чтобы добавить вершину'}.get(mode, 'Выбор вершин'))

    def _touch(self):
        self.custom_outline = True
        self.refresh_outline_status()
        self.render()

    def _float_value(self, key, default=0.0):
        try:
            return float(self.values[key].get().replace(',', '.'))
        except Exception:
            return default

    def sample_rectangle(self):
        self.outline_points = [[0, 0], [20, 0], [20, 12], [0, 12]]
        self.outline_closed = True
        self.manual_ridges = []
        self._touch()
        self.recalc()

    def sample_l(self):
        self.outline_points = [[0, 0], [20, 0], [20, 7], [12, 7], [12, 14], [0, 14]]
        self.outline_closed = True
        self.manual_ridges = []
        self._touch()
        self.recalc()

    def sample_protrusion(self):
        self.outline_points = [[0, 0], [24, 0], [24, 8], [17, 8], [17, 12], [11, 12], [11, 8], [0, 8]]
        self.outline_closed = True
        self.manual_ridges = []
        self._touch()
        self.recalc()

    def clear_outline(self):
        if self.outline_points and not messagebox.askyesno('Новый контур', 'Удалить текущие точки и линии?'):
            return
        self.outline_points = [[0.0, 0.0]]
        self.outline_closed = False
        self.manual_ridges = []
        self.selected_vertex = 0
        self.complex_roof = None
        self._touch()

    def add_measured_segment(self):
        try:
            length = float(self.segment_length.get().replace(',', '.'))
            angle = float(self.angle_value.get().replace(',', '.'))
            if not (0.01 <= length <= 100000 and math.isfinite(angle)):
                raise ValueError()
        except ValueError:
            messagebox.showwarning('Длина и угол', 'Введите положительную длину и числовой угол.')
            return
        if self.outline_closed:
            messagebox.showinfo('Контур замкнут', 'Нажмите «Новый контур» или «Отменить точку» для изменения.')
            return
        if not self.outline_points:
            self.outline_points = [[0, 0]]
        x, y = self.outline_points[-1]
        p = [round(x + length * math.cos(math.radians(angle)), 5), round(y + length * math.sin(math.radians(angle)), 5)]
        if distance(p, self.outline_points[0]) < 0.02 and len(self.outline_points) >= 3:
            self.close_outline()
            return
        if distance(p, self.outline_points[-1]) < 0.01:
            return
        self.outline_points.append(p)
        self.selected_vertex = len(self.outline_points) - 1
        self._touch()

    def undo_point(self):
        if self.outline_closed:
            self.outline_closed = False
            self.complex_roof = None
        elif len(self.outline_points) > 1:
            self.outline_points.pop()
            self.complex_roof = None
        else:
            return
        self.selected_vertex = None
        self._touch()

    def close_outline(self):
        if len(self.outline_points) < 3:
            messagebox.showwarning('Контур', 'Для замыкания нужно не менее трёх вершин.')
            return
        if distance(self.outline_points[0], self.outline_points[-1]) < 0.02:
            self.outline_points.pop()
        err = validate_polygon(self.outline_points)
        if err:
            messagebox.showwarning('Проверка контура', err)
            return
        self.outline_closed = True
        self._touch()
        self.recalc()

    def update_selected_point(self):
        i = self.selected_vertex
        if i is None or i >= len(self.outline_points):
            messagebox.showinfo('Вершина', 'Выберите вершину на схеме.')
            return
        try:
            x = float(self.point_x.get().replace(',', '.'))
            y = float(self.point_y.get().replace(',', '.'))
            if not all(map(math.isfinite, [x, y])):
                raise ValueError()
        except ValueError:
            messagebox.showwarning('Координаты', 'Неверные X или Y.')
            return
        self.outline_points[i] = [round(x, 5), round(y, 5)]
        self.complex_roof = None
        self._touch()

    def validate_current(self):
        if not self.outline_closed:
            messagebox.showwarning('Проверка', 'Контур пока не замкнут.')
            return
        err = validate_polygon(self.outline_points)
        messagebox.showwarning('Проверка', err) if err else messagebox.showinfo('Проверка', 'Контур корректен: пересечений нет.')

    def delete_last_ridge(self):
        if self.manual_ridges:
            self.manual_ridges.pop()
            self.recalc()

    def refresh_outline_status(self):
        if not hasattr(self, 'outline_summary'):
            return
        pts = self.outline_points
        n = len(pts)
        total = sum(distance(a, b) for a, b in polygon_edges(pts, self.outline_closed)) if n > 1 else 0
        closed = 'замкнут' if self.outline_closed else 'не замкнут'
        err = validate_polygon(pts) if self.outline_closed else None
        area = polygon_area(pts) if self.outline_closed and not err else None
        extra = ''
        if self.complex_roof:
            extra = f"  |  Кровля: {self.complex_roof['roof_area_total']:.2f} м², плоскостей {self.complex_roof['plane_count']}, коньки {self.complex_roof['ridge_total']:.2f} м"
        self.outline_summary.set(f'Точек: {n}  |  Контур: {closed}  |  Периметр: {total:.2f} м  |  '
                                 + (f'Площадь пятна здания: {area:.2f} м²' if area is not None else 'Площадь: —')
                                 + (f'  |  ОШИБКА: {err}' if err else '') + extra)
        if self.complex_roof:
            self.status.set('Сложная кровля построена: предварительные плоскости, коньки, ендовы и площади обновлены')
        else:
            self.status.set('Обмерный контур: для расчёта кровли замкните контур и задайте параметры высоты/уклона')

    def _model_bounds(self):
        p = self.outline_points or [[0, 0], [20, 12]]
        xs = [v[0] for v in p]
        ys = [v[1] for v in p]
        return min(xs), min(ys), max(xs), max(ys)

    def _set_transform(self, c):
        x0, y0, x1, y1 = self._model_bounds()
        w = max(c.winfo_width(), 500)
        h = max(c.winfo_height(), 300)
        spread_x = max(x1 - x0, 5)
        spread_y = max(y1 - y0, 5)
        self.scale = min((w - 125) / spread_x, (h - 130) / spread_y)
        self.ox = (w - spread_x * self.scale) / 2 - x0 * self.scale
        self.oy = (h - spread_y * self.scale) / 2 - y0 * self.scale

    def _plane_fill(self, idx):
        palette = ['#E6EEFF', '#DCEBFF', '#EAF3FF', '#D7E7FB', '#E7F0FA', '#DCE7F8', '#ECF4FF', '#E4EEFA']
        return palette[(idx - 1) % len(palette)]

    def render(self):
        if self.roof_type_choice == 'Двускатная' and not self.custom_outline and hasattr(self, 'canvas') and self.canvas is not None and self.canvas.winfo_exists():
            return self._render_gable()
        if not getattr(self, 'custom_outline', False) or not hasattr(self, 'canvas') or self.canvas is None or not self.canvas.winfo_exists() or getattr(self, 'tab', None) not in ('Контур здания', 'Геометрия', 'Элементы кровли'):
            return super().render()
        c = self.canvas
        c.delete('all')
        self._set_transform(c)
        p = self.outline_points
        width, height = c.winfo_width(), c.winfo_height()

        step = 1
        for candidate in [0.5, 1, 2, 5, 10, 20, 50, 100]:
            step = candidate
            if step * self.scale >= 30:
                break
        mx, my, Mx, My = self._model_bounds()
        for i in range(math.floor(mx / step) - 2, math.ceil(Mx / step) + 3):
            sx = self.ox + i * step * self.scale
            c.create_line(sx, 0, sx, height, fill='#E9EEF6')
        for i in range(math.floor(my / step) - 2, math.ceil(My / step) + 3):
            sy = self.oy + i * step * self.scale
            c.create_line(0, sy, width, sy, fill='#E9EEF6')

        if self.complex_roof and self.outline_closed:
            for plane in self.complex_roof['planes']:
                flat = [u for pt in plane.polygon for u in self.screen(*pt)]
                c.create_polygon(*flat, fill=self._plane_fill(plane.index), outline='')
                cx = sum(pt[0] for pt in plane.polygon) / len(plane.polygon)
                cy = sum(pt[1] for pt in plane.polygon) / len(plane.polygon)
                sx, sy = self.screen(cx, cy)
                c.create_text(sx, sy, text=f'P{plane.index}\n{plane.area:.1f} м²', font=self.f_small, fill='#173A60')
        elif len(p) >= 3 and self.outline_closed:
            c.create_polygon(*[u for pt in p for u in self.screen(*pt)], fill='#E6EEFF', outline='')

        for i, (a, b) in enumerate(polygon_edges(p, self.outline_closed)):
            sa, sb = self.screen(*a), self.screen(*b)
            c.create_line(*sa, *sb, fill='#173A60', width=3)
            cx, cy = (sa[0] + sb[0]) / 2, (sa[1] + sb[1]) / 2
            c.create_rectangle(cx - 35, cy - 10, cx + 35, cy + 10, fill='#FFFFFF', outline='')
            c.create_text(cx, cy, text=f'{distance(a, b):.2f} м', font=self.f_small, fill='#2563EB')

        roof_data = self.complex_roof
        ridge_segs = []
        valley_segs = []
        if roof_data:
            ridge_segs = roof_data['ridge_segments']
            valley_segs = roof_data['valley_segments']
        else:
            ridge_segs = self.manual_ridges
        for i, (a, b) in enumerate(ridge_segs):
            c.create_line(*self.screen(*a), *self.screen(*b), fill='#DC6A2C', width=3, dash=())
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            c.create_text(*self.screen(*m), text=f'К{i + 1}', fill='#C15B27', font=self.f_bold)
        for i, (a, b) in enumerate(valley_segs):
            c.create_line(*self.screen(*a), *self.screen(*b), fill='#8B5CF6', width=3, dash=(6, 3))
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            c.create_text(*self.screen(*m), text=f'Е{i + 1}', fill='#6D47D9', font=self.f_small)
        if self.line_start is not None:
            sx, sy = self.screen(*self.line_start)
            c.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill='#DC6A2C')
        for i, point in enumerate(p):
            x, y = self.screen(*point)
            sel = (i == self.selected_vertex)
            c.create_oval(x - 6, y - 6, x + 6, y + 6, fill='#F97316' if sel else '#2563EB', outline='#FFFFFF', width=1)
            c.create_text(x + 13, y - 13, text=str(i + 1), font=self.f_small, fill='#173A60')
        for i, o in enumerate(self.objects):
            xx, yy = self.screen(float(o['x']), float(o['y']))
            c.create_oval(xx - 10, yy - 10, xx + 10, yy + 10, fill='#F97316', outline='#FFFFFF', width=2)
            c.create_text(xx, yy, text=str(i + 1), fill='white', font=self.f_small)

        if self.outline_closed:
            if roof_data:
                title = (f"Кровля: {roof_data['roof_area_total']:.2f} м² • плоскостей {roof_data['plane_count']} • "
                         f"коньки {roof_data['ridge_total']:.2f} м • ендовы {roof_data['valley_total']:.2f} м")
            else:
                title = 'Контур здания (по обмеру) • задайте параметры и нажмите «Построить кровлю»'
            c.create_text(width / 2, 22, text=title, font=self.f_bold, fill='#173A60')
        else:
            c.create_text(width / 2, 22, text='Ввод стен по длинам и направлениям • контур не замкнут', font=self.f_bold, fill='#173A60')
        self.refresh_outline_status()

    def _render_gable(self):
        c = self.canvas
        c.delete('all')
        g = self.g
        w = max(c.winfo_width(), 500)
        h = max(c.winfo_height(), 300)
        D, W = g['D'], g['W']
        self.scale = min((w - 140) / D, (h - 145) / W)
        self.ox = (w - D * self.scale) / 2
        self.oy = (h - W * self.scale) / 2
        c.create_rectangle(*self.screen(0, 0), *self.screen(D, W), fill='#E3ECFA', outline='#173A60', width=3)
        c.create_line(*self.screen(0, W / 2), *self.screen(D, W / 2), fill='#173A60', width=3)
        c.create_text(w / 2, 22, text=f'Двускатная кровля • {g["area"]:.2f} м²', fill='#2563EB', font=self.f_bold)
        for i, o in enumerate(self.objects):
            x, y = self.screen(o['x'], o['y'])
            c.create_oval(x - 9, y - 9, x + 9, y + 9, fill='#F97316', outline='white')
        c.create_text(w / 2, self.oy + W * self.scale + 30, text=f'{D:.2f} м', fill='#2563EB', font=self.f_bold)

    def coords(self, x, y):
        if self.custom_outline and getattr(self, 'tab', None) in ('Контур здания', 'Геометрия', 'Элементы кровли', 'Стропильная система', 'Обрешётка'):
            return (x - self.ox) / self.scale, (y - self.oy) / self.scale
        return super().coords(x, y)

    @staticmethod
    def point_in_polygon(point, poly):
        if len(poly) < 3:
            return False
        x, y = point
        inside = False
        for a, b in polygon_edges(poly):
            if on_segment(a, b, point):
                return True
            if (a[1] > y) != (b[1] > y):
                if x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                    inside = not inside
        return inside

    def click(self, event):
        if self.custom_outline and getattr(self, 'tab', None) == 'Элементы кровли':
            x, y = self.coords(event.x, event.y)
            if self.mode != 'select':
                if not self.outline_closed or not self.point_in_polygon((x, y), self.outline_points):
                    self.status.set('Укажите точку внутри замкнутого контура здания')
                    return
                self.objects.append({'type': self.mode, 'x': round(x, 3), 'y': round(y, 3)})
                self.selected = len(self.objects) - 1
                self.mode = 'select'
                self.render()
                return
            self.selected = None
            for i in range(len(self.objects) - 1, -1, -1):
                a, b = self.screen(self.objects[i]['x'], self.objects[i]['y'])
                if math.hypot(a - event.x, b - event.y) < 18:
                    self.selected = i
                    break
            self.drag_index = self.selected
            self.render()
            return
        if not self.custom_outline or getattr(self, 'tab', None) != 'Контур здания':
            return super().click(event)
        x, y = self.coords(event.x, event.y)
        if self.outline_mode == 'ridge':
            pt = [round(x, 4), round(y, 4)]
            if self.line_start is None:
                self.line_start = pt
            else:
                if distance(self.line_start, pt) > 0.05:
                    self.manual_ridges.append([self.line_start, pt])
                self.line_start = None
                self.outline_mode = 'select'
                self.recalc()
            self.render()
            return
        if self.outline_mode == 'point':
            if self.outline_closed:
                messagebox.showinfo('Контур', 'Сначала нажмите «Отменить точку», чтобы разомкнуть контур.')
            else:
                self.outline_points.append([round(x, 3), round(y, 3)])
                self.selected_vertex = len(self.outline_points) - 1
            self.outline_mode = 'select'
            self._touch()
            return
        self.selected_vertex = None
        for i, pt in enumerate(self.outline_points):
            if math.hypot(self.screen(*pt)[0] - event.x, self.screen(*pt)[1] - event.y) < 14:
                self.selected_vertex = i
                break
        self.outline_drag = self.selected_vertex
        if self.selected_vertex is not None:
            xx, yy = self.outline_points[self.selected_vertex]
            self.point_x.set(f'{xx:.3f}')
            self.point_y.set(f'{yy:.3f}')
        self.render()

    def drag(self, event):
        if self.custom_outline and getattr(self, 'tab', None) == 'Элементы кровли':
            i = getattr(self, 'drag_index', None)
            if i is not None and 0 <= i < len(self.objects):
                x, y = self.coords(event.x, event.y)
                if self.point_in_polygon((x, y), self.outline_points):
                    self.objects[i]['x'] = round(x, 3)
                    self.objects[i]['y'] = round(y, 3)
                    self.render()
            return
        if not self.custom_outline or getattr(self, 'tab', None) != 'Контур здания':
            return super().drag(event)
        i = self.outline_drag
        if i is None or i >= len(self.outline_points):
            return
        x, y = self.coords(event.x, event.y)
        self.outline_points[i] = [round(x, 2), round(y, 2)]
        self.point_x.set(f'{x:.2f}')
        self.point_y.set(f'{y:.2f}')
        self.complex_roof = None
        self.render()

    def recalc(self):
        if not self.custom_outline:
            self.complex_roof = None
            return super().recalc()
        self.res['items'].set(str(len(self.objects)))
        if not self.outline_closed:
            for k in ('area', 'side_area', 'end_area', 'ridge', 'height', 'slope', 'rafters', 'laths', 'planes', 'valleys'):
                self.res[k].set('—')
            self.status.set('Сначала замкните контур здания')
            self.render()
            if getattr(self, 'tab', None) == 'Ведомости' and hasattr(self, 'data_table'):
                self.fill_table()
            return
        err = validate_polygon(self.outline_points)
        if err:
            messagebox.showwarning('Проверка контура', err)
            for k in ('area', 'side_area', 'end_area', 'ridge', 'height', 'slope', 'rafters', 'laths', 'planes', 'valleys'):
                self.res[k].set('—')
            self.complex_roof = None
            self.render()
            return
        try:
            eave_h = self._float_value('eave_height', 0.0)
            ridge_h = self._float_value('ridge_height', 3.2)
            pitch = self._float_value('complex_pitch', 28.0)
            self.complex_roof = generate_roof_geometry(self.outline_points, self.manual_ridges, eave_h, ridge_h, pitch)
        except Exception as ex:
            self.complex_roof = None
            messagebox.showwarning('Построение кровли', str(ex))
            return
        roof = self.complex_roof
        main_area = sum(p.area for p in roof['planes'] if p.kind == 'Основной')
        aux_area = roof['roof_area_total'] - main_area
        self.res['area'].set(f"{roof['roof_area_total']:.2f} м²")
        self.res['side_area'].set(f"{main_area:.2f} м²")
        self.res['end_area'].set(f"{aux_area:.2f} м²")
        self.res['ridge'].set(f"{roof['ridge_total']:.2f} м")
        self.res['height'].set(f"{roof['rise']:.2f} м")
        self.res['slope'].set(f"{roof['avg_slope']:.1f}°")
        self.res['rafters'].set('—')
        self.res['laths'].set('—')
        self.res['planes'].set(str(roof['plane_count']))
        self.res['valleys'].set(f"{len(roof['valley_segments'])} / {roof['valley_total']:.2f} м")
        self.status.set('Сложная кровля рассчитана: площади плоскостей, коньки и ендовы обновлены')
        if getattr(self, 'tab', None) == 'Ведомости' and hasattr(self, 'data_table'):
            self.fill_table()
        self.render()

    def fill_table(self):
        if not self.custom_outline:
            return super().fill_table()
        table = getattr(self, 'data_table', None)
        if table is None or not table.winfo_exists():
            return
        for row in table.get_children():
            table.delete(row)
        valid = self.outline_closed and not validate_polygon(self.outline_points)
        area_outline = roof_polygon_area(self.outline_points) if valid else 0.0
        table.insert('', 'end', values=('Обмеры', 'Площадь пятна здания', f'{area_outline:.2f}' if valid else '—', 'м²'))
        if not self.complex_roof:
            table.insert('', 'end', values=('Кровля', 'Площадь скатов', 'не определена', 'м²'))
            table.insert('', 'end', values=('Кровля', 'Ручные линии конька', len(self.manual_ridges), 'шт.'))
            table.insert('', 'end', values=('Элементы', 'Размещённые объекты', len(self.objects), 'шт.'))
            return
        roof = self.complex_roof
        table.insert('', 'end', values=('Кровля', 'Суммарная площадь скатов', f"{roof['roof_area_total']:.2f}", 'м²'))
        table.insert('', 'end', values=('Кровля', 'Суммарная длина коньков', f"{roof['ridge_total']:.2f}", 'м'))
        table.insert('', 'end', values=('Кровля', 'Суммарная длина ендов', f"{roof['valley_total']:.2f}", 'м'))
        table.insert('', 'end', values=('Кровля', 'Средний уклон', f"{roof['avg_slope']:.1f}", '°'))
        for plane in roof['planes']:
            table.insert('', 'end', values=(f'Плоскость P{plane.index}', f'{plane.kind} скат (у стены {plane.edge_index})', f'{plane.area:.2f}', 'м²'))
        table.insert('', 'end', values=('Элементы', 'Размещённые объекты', len(self.objects), 'шт.'))

    def _defaults_for_new(self):
        return {'name': 'Новый проект', 'length': 20, 'width': 12, 'eave': 0.6, 'side': 7.3, 'end': 7.3,
                'rafter_step': 1.0, 'rafter_size': '50×200', 'lath_step': 0.4, 'lath_size': '50×150',
                'cover': 'Профлист', 'eave_height': 0.0, 'ridge_height': 3.2, 'complex_pitch': 28.0}

    def new(self):
        if not messagebox.askyesno('Новый проект', 'Очистить текущие данные и создать новый проект?'):
            return
        self.objects = []
        self.selected = None
        self.path = None
        for k, v in self._defaults_for_new().items():
            self.values[k].set(str(v))
        self.custom_outline = False
        self.outline_points = []
        self.outline_closed = False
        self.manual_ridges = []
        self.complex_roof = None
        self.roof_type_choice = 'Вальмовая'
        if hasattr(self, 'roof_choice'):
            self.roof_choice.set(self.roof_type_choice)
        self.recalc()
        self.switch('Геометрия')

    def save(self, asnew=False):
        import json
        from pathlib import Path
        from tkinter import filedialog
        path = None if asnew else self.path
        if not path:
            path = filedialog.asksaveasfilename(title='Сохранить проект', defaultextension='.roof.json', filetypes=[('Проект RoofStudio', '*.json')])
        if not path:
            return
        data = {'version': '0.7', 'roof_type': self.roof_type_choice, 'parameters': {k: v.get() for k, v in self.values.items()}, 'objects': self.objects,
                'outline': {'enabled': self.custom_outline, 'points': self.outline_points,
                            'closed': self.outline_closed, 'manual_ridges': self.manual_ridges}}
        try:
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            self.path = path
            self.status.set('Проект сохранён: ' + path)
        except OSError as e:
            messagebox.showerror('Сохранение', str(e))

    def load(self):
        from pathlib import Path
        import json
        from tkinter import filedialog
        path = filedialog.askopenfilename(title='Открыть проект', filetypes=[('Проект RoofStudio', '*.json')])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            params = data.get('parameters', data)
            for k in self.values:
                if k in params:
                    self.values[k].set(str(params[k]))
            self.objects = [o for o in data.get('objects', []) if isinstance(o, dict) and {'type', 'x', 'y'} <= o.keys()]
            out = data.get('outline', {})
            self.roof_type_choice = data.get('roof_type', 'Вальмовая')
            if hasattr(self, 'roof_choice'):
                self.roof_choice.set(self.roof_type_choice)
            self.custom_outline = bool(out.get('enabled', False))
            self.outline_points = [[float(x), float(y)] for x, y in out.get('points', [])]
            self.outline_closed = bool(out.get('closed', False))
            self.manual_ridges = [[[float(x), float(y)] for x, y in seg] for seg in out.get('manual_ridges', [])]
            if len(self.outline_points) > 500 or len(self.manual_ridges) > 500:
                raise ValueError('Слишком большой проект')
            self.path = path
            self.recalc()
            self.switch('Контур здания' if self.custom_outline else 'Геометрия')
            self.status.set('Открыт проект: ' + path)
        except (OSError, ValueError, TypeError, KeyError) as e:
            messagebox.showerror('Открытие', str(e))

    def export_csv(self):
        if not self.custom_outline:
            return super().export_csv()
        from tkinter import filedialog
        import csv
        path = filedialog.asksaveasfilename(title='Ведомость обмеров CSV', defaultextension='.csv', filetypes=[('CSV', '*.csv')])
        if not path:
            return
        valid = self.outline_closed and not validate_polygon(self.outline_points)
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['RoofStudio v0.7', '', ''])
            w.writerow(['Показатель', 'Значение', 'Единица'])
            w.writerow(['Площадь пятна здания', f'{roof_polygon_area(self.outline_points):.3f}' if valid else 'Не определена', 'м²'])
            if self.complex_roof:
                w.writerow(['Площадь скатов', f"{self.complex_roof['roof_area_total']:.3f}", 'м²'])
                w.writerow(['Длина коньков', f"{self.complex_roof['ridge_total']:.3f}", 'м'])
                w.writerow(['Длина ендов', f"{self.complex_roof['valley_total']:.3f}", 'м'])
                for plane in self.complex_roof['planes']:
                    w.writerow([f'Плоскость P{plane.index}', f'{plane.area:.3f}', 'м²'])
            else:
                w.writerow(['Площадь скатов', 'Не определена', 'м²'])
            w.writerow(['Число вершин', len(self.outline_points), 'шт.'])
            for i, (a, b) in enumerate(polygon_edges(self.outline_points, self.outline_closed), 1):
                w.writerow([f'Стена {i}', f'{distance(a, b):.3f}', 'м'])
        self.status.set('Ведомость обмеров CSV: ' + path)

    def export_dxf(self):
        if not self.custom_outline and self.roof_type_choice == 'Двускатная':
            from tkinter import filedialog
            from cad_export import write_gable_dxf
            path = filedialog.asksaveasfilename(title='Экспорт двускатной кровли DXF', defaultextension='.dxf', filetypes=[('AutoCAD DXF', '*.dxf')])
            if path:
                try:
                    write_gable_dxf(path, self.g['D'], self.g['W'])
                    self.status.set('Двускатная кровля DXF: ' + path)
                except OSError as e:
                    messagebox.showerror('Ошибка DXF', str(e))
            return
        if not self.custom_outline:
            return super().export_dxf()
        from tkinter import filedialog
        if not self.outline_closed or validate_polygon(self.outline_points):
            messagebox.showwarning('DXF', 'Перед экспортом замкните и проверьте контур.')
            return
        path = filedialog.asksaveasfilename(title='Экспорт обмерного плана DXF', defaultextension='.dxf', filetypes=[('AutoCAD DXF', '*.dxf')])
        if not path:
            return
        from cad_export import write_outline_dxf
        try:
            planes = self.complex_roof['planes'] if self.complex_roof else []
            valleys = self.complex_roof['valley_segments'] if self.complex_roof else []
            ridges = self.complex_roof['ridge_segments'] if self.complex_roof else self.manual_ridges
            write_outline_dxf(path, self.outline_points, ridges, self.objects, valleys=valleys, planes=planes)
            self.status.set('DXF обмерного плана (мм, 1:1): ' + path)
        except (OSError, ValueError) as e:
            messagebox.showerror('Ошибка DXF', str(e))
