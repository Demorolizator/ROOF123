"""Headless smoke checks. GUI checks require Xvfb on Linux."""
import json, os, sys, tempfile
from pathlib import Path
from attic_model import (ceil5, offset_polygon_inward, polygon_area, shaft_quantities,
                         section_geometry, validate_shaft_placement)
from attic_ui import DEFAULT_SHAFT_CATALOG
from complex_roof import generate_roof_geometry
from attic_cad_export import write_attic_plan_dxf,write_section_dxf

L = [(0,0),(20,0),(20,7),(12,7),(12,14),(0,14)]
inner=offset_polygon_inward(L,.510)
assert abs(polygon_area(L)-224)<1e-9
assert abs(polygon_area(inner)-190.3604)<1e-6
assert ceil5(3100)==3100 and ceil5(3100.1)==3105 and ceil5(3099.9999999999)==3100
inst={'type_id':'vsh1','x':4.,'y':3.,'rotation':0}
assert validate_shaft_placement(inst,DEFAULT_SHAFT_CATALOG[0],inner)
r=shaft_quantities(inst,DEFAULT_SHAFT_CATALOG[0],L,400,3250,28.0)
assert r['top_from_slag_rounded_mm']>=r['top_from_slag_raw_mm']
assert r['above_roof_rounded_mm']==800
assert abs(r['cladding_above_roof_m2']-1.6)<1e-10
sc=section_geometry(L, 5,400,3250,28,.6)
assert abs(sc['span_m']-14)<1e-7
roof=generate_roof_geometry(L,[],.4,3.25,28)
assert len(roof['planes'])>=4
with tempfile.TemporaryDirectory() as temp:
    p=Path(temp)/'attic.dxf'
    write_attic_plan_dxf(p,L,inner,DEFAULT_SHAFT_CATALOG,[inst],510,400,3250,28)
    assert 'VENT_SHAFT' in p.read_text() and 'ATTIC_INNER' in p.read_text()
    p=Path(temp)/'section.dxf'
    write_section_dxf(p,L,4,400,3250,28,.6,DEFAULT_SHAFT_CATALOG,[inst])
    assert 'SHAFT_SECTION' in p.read_text()
print('Attic model and CAD exports passed')

if '--gui' in sys.argv:
    from roofstudio import RoofStudioV08
    app=RoofStudioV08()
    app.withdraw()
    app.update()
    for tab in ('Чердак','Каталог ВШ','Разрез 1–1','Геометрия','Контур здания','Чердак'):
        app.switch(tab)
        app.update()
    app.wall_thickness_mm=510
    app.switch('Чердак');app.update()
    app.shaft_instances.append({'type_id':'vsh1','x':5,'y':4,'rotation':0})
    app._render_attic()
    app.section_cut_x_m=5
    app.switch('Разрез 1–1');app.update()
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'test.roof.json'
        # avoid dialogs
        app.path=str(path)
        app.save()
        data=json.loads(path.read_text(encoding='utf-8'))
        assert data['version']=='0.8'
        assert len(data['attic']['shaft_instances'])==1
        assert data['attic']['wall_mm']==510
    app.destroy()
    print('GUI smoke test passed')
