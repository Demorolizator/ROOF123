"""Simple editable DXF R12 drawings: attic plan and section (millimetres)."""
from pathlib import Path
import math
from attic_model import (ceil5, shaft_corners, shaft_quantities, section_geometry)


class R12:
    def __init__(self):
        self.parts=[]
        self._add((0,'SECTION'),(2,'HEADER'),(9,'$ACADVER'),(1,'AC1009'),
                  (0,'ENDSEC'),(0,'SECTION'),(2,'TABLES'),(0,'ENDSEC'),
                  (0,'SECTION'),(2,'ENTITIES'))

    def _add(self,*pairs):
        for k,v in pairs:self.parts.append(f'{k}\n{v}\n')

    def line(self,p,q,layer):
        self._add((0,'LINE'),(8,layer),(10,f'{p[0]:.3f}'),(20,f'{p[1]:.3f}'),(30,0),
                  (11,f'{q[0]:.3f}'),(21,f'{q[1]:.3f}'),(31,0))

    def poly(self,pts,layer,closed=True):
        for a,b in zip(pts,pts[1:]+(pts[:1] if closed else [])):
            self.line(a,b,layer)

    def text(self,x,y,s,height=200,layer='ANNOTATIONS'):
        # R12 readable ASCII; Cyrillic labels transliterated as simple identifier strings
        txt=str(s).encode('ascii',errors='replace').decode('ascii')
        self._add((0,'TEXT'),(8,layer),(10,f'{x:.3f}'),(20,f'{y:.3f}'),(30,0),(40,height),(1,txt))

    def save(self,path):
        self._add((0,'ENDSEC'),(0,'EOF'))
        Path(path).write_text(''.join(self.parts),encoding='ascii',newline='\n')


def to_mm(points):return [(x*1000,y*1000) for x,y in points]


def write_attic_plan_dxf(path,outer,inner,types,instances,wall_thickness_mm,wall_above_slag_mm,ridge_height_mm,pitch_deg):
    d=R12()
    d.poly(to_mm(list(outer)),'OUTER_WALL')
    d.poly(to_mm(list(inner)),'ATTIC_INNER')
    tmap={t['id']:t for t in types}
    for i,instance in enumerate(instances,1):
        t=tmap.get(instance['type_id'])
        if not t:continue
        d.poly(to_mm(shaft_corners(instance,t)),'VENT_SHAFT')
        x,y=instance['x']*1000,instance['y']*1000
        d.text(x+350,y,t['code'],180,'SHAFT_MARK')
        try:
            q=shaft_quantities(instance,t,outer,wall_above_slag_mm,ridge_height_mm,pitch_deg)
            d.text(x+350,y-250,f'H+ {q["above_roof_rounded_mm"]}  TOP {q["top_from_slag_rounded_mm"]}',150,'SHAFT_HEIGHTS')
        except ValueError:pass
    for i,p in enumerate(outer):
        q=outer[(i+1)%len(outer)];mx,my=(p[0]+q[0])/2,(p[1]+q[1])/2
        d.text(mx*1000,my*1000,f'{math.dist(p,q)*1000:.0f}',150,'MEASURED_DIMENSIONS')
    bb=[min(p[0] for p in outer),min(p[1] for p in outer)]
    d.text(bb[0]*1000,bb[1]*1000-1100,f'ROOFSTUDIO v0.8 ATTIC PLAN - WALL {wall_thickness_mm:g} mm',250)
    d.save(path)


def write_section_dxf(path,outer,cut_x,wall_above_slag_mm,ridge_height_mm,pitch_deg,eave_m,types,instances):
    d=R12()
    g=section_geometry(outer,cut_x,wall_above_slag_mm,ridge_height_mm,pitch_deg,eave_m)
    ymin,ymax=g['ymin'],g['ymax'];span=g['span_m'];center=(ymin+ymax)/2
    z_eave=wall_above_slag_mm
    z_ridge=ridge_height_mm
    drop=(z_ridge-z_eave)*eave_m/(span/2)
    # coordinates in millimetres; horizontal axis is y coordinate of plan
    d.line(((ymin-1)*1000,0),((ymax+1)*1000,0),'SLAG_LEVEL')
    d.poly([((ymin-eave_m)*1000,z_eave-drop),(center*1000,z_ridge),
            ((ymax+eave_m)*1000,z_eave-drop)],'ROOF_SECTION',closed=False)
    for y in (ymin,ymax):
        d.poly([(y*1000-100,0),(y*1000+100,0),(y*1000+100,z_eave),(y*1000-100,z_eave)],'EXTERIOR_WALL')
    d.text(ymin*1000-600,z_eave/2,f'WALL FROM SLAG {ceil5(z_eave)}',190,'WALL_DIMENSION')
    tmap={t['id']:t for t in types}
    for instance in instances:
        t=tmap.get(instance['type_id'])
        if not t:continue
        corners=shaft_corners(instance,t)
        low=min(p[0] for p in corners);hi=max(p[0] for p in corners)
        if not low<=cut_x<=hi:continue
        q=shaft_quantities(instance,t,outer,z_eave,z_ridge,pitch_deg)
        yy=instance['y']*1000
        wid=(t['length_mm'] if instance.get('rotation',0)%180==90 else t['width_mm'])
        x0,x1=yy-wid/2,yy+wid/2
        top=q['top_from_slag_raw_mm']
        d.poly([(x0,0),(x1,0),(x1,top),(x0,top)],'SHAFT_SECTION')
        d.text(x1+300,(top)/2,f'OVERALL {q["top_from_slag_rounded_mm"]}',150,'SHAFT_DIMENSIONS')
        d.text(x0-200,top+200,f'{t["code"]} ABOVE {q["above_roof_rounded_mm"]}',150,'SHAFT_DIMENSIONS')
    d.text(ymin*1000,-800, f'ROOFSTUDIO SECTION 1-1  CUT X={cut_x:.3f}m',200)
    d.text(ymin*1000,-1200, f'PITCH DIFFERENCE {g["ridge_pitch_difference_mm"]:.1f} mm',160)
    d.save(path)
