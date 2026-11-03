"""RoofStudio attic module: editable attic inner outline, shaft catalog, placement, section."""
import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from attic_model import (WALL_PRESETS, ceil5, offset_polygon_inward, polygon_area,
                         point_in_polygon, shaft_corners, shaft_quantities,
                         validate_shaft_placement, section_geometry)
from perimeter_editor import validate_polygon

BG = '#FFFFFF'
TEXT = '#162033'
MUTED = '#6B778C'
BLUE = '#2563EB'

DEFAULT_SHAFT_CATALOG = [
    dict(id='vsh1', code='ВШ1', construction='Сборная', width_mm=500, length_mm=500,
         wall_mm=60, insulation_mm=50, above_roof_mm=800, insulate_attic=True, note='Уточнить конструкцию по обследованию'),
    dict(id='vsh2', code='ВШ2', construction='Железобетонная', width_mm=300, length_mm=1100,
         wall_mm=80, insulation_mm=50, above_roof_mm=800, insulate_attic=True, note='Пример типоразмера, не норматив'),
    dict(id='vsh3', code='ВШ3', construction='Блочная', width_mm=460, length_mm=1350,
         wall_mm=80, insulation_mm=50, above_roof_mm=800, insulate_attic=True, note='Пример типоразмера, не норматив'),
]


class AtticMixin:
    def __init__(self):
        self.wall_material = 'Кирпичный'
        self.wall_preset = 'Кирпич 510 мм'
        self.wall_thickness_mm = 510.0
        self.wall_above_slag_mm = 400.0
        self.section_cut_x_m = 10.0
        self.shaft_catalog = [dict(t) for t in DEFAULT_SHAFT_CATALOG]
        self.shaft_instances = []
        self.attic_mode = 'select'
        self.attic_selected = None
        self.attic_drag = None
        self.current_shaft_id = 'vsh1'
        self.attic_vars = {}
        self.attic_scale = 1.0
        self.attic_ox = 0
        self.attic_oy = 0
        self.attic_canvas = None
        self.section_canvas = None
        super().__init__()
        self.title('RoofStudio v0.8 — Проектирование кровли и чердака')

    def _attic_outline(self):
        if self.custom_outline:
            if not self.outline_closed or validate_polygon(self.outline_points):
                raise ValueError('Для чердака нужен корректный замкнутый контур здания')
            return [(float(x),float(y)) for x,y in self.outline_points]
        try:
            L = float(self.values['length'].get().replace(',','.'))
            B = float(self.values['width'].get().replace(',','.'))
        except ValueError:
            raise ValueError('Укажите длину и ширину дома')
        if L <= 0 or B <= 0:
            raise ValueError('Длина и ширина должны быть положительными')
        return [(0,0),(L,0),(L,B),(0,B)]

    def _inner_outline(self):
        return offset_polygon_inward(self._attic_outline(),self.wall_thickness_mm/1000)

    def _type(self, id):
        return next((t for t in self.shaft_catalog if t['id']==id),None)

    def _roof_height(self):
        # roof settings in main project are absolute levels from slag
        try:
            val=float(self.values['ridge_height'].get().replace(',','.'))*1000
            pitch=float(self.values['complex_pitch'].get().replace(',','.'))
        except (ValueError,KeyError):
            val,pitch=3200.0,28.0
        return max(val,self.wall_above_slag_mm+5),pitch

    def switch(self,tab):
        if tab not in ('Чердак','Каталог ВШ','Разрез 1–1'):
            self.attic_canvas=None
            self.section_canvas=None
            return super().switch(tab)
        self.tab=tab
        self.mark_tab(tab)
        for child in self.workspace.winfo_children():child.destroy()
        self.canvas=None
        self.data_table=None
        if tab=='Чердак':self._build_attic()
        elif tab=='Каталог ВШ':self._build_shaft_catalog()
        else:self._build_section()

    def _frame_head(self,name):
        head=tk.Frame(self.workspace,bg=BG)
        head.pack(fill='x',padx=12,pady=(10,6))
        tk.Label(head,text=name,bg=BG,fg=TEXT,font=self.f_h2).pack(side='left')
        return head

    def _entry(self,parent,label,value,width=9):
        tk.Label(parent,text=label,bg=BG,fg=TEXT,font=self.f_small).pack(side='left',padx=(8,3))
        var=tk.StringVar(value=str(value))
        ttk.Entry(parent,textvariable=var,width=width).pack(side='left',padx=(0,5))
        return var

    def _build_attic(self):
        h=self._frame_head('План чердака')
        self.button(h,'DXF чердака',self.export_attic_dxf,padx=9,side='right')
        self.button(h,'Справочник ВШ',lambda:self.switch('Каталог ВШ'),padx=9,side='right')
        self.button(h,'Разрез 1–1',lambda:self.switch('Разрез 1–1'),padx=9,side='right')
        row=tk.Frame(self.workspace,bg=BG)
        row.pack(fill='x',padx=12,pady=(2,7))
        tk.Label(row,text='Тип дома:',bg=BG,font=self.f_small).pack(side='left')
        material=tk.StringVar(value=self.wall_material)
        self.attic_vars['wall_material']=material
        cb=ttk.Combobox(row,textvariable=material,values=list(WALL_PRESETS),width=13,state='readonly')
        cb.pack(side='left',padx=4)
        tk.Label(row,text='Толщина:',bg=BG,font=self.f_small).pack(side='left')
        wall_option=tk.StringVar(value=self.wall_preset)
        self.attic_vars['wall_preset']=wall_option
        opts=ttk.Combobox(row,textvariable=wall_option,values=[label for label,_ in WALL_PRESETS[self.wall_material]],width=18,state='readonly')
        opts.pack(side='left',padx=4)
        wall_var=self._entry(row,'Факт, мм',f'{self.wall_thickness_mm:g}',7)
        self.attic_vars['wall_mm']=wall_var
        def change_material(_event=None):
            self.wall_material=material.get(); options=WALL_PRESETS[self.wall_material]
            opts.configure(values=[label for label,_ in options]);wall_option.set(options[0][0]);wall_var.set(str(options[0][1]))
        def change_preset(_event=None):
            for label,mm in WALL_PRESETS[material.get()]:
                if label==wall_option.get():wall_var.set(str(mm));break
        cb.bind('<<ComboboxSelected>>',change_material)
        opts.bind('<<ComboboxSelected>>',change_preset)
        wh=self._entry(row,'Стена над шлаком, мм',f'{self.wall_above_slag_mm:g}',7)
        self.attic_vars['wall_above_slag_mm']=wh
        self.button(row,'Применить',self._apply_attic_settings,True,padx=8)
        row2=tk.Frame(self.workspace,bg=BG)
        row2.pack(fill='x',padx=12,pady=(0,7))
        tk.Label(row2,text='Марка ВШ:',bg=BG,font=self.f_small).pack(side='left')
        codevar=tk.StringVar(value=self._type(self.current_shaft_id)['code'] if self._type(self.current_shaft_id) else '')
        self.attic_vars['shaft_code']=codevar
        cb2=ttk.Combobox(row2,textvariable=codevar,values=[t['code'] for t in self.shaft_catalog],state='readonly',width=12)
        cb2.pack(side='left',padx=4)
        cb2.bind('<<ComboboxSelected>>',lambda e:self._choose_shaft_code(codevar.get()))
        self.button(row2,'+ Разместить ВШ',lambda:self._attic_set_mode('place'),True,padx=9)
        self.button(row2,'Выбрать/переместить',lambda:self._attic_set_mode('select'),padx=9)
        self.button(row2,'Повернуть 90°',self._rotate_selected,padx=8)
        self.button(row2,'Удалить ВШ',self._delete_selected,padx=8)
        self.button(row2,'Обновить план',self._render_attic,padx=9)
        self.attic_canvas=tk.Canvas(self.workspace,bg='#F8FAFD',highlightthickness=0,cursor='crosshair')
        self.attic_canvas.pack(fill='both',expand=True,padx=14,pady=(3,6))
        self.attic_canvas.bind('<Configure>',lambda e:self._render_attic())
        self.attic_canvas.bind('<Button-1>',self._attic_click)
        self.attic_canvas.bind('<B1-Motion>',self._attic_motion)
        self.attic_canvas.bind('<ButtonRelease-1>',lambda e:setattr(self,'attic_drag',None))
        self.attic_status=tk.StringVar(value='')
        tk.Label(self.workspace,textvariable=self.attic_status,bg=BG,fg=BLUE,font=self.f_bold,anchor='w').pack(fill='x',padx=18,pady=(0,5))
        self._render_attic()

    def _choose_shaft_code(self,code):
        item=next((s for s in self.shaft_catalog if s['code']==code),None)
        if item:self.current_shaft_id=item['id']

    def _apply_attic_settings(self):
        v=self.attic_vars
        try:
            mm=float(v['wall_mm'].get().replace(',','.'))
            wall_h=float(v['wall_above_slag_mm'].get().replace(',','.'))
            if not 20<=mm<3000 or not 0<=wall_h<=15000:
                raise ValueError('Толщина от 20 до 2999 мм, высота от 0 до 15000 мм')
            offset_polygon_inward(self._attic_outline(),mm/1000)
        except Exception as e:
            messagebox.showwarning('Толщина стен',str(e));return
        self.wall_material=v['wall_material'].get()
        self.wall_preset=v['wall_preset'].get()
        self.wall_thickness_mm=mm
        self.wall_above_slag_mm=wall_h
        self.recalc()
        self._render_attic()

    def _attic_set_mode(self,mode):
        self.attic_mode=mode
        self.status.set('Щёлкни на внутреннем контуре, чтобы установить ВШ' if mode=='place' else 'Выбор и перетаскивание ВШ')

    def _attic_transform(self):
        c=self.attic_canvas
        outline=self._attic_outline()
        xs=[p[0] for p in outline];ys=[p[1] for p in outline]
        minx,maxx,miny,maxy=min(xs),max(xs),min(ys),max(ys)
        width=max(c.winfo_width(),550);height=max(c.winfo_height(),220)
        self.attic_scale=min((width-110)/max(maxx-minx,2),(height-100)/max(maxy-miny,2))
        self.attic_ox=(width-(maxx-minx)*self.attic_scale)/2-minx*self.attic_scale
        self.attic_oy=(height-(maxy-miny)*self.attic_scale)/2-miny*self.attic_scale
        return outline

    def _attic_screen(self,p):
        return self.attic_ox+p[0]*self.attic_scale,self.attic_oy+p[1]*self.attic_scale

    def _attic_model(self,x,y):
        return (x-self.attic_ox)/self.attic_scale,(y-self.attic_oy)/self.attic_scale

    def _render_attic(self):
        c=self.attic_canvas
        if c is None or not c.winfo_exists():return
        c.delete('all')
        try:
            outer=self._attic_transform()
            inner=self._inner_outline()
        except Exception as e:
            c.create_text(c.winfo_width()/2,100,text=str(e),fill='#B91C1C',font=self.f_bold)
            if hasattr(self,'attic_status'):self.attic_status.set('Невозможно построить внутренний контур')
            return
        w,h=c.winfo_width(),c.winfo_height()
        step=1
        for v in [0.5,1,2,5,10,20,50]:
            step=v
            if step*self.attic_scale>=32:break
        for idx in range(int(w/(step*self.attic_scale))+4):
            xx=(idx-2)*step*self.attic_scale+w/2 % (step*self.attic_scale)
            c.create_line(xx,0,xx,h,fill='#E9EEF6')
        for idx in range(int(h/(step*self.attic_scale))+4):
            yy=(idx-2)*step*self.attic_scale+h/2 % (step*self.attic_scale)
            c.create_line(0,yy,w,yy,fill='#E9EEF6')
        c.create_polygon(*[v for p in outer for v in self._attic_screen(p)],fill='#E1E7F0',outline='#173A60',width=3)
        c.create_polygon(*[v for p in inner for v in self._attic_screen(p)],fill='#FFFFFF',outline='#2563EB',width=2)
        for i,(a,b) in enumerate(zip(outer,outer[1:]+outer[:1])):
            aa=self._attic_screen(a);bb=self._attic_screen(b)
            x,y=(aa[0]+bb[0])/2,(aa[1]+bb[1])/2
            c.create_text(x,y,text=f'{math.dist(a,b):.2f}',fill='#1D4FD0',font=self.f_small)
        for i,instance in enumerate(self.shaft_instances):
            shaft=self._type(instance['type_id'])
            if not shaft:continue
            pts=shaft_corners(instance,shaft)
            coords=[v for p in pts for v in self._attic_screen(p)]
            good=validate_shaft_placement(instance,shaft,inner)
            c.create_polygon(*coords,fill='#FDBA74' if good else '#FECACA',outline=BLUE if i==self.attic_selected else '#C2410C',width=3 if i==self.attic_selected else 2)
            x,y=self._attic_screen((instance['x'],instance['y']))
            c.create_text(x,y,text=shaft['code'],fill='#7C2D12',font=self.f_small)
        if hasattr(self,'attic_status'):
            self.attic_status.set(f'Тип: {self.wall_material} • толщина стены {self.wall_thickness_mm:g} мм • '
                f'Пятно {polygon_area(outer):.2f} м² • чистая площадь чердака {polygon_area(inner):.2f} м² • ВШ: {len(self.shaft_instances)}')

    def _attic_hit(self,x,y):
        for i in range(len(self.shaft_instances)-1,-1,-1):
            o=self.shaft_instances[i]; t=self._type(o['type_id'])
            if not t:continue
            pts=shaft_corners(o,t)
            if point_in_polygon((x,y),pts):return i
            if math.hypot(o['x']-x,o['y']-y)<max(10/self.attic_scale,0.1):return i
        return None

    def _attic_click(self,event):
        try:inner=self._inner_outline()
        except Exception:return
        x,y=self._attic_model(event.x,event.y)
        if self.attic_mode=='place':
            shaft=self._type(self.current_shaft_id)
            if not shaft:
                messagebox.showwarning('Каталог ВШ','Выберите тип ВШ');return
            inst={'type_id':shaft['id'],'x':round(x,3),'y':round(y,3),'rotation':0}
            if not validate_shaft_placement(inst,shaft,inner):
                self.status.set('ВШ не помещается внутри контура чердака');return
            self.shaft_instances.append(inst)
            self.attic_selected=len(self.shaft_instances)-1
            self.attic_mode='select'
            self._render_attic();return
        self.attic_selected=self._attic_hit(x,y)
        self.attic_drag=self.attic_selected
        self._render_attic()

    def _attic_motion(self,event):
        i=self.attic_drag
        if i is None:return
        x,y=self._attic_model(event.x,event.y)
        obj=self.shaft_instances[i]
        candidate={**obj,'x':round(x,3),'y':round(y,3)}
        try:inner=self._inner_outline()
        except Exception:return
        t=self._type(obj['type_id'])
        if t and validate_shaft_placement(candidate,t,inner):
            self.shaft_instances[i]=candidate
            self._render_attic()

    def _rotate_selected(self):
        i=self.attic_selected
        if i is None:
            self.status.set('Сначала выберите ВШ на плане');return
        obj=self.shaft_instances[i]
        candidate={**obj,'rotation':(int(obj.get('rotation',0))+90)%180}
        t=self._type(obj['type_id'])
        if t and validate_shaft_placement(candidate,t,self._inner_outline()):
            self.shaft_instances[i]=candidate
            self._render_attic()
        else:messagebox.showwarning('Поворот','После поворота ВШ выходит за пределы чердака')

    def _delete_selected(self):
        i=self.attic_selected
        if i is not None:
            self.shaft_instances.pop(i);self.attic_selected=None;self._render_attic()

    def _build_shaft_catalog(self):
        head=self._frame_head('Каталог вентиляционных шахт')
        self.button(head,'Добавить тип',lambda:self._shaft_dialog(None),True,side='right')
        self.button(head,'Изменить тип',lambda:self._shaft_dialog(self._catalog_selected()),side='right')
        self.button(head,'Удалить тип',self._catalog_remove,side='right')
        self.button(head,'Вернуться к чердаку',lambda:self.switch('Чердак'),side='right')
        columns=('code','construction','width_mm','length_mm','wall_mm','above_roof_mm','insulation_mm','count')
        self.catalog_table=ttk.Treeview(self.workspace,columns=columns,show='headings',style='Table.Treeview')
        for key,title in zip(columns,('Марка','Конструкция','Ширина, мм','Длина, мм','Стенка, мм','Над кровлей, мм','Утеплитель, мм','На плане')):
            self.catalog_table.heading(key,text=title)
            self.catalog_table.column(key,width=100,anchor='center')
        self.catalog_table.pack(fill='both',expand=True,padx=16,pady=8)
        self.catalog_table.bind('<Double-1>',lambda e:self._shaft_dialog(self._catalog_selected()))
        self._update_catalog()
        tk.Label(self.workspace,text='Введённые типоразмеры — пользовательские. Расход оцинковки и утеплителя считается предварительно по наружным граням ВШ.',
            bg=BG,fg=MUTED,font=self.f_small,wraplength=900).pack(padx=15,pady=9,anchor='w')

    def _update_catalog(self):
        if not hasattr(self,'catalog_table') or not self.catalog_table.winfo_exists():return
        for row in self.catalog_table.get_children():self.catalog_table.delete(row)
        for t in self.shaft_catalog:
            count=sum(o['type_id']==t['id'] for o in self.shaft_instances)
            self.catalog_table.insert('', 'end', iid=t['id'],values=tuple(t[k] for k in ('code','construction','width_mm','length_mm','wall_mm','above_roof_mm','insulation_mm'))+(count,))

    def _catalog_selected(self):
        sel=self.catalog_table.selection() if hasattr(self,'catalog_table') else ()
        return sel[0] if sel else None

    def _catalog_remove(self):
        id=self._catalog_selected()
        if id is None:return
        if any(o['type_id']==id for o in self.shaft_instances):
            messagebox.showwarning('Удаление','Сначала удалите все экземпляры ВШ этого типа на плане');return
        self.shaft_catalog=[t for t in self.shaft_catalog if t['id']!=id]
        if self.current_shaft_id==id:self.current_shaft_id=self.shaft_catalog[0]['id'] if self.shaft_catalog else None
        self._update_catalog()

    def _shaft_dialog(self,id=None):
        old=self._type(id) if id else None
        w=tk.Toplevel(self)
        w.title('Редактирование типа ВШ' if old else 'Добавление типа ВШ')
        w.configure(bg=BG)
        w.resizable(False,False)
        w.transient(self);w.grab_set()
        fields=[('code','Марка','ВШ4'),('construction','Конструкция','Сборная'),
                ('width_mm','Ширина наружная, мм',500),('length_mm','Длина наружная, мм',500),
                ('wall_mm','Толщина стенки ВШ, мм',60),('above_roof_mm','Возвышение над кровлей, мм',800),
                ('insulation_mm','Толщина утепления, мм',50),('note','Примечание','')]
        vars={}
        for i,(key,title,default) in enumerate(fields):
            tk.Label(w,text=title,bg=BG,fg=TEXT,font=self.f_base).grid(row=i,column=0,sticky='w',padx=14,pady=5)
            v=tk.StringVar(value=str(old.get(key,default) if old else default))
            ttk.Entry(w,textvariable=v,width=35).grid(row=i,column=1,padx=14,pady=5)
            vars[key]=v
        def commit():
            try:
                data={k:v.get().strip() for k,v in vars.items()}
                for k in ('width_mm','length_mm','wall_mm','above_roof_mm','insulation_mm'):
                    data[k]=float(data[k].replace(',','.'))
                if not data['code'] or data['width_mm']<50 or data['length_mm']<50 or data['above_roof_mm']<=0 or data['insulation_mm']<0 or not 0<=data['wall_mm']<min(data['width_mm'],data['length_mm'])/2:
                    raise ValueError('Некорректный типоразмер ВШ')
                if any(t['code'].lower()==data['code'].lower() and t['id']!=id for t in self.shaft_catalog):
                    raise ValueError('Такая марка уже существует')
                import uuid
                data['id']=id or uuid.uuid4().hex[:10]
                if old:old.update(data)
                else:self.shaft_catalog.append(data)
                self.current_shaft_id=data['id']
                self._update_catalog()
                w.destroy()
            except ValueError as e:messagebox.showwarning('Параметры ВШ',str(e),parent=w)
        tk.Button(w,text='Сохранить тип ВШ',command=commit,bg=BLUE,fg='white',font=self.f_bold,padx=10,pady=9).grid(row=len(fields),column=0,columnspan=2,pady=12)
        w.wait_window()

    def _build_section(self):
        head=self._frame_head('Разрез 1–1 (предварительный)')
        self.button(head,'DXF разреза',self.export_section_dxf,side='right')
        self.button(head,'План чердака',lambda:self.switch('Чердак'),side='right')
        row=tk.Frame(self.workspace,bg=BG)
        row.pack(fill='x',padx=12,pady=(2,6))
        vx=self._entry(row,'Сечение X, м',f'{self.section_cut_x_m:g}',9)
        wall=self._entry(row,'Стена от шлака, мм',f'{self.wall_above_slag_mm:g}',9)
        self.section_vars={'x':vx,'wall':wall}
        def redraw():
            try:
                self.section_cut_x_m=float(vx.get().replace(',','.'))
                self.wall_above_slag_mm=float(wall.get().replace(',','.'))
                if self.wall_above_slag_mm<0:raise ValueError('Высота стены не может быть отрицательной')
            except ValueError as e:
                messagebox.showwarning('Размер',str(e));return
            self._render_section()
        self.button(row,'Построить разрез',redraw,True,padx=10)
        self.section_canvas=tk.Canvas(self.workspace,bg='#FCFDFE',highlightthickness=0)
        self.section_canvas.pack(fill='both',expand=True,padx=14,pady=(3,6))
        self.section_canvas.bind('<Configure>',lambda e:self._render_section())
        self.section_status=tk.StringVar()
        tk.Label(self.workspace,textvariable=self.section_status,bg=BG,fg=MUTED,font=self.f_small,wraplength=1000,justify='left',anchor='w').pack(fill='x',padx=16,pady=(0,8))
        self._render_section()

    def _render_section(self):
        c=self.section_canvas
        if c is None or not c.winfo_exists():return
        c.delete('all')
        try:
            outline=self._attic_outline()
            ridge_mm,pitch=self._roof_height()
            section=section_geometry(outline,self.section_cut_x_m,self.wall_above_slag_mm,ridge_mm,pitch,float(self.values['eave'].get().replace(',','.')))
        except Exception as e:
            c.create_text(c.winfo_width()/2,120,text=str(e),fill='#B91C1C',font=self.f_bold)
            if hasattr(self,'section_status'):self.section_status.set(str(e))
            return
        w=max(c.winfo_width(),550);h=max(c.winfo_height(),250)
        ymin,ymax=section['ymin'],section['ymax'];span=ymax-ymin
        left=100;right=w-90
        roof_span=span+2*section['eave_projection_m']
        sx=min((right-left)/max(roof_span,1),(h-110)/max(ridge_mm/1000+1,2))
        cx=w/2;floor=h-75
        def xy(y,z):return cx+(y-(ymin+ymax)/2)*sx, floor-z*sx
        wall=self.wall_above_slag_mm
        c.create_line(*xy(ymin-1.0,0),*xy(ymax+1.0,0),fill='#52687D',width=3)
        roof_base=wall/1000
        h_ridge=ridge_mm/1000
        center=(ymin+ymax)/2
        eave=section['eave_projection_m']
        eave_drop= (ridge_mm-wall)/1000 * eave / max(span/2,0.01)
        pts=[(ymin-eave,roof_base-eave_drop),(center,h_ridge),(ymax+eave,roof_base-eave_drop)]
        for a,b in zip(pts,pts[1:]):c.create_line(*xy(*a),*xy(*b),fill='#8C552B',width=5)
        for yy in [ymin,ymax]:
            c.create_rectangle(*xy(yy-0.12,0),*xy(yy+0.12,roof_base),fill='#B8C6D9',outline='#415A77')
        c.create_line(*xy(ymin,0),*xy(ymin,roof_base),fill='#2563EB',width=2)
        c.create_text(*xy(ymin-0.45,roof_base/2),text=f'{ceil5(wall)}',fill=BLUE,font=self.f_bold)
        c.create_text(cx,18,text='Разрез 1–1 • условная геометрия',font=self.f_h2,fill=TEXT)
        c.create_text(cx,floor+23,text=f'Ширина по наружным граням: {span:.2f} м',font=self.f_bold,fill=BLUE)
        c.create_text(cx,xy(center,h_ridge)[1]-18,text=f'+{ridge_mm/1000:.3f} м',font=self.f_bold,fill=BLUE)
        c.create_text(cx+120,xy(center,h_ridge)[1]+35,text=f'Уклон по разрезу {section["effective_pitch_deg"]:.1f}°',font=self.f_small,fill=BLUE)
        shaft_count=0
        for inst in self.shaft_instances:
            t=self._type(inst['type_id'])
            if not t:continue
            # Cut line crosses the shaft footprint, not arbitrary nearby instances
            rect=shaft_corners(inst,t);xmin=min(p[0] for p in rect);xmax=max(p[0] for p in rect)
            if not xmin-1e-8<=self.section_cut_x_m<=xmax+1e-8:continue
            try:
                q=shaft_quantities(inst,t,outline,wall,ridge_mm,pitch)
            except ValueError:continue
            yy=inst['y'];w_m=(t['length_mm'] if inst.get('rotation',0)%180==90 else t['width_mm'])/1000
            x0,y0=xy(yy-w_m/2,0);x1,y1=xy(yy+w_m/2,q['top_from_slag_raw_mm']/1000)
            c.create_rectangle(x0,y1,x1,y0,fill='#FDE8C5',outline='#B45309',width=2)
            # long overall height from slag, short above roof, both rounded UP to 5 mm
            xdim=x1+24+shaft_count*10
            c.create_line(xdim, floor,xdim,y1,fill=BLUE,width=1)
            c.create_text(xdim+24,(floor+y1)/2,text=f"{q['top_from_slag_rounded_mm']} мм",angle=90,fill=BLUE,font=self.f_small)
            y_roof=xy(yy,q['roof_elevation_raw_mm']/1000)[1]
            xshort=x0-17-shaft_count*8
            c.create_line(xshort,y_roof,xshort,y1,fill='#C2410C',width=2)
            c.create_text(xshort-13,(y_roof+y1)/2,text=f"{q['above_roof_rounded_mm']} мм",angle=90,fill='#C2410C',font=self.f_small)
            c.create_text((x0+x1)/2,y1-13,text=t['code'],font=self.f_bold,fill='#92400E')
            shaft_count+=1
        if abs(section['ridge_pitch_difference_mm']) > 5:
            c.create_text(cx,48,text=f"Расхождение заданного уклона и конька: {section['ridge_pitch_difference_mm']:+.1f} мм",fill='#B45309',font=self.f_bold)
        if hasattr(self,'section_status'):
            self.section_status.set(f'Синий размер: высота стены от шлака = {ceil5(wall)} мм. '
                f'Показано ВШ: {shaft_count}. Длинный размер от шлака = отметка кровли в месте ВШ + возвышение; '
                'все подписи округлены ВВЕРХ до 5 мм. При несовпадении фактических обмеров и расчётного профиля '
                f'расхождение высоты по уклону = {section["ridge_pitch_difference_mm"]:+.1f} мм. '
                'Схема требует проверки и корректировки проектировщиком.')

    def export_attic_dxf(self):
        from attic_cad_export import write_attic_plan_dxf
        try:
            outer=self._attic_outline();inner=self._inner_outline();ridge,pitch=self._roof_height()
        except Exception as e:
            messagebox.showwarning('Экспорт чердака DXF',str(e));return
        path=filedialog.asksaveasfilename(title='DXF: план чердака',defaultextension='.dxf',filetypes=[('AutoCAD DXF','*.dxf')])
        if not path:return
        try:
            write_attic_plan_dxf(path,outer,inner,self.shaft_catalog,self.shaft_instances,self.wall_thickness_mm,self.wall_above_slag_mm,ridge,pitch)
            self.status.set('План чердака DXF: '+path)
        except Exception as e:messagebox.showerror('DXF чердака',str(e))

    def export_section_dxf(self):
        from attic_cad_export import write_section_dxf
        try:
            outer=self._attic_outline();ridge,pitch=self._roof_height()
            eave=float(self.values['eave'].get().replace(',','.'))
        except Exception as e:
            messagebox.showwarning('Экспорт разреза DXF',str(e));return
        path=filedialog.asksaveasfilename(title='DXF: разрез 1–1',defaultextension='.dxf',filetypes=[('AutoCAD DXF','*.dxf')])
        if not path:return
        try:
            write_section_dxf(path,outer,self.section_cut_x_m,self.wall_above_slag_mm,ridge,pitch,eave,self.shaft_catalog,self.shaft_instances)
            self.status.set('Разрез DXF: '+path)
        except Exception as e:messagebox.showerror('DXF разреза',str(e))

    def recalc(self):
        # A single datum for the complex-roof model and attic section:
        # roof eave starts at measured top of attic wall above slag.
        if self.custom_outline and 'eave_height' in self.values:
            self.values['eave_height'].set(f'{self.wall_above_slag_mm/1000:.4f}')
        super().recalc()
        if self.attic_canvas and self.attic_canvas.winfo_exists():self._render_attic()
        if self.section_canvas and self.section_canvas.winfo_exists():self._render_section()

    def _attic_data(self):
        return {'material':self.wall_material,'preset':self.wall_preset,'wall_mm':self.wall_thickness_mm,
                'wall_above_slag_mm':self.wall_above_slag_mm,'section_cut_x_m':self.section_cut_x_m,
                'shaft_catalog':self.shaft_catalog,'shaft_instances':self.shaft_instances}

    def save(self,asnew=False):
        # Preserve prior project schema, update attic data as an extra top-level key.
        if getattr(self,'attic_vars',None) and getattr(self,'tab',None)=='Чердак':
            self._apply_attic_settings()
        path=None if asnew else self.path
        if not path:path=filedialog.asksaveasfilename(title='Сохранить проект',defaultextension='.roof.json',filetypes=[('Проект RoofStudio','*.json')])
        if not path:return
        data={'version':'0.8','roof_type':self.roof_type_choice,'parameters':{k:v.get() for k,v in self.values.items()},
              'objects':self.objects,'outline':{'enabled':self.custom_outline,'points':self.outline_points,
                'closed':self.outline_closed,'manual_ridges':self.manual_ridges},'attic':self._attic_data()}
        try:
            Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            self.path=path;self.status.set('Проект сохранён: '+path)
        except OSError as e:messagebox.showerror('Сохранение',str(e))

    def load(self):
        path=filedialog.askopenfilename(title='Открыть проект',filetypes=[('Проект RoofStudio','*.json')])
        if not path:return
        try:
            data=json.loads(Path(path).read_text(encoding='utf-8'))
            params=data.get('parameters',data)
            for k in self.values:
                if k in params:self.values[k].set(str(params[k]))
            self.objects=[o for o in data.get('objects',[]) if isinstance(o,dict) and {'type','x','y'}<=o.keys()]
            out=data.get('outline',{})
            self.roof_type_choice=data.get('roof_type','Вальмовая')
            if hasattr(self,'roof_choice'):self.roof_choice.set(self.roof_type_choice)
            self.custom_outline=bool(out.get('enabled',False))
            self.outline_points=[[float(x),float(y)] for x,y in out.get('points',[])]
            self.outline_closed=bool(out.get('closed',False))
            self.manual_ridges=[[[float(x),float(y)] for x,y in seg] for seg in out.get('manual_ridges',[])]
            if len(self.outline_points)>500 or len(self.manual_ridges)>500:raise ValueError('Слишком большой проект')
            attic=data.get('attic',{})
            self.wall_material=attic.get('material','Кирпичный')
            self.wall_preset=attic.get('preset','Кирпич 510 мм')
            self.wall_thickness_mm=float(attic.get('wall_mm',510))
            self.wall_above_slag_mm=float(attic.get('wall_above_slag_mm',400))
            self.section_cut_x_m=float(attic.get('section_cut_x_m',10))
            self.shaft_catalog=[dict(x) for x in attic.get('shaft_catalog',DEFAULT_SHAFT_CATALOG)]
            self.shaft_instances=[dict(x) for x in attic.get('shaft_instances',[])]
            if len(self.shaft_catalog)>300 or len(self.shaft_instances)>1000:raise ValueError('Слишком большой каталог/план ВШ')
            self.path=path
            self.recalc()
            self.switch('Контур здания' if self.custom_outline else 'Геометрия')
            self.status.set('Открыт проект: '+path)
        except (OSError,ValueError,TypeError,KeyError) as e:messagebox.showerror('Открытие',str(e))

    def new(self):
        if not messagebox.askyesno('Новый проект','Очистить текущие данные и создать новый проект?'):return
        self.objects=[];self.selected=None;self.path=None
        for k,v in self._defaults_for_new().items():self.values[k].set(str(v))
        self.custom_outline=False;self.outline_points=[];self.outline_closed=False;self.manual_ridges=[]
        self.complex_roof=None;self.roof_type_choice='Вальмовая'
        if hasattr(self,'roof_choice'):self.roof_choice.set('Вальмовая')
        self.wall_material='Кирпичный';self.wall_preset='Кирпич 510 мм';self.wall_thickness_mm=510
        self.wall_above_slag_mm=400;self.section_cut_x_m=10
        self.shaft_catalog=[dict(t) for t in DEFAULT_SHAFT_CATALOG]
        self.shaft_instances=[];self.attic_selected=None;self.current_shaft_id='vsh1'
        self.recalc();self.switch('Геометрия')

    def fill_table(self):
        super().fill_table()
        table=getattr(self,'data_table',None)
        if table is None or not table.winfo_exists():return
        try:
            inner=self._inner_outline();outer=self._attic_outline()
        except Exception:return
        table.insert('','end',values=('Чердак','Площадь по внутреннему контуру',f'{polygon_area(inner):.2f}','м²'))
        table.insert('','end',values=('Чердак','Толщина наружных стен',f'{self.wall_thickness_mm:g}','мм'))
        ridge,pitch=self._roof_height()
        qty_total={'cladding_above_roof_m2':0,'insulation_above_roof_m3':0,'insulation_attic_m3':0,
                   'shaft_wall_volume_above_roof_m3':0,'shaft_wall_volume_full_m3':0}
        for inst in self.shaft_instances:
            t=self._type(inst['type_id'])
            if not t:continue
            try:
                q=shaft_quantities(inst,t,outer,self.wall_above_slag_mm,ridge,pitch)
            except ValueError:continue
            table.insert('','end',values=('Вентшахта',t['code']+' — верх от шлака',q['top_from_slag_rounded_mm'],'мм'))
            for k in qty_total:qty_total[k]+=q[k]
        table.insert('','end',values=('ВШ','Обшивка ВШ над кровлей (без запаса)',f'{qty_total["cladding_above_roof_m2"]:.2f}','м²'))
        table.insert('','end',values=('ВШ','Утеплитель над кровлей (без запаса)',f'{qty_total["insulation_above_roof_m3"]:.3f}','м³'))
        table.insert('','end',values=('ВШ','Утеплитель шахт в чердаке (без запаса)',f'{qty_total["insulation_attic_m3"]:.3f}','м³'))
        table.insert('','end',values=('ВШ','Объём материала стен ВШ выше кровли',f'{qty_total["shaft_wall_volume_above_roof_m3"]:.3f}','м³'))
        table.insert('','end',values=('ВШ','Объём стен шахт от шлака до верха',f'{qty_total["shaft_wall_volume_full_m3"]:.3f}','м³'))
